"""The 3D hand-off: a town that grows on a grid of streets, a house per person, and each post as a timeline."""
import json

from city.living import frontier as F
from city.living import scene


def _world(followers=6):
    from city import config
    from city.living.world import World
    from city.mayor import RuleMayor
    from city.model import City
    city = City(config.load(), seed=4)
    w = World(city)
    r = w.post(RuleMayor(), [f"u{i}" for i in range(followers)], [])
    return city, w, r


def _overlap(a, b, gap=0.0):
    return abs(a[0] - b[0]) < (a[2] + b[2]) / 2 + gap and abs(a[1] - b[1]) < (a[3] + b[3]) / 2 + gap


def test_every_post_comes_with_a_scene():
    city, w, r = _world()
    s = r["scene"]
    assert s["schema"] == scene.SCHEMA and s["end"] > s["start"]
    json.dumps(s)
    assert len(s["houses"]) == 6 and s["town"]["streets"] and s["buildings"][0]["kind"] == "keep"
    assert all(len(p["schedule"]) == 8 and p["work_pos"] and p["door"] for p in s["actors"]["settlers"])


def test_the_town_grows_out_from_the_keep_and_nothing_overlaps():
    city, w, _ = _world(followers=0)
    from city.living.frontier import join_road
    c = city.citizens
    join_road(w, c.add_many([f"h{i}" for i in range(60)], 1, city.ward_for, revive=False))
    city.treasury = 2000
    for kind in ("farm", "well", "brewery", "tavern"):
        p, why = F.start(w, kind, 0)
        assert p, why
    s = scene.export(w)
    rects = [(h[0], h[1], h[4], h[4]) for h in s["houses"]]
    rects += [(b["pos"][0], b["pos"][1], b["size"][0], b["size"][1]) for b in s["buildings"] + s["projects"]
              if b["kind"] != "keep"]
    rects.append((0, 0, 9, 9))                                       # the keep
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert not _overlap(a, b), (a, b)
    far = max(abs(x) + abs(z) for x, z, *_ in rects)
    assert far < 120                                                 # a compact town, not a scatter
    for x, z, *_ in rects:                                           # nothing on the river or the road
        assert not scene._near_path(x, z, scene.RIVER, 8) and not scene._near_path(x, z, scene.ROAD, 3)


def test_lots_are_kept():
    city, w, _ = _world(followers=10)
    city.treasury = 500
    p, _ = F.start(w, "farm", 0)
    lot = dict(p["lot"])
    p["done"] = p["need"]
    F.finish(w, p)
    assert F.land(w)["buildings"][-1]["lot"] == lot
    before = {h: scene.house_lot(w, F.land(w)["houses"][h]["n"])["pos"] for h in F.land(w)["houses"]}
    F.join_road(w, city.citizens.add_many(["late"], 1, city.ward_for, revive=False))
    assert all(scene.house_lot(w, F.land(w)["houses"][h]["n"])["pos"] == pos for h, pos in before.items())


def test_people_go_where_their_job_is():
    city, w, _ = _world(followers=12)
    city.treasury = 500
    p, _ = F.start(w, "farm", 0)
    p["done"] = p["need"]
    F.finish(w, p)
    s = scene.export(w)
    farm = s["buildings"][-1]
    workers = [x for x in s["actors"]["settlers"] if x["work"] == "b:" + farm["id"]]
    assert len(workers) >= 10 and all(x["work_pos"] == farm["pos"] for x in workers)
    day = workers[0]["schedule"]
    assert day[2]["what"] == "work" and day[2]["pos"] == farm["pos"]


def test_the_day_changes_hour_by_hour():
    city, w, _ = _world(followers=8)
    city.treasury = 500
    F.start(w, "farm", 0)
    for _ in range(48):
        w.tick()
    s = scene.export(w)
    assert len(s["samples"]) >= 12 and any(x["progress"] for x in s["samples"])
