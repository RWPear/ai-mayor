"""People's own builds: "I want to start a garden behind my house."

A settler asks; Aldric rules on it at court (or, if nobody gets to it in a day, nobody stops them). Granted, it's
THEIR project: a lot by their home, raised by their own hands - a couple of hours every evening, five more on any
day they comment about it. Finished, it stands in the world with their name on it ("@rowan's garden") and does
what that kind of thing does (a garden feeds people, a hut houses them, a workbench makes work faster).

It scales because it's bounded: one personal build per person at a time, and only small things (a garden, a hut,
a beehive, a stall). Anything bigger is a petition for the king to build.
"""
import re

import numpy as np

from . import frontier as F
from . import life

ALLOWED = ("tiny", "small")
PASSIVE = 2.0        # hours a day they put in after work, without saying anything
KEEN = 5.0           # on a day they comment about it
VERBS = r"(?:start|build|plant|make|dig|set up|open|put up|raise|grow|craft|carve|clear|fence|knock together)"
WANTS = (r"\b(?:i|i'?m|i'?d|i'?ll|let me|can i|may i|we|we'?ll|time to|going to|gonna|wanna|want to|would like to|"
         r"plan to|hope to)\b[^.!?]{0,30}?\b" + VERBS + r"s?\b")
NOUN = (r"garden|farm|plot|patch|orchard|vineyard|beehive|hive|apiary|coop|henhouse|pen|sty|stable|hut|shack|cabin|"
        r"cottage|house|home|shed|workshop|forge|smithy|bakery|oven|kiln|stall|shop|booth|tavern|inn|brewery|still|"
        r"shrine|altar|chapel|well|dock|jetty|pier|bench|table|rack|smokehouse|fish ?trap|weir|loom|tannery|"
        r"mill|bridge|fence|wall|tower|statue|sign|school|library|clinic|infirmary|herb")
ASK = re.compile(WANTS + r"[^.!?]{0,50}?\b(" + NOUN + r")s?\b", re.I)


def wants_to_build(text):
    return bool(ASK.search(text or ""))


def rule_idea(text):
    """'I want to start a little herb garden behind my cottage' -> 'a little herb garden'."""
    m = re.search(VERBS + r"s?\s+((?:a|an|my|me a|our|some|the|my own)\s+[^.!?,]{0,40}?\b(?:" + NOUN + r")s?)\b",
                  text or "", re.I)
    if m:
        idea = re.sub(r"^(my own|my|our|the|me a)\s+", "a ", m.group(1).strip(), flags=re.I)
        return idea[:50]
    m = re.search(r"\b(" + NOUN + r")s?\b", text or "", re.I)
    return f"a {m.group(1).lower()}" if m else ""


def _all(world):
    return F.land(world).setdefault("personal", [])


def of(world, handle):
    """Their build in progress, if any."""
    return next((p for p in _all(world) if p["owner"] == handle and not p.get("done")), None)


def pending(city, handle):
    return next((k for k in city.living.get("docket", []) if k["kind"] == "permit" and k["who"] == handle), None)


def _key(p):
    return F.bare(p["name"]).split()[-1].lower() if p.get("name") else ""


def mentions(p, text):
    k = _key(p)
    return bool(k and re.search(r"\b" + re.escape(k), (text or "").lower()))


def owned_name(p):
    return f"@{p['owner']}'s {F.bare(p['name'])}"


def hours_for(d):
    S = F.SCALES[d["scale"]]
    return round(S["hours"] * (0.6 if d["kind"] in ("tool", "comfort") else 1.0) + S["units"] / 4, 1)


# ---------------------------------------------------------------- asking
def ask(world, r):
    """From a comment (intents.resolve). Fills r['facts'] / r['reply_rule']."""
    city, c = world.city, world.city.citizens
    u = r["user"]
    mine = of(world, u)
    if mine:
        return work_on(world, r, mine)
    case = pending(city, u)
    if case:
        r["facts"] = f"asked again about building {case['idea']}; Aldric still hasn't answered"
        r["reply_rule"] = (f"Your request to build {case['idea']} is still waiting for Aldric. If nobody says no by "
                           "tomorrow, you can start anyway.")
        return
    idea = (r.get("item") or rule_idea(r.get("text", ""))).strip() or "a little garden"
    d = F.design(world, idea)
    if not d or not d.get("possible", True):
        why = (d or {}).get("why_not") or "nobody could make sense of it"
        r["facts"] = f"wanted to build {idea}, but {why}"
        r["reply_rule"] = f"You stared at the field and pictured {idea}. Then reality set in: {why}."
        return
    if d["scale"] not in ALLOWED:
        life.add_case(city, "petition", u, f"@{u} asks the king to build {d['name']}")
        r["facts"] = f"wanted to build {d['name']} - far too big for one pair of hands - so they asked the king to"
        r["reply_rule"] = (f"{d['name'][0].upper() + d['name'][1:]} is a job for the whole settlement, not one pair "
                           "of hands. You asked Aldric to take it on instead; he'll hear you at court.")
        r["drama_floor"] = 1
        return
    case = life.add_case(city, "permit", u, f"@{u} ({trades_label(c, u)}) asks to build {d['name']} by their home")
    case["idea"] = d["name"]
    case["design"] = d
    r["facts"] = f"asked Aldric's leave to build {d['name']} by their home"
    r["reply_rule"] = (f"You asked Aldric if you can build {d['name']} by your home. He'll answer at court - and if "
                       "nobody says no by tomorrow, you can start anyway.")
    r["drama_floor"] = 1


def trades_label(c, u):
    from .. import trades
    i = c.index[u]
    return trades.a_(c.label(i))


def work_on(world, r, p):
    """They commented about their own build: a proper day on it."""
    done = work(world, p, KEEN, keen=True)
    r["facts"] = (f"put a long day into their {F.bare(p['name'])}" + (" - and finished it" if p.get("done")
                                                                       else f" ({round(p['progress'] * 100)}% done)"))
    if not p.get("done"):
        r["reply_rule"] = (f"You put a long day into your {F.bare(p['name'])}. It's {round(p['progress'] * 100)}% "
                           "done - you can see it taking shape now.")
    r["drama_floor"] = 1 if done else 0
    world.city.living.setdefault("own_work_today", []).append(r["user"])


# ---------------------------------------------------------------- ruling
def grant(world, case, words=""):
    """Aldric (or nobody) said yes: the plot is pegged out by their home."""
    from . import scene
    city, L = world.city, F.land(world)
    d = case.get("design") or F.design(world, case.get("idea") or "a little garden")
    u = case["who"]
    if of(world, u):
        return None
    n = L.get("personal_no", 0) + 1
    L["personal_no"] = n
    p = {"id": f"o{n}", "owner": u, "name": d["name"], "idea": case.get("idea") or d["name"], "kind": d["kind"],
         "scale": d["scale"], "capacity": d.get("capacity", 0), "boosts": d.get("boosts", ""), "look": d.get("look", ""),
         "material": d.get("material"), "place": "field", "progress": 0.0, "hours": hours_for(d),
         "started": city.day + 1, "started_t": world.clock, "progress_log": []}
    p["near"] = scene.home_pos(world, u)
    scene.place(world, p)
    _all(world).append(p)
    return p


def deny(world, case):
    i = world.city.citizens.index.get(case["who"])
    if i is not None:
        c = world.city.citizens
        c.mood[i] = float(np.clip(c.mood[i] - 0.05, 0, 1))


# ---------------------------------------------------------------- building
def work(world, p, hours, keen=False):
    """Returns True if it got finished."""
    if p.get("done") or hours <= 0:
        return False
    p["progress"] = min(1.0, p["progress"] + hours / max(1.0, p["hours"]))
    p.setdefault("progress_log", []).append([world.clock, round(p["progress"], 3)])
    del p["progress_log"][:-48]
    if p["progress"] >= 0.999:
        finish(world, p)
        return True
    return False


def daily(world):
    """Evenings after work: everyone with a build puts in a couple of hours (not if they're hurt or jailed)."""
    from .intents import condition
    city, c = world.city, world.city.citizens
    keen = set(city.living.get("own_work_today", []))
    for p in list(_all(world)):
        if p.get("done"):
            continue
        i = c.index.get(p["owner"])
        if i is None or c.status[i] != 0:
            p["abandoned"] = True
            continue
        if condition(city, p["owner"]) or p["owner"] in keen:
            continue
        work(world, p, PASSIVE)
    city.living["own_work_today"] = []
    F.land(world)["personal"] = [p for p in _all(world) if not p.get("done") and not p.get("abandoned")]


def finish(world, p):
    city, L = world.city, F.land(world)
    p["done"] = True
    good = city.rng.random() < 0.85
    cap = p.get("capacity", 0) if p["kind"] == "housing" else 0
    b = {"id": f"b{len(L['buildings'])}", "name": owned_name(p), "kind": p["kind"], "scale": p["scale"],
         "capacity": cap, "place": p.get("place", "field"), "quality": "good" if good else "shoddy",
         "day": city.day + 1, "by": "@" + p["owner"], "owner": p["owner"], "look": p.get("look", ""),
         "boosts": p.get("boosts", ""), "material": p.get("material"), "lot": p.get("lot"), "t": world.clock,
         "started_t": p.get("started_t")}
    L["buildings"].append(b)
    q = 1.0 if good else 0.6
    if p["kind"] in ("tool", "workshop"):
        L["tools"].append({"name": b["name"], "tool": p.get("boosts") or "wood", "x": round(1 + 0.15 * q, 2)})
    if p["kind"] == "housing":                      # out of the tent and into the hut they built
        i = city.citizens.index.get(p["owner"])
        if i is not None and int(city.citizens.walled[i]) == -2 and cap:
            L.setdefault("homes", {})[p["owner"]] = b["id"]
            L["occupancy"][b["id"]] = 1
            city.citizens.walled[i] = 0
    i = city.citizens.index.get(p["owner"])
    if i is not None:
        c = city.citizens
        c.mood[i] = float(np.clip(c.mood[i] + 0.12, 0, 1))
        c.loyalty[i] = float(np.clip(c.loyalty[i] + 0.05, 0, 1))
        c.log(i, city.day + 1, f"finished building {F.bare(p['name'])} by their home")
    what = F.bare(p["name"])
    world.reply(p["owner"], f"🌱 Your {what} is finished{'' if good else ' (a bit crooked, but yours)'}. It stands by "
                            "your home for the whole settlement to see, with your name on it.", "own_build",
                credit=f"built their own {what}")
    world.moment("@" + p["owner"], f"@{p['owner']} finished their own {what} by their home"
                 + ("." if good else " - a bit crooked, but theirs."), 2, public=True, place="field",
                 handles=[p["owner"]])
    if p["kind"] == "housing":
        F.rehouse(world, quiet=True)


def summary(world):
    return [{"owner": p["owner"], "name": p["name"], "progress": round(p["progress"], 2)} for p in _all(world)
            if not p.get("done")]
