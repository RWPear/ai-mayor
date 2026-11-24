"""The 3D hand-off: everything gets a spot and keeps it, and each post comes with a timeline."""
import json
import math

from city.living import frontier as F
from city.living import scene


def _world(followers=6):
    from city import config
    from city.living.world import World
    from city.mayor import RuleMayor
    from city.model import City
    cfg = config.load()
    cfg["frontier_arrivals"] = "weekly"
    city = City(cfg, seed=4)
    w = World(city)
    r = w.post(RuleMayor(), [f"u{i}" for i in range(followers)], [])
    return city, w, r


def _rects_overlap(a, b):
    ax, az, bx, bz = a["pos"][0], a["pos"][1], b["pos"][0], b["pos"][1]
    aw, ad = a["size"][:2] if a.get("rot", 0) % 180 == 0 else a["size"][1::-1]
    bw, bd = b["size"][:2] if b.get("rot", 0) % 180 == 0 else b["size"][1::-1]
    return abs(ax - bx) < (aw + bw) / 2 and abs(az - bz) < (ad + bd) / 2


def test_every_post_comes_with_a_scene():
    city, w, r = _world()
    s = r["scene"]
    assert s["schema"] == scene.SCHEMA and s["end"] > s["start"]
    json.dumps(s)                                                  # plain JSON, nothing exotic
    assert {"terrain", "places", "trees", "buildings", "projects", "actors", "events", "shots"} <= set(s)
    assert s["buildings"][0]["shape"] == "shack"
    assert s["actors"]["king"]["track"], "the king's day is a track"
    assert all(e["anim"] for e in s["actors"]["king"]["track"])


def test_lots_are_kept_and_never_overlap():
    city, w, _ = _world()
    me = w.agent("king")
    for idea in ("a small cottage", "a longhouse for the newcomers", "a vegetable garden"):
        F.land(w)["projects"] = [p for p in F.land(w)["projects"] if p["progress"] > 0]
        p, _ = F.start_project(w, idea, "field")
        if p:
            assert p["lot"]
    lots = [x["lot"] for x in F.land(w)["projects"] + F.land(w)["buildings"] if x.get("lot")]
    for i, a in enumerate(lots):
        for b in lots[i + 1:]:
            assert not _rects_overlap(a, b)
    p = F.land(w)["projects"][0]
    before = list(p["lot"]["pos"])
    for m, n in p["needs"].items():
        F.land(w)["stock"][m] = n
    city.rng.random = lambda: 0.01
    F.work(w, p, 10 ** 4)
    b = F.land(w)["buildings"][-1]
    assert b["lot"]["pos"] == before                               # the building stands where its scaffold was


def test_the_woods_thin_out_as_wood_is_cut():
    city, w, _ = _world()
    n0, f0 = len(scene.trees(w)[0]), scene.trees(w)[1]
    scene.harvested(w, "wood", 240)
    ts, felled = scene.trees(w)
    assert felled == f0 + 20 and len(ts) == n0 - 20
    near = min(math.hypot(x, z) for x, z, _ in ts)
    assert near > 0


def test_collapses_leave_ruins_where_they_stood():
    city, w, _ = _world()
    F.land(w)["buildings"].append({"id": "b9", "name": "a hut", "kind": "housing", "scale": "tiny", "capacity": 1,
                                   "place": "field", "quality": "good", "day": 1})   # (the first house never falls)
    p, _ = F.start_project(w, "a small cottage", "field")
    for m, n in p["needs"].items():
        F.land(w)["stock"][m] = n
    city.rng.random = lambda: 0.999
    F.work(w, p, 10 ** 4)
    s = scene.export(w)
    ruin = [b for b in s["buildings"] if b["state"] == "ruin"]
    assert ruin and ruin[0]["pos"] == p["lot"]["pos"]


def test_settlers_have_homes_and_work():
    city, w, _ = _world(followers=4)
    L = F.land(w)
    L["buildings"].append({"id": "bz", "name": "a cottage", "kind": "housing", "scale": "small", "capacity": 2,
                           "place": "field", "quality": "good", "day": 1})
    scene.place(w, L["buildings"][-1])
    L["next_arrival"] = city.day + 1
    F.arrive(w)
    s = scene.export(w)
    people = {p["handle"]: p for p in s["actors"]["settlers"]}
    assert len(people) == 4
    housed = [p for p in people.values() if "building" in p["home"]]
    tented = [p for p in people.values() if "tent" in p["home"]]
    assert len(housed) == 2 and len(tented) == 2 and len(s["tents"]) >= 1
    assert all(p["work_pos"] and p["home_pos"] for p in people.values())


def test_the_viewer_page_can_be_built():
    from city.config import ROOT
    page = (ROOT / "viewer" / "index.html").read_text()
    assert '<script id="scene-data" type="application/json">null</script>' in page


def test_the_day_changes_hour_by_hour():
    city, w, _ = _world()
    from city.mayor import RuleMayor
    r = w.post(RuleMayor(), [], [])
    s = r["scene"]
    assert len(s["samples"]) >= 20                              # an hourly snapshot through the day
    assert all({"t", "felled", "hauled", "tents", "stores", "progress"} <= set(x) for x in s["samples"])
    assert s["trees_all"] and len(s["trees_all"]) >= len(s["trees"])
    for p in s["projects"]:
        assert "progress_at" in p and "started_t" in p
    assert isinstance(s["trails"], list)


def test_the_viewer_is_served_with_the_runs_days(tmp_path):
    import urllib.request
    from city import recorder
    from city.config import ROOT
    days = tmp_path / "days"
    days.mkdir()
    city, w, r = _world()
    (days / f"day{r['day']:03d}.scene.json").write_text(json.dumps(r["scene"]))
    srv = recorder.serve(days, port=8833, block=False)
    try:
        get = lambda p: urllib.request.urlopen(f"http://127.0.0.1:8833{p}", timeout=5).read().decode()
        assert "Emberfall" in get("/")
        assert json.loads(get("/days/scenes.json"))[0]["day"] == r["day"]
        assert "overview" in [x["name"] for x in json.loads(get("/recorders.json"))]
        assert "kingdom" in get("/js/main.js")
        assert json.loads(get(f"/days/day{r['day']:03d}.scene.json"))["schema"] == scene.SCHEMA
    finally:
        srv.shutdown()
    assert (ROOT / "content" / "recorders.yaml").exists()
