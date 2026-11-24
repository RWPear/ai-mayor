"""The frontier: the king starts with nothing.

A leaky one-room shack in a field, a dull axe, the clothes on his back. No subjects, no court, no gold to
speak of, and nobody has crowned him. Everything gets built by hand, starting with his own.

THE WORLD HAS RULES, THE KING HAS IDEAS
  - Materials are real: wood, stone, clay, thatch, rope, food, iron. He gathers them himself where they are
    (wood in the woods, clay at the river, stone on the hill), at rates set by his tools, his practice, his
    energy and the weather.
  - He invents what to build in his own words ("a cottage with a thatched roof", "a smokehouse", "a tall
    apartment building of stone and timber"). The first time he has an idea, the world prices it once: what it
    is (housing, food, storage, a workshop, a tool, defense, comfort, a place for people to gather), how big,
    what it's made of, what techniques it needs. The code turns that into materials, hours of work and how many
    people it holds - so nothing is free and nothing is a menu.
  - Bigger buildings are more efficient per person but need techniques he has to learn: thatching, timber
    framing, stone foundations, mortar, kiln firing, multi-storey building. He can try without them (it's
    risky); succeeding - or failing badly - teaches him. Settlers who know a craft can show him.
  - What he builds becomes real: a named building with his description, at a place, with tags. Big gathering
    places become places you can walk to. (The 3D view will use the tags and the description.)

PEOPLE COME THE DAY THEY FOLLOW
  A new follower walks into Emberfall at once: a bed if there's room, otherwise a tent in the camp by the road
  (cold nights, low mood, nobody dies). When a new house is finished, the people in tents move in - and hear
  about it.

THE KING GOES FROM HANDS TO HEAD
  Settled people work: a little every day on their own, a lot more on days they comment WORK (or describe their
  work). They work on HIS projects - he decides what gets built - and gather what those projects need, and
  feed everyone. Their roles matter (woodcutters fell more trees, masons lay stone). As the place grows he gets
  new verbs: ask people for help, organize crews, appoint a foreman.

STAGES: alone -> hamlet (1+ settlers) -> village (10+) -> town (50+) -> city (200+). At the village stage the
settlers vote on crowning him. Skarn the Red only shows up once the place is worth raiding.

State lives in city.living['town']['land'].
"""
import re

import numpy as np

from .. import effects, trades
from ..roles import JOB_NAMES
from . import life

ROAD = 2                     # citizens.status: on the road to Emberfall
MATERIALS = ["wood", "stone", "clay", "thatch", "rope", "food", "iron"]
UNIT = {"wood": "wood", "stone": "stone", "clay": "clay", "thatch": "bundles of thatch", "rope": "rope",
        "food": "food", "iron": "iron"}

# the land at the start. walk = minutes from the shack
PLACES = {
    "shack": {"name": "the shack", "walk": 2, "resources": [],
              "offers": "a straw mat to sleep on and a cold fire pit"},
    "field": {"name": "the field", "walk": 4, "resources": ["thatch", "food"],
              "offers": "tall grass for thatch, wild onions, room to build"},
    "woods": {"name": "the woods", "walk": 12, "resources": ["wood", "rope", "food"],
              "offers": "birch and old oaks, deadfall everywhere, vines and bark for rope, mushrooms"},
    "river": {"name": "the river", "walk": 15, "resources": ["clay", "thatch", "food"],
              "offers": "clay banks, reeds, slow brown water with fish in it"},
    "hill":  {"name": "the rocky hill", "walk": 20, "resources": ["stone"],
              "offers": "a hill strewn with loose grey stone"},
    "road":  {"name": "the old road", "walk": 8, "resources": [],
              "offers": "a rutted track from the south - travellers come this way"},
}
FEATURES = {
    "shack": {"shack": "a one-room shack: the roof leaks, the door won't shut, a straw mat on the dirt floor"},
    "field": {"field": "knee-high grass and thistles, nothing built"},
    "woods": {"trees": "dense birch and oak, nobody has cut a tree here in years"},
    "river": {"bank": "muddy clay banks and reeds"},
    "hill":  {"stones": "loose stones the size of loaves and anvils"},
    "road":  {"track": "a rutted dirt track, a rotten signpost with no words left on it"},
}
RATES = {"wood": 5.0, "stone": 3.0, "clay": 5.0, "thatch": 8.0, "rope": 2.5, "food": 2.5, "iron": 0.0}  # per hour
SKILLED = {"wood": {"woodcutter", "lumberjack", "carpenter"}, "stone": {"mason", "miner"},
           "clay": {"potter", "miller"}, "thatch": {"farmer", "shepherd", "farmhand"},
           "rope": {"sailor", "fisher"}, "food": {"farmer", "fisher", "hunter", "shepherd", "baker", "cook"}}
HOME = {"woodcutter": "woods", "mason": "hill", "miner": "hill", "fisher": "river", "sailor": "river",
        "miller": "river", "farmer": "field", "shepherd": "field", "scout": "road", "guard": "road"}

TECHNIQUES = ["thatching", "timber framing", "stone foundations", "mortar", "kiln firing", "multi-storey building",
              "carpentry", "metalwork", "knots"]
TEACH = {"masonry": ["stone foundations", "mortar"], "smithing": ["metalwork"], "baking": ["kiln firing"],
         "brewing": ["kiln firing"], "sailing": ["knots"], "hunting": ["knots"], "letters": ["multi-storey building"],
         "tailoring": ["thatching"]}
TEACH_JOB = {"woodcutter": ["timber framing", "carpentry"], "farmer": ["thatching"], "shepherd": ["thatching"],
             "mason": ["stone foundations", "mortar"], "miner": ["stone foundations"], "carpenter": ["timber framing",
                                                                                            "carpentry"]}

KINDS = ["housing", "food", "storage", "workshop", "tool", "defense", "comfort", "gathering", "path", "other"]
SCALES = {   # bigger = more people per unit of work, but needs know-how
    # crew = how many people can usefully work on one at once (8 hours a day each), so even a crowd takes days.
    # A man alone should finish a cottage in about a day: the first week has to show something.
    "tiny":   {"units": 8,   "hours": 2,   "cap": 1,  "crew": 1,  "know": [],                        "ok": 0.95},
    "small":  {"units": 20,  "hours": 7,   "cap": 3,  "crew": 3,  "know": ["thatching"],             "ok": 0.88},
    "medium": {"units": 60,  "hours": 22,  "cap": 10, "crew": 4,  "know": ["thatching", "timber framing"], "ok": 0.78},
    "large":  {"units": 160, "hours": 60,  "cap": 30, "crew": 6,  "know": ["timber framing", "stone foundations"],
               "ok": 0.68},
    "huge":   {"units": 400, "hours": 160, "cap": 90, "crew": 10, "know": ["timber framing", "stone foundations", "mortar",
                                                                          "multi-storey building"], "ok": 0.58},
}
MIX = {"wood": {"wood": .65, "thatch": .25, "rope": .10}, "stone": {"stone": .6, "wood": .25, "clay": .15},
       "clay": {"clay": .55, "thatch": .25, "wood": .20},
       "mixed": {"wood": .40, "stone": .30, "clay": .15, "thatch": .10, "rope": .05},
       "iron": {"iron": .25, "wood": .55, "stone": .20}}
FOOD_OUT = {"tiny": 1, "small": 3, "medium": 8, "large": 20, "huge": 50}    # food a day from a food building
STAGES = [("city", 200), ("town", 50), ("village", 10), ("hamlet", 1), ("alone", 0)]
COURT_ARRIVES = {"hamlet": "jester", "village": "steward"}

PEDDLER = [  # name, gold, what it does
    ("an iron axe", 25, {"tool": "wood", "x": 2.0}), ("an iron pick", 30, {"tool": "stone", "x": 2.0}),
    ("a bow saw", 20, {"tool": "wood", "x": 1.3, "build": 1.1}), ("a bag of nails", 15, {"build": 1.2}),
    ("seed potatoes", 10, {"food_day": 2}), ("a coil of rope", 8, {"stock": ("rope", 15)}),
    ("a sack of grain", 12, {"stock": ("food", 20)}), ("iron bars", 20, {"stock": ("iron", 6)}),
    ("a clay pot", 6, {"comfort": 1}), ("a wool blanket", 9, {"comfort": 1}),
]
SELL = {"wood": 0.5, "stone": 0.6, "clay": 0.4, "thatch": 0.2, "rope": 1.0, "food": 1.0, "iron": 3.0}
GIFT_TOOLS = [(r"\baxe|hatchet", "wood", 1.6), (r"\bpick|pickaxe|mattock", "stone", 1.6), (r"\bsaw\b", "wood", 1.3),
              (r"\bshovel|spade", "clay", 1.5), (r"\bsickle|scythe", "thatch", 1.5),
              (r"\bfishing rod|net\b|fishing", "food", 1.4), (r"\bhammer|nails|mallet", None, 1.1)]
GIFT_STOCK = [(r"\bwood|logs?|planks?|timber|lumber", "wood"), (r"\bstones?|bricks?\b", "stone"),
              (r"\bclay\b", "clay"), (r"\bthatch|straw|reeds", "thatch"), (r"\brope|twine|cord", "rope"),
              (r"\biron|ingots?|nails\b", "iron"),
              (r"\bbread|food|meat|apples?|potatoes|grain|cheese|fish|pie|stew|eggs|vegetables|carrots?|berries",
               "food")]


# ---------------------------------------------------------------- state
def new_town():
    """A town state (city.living['town']) for the frontier start."""
    return {"features": {pid: dict(f) for pid, f in FEATURES.items()},
            "places": {pid: dict(p) for pid, p in PLACES.items()},
            "rooms": {}, "works": [], "done": [], "invented": {}, "walls": {"capacity": 0, "built": None},
            "land": {"stock": {m: 0 for m in MATERIALS} | {"food": 6}, "tools": [{"name": "a dull axe",
                                                                                 "tool": "wood", "x": 1.0}],
                     "buildings": [{"id": "b0", "name": "the shack", "kind": "comfort", "scale": "tiny",
                                    "capacity": 0, "place": "shack", "quality": "poor", "day": 0, "by": "nobody",
                                    "look": "a one-room shack with a leaking roof"}],
                     "projects": [], "designs": {}, "know": [], "practice": {}, "occupancy": {},
                     "stage": "alone", "crowned": False, "court": [], "court_place": "shack", "officers": {},
                     "crews": [], "help": None, "forecast": None, "next_arrival": 7, "peddler": None,
                     "hungry_days": 0, "workers_today": [], "camp": False, "builds": 0}}


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


def capacity(city):
    return int(sum(b.get("capacity", 0) for b in land(city)["buildings"] if b.get("kind") == "housing"))


def housed(city):
    c = city.citizens
    return int((c.active() & (c.walled >= 0)).sum())


def tents(city):
    c = city.citizens
    return int((c.active() & (c.walled == -2)).sum())


def free_beds(city):
    return max(0, capacity(city) - housed(city))


def title(city, text):
    """Before he's crowned, nobody calls him king."""
    if not is_frontier(city) or land(city).get("crowned"):
        return text
    name = "Aldric"
    for a, b in (("King Aldric", name), ("The king's", f"{name}'s"), ("the king's", f"{name}'s"),
                 ("The king", name), ("the king", name)):
        text = text.replace(a, b)
    return text


def stock_line(city):
    L = land(city)
    s = L["stock"]
    have = [f"{int(s[m])} {UNIT[m]}" for m in MATERIALS if s.get(m, 0) >= 1]
    eaters = settled(city) + 1
    days = s.get("food", 0) / eaters
    return ("Your stores: " + (", ".join(have) if have else "nothing at all")
            + f". Food lasts {days:.1f} day{'s' if abs(days - 1) > 0.05 else ''} for {eaters} mouth"
            + ("s" if eaters > 1 else "") + ".")


def tool_x(city, material):
    return max([t.get("x", 1.0) for t in land(city)["tools"] if t.get("tool") == material] or [1.0])


def build_x(city):
    x = 1.0
    for t in land(city)["tools"]:
        x *= t.get("build", 1.0)
    return x


# ---------------------------------------------------------------- pricing an idea (decided once)
DESIGN = {"type": "object", "properties": {
    "possible": {"type": "boolean"}, "why_not": {"type": "string"},
    "name": {"type": "string"}, "kind": {"type": "string", "enum": KINDS},
    "scale": {"type": "string", "enum": list(SCALES)},
    "material": {"type": "string", "enum": list(MIX)},
    "capacity": {"type": "integer"}, "techniques": {"type": "array", "items": {"type": "string", "enum": TECHNIQUES}},
    "boosts": {"type": "string", "enum": MATERIALS + [""]}, "look": {"type": "string"}},
    "required": ["possible", "why_not", "name", "kind", "scale", "material", "capacity", "techniques", "boosts",
                 "look"]}
DESIGN_SYSTEM = """A man with nothing is building a medieval settlement by hand (no magic, no modern machines). He has
an idea for something to build. Say honestly what it would be:
possible: false only if it can't exist in this world (a flying castle, electricity). why_not: if so, a few words.
name: a short name for it (2-5 words). kind: housing (people live in it), food (makes food: garden, fish trap,
  farm plot, smokehouse), storage (keeps food/materials), workshop (sawpit, kiln, forge, workbench), tool (a thing
  he holds: a stone axe, a sledge), defense (fence, palisade, wall, watchtower), comfort (for himself: a bed, a
  chair, a better roof), gathering (a place for people: a fire circle, meeting hall, tavern, chapel, market),
  path (a road, a bridge, a well), other.
scale: tiny (an afternoon: a bed, a stone axe, a drying rack), small (a few days by hand: a hut, a cottage, a
  garden), medium (a longhouse, a barn, a smokehouse), large (a row of houses, a hall, a palisade), huge (an
  apartment building, a stone keep). material: what it's mostly made of. capacity: people who could live in it
  (housing only, else 0). techniques: the know-how it really needs. boosts: for a tool or workshop, the material
  it helps gather, else "". look: one sentence describing what it looks like."""

RULE_DESIGNS = [  # (pattern, kind, scale, material, boosts) - the model does better; these keep tests honest
    (r"apartment|tenement|insula|block of flats|tower block|multi.?stor", "housing", "huge", "mixed", ""),
    (r"row ?houses?|terrace|row of (\w+ )?(houses|cottages|homes)|tenements?", "housing", "large", "wood", ""),
    (r"fire ?pit|campfire|cook ?fire|hearth|fireplace|clay oven|bread oven", "comfort", "tiny", "stone", ""),
    (r"drying rack|rack|bench|stool|log seat|seat|wood ?pile|chopping block", "comfort", "tiny", "wood", ""),
    (r"longhouse|barracks|dormitor|bunkhouse|lodge", "housing", "medium", "wood", ""),
    (r"\b(cottage|hut|cabin|house|home|shelter|lean.?to|hovel|dwelling)s?\b", "housing", "small", "wood", ""),
    (r"garden|farm|field|plot|orchard|fish ?trap|weir|smokehouse|henhouse|chicken|pig ?pen|beehive", "food", "small",
     "wood", ""),
    (r"granary|storehouse|store ?room|cellar|shed|barn|larder", "storage", "medium", "wood", ""),
    (r"sawpit|saw ?pit|kiln|forge|workbench|workshop|smithy|tannery|loom", "workshop", "small", "mixed", "wood"),
    (r"axe|pick|sledge|hammer|shovel|spade|saw|sickle|knife|spear|tool", "tool", "tiny", "mixed", "wood"),
    (r"wall|palisade|fence|rampart|watchtower|tower|gate|ditch|moat|stockade", "defense", "large", "wood", ""),
    (r"bed|chair|table|roof|door|window|hearth|fireplace|chimney|rug|shelf", "comfort", "tiny", "wood", ""),
    (r"hall|tavern|inn|chapel|church|temple|market|square|fire ?circle|meeting|bathhouse|theater|school", "gathering",
     "medium", "wood", ""),
    (r"road|path|bridge|well|dock|jetty|pier|canal|steps", "path", "small", "stone", ""),
]
IMPOSSIBLE = r"flying|magic|teleport|electric|robot|rocket|laser|plastic|steel skyscraper|castle in the sky|engine"


def _norm(idea):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", str(idea or "").lower())).strip()[:80]


def design(world, idea):
    """What his idea really is. Decided once per idea, then remembered (so retrying doesn't change the price)."""
    L = land(world)
    key = _norm(idea)
    if not key:
        return None
    if key in L["designs"]:
        return L["designs"][key]
    d = None
    if re.search(IMPOSSIBLE, key):
        d = {"possible": False, "why_not": "nothing like that exists in this world", "name": _short(idea)}
    elif world.voice_llm and world.can_think():
        world.spend_calls(1)
        try:
            d = world.voice_llm.json(DESIGN_SYSTEM, f"His idea: {idea}", DESIGN, max_tokens=400, temperature=0.3)
        except Exception:
            d = None
    if not d:
        d = _rule_design(idea)
    d = _priced(d, idea)
    L["designs"][key] = d
    if len(L["designs"]) > 80:
        for k in list(L["designs"])[:20]:
            del L["designs"][k]
    return d


def _short(name, n=60):
    name = re.sub(r"\s+", " ", str(name)).strip()
    return name if len(name) <= n else name[:n].rsplit(" ", 1)[0]


def _rule_design(idea):
    t = idea.lower()
    for pat, kind, scale, material, boosts in RULE_DESIGNS:
        if re.search(pat, t):
            if re.search(r"\bstone\b", t):
                material = "stone"
            elif re.search(r"\bclay|brick|mud\b", t):
                material = "clay"
            if kind == "tool" and re.search(r"pick|sledge", t):
                boosts = "stone"
            if kind == "tool" and re.search(r"shovel|spade", t):
                boosts = "clay"
            return {"possible": True, "name": _short(idea), "kind": kind, "scale": scale, "material": material,
                    "capacity": SCALES[scale]["cap"] if kind == "housing" else 0, "techniques": [], "boosts": boosts,
                    "look": ""}
    return {"possible": True, "name": _short(idea), "kind": "other", "scale": "small", "material": "wood", "capacity": 0,
            "techniques": [], "boosts": "", "look": ""}


def _priced(d, idea):
    """The model says what it is; the code says what it costs. Bounded, so nothing is free."""
    if not d.get("possible", True):
        return {"possible": False, "why_not": str(d.get("why_not") or "it can't be built here")[:80],
                "name": str(d.get("name") or idea)[:40]}
    kind = d.get("kind") if d.get("kind") in KINDS else "other"
    scale = d.get("scale") if d.get("scale") in SCALES else "small"
    if kind == "tool":
        scale = "tiny"
    mat = d.get("material") if d.get("material") in MIX else "wood"
    S = SCALES[scale]
    units = S["units"] * (0.6 if kind in ("tool", "comfort") else 1.0)
    needs = {m: max(1, round(units * share)) for m, share in MIX[mat].items()}
    know = set(S["know"]) if kind in ("housing", "storage", "gathering", "food") else set(S["know"][1:])
    if mat == "stone" and scale in ("medium", "large", "huge"):
        know |= {"mortar", "stone foundations"}
    if mat == "clay" and scale in ("medium", "large", "huge"):
        know.add("kiln firing")
    if mat == "iron":
        know.add("metalwork")
    know |= {k for k in (d.get("techniques") or []) if k in TECHNIQUES}
    if scale == "tiny":
        know &= {"metalwork", "knots", "carpentry"}
    cap = 0
    if kind == "housing":
        lo, hi = {"tiny": (1, 1), "small": (2, 4), "medium": (6, 12), "large": (20, 40), "huge": (60, 120)}[scale]
        cap = int(np.clip(int(d.get("capacity") or S["cap"]), lo, hi))
    boosts = d.get("boosts") if d.get("boosts") in MATERIALS and kind in ("tool", "workshop", "gathering") else ""
    if kind in ("tool", "workshop") and not boosts:
        boosts = "wood"
    return {"possible": True, "name": _short(d.get("name") or idea), "kind": kind, "scale": scale,
            "material": mat, "needs": needs, "hours": S["hours"] * (0.6 if kind in ("tool", "comfort") else 1.0),
            "capacity": cap, "know": sorted(know), "boosts": boosts, "look": str(d.get("look") or "")[:160]}


# ---------------------------------------------------------------- projects
ORDER = ["tiny", "small", "medium", "large", "huge"]
HANDS = [(0, "small"), (1, "medium"), (10, "large"), (50, "huge")]      # settlers -> the biggest they could raise
EXAMPLE = {"tiny": "a bed, a stone axe", "small": "a cottage, a garden, a shed", "medium": "a longhouse, a barn",
           "large": "a row of houses, a hall, a palisade", "huge": "a tenement block, a stone keep"}


def example(scale, rng=None):
    """A few things of that size, drawn fresh (fixed examples turn into the model's only ideas)."""
    from . import flavor
    return flavor.some(flavor.BY_SCALE[scale], 3, rng) if rng else EXAMPLE[scale]


def max_scale(world):
    """The biggest thing that's realistic right now: limited by how many hands there are, and by experience -
    one size up from the biggest thing he's actually finished. One man alone raises cottages, not tenements."""
    L = land(world)
    n = settled(world.city)
    hands = max(ORDER.index(s) for need, s in HANDS if n >= need)
    done = max([ORDER.index(b.get("scale", "tiny")) for b in L["buildings"] if b["id"] != "b0"] or [0])
    return ORDER[min(hands, done + 1)]


def too_big(world, d):
    """None if he could take it on, else why not (in the world's words)."""
    cap = max_scale(world)
    if ORDER.index(d["scale"]) <= ORDER.index(cap):
        return None
    n = settled(world.city)
    who = "one man alone" if not n else f"{n} settler{'s' if n > 1 else ''} and him"
    built = max([ORDER.index(b.get("scale", "tiny")) for b in land(world)["buildings"] if b["id"] != "b0"] or [0])
    if ORDER.index(d["scale"]) > built + 1:
        return (f"nothing he's built comes close to that size - he'd need to raise something "
                f"{ORDER[built + 1]} first ({example(ORDER[built + 1], world.city.rng)})")
    return f"that's far too much for {who} - for now, think {cap}: {example(cap, world.city.rng)}"


def start_project(world, idea, place=None):
    """Returns (project, None) or (None, why)."""
    L = land(world)
    d = design(world, idea)
    if not d:
        return None, "no idea"
    if not d["possible"]:
        return None, d["why_not"]
    why = too_big(world, d)
    if why:
        return None, why
    if len([p for p in L["projects"] if not p.get("done")]) >= 3:
        return None, "too many things on the go already"
    pid = match(world, place) or world.agent("king").get("location", "field")
    if pid in ("road",) and d["kind"] == "housing":
        pid = "field"
    p = {"id": f"p{len(L['buildings']) + len(L['projects']) + 1}", "name": d["name"], "idea": idea[:90],
         "design": _norm(idea), "place": pid, "progress": 0.0, "hours": d["hours"],
         "needs": dict(d["needs"]), "used": {m: 0 for m in d["needs"]}, "kind": d["kind"], "scale": d["scale"],
         "capacity": d["capacity"], "know": d["know"], "boosts": d["boosts"], "look": d["look"],
         "missing": [k for k in d["know"] if k not in L["know"]], "started": world.city.day + 1, "helpers": [],
         "material": d.get("material"), "started_t": world.clock,
         "king_hours": 0.0}
    L["projects"].append(p)
    from . import scene
    scene.place(world, p)                   # its lot: the scaffolding stands where the building will
    return p, None


def remaining(p):
    """Materials still to bring for the rest of the job."""
    left = 1 - p["progress"]
    return {m: max(0, round(n * left - 1e-9 + 0.4999)) for m, n in p["needs"].items()}


def short_of(world, p):
    s = land(world)["stock"]
    return {m: n - int(s.get(m, 0)) for m, n in remaining(p).items() if n > s.get(m, 0)}


def work(world, p, hours, who="king"):
    """Hours of work on a project, using up materials as it goes. Returns (fraction done now, blocked by)."""
    L = land(world)
    s = L["stock"]
    if p.get("done") or hours <= 0:
        return 0.0, []
    day = world.city.day + 1                       # only so many hands fit on one building in a day
    if p.get("hours_day") != day:
        p["hours_day"], p["hours_today"] = day, 0.0
    room = SCALES[p["scale"]]["crew"] * 8 + (4 if who == "king" else 0) - p["hours_today"]
    hours = min(hours, max(0.0, room))
    if hours <= 0:
        return 0.0, []
    p["hours_today"] += hours
    df = min(hours / p["hours"], 1 - p["progress"])
    blocked = []
    for m, n in p["needs"].items():
        if n and s.get(m, 0) < n * df:
            df = min(df, s.get(m, 0) / n)
            blocked.append(m)
    if df <= 0:
        return 0.0, blocked
    for m, n in p["needs"].items():
        take = n * df
        s[m] = max(0.0, s.get(m, 0) - take)
        p["used"][m] = p["used"].get(m, 0) + take
    p["progress"] = min(1.0, p["progress"] + df)
    if who == "king":
        p["king_hours"] = p.get("king_hours", 0) + hours
    if p["progress"] >= 0.999:
        finish(world, p)
    return df, blocked


def finish(world, p):
    city, L = world.city, land(world)
    rng = city.rng
    p["done"] = True
    L["projects"] = [x for x in L["projects"] if x is not p]
    S = SCALES[p["scale"]]
    chance = (S["ok"] - (0.1 if p["scale"] in ("tiny", "small") else 0.2) * len(p["missing"])
              + 0.03 * min(5, L.get("builds", 0))
              + 0.04 * min(3, len(p.get("helpers", [])) // 5) + (0.05 if L["officers"].get("builder") else 0))
    roll = rng.random()
    result = "success" if roll < chance else ("shoddy" if roll < chance + 0.6 * (1 - chance) else "failed")
    if result == "failed" and p["kind"] == "housing" and not any(b["kind"] == "housing" for b in L["buildings"]):
        result = "shoddy"                        # his first roof over a bed leans, but it stands
    feats = city.living["town"]["features"].setdefault(p["place"], {})
    king = world.agent("king")
    lf = king.setdefault("life", life.new_life())
    learned = [k for k in p["missing"] if result != "failed" or rng.random() < 0.5]
    for k in learned:
        if k not in L["know"]:
            L["know"].append(k)
    lf["outcomes"] = (lf.get("outcomes", []) + [{"name": p["name"], "result": result, "day": city.day + 1}])[-20:]
    place_name = place_of(world, p["place"])
    if result == "failed":
        feats[f"ruin_{p['id']}"] = f"the collapsed remains of {p['name']}"
        if p.get("lot"):
            L.setdefault("ruins", []).append({"id": f"r_{p['id']}", "name": f"the collapsed {bare(p['name'])}",
                                              "shape": "ruin", "of": p["lot"]["shape"], "pos": p["lot"]["pos"],
                                              "size": p["lot"]["size"], "rot": p["lot"]["rot"],
                                              "kind": p["kind"], "day": city.day + 1, "t": world.clock})
        world.moment("king", f"{p['name']} collapsed before it was finished. Days of work, gone."
                     + (f" At least he learned something about {', '.join(learned)}." if learned else ""),
                     2, public=True, place=p["place"])
        world.notify(f"The king's {p['name']} failed")
        return result
    L["builds"] = L.get("builds", 0) + 1
    cap = p["capacity"] if result == "success" else int(p["capacity"] * 0.7)
    b = {"id": f"b{len(L['buildings'])}", "name": p["name"], "kind": p["kind"], "scale": p["scale"], "capacity": cap,
         "place": p["place"], "quality": "good" if result == "success" else "shoddy", "day": city.day + 1,
         "by": "the king", "look": p.get("look", ""), "boosts": p.get("boosts", ""), "material": p.get("material"),
         "lot": p.get("lot"), "t": world.clock, "started_t": p.get("started_t")}
    L["buildings"].append(b)
    feats[f"b_{b['id']}"] = p["name"] + ("" if result == "success" else " (shoddy - it leans)")
    q = 1.0 if result == "success" else 0.6
    if p["kind"] == "tool":
        L["tools"].append({"name": p["name"], "tool": p["boosts"] or "wood", "x": round(1 + 0.4 * q, 2)})
    if p["kind"] == "workshop":
        L["tools"].append({"name": p["name"], "tool": p["boosts"] or "wood", "x": round(1 + 0.3 * q, 2),
                           "build": 1.05})
    if p["kind"] == "defense":
        effects.apply(city, {"service.defense": 0.05 * q * (2 if p["scale"] in ("large", "huge") else 1)})
        if re.search(r"wall|palisade|rampart|stockade|fence", p["name"].lower()):
            from . import town as T
            T.build_walls(world, result)
    if p["kind"] == "gathering":
        effects.apply(city, {"service.festivals": 0.05 * q, "mood": 0.02 * q})
        if p["scale"] in ("medium", "large", "huge"):
            _new_place(world, b)
    if p["kind"] == "path":
        effects.apply(city, {"service.roads": 0.05 * q})
    if p["kind"] == "food":
        effects.apply(city, {"service.food": 0.04 * q})
    drama = 3 if p["kind"] == "housing" and not any(x["kind"] == "housing" for x in L["buildings"][:-1]) else (
        3 if p["scale"] in ("large", "huge") else 2)
    learned_txt = f" He learned {', '.join(learned)} doing it." if learned else ""
    what = (f" Room for {cap}." if p["kind"] == "housing" else "")
    world.moment("king", f"Aldric finished {p['name']} at {place_name}"
                 + (" - and it's good work." if result == "success" else " - it leans a little, but it stands.")
                 + what + learned_txt, drama, public=True, place=p["place"])
    world.notify(f"Finished: {p['name']} ({result})")
    for h in p.get("helpers", [])[:30]:
        world.reply(h, f"🔨 {p['name'][0].upper() + p['name'][1:]} is finished - and you helped build it.", "helped_build",
                    credit=f"helped build {p['name']}")
    if p["kind"] == "housing":
        rehouse(world)
    return result


def _new_place(world, b):
    t = world.city.living["town"]
    pid = re.sub(r"[^a-z]+", "_", b["name"].lower()).strip("_")[:24] or b["id"]
    if pid in t["places"]:
        pid = f"{pid}_{b['id']}"
    t["places"][pid] = {"name": roles_the(b["name"]), "walk": 5, "resources": [], "offers": b.get("look") or
                        "a place for people to gather", "built": b["id"]}
    t["features"][pid] = {"room": b["name"]}
    L = land(world)
    if re.search(r"hall|meeting|court|longhouse|fire circle", b["name"].lower()) and L["court_place"] == "shack":
        L["court_place"] = pid
    return pid


def bare(name):
    """'a small cottage' -> 'small cottage' (for 'the half-built ...')."""
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
    for word, pid in (("home", "shack"), ("house", "shack"), ("forest", "woods"), ("tree", "woods"),
                      ("stream", "river"), ("water", "river"), ("rock", "hill"), ("quarry", "hill"),
                      ("meadow", "field"), ("camp", "camp" if "camp" in pl else "road"), ("tent", "road")):
        if word in t and pid in pl:
            return pid
    return None


def where_to_get(world, material):
    return [pid for pid, p in places(world).items() if material in p.get("resources", [])]


def home_of(c, i):
    lab = c.label(i)
    rec = c.role(i) or {}
    for k, pid in HOME.items():
        if k in lab:
            return pid
    return {"river": "river", "fields": "field", "city_walls": "road"}.get(rec.get("place"), "field")


# ---------------------------------------------------------------- arriving
def join_road(world, idx):
    """New followers come to Emberfall straight away: they take a free bed or pitch a tent."""
    c = world.city.citizens
    idx = np.asarray(idx, np.int64)
    if not len(idx):
        return 0
    idx = idx[c.status[idx] == 0]
    if len(idx):
        arrive(world, idx)
    return len(idx)


ARRIVE_LINES = ["walked up the old road with everything they own on their back",
                "came over the hill at {time}, muddy to the knees", "turned up on the old road with a bundle and a grin",
                "followed the smoke of Aldric's fire to the field", "arrived footsore and hungry",
                "came up the road behind a goat that wasn't theirs", "walked in from the south road, looking around a lot"]


def arrive(world, idx=None):
    """People reach Emberfall (the ones given; or anyone an old save left on the road). They take any free beds;
    the rest pitch tents by the old road. They don't get a reply of their own: the fact that they just arrived goes
    into the reply to whatever they said (see intents.process)."""
    city, c, L = world.city, world.city.citizens, land(world)
    if idx is None:
        idx = np.where(c.status == ROAD)[0]
    idx = np.asarray(idx, np.int64)
    if not len(idx):
        return 0
    before = stage_of(settled(city))
    c.status[idx] = 0
    c.joined[idx] = city.day + 1
    c.walled[idx] = -2
    homes = rehouse(world, quiet=True, homes={})
    got = idx[c.walled[idx] >= 0]
    camped = idx[c.walled[idx] == -2]
    if len(camped) and not L.get("camp"):
        L["camp"] = True
        t = city.living["town"]
        t["places"]["camp"] = {"name": "the camp", "walk": 6, "resources": [],
                               "offers": "rows of tents and cook fires by the old road"}
        t["features"]["camp"] = {"tents": "patched tents in muddy rows"}
    new = city.living.setdefault("just_arrived", {})
    for i in idx:
        u = c.handles[int(i)]
        how = city.rng.choice(ARRIVE_LINES).format(time=world.now_str().split(", ")[-1])
        where = (f"and got a bed in {homes.get(int(i), 'a house')}" if c.walled[i] >= 0 else
                 "and pitched a tent by the old road (there are no free beds yet)")
        new[u] = {"day": city.day + 1, "text": f"{how}, {where}"}
        c.log(int(i), city.day + 1, "arrived in Emberfall" + ("" if c.walled[i] >= 0 else " (and pitched a tent)"))
    for u in list(new):                             # (forget arrivals from more than a day ago)
        if new[u]["day"] < city.day:
            del new[u]
    names = [c.handles[int(i)] for i in idx[:4]]
    who = ", ".join("@" + h for h in names) + (f" and {len(idx) - 4} more" if len(idx) > 4 else "")
    if len(idx) > 1:
        text = (f"{len(idx)} {'newcomer' if len(idx) == 1 else 'newcomers'} walked up the old road: {who}. "
                + (f"{len(got)} got a roof over their heads" if len(got) else "There wasn't a single bed for them")
                + (f"; {len(camped)} pitched tents by the road." if len(camped) and len(got) else
                   (" - they pitched tents by the road." if len(camped) else ".")))
    else:
        text = f"@{names[0]} {new[names[0]]['text']}."
    world.moment("world", text, 3 if len(idx) >= 5 else 1, public=True, place="road", handles=names)
    if len(idx) >= 5:
        world.notify(text)
    _stage(world, before)
    return len(idx)


def c_home(world, i):
    """Which house they get (and the 3D view draws them going home to it)."""
    L = land(world)
    occ = L["occupancy"]
    for b in L["buildings"]:
        if b.get("kind") == "housing" and occ.get(b["id"], 0) < b.get("capacity", 0):
            occ[b["id"]] = occ.get(b["id"], 0) + 1
            L.setdefault("homes", {})[world.city.citizens.handles[int(i)]] = b["id"]
            return roles_the(b["name"])
    return "a house"


def rehouse(world, quiet=False, homes=None):
    """People in tents move into free beds - the ones who've waited longest first.
    Returns how many moved (or, given a homes dict, fills it {citizen: house} and returns it)."""
    city, c = world.city, world.city.citizens
    free = free_beds(city)
    wait = np.where(c.active() & (c.walled == -2))[0] if free > 0 else np.zeros(0, np.int64)
    if not len(wait):
        return homes if homes is not None else 0
    wait = wait[np.argsort(c.joined[wait], kind="stable")][:free]
    inside = max(0, city.living["town"]["walls"]["capacity"] - int((c.walled == 1).sum()))
    for k, i in enumerate(wait):
        c.walled[i] = 1 if k < inside else 0
        home = c_home(world, int(i))
        if homes is not None:
            homes[int(i)] = home
        c.mood[i] = min(1.0, float(c.mood[i]) + 0.08)
        if not quiet:
            world.reply(c.handles[int(i)], f"🏠 You packed up your tent and moved into {home}. A real roof!", "moved_in")
    if not quiet and len(wait):
        world.moment("world", f"{len(wait)} {'family' if len(wait) == 1 else 'families'} moved out of the tents and "
                              f"into the new houses.", 2, public=True)
    return homes if homes is not None else len(wait)


# ---------------------------------------------------------------- the settlers' day
def _hours_today(world):
    city, c, L = world.city, world.city.citizens, land(world)
    from .intents import condition
    a = np.where(c.active())[0]
    if not len(a):
        return 0.0, 0
    workers = set(L.get("workers_today", []))
    base = float(city.cfg.get("frontier_passive_hours", 1.0))
    keen = float(city.cfg.get("frontier_work_hours", 4.0))
    able = [i for i in a if not condition(city, c.handles[i])]
    hours = sum(keen if c.handles[i] in workers else base for i in able)
    return hours, len(able)


def labor(world, share):
    """A share of the day's settler work: crews first, then food if it's short, then the king's projects (and
    what they're missing), then the stockpile."""
    city, c, L = world.city, world.city.citizens, land(world)
    total, n = _hours_today(world)
    if not n:
        return {}
    H = total * share
    if L.get("help") and L["help"].get("day") == city.day + 1:
        H *= 1.5
    s = L["stock"]
    done = {}
    org = 1.25 if L.get("crews") else 1.0
    a = np.where(c.active())[0]

    def skill(m):
        labs = [c.label(i) for i in a[:400]]
        k = sum(1 for lab in labs if any(x in lab for x in SKILLED.get(m, ())))
        return 1 + 0.6 * k / max(1, len(labs))

    def gather(m, hrs):
        got = RATES[m] * hrs * skill(m) * (1 + 0.3 * (tool_x(city, m) - 1)) * org
        if m == "food" and L["officers"].get("forager"):
            got *= 1.2
        s[m] = s.get(m, 0) + got
        done[m] = done.get(m, 0) + got
        day_log(world, "settlers", m, got)
        h = L.setdefault("harvested", {})
        h[m] = h.get(m, 0) + got

    for crew in [x for x in L.get("crews", []) if x["until"] >= city.day + 1]:
        hrs = min(H, crew["people"] * total / max(1, n) * share)
        H -= hrs
        if crew["task"].startswith("build:"):
            p = next((p for p in L["projects"] if p["id"] == crew["task"][6:]), None)
            if p:
                work(world, p, hrs * build_x(city) * org, who="crew")
        else:
            gather(crew["task"][7:], hrs)
    L["crews"] = [x for x in L.get("crews", []) if x["until"] >= city.day + 1]
    eaters = settled(city) + 1
    if s.get("food", 0) < 2 * eaters and H > 0:
        hrs = min(H, (2 * eaters - s.get("food", 0)) / RATES["food"])
        gather("food", hrs)
        H -= hrs
    workers = L.get("workers_today", [])
    for p in list(L["projects"]):
        if H <= 0:
            break
        want = min(H, H * 0.6 if len(L["projects"]) > 1 else H)
        df, blocked = work(world, p, want * build_x(city) * (1.2 if L["officers"].get("builder") else 1.0),
                           who="settlers")
        used = want if df > 0 else 0
        H -= used
        if df > 0:
            p["helpers"] = list(dict.fromkeys(p.get("helpers", []) + workers))[-60:]
        for m, short in short_of(world, p).items():
            if H <= 0 or m == "iron":
                continue
            hrs = min(H, short / max(0.1, RATES[m]))
            gather(m, hrs)
            H -= hrs
    if H > 0:                       # a sensible reserve of each, then nothing: idle hands tell the king something
        reserve = {"wood": 40, "thatch": 25, "stone": 20, "clay": 15, "rope": 10}
        for p in L["projects"]:
            for m, n in remaining(p).items():
                if m in reserve:
                    reserve[m] = max(reserve[m], n)
        for m, want_ in reserve.items():
            if H <= 0:
                break
            short = want_ - s.get(m, 0)
            if short > 0:
                hrs = min(H, short / RATES[m])
                gather(m, hrs)
                H -= hrs
    if H > 0:
        L["idle_hours"] = L.get("idle_hours", 0) + H
    return done


def day_log(world, who, key, n):
    d = land(world).setdefault("today", {})
    d.setdefault(who, {})
    d[who][key] = d[who].get(key, 0) + n


def day_summary(world):
    """Late evening: what the day added up to - so a quiet day alone still has a story in the post."""
    L = land(world)
    d = L.pop("today", {})
    k, s = d.get("king", {}), d.get("settlers", {})
    bits = []
    got = [f"{int(v)} {UNIT[m]}" for m, v in k.items() if m in UNIT and v >= 1]
    if got:
        bits.append("gathered " + ", ".join(got))
    if k.get("build_hours"):
        bits.append(f"put {k['build_hours']:.0f} hours into building")
    if not bits:
        return None
    them = sum(v for m, v in s.items() if m in UNIT)
    proj = "; ".join(f"{p['name']} is {p['progress']:.0%} done" for p in L["projects"][:2])
    text = (f"Aldric's day: he {' and '.join(bits)}." + (f" The settlers brought in {int(them)} more." if them >= 1 else "")
            + (f" {proj[0].upper() + proj[1:]}." if proj else ""))
    alone = L["stage"] in ("alone", "hamlet")
    return world.moment("king", text, 1 if alone else 0, public=alone, place="shack")


def meals(world):
    """Evening: everyone eats. Short of food, moods drop - and after three hungry days, people leave."""
    city, c, L = world.city, world.city.citizens, land(world)
    n = settled(city)
    if not n:
        return
    s = L["stock"]
    if s.get("food", 0) >= n:
        s["food"] -= n
        L["hungry_days"] = 0
        return
    short = n - s.get("food", 0)
    s["food"] = 0
    a = c.active()
    c.mood[a] = np.clip(c.mood[a] - 0.05 * short / n, 0, 1)
    L["hungry_days"] = L.get("hungry_days", 0) + 1
    world.moment("world", f"Not enough food to go round tonight: {int(short)} went to bed hungry.", 2, public=True)
    if L["hungry_days"] >= 3:
        idx = np.where(a)[0]
        k = max(1, len(idx) // 10)
        go = idx[np.argsort(c.mood[idx])][:k]
        c.status[go] = 1
        world.moment("world", f"After three hungry nights, {k} settler{'s' if k > 1 else ''} packed up and walked "
                              f"back down the old road.", 3, public=True,
                     handles=[c.handles[int(i)] for i in go[:3]])
        for i in go:
            world.reply(c.handles[int(i)], "You couldn't take another hungry night. You packed up and left Emberfall. "
                                           "(Comment JOIN to come back.)", "left")
        L["hungry_days"] = 0


def morning(world):
    """Food buildings produce, food spoils without storage, tent nights wear people down."""
    city, c, L = world.city, world.city.citizens, land(world)
    s = L["stock"]
    for b in L["buildings"]:
        if b.get("kind") == "food":
            s["food"] = s.get("food", 0) + FOOD_OUT.get(b["scale"], 2) * (1.0 if b["quality"] == "good" else 0.6)
    for t in L["tools"]:
        if t.get("food_day"):
            s["food"] += t["food_day"]
    room = 20 + sum(SCALES[b["scale"]]["units"] for b in L["buildings"] if b.get("kind") == "storage")
    if s.get("food", 0) > room:
        s["food"] = room + (s["food"] - room) * 0.85
    a = c.active()
    camp = a & (c.walled == -2)
    c.mood[camp] = np.maximum(0.2, c.mood[camp] - 0.015)


# ---------------------------------------------------------------- rough nights
def rough_night(world):
    """Now and then the frontier bites: wolves at the stores, a storm on a half-built frame, a cold snap."""
    city, L = world.city, land(world)
    rng = city.rng
    if rng.random() > 0.12:
        return None
    s = L["stock"]
    options = []
    if s.get("food", 0) >= 8 and not any(b["kind"] == "storage" for b in L["buildings"]):
        options.append("wolves")
    if L["projects"] and any(p["progress"] > 0.15 for p in L["projects"]):
        options.append("storm")
    if tents(city):
        options.append("cold")
    if s.get("wood", 0) >= 15:
        options.append("damp")
    if not options:
        return None
    pick = rng.choice(options)
    if pick == "wolves":
        n = round(s["food"] * rng.uniform(0.2, 0.4))
        s["food"] -= n
        text = f"Wolves got into the food stores in the night. {n} food gone - and paw prints all round the shack."
    elif pick == "storm":
        p = max(L["projects"], key=lambda x: x["progress"])
        p["progress"] = max(0.0, p["progress"] - 0.12)
        text = f"A storm in the night tore at the half-built {bare(p['name'])}. Some of it will have to be done again."
    elif pick == "cold":
        c = city.citizens
        camp = c.active() & (c.walled == -2)
        c.mood[camp] = np.maximum(0.15, c.mood[camp] - 0.05)
        text = f"A hard frost fell on the tents by the road. {tents(city)} people woke up shivering."
    else:
        n = round(s["wood"] * rng.uniform(0.1, 0.25))
        s["wood"] -= n
        text = f"Rain soaked the woodpile overnight; {n} wood is too rotten to use."
    world.moment("world", text, 2, public=True)
    return text


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
                world.moment("world", "The settlers crowned Aldric king of Emberfall - a crown hammered out of a "
                                      "cooking pot, but a crown.", 3, public=True)
                world.notify("Aldric was crowned king")
            else:
                world.moment("world", "The settlers voted: not yet. Aldric isn't king - not this week.", 3, public=True)
                L["crown_retry"] = city.day + 7
    if (not L["crowned"] and n >= int(city.cfg.get("frontier_crown_at", 10))
            and city.day >= L.get("crown_retry", 0) and not any(a["id"].startswith("crowning_") for a in city.events)):
        from .. import storyteller
        eid = f"crowning_{city.day}"
        ev = {"id": eid, "title": "The settlers gather: should Aldric be crowned king of Emberfall?", "scope": "city",
              "planned_only": True, "days": 2, "invented_by": "frontier",
              "choices": {"CROWN": {"text": "The people chose to crown him."},
                          "NOTYET": {"text": "The people said: not yet."}}, "options": []}
        city.living.setdefault("custom_events", {})[eid] = ev
        storyteller.register(ev)
        storyteller.start(city, eid, source="frontier", extra={"started": city.day + 1})
        world.notify("Crowning vote starts")
    due = int(city.cfg.get("frontier_warlord_pop", 15))
    if not L.get("warlord_day") and n >= due and city.day >= 9:
        L["warlord_day"] = city.day + 3          # rumours the day before, smoke after
    L["workers_today"] = []
    L["idle_yesterday"] = round(L.pop("idle_hours", 0))


# ---------------------------------------------------------------- the peddler
def peddler(world, force=False):
    city, L = world.city, land(world)
    if L.get("peddler") and L["peddler"]["until"] > world.clock:
        return None
    if not force and (city.day < 2 or city.rng.random() > 0.12):
        return None
    goods = city.rng.sample(PEDDLER, 4)
    L["peddler"] = {"until": world.clock + 7 * 60, "goods": [g[0] for g in goods]}
    world.moment("world", "A peddler with a creaking cart stopped on the old road: " + ", ".join(g[0] for g in goods)
                 + " for sale.", 1, public=True, place="road")
    return goods


def peddler_here(world):
    P = land(world).get("peddler")
    return bool(P and P["until"] > world.clock)


# ---------------------------------------------------------------- gifts from followers
def gift(world, item, who):
    """A follower sent something. Tools make him faster; materials go in the stores."""
    L, t = land(world), str(item).lower()
    for pat, mat, x in GIFT_TOOLS:  # noqa: B007
        if re.search(pat, t):
            if any(_norm(x_.get("name")) == _norm(item) for x_ in L["tools"]):
                return "(he already has one - it went on the shelf)"
            del L["tools"][1:-20]
            if mat:
                L["tools"].append({"name": item, "tool": mat, "x": x, "from": who})
                return f"(with it, gathering {mat} goes faster)"
            L["tools"].append({"name": item, "build": x, "from": who})
            return "(building goes a little faster now)"
    for pat, mat in GIFT_STOCK:
        if re.search(pat, t):
            n = int(world.city.rng.uniform(6, 16))
            L["stock"][mat] = L["stock"].get(mat, 0) + n
            return f"(+{n} {UNIT[mat]} in the stores)"
    return ""


def learn_from(world, i):
    """Talking with a settler who knows a craft: he picks up a technique."""
    c, L = world.city.citizens, land(world)
    job = JOB_NAMES[int(c.job[i])]
    knows = list(TEACH_JOB.get(job, []))
    rec = c.role(i)
    for sk in trades.skills_of(rec, job):
        knows += TEACH.get(sk, [])
    new = [k for k in dict.fromkeys(knows) if k not in L["know"]]
    if new and world.city.rng.random() < 0.6:
        L["know"].append(new[0])
        return new[0]
    return None


def learn_by_doing(world, text):
    L = land(world)
    t = text.lower()
    keys = {"thatching": r"thatch", "timber framing": r"fram|joint|beam|timber", "stone foundations": r"foundation",
            "mortar": r"mortar|lime", "kiln firing": r"kiln|brick|fire clay", "multi-storey building": r"stor(e)?y|floor",
            "carpentry": r"carpent|joinery|whittl", "knots": r"knot|lash|rope", "metalwork": r"smith|metal|forge"}
    for k, pat in keys.items():
        if k not in L["know"] and re.search(pat, t) and world.city.rng.random() < 0.35:
            L["know"].append(k)
            return k
    return None


# ---------------------------------------------------------------- for the post
def summary(world):
    city, L = world.city, land(world)
    return {"stage": L["stage"], "crowned": L["crowned"], "settled": settled(city), "on_road": on_road(city),
            "beds": capacity(city), "free": free_beds(city), "tents": tents(city),
            "stock": {m: int(v) for m, v in L["stock"].items() if v >= 1},
            "next_arrival": None,
            "built": [b["name"] for b in L["buildings"] if b["id"] != "b0"],
            "projects": [f"{p['name']} {p['progress']:.0%}" for p in L["projects"]],
            "know": list(L["know"])}


def status_line(f):
    """One line for the caption: how the frontier stands."""
    if not f:
        return ""
    stock = ", ".join(f"{v} {k}" for k, v in f["stock"].items())
    who = ("Aldric, alone" if not f["settled"] else f"{f['settled']} settler{'s' if f['settled'] > 1 else ''}")
    return (f"🏝️ {who} · {f['beds']} beds ({f['free']} free)" + (f" · {f['tents']} in tents" if f["tents"] else "")
            + (f" · stores: {stock}" if stock else ""))
