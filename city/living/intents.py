"""Subjects in their own words - including to each other.

A comment that isn't one of the post's words is that subject's move for the day:
  "I sneak into the castle kitchens to steal bread for my kids"
  "I rob @jordan.2781 while he's asleep"
  "I challenge @finley_pgh5426 to a duel for insulting my mother"
  "I give @riley_9029 my best hammer"
  "I beg the king for a job as his food taster"

Three steps, so the dice are fair and the story is good:
  1. read  - the model (or the rules) works out what they're trying: an action and maybe a target
  2. roll  - the game decides what happens from both characters' stats and some luck (code, not the model)
  3. tell  - the model narrates one sentence of what happened, given the result
Nobody dies. Fights leave the loser WOUNDED for a day or two; people caught breaking the law go to the
dungeon (or the stocks, if the king hasn't built one) and onto the king's docket. A target can only be
hit by a couple of hostile acts a day. Two people who keep clashing become a FEUD.

Comments are processed through the day in the living world (hourly), so the king hears about them as
they happen. The GPU budget decides how many get the model; the rest get the rules.
"""
import math
import re

import numpy as np

from ..effects import COMMAND_EFFECTS
from ..roles import FACTIONS, JOB_NAMES
from . import life

SIM = ["work", "shop", "train", "protest", "volunteer", "donate", "support", "oppose", "event.help", "event.hinder"]
SOCIAL = ["steal", "attack", "gift", "befriend", "insult"]
ACTIONS = SIM + SOCIAL + ["petition", "gift_king", "none"]
HOSTILE = {"steal", "attack", "insult"}
SIM_OF = {"gift": "donate", "befriend": "volunteer", "petition": "support", "gift_king": "support"}   # what a social act counts as in the sim

RULES = [  # (pattern, action) - first match wins
    (r"\b(steal|rob|pickpocket|swipe|loot)\b.*@|@\S+.*\b(steal|rob|pickpocket)\b", "steal"),
    (r"\b(attack|punch|fight|kill|stab|duel|challenge|slap|tackle|beat up|murder)\b.*@|@\S+.*\b(attack|duel|fight)\b",
     "attack"),
    (r"\b(give|gift|send|pay|lend|share)\b.*@", "gift"),
    (r"\b(insult|mock|laugh at|roast|curse|spit on)\b.*@", "insult"),
    (r"@\S+", "befriend"),
    (r"\b(give|send|gift|bring|offer|make)\b.*\bking\b|\bking\b.*\b(a gift|present)\b", "gift_king"),
    (r"\b(ask|beg|petition|request|plead|suggest|propose)\b.*\bking\b|\bking\b.*\b(ask|beg|petition|request|job|should)\b",
     "petition"),
    (r"\b(fight|defend|guard|protect|rescue|save|charge|battle|slay|shoot|barricade)\b", "event.help"),
    (r"\b(steal|rob|sabotage|flee|run away|hide|betray|loot|desert)\b", "event.hinder"),
    (r"\b(train|drill|practice|spar|sharpen|enlist)\b", "train"),
    (r"\b(protest|riot|complain|yell|grumble|march|strike)\b", "protest"),
    (r"\b(praise|cheer|kneel|toast|serve the king|bow)\b", "support"),
    (r"\b(mock|insult|hate|boo|laugh at the king|overthrow)\b", "oppose"),
    (r"\b(give|donate|share|feed the poor|charity|pray)\b", "donate"),
    (r"\b(help|volunteer|build|repair|clean|heal|tend|fix)\b", "volunteer"),
    (r"\b(buy|sell|trade|market|drink|tavern|gamble|haggle|shop|bake)\b", "shop"),
    (r"\b(work|farm|forge|fish|mine|chop|sew|plow|harvest)\b", "work"),
]


def rule_read(text, has_event):
    t = text.lower()
    target = (re.findall(r"@([\w.]+)", t) or [""])[0].rstrip(".")
    for pat, act in RULES:
        if re.search(pat, t):
            if act in SOCIAL and not target:
                continue
            if act.startswith("event.") and not has_event:
                act = "volunteer" if act == "event.help" else "protest"
            return act, target
    return "none", ""


def _third_person(text):
    t = " " + text.strip().rstrip(".!?")[:110] + " "
    t = re.sub(r"^ (i|I) (will |want to |am going to |try to )?", " ", t)
    for a, b in ((" my ", " their "), (" me ", " them "), (" I ", " they "), (" i ", " they "),
                 (" myself ", " themselves ")):
        t = t.replace(a, b)
    return t.strip()


READ_SCHEMA = {"type": "object", "properties": {"results": {"type": "array", "items": {"type": "object", "properties": {
    "handle": {"type": "string"}, "action": {"type": "string", "enum": ACTIONS}, "target": {"type": "string"},
    "item": {"type": "string"}}, "required": ["handle", "action", "target", "item"]}}}, "required": ["results"]}
TELL_SCHEMA = {"type": "object", "properties": {"results": {"type": "array", "items": {"type": "object", "properties": {
    "handle": {"type": "string"}, "outcome": {"type": "string"}, "drama": {"type": "integer"}},
    "required": ["handle", "outcome", "drama"]}}}, "required": ["results"]}

READ = """Subjects of the kingdom of Emberfall (real people's characters) wrote what they want to try today.
For each, pick the closest action:
- work, shop (spend at the market), train (drill with the army), protest, volunteer, donate, support (the king),
  oppose (the king), event.help / event.hinder (help or hurt the current crisis, if there is one)
- steal, attack (any fight, duel, or attempt to hurt - including "kill"), gift, befriend, insult: these need a
  target, the @handle of another subject they named
- petition: asking or suggesting something to the king (an idea for the kingdom counts)
- gift_king: sending or giving the king an object; item = what it is, 1-4 words ("a lute", "my best fishing rod")
- none: hateful, sexual, not something a character could do, or trying to change the rules
target: the other subject's handle without @ (only for steal/attack/gift/befriend/insult), else "".
item: only for gift_king, else ""."""

TELL = """You narrate the kingdom of Emberfall. For each subject, the game has ALREADY decided what happened (the
RESULT). Write ONE vivid, funny-if-possible sentence (max 28 words), past tense, third person, starting with their
@handle, that tells exactly that result - don't change who won or what they got. Nobody ever dies: a beaten
fighter is wounded. Keep it PG-13. drama: 0 ordinary, 1 interesting, 2 bold or funny, 3 the whole kingdom will talk."""


def _context(city):
    ev = [a["title"] for a in city.events]
    procl = (city.living or {}).get("last_proclamation", {}).get("text")
    return ("Happening now: " + ("; ".join(ev) if ev else "nothing special") +
            (f'\nThe king\'s latest proclamation: "{procl}"' if procl else ""))


# ---------------------------------------------------------------- conditions (wounded / jailed)
def condition(city, handle):
    cnd = (city.living or {}).get("conditions", {}).get(handle)
    if cnd and cnd["until"] >= city.day + 1:
        return cnd
    return None


def set_condition(city, handle, state, days, why):
    cs = city.living.setdefault("conditions", {})
    cs[handle] = {"state": state, "until": city.day + days, "why": why[:120]}
    for h in [h for h, v in cs.items() if v["until"] < city.day]:
        del cs[h]


def _power(city, i):
    c = city.citizens
    rank = {"Freeman": 0.1, "Squire": 0.25, "Knight": 0.5}.get(c.rank(i), 0)
    return (1 + 0.6 * (int(c.faction[i]) == FACTIONS.index("army")) + 0.08 * min(10, int(c.counts["battles"][i]))
            + rank + 0.2 * float(c.mood[i]))


def _bond(city, a, b, delta):
    key = "|".join(sorted((a, b)))
    bonds = city.living.setdefault("bonds", {})
    bonds[key] = bonds.get(key, 0) + delta
    if len(bonds) > 3000:
        for k in list(bonds)[:500]:
            del bonds[k]
    return bonds[key]


# ---------------------------------------------------------------- 2. roll
def resolve(world, r, hostile_today):
    """The game decides. Fills r['facts'] (for the narrator) and r['drama_floor']."""
    city, c, rng = world.city, world.city.citizens, world.city.rng
    act, u, t = r["action"], r["user"], r.get("target", "")
    i = c.index[u]
    j = c.index.get(t) if t else None
    r["drama_floor"] = 0
    if act in SOCIAL:
        if j is None or t == u or c.status[j] != 0:
            r["action"], r["facts"] = "none", ""
            return
        if act in HOSTILE:
            hostile_today[t] = hostile_today.get(t, 0) + 1
            if hostile_today[t] > 2:
                r["facts"] = f"tried to {act} @{t}, but the guards were already watching @{t}'s house; nothing happened"
                return
        cnd = condition(city, t)
        if cnd and cnd["state"] == "jailed" and act in ("steal", "attack"):
            r["facts"] = f"went after @{t}, but @{t} is locked up; the guards turned them away"
            return
    jail = "the dungeon" if city.living["town"]["rooms"].get("dungeon") else "the stocks in the square"
    if act == "steal":
        p = 0.55 - 0.25 * (city.quality["defense"] - 0.8) - 0.15 * (int(c.faction[j]) == FACTIONS.index("army"))
        ok = rng.random() < p
        caught = rng.random() < (0.2 if ok else 0.6)
        amount = round(min(float(c.wealth[j]) * 0.15, 60.0)) if ok else 0
        if ok:
            c.wealth[j] -= amount
            c.wealth[i] += amount
            c.log(j, city.day + 1, f"was robbed of {amount} gold by @{u}")
        c.mood[j] = max(0.0, c.mood[j] - 0.05)
        r["facts"] = (f"stole from @{t}: {'SUCCESS, took ' + str(amount) + ' gold' if ok else 'FAILED'}"
                      + (f"; CAUGHT by the guards and sent to {jail}" if caught else "; got away"))
        if caught:
            set_condition(city, u, "jailed", 1, f"caught stealing from @{t}")
            life.add_case(city, "crime", u, f"@{u} was caught stealing from @{t}")
        _bond(city, u, t, -1)
        r["drama_floor"] = 2 if (ok or caught) else 1
    elif act == "attack":
        pa, pt = _power(city, i) * rng.uniform(0.6, 1.4), _power(city, j) * rng.uniform(0.6, 1.4)
        won = pa > pt
        loser, winner = (t, u) if won else (u, t)
        bad = bool(re.search(r"\b(kill|murder|stab|slay)\b", r.get("text", "").lower()))
        days = 2 if bad else 1
        set_condition(city, loser, "wounded", days, f"lost a fight with @{winner}")
        li, wi = c.index[loser], c.index[winner]
        c.mood[li] = max(0.0, c.mood[li] - 0.08)
        c.mood[wi] = min(1.0, c.mood[wi] + 0.03)
        arrested = rng.random() < (0.35 + (0.25 if not won else 0) + (0.2 if bad else 0))
        c.log(j, city.day + 1, f"was attacked by @{u} and {'lost' if won else 'won'}")
        r["facts"] = (f"attacked @{t} and {'WON' if won else 'LOST'}; @{loser} is {'badly ' if bad else ''}wounded "
                      f"for {days} day{'s' if days > 1 else ''} (nobody dies)"
                      + (f"; @{u} was ARRESTED and dragged to {jail}" if arrested else ""))
        if arrested:
            set_condition(city, u, "jailed", 2, f"attacked @{t}")
            life.add_case(city, "crime", u, f"@{u} attacked @{t}" + (" and tried to kill them" if bad else ""))
        hostility = _bond(city, u, t, -2)
        r["drama_floor"] = 2
        if hostility <= -5 and not world.recent_feud(u, t):
            world.moment("world", f"The feud between @{u} and @{t} is now the talk of the kingdom.", 3,
                         public=True, handles=[u, t])
    elif act == "gift":
        num = re.findall(r"\b(\d{1,4})\b", r.get("text", ""))
        amount = min(float(num[0]) if num else float(c.wealth[i]) * 0.1, float(c.wealth[i]) * 0.5, 200.0)
        amount = round(max(0.0, amount))
        c.wealth[i] -= amount
        c.wealth[j] += amount
        c.mood[j] = min(1.0, c.mood[j] + 0.05)
        c.log(j, city.day + 1, f"got a gift from @{u}")
        _bond(city, u, t, 2)
        r["facts"] = f"gave @{t} a gift" + (f" (and {amount:.0f} gold)" if amount else "")
        r["drama_floor"] = 1
    elif act == "befriend":
        c.mood[i] = min(1.0, c.mood[i] + 0.03)
        c.mood[j] = min(1.0, c.mood[j] + 0.03)
        _bond(city, u, t, 1)
        r["facts"] = f"spent time with @{t}; they get along"
    elif act == "insult":
        c.mood[j] = max(0.0, c.mood[j] - 0.03)
        _bond(city, u, t, -1)
        r["facts"] = f"insulted @{t} in public"
        r["drama_floor"] = 1
    elif act == "petition":
        life.add_case(city, "petition", u, f"@{u}: {r.get('text', '')[:160]}")
        log = city.living.setdefault("petitions_log", [])
        log.append({"who": u, "text": r.get("text", "")[:200], "day": city.day + 1})
        del log[:-60]
        r["facts"] = "went to the castle to petition the king; they'll be heard at court"
        r["drama_floor"] = 1
    elif act == "gift_king":
        item = re.sub(r"[^a-zA-Z' -]", "", r.get("item") or "").strip()[:40] or "a small gift"
        king = world.agent("king")
        inv = king.setdefault("life", life.new_life()).setdefault("inventory", [])
        inv.append({"item": item, "from": u, "day": city.day + 1, "used": 0})
        del inv[:-20]
        r["facts"] = f"sent the king a gift: {item}. It's waiting for him at the castle gate"
        world.moment("world", f"A gift arrived at the castle from @{u}: {item}.", 1, public=True, handles=[u])
        r["drama_floor"] = 1
    elif act == "none":
        r["facts"] = ""
    else:
        r["facts"] = f"did this: {act}"


# ---------------------------------------------------------------- the whole thing
def process(world, free, llm=None, ai_people=0):
    """free: {username: text}. Runs read -> roll -> tell. ai_people = how many may use the model (the budget)."""
    city, c = world.city, world.city.citizens
    lv = city.living
    acted = set(lv.setdefault("acted_today", []))
    hostile_today = lv.setdefault("hostile_today", {})
    has_event = bool(city.events)
    out = []
    users = [u for u in free if u in c.index and u not in acted and c.status[c.index[u]] == 0]
    city.rng.shuffle(users)
    for u in [u for u in users if condition(city, u)]:
        cnd = condition(city, u)
        out.append({"user": u, "text": free[u], "action": "none", "drama": 0, "target": "",
                    "outcome": f"@{u} is {'locked up' if cnd['state'] == 'jailed' else 'still wounded'} "
                               f"({cnd['why']}) and can't do anything today."})
    users = [u for u in users if not condition(city, u)]
    ai = users[:ai_people] if llm else []
    reads = {}
    for k in range(0, len(ai), 8):          # 1. read
        batch = ai[k:k + 8]
        lines = [f"@{u} ({JOB_NAMES[int(c.job[c.index[u]])]} of {city.wards[int(c.ward[c.index[u]])]['name']}): "
                 f"{free[u]}" for u in batch]
        try:
            res = llm.json(READ, _context(city) + "\n\nSubjects:\n" + "\n".join(lines), READ_SCHEMA,
                           max_tokens=60 * len(batch), temperature=0.3)["results"]
            for x in res:
                h = str(x.get("handle", "")).lstrip("@").lower()
                if h in batch and x.get("action") in ACTIONS:
                    reads[h] = (x["action"], str(x.get("target", "")).lstrip("@").lower().rstrip("."),
                                str(x.get("item", "")))
        except Exception:
            world.stats["crowd_fallbacks"] = world.stats.get("crowd_fallbacks", 0) + 1
        world.spend_calls(1)
    results = []
    for u in users:                          # 2. roll
        act, tgt, item = reads.get(u) or (*rule_read(free[u], has_event), _rule_item(free[u]))
        if act.startswith("event.") and not has_event:
            act = "volunteer" if act == "event.help" else "protest"
        r = {"user": u, "text": free[u], "action": act, "target": tgt, "item": item}
        resolve(world, r, hostile_today)
        results.append(r)
    told = {}
    ai_set = set(ai)
    tell = [r for r in results if r["user"] in ai_set and r["facts"]]
    for k in range(0, len(tell), 8):         # 3. tell
        batch = tell[k:k + 8]
        lines = [f"@{r['user']} wanted: {r['text']}\n   RESULT: @{r['user']} {r['facts']}" for r in batch]
        try:
            res = llm.json(TELL, "\n".join(lines), TELL_SCHEMA, max_tokens=90 * len(batch), temperature=0.9)["results"]
            for x in res:
                told[str(x.get("handle", "")).lstrip("@").lower()] = x
        except Exception:
            world.stats["crowd_fallbacks"] = world.stats.get("crowd_fallbacks", 0) + 1
        world.spend_calls(1)
    for r in results:
        x = told.get(r["user"])
        if x and x.get("outcome"):
            r["outcome"] = str(x["outcome"])[:240]
            r["drama"] = int(np.clip(int(x.get("drama", 0) or 0), r["drama_floor"], 3))
        else:
            r["outcome"] = _rule_tell(r)
            r["drama"] = r["drama_floor"]
    out += results
    for r in out:
        acted.add(r["user"])
        if r["outcome"] and r["action"] != "none":
            c.log(c.index[r["user"]], city.day + 1, r["outcome"].replace(f"@{r['user']} ", "", 1)[:160])
        if r["outcome"]:                      # they hear what came of it
            world.reply(r["user"], r["outcome"], "your_move")
        tgt = r.get("target")
        if tgt and r["action"] in SOCIAL and r["outcome"] and tgt in c.index:
            world.reply(tgt, f"Meanwhile: {r['outcome']}", "done_to_you")
    lv["acted_today"] = sorted(acted)
    lv.setdefault("crowd_today", []).extend({k: r.get(k, "") for k in ("user", "action", "outcome", "drama")} for r in out)
    for r in out:
        if r["outcome"] and r["drama"] >= 2:
            i = c.index[r["user"]]
            world.moment("@" + r["user"], r["outcome"], r["drama"], public=True,
                         hold=city.wards[int(c.ward[i])]["name"],
                         handles=[r["user"]] + ([r["target"]] if r.get("target") else []))
    return out


def _rule_item(text):
    m = re.search(r"\b(?:give|send|gift|bring|offer|make)s?\b.*?\bking\b\s+(?:a|an|my|some|the)?\s*([a-zA-Z' ]{2,30})",
                  text, re.I) or re.search(r"\b(?:a|an|my)\s+([a-zA-Z' ]{2,30}?)\s+(?:to|for)\s+the\s+king", text, re.I)
    return m.group(1).strip().rstrip(".") if m else ""


def _rule_tell(r):
    if not r.get("facts"):
        return ""
    if r["action"] in SOCIAL + ["petition"] or "guards" in r["facts"] or "locked up" in r["facts"]:
        return f"@{r['user']} {r['facts']}."
    return f"@{r['user']} tried to {_third_person(r['text'])}."


def finish_day(world, ctx, pack):
    """At the post's close: every own-words move of the day counts in the sim (like a keyword would)."""
    city, c = world.city, world.city.citizens
    lv = city.living
    groups = {}
    for r in lv.get("crowd_today", []):
        act = SIM_OF.get(r["action"], r["action"])
        if act in COMMAND_EFFECTS and r["user"] in c.index and c.status[c.index[r["user"]]] == 0:
            groups.setdefault(act, []).append(c.index[r["user"]])
    tallies = {}
    event = (pack or {}).get("event") or (city.events[-1]["id"] if city.events else None)
    for act, idx in groups.items():
        ctx.word = None
        idx = np.array(idx, np.int64)
        COMMAND_EFFECTS[act](city, idx, ctx, event if act.startswith("event.") else None)
        c.counts["commands"][idx] += 1
        c.last_cmd[idx] = city.day
        tallies[f"(own words) {act}"] = len(idx)
    for r in lv.get("crowd_today", []):
        if r["action"] in SOCIAL:
            tallies[f"(own words) {r['action']}"] = tallies.get(f"(own words) {r['action']}", 0) + 1
    lv["crowd_today"], lv["acted_today"], lv["hostile_today"] = [], [], {}
    return tallies


def calls_needed(n):
    return 2 * math.ceil(n / 8)
