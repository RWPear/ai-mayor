"""Emberfall on People Power: everyone works a shift a day, buildings need crews to run and builders to go up, gold
decides how fine they are (city/living/frontier.py)."""
import numpy as np

from city.living import frontier as F
from city.living import frontier_tools as FT


def _world(followers=5, seed=3, llm=None, voice=None):
    from city import config
    from city.living.world import World
    from city.mayor import RuleMayor
    from city.model import City
    city = City(config.load(), seed=seed)
    w = World(city, king_brain=llm, voice_llm=voice)
    w.post(RuleMayor(), [f"u{i}" for i in range(followers)], [])
    return city, w


def _arrive(w, handles):
    c = w.city.citizens
    return F.join_road(w, c.add_many(handles, w.city.day, w.city.ward_for, revive=False))


def _build_now(w, kind, gold=None):
    """A finished building of this kind (as if the people had built it)."""
    w.city.treasury += 1000
    p, why = F.start(w, kind, F.spec(kind)["tiers"][0]["gold"] if gold is None else gold)
    assert p, why
    p["done"] = p["need"]
    F.finish(w, p)
    return F.land(w)["buildings"][-1]


def test_he_starts_alone_and_every_follower_gets_a_house_straight_away():
    from city import config
    from city.living.world import World
    from city.model import City
    city = City(config.load(), seed=3)
    w = World(city)
    L = F.land(w)
    assert [b["kind"] for b in L["buildings"]] == ["keep"] and not L["houses"] and not L["crowned"]
    _arrive(w, ["ann", "bob", "cat", "dan", "eve"])
    assert F.settled(city) == 5 and set(L["houses"]) == {"ann", "bob", "cat", "dan", "eve"}
    from city.living import scene
    lots = [scene.house_lot(w, L["houses"][h]["n"])["pos"] for h in L["houses"]]
    assert len({tuple(p) for p in lots}) == 5                         # a house each, on its own lot
    assert "moved into a little house" in city.living["just_arrived"]["ann"]["text"]


def test_everyone_works_a_shift_and_commenters_work_two_where_they_say():
    city, w = _world(followers=12)
    _build_now(w, "farm")
    F.nudge(w, "u0", "I'll help out at the farm today")
    jobs = F.assign(w)
    assert len(jobs) == 12 and F.land(w)["jobs"]["u0"] == F.land(w)["buildings"][-1]["id"]
    assert F.today(w)["extra"] == {"u0": 1}
    r = F.settle(w)
    assert r["shifts"] == 13 and r["extra"] == 1


def test_a_building_only_runs_when_its_whole_crew_turns_up():
    city, w = _world(followers=9)
    farm = _build_now(w, "farm")
    F.assign(w)
    assert not farm["running"]                                        # nine people, a farm needs ten
    gold = city.treasury
    r = F.settle(w)
    assert any(n == farm["name"] for n, *_ in r["idle"]) and farm["condition"] < 1
    _arrive(w, ["tenth"])
    F.assign(w)
    assert farm["running"]
    r = F.settle(w)
    assert any(n == farm["name"] for n, *_ in r["ran"]) and city.treasury > gold


def test_nobody_builds_it_and_it_never_goes_up_and_a_crowd_still_takes_a_day():
    city, w = _world(followers=0)
    city.treasury = 500
    p, why = F.start(w, "farm", 0)
    assert p and p["need"] >= 8
    F.settle(w)
    assert p in F.land(w)["projects"] and p["done"] == 0               # nobody here: nothing happens
    _arrive(w, [f"b{i}" for i in range(40)])
    assert p in F.land(w)["projects"] and p["done"] == 0               # arriving isn't building: it's counted tonight
    F.settle(w)
    assert p not in F.land(w)["projects"] and F.land(w)["buildings"][-1]["kind"] == "farm"


def test_gold_decides_which_version_you_get_and_upgrades_take_builders():
    city, w = _world(followers=15)
    city.treasury = 300
    p, _ = F.start(w, "tavern", 0)
    assert p["name"] == "a beer tent" and city.treasury == 300
    F.land(w)["projects"].clear()
    p, _ = F.start(w, "tavern", 260)
    assert p["name"] == "a beer hall" and p["tier"] == 2 and city.treasury == 50
    F.land(w)["projects"].clear()
    b = _build_now(w, "brewery", 0)
    up, why = F.invest(w, b, 60)
    assert up and up["upgrade_of"] == b["id"] and b["tier"] == 0       # not yet: the people have to do it up
    up["done"] = up["need"]
    F.finish(w, up)
    assert b["tier"] == 1 and b["name"] == "a brewery"


def test_a_tavern_without_beer_stands_idle():
    city, w = _world(followers=20)
    tav = _build_now(w, "tavern", 0)
    F.assign(w)
    assert not tav["running"]
    _build_now(w, "brewery", 0)
    F.assign(w)
    assert tav["running"]


def test_turning_up_at_the_same_work_makes_you_it():
    city, w = _world(followers=10)
    _build_now(w, "farm")
    for _ in range(F.STREAK):
        F.settle(w)
    assert set(F.land(w)["prof"].values()) == {"farmer"}
    assert city.citizens.label(city.citizens.index["u0"]) == "farmer"
    assert any("became a farmer" in x["text"] for x in city.living["impact"]["u0"])     # (their record says so)


def test_wants_and_happiness():
    city, w = _world(followers=20)
    assert F.wants(w)["food"]["met"] == 0
    low = F.happiness(w)
    _build_now(w, "farm")
    F.assign(w)
    assert F.wants(w)["food"]["met"] == 1 and F.happiness(w) > low


def test_your_own_gold_does_up_your_own_house():
    city, w = _world(followers=3)
    c = city.citizens
    c.wealth[c.index["u1"]] = 30
    name, cost = F.upgrade_house(w, "u1", -1)
    assert name == "a cottage" and cost == 25 and F.land(w)["houses"]["u1"]["tier"] == 1
    name, need = F.upgrade_house(w, "u1", -1)
    assert name is None and need > 5


def test_the_king_builds_what_people_want_and_not_twins_of_idle_buildings():
    city, w = _world(followers=12)
    city.treasury = 100
    assert FT.next_build(w) == "farm"                                  # food first
    farm = _build_now(w, "farm")
    farm["running"] = False
    F.land(w)["wants"] = F.wants(w)
    assert FT.next_build(w) != "farm"                                  # it's standing idle: it needs people, not a twin
    tool, args = FT.rule_king(w, w.agent("king"), FT.unlocked(w) | {"plan": None})
    assert tool in ("plan", "invest", "build", "rally", "walk", "do", "talk", "hold_court")


def test_the_kings_tools():
    city, w = _world(followers=25)
    city.treasury = 200
    me = w.agent("king")
    m = FT.plan(w, me, {"kind": "a tavern", "gold": 60})
    assert "tavern" in m["text"] and F.land(w)["projects"][-1]["kind"] == "tavern"
    m = FT.rally(w, me, {"building": "tavern", "text": "Beer by Friday!"})
    assert F.land(w)["rally"]["id"] == F.land(w)["projects"][-1]["id"]
    b = _build_now(w, "farm")
    m = FT.invest(w, me, {"building": b["name"], "gold": 40})
    assert m and "a farm" in m["text"]


def test_a_month_on_people_power():
    """The whole thing, end to end: people arrive, the king plans, the people build and run, gold comes in."""
    city, w = _world(followers=0)
    from city.mayor import RuleMayor
    for d in range(14):
        new = [f"p{d}_{k}" for k in range(4)]
        w.post(RuleMayor(), new, [])
    L = F.land(w)
    assert F.settled(city) >= 50
    assert len([b for b in L["buildings"] if b["kind"] != "keep"]) >= 4
    assert any(b.get("running") for b in L["buildings"]) and L["history"] and city.treasury >= 0
    assert L["happiness"] > 0.3
