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
    "throne_room":    {"name": "the throne room", "area": "castle", "walk": 10,
                       "features": {"throne": "a creaky wooden throne with one short leg",
                                    "banners": "faded, moth-eaten banners"}},
    "bedchamber":     {"name": "the royal bedchamber", "area": "castle", "walk": 10,
                       "features": {"bed": "a lumpy bed"}},
    "kitchens":       {"name": "the castle kitchens", "area": "castle", "walk": 8,
                       "features": {"hearth": "a smoky hearth"}, "people": {(5, 21): ["baker"]}},
    "castle_yard":    {"name": "the castle yard", "area": "castle", "walk": 3,
                       "features": {"yard": "a muddy training yard"},
                       "people": {(7, 19): ["soldier", "guard", "archer"]}},
    "war_room":       {"name": "the war room", "area": "castle", "walk": 10, "room": True},
    "spymaster_tower": {"name": "the spymaster's tower", "area": "castle", "walk": 12, "room": True},
    "great_hall":     {"name": "the great hall", "area": "castle", "walk": 8, "room": True},
    "dungeon":        {"name": "the dungeon", "area": "castle", "walk": 10, "room": True},
    "royal_gardens":  {"name": "the royal gardens", "area": "castle", "walk": 6,
                       "features": {"beds": "overgrown flower beds full of weeds"}},
    "market_square":  {"name": "the market square", "area": "town", "walk": 15,
                       "features": {"square": "a few rickety stalls on bare dirt"},
                       "people": {(7, 18): ["merchant", "baker", "tailor", "farmer"]}},
    "tavern":         {"name": "the tavern", "area": "town", "walk": 18,
                       "features": {"tavern": "a dark, crowded tavern with sticky tables"},
                       "people": {(17, 24): ["innkeeper", "bard", "miner", "woodcutter", "soldier", "farmer"],
                                  (11, 17): ["innkeeper", "bard"]}},
    "kings_street":   {"name": "King's Street", "area": "town", "walk": 12,
                       "features": {"road": "a dirt road churned into mud, full of potholes"},
                       "people": {(6, 20): ["merchant", "farmer", "mason", "tailor"]}},
    "smithy":         {"name": "the smithy", "area": "town", "walk": 16,
                       "features": {"forge": "a busy forge"}, "people": {(6, 19): ["blacksmith", "mason"]}},
    "chapel":         {"name": "the chapel", "area": "town", "walk": 14,
                       "features": {"bell": "a cracked bell that clanks instead of rings"}},
    "river":          {"name": "the river", "area": "town", "walk": 22,
                       "features": {"crossing": "a rotten plank bridge", "docks": "a single muddy jetty"},
                       "people": {(5, 18): ["fisher", "sailor", "miller"]}},
    "fields":         {"name": "the fields outside the walls", "area": "outside", "walk": 30,
                       "features": {"fields": "thin rows of wheat on dry ground"},
                       "people": {(5, 19): ["farmer", "shepherd", "miller"]}},
    "city_walls":     {"name": "the city walls", "area": "town", "walk": 20,
                       "features": {"walls": "a wooden palisade with gaps you could walk through"},
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
    """The town's state for a new kingdom (saved in city.living['town'])."""
    return {"features": {pid: dict(p.get("features", {})) for pid, p in PLACES.items()},
            "rooms": {r: False for r in ROOMS}, "works": [], "done": [], "invented": {}}


def ruins(town):
    return [pid for pid, ok in town["rooms"].items() if not ok]


def place_of(pid, town):
    p = PLACES[pid]
    if p.get("room") and not town["rooms"].get(pid):
        return f"{p['name']} (a ruin - it hasn't been built yet)"
    return p["name"]


def describe(town, pid):
    feats = town["features"].get(pid, {})
    return "; ".join(f"{k}: {v}" for k, v in feats.items()) or "nothing much"


def jobs_here(pid, hour):
    for (a, b), jobs in PLACES[pid].get("people", {}).items():
        if a <= hour < b:
            return [j for j in jobs if j in JOBS]
    return []


def match_place(text, town=None):
    t = str(text or "").lower().replace("'", "").replace("_", " ")
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
