"""The king as a person - who starts out as nobody in particular.

He begins with a name, a body and one goal (keep the crown at the Reckoning). No personality, no
hobbies, no plans. Everything else grows from what he does and what happens to him:

  - needs (0 = desperate, 1 = fine): hunger, energy, company, fun. Just a body; they push him around.
  - pastimes: he can try anything (paint, sing, carve, garden, write poems, juggle...). Whatever he keeps
    coming back to becomes a passion, and he gets better at it.
  - self: every night, going to sleep, he reflects on his day and updates who he is - traits, likes,
    dislikes, passions, wants, fears, and one line about who he's becoming. That's his personality,
    and he writes it himself.
  - works: his own projects, from his own ideas, wherever he is. Nothing is suggested to him. He pays,
    workers build over days, setbacks happen, and when it's done it can turn out well, shoddy, or fail
    outright - gold gone. Experience and pitching in himself help.

The court (steward, captain, jester) and the docket (petitioners, criminals, visitors) give him people
to deal with every day.
"""
import re

import numpy as np
import yaml

from ..config import CONTENT

NEEDS = {"hunger": 0.025, "energy": 0.012, "company": 0.015, "fun": 0.012}   # loss per tick awake
WORDS = {"hunger": "hungry", "energy": "exhausted", "company": "lonely", "fun": "bored"}
SELF_KEYS = {"traits": 6, "likes": 6, "dislikes": 6, "passions": 4, "wants": 4, "fears": 3}


def court():
    f = CONTENT / "court.yaml"
    return yaml.safe_load(f.read_text()) if f.exists() else {}


def new_life():
    return {"needs": {k: 0.8 for k in NEEDS}, "skills": {}, "creations": [], "builds": 0, "outcomes": []}


def new_self():
    return {**{k: [] for k in SELF_KEYS}, "becoming": "", "history": []}


def drift(me, awake, alone=False, around=0):
    """Needs wear down. A man alone on purpose misses people less - he chose the island. And people living around
    him are company of a sort (a wave, a joke across the field), even when he isn't talking to anyone."""
    n = me.setdefault("life", new_life())["needs"]
    for k, loss in NEEDS.items():
        if k == "company" and alone:
            loss *= 0.3
        if k == "company" and around and awake:
            loss *= max(0.0, 1 - min(1.0, around / 4))
        if k == "energy" and not awake:
            n[k] = min(1.0, n.get(k, 0.8) + 0.07)
        elif awake or k == "hunger":
            n[k] = max(0.0, n.get(k, 0.8) - loss * (1 if awake else 0.4))


def feeling(me):
    n = me.get("life", new_life())["needs"]
    bad = sorted((v, k) for k, v in n.items() if k in NEEDS and v < 0.4)
    if not bad:
        return "You feel fine."
    return "You feel " + ", ".join(("desperately " if v < 0.15 else "") + WORDS[k] for v, k in bad) + "."


def needs_of(me):
    return me.setdefault("life", new_life()).setdefault("needs", {k: 0.8 for k in NEEDS})


def satisfy(me, need, amount):
    n = me.setdefault("life", new_life())["needs"]
    if need in NEEDS:
        n[need] = float(np.clip(n.get(need, 0.8) + amount, 0, 1))


def who_am_i(me):
    """His self, as he's written it so far - or nothing at all."""
    s = me.get("self") or new_self()
    parts = [f"{k}: {', '.join(s[k])}" for k in SELF_KEYS if s.get(k)]
    if s.get("becoming"):
        parts.insert(0, f"who you're becoming: {s['becoming']}")
    return "; ".join(parts)


# ---------------------------------------------------------------- pastimes
def _slug(activity):
    w = re.findall(r"[a-z]+", str(activity).lower())
    return " ".join(w[:3]) or "idling"


def pastime(world, me, activity, title, description):
    life = me.setdefault("life", new_life())
    act = _slug(activity)
    practice = life["skills"].get(act, 0) + 1
    life["skills"][act] = practice
    if len(life["skills"]) > 40:
        for k in sorted(life["skills"], key=life["skills"].get)[:10]:
            del life["skills"][k]
    level = min(10, 1 + practice // 3)
    item = {"id": f"c{len(life['creations']) + 1}", "kind": act, "title": title[:80], "description": description[:300],
            "skill": level, "day": world.city.day + 1}
    life["creations"].append(item)
    del life["creations"][:-60]
    satisfy(me, "fun", 0.45)
    return item, level, practice


def tried(me):
    sk = me.get("life", {}).get("skills", {})
    return ", ".join(f"{k} ({n}x)" for k, n in sorted(sk.items(), key=lambda kv: -kv[1])[:6])


# ---------------------------------------------------------------- reflection (who he's becoming)
REFLECT_SCHEMA = {"type": "object", "properties": {
    **{k: {"type": "array", "items": {"type": "string"}} for k in SELF_KEYS},
    "becoming": {"type": "string"}}, "required": list(SELF_KEYS) + ["becoming"]}


def reflect(world, me, llm=None):
    """Last thing at night: he looks back on his day and rewrites who he is (keeps what still fits)."""
    s = me.setdefault("self", new_self())
    day = [m["text"] for m in world.moments_since(world.clock - 18 * 60) if m["who"] == "king"
           or (m["public"] and m["drama"] >= 2)][-14:]
    if llm and world.can_think():
        world.spend_calls(1)
        try:
            out = llm.json(
                (f"You are Aldric, building {world.city.name} from nothing - you want to be its king. "
                 if not world.city.living["town"]["land"].get("crowned") else
                 f"You are {me['name']}, king of {world.city.name}. ")
                + "Nobody told you who to be; you're figuring it out. "
                f"Your goal: {me.get('frontier_goal') or me.get('goal', '')} It's late and you're going to sleep. Look back on today and update "
                "who you are: traits (what you're like), likes, dislikes, passions (only things you really keep "
                "coming back to), wants (your own goals beyond the crown), fears. Keep what still fits, change what "
                "doesn't, add only what today actually showed. Short phrases. 'becoming': one honest sentence about "
                "who you're turning into. It's fine to stay unsure.",
                f"Who you were this morning: {who_am_i(me) or 'nobody in particular yet'}\n"
                f"Things you've tried: {tried(me) or 'nothing yet'}\nToday:\n- " + "\n- ".join(day or ["a quiet day"]),
                REFLECT_SCHEMA, max_tokens=400, temperature=0.7)
            for k, cap in SELF_KEYS.items():
                s[k] = [str(x)[:60] for x in (out.get(k) or [])][:cap]
            s["becoming"] = str(out.get("becoming", ""))[:200]
        except Exception:
            world.stats["reflect_fallbacks"] = world.stats.get("reflect_fallbacks", 0) + 1
            _reflect_rules(me)
    else:
        _reflect_rules(me)
    if s.get("becoming"):
        s["history"] = (s.get("history", []) + [{"day": world.city.day + 1, "becoming": s["becoming"]}])[-30:]
    return s


def _reflect_rules(me):
    """Without the model: whatever he keeps doing becomes a passion; projects that failed become a fear."""
    s = me.setdefault("self", new_self())
    sk = me.get("life", {}).get("skills", {})
    s["passions"] = [k for k, n in sorted(sk.items(), key=lambda kv: -kv[1]) if n >= 3][:SELF_KEYS["passions"]]
    fails = [o for o in me.get("life", {}).get("outcomes", []) if o["result"] == "failed"]
    if fails and "building things that collapse" not in s["fears"]:
        s["fears"] = (s["fears"] + ["building things that collapse"])[-SELF_KEYS["fears"]:]


# ---------------------------------------------------------------- docket
def add_case(city, kind, who, text):
    """One open case per person per kind: asking again just updates it (and doesn't reset how long they've waited)."""
    d = city.living.setdefault("docket", [])
    same = next((k for k in d if k["who"] == who and k["kind"] == kind), None)
    if same:
        same["text"] = text[:200]
        return same
    case = {"id": f"k{city.living.get('case_no', 0) + 1}", "kind": kind, "who": who, "text": text[:200],
            "day": city.day + 1}
    city.living["case_no"] = city.living.get("case_no", 0) + 1
    d.append(case)
    del d[:-30]
    return case


def age_docket(world):
    """People don't wait forever. Cases left unheard for 2 days drop off - and the petitioners remember."""
    city, c = world.city, world.city.citizens
    keep, gone = [], []
    for k in city.living.get("docket", []):
        (gone if k["day"] <= city.day - 1 else keep).append(k)
    city.living["docket"] = keep
    for k in gone:
        i = c.index.get(k["who"])
        if i is None:
            continue
        if k["kind"] == "permit":                    # (older saves)
            continue
        if k["kind"] == "crime":
            city.living.get("conditions", {}).pop(k["who"], None)
            world.moment("world", f"@{k['who']} was let go - the king never got around to hearing the case.", 1,
                         public=True, handles=[k["who"]])
        else:
            c.loyalty[i] = float(np.clip(c.loyalty[i] - 0.06, 0, 1))
            c.log(i, city.day + 1, "gave up waiting for the king's court")
            world.reply(k["who"], "You waited two days at the castle, but the king never heard your case. You went "
                                  "home.", "court")
            world.moment("world", f"@{k['who']} gave up waiting for the king's court and went home annoyed.", 1,
                         public=True, handles=[k["who"]])
    return gone


def visitors(world):
    """Now and then someone turns up at the gate on their own (cheap, no model call)."""
    city = world.city
    c = city.citizens
    act = c.active()
    if not act.any() or city.rng.random() > 0.25:
        return None
    i = int(city.rng.choice(np.where(act)[0].tolist()))
    if city.living.get("town", {}).get("land"):
        asks = ["wants to know why the farm needs ten people when they could do it with six",
                "says their neighbour's goat keeps eating their roof", "found a strange old coin in the field",
                "wants Aldric to settle whose turn it is to run the well", "asks for a bigger window",
                "says there are wolf tracks by the farm", "offers to teach the children their letters",
                "wants to know when there'll be a proper tavern", "complains the builders start hammering at dawn",
                "asks if a street could be named after their grandmother"]
    else:
        asks = None
    asks = asks or ["wants the king to settle a dispute about a stolen goat", "asks for a loan to fix their roof",
            "complains that the tax collector was rude", "wants permission to marry a soldier",
            "offers the king a suspiciously large turnip", "says a ghost lives in the old mill",
            "asks the king to bless their new shop", "reports strange lights near the northern pass"]
    return add_case(city, "visitor", c.handles[i], f"@{c.handles[i]} {city.rng.choice(asks)}")
