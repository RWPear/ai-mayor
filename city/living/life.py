"""The king as a person: needs, passions, his own projects, his court, his docket.

Needs (0 = desperate, 1 = fine): hunger, energy, company, fun, pride. They drift
every tick and colour what he wants to do. Passions (painting, the lute, roses)
make creations whose quality grows with practice. Works are his own projects at
real places ("pave King's Street with stone"): he pays, workers build, he can
pitch in himself, and when it's done the place changes. Castle rooms are works
too, and they unlock his tools.

The court (steward, captain, jester) gives him people to talk to every day, and
the docket brings him petitioners and criminals - many of them real followers.
"""
import yaml

from .. import effects
from ..config import CONTENT
from . import town as T

NEEDS = {"hunger": 0.03, "energy": 0.02, "company": 0.015, "fun": 0.015, "pride": 0.01}   # loss per tick awake
WORDS = {"hunger": "hungry", "energy": "exhausted", "company": "lonely", "fun": "bored", "pride": "unappreciated"}


def court():
    f = CONTENT / "court.yaml"
    return yaml.safe_load(f.read_text()) if f.exists() else {}


def new_life():
    return {"needs": {k: 0.8 for k in NEEDS}, "skills": {}, "creations": [], "asleep": False}


def drift(me, awake):
    n = me.setdefault("life", new_life())["needs"]
    for k, loss in NEEDS.items():
        if k == "energy" and not awake:
            n[k] = min(1.0, n[k] + 0.07)
        elif awake or k == "hunger":
            n[k] = max(0.0, n[k] - loss * (0.4 if not awake else 1))


def feeling(me):
    n = me.get("life", new_life())["needs"]
    bad = sorted((v, k) for k, v in n.items() if v < 0.4)
    if not bad:
        return "You feel fine."
    return "You feel " + ", ".join(("desperately " if v < 0.15 else "") + WORDS[k] for v, k in bad) + "."


def satisfy(me, need, amount):
    n = me.setdefault("life", new_life())["needs"]
    n[need] = min(1.0, n[need] + amount)


# ---------------------------------------------------------------- creations
def create(world, me, passion, title, description):
    life = me.setdefault("life", new_life())
    skills = life["skills"]
    practice = skills.get(passion, 0) + 1
    skills[passion] = practice
    level = min(10, 1 + practice // 3)
    item = {"id": f"c{len(life['creations']) + 1}", "kind": passion, "title": title[:80], "description": description[:300],
            "skill": level, "day": world.city.day + 1, "owner": "king"}
    life["creations"].append(item)
    del life["creations"][:-60]
    satisfy(me, "fun", 0.45)
    satisfy(me, "pride", 0.15)
    return item, level, practice % 3 == 0 and level > 1


# ---------------------------------------------------------------- works (his own projects)
def start_work(world, imp, place):
    city = world.city
    t = city.living["town"]
    size = T.SIZES[imp.get("size", "medium")]
    cost = T.cost(imp.get("size", "medium"), city.population())
    if city.treasury < cost:
        return None, cost
    city.treasury -= cost
    work = {"id": imp["id"], "name": imp["name"], "place": place, "progress": 0.0, "days": size["days"],
            "feature": imp.get("feature"), "after": imp.get("after"), "flavor": imp.get("flavor", "nothing"),
            "room": imp.get("room", False), "started": city.day, "cost": cost}
    t["works"].append(work)
    return work, cost


def advance_works(world, minutes, boost=None, by=0.0):
    """Workers move every work forward; the king pitching in moves one faster. Returns finished works."""
    from .tools import FLAVORS
    city = world.city
    t = city.living["town"]
    done = []
    for w in list(t["works"]):
        w["progress"] += minutes / (w["days"] * 1440)
        if boost == w["id"]:
            w["progress"] += by
        if w["progress"] >= 1:
            t["works"].remove(w)
            t["done"].append(w["id"])
            if w["room"]:
                t["rooms"][w["id"]] = True
                t["features"][w["id"]] = {"room": f"newly built {T.ROOMS[w['id']]['name']}"}
            elif w.get("feature"):
                t["features"].setdefault(w["place"], {})[w["feature"]] = w.get("after") or f"improved ({w['name']})"
            effects.apply(city, FLAVORS.get(w["flavor"], {}))
            done.append(w)
    return done


# ---------------------------------------------------------------- docket
def add_case(city, kind, who, text):
    d = city.living.setdefault("docket", [])
    case = {"id": f"k{city.living.get('case_no', 0) + 1}", "kind": kind, "who": who, "text": text[:200],
            "day": city.day + 1}
    city.living["case_no"] = city.living.get("case_no", 0) + 1
    d.append(case)
    del d[:-30]
    return case


def visitors(world):
    """Now and then someone turns up at the gate on their own (cheap, no model call)."""
    city = world.city
    c = city.citizens
    act = c.active()
    if not act.any() or city.rng.random() > 0.25:
        return None
    import numpy as np
    i = int(city.rng.choice(np.where(act)[0].tolist()))
    asks = ["wants the king to settle a dispute about a stolen goat", "asks for a loan to fix their roof",
            "complains that the tax collector was rude", "wants permission to marry a soldier",
            "offers the king a suspiciously large turnip", "says a ghost lives in the old mill",
            "asks the king to bless their new shop", "reports strange lights near the northern pass"]
    return add_case(city, "visitor", c.handles[i], f"@{c.handles[i]} {city.rng.choice(asks)}")
