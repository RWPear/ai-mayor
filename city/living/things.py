"""Things: what's actually lying around Emberfall today, and what the king wants that isn't.

STOCK - every place has things in it, and they change. Each morning places restock from what that kind of
place would have (the kitchens: bread, onions... sometimes carrots, now and then something odd), and once
in a while a surprise turns up (a crate of oranges washed up at the river, a strange blue egg at the market).
New things are marked new, so they "pop up" in what the king sees. He can eat them, take them, use them -
whatever he says he does with them in his own words.

WANTS - if he wants something that isn't in front of him ("I want a carrot"), there's no dice to keep
rerolling. The world decides ONCE how it could happen, and he gets a want with a path and a wait:
  - it's somewhere in town right now          -> he's told where (go and get it)
  - it comes in on the farmers' cart / a caravan -> it arrives in a day or a few (or the delivery goes wrong)
  - someone can make it                        -> a commission from a real follower with that trade (the
                                                  smith makes the sword, the bard strings the lute)
  - nobody here has it                         -> it goes on the "Wanted by the king" list in the post, for
                                                  followers to bring (they get the credit)
  - it doesn't exist here                      -> the world says no, and he remembers
Asking again just tells him where it stands. Followers can fulfil any want by sending it ("I bring the king
a carrot"), which beats waiting.
"""
import re

import numpy as np

from ..roles import JOB_NAMES

# what each kind of place tends to have: (thing, kind, chance per morning). kind: food / goods / material / curio
POOLS = {
    "kitchens": [("bread", "food", 0.95), ("stew", "food", 0.9), ("onions", "food", 0.7), ("porridge", "food", 0.6),
                 ("cheese", "food", 0.5), ("carrots", "food", 0.15), ("honey", "food", 0.15), ("roast chicken", "food", 0.25),
                 ("apples", "food", 0.2), ("a jar of pickled eels", "food", 0.04)],
    "market_square": [("fish", "food", 0.7), ("turnips", "food", 0.7), ("cabbages", "food", 0.6), ("rope", "goods", 0.5),
                      ("candles", "goods", 0.5), ("carrots", "food", 0.25), ("spices", "goods", 0.15),
                      ("lute strings", "goods", 0.1), ("a hand mirror", "goods", 0.1), ("a map of the north", "curio", 0.03),
                      ("a caged songbird", "curio", 0.04)],
    "tavern": [("ale", "food", 0.95), ("meat pie", "food", 0.8), ("dice", "goods", 0.6), ("cider", "food", 0.3),
               ("a stranger's lost pipe", "curio", 0.05)],
    "smithy": [("nails", "material", 0.9), ("horseshoes", "goods", 0.8), ("a plain dagger", "goods", 0.25),
               ("iron bars", "material", 0.5), ("a fine sword", "goods", 0.03)],
    "chapel": [("candles", "goods", 0.9), ("an old book", "curio", 0.4), ("a dusty hymnal", "curio", 0.3)],
    "river": [("reeds", "material", 0.9), ("smooth stones", "material", 0.7), ("a fish", "food", 0.5),
              ("driftwood", "material", 0.4), ("a message in a bottle", "curio", 0.02)],
    "fields": [("wheat", "food", 0.8), ("wildflowers", "goods", 0.6), ("carrots", "food", 0.3), ("a lost lamb", "curio", 0.05),
               ("a four-leaf clover", "curio", 0.02)],
    "royal_gardens": [("weeds", "material", 0.9), ("a snail", "curio", 0.4), ("a hedgehog", "curio", 0.05)],
    "castle_yard": [("practice swords", "goods", 0.9), ("straw", "material", 0.8), ("arrows", "goods", 0.5)],
    "kings_street": [("mud", "material", 0.95), ("a dropped coin", "goods", 0.15), ("a runaway goat", "curio", 0.04)],
    "city_walls": [("loose stones", "material", 0.6)],
}
# what kind of follower could make a thing (commissions)
MAKERS = [(r"sword|dagger|shield|armou?r|helmet|axe|spear|horseshoe|crown|chain|blade|tool", "blacksmith"),
          (r"lute|song|music|ballad|drum|flute", "bard"),
          (r"cloak|coat|robe|dress|boots|hat|gloves|banner|tunic|cape", "tailor"),
          (r"cake|pie|bread|pastry|tart|biscuit", "baker"),
          (r"chair|table|bed|chest|cart|bow|boat|carving", "woodcutter"),
          (r"statue|bust|fountain|wall|bench", "mason"),
          (r"potion|medicine|remedy|perfume|dye", "alchemist")]
IMPOSSIBLE = r"dragon|unicorn|phoenix|magic|wand|spell|elixir of life|gun|phone|car\b|computer|electric"

WANT_SCHEMA = {"type": "object", "properties": {
    "kind": {"type": "string", "enum": ["food", "goods", "material", "curio"]},
    "path": {"type": "string", "enum": ["delivery", "made", "people", "impossible"]},
    "days": {"type": "integer"}, "how": {"type": "string"}},
    "required": ["kind", "path", "days", "how"]}


def _norm(name):
    return re.sub(r"^(a|an|some|the|my|a few|three|two)\s+", "", str(name).strip().lower()).rstrip(".!")[:50]


def _sing(w):
    return w[:-1] if w.endswith("s") and not w.endswith("ss") else w


def _parts(name):
    """'a fine sword with a red hilt' -> ('sword', {'fine', 'red', 'hilt'})"""
    n = _norm(name)
    m = re.match(r"(?:\w+\s+)?(?:jar|bowl|plate|cup|basket|bag|box|crate|piece|bunch|sack|pot|loaf)s?\s+of\s+(.+)", n)
    if m:                                           # "a jar of pickled eels" is eels
        n = m.group(1)
    core = re.split(r"\s+(?:with|of|for|that|which|from|made|i|to)\s+", n)[0]
    words = [_sing(w) for w in re.findall(r"[a-z]{3,}", core)]
    extra = {_sing(w) for w in re.findall(r"[a-z]{3,}", n)} - {words[-1] if words else ""}
    return (words[-1] if words else ""), extra


VAGUE = {"fresh", "some", "good", "nice", "big", "little", "small", "new", "old", "few", "bunch", "basket", "bag",
         "piece", "bowl", "plate", "cup", "jar", "box", "crate"}


def _match(item, want_):
    """Is this item the thing wanted? Same kind of thing, and nothing the wanter specified is missing."""
    hi, ei = _parts(item)
    hw, ew = _parts(want_)
    if not hi or hi != hw:
        return False
    return (ew - VAGUE) <= (ei | {hi})


def new_state():
    return {"stock": {}, "wants": [], "commissions": [], "deliveries": [], "known_impossible": []}


def state(city):
    return city.living.setdefault("things", new_state())


# ---------------------------------------------------------------- stock
def restock(world):
    """Morning: places refill from what they'd have. Leftovers mostly stay; new arrivals are marked new."""
    city, st = world.city, state(world.city)
    rng = city.rng
    for pid, pool in POOLS.items():
        here = st["stock"].setdefault(pid, [])
        for it in here:
            it["new"] = False
        keep = [it for it in here if it.get("kept") or rng.random() < 0.5]
        names = {it["name"] for it in keep}
        for name, kind, chance in pool:
            if name not in names and rng.random() < chance:
                keep.append({"name": name, "kind": kind, "new": True})
        st["stock"][pid] = keep[:12]
    surprise = _surprise(world)
    if surprise:
        pid, item = surprise
        st["stock"].setdefault(pid, []).append(item)


SURPRISES = [("river", "a crate of oranges washed up from somewhere downstream", "food"),
             ("market_square", "a peddler selling strange blue eggs", "curio"),
             ("kings_street", "a cart of fine stone left behind by a merchant who never came back", "material"),
             ("chapel", "a sealed letter addressed to 'the king, whoever he is'", "curio"),
             ("fields", "a patch of giant pumpkins nobody planted", "food"),
             ("tavern", "a traveling cook offering to make one dish for the king", "goods")]


def _surprise(world):
    """Now and then something nobody expected turns up. With a model it can be anything; without, one of a few."""
    city = world.city
    if city.rng.random() > 0.2:
        return None
    pid, text, kind = city.rng.choice(SURPRISES)
    if world.voice_llm and world.can_think():
        world.spend_calls(1)
        try:
            out = world.voice_llm.json(
                "You are the world of a small medieval kingdom. Invent ONE unusual but ordinary-world thing that turned "
                "up somewhere in town this morning (no magic). Keep it short and concrete.",
                f"Places: {', '.join(POOLS)}. Weather: {city.living.get('weather', '')}. Day {city.day + 1}.",
                {"type": "object", "properties": {"place": {"type": "string", "enum": list(POOLS)},
                                                  "thing": {"type": "string"},
                                                  "kind": {"type": "string", "enum": ["food", "goods", "material", "curio"]}},
                 "required": ["place", "thing", "kind"]}, max_tokens=80, temperature=1.0)
            if out.get("place") in POOLS and out.get("thing"):
                pid, text, kind = out["place"], str(out["thing"])[:80], out.get("kind", "curio")
        except Exception:
            pass
    from .town import PLACES
    world.moment("world", f"Something new at {PLACES[pid]['name']}: {text}.", 1, public=True, place=pid)
    return pid, {"name": text, "kind": kind, "new": True, "surprise": True}


def stock_line(city, pid):
    items = state(city)["stock"].get(pid, [])
    if not items:
        return ""
    return "Here right now: " + ", ".join(it["name"] + (" (new today!)" if it.get("new") else "") for it in items) + "."


def use_stock(world, me, text):
    """He did something with things that are here ("eat the carrots", "take the map"): they're used up or his now."""
    city = world.city
    pid = me.get("location")
    items = state(city)["stock"].get(pid, [])
    t = text.lower()
    got = []
    words = {_sing(w) for w in re.findall(r"[a-z]{3,}", t)}
    for it in list(items):
        if _parts(it["name"])[0] in words:
            items.remove(it)
            got.append(it)
            eaten = it["kind"] == "food" and re.search(r"\b(eat|ate|taste|bite|drink|cook|munch|devour)", t)
            if not eaten:
                inv = me.setdefault("life", {}).setdefault("inventory", [])
                inv.append({"item": it["name"], "from": None, "day": city.day + 1})
                del inv[:-20]
            _fulfil(world, it["name"], None, me)
    return got


# ---------------------------------------------------------------- wants
def want(world, me, thing, why=""):
    """He wants something. Decided once; the answer is a path and a wait, never a reroll."""
    city, st = world.city, state(world.city)
    name = _norm(thing)
    if not name:
        return None
    label = re.sub(r"^(i want|i'd like|i need|some)\s+", "", str(thing).strip(), flags=re.I).rstrip(".!")[:50]
    for w in st["wants"]:
        if w.get("open") and (_match(w["name"], name) or _match(name, w["name"])):
            return w, "already"
    if any(_match(x, name) or _match(name, x) for x in st["known_impossible"]):
        return {"name": name, "label": label, "path": "impossible",
                "how": "you already know there's none of that in Emberfall"}, "known"
    for pid, items in st["stock"].items():                   # 1. it's somewhere in town right now
        for it in items:
            if _match(it["name"], name):
                from .town import PLACES
                w = {"name": name, "label": label, "path": "here", "where": pid,
                     "how": f"there's {it['name']} at {PLACES[pid]['name']}"}
                return w, "here"
    path, days, how = _decide(world, name)
    if path == "impossible":
        st["known_impossible"] = (st["known_impossible"] + [name])[-30:]
        return {"name": name, "label": label, "path": path, "how": how}, "impossible"
    w = {"name": name, "label": label, "why": str(why)[:120], "path": path, "since": city.day + 1, "how": how, "open": True}
    if path == "delivery":
        ok = city.rng.random() < 0.8                          # decided now: will it really come?
        w["due"] = world.clock + days * 1440
        w["arrives"] = ok
    elif path == "made":
        w.update(_commission(world, name, days))
    st["wants"] = (st["wants"] + [w])[-6:]
    return w, path


def _decide(world, name):
    """How could this thing come to Emberfall? (rules, or the world model for things the rules don't know)"""
    if re.search(IMPOSSIBLE, name):
        return "impossible", 0, "there's no such thing in Emberfall"
    known = [(pid, chance) for pid, pool in POOLS.items() for n, _, chance in pool if _match(n, name)]
    if known:
        best = max(c for _, c in known)
        days = 1 if best >= 0.2 else (2 if best >= 0.08 else 4)
        source = "farmers' cart" if days == 1 else "next merchant caravan"
        return "delivery", days, f"it comes in with the {source}"
    for pat, job in MAKERS:
        if re.search(pat, name):
            return "made", 2, f"a {job} could make it"
    if world.voice_llm and world.can_think():
        world.spend_calls(1)
        try:
            out = world.voice_llm.json(
                "You are the world of a small, ordinary medieval kingdom (no magic, no modern things). The king wants "
                "something. Decide honestly how he could get it: path = delivery (traders bring it; days 1-6), made "
                "(a local craftsperson could make it; days 1-5), people (only someone in the kingdom might have one), or "
                "impossible. how = a few words on how.", f"The king wants: {name}", WANT_SCHEMA, max_tokens=80,
                temperature=0.4)
            if out.get("path") in ("delivery", "made", "people", "impossible"):
                return out["path"], int(np.clip(int(out.get("days") or 2), 1, 6)), str(out.get("how") or "")[:100]
        except Exception:
            pass
    return "people", 0, "nobody in town has one - maybe one of your subjects does"


def _label(w):
    return w.get("label") or w["name"]


def _commission(world, name, days):
    """A real follower with the right trade makes it (and hears about it)."""
    city, c = world.city, world.city.citizens
    job = next((j for pat, j in MAKERS if re.search(pat, name)), "blacksmith")
    pool = np.where(c.active() & (c.job == JOB_NAMES.index(job)))[0]
    maker = c.handles[int(city.rng.choice(pool.tolist()))] if len(pool) else None
    cost = round(30 + 20 * days)
    city.treasury -= cost
    if maker:
        world.reply(maker, f"🔨 The king has commissioned your character to make: {name}. You have {days} days. "
                           "The whole court is waiting.", "commission", credit=f"was commissioned by the king ({name})")
    return {"maker": maker, "job": job, "due": world.clock + days * 1440, "cost": cost,
            "how": f"commissioned from {'@' + maker if maker else 'a ' + job} ({cost} gold, {days} days)"}


def tick(world):
    """Deliveries arrive (or don't), commissions finish, stale wants are dropped."""
    city, st = world.city, state(world.city)
    king = world.agent("king")
    for w in [w for w in st["wants"] if w.get("open") and w.get("due") and world.clock >= w["due"]]:
        if w["path"] == "delivery" and not w.get("arrives"):
            w["open"] = False
            world.moment("world", f"The {_norm(_label(w))} the king was waiting for never arrived - the cart broke down on "
                                  f"the north road.", 1, public=True)
            continue
        who = w.get("maker")
        _give(king, w["name"], who, city)
        w["open"] = False
        text = (f"@{who} finished the {_norm(_label(w))} the king commissioned." if who else
                f"The {_norm(_label(w))} the king wanted arrived at the castle.")
        world.moment("world", text, 2 if who else 1, public=True, handles=[who] if who else [])
        if who:
            world.reply(who, f"🔨 You delivered the {_norm(_label(w))} to the king.", "commission",
                        credit=f"made the king's {_norm(_label(w))}")
    for w in st["wants"]:
        if w.get("open") and w.get("since", 0) <= city.day + 1 - 7:
            w["open"] = False
            world.moment("king", f"The king gave up on ever getting {_label(w)}.", 0, public=False)
    st["wants"] = [w for w in st["wants"] if w.get("open")] + [w for w in st["wants"] if not w.get("open")][-3:]


def _give(king, name, giver, city):
    inv = king.setdefault("life", {}).setdefault("inventory", [])
    inv.append({"item": name, "from": giver, "day": city.day + 1})
    del inv[:-20]


def _fulfil(world, item, giver, king=None):
    """Something arrived (a follower's gift, or he found it): any open want for it is done."""
    st = state(world.city)
    for w in st["wants"]:
        if w.get("open") and _match(item, w["name"]):
            w["open"] = False
            if giver:
                world.reply(giver, f"👑 The king had been wanting {_label(w)} - and you brought it. He won't forget.",
                            "want_fulfilled", credit=f"brought the king the {_norm(_label(w))} he wanted")
                world.city.treasury -= 20
                c = world.city.citizens
                if giver in c.index:
                    c.wealth[c.index[giver]] += 20
            return w
    return None


def wanted(city):
    """For the post: what the king is looking for that followers could bring."""
    return [_label(w) for w in state(city)["wants"] if w.get("open") and w["path"] in ("people", "delivery")][:3]


def wants_line(city):
    open_ = [w for w in state(city)["wants"] if w.get("open")]
    if not open_:
        return ""
    return "Things you're waiting for: " + "; ".join(f"{_label(w)} ({w['how']})" for w in open_) + "."
