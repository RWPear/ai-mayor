"""The capital of Emberfall, as places the king can walk to.

Every place has a few features in a current state ("the road: churned mud"),
improvements that could be made there, and the kinds of subjects you'd find
there at that hour. When the king stands somewhere he sees all of that - which
is how "this road should be paved with stone" happens: he notices, decides it's
his project, pays for it, works on it, and the place really changes (and the 3D
view will show it).

Castle rooms are the same kind of thing: they start ruined, and building them
unlocks the king's tools.

The king (or the model) can also invent an improvement nobody wrote, at any
place - it's bounded the same way invented decrees are (a size and an effect
package).
"""
import copy

from ..roles import JOBS

# id -> place. walk: minutes from the castle gate. people: jobs found there (by hour range).
PLACES = {
    "throne_room":    {"offers": "the throne, petitioners' benches, the court",
                       "name": "the throne room", "area": "castle", "walk": 10,
                       "features": {"throne": "a creaky wooden throne with one short leg",
                                    "banners": "faded, moth-eaten banners"}},
    "bedchamber":     {"offers": "his bed and a washbasin",
                       "name": "the royal bedchamber", "area": "castle", "walk": 10,
                       "features": {"bed": "a lumpy bed"}},
    "kitchens":       {"offers": "the cooks' stew pot, fresh bread, and whatever's in the larder",
                       "name": "the castle kitchens", "area": "castle", "walk": 8,
                       "features": {"hearth": "a smoky hearth"}, "people": {(5, 21): ["baker"]}},
    "castle_yard":    {"offers": "practice swords, straw dummies and soldiers drilling",
                       "name": "the castle yard", "area": "castle", "walk": 3,
                       "features": {"yard": "a muddy training yard"},
                       "people": {(7, 19): ["soldier", "guard", "archer"]}},
    "war_room":       {"name": "the war room", "area": "castle", "walk": 10, "room": True},
    "spymaster_tower": {"name": "the spymaster's tower", "area": "castle", "walk": 12, "room": True},
    "great_hall":     {"name": "the great hall", "area": "castle", "walk": 8, "room": True},
    "dungeon":        {"name": "the dungeon", "area": "castle", "walk": 10, "room": True},
    "royal_gardens":  {"offers": "benches, weeds, birdsong",
                       "name": "the royal gardens", "area": "castle", "walk": 6,
                       "features": {"beds": "overgrown flower beds full of weeds"}},
    "market_square":  {"offers": "stalls selling fruit, fish, cheese and trinkets",
                       "name": "the market square", "area": "town", "walk": 15,
                       "features": {"square": "a few rickety stalls on bare dirt"},
                       "people": {(7, 18): ["merchant", "baker", "tailor", "farmer"]}},
    "tavern":         {"offers": "ale, meat pies, dice games and gossip",
                       "name": "the tavern", "area": "town", "walk": 18,
                       "features": {"tavern": "a dark, crowded tavern with sticky tables"},
                       "people": {(17, 24): ["innkeeper", "bard", "miner", "woodcutter", "soldier", "farmer"],
                                  (11, 17): ["innkeeper", "bard"]}},
    "kings_street":   {"offers": "carts, mud and passers-by",
                       "name": "King's Street", "area": "town", "walk": 12,
                       "features": {"road": "a dirt road churned into mud, full of potholes"},
                       "people": {(6, 20): ["merchant", "farmer", "mason", "tailor"]}},
    "smithy":         {"offers": "hammers, blades, horseshoes and tools",
                       "name": "the smithy", "area": "town", "walk": 16,
                       "features": {"forge": "a busy forge"}, "people": {(6, 19): ["blacksmith", "mason"]}},
    "chapel":         {"offers": "candles, old books and silence",
                       "name": "the chapel", "area": "town", "walk": 14,
                       "features": {"bell": "a cracked bell that clanks instead of rings"}},
    "river":          {"offers": "fishing spots, reeds and cold water",
                       "name": "the river", "area": "town", "walk": 22,
                       "features": {"crossing": "a rotten plank bridge", "docks": "a single muddy jetty"},
                       "people": {(5, 18): ["fisher", "sailor", "miller"]}},
    "fields":         {"offers": "open sky, sheep and farmers at work",
                       "name": "the fields outside the walls", "area": "outside", "walk": 30,
                       "features": {"fields": "thin rows of wheat on dry ground"},
                       "people": {(5, 19): ["farmer", "shepherd", "miller"]}},
    "city_walls":     {"offers": "a view over the fields to the northern hills",
                       "name": "the edge of town", "area": "town", "walk": 20,
                       "features": {"edge": "no wall at all - houses just trail off into open fields"},
                       "people": {(0, 24): ["guard", "archer", "scout"]}},
}

# castle rooms: ruins at the start. Rebuilding one quietly unlocks tools (he finds out when it's done)
ROOMS = {
    "war_room":        {"name": "the war room", "size": "medium", "unlocks": "garrison soldiers in a hold"},
    "spymaster_tower": {"name": "the spymaster's tower", "size": "medium", "unlocks": "send spies"},
    "great_hall":      {"name": "the great hall", "size": "medium", "unlocks": "throw feasts"},
    "dungeon":         {"name": "the dungeon", "size": "small", "unlocks": "jail criminals"},
}

SIZES = {"small": {"cost_pc": 3, "days": 2}, "medium": {"cost_pc": 7, "days": 4}, "large": {"cost_pc": 14, "days": 7}}


def cost(size, pop):
    """Gold for a project of this size: scales with the kingdom, never dirt cheap."""
    return SIZES[size]["cost_pc"] * max(60, pop)


def new_town():
    """The town's state for a new kingdom (saved in city.living['town']). There are no walls to start with."""
    return {"features": {pid: dict(p.get("features", {})) for pid, p in PLACES.items()},
            "rooms": {r: False for r in ROOMS}, "works": [], "done": [], "invented": {},
            "walls": {"capacity": 0, "built": None}}


# ---------------------------------------------------------------- houses and walls
def settle(world, start):
    """New subjects (index >= start) get a house in their hold: inside the walls if there's room, else outside."""
    import numpy as np
    city, c = world.city, world.city.citizens
    t = city.living["town"]
    new = np.arange(start, len(c.handles))
    if not len(new):
        return 0
    room = max(0, t["walls"]["capacity"] - int((c.walled == 1).sum()))
    inside = new[:room]
    c.walled[inside] = 1
    outside = len(new) - len(inside)
    if t["walls"]["capacity"] and outside:
        world.moment("world", f"{len(new)} new families moved to Emberfall. {outside} of them had to build outside the "
                              f"walls.", 1, public=True)
    elif len(new) >= 3:
        world.moment("world", f"{len(new)} new families moved to Emberfall and put up houses.", 1, public=True)
    return len(new)


def build_walls(world, quality):
    """The king's walls are finished: everyone living now (and a little more) fits inside."""
    import numpy as np
    city, c = world.city, world.city.citizens
    t = city.living["town"]
    houses = int(c.active().sum())
    extra = {"success": 1.3, "shoddy": 1.05}.get(quality, 1.0)
    t["walls"]["capacity"] = max(t["walls"]["capacity"], int(houses * extra) + 20)
    t["walls"]["built"] = city.day + 1
    t["features"]["city_walls"]["edge"] = ("stone walls around the town" if quality == "success"
                                           else "crooked walls around the town, with a few weak spots")
    room = t["walls"]["capacity"] - int((c.walled == 1).sum())
    out = np.where(c.active() & (c.walled == 0))[0][:max(0, room)]
    c.walled[out] = 1


def burn_houses(world, ward, raiders):
    """A raid that got through burns houses outside the walls in that hold. Returns the handles hit."""
    import numpy as np
    city, c = world.city, world.city.citizens
    pool = np.where(c.active() & (c.ward == ward) & (c.walled == 0) & (c.burned == 0))[0]
    if not len(pool):
        return []
    n = min(len(pool), max(1, raiders // 3))
    hit = np.array(city.rng.sample(pool.tolist(), n), np.int64)
    c.burned[hit] = city.day + 1
    c.wealth[hit] *= 0.7
    c.mood[hit] = np.clip(c.mood[hit] - 0.15, 0, 1)
    for i in hit[:50]:
        c.log(int(i), city.day + 1, "lost their house to the raiders' fire")
    return [c.handles[i] for i in hit]


def rebuild(world):
    """Three days after a fire, neighbours have helped put the house back up."""
    c = world.city.citizens
    back = (c.burned > 0) & (c.burned <= world.city.day + 1 - 3)
    c.burned[back] = 0
    return int(back.sum())


def summary(world):
    c = world.city.citizens
    a = c.active()
    houses = int((a & (c.walled >= 0)).sum())
    homeless = int((a & (c.walled == -1)).sum())
    tents = int((a & (c.walled == -2)).sum())
    inside = int((a & (c.walled == 1)).sum())
    burned = int((a & (c.burned > 0)).sum())
    t = world.city.living["town"]
    walls = "no walls" if not t["walls"]["capacity"] else f"{inside} inside the walls, {houses - inside} outside"
    return (f"{houses} houses ({walls}" + (f", {burned} burned down" if burned else "") + ")"
            + (f", {homeless} sleeping rough" if homeless else "") + (f", {tents} in tents" if tents else ""))


def court_place(world):
    """Where the king hears cases: the throne room, or on the frontier his shack (until he builds a hall)."""
    land = world.city.living["town"].get("land")
    return land["court_place"] if land else "throne_room"


def ruins(town):
    return [pid for pid, ok in town["rooms"].items() if not ok]


def places(town):
    """The places there are: the capital's (PLACES), or the frontier's own, which grow as things get built."""
    return town.get("places") or PLACES


def place_of(pid, town):
    p = places(town).get(pid) or PLACES.get(pid) or {"name": str(pid)}
    if p.get("room") and not town["rooms"].get(pid):
        return f"{p['name']} (a ruin - it hasn't been built yet)"
    return p["name"]


def describe(town, pid):
    feats = town["features"].get(pid, {})
    return "; ".join(f"{k}: {v}" for k, v in feats.items()) or "nothing much"


def jobs_here(pid, hour):
    for (a, b), jobs in PLACES.get(pid, {}).get("people", {}).items():
        if a <= hour < b:
            return [j for j in jobs if j in JOBS]
    return []


def match_place(text, town=None):
    t = str(text or "").lower().replace("'", "").replace("_", " ")
    if town is not None and town.get("land"):
        from .frontier import match_in
        return match_in(town["places"], text)
    for pid, p in PLACES.items():
        name = p["name"].lower().replace("the ", "").replace("'", "")
        if pid.replace("_", " ") in t or name in t:
            return pid
    for word, pid in (("road", "kings_street"), ("street", "kings_street"), ("market", "market_square"),
                      ("bridge", "river"), ("wall", "city_walls"), ("garden", "royal_gardens"),
                      ("bed", "bedchamber"), ("sleep", "bedchamber"), ("kitchen", "kitchens"), ("yard", "castle_yard"),
                      ("throne", "throne_room"), ("hall", "great_hall"), ("tower", "spymaster_tower"),
                      ("spy", "spymaster_tower"), ("war", "war_room"), ("forge", "smithy"), ("field", "fields")):
        if word in t:
            return pid
    return None


def copy_town(t):
    return copy.deepcopy(t)
