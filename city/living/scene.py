"""What the 3D view needs: Emberfall as a place with coordinates, and each day as a timeline.

The simulation never thinks in metres - this module gives everything a spot and keeps it there:
  - a fixed LAYOUT on the island: the keep in the middle, the square next to it, the field, the woods, the river,
    the rocky hill and the old road (x east, z north, metres; y is up), plus the river and road as paths
  - THE TOWN is a grid of blocks spiralling out from the keep, nearest first (skipping the river, the road, the
    crag and the island's edge; the woods only once there's nowhere else). Every person's house takes a quarter of
    a block (an eighth once the town is big: rowhouses); every building takes a whole block. Lots are handed out
    in the order things happen and kept forever, so the town grows ring by ring like a real one
  - the king's day is a track: where he was, what he was doing (an animation name), for how long
  - people: everyone's day (city/living/routine.py) with real positions - their door, their job, the square

export(world) -> one JSON-able dict per post (schema "scene/2", see docs/SCENE.md). The renderer reads only that.
"""
import math
import random
import re
import zlib

import numpy as np

from . import frontier as F
from . import routine

SCHEMA = "scene/2"

LAYOUT = {
    "shack": {"pos": [0, 0], "r": 6, "stand": [0, -6]},           # the keep (whatever it is this week)
    "square": {"pos": [-13, -13], "r": 6},                         # the fire everyone eats at
    "field": {"pos": [38, 6], "r": 48},
    "woods": {"pos": [-72, 48], "r": 38},
    "river": {"pos": [-28, -40], "r": 10},
    "hill":  {"pos": [84, 78], "r": 28},
    "road":  {"pos": [16, -46], "r": 6},
}
LAYOUT["commons"] = LAYOUT["square"]
RIVER = [[-140, -84], [-80, -58], [-30, -42], [8, -66], [48, -112], [70, -160]]       # a slow bend, 10 m wide
ROAD = [[22, -170], [20, -110], [16, -46], [6, -10]]                                  # from the south to the keep
TREES = 240
STONES = 240
BLOCK = 13.0              # block pitch: 9 m of lots and a 4 m street
LOT = 9.0
STREETS = ["Keep Street", "Baker's Row", "Mud Lane", "Cloud Street", "Lantern Lane", "Goat Walk", "Bell Street",
           "Ember Row", "Well Lane", "Rook Street", "Thistle Lane", "Fiddler's Walk", "Crooked Lane", "Edge Street",
           "Barrel Row", "Sparrow Lane", "Mill Street", "Ladder Lane", "Copper Row", "Moss Street"]

ANIM_DO = [(r"\b(eat|ate|meal|breakfast|lunch|dinner|supper|stew|bread|snack)", "eat"),
           (r"\b(sleep|nap|doze|rest|lie down)", "sleep"), (r"\b(read|book|study|letters)", "read"),
           (r"\b(sing|hum|whistle)", "sing"), (r"\b(run|jog|sprint)", "run"), (r"\b(swim|wash|bathe)", "swim"),
           (r"\b(fish)", "fish"), (r"\b(carve|whittle|paint|draw|sketch|sculpt|weave|knit)", "craft"),
           (r"\b(pray)", "pray"), (r"\b(dance)", "dance"), (r"\b(cook|bake|stir)", "cook"),
           (r"\b(watch|sit|look|gaze|think|stare)", "sit"), (r"\b(explore|wander|stroll|walk)", "walk")]
ANIM_TOOL = {"sleep": "sleep", "walk": "walk", "build": "hammer", "plan": "think", "invest": "think", "talk": "talk",
             "hold_court": "judge", "rally": "speak", "proclaim": "speak", "appoint": "speak", "decree": "speak",
             "want": "think", "summon": "speak"}


def anim_for(tool, args, location):
    if tool == "do":
        t = str(args.get("what") or "").lower()
        return next((a for pat, a in ANIM_DO if re.search(pat, t)), "idle")
    return ANIM_TOOL.get(tool, "idle")


# ---------------------------------------------------------------- where things can go
def _near_path(x, z, path, width):
    for (x1, z1), (x2, z2) in zip(path, path[1:]):
        dx, dz = x2 - x1, z2 - z1
        t = max(0.0, min(1.0, ((x - x1) * dx + (z - z1) * dz) / (dx * dx + dz * dz)))
        if math.hypot(x - (x1 + t * dx), z - (z1 + t * dz)) < width:
            return True
    return False


def on_crag(x, z, pad=0.0):
    """The rocky hill is a crag (viewer/js/terrain.js): cliffs, a flat top, one ramp down toward the field."""
    hx, hz = LAYOUT["hill"]["pos"]
    fx, fz = LAYOUT["field"]["pos"]
    dx, dz, d0 = x - hx, z - hz, math.hypot(x - hx, z - hz)
    tl = math.hypot(fx - hx, fz - hz) or 1
    toward = max(0.0, (dx * (fx - hx) + dz * (fz - hz)) / (max(d0, 0.01) * tl))
    reach = LAYOUT["hill"]["r"] * 1.35 * (1 + 0.6 * toward ** 3)
    return d0 < reach * 1.12 + pad


_BLOCKS = None


def blocks():
    """Every block the town could ever use, nearest the keep first. [(bx, bz, x, z)]"""
    global _BLOCKS
    if _BLOCKS is not None:
        return _BLOCKS
    isl = F.ISLAND
    out = []
    n = int(isl["r"] // BLOCK) + 2
    sq = LAYOUT["square"]["pos"]
    for bx in range(-n, n + 1):
        for bz in range(-n, n + 1):
            x, z = bx * BLOCK, bz * BLOCK
            if math.hypot(x - isl["pos"][0], z - isl["pos"][1]) > isl["r"] - 16:
                continue
            if (bx, bz) == (0, 0) or math.hypot(x - sq[0], z - sq[1]) < 2:    # the keep's block; the square
                continue
            if _near_path(x, z, RIVER, 13) or _near_path(x, z, ROAD, 8.5) or on_crag(x, z, 8):
                continue
            d = math.hypot(x, z) + (zlib.crc32(f"{bx},{bz}".encode()) % 100) / 30
            if math.hypot(x - LAYOUT["woods"]["pos"][0], z - LAYOUT["woods"]["pos"][1]) < LAYOUT["woods"]["r"] + 6:
                d += 90                                          # the woods: last
            out.append((d, bx, bz, x, z))
    out.sort()
    _BLOCKS = [(bx, bz, x, z) for _, bx, bz, x, z in out]
    return _BLOCKS


def _take_block(world, use, cap=0):
    L = F.land(world)
    used = L.setdefault("blocks", [])
    k = len(used)
    if k >= len(blocks()):
        k = len(used) % len(blocks())                       # (the whole island's full: stack up)
    used.append({"i": k, "use": use, "cap": cap})
    return used[-1]


def house_lot(world, n):
    """House n (in order of arrival): a quarter of a block (an eighth once the town is big). Returns {pos, rot}."""
    L = F.land(world)
    hb = [b for b in L.setdefault("blocks", []) if b["use"] == "houses"]
    start = 0
    for b in hb:
        if n < start + b["cap"]:
            return _house_in(b, n - start)
        start += b["cap"]
    while True:                                             # a new block of houses
        b = _take_block(world, "houses", cap=4 if len(hb) < 40 else 8)
        hb.append(b)
        if n < start + b["cap"]:
            return _house_in(b, n - start)
        start += b["cap"]


def _house_in(b, k):
    bx, bz, x, z = blocks()[b["i"]]
    if b["cap"] == 4:                                       # four cottages, each facing its street
        sx, sz = (-1, 1, -1, 1)[k], (-1, -1, 1, 1)[k]
        return {"pos": [round(x + sx * 2.3, 1), round(z + sz * 2.3, 1)], "rot": 180 if sz < 0 else 0, "size": 3.8}
    row, col = divmod(k, 4)                                 # two rows of four narrow houses
    return {"pos": [round(x - 3.4 + col * 2.27, 1), round(z + (-2.4 if row == 0 else 2.4), 1)],
            "rot": 180 if row == 0 else 0, "size": 2.1}


def street_of(world, n):
    L = F.land(world)
    hb = [b for b in L.get("blocks", []) if b["use"] == "houses"]
    start = 0
    for b in hb:
        if n < start + b["cap"]:
            bx, bz, _, _ = blocks()[b["i"]]
            return STREETS[(bx * 7 + bz * 3) % len(STREETS)]
        start += b["cap"]
    return STREETS[0]


def civic_lot(world, p):
    """A whole block for a building (kept when it's finished). The palisade rings the town instead."""
    if p.get("lot"):
        return p["lot"]
    if p["kind"] == "palisade":
        r = town_radius(world) + 10
        p["lot"] = {"pos": [0, 0], "size": [r * 2, r * 2], "rot": 0, "radius": r}
        return p["lot"]
    b = _take_block(world, p["id"])
    _, _, x, z = blocks()[b["i"]]
    p["lot"] = {"pos": [x, z], "size": [LOT, LOT], "rot": (zlib.crc32(p["id"].encode()) % 4) * 90}
    return p["lot"]


def town_radius(world):
    used = F.land(world).get("blocks", [])
    return max([20.0] + [math.hypot(*blocks()[b["i"]][2:]) + 8 for b in used])


def streets(world):
    """The streets between the blocks in use: segments [[x1, z1], [x2, z2]] (deduped)."""
    seen, out = set(), []
    h = BLOCK / 2
    used = [blocks()[b["i"]] for b in F.land(world).get("blocks", [])] + [(0, 0, 0.0, 0.0)]
    sq = LAYOUT["square"]["pos"]
    used.append((round(sq[0] / BLOCK), round(sq[1] / BLOCK), sq[0], sq[1]))
    for bx, bz, x, z in used:
        for a, b in (((x - h, z - h), (x + h, z - h)), ((x - h, z + h), (x + h, z + h)),
                     ((x - h, z - h), (x - h, z + h)), ((x + h, z - h), (x + h, z + h))):
            key = (round(a[0], 1), round(a[1], 1), round(b[0], 1), round(b[1], 1))
            if key not in seen:
                seen.add(key)
                out.append([[key[0], key[1]], [key[2], key[3]]])
    return out


def house_pos(world, h):
    hs = F.land(world)["houses"].get(h)
    if not hs:
        return list(LAYOUT["field"]["pos"])
    return house_lot(world, hs["n"])["pos"]


def door_pos(world, h):
    """Just outside their front door (on the street side)."""
    hs = F.land(world)["houses"].get(h)
    if not hs:
        return list(LAYOUT["square"]["pos"])
    lot = house_lot(world, hs["n"])
    dz = -1 if lot["rot"] == 180 else 1
    return [lot["pos"][0], round(lot["pos"][1] + dz * (lot["size"] / 2 + 1.2), 1)]


def place_pos(world, pid):
    """A place id, or 'b:<building>' / 'p:<project>' (where people work), -> [x, z]."""
    L = F.land(world)
    if isinstance(pid, str) and pid[:2] in ("b:", "p:"):
        pool = L["buildings"] if pid[0] == "b" else L["projects"]
        x = next((x for x in pool if x["id"] == pid[2:]), None)
        if x and x.get("lot"):
            return list(x["lot"]["pos"])
        if x and x["id"] == "b0":
            return list(LAYOUT["shack"]["pos"])
        return list(LAYOUT["square"]["pos"])
    if pid in LAYOUT:
        return list(LAYOUT[pid]["pos"])
    p = F.places(world).get(pid) or {}
    if p.get("pos"):                                          # new land risen from the clouds
        return list(p["pos"])
    b = next((b for b in L["buildings"] if b["id"] == p.get("built")), None)
    if b and b.get("lot"):
        return list(b["lot"]["pos"])
    return list(LAYOUT["field"]["pos"])


def stand_pos(world, pid):
    return list(LAYOUT.get(pid, {}).get("stand") or place_pos(world, pid))


# ---------------------------------------------------------------- scenery
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


def trees_all(world):
    return _scatter(TREES, LAYOUT["woods"]["pos"], LAYOUT["woods"]["r"], 11, keep_out=lambda x, z: _near_path(x, z, RIVER, 7))


def stones_all(world):
    return _scatter(STONES // 3, LAYOUT["hill"]["pos"], LAYOUT["hill"]["r"] * 0.9, 13)


# ---------------------------------------------------------------- tracks
def record(world, who, tool, args, moment):
    """Called after each action: where he was, what he did, for how long (the renderer animates it)."""
    if who != "king":
        return
    me = world.agent(who)
    lv = world.city.living
    loc = me.get("location", "shack")
    dur = max(5, int(me.get("next_act", world.clock) - world.clock))
    pos = stand_pos(world, loc)
    if tool == "build" and F.land(world)["projects"]:
        p = F.land(world)["projects"][0]
        if p.get("lot"):
            pos = [p["lot"]["pos"][0] + 5.5, p["lot"]["pos"][1]]
    entry = {"t": world.clock, "place": loc, "pos": [round(pos[0], 1), round(pos[1], 1)],
             "anim": anim_for(tool, args, loc), "dur": dur, "tool": tool,
             "text": (moment or {}).get("text", "")[:200] if moment else ""}
    tr = lv.setdefault("tracks", {}).setdefault(who, [])
    tr.append(entry)
    keep = world.clock - 3 * 1440
    lv["tracks"][who] = [e for e in tr if e["t"] >= keep]


def sample(world):
    """Every hour: what the 3D view needs to show the day changing (projects rising, people arriving)."""
    L = F.land(world)
    s = {"t": world.clock, "settled": F.settled(world.city), "gold": round(world.city.treasury),
         "progress": {p["id"]: round(p["done"] / p["need"], 3) for p in L["projects"]},
         "houses": len(L["houses"])}
    lv = world.city.living
    lv["samples"] = [x for x in lv.get("samples", []) if x["t"] >= world.clock - 2 * 1440] + [s]


# ---------------------------------------------------------------- the export
def _lot_of_b0():
    return {"pos": list(LAYOUT["shack"]["pos"]), "size": [LOT, LOT], "rot": 0}


def export(world, since=None, until=None):
    """Everything a renderer needs for the 24 hours of one post."""
    city, c, L = world.city, world.city.citizens, F.land(world)
    lv = city.living
    until = world.clock if until is None else until
    since = lv.get("last_post_clock", until - 1440) if since is None else since
    samples = [x for x in lv.get("samples", []) if since <= x["t"] <= until]
    crew = L.get("crew", {})
    jobs = L.get("jobs", {})
    staff = {}
    for h, j in jobs.items():
        staff[j] = staff.get(j, 0) + 1
    buildings = []
    for b in L["buildings"]:
        lot = b.get("lot") or (_lot_of_b0() if b["id"] == "b0" else None)
        if not lot:
            continue
        s = F.spec(b["kind"])
        buildings.append({"id": b["id"], "kind": b["kind"], "shape": s["shape"], "name": b["name"], "tier": b["tier"],
                          "tiers": len(s["tiers"]), "state": b["state"], "pos": lot["pos"], "size": lot["size"],
                          "rot": lot["rot"], "radius": lot.get("radius"), "running": bool(b.get("running")),
                          "crew": crew.get(b["id"], staff.get(b["id"], 0)), "needs_crew": F.crew_of(b), "job": s["job"],
                          "condition": round(b.get("condition", 1.0), 2), "disrepair": bool(b.get("disrepair")),
                          "look": b.get("look", ""), "built_t": b.get("t") if b["id"] != "b0" else None,
                          "place": b.get("place")})
    projects = []
    for p in L["projects"]:
        lot = p.get("lot") or (_lot_of_b0() if p.get("upgrade_of") == "b0" else None)
        if not lot:
            continue
        s = F.spec(p["kind"])
        projects.append({"id": p["id"], "kind": p["kind"], "shape": s["shape"], "name": p["name"], "tier": p["tier"],
                         "pos": lot["pos"], "size": lot["size"], "rot": lot["rot"], "radius": lot.get("radius"),
                         "state": "scaffold", "progress": round(p["done"] / p["need"], 3), "need": p["need"],
                         "builders": staff.get("build:" + p["id"], 0), "upgrade_of": p.get("upgrade_of"),
                         "started_t": p.get("started_t"), "look": p.get("look", ""),
                         "progress_at": [[x["t"], x["progress"][p["id"]]] for x in samples if p["id"] in x["progress"]]})
    houses = []
    for h, hs in L["houses"].items():
        i = c.index.get(h)
        if i is None or c.status[i] != 0:
            continue
        lot = house_lot(world, hs["n"])
        houses.append([lot["pos"][0], lot["pos"][1], lot["rot"], hs["tier"], lot["size"], h, hs.get("t") or 0])
    moments = [m for m in lv.get("moments", []) if since < m["clock"] <= until]
    events = [{"t": m["clock"], "time": m["time"], "who": m["who"], "place": m.get("place"),
               "pos": place_pos(world, m["place"]) if m.get("place") else None, "text": m["text"],
               "drama": m["drama"], "public": m["public"], "kind": m.get("kind"), "handles": m.get("handles", [])}
              for m in moments]
    king = world.agent("king")
    track = [e for e in lv.get("tracks", {}).get("king", []) if since < e["t"] <= until]
    named = _people(world, moments)
    shots = []
    for m in sorted([e for e in events if e["public"]], key=lambda e: (-e["drama"], e["t"]))[:3]:
        target = m["pos"] or (track[-1]["pos"] if track else LAYOUT["shack"]["pos"])
        shots.append({"t": m["t"], "target": target, "distance": 18 if m["drama"] >= 3 else 12, "text": m["text"]})
    weather = [w for w in lv.get("weather_log", []) if since - 1440 < w["t"] <= until] or \
        [{"t": since, "weather": lv.get("weather", "a mild day")}]
    hist = L.get("history", [])
    return {
        "schema": SCHEMA, "city": city.name, "day": city.day, "start": since, "end": until,
        "minutes_per_day": 1440, "post_hour": 19,
        "settlement": {"stage": L["stage"], "crowned": L["crowned"], "settled": F.settled(city),
                       "gold": round(city.treasury), "happiness": L.get("happiness", 0.6),
                       "houses": len(houses), "power": hist[-1] if hist else None,
                       "wants": L.get("wants", {}), "tents": 0, "beds": F.settled(city), "free_beds": 0},
        "terrain": {"ground": {"size": [640, 640]}, "island": F.island(city), "river": {"path": RIVER, "width": 10},
                    "road": {"path": ROAD, "width": 4}, "hill": {"pos": LAYOUT["hill"]["pos"],
                                                                 "r": LAYOUT["hill"]["r"], "height": 20},
                    "woods": {"pos": LAYOUT["woods"]["pos"], "r": LAYOUT["woods"]["r"]}},
        "town": {"block": BLOCK, "lot": LOT, "streets": streets(world), "square": LAYOUT["square"]["pos"],
                 "radius": round(town_radius(world), 1)},
        "places": [{"id": pid, "name": p["name"], "pos": place_pos(world, pid), "r": LAYOUT.get(pid, {}).get("r", 6)}
                   for pid, p in F.places(world).items()],
        "trees": trees_all(world), "trees_all": trees_all(world), "trees_felled": 0,
        "stones": stones_all(world), "stones_all": stones_all(world), "stones_hauled": 0,
        "samples": samples, "trails": [],
        "buildings": buildings, "projects": projects, "houses": houses, "tents": [], "piles": [],
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
            "crowd": {"day": {}, "night": {}},
        },
        "events": events, "shots": shots,
        "routine": {"day": [{"from": m, "what": w, "where": x} for m, w, x in routine.DAY],
                    "commons": LAYOUT["square"]["pos"]},
        "encounters": [{"t": e["t"], "a": e["a"], "b": e["b"], "kind": e["kind"], "anim": e["anim"],
                        "label": e["label"], "text": e["text"], "what": e["what"]}
                       for e in routine.today(world, since) if e["t"] <= until],
        "today": {"built": [b["name"] for b in L["buildings"] if b.get("day") == city.day],
                  "arrived": sum(1 for m in moments if "walked up the old road" in m["text"])},
    }


MAX_PEOPLE = 1500


def _people(world, moments):
    """Everyone (up to MAX_PEOPLE: the ones in today's story first), with their day."""
    city, c, L = world.city, world.city.citizens, F.land(world)
    want = []
    for m in moments:
        want += m.get("handles", [])
    want += [e[k] for e in routine.today(world, world.clock - (world.clock % 1440)) for k in ("a", "b")]
    act = np.where(c.active())[0]
    want += [c.handles[int(i)] for i in act]
    out = []
    from .intents import condition
    for h in dict.fromkeys(want):
        i = c.index.get(h)
        if i is None or c.status[i] != 0:
            continue
        cnd = condition(city, h)
        out.append({"handle": h, "name": c.names[i], "role": L["prof"].get(h) or c.roles.get(int(i)) or "settler",
                    "job": F.job_label(world, h), "home_pos": house_pos(world, h), "door": door_pos(world, h),
                    "work": F.job_place(world, h), "work_pos": place_pos(world, F.job_place(world, h)),
                    "mood": round(float(c.mood[i]), 2), "condition": cnd["state"] if cnd else None,
                    "schedule": day_of(world, i)})
        if len(out) >= MAX_PEOPLE:
            break
    return out


def day_of(world, i):
    """Someone's day for the 3D view: each block with where it is."""
    h = world.city.citizens.handles[int(i)]
    out = []
    for b in routine.schedule(world, i):
        w = b["where"]
        if w == "home":
            pos = door_pos(world, h)
        elif w == "visit" and b.get("with") in world.city.citizens.index:
            pos = door_pos(world, b["with"])
        else:
            pos = place_pos(world, w)
        out.append({"from": b["from"], "to": b["to"], "what": b["what"], "where": w, "pos": [round(pos[0], 1), round(pos[1], 1)],
                    "with": b.get("with")})
    return out


# (older callers)
def home_pos_of(world, h):
    return house_pos(world, h)


def home_pos(world, h):
    return house_pos(world, h)
