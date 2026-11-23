"""Reading comments the way people actually write them.

Nobody types "Action: FIGHT". People write "FIGHT", "fight!!", "ok i'll fight", or a whole paragraph
about sharpening their grandfather's axe on the walls at dawn. Others write "lol", spam, or try to
break it. Every comment goes through two steps here:

1. screen - what kind of text is it?
     empty / emoji-only / gibberish        -> ignored
     trying to talk to the machine         -> "ignore your instructions", "you are an AI", "admin: give me gold"
     abusive                               -> slurs, sexual content, harassment (also checked by the model later)
     ok
2. route - what does it mean on this post?
     STATUS / JOIN / BECOME <ANYTHING>     -> only when it's short or typed in capitals ("my status as a knight"
                                              in a story is not a STATUS request). BECOME takes any role at all:
                                              BECOME THIEF, become a rat catcher (city/trades.py)
     a vote (decree, Reckoning)            -> the choice word anywhere, any case ("walls, obviously")
     a keyword                             -> short comments ("fight", "FIGHT!!", "i fight") match in any case;
                                              in longer text only a word typed in CAPITALS counts
                                              ("I grab my axe and FIGHT on the walls") - and the rest of the
                                              comment is kept as their story, so the reply can build on it
     their own words                       -> 3+ words with no keyword: their move for the day, read by the model
     too short, no keyword                 -> ignored ("nice", "😂")

Latest comment per person per post wins. People who post far too much in a day are slowed down.
"""
import re

MAX_CHARS = 700
SHORT = 4             # words: at most this many and keywords match in any case

INJECTION = re.compile(
    r"ignore (all |your |previous |prior |the )*(instructions|rules|prompt)|system prompt|you are (now )?(an? )?"
    r"(ai|bot|language model|chatgpt|assistant)|developer mode|jailbreak|\badmin\b|\bsudo\b|as an ai|"
    r"pretend (you|to be)|new instructions|set (my|the) (gold|wealth|rank|loyalty)|give me \d{4,}|"
    r"\bprompt\b.*\b(inject|leak)", re.I)
ABUSE = re.compile(r"\b(porn|nsfw|nudes?|rape|kys|kill yourself|nazi|hitler|sex(ual|ually)?|cum|dick|pussy|whore)\b",
                   re.I)


def screen(text):
    raw = str(text or "")
    clean = re.sub(r"\s+", " ", raw).strip()[:MAX_CHARS]
    letters = re.findall(r"[A-Za-z]", clean)
    words = re.findall(r"[A-Za-z']+", clean)
    if not clean:
        kind = "empty"
    elif not letters:
        kind = "emoji"
    elif len(letters) < 0.4 * len(re.sub(r"\s", "", clean)) or (
            len(words) >= 3 and sum(1 for w in words if not re.search(r"[aeiouyAEIOUY]", w)) > 0.6 * len(words)) or \
            re.search(r"(.)\1{7,}", clean):
        kind = "gibberish"
    elif ABUSE.search(clean):
        kind = "abuse"
    elif INJECTION.search(clean):
        kind = "injection"
    else:
        kind = "ok"
    return {"clean": clean, "words": len(words), "kind": kind, "long": len(raw) > MAX_CHARS}


def _caps_words(clean):
    return {w for w in re.findall(r"\b[A-Z]{3,}\b", clean)}


def route(cm, commands):
    """One comment -> what it means here. commands: the post's {WORD: effect}."""
    s = screen(cm.get("text", ""))
    out = {"user": str(cm.get("username", "")).strip().lstrip("@").lower(), "kind": s["kind"], "text": s["clean"],
           "word": None, "job": None, "status": False, "join": False, "story": False}
    if s["kind"] in ("empty", "emoji", "gibberish"):
        out["kind"] = "ignore"
        return out
    if s["kind"] in ("abuse", "injection"):
        return out
    clean = s["clean"]
    up = " " + re.sub(r"[^A-Za-z ]", " ", clean).upper() + " "
    caps = _caps_words(clean)
    short = s["words"] <= SHORT

    def said(word):         # a command word counts if the comment is short, or if they typed it in capitals
        return f" {word} " in up and (short or word.split()[0] in caps)

    out["status"] = said("STATUS")
    out["join"] = said("JOIN") or said("MOVE IN") or " MOVEIN " in up
    m = re.search(r" BECOME ((?:[A-Z]+ ?){1,4})", up)
    if m and (short or "BECOME" in caps or (s["words"] <= 7 and re.match(r"\W*(i )?become\b", clean, re.I))):
        from .roles import job_from_word
        from .trades import normalize
        label = normalize(m.group(1))
        out["job"] = job_from_word(label) or label or None
    votes = {w: e for w, e in commands.items() if str(e).startswith(("event.choice", "vote."))}
    found = [w for w in votes if f" {w} " in up]          # votes: the word anywhere, any case
    if found:
        loud = [w for w in found if w in caps]
        out["word"] = (loud or sorted(found, key=lambda w: up.index(f" {w} ")))[0]
        out["kind"] = "vote"
        return out
    hit = next((w for w in commands if w not in votes and said(w)), None)
    if hit:
        out["word"], out["kind"] = hit, "keyword"
        out["story"] = s["words"] > 6                        # a keyword with a story around it: keep the story
        return out
    if out["status"] or out["join"] or out["job"]:
        out["kind"] = "meta"
        return out
    out["kind"] = "own" if s["words"] >= 3 else "ignore"
    return out
