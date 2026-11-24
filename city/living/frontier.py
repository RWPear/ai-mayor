"""Emberfall: a kingdom that grows on People Power.

Aldric starts alone in a shack on a floating island. Everyone who follows walks in the same day and gets a little
house of their own on the town's streets (free, automatic). From then on the kingdom runs on two things:

PEOPLE POWER - every follower works one shift a day, whether or not they say anything. Followers who comment work
  an extra shift that day, and what they say steers where: "I'll help at the farm", "I want to be a brewer",
  "I help build the tavern". People who keep turning up at the same kind of work become it (a farmer, a brewer,
  a builder) and keep going there. Shifts are counted once a day, in the evening:
    - a building only RUNS if its crew turns up: a farm needs 10 people a day, a tavern 3. Short of that it
      stands idle (and slowly falls into disrepair);
    - a building only GETS BUILT by builders: a brewery is 10 person-days, so 10 people finish it in a day and
      one person in ten. Nobody works on the blacksmith, the blacksmith never goes up. A day at the least.
GOLD - the one thing you can count. Running buildings earn it, the people pay a little tax when they're happy, and
  followers can give theirs. Building costs no gold - but the gold Aldric puts into a building decides which one
  you get: the same 12 person-days of work make a beer tent or, with 250 gold behind them, a beer hall. Gold put into
  a standing building later upgrades it (and takes builders again).

WANTS - the people want things: food, water, a pint, a seat at a tavern, safety at night, music, bread, a chapel,
  wine, a market. More of them want more of it as the place grows. A want is met by RUNNING buildings that serve
  it; how well they're met is the town's happiness, which drifts everyone's mood - and unhappy people don't always
  turn up for their shift. Aldric decides what gets built and how much gold goes into it; the people decide
  whether it gets built at all, by turning up.

The catalog (what can be built, crews, person-days, tiers by gold) is content/buildings.yaml.
State lives in city.living['town']['land'].
"""
import math
import re
import zlib

import numpy as np
import yaml

from ..config import CONTENT
from . import life

ROAD = 2                     # citizens.status: on the road (old saves only: people arrive at once now)
STAGES = [("city", 200), ("town", 50), ("village", 10), ("hamlet", 1), ("alone", 0)]
COURT_ARRIVES = {"hamlet": "jester", "village": "steward"}
STREAK = 4                   # days at the same work before you become it
DISREPAIR = 0.35             # a building's condition below this: "in disrepair" (it still works when crewed)

PLACES = {   # the island's own places (buildings add theirs). walk = minutes from the keep
    "shack": {"name": "the keep", "walk": 2, "offers": "Aldric's home, whatever it is this week"},
    "square": {"name": "the square", "walk": 2, "offers": "the fire everyone eats at, and the town's gossip"},
    "field": {"name": "the field", "walk": 4, "offers": "open grass, room to build"},
    "woods": {"name": "the woods", "walk": 12, "offers": "birch and old oaks, mushrooms, quiet"},
    "river": {"name": "the river", "walk": 15, "offers": "slow brown water with fish in it"},
    "hill": {"name": "the rocky hill", "walk": 20, "offers": "a crag with a view of the whole island"},
    "road": {"name": "the old road", "walk": 8, "offers": "a rutted track to the island's edge - travellers come this way"},
}
FEATURES = {
    "shack": {"shack": "a one-room shack: the roof leaks, the door won't shut"},
    "square": {"fire": "a fire ring with logs to sit on"},
    "field": {"field": "knee-high grass and thistles"},
    "woods": {"trees": "dense birch and oak"},
    "river": {"bank": "muddy banks and reeds"},
    "hill": {"stones": "loose grey stone and a long view"},
    "road": {"track": "a rutted dirt track, a rotten signpost"},
}

_CAT = None


def catalog():
    """content/buildings.yaml: {type: spec}, plus 'wants' and 'houses'."""
    global _CAT
    if _CAT is None:
        _CAT = yaml.safe_load((CONTENT / "buildings.yaml").read_text())
    return _CAT


def kinds():
    return {k: v for k, v in catalog().items() if k not in ("wants", "houses")}


def spec(kind):
    return kinds()[kind]


def crew_of(b):
    """People a day to run it: finer versions serve more people and need more hands."""
    s = spec(b["kind"])
    return int(round(s["crew"] * (1 + 0.6 * b.get("tier", 0)))) if s["crew"] else 0


def tier_for(kind, gold):
    """The best tier this much gold buys (or -1 if it isn't enough for the least of it)."""
    tiers = spec(kind)["tiers"]
    best = -1
    for k, t in enumerate(tiers):
        if gold >= t["gold"]:
            best = k
    return best


# ---------------------------------------------------------------- state
def new_town():
    return {"features": {pid: dict(f) for pid, f in FEATURES.items()},
            "places": {pid: dict(p) for pid, p in PLACES.items()},
            "rooms": {}, "works": [], "done": [], "invented": {}, "walls": {"capacity": 0, "built": None},
            "land": {"buildings": [{"id": "b0", "kind": "keep", "tier": 0, "gold": 0, "name": "the shack",
                                    "place": "shack", "state": "standing", "day": 0, "condition": 1.0}],
                     "projects": [], "houses": {}, "blocks": [], "prof": {}, "streak": {}, "pref": {},
                     "today": {}, "jobs": {}, "history": [], "happiness": 0.6, "wants": {},
                     "stage": "alone", "crowned": False, "court": [], "court_place": "shack", "officers": {},
                     "rally": None, "built_n": 0, "know": []}}


def is_frontier(city):
    return bool(getattr(city, "living", None) and city.living.get("town", {}).get("land"))


def land(world_or_city):
    city = getattr(world_or_city, "city", world_or_city)
    return city.living["town"]["land"]


def settled(city):
    return int(city.citizens.active().sum())


def on_road(city):
    return int((city.citizens.status == ROAD).sum())


def stage_of(n):
    return next(name for name, need in STAGES if n >= need)


def capacity(city):                      # everyone has a house: there are always exactly enough
    return settled(city)


def housed(city):
    return settled(city)


def tents(city):
    return 0


def free_beds(city):
    return 0


def title(city, text):
    """Before he's crowned, nobody calls him king."""
    if not is_frontier(city) or land(city).get("crowned"):
        return text
    for a, b in (("King Aldric", "Aldric"), ("The king's", "Aldric's"), ("the king's", "Aldric's"),
                 ("The king", "Aldric"), ("the king", "Aldric")):
        text = text.replace(a, b)
    return text


def bare(name):
    """'a small cottage' -> 'small cottage'."""
    return re.sub(r"^(a|an|the|my|our)\s+", "", str(name), flags=re.I)


def roles_the(name):
    return name if name.lower().startswith(("the ", "a ", "an ")) else f"the {name}"


# ---------------------------------------------------------------- places
def places(world):
    return world.city.living["town"]["places"]


def place_of(world, pid):
    p = places(world).get(pid)
    return p["name"] if p else pid


def match(world, text):
    return match_in(places(world), text)


def match_in(pl, text):
    t = str(text or "").lower().replace("'", "")
    if not t:
        return None
    for pid, p in pl.items():
        if pid.replace("_", " ") in t or p["name"].lower().replace("the ", "").replace("your ", "").replace("'", "") in t:
            return pid
    for word, pid in (("home", "shack"), ("hall", "shack"), ("keep", "shack"), ("castle", "shack"),
                      ("forest", "woods"), ("tree", "woods"), ("stream", "river"), ("water", "river"),
                      ("rock", "hill"), ("fire", "square"), ("town", "square"), ("meadow", "field")):
        if word in t and pid in pl:
            return pid
    return None


def building(world, bid):
    return next((b for b in land(world)["buildings"] if b["id"] == bid), None)


def find_building(world, text, standing=True):
    """'the tavern', 'brewery', 'b4', a building's name -> the building."""
    t = str(text or "").lower()
    bs = [b for b in land(world)["buildings"] if not standing or b["state"] == "standing"]
    for b in bs:
        if t == b["id"] or b["name"].lower() in t or bare(b["name"]).lower() in t:
            return b
    for b in bs:
        if b["kind"] in t or spec(b["kind"])["job"] in t:
            return b
    return None


# ---------------------------------------------------------------- the island
# Emberfall is on a floating island above the clouds. As the place grows, new land rises out of the clouds at the rim.
ISLAND = {"pos": [5, -10], "r": 175}
LANDS = [("the east meadow", "meadow", "wildflowers, fat bees and grass up to your waist"),
         ("the glass cliffs", "cliffs", "pale stone that rings like a bell when you strike it"),
         ("the silver grove", "grove", "silver-barked trees and fruit nobody can name"),
         ("the warm springs", "springs", "steaming pools that smell of eggs and lightning"),
         ("the old ruins", "ruins", "tumbled stones carved in a language nobody can read"),
         ("the crystal fields", "crystals", "crystals the size of fists growing out of the grass"),
         ("the misty point", "point", "a long spit of land where the clouds pour over like water"),
         ("the sky garden", "skygarden", "a hanging garden of vines on a ledge over nothing")]
LOBE_ANGLES = [20, 110, 200, 60, 160, 250, 330, 290]      # degrees, east = 0, north = 90 (the road leaves south)


def island(city):
    return land(city).setdefault("island", {"pos": list(ISLAND["pos"]), "r": ISLAND["r"], "lobes": []})


def grow_island(city, n=1):
    """New land rises out of the clouds at the island's rim - with a new place on it. Returns the new lands."""
    isl = island(city)
    t = city.living["town"]
    out = []
    for _ in range(n):
        k = len(isl["lobes"])
        if k >= len(LANDS):
            break
        name, pid, offers = LANDS[k]
        a = math.radians(LOBE_ANGLES[k])
        r = 62 + 10 * (k % 3)
        d = isl["r"] + r * 0.42
        pos = [round(isl["pos"][0] + d * math.cos(a)), round(isl["pos"][1] + d * math.sin(a))]
        lobe = {"id": pid, "name": name, "pos": pos, "r": r, "day": city.day + 1}
        isl["lobes"].append(lobe)
        t["places"][pid] = {"name": name, "walk": 30 + 5 * k, "offers": offers, "pos": pos, "risen": city.day + 1}
        t["features"][pid] = {"land": f"new land, risen from the clouds on day {city.day + 1}: {offers}"}
        out.append(lobe)
        city.living.setdefault("risen_today", []).append(name)
    return out


RISE_LINES = ["The ground shook before dawn. When the mist cleared, there was new land at the island's edge: {name} - "
              "{offers}.",
              "Something huge moved under the clouds all night. By morning {name} had risen out of them: {offers}.",
              "New land rose from the clouds at the edge of Emberfall: {name}. Nobody has set foot on it yet."]


def announce_risen(world):
    for name in world.city.living.pop("risen_today", []) or []:
        p = next((p for p in places(world).values() if p["name"] == name), {})
        text = world.city.rng.choice(RISE_LINES).format(name=name, offers=p.get("offers", "unknown ground"))
        world.moment("world", text, 3, public=True)
        world.notify(f"New land: {name}")


# ---------------------------------------------------------------- arriving: a house each
ARRIVE_LINES = ["walked up the old road with everything they own on their back",
                "came over the hill at {time}, muddy to the knees", "turned up on the old road with a bundle and a grin",
                "followed the smoke of Aldric's fire into town", "arrived footsore and hungry",
                "came up the road behind a goat that wasn't theirs", "walked in from the edge of the island, looking around a lot"]


def join_road(world, idx):
    """New followers come to Emberfall straight away, and get a house."""
    c = world.city.citizens
    idx = np.asarray(idx, np.int64)
    if not len(idx):
        return 0
    idx = idx[c.status[idx] == 0]
    if len(idx):
        arrive(world, idx)
    return len(idx)


def house_of(world, h):
    return land(world)["houses"].get(h)


def arrive(world, idx=None):
    """People reach Emberfall: each gets a little house on the next lot of the town's streets. They don't get a reply
    of their own: that they just arrived goes into the reply to whatever they said (see intents.process)."""
    city, c, L = world.city, world.city.citizens, land(world)
    if idx is None:
        idx = np.where(c.status == ROAD)[0]
    idx = np.asarray(idx, np.int64)
    if not len(idx):
        return 0
    before = L.get("stage", "alone")
    c.status[idx] = 0
    c.joined[idx] = city.day + 1
    c.walled[idx] = 1 if city.living["town"]["walls"].get("built") else 0
    new_here = [int(i) for i in idx if c.handles[int(i)] not in L["houses"]]
    c.wealth[new_here] = 5                   # nobody brings much: a coin a shift from here on
    from . import scene
    new = city.living.setdefault("just_arrived", {})
    for i in idx:
        u = c.handles[int(i)]
        if u not in L["houses"]:
            L["houses"][u] = {"n": len(L["houses"]), "tier": 0, "gold": 0, "day": city.day + 1, "t": world.clock}
            scene.house_lot(world, L["houses"][u]["n"])
        how = city.rng.choice(ARRIVE_LINES).format(time=world.now_str().split(", ")[-1])
        new[u] = {"day": city.day + 1, "text": f"{how}, and moved into a little house of their own on "
                                               f"{scene.street_of(world, L['houses'][u]['n'])}"}
        c.log(int(i), city.day + 1, "arrived in Emberfall and got a house")
    for u in list(new):
        if new[u]["day"] < city.day:
            del new[u]
    names = [c.handles[int(i)] for i in idx[:4]]
    who = ", ".join("@" + h for h in names) + (f" and {len(idx) - 4} more" if len(idx) > 4 else "")
    if len(idx) > 1:
        text = f"{len(idx)} newcomers walked up the old road: {who}. {len(idx)} new houses went up on the streets by nightfall."
    else:
        text = f"@{names[0]} {new[names[0]]['text']}."
    world.moment("world", text, 3 if len(idx) >= 5 else 1, public=True, place="road", handles=names)
    if len(idx) >= 5:
        world.notify(text)
    _stage(world, before)
    assign(world)
    return len(idx)


def upgrade_house(world, h, gold):
    """Their own gold into their own house. Returns (new tier name or None, what it cost)."""
    c, L = world.city.citizens, land(world)
    hs = L["houses"].get(h)
    i = c.index.get(h)
    if not hs or i is None:
        return None, 0
    tiers = catalog()["houses"]
    have = int(c.wealth[i])
    spend = min(have, gold if gold > 0 else have)
    target = hs["tier"]
    for k, t in enumerate(tiers):
        if hs["gold"] + spend >= t["gold"]:
            target = max(target, k)
    if target == hs["tier"]:
        nxt = tiers[min(len(tiers) - 1, hs["tier"] + 1)]
        return None, max(0, nxt["gold"] - hs["gold"])
    cost = tiers[target]["gold"] - hs["gold"]
    c.wealth[i] -= cost
    hs["gold"] += cost
    hs["tier"] = target
    return tiers[target]["name"], cost


# ---------------------------------------------------------------- wants and happiness
def wants(world):
    """{want: {demand, supply, met, line}} for the wants the town has right now."""
    city, L = world.city, land(world)
    n = settled(city)
    W = catalog()["wants"]
    supply = {}
    for b in L["buildings"]:
        if b["state"] == "standing" and b.get("running"):
            s = spec(b["kind"])
            supply[s["want"]] = supply.get(s["want"], 0) + s["serves"] * s["tiers"][b["tier"]]["x"]
    out = {}
    for w, x in W.items():
        if x["weight"] <= 0 or n < x["pop"]:
            continue
        demand = max(1, round(n * x["share"]))
        out[w] = {"demand": demand, "supply": round(supply.get(w, 0)), "met": round(min(1.0, supply.get(w, 0) / demand), 2),
                  "line": x["line"], "weight": x["weight"]}
    return out


def happiness(world):
    w = wants(world)
    if not w:
        return 0.6
    tot = sum(x["weight"] for x in w.values())
    return round(0.25 + 0.75 * sum(x["met"] * x["weight"] for x in w.values()) / tot, 2)


# ---------------------------------------------------------------- people power: who works where today
JOB_WORDS = [  # what a comment says -> the kind of work it steers them to
    (r"\b(build|builder|construct|carpent|hammer|raise|roof|lay bricks|help build|put up)", "build"),
    (r"\b(farm|farmer|field|crop|harvest|plough|plow|plant|sow|cabbage|onion|potato|wheat|hoe|garden|vegetable)", "farm"),
    (r"\b(well|water|bucket)", "well"),
    (r"\b(brew|brewer|beer|ale|hops|mash)", "brewery"),
    (r"\b(tavern|barkeep|bartend|pour|inn|pub|beer tent|beer hall)", "tavern"),
    (r"\b(bake|baker|bread|loaf|loaves|oven|pastr)", "bakery"),
    (r"\b(smith|forge|anvil|blacksmith|metal|horseshoe)", "blacksmith"),
    (r"\b(guard|watch|lookout|patrol|sentry|keep watch)", "watchtower"),
    (r"\b(wall|palisade|fortif)", "palisade"),
    (r"\b(pray|priest|chapel|shrine|bless|monk|nun)", "chapel"),
    (r"\b(sing|music|musician|play the|lute|fiddle|drum|bard|song|dance)", "stage"),
    (r"\b(trade|trader|sell|market|stall|merchant|haggle)", "market"),
    (r"\b(vine|vineyard|grape|vintner)", "vineyard"),
    (r"\b(wine|cellar|cellarer)", "cellar"),
    (r"\b(soldier|barracks|train|drill|spear|sword)", "barracks"),
    (r"\b(teach|teacher|school|lesson|learn|book|letters)", "school"),
    (r"\b(bath|bathhouse|steam|soak)", "baths"),
]


def job_of_text(text):
    t = str(text or "").lower()
    for pat, k in JOB_WORDS:
        if re.search(pat, t):
            return k
    return None


def prof_kind(prof):
    """'farmer' -> 'farm' (the kind of work a profession goes back to)."""
    if prof == "builder":
        return "build"
    return next((k for k, s in kinds().items() if s["job"] == prof), None)


def today(world):
    L = land(world)
    d = world.city.day + 1
    if L["today"].get("day") != d:
        L["today"] = {"day": d, "extra": {}, "nudge": {}, "king": 0}
    return L["today"]


def nudge(world, h, text):
    """A comment: an extra shift today, and a push toward the work it talks about (which sticks a little)."""
    T = today(world)
    T["extra"][h] = 1
    k = job_of_text(text)
    if k:
        T["nudge"][h] = k
        land(world)["pref"][h] = k
    return k


def _priority(world, b):
    """Which buildings get their crew first: what was rallied, then food, then whatever the people are shortest of."""
    L = land(world)
    if L.get("rally") and L["rally"].get("day") == world.city.day + 1 and L["rally"]["id"] == b["id"]:
        return -100
    s = spec(b["kind"])
    w = L.get("wants", {}).get(s["want"]) or {}
    return -(catalog()["wants"].get(s["want"], {}).get("weight", 1) * (1.2 - w.get("met", 0)))


def assign(world):
    """Everyone's job today: crews for the buildings first (people who chose that work, then people who've become
    it, then whoever's free), builders for the projects, odd jobs for the rest. Called each morning and whenever
    someone comments; counted for real in the evening (settle)."""
    from .intents import condition
    city, c, L = world.city, world.city.citizens, land(world)
    T = today(world)
    act = np.where(c.active())[0]
    people, shifts = [], {}
    for i in act:
        h = c.handles[int(i)]
        cnd = condition(city, h)
        if cnd and cnd["state"] in ("jailed", "wounded"):
            continue
        # the unhappiest don't always turn up (the same people each day, so it's a mood, not dice)
        if float(c.mood[i]) < 0.3 and h not in T["extra"] and (zlib.crc32(h.encode()) + city.day) % 3 == 0:
            continue
        people.append(h)
        shifts[h] = 1 + T["extra"].get(h, 0)
    standing = [b for b in L["buildings"] if b["state"] == "standing" and crew_of(b) > 0]
    standing.sort(key=lambda b: _priority(world, b))
    projects = sorted(L["projects"], key=lambda p: 0 if (L.get("rally") or {}).get("id") == p["id"] else 1)
    room = {p["id"]: max(0.0, p["need"] - p["done"]) for p in projects}
    want = {h: T["nudge"].get(h) or L["pref"].get(h) or prof_kind(L["prof"].get(h)) for h in people}
    jobs, crew = {}, {}
    # people who said today they'd build keep a place on the projects (as many as there's work for)
    left = sum(room.values())
    builders = set()
    for h in people:
        if T["nudge"].get(h) == "build" and left > 0:
            builders.add(h)
            left -= shifts[h]
    # 1. crews, most needed building first: the people who want that work, then anyone without a pull elsewhere,
    #    then builders. A crew that can't come together doesn't start - those people go and build instead.
    for b in standing:
        need = crew_of(b)
        keen = [h for h in people if h not in jobs and want[h] == b["kind"]]
        loose = [h for h in people if h not in jobs and not want[h]]
        others = [h for h in people if h not in jobs and want[h] and want[h] not in (b["kind"], "build")
                  and not any(x["kind"] == want[h] for x in standing)]       # (what they want isn't here: they'll pitch in)
        spare = [h for h in people if h not in jobs and want[h] == "build" and h not in builders]
        pool = keen + loose[::-1] + others + spare
        if sum(shifts[h] for h in pool) < need:
            continue
        got = 0
        for h in pool:
            if got >= need and (h not in keen or got >= need * 1.5):
                break
            jobs[h] = b["id"]
            got += shifts[h]
        crew[b["id"]] = got
    running = _running(world, standing, crew)
    for h, j in list(jobs.items()):               # a crew whose supplies didn't come (no beer, no tavern) goes and builds
        if j not in running:
            del jobs[h]
    # 2. builders (the keen ones first, then the rest), as much as the projects can take; 3. odd jobs for the rest
    rest = sorted([h for h in people if h not in jobs], key=lambda h: 0 if want[h] == "build" else 1)
    for h in rest:
        k = want[h]
        target = next((p for p in projects if room[p["id"]] > 0 and p["kind"] == k), None) or \
            next((p for p in projects if room[p["id"]] > 0), None)
        if target:
            jobs[h] = "build:" + target["id"]
            room[target["id"]] -= shifts[h]
        else:
            jobs[h] = "odd"
    crew = {bid: n for bid, n in crew.items() if bid in running}
    L["jobs"] = jobs
    L["crew"] = crew
    for b in L["buildings"]:
        b["running"] = b["id"] in running
    return jobs


def _running(world, standing, crew):
    """Which buildings have their crew today - and what they need (beer for the tavern) running too."""
    ok = {b["id"] for b in standing if crew.get(b["id"], 0) >= crew_of(b)}
    kinds_up = {b["kind"] for b in standing if b["id"] in ok}
    changed = True
    while changed:
        changed = False
        for b in standing:
            need = spec(b["kind"]).get("needs")
            if b["id"] in ok and need and need not in kinds_up:
                ok.discard(b["id"])
                kinds_up = {x["kind"] for x in standing if x["id"] in ok}
                changed = True
    return ok


def job_place(world, h):
    """Where someone works today: a building's place id, a project's, or the square (odd jobs)."""
    L = land(world)
    j = L.get("jobs", {}).get(h)
    if not j or j == "odd":
        return "square"
    if j.startswith("build:"):
        return "p:" + j[6:]
    return "b:" + j


def job_label(world, h):
    L = land(world)
    j = L.get("jobs", {}).get(h)
    if not j or j == "odd":
        return "odd jobs about town"
    if j.startswith("build:"):
        p = next((p for p in L["projects"] if p["id"] == j[6:]), None)
        return f"building {p['name']}" if p else "building"
    b = building(world, j)
    return f"{spec(b['kind'])['job']} at {b['name']}" if b else "work"


# ---------------------------------------------------------------- the evening count
def settle(world):
    """The day's People Power, counted: buildings that ran earn gold and serve the people, builders' shifts go into
    the projects, idle buildings wear, people who keep doing the same work become it."""
    city, c, L = world.city, world.city.citizens, land(world)
    jobs = assign(world)
    T = today(world)
    smithy = any(b["running"] and b["kind"] == "blacksmith" for b in L["buildings"])
    shifts = {h: 1 + T["extra"].get(h, 0) for h in jobs}
    total = sum(shifts.values()) + T.get("king", 0)
    report = {"day": city.day + 1, "shifts": total, "people": len(jobs), "ran": [], "idle": [], "built": [],
              "odd": 0, "gold": 0.0, "extra": len(T["extra"])}
    crew = L.get("crew", {})
    for b in L["buildings"]:
        if b["state"] != "standing" or b["kind"] == "keep":
            continue
        s = spec(b["kind"])
        if b.get("running"):
            g = s["gold"] * s["tiers"][b["tier"]]["x"]
            report["gold"] += g
            b["days_run"] = b.get("days_run", 0) + 1
            b["condition"] = min(1.0, b.get("condition", 1.0) + 0.1)
            report["ran"].append((b["name"], crew.get(b["id"], 0), crew_of(b)))
        elif crew_of(b) > 0:
            came = sum(shifts[h] for h, j in jobs.items() if j == b["id"])
            b["condition"] = max(0.0, b.get("condition", 1.0) - 0.06)
            report["idle"].append((b["name"], came, crew_of(b)))
            if b["condition"] < DISREPAIR and not b.get("disrepair"):
                b["disrepair"] = True
                world.moment("world", f"{b['name'][0].upper() + b['name'][1:]} has stood idle so long it's falling "
                                      f"into disrepair: nobody's turned up to run it.", 1, public=True,
                             place=b.get("place"))
            if b.get("disrepair") and b["condition"] >= DISREPAIR:
                b["disrepair"] = False
    builders = {}
    for h, j in jobs.items():
        if j.startswith("build:"):
            builders.setdefault(j[6:], []).append(h)
    for p in list(L["projects"]):
        hs = builders.get(p["id"], [])
        work = sum(shifts[h] for h in hs) * (1.25 if smithy else 1.0) + (T.get("king", 0) if p is L["projects"][0] else 0)
        if work <= 0 and p["done"] < p["need"]:
            p["idle_days"] = p.get("idle_days", 0) + 1
            continue
        p["done"] = min(p["need"], p["done"] + work)
        p["helpers"] = list(dict.fromkeys(p.get("helpers", []) + hs))[-80:]
        if p["done"] >= p["need"] - 1e-6:
            finish(world, p)
            report["built"].append(p["name"])
        else:
            report.setdefault("building", []).append((p["name"], round(p["done"] / p["need"] * 100)))
    report["odd"] = sum(1 for j in jobs.values() if j == "odd")
    report["gold"] += 0.25 * report["odd"]                      # odd jobs pay a little
    tax = 0.3 * settled(city) * L.get("happiness", 0.6)
    report["gold"] = round(report["gold"] + tax, 1)
    city.treasury += report["gold"]
    for h, n in shifts.items():                                 # a coin a shift, theirs to keep
        i = c.index.get(h)
        if i is not None:
            c.wealth[i] += n
    _professions(world, jobs)
    L["wants"] = wants(world)
    L["happiness"] = happiness(world)
    a = c.active()
    c.mood[a] = np.clip(c.mood[a] + (L["happiness"] - c.mood[a]) * 0.2, 0, 1)
    report["happiness"] = L["happiness"]
    L["history"] = (L["history"] + [report])[-30:]
    world.moment("world", power_line(report), 1, public=True, place="square")
    return report


def power_line(r):
    """'People Power today: 64 shifts (12 extra from comments). The farm ran (11 of 10). ...'"""
    bits = [f"People Power today: {r['shifts']} shifts" + (f" ({r['extra']} from people who spoke up)" if r["extra"] else "") + "."]
    if r["ran"]:
        bits.append("Ran: " + ", ".join(f"{n} ({have}/{need})" for n, have, need in r["ran"][:5]) + ".")
    if r["idle"]:
        bits.append("Stood idle: " + ", ".join(f"{n} ({have} of {need} came)" for n, have, need in r["idle"][:3]) + ".")
    if r.get("built"):
        bits.append("Finished: " + ", ".join(r["built"]) + "!")
    if r.get("building"):
        bits.append("Going up: " + ", ".join(f"{n} {pc}%" for n, pc in r["building"][:3]) + ".")
    if r["odd"]:
        bits.append(f"{r['odd']} had nothing to do but odd jobs.")
    bits.append(f"+{r['gold']:g} gold.")
    return " ".join(bits)


def _professions(world, jobs):
    """Four days at the same kind of work and that's who you are now (and where you go first)."""
    c, L = world.city.citizens, land(world)
    for h, j in jobs.items():
        if j == "odd":
            kind = None
        elif j.startswith("build:"):
            kind = "build"
        else:
            b = building(world, j)
            kind = b["kind"] if b else None
        st = L["streak"].get(h)
        if not kind:
            L["streak"].pop(h, None)
            continue
        if st and st[0] == kind:
            st[1] += 1
        else:
            st = L["streak"][h] = [kind, 1]
        prof = "builder" if kind == "build" else spec(kind)["job"]
        if st[1] >= STREAK and L["prof"].get(h) != prof:
            old = L["prof"].get(h)
            L["prof"][h] = prof
            i = c.index.get(h)
            if i is not None:
                c.roles[int(i)] = prof
            world.reply(h, f"{_ICON.get(kind, '⚒️')} {st[1]} days running at it - you're Emberfall's newest {prof} now"
                           + (f" (no longer {_a(old)})" if old else "") + ". That's where you'll go first.",
                        "profession", credit=f"became {_a(prof)}")


_ICON = {"farm": "🌾", "build": "🔨", "brewery": "🍺", "tavern": "🍻", "bakery": "🍞", "blacksmith": "⚒️",
         "watchtower": "🛡️", "chapel": "🕯️", "stage": "🎶", "market": "🪙", "vineyard": "🍇", "cellar": "🍷",
         "well": "💧", "barracks": "⚔️", "school": "📜", "baths": "♨️"}


def _a(w):
    return ("an " if str(w)[:1].lower() in "aeiou" else "a ") + str(w)


# ---------------------------------------------------------------- building (Aldric decides; people do it)
def max_projects(world):
    return min(12, 1 + settled(world.city) // 20)


def can_build(world, kind):
    """None if Aldric can start one, else why not."""
    if kind not in kinds() or kind == "keep":
        return "nobody knows what that is"
    s = spec(kind)
    n = settled(world.city)
    if n < s["pop"]:
        return f"Emberfall's too small for {_a(bare(s['name']))} yet (it'll matter at {s['pop']} people)"
    if len(land(world)["projects"]) >= max_projects(world):
        return "too many things going up already - people can only build so much at once"
    return None


def start(world, kind, gold=0, name=None, place=None):
    """Aldric decides to build something. The gold he puts in decides which tier it is. Returns (project, why)."""
    city, L = world.city, land(world)
    why = can_build(world, kind)
    if why:
        return None, why
    s = spec(kind)
    gold = int(max(0, min(gold, city.treasury)))
    tier = tier_for(kind, gold)
    if tier < 0:
        need = s["tiers"][0]["gold"]
        if city.treasury < need:
            return None, f"even the least {bare(s['name'])} takes {need} gold, and there's {city.treasury:.0f} in the chest"
        gold, tier = need, 0
    gold = s["tiers"][tier]["gold"]                 # (the price of the version it buys, not a coin more)
    city.treasury -= gold
    t = s["tiers"][tier]
    L["built_n"] = L.get("built_n", 0) + 1
    p = {"id": f"p{L['built_n']}", "kind": kind, "tier": tier, "gold": gold, "name": name or t["name"],
         "look": t["look"], "need": float(s["build"]), "done": 0.0, "started": city.day + 1, "started_t": world.clock,
         "upgrade_of": None, "helpers": []}
    L["projects"].append(p)
    from . import scene
    scene.civic_lot(world, p)
    assign(world)
    return p, None


def invest(world, b, gold):
    """Gold into a standing building: the next tier it buys goes up as an upgrade (builders again, half the work
    per tier). Returns (project, why)."""
    city, L = world.city, land(world)
    if any(p.get("upgrade_of") == b["id"] for p in L["projects"]):
        return None, f"{b['name']} is already being done up"
    s = spec(b["kind"])
    gold = int(max(0, min(gold, city.treasury)))
    tier = tier_for(b["kind"], b.get("gold", 0) + gold)
    if tier <= b["tier"]:
        nxt = s["tiers"][b["tier"] + 1] if b["tier"] + 1 < len(s["tiers"]) else None
        return None, (f"{b['name']} is already as fine as it gets" if not nxt else
                      f"{nxt['name']} takes {nxt['gold'] - b.get('gold', 0)} more gold")
    cost = s["tiers"][tier]["gold"] - b.get("gold", 0)
    city.treasury -= cost
    b["gold"] = b.get("gold", 0) + cost
    L["built_n"] = L.get("built_n", 0) + 1
    need = max(2.0, s["build"] * 0.5 * tier) if b["kind"] != "keep" else 6.0 * tier * tier
    t = s["tiers"][tier]
    p = {"id": f"p{L['built_n']}", "kind": b["kind"], "tier": tier, "gold": cost, "name": t["name"], "look": t["look"],
         "need": float(need), "done": 0.0, "started": city.day + 1, "started_t": world.clock, "upgrade_of": b["id"],
         "helpers": [], "lot": b.get("lot")}
    L["projects"].append(p)
    assign(world)
    return p, None


def finish(world, p):
    city, L = world.city, land(world)
    L["projects"] = [x for x in L["projects"] if x is not p]
    if p.get("upgrade_of"):
        b = building(world, p["upgrade_of"])
        if b:
            old = b["name"]
            b.update({"tier": p["tier"], "name": p["name"], "look": p["look"], "condition": 1.0, "disrepair": False,
                      "t": world.clock})
            if b["kind"] == "keep":
                places(world)["shack"]["name"] = roles_the(bare(p["name"]))
            world.moment("world", f"{old[0].upper() + old[1:]} is {p['name']} now: {p['look']}.", 3, public=True,
                         place=b.get("place"))
            world.notify(f"Upgraded: {p['name']}")
    else:
        b = {"id": f"b{len(L['buildings'])}", "kind": p["kind"], "tier": p["tier"], "gold": p["gold"], "name": p["name"],
             "look": p["look"], "state": "standing", "day": city.day + 1, "t": world.clock, "condition": 1.0,
             "started_t": p.get("started_t"), "lot": p.get("lot"), "days_run": 0}
        L["buildings"].append(b)
        b["place"] = _new_place(world, b)
        s = spec(p["kind"])
        first = sum(1 for x in L["buildings"] if x["kind"] == p["kind"]) == 1
        world.moment("world", f"{p['name'][0].upper() + p['name'][1:]} is finished: {p['look']}."
                     + (f" It needs {s['crew']} people a day to run." if s["crew"] else ""),
                     3 if first else 2, public=True, place=b["place"])
        world.notify(f"Built: {p['name']}")
        if p["kind"] == "palisade":
            from . import town as T
            T.build_walls(world, "success")
    for h in p.get("helpers", [])[:40]:
        world.reply(h, f"🔨 {p['name'][0].upper() + p['name'][1:]} is finished - and you helped build it.", "helped_build",
                    credit=f"helped build {p['name']}")
    assign(world)


def _new_place(world, b):
    t = world.city.living["town"]
    pid = b["kind"] if b["kind"] not in t["places"] else f"{b['kind']}_{b['id']}"
    t["places"][pid] = {"name": roles_the(bare(b["name"])) if not b["name"].lower().startswith("the ") else b["name"],
                        "walk": 5, "offers": b.get("look", ""), "built": b["id"]}
    t["features"][pid] = {"building": b["name"]}
    if b["kind"] in ("tavern", "market") and land(world)["court_place"] == "shack":
        pass
    return pid


def gift_building(world_or_city, kind):
    """An event leaves something behind (a sky-whale's bones become a hall...): a finished building, first tier."""
    city = getattr(world_or_city, "city", world_or_city)
    L = land(city)
    s = spec(kind)
    t = s["tiers"][0]
    L["built_n"] = L.get("built_n", 0) + 1
    p = {"id": f"p{L['built_n']}", "kind": kind, "tier": 0, "gold": 0, "name": t["name"], "look": t["look"],
         "need": 1.0, "done": 1.0, "started": city.day + 1, "upgrade_of": None, "helpers": []}
    L["projects"].append(p)                    # (finished on the next count, so it gets a lot and a moment)
    from . import scene
    scene.civic_lot(city, p)
    return p


def rally(world, b_or_p):
    """Aldric asks everyone to put their backs into one thing today: it gets its people first."""
    land(world)["rally"] = {"id": b_or_p["id"], "day": world.city.day + 1}
    assign(world)


# ---------------------------------------------------------------- stages, the court, the crown
def _stage(world, before=None):
    city, L = world.city, land(world)
    now = stage_of(settled(city))
    before = before or L.get("stage", "alone")
    L["stage"] = now
    order = [s for s, _ in STAGES][::-1]
    if order.index(now) > order.index(before):
        text = {"hamlet": "Emberfall isn't just one man in a shack any more. It's a hamlet.",
                "village": "Emberfall has become a village.", "town": "Emberfall is a town now.",
                "city": "Emberfall is a city."}[now]
        world.moment("world", text, 3, public=True)
        world.notify(text)
        grow_island(world.city, order.index(now) - order.index(before))
        for s in order[order.index(before) + 1:order.index(now) + 1]:
            npc = COURT_ARRIVES.get(s)
            if npc and npc not in L["court"]:
                L["court"].append(npc)
                who = life.court().get(npc, {}).get("name", npc)
                why = {"jester": "turned up with the travellers - juggling, uninvited, and staying",
                       "steward": "arrived claiming he once kept the books for a great house. He'd be happy to "
                                  "keep Aldric's"}.get(npc, "arrived")
                world.moment("world", f"{who} {why}.", 2, public=True)
    return now


def after_post(world):
    """Once a day after the post: the crown, the warlord, stage changes."""
    city, L = world.city, land(world)
    _stage(world)
    n = settled(city)
    for a in city.event_log[-5:]:
        if a["id"].startswith("crowning_") and not a.get("_seen"):
            a["_seen"] = True
            crowd = a.get("crowd")
            yes = crowd == "CROWN" if crowd else city.approval() > 0.55
            if yes:
                L["crowned"] = True
                L["crowned_day"] = city.day
                world.moment("world", "The people crowned Aldric king of Emberfall - a crown hammered out of a "
                                      "cooking pot, but a crown.", 3, public=True)
                world.notify("Aldric was crowned king")
            else:
                world.moment("world", "The people voted: not yet. Aldric isn't king - not this week.", 3, public=True)
                L["crown_retry"] = city.day + 7
    if (not L["crowned"] and n >= int(city.cfg.get("frontier_crown_at", 10))
            and city.day >= L.get("crown_retry", 0) and not any(a["id"].startswith("crowning_") for a in city.events)):
        from .. import storyteller
        eid = f"crowning_{city.day}"
        ev = {"id": eid, "title": "The people gather: should Aldric be crowned king of Emberfall?", "scope": "city",
              "planned_only": True, "days": 2, "invented_by": "frontier",
              "choices": {"CROWN": {"text": "The people chose to crown him."},
                          "NOTYET": {"text": "The people said: not yet."}}, "options": []}
        city.living.setdefault("custom_events", {})[eid] = ev
        storyteller.register(ev)
        storyteller.start(city, eid, source="frontier", extra={"started": city.day + 1})
        world.notify("Crowning vote starts")
    due = int(city.cfg.get("frontier_warlord_pop", 15))
    if not L.get("warlord_day") and n >= due and city.day >= 9:
        L["warlord_day"] = city.day + 3


# ---------------------------------------------------------------- gifts from followers
def gift(world, item, who):
    """A follower sent Aldric something (gold is handled where it's given). Nothing to stock: it's his."""
    return ""


# ---------------------------------------------------------------- for the post
def summary(world):
    city, L = world.city, land(world)
    return {"stage": L["stage"], "crowned": L["crowned"], "settled": settled(city), "on_road": 0,
            "beds": settled(city), "free": 0, "tents": 0, "gold": round(city.treasury),
            "happiness": L.get("happiness", 0.6),
            "built": [b["name"] for b in L["buildings"] if b["id"] != "b0" and b["state"] == "standing"],
            "running": [b["name"] for b in L["buildings"] if b.get("running")],
            "projects": [f"{p['name']} {p['done'] / p['need']:.0%}" for p in L["projects"]],
            "power": (L["history"][-1]["shifts"] if L["history"] else 0)}


def status_line(f):
    if not f:
        return ""
    who = "Aldric, alone" if not f["settled"] else f"{f['settled']} people"
    return (f"🏝️ {who} · {f['power']} shifts yesterday · {f['gold']} gold · happiness {f['happiness']:.0%}"
            + (f" · going up: {', '.join(f['projects'][:2])}" if f["projects"] else ""))


def day_summary(world):
    """Evening: the day's People Power, counted (settle) - the town's daily heartbeat in the feed."""
    return settle(world)


def stock_line(city):
    return f"The treasury: {city.treasury:.0f} gold."
