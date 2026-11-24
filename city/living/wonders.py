"""Wonders: the strange things on the island - real, persistent, and always at a cost.

Emberfall sits on an old floating island, and the island says "yes, and..." to wild claims. Someone rides in on a
dragon? There IS a dragon - a hatchling the size of a cat that eats the stores. A magic sword? It's real; it only
cuts bread. Each wonder sticks around: it's in what the narrator sees, people can do things to it ("I hunt the goat",
"I feed the dragon"), and its catch keeps costing something until it's dealt with.

Wonders come from three places:
  - conjuring: a comment claims or calls up something fantastic (city/living/intents.py, action "conjure")
  - the narrator: a reply introduces something that should come back (a goat that follows you) - a "thread"
  - the island itself: events (land rising from the clouds, a sky-whale passing) - see content/events.yaml
"""
import re

KINDS = ("creature", "object", "magic", "place", "thread")
MAX_OPEN = 10            # wonders on the island at once (the oldest fade into stories)

# what kind of wonder a claim is, by its words
KIND_OF = [(r"dragon|wyrm|drake|griffin|gryphon|unicorn|phoenix|kraken|beast|monster|wolf|bear|horse|steed|pony|"
            r"owl|raven|cat|dog|hound|goat|sheep|pig|serpent|snake|fairy|faerie|sprite|imp|golem|troll|giant|ghost|"
            r"spirit|demon|familiar|whale|bird|fox|creature", "creature"),
           (r"sword|blade|axe|staff|wand|ring|amulet|crown|cloak|boots|armou?r|shield|book|tome|scroll|map|key|"
            r"lamp|orb|crystal|gem|egg|potion|chest|horn|bow|mirror|compass|bell", "object"),
           (r"spell|curse|summon|conjure|magic|enchant|hex|portal|teleport|fly|flying|levitat|invisib|storm|rain|"
            r"lightning|fire ?ball|heal(ing)? light|prophecy|vision|blessing", "magic"),
           (r"tower|castle|cave|door|gate|well|island|ship|airship|garden|ruin|temple|tree", "place")]

# the catch, by kind: (what it is really, its daily cost, how the cost reads). {thing} = what they claimed
TWISTS = {
    "creature": [("a {thing} - a hatchling no bigger than a cat, and hungry all the time", "hungry",
                  "eats from the stores every day"),
                 ("a {thing}, real and enormous, and completely uninterested in being ridden", "mischief",
                  "goes wherever it likes and knocks things over"),
                 ("a {thing} that follows its owner everywhere and screams at sunrise", "noisy",
                  "wakes the whole camp at dawn"),
                 ("a {thing} that is very clearly a goat, but insists it isn't", "mischief",
                  "eats thatch off the roofs")],
    "object": [("a {thing} that's real and magic - and only works on Tuesdays", "fickle", "is useless most days"),
               ("a {thing} that hums, glows, and won't stop whispering to its owner", "unsettling",
                "keeps its owner up at night"),
               ("a {thing} that's genuinely magic and very heavy", "heavy", "slows its owner down"),
               ("a {thing} that works, but every use turns something nearby a little bit blue", "blue",
                "things around it keep turning blue")],
    "magic": [("a {thing} - it worked, a little, and something on the island noticed", "noticed",
               "draws strange visitors"),
              ("a {thing} that worked far too well", "backfire", "keeps happening on its own"),
              ("a {thing} that went sideways: it rained frogs over the field for an hour", "sideways",
               "left the field full of frogs"),
              ("a {thing} that worked - and left its caster with glowing hair for a week", "marked",
               "makes it obvious to everyone who did it")],
    "place": [("a {thing} that wasn't there yesterday, at the edge of the island - its door won't open", "sealed",
               "nobody can get in yet"),
              ("a {thing} that's real, small, and only visible at night", "shy", "vanishes by day"),
              ("a {thing} that appeared overnight in the woods and is slowly growing", "growing",
               "spreads a little every day")],
}


def state(city):
    return city.living.setdefault("wonders", {"open": [], "gone": [], "n": 0})


def kind_of(text):
    t = str(text).lower()
    for pat, kind in KIND_OF:
        if re.search(pat, t):
            return kind
    return "magic"


def thing_of(text):
    """'I ride my dragon into town' -> 'dragon'. A short name for what they claimed."""
    t = re.sub(r"[^a-z' -]", " ", str(text).lower())
    for pat, _ in KIND_OF:
        m = re.search(rf"((?:[a-z']+ ){{0,2}}(?:{pat})[a-z]*)", t)
        if m:
            words = [w for w in m.group(1).split() if w not in ("my", "a", "an", "the", "i", "his", "her", "their",
                                                                 "ride", "rides", "riding", "on", "with", "cast",
                                                                 "summon", "find", "found", "have", "own")]
            if words:
                after = re.match(r"\s*(spell|storm|sword|staff|curse|charm|wand|bolt|egg)\b", t[m.end():])
                return " ".join(words[-3:] + ([after.group(1)] if after else []))
    return "spell"


def add(world, name, kind, owner=None, what="", cost="", upkeep="", by="conjured"):
    """A new wonder on the island. Returns it. (world, or just the city)"""
    city = getattr(world, "city", world)
    st = state(city)
    st["n"] += 1
    w = {"id": f"w{st['n']}", "name": str(name)[:60], "kind": kind if kind in KINDS else "thread",
         "owner": owner, "what": str(what)[:160], "cost": str(cost)[:120], "upkeep": upkeep, "by": by,
         "day": city.day + 1, "fed": city.day + 1, "mood": "fine"}
    st["open"].append(w)
    while len(st["open"]) > MAX_OPEN:                 # the oldest fade into stories
        old = st["open"].pop(0)
        old["gone_day"] = city.day + 1
        st["gone"] = (st["gone"] + [old])[-20:]
    return w


def find(city, text):
    """The open wonder someone means by 'the goat' / 'my dragon' / 'the humming stone'."""
    t = str(text or "").lower().replace("@", "")
    if not t.strip():
        return None
    words = set(re.findall(r"[a-z]{3,}", t)) - {"the", "and", "his", "her", "their", "that", "with"}
    best, score = None, 0
    for w in state(city)["open"]:
        n = set(re.findall(r"[a-z]{3,}", w["name"].lower())) - {"the", "that", "with"}
        s = len(words & n)
        if s > score:
            best, score = w, s
    return best


def conjure(world, u, text, item=""):
    """Someone claims or calls up something fantastic. It comes true - at a cost. Returns (wonder, facts)."""
    city = world.city
    st = state(city)
    mine = [w for w in st["open"] if w.get("owner") == u and w["by"] == "conjured" and w["day"] >= city.day - 2]
    if mine:                                          # one wonder every few days each: the island isn't a vending machine
        w = mine[-1]
        return w, (f"tried to conjure something more, but the island is still busy with their {w['name']} - "
                   f"nothing new happened, and the {w['name']} is still {w['cost']}")
    kind = kind_of(item or text)
    thing = (item or thing_of(text)).strip() or "spell"
    pick = city.rng.choice(TWISTS.get(kind, TWISTS["magic"]))
    what, upkeep, cost = pick[0].format(thing=thing), pick[1], pick[2]
    w = add(world, thing, kind, owner=u, what=what, cost=cost, upkeep=upkeep)
    _now(world, w)
    return w, (f"IT CAME TRUE, at a cost: there is now {what} on the island (theirs). The catch: it {cost}. "
               f"Wonders here are real but never free")


def _now(world, w):
    """The cost bites the day it appears too, so it's felt."""
    city = world.city
    from . import frontier as F
    st = F.land(world)["stock"]
    if w["upkeep"] == "hungry":
        st["food"] = max(0, st.get("food", 0) - 2)
    elif w["upkeep"] == "mischief" and st.get("thatch", 0):
        st["thatch"] = max(0, st["thatch"] - 2)


def daily(world):
    """06:00: every wonder costs what it costs. Some wander off. Returns moments worth telling.
    (upkeep: hungry eats the stores; mischief knocks things over; noisy costs everyone sleep; noticed / growing /
    backfire make news now and then; anything else is just a story)"""
    city = world.city
    from . import frontier as F
    stock = F.land(world)["stock"]
    c = city.citizens
    told = []
    for w in list(state(city)["open"]):
        up = w.get("upkeep")
        if up == "hungry":
            if stock.get("food", 0) >= 2:
                stock["food"] -= 2
                if city.rng.random() < 0.3:
                    told.append(f"The {w['name']} ate two days' worth of food from the stores before anyone woke up.")
            else:
                w["mood"] = "hungry"
                told.append(f"There was nothing left for the {w['name']} to eat. It is looking at the goats. And at people.")
        elif up == "mischief" and city.rng.random() < 0.5:
            what = city.rng.choice(["knocked over the woodpile", "chewed through a tent rope", "got into the stores",
                                    "chased Aldric round the shack", "stole someone's boots"])
            if "woodpile" in what:
                stock["wood"] = max(0, stock.get("wood", 0) - 3)
            told.append(f"The {w['name']} {what}.")
        elif up == "noisy":
            for i in c.active().nonzero()[0][:40]:
                c.mood[i] = max(0.0, float(c.mood[i]) - 0.01)
            if city.rng.random() < 0.3:
                told.append(f"The {w['name']} screamed at sunrise again. Nobody in the camp is a morning person anymore.")
        elif up in ("noticed", "growing", "backfire") and city.rng.random() < 0.25:
            told.append({"noticed": f"Something came to look at the {w['name']} in the night. It left tracks the size of "
                                    f"cartwheels.",
                         "growing": f"The {w['name']} is bigger this morning.",
                         "backfire": f"The {w['name']} happened again, all on its own."}[up])
        if w["by"] == "thread" and city.day + 1 - w["day"] > 6 and city.rng.random() < 0.3:
            state(city)["open"].remove(w)            # small story threads drift off if nobody picks them up
    for t in told[:2]:
        world.moment("world", t, 2, public=True)
    return told


def act_on(world, r, w):
    """Someone does something to a wonder: hunts the goat, feeds the dragon, steals the sword. Fills r['facts']."""
    city, rng = world.city, world.city.rng
    act, u = r["action"], r["user"]
    own = w.get("owner") == u
    who = f"@{w['owner']}'s " if w.get("owner") and not own else ("their own " if own else "the ")
    st = state(city)
    if act in ("attack",):
        tough = {"creature": 0.45, "object": 0.7, "magic": 0.5, "place": 0.2, "thread": 0.65}.get(w["kind"], 0.5)
        if rng.random() < tough:
            st["open"].remove(w)
            w["gone_day"], w["fate"] = city.day + 1, f"ended by @{u}"
            st["gone"] = (st["gone"] + [w])[-20:]
            r["facts"] = f"went after {who}{w['name']} and SUCCEEDED - it's gone from the island for good"
            r["reply_rule"] = f"You went after {who}{w['name']} - and that's the end of it. It's gone from the island."
            r["drama_floor"] = 2
            if w.get("owner") and not own:
                r["to_target_handle"] = w["owner"]
                r["to_target"] = f"@{u} did away with your {w['name']}. It's gone."
        else:
            r["facts"] = (f"went after {who}{w['name']} and FAILED - it got the better of them (bruised, muddy, "
                          f"and now it has a grudge)")
            r["reply_rule"] = f"You went after {who}{w['name']}. It won. You're muddy, bruised, and it holds a grudge now."
            w["mood"] = "a grudge against @" + u
            r["drama_floor"] = 2
    elif act == "steal":
        if w.get("owner") and not own and rng.random() < 0.5:
            r["facts"] = f"stole {who}{w['name']} - it's theirs now (and so is its catch: it {w['cost']})"
            r["to_target_handle"], r["to_target"] = w["owner"], f"@{u} stole your {w['name']}!"
            w["owner"] = u
            r["drama_floor"] = 2
        else:
            r["facts"] = f"tried to steal {who}{w['name']} and FAILED - it would not be taken"
            r["drama_floor"] = 1
    elif act in ("gift", "heal", "befriend", "bless", "work", "volunteer"):
        w["fed"], w["mood"] = city.day + 1, "content"
        if w.get("upkeep") == "hungry" and rng.random() < 0.4:
            w["upkeep"], w["cost"] = "tame", "is tame now - mostly"
            r["facts"] = f"looked after {who}{w['name']} - and it took to them; it's calmer now (no more eating the stores)"
            r["drama_floor"] = 2
        else:
            r["facts"] = f"looked after {who}{w['name']}; it seems to like them (its catch hasn't gone away: it {w['cost']})"
            r["drama_floor"] = 1
    else:
        r["facts"] = f"spent the day with {who}{w['name']} ({w['what']})"
    r.setdefault("reply_rule", r["facts"][:1].upper() + r["facts"][1:] + ".")
    r["wonder"] = w["name"]


def line(city):
    """For THE WORLD: the strange things on the island right now."""
    ws = state(city)["open"]
    if not ws:
        return ""
    bits = [f"{w['name']}" + (f" (@{w['owner']}'s)" if w.get("owner") else "") + f": {w['what']}"
            + (f" - it {w['cost']}" if w.get("cost") else "") + (f"; mood: {w['mood']}" if w.get("mood") != "fine" else "")
            for w in ws[-8:]]
    return "Wonders on the island (real; people can do things to them): " + " | ".join(bits) + "."
