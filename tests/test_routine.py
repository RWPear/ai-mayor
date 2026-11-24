"""Everyone's day, and the little things that happen in it (city/living/routine.py)."""
import pytest

from city.play import Play
from city import demo
from city.living import routine, scene


@pytest.fixture(scope="module")
def town(tmp_path_factory):
    p = Play(tmp_path_factory.mktemp("demo") / "s", fresh=True, seed=3)
    return demo.build(p, people=30, days=3)


def test_everyone_keeps_the_same_simple_day(town):
    w, c = town.world, town.city.citizens
    i = c.index["mara"]
    day = routine.schedule(w, i)
    assert [b["what"] for b in day] == ["up", "breakfast", "work", "lunch", "work", "free", "supper", "sleep"]
    assert -15 <= day[0]["from"] - 6 * 60 <= 15 and day[-1]["to"] - day[0]["from"] == 24 * 60
    assert all(a["to"] == b["from"] for a, b in zip(day, day[1:]))
    assert routine.doing(w, i, 3 * 60)["what"] == "sleep"
    assert routine.doing(w, i, day[3]["from"] + 5)["what"] == "lunch"


def test_people_bump_into_each_other_all_day_and_it_adds_up(town):
    lv = town.city.living
    enc = lv["encounters"]
    assert len(enc) > 100                                     # three days of thirty people: lots of little things
    assert {e["what"] for e in enc} >= {"breakfast", "work", "supper"}
    assert all(e["a"] != e["b"] for e in enc)
    stages = {v.get("stage") for v in routine.bonds(town.world).values()}
    assert "friends" in stages                                # ...and some of them became friends
    told = [m for m in lv["moments"] if "friends" in m["text"] and len(m["handles"]) == 2]
    assert told and all(m["public"] for m in told)


def test_the_bard_hears_about_their_people(town):
    w = town.world
    friend = next(k for k, v in routine.bonds(w).items() if v.get("stage") == "friends")
    a, b = friend.split("|")
    line = routine.people_line(w, a)
    assert "@" + b in line and "friends with" in line


def test_a_feud_comes_to_blows_once_and_not_every_day(town):
    w = town.world
    for _ in range(12):
        routine.meet(w, "tob", "wes", "lunch", "commons")
    bd = routine.bond(w, "tob", "wes")
    bd["s"] = -9
    bd["stage"] = "rivals"
    w.city.living.pop("stories_told", None)
    assert routine._story(w, "tob", "wes", bd, "Tob blamed Wes for a squashed toe", "hill")
    assert bd["stage"] == "enemies" and bd["s"] == -4
    bd["s"] = -12
    assert routine._story(w, "tob", "wes", bd, "again", "hill") is None


def test_the_3d_view_gets_everyones_day_and_the_encounters(town):
    s = scene.export(town.world)
    assert s["routine"]["commons"] and len(s["routine"]["day"]) == 8
    st = s["actors"]["settlers"]
    assert len(st) == 30 and all(len(x["schedule"]) == 8 and x["schedule"][0]["pos"] for x in st)
    assert s["encounters"] and {"t", "a", "b", "label", "text", "anim"} <= set(s["encounters"][0])
    feed = town.feed()["log"]
    assert any(m.get("small") for m in feed)                  # the little things are in "What happened" too
