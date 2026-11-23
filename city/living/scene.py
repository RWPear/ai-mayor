"""What the 3D view needs: the frontier as a place with coordinates, and each day as a timeline.

The simulation never thinks in metres - this module gives everything a spot and keeps it there:
  - a fixed LAYOUT: where the shack, the field, the woods, the river, the rocky hill and the old road are
    (x east, z north, metres; y is up), plus the river and road as paths
  - every project gets a lot when it's planned (so its scaffolding stands where the building will), and the
    building keeps it forever; failed ones leave a ruin there. Big gathering places become walkable places.
  - trees disappear from the woods as wood is cut, stones from the hill as stone is hauled, tents fill the
    camp, piles by the shack grow and shrink with the stores
  - the king's day is a track: where he was, what he was doing (an animation name), for how long
  - settlers: the ones in today's story get a schedule (home -> where they work -> home); everyone else is a
    crowd count per place and hour

export(world) -> one JSON-able dict per post (schema "scene/1", see docs/SCENE.md). The renderer reads only
that - it never needs the save files.
"""
import math
import random
import re
import zlib

import numpy as np

from . import frontier as F

SCHEMA = "scene/1"

# where things are (metres). r = radius of the area; stand = where a person stands to do the place's thing
LAYOUT = {
    "shack": {"pos": [0, 0], "r": 6, "stand": [-1.4, -4.6]},     # stand: by the door, not inside the walls
    "field": {"pos": [38, 6], "r": 48},
    "woods": {"pos": [-72, 48], "r": 38},
    "river": {"pos": [-28, -40], "r": 10},
    "hill":  {"pos": [84, 78], "r": 28},
    "road":  {"pos": [16, -46], "r": 6},
    "camp":  {"pos": [46, -64], "r": 20},
}
RIVER = [[-140, -84], [-80, -58], [-30, -42], [8, -66], [48, -112], [70, -160]]       # a slow bend, 10 m wide
ROAD = [[22, -170], [20, -110], [16, -46], [6, -10]]                                  # from the south to the shack
TREES = 240
STONES = 240

# footprints: width (x), depth (z), height
SIZE = {"tiny": [3, 3, 2.2], "small": [6, 5, 3.6], "medium": [13, 7, 5.5], "large": [24, 9, 6.5],
        "huge": [18, 14, 16]}

ANIM_DO = [(r"\b(eat|ate|meal|breakfast|lunch|dinner|supper|stew|bread|snack)", "eat"),
           (r"\b(sleep|nap|doze|rest|lie down)", "sleep"), (r"\b(read|book|study|letters)", "read"),
           (r"\b(sing|hum|whistle)", "sing"), (r"\b(run|jog|sprint)", "run"), (r"\b(swim|wash|bathe)", "swim"),
           (r"\b(fish)", "fish"), (r"\b(carve|whittle|paint|draw|sketch|sculpt|weave|knit)", "craft"),
           (r"\b(pray)", "pray"), (r"\b(dance)", "dance"), (r"\b(cook|bake|stir)", "cook"),
           (r"\b(watch|sit|look|gaze|think|stare)", "sit"), (r"\b(explore|wander|stroll|walk)", "walk")]
ANIM_GATHER = {"wood": "chop", "stone": "mine", "clay": "dig", "thatch": "cut", "rope": "twist", "food": "forage"}
ANIM_TOOL = {"sleep": "sleep", "walk": "walk", "build": "hammer", "plan": "think", "talk": "talk", "hold_court": "judge",
             "ask_help": "speak", "organize": "speak", "proclaim": "speak", "appoint": "speak", "decree": "speak",
             "trade": "trade", "want": "think", "summon": "speak"}


def anim_for(tool, args, location):
    if tool == "gather":
        m = str(args.get("material") or "").lower().rstrip("s")
        return "fish" if m == "food" and location == "river" else ANIM_GATHER.get(m, "gather")
    if tool == "do":
        t = str(args.get("what") or "").lower()
        return next((a for pat, a in ANIM_DO if re.search(pat, t)), "idle")
    return ANIM_TOOL.get(tool, "idle")


# ---------------------------------------------------------------- shapes and lots
def shape_of(rec):
    """What the renderer should build: a family of models, picked from what the thing is."""
    kind, scale, name = rec.get("kind"), rec.get("scale", "small"), str(rec.get("name", "")).lower()
    if kind in ("tool", "comfort"):
        return None                                        # carried, or part of the shack
    if kind == "housing":
        return {"tiny": "hut", "small": "cottage", "medium": "longhouse", "large": "rowhouses", "huge": "apartments"}[scale]
    if kind == "food":
        if re.search(r"garden|farm|plot|field|orchard|patch|crop", name):
            return "plot"
        if re.search(r"trap|weir|net", name):
            return "fish_trap"
        return "shed"
    if kind == "storage":
        return "storehouse"
    if kind == "workshop":
        return "workshop"
    if kind == "defense":
        if re.search(r"wall|palisade|rampart|stockade|fence", name):
            return "wall_ring"
        return "tower"
    if kind == "gathering":
        return "hall"
    if kind == "path":
        if re.search(r"bridge", name):
            return "bridge"
        if re.search(r"well", name):
            return "well"
        if re.search(r"dock|jetty|pier", name):
            return "jetty"
        return "road"
    return "shed"


def size_of(rec, shape):
    w, d, h = SIZE.get(rec.get("scale", "small"), SIZE["small"])
    if shape == "plot":
        return [round(w * 1.3, 1), round(d * 1.3, 1), 0.4]
    if shape == "well":
        return [2.2, 2.2, 1.4]
    if shape == "fish_trap":
        return [4, 3, 0.8]
    if shape == "tower":
        return [4, 4, max(8, h)]
    if shape == "bridge":
        return [4, 16, 1.2]
    if shape == "jetty":
        return [3, 10, 1.0]
    return [w, d, h]


def _rect(pos, size, rot):
    w, d = (size[0], size[1]) if rot % 180 == 0 else (size[1], size[0])
    return (pos[0] - w / 2, pos[1] - d / 2, pos[0] + w / 2, pos[1] + d / 2)


def _hits(a, b, gap=2.0):
    return not (a[2] + gap < b[0] or b[2] + gap < a[0] or a[3] + gap < b[1] or b[3] + gap < a[1])


def _near_path(x, z, path, width):
    for (x1, z1), (x2, z2) in zip(path, path[1:]):
        dx, dz = x2 - x1, z2 - z1
        t = max(0.0, min(1.0, ((x - x1) * dx + (z - z1) * dz) / (dx * dx + dz * dz)))
        if math.hypot(x - (x1 + t * dx), z - (z1 + t * dz)) < width:
            return True
    return False


def _taken(world):
    L = F.land(world)
    out = [_rect(LAYOUT["shack"]["pos"], [8, 8, 3], 0)]
    for x in L["buildings"] + L["projects"]:
        if x.get("lot"):
            out.append(_rect(x["lot"]["pos"], x["lot"]["size"], x["lot"]["rot"]))
    return out


def place(world, rec):
    """Gives a project (or building) a lot near where it was planned, if it doesn't have one. Stays forever."""
    if rec.get("lot") or rec.get("id") == "b0":
        return rec.get("lot")
    shape = shape_of(rec)
    if not shape:
        return None
    size = size_of(rec, shape)
    if shape == "wall_ring":
        r = _settlement_radius(world) + 10
        rec["lot"] = {"pos": list(LAYOUT["field"]["pos"]), "size": [r * 2, r * 2, 3], "rot": 0, "shape": shape,
                      "radius": r}
        return rec["lot"]
    if shape in ("bridge", "jetty", "fish_trap"):
        x, z = RIVER[2]
        rec["lot"] = {"pos": [x + 2.0 * len(F.land(world)["buildings"]) % 9, z], "size": size, "rot": 0,
                      "shape": shape}
        return rec["lot"]
    where = rec.get("place") if rec.get("place") in LAYOUT else "field"
    if where in ("road", "shack", "river", "hill", "woods", "camp"):
        where = "field" if shape not in ("tower",) else where
    cx, cz = LAYOUT[where]["pos"]
    taken = _taken(world)
    rng = random.Random(zlib.crc32(str(rec.get("id", "")).encode()))
    rot = rng.choice([0, 90]) if shape not in ("rowhouses",) else 0
    for k in range(4000):                                       # a spiral out from the place's middle
        ang = k * 0.5
        rad = 3 + 1.1 * math.sqrt(k) * 3
        x, z = cx + rad * math.cos(ang), cz + rad * math.sin(ang)
        r = _rect([x, z], size, rot)
        if any(_hits(r, t) for t in taken):
            continue
        if _near_path(x, z, RIVER, 10 + max(size[:2]) / 2) or _near_path(x, z, ROAD, 4 + max(size[:2]) / 2):
            continue
        rec["lot"] = {"pos": [round(x, 1), round(z, 1)], "size": size, "rot": rot, "shape": shape}
        return rec["lot"]
    return None


def _settlement_radius(world):
    L = F.land(world)
    far = [math.hypot(b["lot"]["pos"][0] - LAYOUT["field"]["pos"][0], b["lot"]["pos"][1] - LAYOUT["field"]["pos"][1])
           + max(b["lot"]["size"][:2]) / 2 for b in L["buildings"] + L["projects"] if b.get("lot")
           and b["lot"]["shape"] != "wall_ring"]
    return max([30.0] + far)


def ensure(world):
    """Older saves: give anything without a lot a lot."""
    L = F.land(world)
    for x in L["buildings"] + L["projects"]:
        place(world, x)


# ---------------------------------------------------------------- the land's own things
def _scatter(n, center, r, seed, keep_out=None):
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        a, d = rng.random() * 2 * math.pi, r * math.sqrt(rng.random())
        x, z = center[0] + d * math.cos(a), center[1] + d * math.sin(a)
        if keep_out and keep_out(x, z):
            continue
        out.append([round(x, 1), round(z, 1), round(rng.uniform(0.8, 1.3), 2)])
    return out


def trees(world):
    """The woods, minus every tree that's been cut (closest to the shack first - that's where you'd start)."""
    L = F.land(world)
    cut = int(L.get("harvested", {}).get("wood", 0) // 12)
    all_ = _scatter(TREES, LAYOUT["woods"]["pos"], LAYOUT["woods"]["r"], 11,
                    keep_out=lambda x, z: _near_path(x, z, RIVER, 7))
    all_.sort(key=lambda t: math.hypot(t[0], t[1]))
    return all_[min(cut, TREES - 10):], cut


def stones(world):
    L = F.land(world)
    hauled = int(L.get("harvested", {}).get("stone", 0) // 15)
    all_ = _scatter(STONES, LAYOUT["hill"]["pos"], LAYOUT["hill"]["r"] * 0.9, 13)
    all_.sort(key=lambda t: math.hypot(t[0], t[1]))
    return all_[min(hauled, STONES - 5):], hauled


def tents(world, n):
    cx, cz = LAYOUT["camp"]["pos"]
    out = []
    per_row = 12
    for k in range(min(n, 600)):
        row, col = divmod(k, per_row)
        out.append([round(cx - 18 + col * 3.2 + (row % 2) * 1.6, 1), round(cz + 10 - row * 3.4, 1)])
    return out


def piles(world):
    """The stores, as heaps by the shack (or by the storehouse once there is one)."""
    L = F.land(world)
    store = next((b for b in L["buildings"] if b.get("kind") == "storage" and b.get("lot")), None)
    base = store["lot"]["pos"] if store else [5, -6]
    out = []
    for k, m in enumerate(("wood", "stone", "clay", "thatch", "rope", "food", "iron")):
        n = int(L["stock"].get(m, 0))
        if n >= 1:
            out.append({"material": m, "amount": n, "pos": [base[0] + 3 * (k % 4), base[1] - 3 * (k // 4)]})
    return out


def stand_pos(world, pid):
    """Where a person stands at a place (the shack's door rather than its middle)."""
    return list(LAYOUT.get(pid, {}).get("stand") or place_pos(world, pid))


def place_pos(world, pid):
    if pid in LAYOUT:
        return list(LAYOUT[pid]["pos"])
    p = F.places(world).get(pid) or {}
    b = next((b for b in F.land(world)["buildings"] if b["id"] == p.get("built")), None)
    if b and b.get("lot"):
        return list(b["lot"]["pos"])
    return list(LAYOUT["field"]["pos"])


# ---------------------------------------------------------------- tracks
def record(world, who, tool, args, moment):
    """Called after each action: where he was, what he did, for how long (the renderer animates it)."""
    if not world.frontier or who != "king":
        return
    me = world.agent(who)
    lv = world.city.living
    loc = me.get("location", "shack")
    dur = max(5, int(me.get("next_act", world.clock) - world.clock))
    pos = stand_pos(world, loc)
    if tool == "build":
        p = next((p for p in F.land(world)["projects"] if p["place"] == loc and p.get("lot")), None)
        if p:
            pos = list(p["lot"]["pos"])
    elif tool == "gather":
        pos = _gather_spot(world, loc, str(args.get("material") or ""))
    tr0 = lv.get("tracks", {}).get(who) or []
    if tool == "walk" and tr0 and tr0[-1]["place"] != loc:     # worn paths: where he keeps walking
        key = "|".join(sorted([tr0[-1]["place"], loc]))
        walks = F.land(world).setdefault("walks", {})
        walks[key] = walks.get(key, 0) + 1
    entry = {"t": world.clock, "place": loc, "pos": [round(pos[0], 1), round(pos[1], 1)],
             "anim": anim_for(tool, args, loc), "dur": dur, "tool": tool,
             "text": (moment or {}).get("text", "")[:200] if moment else ""}
    tr = lv.setdefault("tracks", {}).setdefault(who, [])
    tr.append(entry)
    keep = world.clock - 3 * 1440
    lv["tracks"][who] = [e for e in tr if e["t"] >= keep]


def _gather_spot(world, loc, material):
    if loc == "woods":
        ts, _ = trees(world)
        if ts:
            t = min(ts, key=lambda t: math.hypot(t[0], t[1]))
            return [t[0] + 1, t[1] + 1]
    if loc == "hill":
        ss, _ = stones(world)
        if ss:
            s = min(ss, key=lambda s: math.hypot(s[0], s[1]))
            return [s[0] + 1, s[1]]
    if loc == "river":
        return [RIVER[2][0] + 3, RIVER[2][1] + 6]
    return place_pos(world, loc)


def trees_all(world):
    """All the trees the woods started with, in the order they get cut (nearest the shack first)."""
    all_ = _scatter(TREES, LAYOUT["woods"]["pos"], LAYOUT["woods"]["r"], 11,
                    keep_out=lambda x, z: _near_path(x, z, RIVER, 7))
    all_.sort(key=lambda t: math.hypot(t[0], t[1]))
    return all_


def stones_all(world):
    all_ = _scatter(STONES, LAYOUT["hill"]["pos"], LAYOUT["hill"]["r"] * 0.9, 13)
    all_.sort(key=lambda t: math.hypot(t[0], t[1]))
    return all_


def sample(world):
    """Every hour: what the 3D view needs to show the day changing (not just how it ended)."""
    L = F.land(world)
    h = L.get("harvested", {})
    s = {"t": world.clock, "felled": min(int(h.get("wood", 0) // 12), TREES - 10),
         "hauled": min(int(h.get("stone", 0) // 15), STONES - 5), "tents": F.tents(world.city),
         "settled": F.settled(world.city), "stores": {m: int(v) for m, v in L["stock"].items() if v >= 1},
         "progress": {p["id"]: round(p["progress"], 3) for p in L["projects"]}}
    lv = world.city.living
    lv["samples"] = [x for x in lv.get("samples", []) if x["t"] >= world.clock - 2 * 1440] + [s]


def harvested(world, material, n):
    h = F.land(world).setdefault("harvested", {})
    h[material] = h.get(material, 0) + n


# ---------------------------------------------------------------- the export
def export(world, since=None, until=None):
    """Everything a renderer needs for the 24 hours of one post."""
    city, c, L = world.city, world.city.citizens, F.land(world)
    ensure(world)
    lv = city.living
    until = world.clock if until is None else until
    since = lv.get("last_post_clock", until - 1440) if since is None else since
    ts, felled = trees(world)
    ss, hauled = stones(world)
    samples = [x for x in lv.get("samples", []) if since <= x["t"] <= until]
    n_tents = F.tents(city)
    homes = L.get("homes", {})
    buildings = []
    for b in L["buildings"]:
        if b["id"] == "b0":
            buildings.append({"id": "b0", "name": "the shack", "shape": "shack", "kind": "housing",
                              "pos": list(LAYOUT["shack"]["pos"]), "size": [5, 4, 3], "rot": 0, "state": "standing",
                              "quality": b.get("quality", "poor"), "material": "wood",
                              "look": b.get("look", ""), "upgrades": [x["name"] for x in L["buildings"]
                                                                       if x.get("kind") == "comfort" and x is not b]})
            continue
        lot = b.get("lot")
        if not lot:
            continue
        buildings.append({"id": b["id"], "name": b["name"], "shape": lot["shape"], "kind": b["kind"],
                          "scale": b["scale"], "pos": lot["pos"], "size": lot["size"], "rot": lot["rot"],
                          "radius": lot.get("radius"), "state": "standing", "quality": b.get("quality"),
                          "material": b.get("material") or "wood", "look": b.get("look", ""),
                          "built_day": b.get("day"), "built_t": b.get("t"), "capacity": b.get("capacity", 0),
                          "residents": sorted(h for h, bid in homes.items() if bid == b["id"])[:200]})
    for r in L.get("ruins", []):
        buildings.append({**r, "state": "ruin"})
    projects = [{"id": p["id"], "name": p["name"], "shape": p["lot"]["shape"], "kind": p["kind"], "scale": p["scale"],
                 "pos": p["lot"]["pos"], "size": p["lot"]["size"], "rot": p["lot"]["rot"],
                 "radius": p["lot"].get("radius"), "state": "scaffold", "progress": round(p["progress"], 3),
                 "material": p.get("material") or "wood", "look": p.get("look", ""), "missing_know": p["missing"],
                 "started_t": p.get("started_t"),
                 "progress_at": [[x["t"], x["progress"][p["id"]]] for x in samples if p["id"] in x["progress"]]}
                for p in L["projects"] if p.get("lot")]
    moments = [m for m in lv.get("moments", []) if since < m["clock"] <= until]
    events = [{"t": m["clock"], "time": m["time"], "who": m["who"], "place": m.get("place"),
               "pos": place_pos(world, m["place"]) if m.get("place") else None, "text": m["text"],
               "drama": m["drama"], "public": m["public"], "kind": m.get("kind"), "handles": m.get("handles", [])}
              for m in moments]
    king = world.agent("king")
    track = [e for e in lv.get("tracks", {}).get("king", []) if since < e["t"] <= until]
    named = _named(world, moments)
    shots = []
    for m in sorted([e for e in events if e["public"]], key=lambda e: (-e["drama"], e["t"]))[:3]:
        target = m["pos"] or (track[-1]["pos"] if track else LAYOUT["shack"]["pos"])
        shots.append({"t": m["t"], "target": target, "distance": 18 if m["drama"] >= 3 else 12, "text": m["text"]})
    weather = [w for w in lv.get("weather_log", []) if since - 1440 < w["t"] <= until] or \
        [{"t": since, "weather": lv.get("weather", "a mild day")}]
    return {
        "schema": SCHEMA, "city": city.name, "day": city.day, "start": since, "end": until,
        "minutes_per_day": 1440, "post_hour": 19,
        "settlement": {"stage": L["stage"], "crowned": L["crowned"], "settled": F.settled(city),
                       "on_road": F.on_road(city), "beds": F.capacity(city), "free_beds": F.free_beds(city),
                       "tents": n_tents, "next_arrival": L["next_arrival"], "know": list(L["know"]),
                       "stores": {m: int(v) for m, v in L["stock"].items() if v >= 1}, "gold": round(city.treasury)},
        "terrain": {"ground": {"size": [420, 420]}, "river": {"path": RIVER, "width": 10},
                    "road": {"path": ROAD, "width": 4}, "hill": {"pos": LAYOUT["hill"]["pos"],
                                                                 "r": LAYOUT["hill"]["r"], "height": 20},
                    "woods": {"pos": LAYOUT["woods"]["pos"], "r": LAYOUT["woods"]["r"]}},
        "places": [{"id": pid, "name": p["name"], "pos": place_pos(world, pid),
                    "r": LAYOUT.get(pid, {}).get("r", 6), "resources": p.get("resources", [])}
                   for pid, p in F.places(world).items()],
        "trees": ts, "trees_felled": felled, "stones": ss, "stones_hauled": hauled,
        "trees_all": trees_all(world), "stones_all": stones_all(world),
        "samples": samples, "trails": _trails(world),
        "peddler": ({"until": L["peddler"]["until"], "goods": L["peddler"]["goods"],
                     "pos": [ROAD[2][0] + 4, ROAD[2][1] - 6]} if L.get("peddler") else None),
        "buildings": buildings, "projects": projects, "tents": tents(world, (n_tents + 1) // 2),
        "piles": piles(world),
        "weather": weather,
        "actors": {
            "king": {"name": "Aldric", "crowned": L["crowned"], "track": track,
                     "start": {"place": track[0]["place"] if track else king.get("location", "shack"),
                               "pos": track[0]["pos"] if track else stand_pos(world, king.get("location", "shack"))},
                     "needs": {k: round(v, 2) for k, v in king.get("life", {}).get("needs", {}).items()},
                     "becoming": king.get("self", {}).get("becoming", "")},
            "court": [{"id": k, "name": (__import__("city.living.life", fromlist=["court"]).court().get(k) or {})
                       .get("name", k), "pos": stand_pos(world, L["court_place"])} for k in L["court"]],
            "settlers": named,
            "crowd": _crowd(world),
        },
        "events": events, "shots": shots,
        "today": {"built": [b["name"] for b in L["buildings"] if b.get("day") == city.day],
                  "arrived": sum(1 for m in moments if "walked up the old road" in m["text"])},
    }


def _trails(world):
    """Worn paths: where people keep walking - settlers between home and work, the king between places."""
    city, c, L = world.city, world.city.citizens, F.land(world)
    wear = {}
    homes = L.get("homes", {})
    lots = {b["id"]: b["lot"]["pos"] for b in L["buildings"] if b.get("lot")}
    act = np.where(c.active())[0]
    for i in act[:5000]:
        h = c.handles[int(i)]
        a = tuple(lots.get(homes.get(h), LAYOUT["camp"]["pos"] if int(c.walled[i]) == -2 else LAYOUT["field"]["pos"]))
        b = tuple(place_pos(world, F.home_of(c, i)))
        key = (tuple(round(v / 6) * 6 for v in a), tuple(round(v / 6) * 6 for v in b))
        wear[key] = wear.get(key, 0) + 1
    for key, n in L.get("walks", {}).items():
        p, q = key.split("|")
        k = (tuple(place_pos(world, p)), tuple(place_pos(world, q)))
        wear[k] = wear.get(k, 0) + 3 * n
    top = sorted(wear.items(), key=lambda kv: -kv[1])[:40]
    return [{"from": list(a), "to": list(b), "wear": n} for (a, b), n in top if a != b]


def _named(world, moments, extra=20):
    """Settlers worth drawing as themselves: everyone in today's story, the officers, and a few more."""
    city, c, L = world.city, world.city.citizens, F.land(world)
    want = []
    for m in moments:
        want += m.get("handles", [])
    want += list(L.get("officers", {}).values())
    act = np.where(c.active())[0]
    if len(act):
        rng = random.Random(city.day)
        want += [c.handles[int(i)] for i in rng.sample(act.tolist(), min(extra, len(act)))]
    out = []
    homes = L.get("homes", {})
    tent_ix = {}
    from .intents import condition
    for h in dict.fromkeys(want):
        i = c.index.get(h)
        if i is None or c.status[i] != 0:
            continue
        if int(c.walled[i]) == -2:
            tent_ix.setdefault(h, len(tent_ix))
            home = {"tent": tent_ix[h]}
            home_pos = (tents(world, F.tents(city)) or [LAYOUT["camp"]["pos"]])[min(tent_ix[h], max(0, F.tents(city) - 1))]
        else:
            bid = homes.get(h)
            b = next((b for b in L["buildings"] if b["id"] == bid and b.get("lot")), None)
            home = {"building": bid}
            home_pos = b["lot"]["pos"] if b else place_pos(world, "field")
        work = F.home_of(c, i)
        cnd = condition(city, h)
        out.append({"handle": h, "name": c.names[i], "role": c.label(i), "home": home, "home_pos": home_pos,
                    "work": work, "work_pos": place_pos(world, work), "mood": round(float(c.mood[i]), 2),
                    "condition": cnd["state"] if cnd else None,
                    "schedule": [{"from": 7, "to": 19, "at": "work"}, {"from": 19, "to": 7, "at": "home"}]})
    return out[:120]


def _crowd(world):
    c = world.city.citizens
    act = np.where(c.active())[0]
    day = {}
    for i in act[:5000]:
        p = F.home_of(c, i)
        day[p] = day.get(p, 0) + 1
    scale = max(1, len(act)) / max(1, min(len(act), 5000))
    return {"day": {k: int(v * scale) for k, v in day.items()}, "night": {"homes": F.housed(world.city),
                                                                         "camp": F.tents(world.city)}}
