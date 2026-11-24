"""Everyone's day, and the little things that happen in it.

The day has one simple shape, the same for everyone (each person a few minutes earlier or later than the next):

    06:00  up           at home
    06:30  breakfast    at home (neighbours over the fence)
    07:30  work         today's job (city/living/frontier.py: People Power): the farm, the brewery, a building site
    12:00  lunch        where they work
    13:00  work
    17:30  their own time   the tavern (once there is one), a friend's door, fishing, the square
    19:00  supper       the square for the first streets, at home further out
    21:30  bed

Wherever two people are in the same place at the same time, something small can happen between them: they share
bread, swap gossip, help with a log, argue about the well, start a song. Every pair keeps a running score, so the
small things add up - into friends, best friends, a feud, a fight - and those are the stories that turn up in the
feed and in the bard's replies, whether or not anyone commented that day.
"""
import zlib

import numpy as np

from . import frontier as F

DAY = [  # (minute, what, where)
    (6 * 60, "up", "home"),
    (6 * 60 + 30, "breakfast", "home"),
    (7 * 60 + 30, "work", "work"),
    (12 * 60, "lunch", "work"),
    (13 * 60, "work", "work"),
    (17 * 60 + 30, "free", "free"),
    (19 * 60, "supper", "commons"),
    (21 * 60 + 30, "sleep", "home"),
]
WORDS = {"up": "up and about", "breakfast": "breakfast at home", "work": "work", "lunch": "lunch where they work",
         "free": "their own time", "supper": "supper", "sleep": "bed"}
SQUARE_SEATS = 60                 # the first streets eat at the square; further out, supper's at home


def _h(*parts):
    return zlib.crc32("|".join(str(p) for p in parts).encode())


def offset(handle):
    """Each person keeps the same day a little earlier or later than the next (-15..+15 minutes)."""
    return _h(handle, "early") % 31 - 15


def bonds(world):
    """Every pair with any history: {"a|b": {"s": score, "n": times, "stage": friends/close/rivals/enemies, "last"}}.
    (Comments feed the same scores: a gift or a punch counts more than a shared loaf.)"""
    b = getattr(world, "city", world).living.setdefault("bonds", {})
    for k, v in list(b.items()):
        if not isinstance(v, dict):                     # (older saves kept a bare number)
            b[k] = {"s": v, "n": 1, "stage": None}
    if len(b) > 3000:                                   # forget the faintest acquaintances
        for k in sorted(b, key=lambda k: (b[k].get("stage") is not None, abs(b[k]["s"])))[:500]:
            del b[k]
    return b


def _key(a, b):
    return "|".join(sorted((a, b)))


def bond(world, a, b):
    return bonds(world).get(_key(a, b), {"s": 0, "n": 0, "stage": None})


def friends_of(world, h, best=3):
    out = []
    for k, v in bonds(world).items():
        a, b = k.split("|")
        if h in (a, b):
            out.append((b if a == h else a, v))
    return sorted(out, key=lambda x: -abs(x[1]["s"]))[:best]


def free_time(world, i):
    """Where someone spends their own time today: the tavern (if it's open and they're a drinker), a friend's door,
    or a pastime."""
    city, c, L = world.city, world.city.citizens, F.land(world)
    h = c.handles[int(i)]
    day = city.day + 1
    pubs = [b for b in L["buildings"] if b.get("running") and b["kind"] in ("tavern", "stage", "baths", "chapel")]
    if pubs and _h(h, day, "pub") % 3:
        b = pubs[_h(h, day) % len(pubs)]
        return "b:" + b["id"], None
    close = [o for o, v in friends_of(world, h) if v["s"] >= 5 and o in c.index and c.active()[c.index[o]]]
    if close and _h(h, day, "visit") % 3 == 0:
        return "visit", close[_h(h, day) % len(close)]
    return ["river", "field", "woods", "square", "square"][_h(h, day, "free") % 5], None


def schedule(world, i):
    """Someone's day: [{"from", "to", "what", "where", "with"}] in minutes after midnight. (Settled each morning.)"""
    c = world.city.citizens
    h = c.handles[int(i)]
    day = world.city.day + 1
    cache = getattr(world, "_sched", None)
    key = (day, len(F.land(world).get("jobs", {})), F.land(world).get("jobs", {}).get(h))
    if cache is None or cache.get("day") != day:
        cache = world._sched = {"day": day}
    if h in cache and cache[h][0] == key:
        return cache[h][1]
    out = _schedule(world, i, h)
    cache[h] = (key, out)
    return out


def _schedule(world, i, h):
    off = offset(h)
    work = F.job_place(world, h)
    free, friend = free_time(world, i)
    hs = F.land(world)["houses"].get(h)
    supper = "square" if hs and hs["n"] < SQUARE_SEATS else "home"
    out = []
    for k, (m, what, where) in enumerate(DAY):
        to = DAY[k + 1][0] if k + 1 < len(DAY) else 30 * 60
        place = {"home": "home", "commons": supper, "work": work, "free": free}[where]
        out.append({"from": m + off, "to": to + off, "what": what, "where": place, "with": friend if where == "free" else None})
    return out


def doing(world, i, minute=None):
    """What someone is doing right now (a block of their schedule)."""
    m = (world.clock if minute is None else minute) % 1440
    sched = schedule(world, i)
    for b in sched:
        if b["from"] <= m < b["to"] or b["from"] <= m + 1440 < b["to"]:
            return b
    return sched[-1]                                 # before getting up: still asleep


# ---------------------------------------------------------------- the little things
# (kind, score change, animation, short label, lines). {a} and {b} are handles, the rest is filled from the world.
SMALL = {
    "meal": [
        ("share", 1, "eat", "shares bread", ["{a} split the last of their bread with {b}", "{a} saved {b} a seat and the good end of the loaf",
                                            "{a} gave {b} their stew when {b} came back late"]),
        ("story", 1, "talk", "tells a story", ["{a} told {b} about {tale}", "{b} sat through {a}'s story about {tale} - twice"]),
        ("joke", 1, "talk", "makes them laugh", ["{a} made {b} laugh so hard the stew went everywhere", "{a} did an impression of Aldric that had {b} in tears"]),
        ("gossip", 1, "talk", "gossips", ["{a} and {b} swapped gossip about {gossip}", "{a} whispered to {b} what they'd heard about {gossip}"]),
        ("argue", -1, "talk", "argues", ["{a} and {b} argued about {argument}", "{a} told {b} they were wrong about {argument}, loudly"]),
        ("tease", -1, "talk", "teases", ["{a} teased {b} about {tease} until {b} walked off", "{a} wouldn't stop going on about {b}'s {tease}"]),
    ],
    "supper": [
        ("song", 1, "sing", "sings", ["{a} started a song and {b} joined in, badly", "{a} and {b} sang the one about {song} until people threw bread"]),
        ("dance", 1, "dance", "dances", ["{a} pulled {b} up to dance by the fire", "{a} and {b} danced until one of them fell over"]),
    ],
    "work": [
        ("help", 1, "work", "lends a hand", ["{a} helped {b} {help}", "{b} couldn't {help} alone, so {a} did it with them"]),
        ("teach", 1, "talk", "shows how", ["{a} showed {b} how to {tip}", "{a} spent an hour teaching {b} to {tip}"]),
        ("race", 0, "work", "races", ["{a} and {b} raced to see who could {race}; {a} won and won't shut up about it"]),
        ("blame", -1, "talk", "blames", ["{a} blamed {b} for {mishap}", "{a} and {b} had words over {mishap}"]),
        ("nap", -1, "talk", "caught napping", ["{a} caught {b} asleep {nap} and told everyone", "{a} found {b} napping {nap} and woke them with cold water"]),
    ],
    "free": [
        ("walk", 1, "walk", "walks together", ["{a} and {b} walked out to {spot} together", "{a} and {b} sat and watched the clouds go under the island"]),
        ("gift", 2, "talk", "gives a gift", ["{a} gave {b} {trinket}", "{a} left {trinket} on {b}'s bed"]),
        ("dice", 0, "sit", "plays dice", ["{a} won {coins} coppers off {b} at dice", "{a} and {b} played dice until it got too dark to see"]),
        ("prank", -1, "talk", "pranks", ["{a} put a frog in {b}'s boot", "{a} hid {b}'s {thing} and only gave it back after supper"]),
    ],
    "up": [
        ("snore", -1, "talk", "complains", ["{a} told {b} their snoring kept the whole row up", "{a} woke {b} by tripping over them in the dark"]),
        ("morning", 1, "talk", "says good morning", ["{a} brought {b} something warm to drink at dawn",
                                                     "{a} and {b} stood at the door watching the sun come up under the island",
                                                     "{a} lent {b} a dry pair of socks", "{a} told {b} about a dream with {gossip} in it"]),
    ],
}
BLOCK_KIND = {"breakfast": ["meal"], "lunch": ["meal"], "supper": ["meal", "supper"], "work": ["work"], "free": ["free"],
              "up": ["up"]}
FILL = {
    "tale": ["the night they outran a bear", "their grandmother's three husbands", "a fish as long as a cart",
             "the time they met a wizard on the road", "the town they came from, which burned", "a ghost in a well"],
    "argument": ["whose turn it was to fetch water", "whether the island is sinking", "the right way to boil turnips",
                 "who sits nearest the fire", "whether Aldric is a real king", "how many legs a sky-whale has"],
    "tease": ["haircut", "singing", "terrible cooking", "fear of the edge", "boots", "laugh"],
    "song": ["the drowned miller", "the king with no crown", "the goat that ate the moon", "a girl from the south road"],
    "help": {"farm": ["get a cart of cabbages out of the mud", "chase the crows off the seedlings"],
             "build": ["get a beam up onto the frame", "hold a wall straight while the pegs went in"],
             "brewery": ["roll a full barrel up the ramp", "stir the mash before it caught"],
             "tavern": ["carry a drunk home", "change a barrel mid-song"], "bakery": ["knead a trough of dough", "pull the loaves before they burned"],
             "blacksmith": ["work the bellows", "hold a red-hot horseshoe steady"], "watchtower": ["haul the bell rope", "spot a fox in the cabbages"],
             "market": ["put up a stall in the wind", "count a jar of coppers"], "well": ["fish a bucket out of the well"],
             "vineyard": ["tie up a row of vines"], "cellar": ["shift a cask"], "*": ["carry a load across town", "fix a broken handle"]},
    "tip": {"farm": ["tell a weed from a carrot", "plant onions the right way up"], "build": ["cut a joint that holds", "set a post plumb"],
            "brewery": ["tell when the mash is ready", "smell bad hops"], "tavern": ["pour a pint without the foam", "end a fight with a joke"],
            "bakery": ["know bread's done by the knock", "shape a plait loaf"], "blacksmith": ["read the colour of hot iron"],
            "*": ["tie a knot that holds", "sharpen a blade on a stone"]},
    "race": {"farm": ["dig a row fastest"], "build": ["hammer in ten pegs"], "brewery": ["roll a barrel the length of the yard"],
             "tavern": ["carry six mugs at once"], "bakery": ["shape the most loaves"], "*": ["finish first"]},
    "mishap": {"farm": ["a trampled row of onions", "a gate left open and a goat in the cabbages"],
               "build": ["a wall that went up crooked", "a hammer dropped from the roof"],
               "brewery": ["a barrel that went sour"], "tavern": ["a smashed mug and a tab nobody paid"],
               "bakery": ["a tray of burned loaves"], "blacksmith": ["a cracked anvil"], "*": ["a broken tool", "a spilled load"]},
    "nap": {"farm": ["behind the haystack"], "build": ["under the scaffolding"], "brewery": ["between two barrels"],
            "tavern": ["under a table"], "*": ["in the shade"]},
    "spot": ["the edge, to look down at the clouds", "the waterfall", "the top of the rocky hill", "the river bend"],
    "trinket": ["a carved wooden bird", "a ribbon from the peddler", "a smooth blue stone from the river", "a crown of daisies",
                "a whistle cut from a reed"],
    "coins": ["three", "five", "eleven", "all their"],
    "thing": ["boots", "hat", "spoon", "favourite stick"],
}


def _fill(world, kind, a, b, where, rng):
    city = world.city
    def pick(key):
        v = FILL[key]
        if isinstance(v, dict):
            v = v.get(where, v["*"])
        return rng.choice(v)
    vals = {k: pick(k) for k in FILL}
    # gossip: what's actually going on (a wonder, new land, Aldric, someone else)
    topics = ["Aldric's moustache", "what Aldric mutters in his sleep", "Skarn the Red", "whatever is under the island"]
    from . import wonders
    topics += [w["name"] for w in wonders.state(city).get("open", [])][-3:]
    topics += [p["name"] for p in F.places(world).values() if p.get("risen")][-2:]
    L = F.land(world)
    topics += [f"whether {p['name']} will ever get finished" for p in L["projects"]][:2]
    topics += [f"who's been skiving off at {b['name']}" for b in L["buildings"] if b.get("disrepair")][:1]
    topics += [f"how much gold Aldric is sitting on"]
    act = np.where(city.citizens.active())[0]
    if len(act) > 2:
        o = city.citizens.handles[int(act[rng.randrange(len(act))])]
        if o not in (a, b):
            topics.append("@" + o)
    vals["gossip"] = rng.choice(topics)
    return vals


def _choose(world, kinds, s, temper, rng):
    """A small thing between two people: friends do friendly things, rivals don't, grumps grump."""
    pool = [x for k in kinds for x in SMALL[k]]
    w = []
    for kind, d, *_ in pool:
        base = 1.0
        if d > 0:
            base *= 1 + max(0, s) * 0.25 + max(0, -temper) * 2
            base *= 0.4 if s <= -3 else 1
        elif d < 0:
            base *= 0.55 + max(0, -s) * 0.3 + max(0, temper) * 3
            base *= 0.5 if s >= 4 else 1
        w.append(base)
    return rng.choices(pool, weights=w)[0]


PER_TICK = 8


def tick(world):
    """Every half hour, awake people in the same place bump into each other."""
    city, c = world.city, world.city.citizens
    m = world.clock % 1440 - 15                          # (each tick looks back over the half hour just gone)
    if m < 6 * 60 or m >= 21 * 60 + 30:
        return []
    rng = city.rng
    from .intents import condition
    groups = {}
    act = np.where(c.active())[0]
    if len(act) > 400:                                  # a big town: a slice of it each tick is plenty
        act = np.asarray(rng.sample(act.tolist(), 400))
    for i in act:
        h = c.handles[int(i)]
        cnd = condition(city, h)
        if cnd and cnd["state"] in ("jailed", "wounded"):
            continue
        b = doing(world, i, m)
        if b["what"] == "sleep":
            continue
        hs = F.land(world)["houses"].get(h)
        place = b["where"] if b["where"] != "home" else "home:" + str(hs["n"] // 4 if hs else "-")
        if b["where"] == "visit":
            place = "visit:" + "|".join(sorted((h, b["with"] or "")))
        groups.setdefault((b["what"], place), []).append(int(i))
    out = []
    keys = list(groups)
    rng.shuffle(keys)
    for what, place in keys:
        idx = groups[(what, place)]
        if len(idx) < 2 or what not in BLOCK_KIND:
            continue
        n = max(1, min(4, len(idx) // (5 if what in ("breakfast", "lunch", "supper") else 6)))
        if rng.random() > min(1.0, len(idx) / 5):
            continue
        for _ in range(n):
            if len(out) >= PER_TICK:
                break
            a = rng.choice(idx)
            ha = c.handles[a]
            # half the time it's someone they already have history with (that's how stories keep going)
            known = [o for o, v in friends_of(world, ha, 6) if o in c.index and c.index[o] in idx]
            hb = rng.choice(known) if known and rng.random() < 0.5 else c.handles[rng.choice([x for x in idx if x != a])]
            out.append(meet(world, ha, hb, what, place.split(":")[0], rng, t=world.clock - 15 + rng.randint(-8, 6)))
    return [e for e in out if e]


def meet(world, a, b, what, where, rng=None, t=None):
    """One small thing between a and b. Returns the encounter (also kept for the 3D view and the feed)."""
    city, c = world.city, world.city.citizens
    rng = rng or city.rng
    bd = bonds(world).setdefault(_key(a, b), {"s": 0, "n": 0, "stage": None})
    temper = float(c.temper[c.index[a]]) if a in c.index else 0.0
    kind, d, anim, label, lines = _choose(world, BLOCK_KIND.get(what, ["meal"]), bd["s"], temper, rng)
    work_place = _work_kind(world, where)
    vals = _fill(world, kind, a, b, work_place, rng)
    text = rng.choice(lines).format(a="@" + a, b="@" + b, **vals)
    bd["s"] += d
    bd["n"] += 1
    bd["last"] = text
    bd["day"] = city.day + 1
    if a in c.index:
        c.mood[c.index[a]] = float(np.clip(c.mood[c.index[a]] + d * 0.01, 0, 1))
    if b in c.index:
        c.mood[c.index[b]] = float(np.clip(c.mood[c.index[b]] + d * 0.015, 0, 1))
    city.living["enc_n"] = city.living.get("enc_n", 0) + 1
    e = {"n": city.living["enc_n"], "t": world.clock if t is None else t, "a": a, "b": b, "kind": kind, "anim": anim, "label": label, "text": text,
         "what": what, "where": where, "d": d}
    log = city.living.setdefault("encounters", [])
    log.append(e)
    del log[:-600]
    _story(world, a, b, bd, text, where)
    return e


def _work_kind(world, where):
    """'b:b3' -> 'farm' (what kind of work), 'p:p4' -> 'build', a place stays a place."""
    if where.startswith("b:"):
        b = F.building(world, where[2:])
        return b["kind"] if b else "*"
    if where.startswith("p:"):
        return "build"
    return where if where in F.places(world) else "*"


def _at(world, where):
    if where.startswith("b:"):
        b = F.building(world, where[2:])
        return "at " + F.roles_the(F.bare(b["name"])) if b else "at work"
    if where.startswith("p:"):
        p = next((p for p in F.land(world)["projects"] if p["id"] == where[2:]), None)
        return f"on the building site of {p['name']}" if p else "on a building site"
    return AT.get(where, "by the fire")


AT = {"woods": "in the woods", "hill": "up on the hill", "river": "down by the river", "field": "out in the field",
      "road": "on the old road", "commons": "by the fire", "square": "in the square", "home": "outside their door",
      "visit": "on a doorstep"}
CAP = {"friends": 3, "close": 1, "rivals": 2, "enemies": 1}      # a day: the rest wait their turn (tomorrow)


def _story(world, a, b, bd, text, where="commons"):
    """When the little things add up: friends, best friends, a feud, a fight."""
    s, stage, rng = bd["s"], bd.get("stage"), world.city.rng
    A, B = "@" + a, "@" + b
    at = _at(world, where)
    small = text[0].lower() + text[1:]
    nxt = ("close" if s >= 12 and stage == "friends" else "friends" if s >= 5 and not stage else
           "enemies" if s <= -8 and stage == "rivals" else "rivals" if s <= -4 and not stage else None)
    if not nxt:
        return None
    day = world.city.day + 1
    told = world.city.living.setdefault("stories_told", {})
    if told.get("day") != day:
        told.clear()
        told["day"] = day
    if told.get(nxt, 0) >= CAP[nxt]:
        return None
    told[nxt] = told.get(nxt, 0) + 1
    bd["stage"] = nxt
    if nxt == "close":
        line, drama = rng.choice([
            f"Everyone has noticed: {A} and {B} are inseparable now. (Today {small}.)",
            f"{A} and {B} have started finishing each other's sentences, which is annoying everyone else.",
            f"{A} asked {B} to share a roof when the next house goes up. {B} said yes before they'd finished asking.",
            f"{A} carved {B}'s name into the big oak {at}. {B} pretended to be embarrassed.",
        ]), 2
    elif nxt == "friends":
        line, drama = rng.choice([f"{A} and {B} have become friends. It started small: {small}.",
                                  f"Somewhere between one thing and another, {A} and {B} became friends. (Today {small}.)",
                                  f"{A} and {B} are friends now - you can tell, they've started saving each other seats."]), 1
    elif nxt == "rivals":
        line, drama = rng.choice([f"A feud is brewing between {A} and {B}: {small}.",
                                  f"{A} and {B} can't stand each other, and everyone knows it. Today {small}.",
                                  f"{A} has started muttering whenever {B} walks past. Today {small}."]), 1
    else:
        from .intents import set_condition
        loser = rng.choice([a, b])
        other = a if loser == b else b
        set_condition(world.city, loser, "wounded", 1, f"a fight with @{other}")
        bd["s"] = -4
        line, drama = rng.choice([
            f"The feud between {A} and {B} came to blows {at}. @{loser} came off worse and is nursing a black eye; "
            f"Aldric made them shake hands, and neither meant it.",
            f"{A} and {B} finally went at it {at}, rolling in the mud until someone threw a bucket of water over them. "
            f"@{loser} limped home.",
            f"It took three people to pull {A} off {B} {at}. @{loser} won't be working tomorrow.",
        ]), 2
    world.moment("world", line, drama, public=True, place=where if where in F.places(world) else None, handles=[a, b])
    return line


def people_line(world, h):
    """For the bard: who this person is close to or at odds with, and the latest small thing between them."""
    bits = []
    for o, v in friends_of(world, h):
        if abs(v["s"]) < 2:
            continue
        rel = {"close": "inseparable from", "friends": "friends with", "rivals": "feuding with",
               "enemies": "at war with"}.get(v.get("stage"), "getting on with" if v["s"] > 0 else "not getting on with")
        bits.append(f"{rel} @{o} (latest: {v.get('last', '')[:110]})")
    return "; ".join(bits)


def today(world, since):
    """Today's encounters, for the 3D view and the feed."""
    return [e for e in world.city.living.get("encounters", []) if e["t"] > since]
