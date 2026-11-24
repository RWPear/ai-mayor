"""Places on the island, and the settlement's houses and walls - the bits the king's tools, the war camp and the
3D view share. The places themselves (and how they grow as things get built) are in city/living/frontier.py."""
import numpy as np


def build_walls(world, quality):
    """His walls are finished: everyone living now (and a little more) fits inside."""
    city, c = world.city, world.city.citizens
    t = city.living["town"]
    houses = int(c.active().sum())
    extra = {"success": 1.3, "shoddy": 1.05}.get(quality, 1.0)
    t["walls"]["capacity"] = max(t["walls"]["capacity"], int(houses * extra) + 20)
    t["walls"]["built"] = city.day + 1
    room = t["walls"]["capacity"] - int((c.walled == 1).sum())
    out = np.where(c.active() & (c.walled == 0))[0][:max(0, room)]
    c.walled[out] = 1


def burn_houses(world, ward, raiders):
    """A raid that got through burns houses outside the walls in that corner. Returns the handles hit."""
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
    tents = int((a & (c.walled == -2)).sum())
    inside = int((a & (c.walled == 1)).sum())
    burned = int((a & (c.burned > 0)).sum())
    t = world.city.living["town"]
    walls = "no walls" if not t["walls"]["capacity"] else f"{inside} inside the walls, {houses - inside} outside"
    return (f"{houses} in houses ({walls}" + (f", {burned} burned down" if burned else "") + ")"
            + (f", {tents} in tents" if tents else ""))


def court_place(world):
    """Where the king hears cases: his shack, until he builds somewhere better."""
    return world.city.living["town"]["land"]["court_place"]


def places(town):
    return town["places"]


def place_of(pid, town):
    return (town["places"].get(pid) or {"name": str(pid)})["name"]


def describe(town, pid):
    feats = town["features"].get(pid, {})
    return "; ".join(f"{k}: {v}" for k, v in feats.items()) or "nothing much"


def match_place(text, town):
    from .frontier import match_in
    return match_in(town["places"], text)
