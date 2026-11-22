"""Quick checks: python -m pytest -q"""
import json
import zipfile

from city import config
from city.day import default_pack, run_day
from city.mayor import RuleMayor
from city.model import City
from city.packs import parse
from city.sources.instagram_export import read_followers


def test_parse_latest_command_wins_and_status():
    pack = default_pack()
    comments = [{"username": "a", "text": "GRUMBLE!", "timestamp": 1},
                {"username": "a", "text": "ok fine, work", "timestamp": 2},
                {"username": "b", "text": "STATUS please", "timestamp": 3},
                {"username": "c", "text": "move in", "timestamp": 4},
                {"username": "d", "text": "great video", "timestamp": 5}]
    actions, status, joins = parse(comments, pack)
    assert actions == {"a": "WORK"}
    assert status == {"b"}
    assert joins == {"a", "c"}


def test_followers_export_shapes(tmp_path):
    data = [{"string_list_data": [{"href": "https://www.instagram.com/one", "value": "one"}]},
            {"title": "two", "string_list_data": [{"href": "https://www.instagram.com/_u/two"}]}]
    f = tmp_path / "followers_1.json"
    f.write_text(json.dumps(data))
    z = tmp_path / "export.zip"
    with zipfile.ZipFile(z, "w") as zz:
        zz.write(f, "connections/followers_and_following/followers_1.json")
    assert read_followers(f) == ["one", "two"]
    assert read_followers(z) == ["one", "two"]


def test_leaving_sticks_until_they_comment(tmp_path):
    city = City(config.load())
    m = RuleMayor()
    run_day(city, m, ["x", "y"], [])
    pack = {"post": "t", "event": None, "commands": {"LEAVE": "leave", "WORK": "work"}}
    run_day(city, m, ["x", "y"], [{"username": "x", "text": "LEAVE", "timestamp": 1}], pack)
    assert city.population() == 1
    run_day(city, m, ["x", "y"], [])                     # still following: stays gone
    assert city.population() == 1
    run_day(city, m, ["x", "y"], [{"username": "x", "text": "WORK", "timestamp": 1}], pack)
    assert city.population() == 2                        # commenting brings them back


def test_save_load_roundtrip(tmp_path):
    city = City(config.load())
    m = RuleMayor()
    for d in range(3):
        run_day(city, m, [f"u{i}" for i in range(50 + d * 10)], [])
    city.save(tmp_path)
    again = City.load(tmp_path, config.load())
    assert again.population() == city.population() and again.day == 3
    run_day(again, m, [f"u{i}" for i in range(80)], [])
    assert again.day == 4


def test_scale_100k_one_day():
    city = City(config.load())
    run_day(city, RuleMayor(), [f"user{i}" for i in range(100_000)], [])
    assert city.population() == 100_000
    assert len(city.wards) >= 200


def _city_with(n=60):
    city = City(config.load())
    run_day(city, RuleMayor(), [f"u{i}" for i in range(n)], [])
    return city


def test_schedule_starts_event_for_that_days_post():
    from city import storyteller
    city = _city_with()
    storyteller.schedule(city, "bandits", city.day + 2)
    run_day(city, RuleMayor(), [], [])                   # end of this day -> starts for tomorrow's post
    assert any(e["id"] == "bandits" for e in city.events)
    assert "HUNT" in city.pack["commands"]


def test_follow_up_chain():
    from city import storyteller
    city = _city_with()
    a = storyteller.start(city, "barbarian_scouts")
    a["days_left"] = 1                                   # make it time out today
    run_day(city, RuleMayor(), [], [])
    assert any(e["id"] == "barbarian_raid" for e in city.events) or \
        any(s["event"] == "barbarian_raid" for s in city.scheduled)


def test_plan_beats_and_conditions(tmp_path):
    from city import plan
    f = tmp_path / "plan.yaml"
    f.write_text("storyteller: off\nbeats:\n"
                 "  - {day: 1, event: coronation}\n"
                 "  - {day: 3, if: 'pop > 100000', event: tournament, else: {event: comet}}\n")
    city = City(config.load())
    plan.attach(city, f)
    from city.day import pack_for_today
    p = pack_for_today(city)
    assert "KNEEL" in p["commands"]
    for _ in range(2):
        run_day(city, RuleMayor(), [f"u{i}" for i in range(50)], [])
    assert any(e["id"] == "comet" for e in city.events)   # condition false -> else branch


def test_placeholders_use_real_handles():
    from city import storyteller
    city = _city_with()
    city.wards[0]["councilor"] = 0
    a = storyteller.start(city, "court_treason", city.wards[0]["name"])
    assert a["title"].startswith("Treason! Lord @" + city.citizens.handles[0])


def test_content_checks_clean():
    from city.checker import check_all
    problems, _ = check_all("seasons")
    assert problems == []


def test_become_job_changes_trade_and_faction():
    city = _city_with()
    run_day(city, RuleMayor(), [], [{"username": "u1", "text": "become a blacksmith!", "timestamp": 1},
                                    {"username": "u2", "text": "BECOME SOLDIERS", "timestamp": 2},
                                    {"username": "u3", "text": "become king", "timestamp": 3}])
    c = city.citizens
    from city.roles import JOB_NAMES
    assert JOB_NAMES[int(c.job[c.index["u1"]])] == "blacksmith"
    assert JOB_NAMES[int(c.job[c.index["u2"]])] == "soldier"
    assert "Peasant" in report_card(city, "u3") or "Freeman" in report_card(city, "u3")


def report_card(city, user):
    from city.report import status_card
    return status_card(city, city.citizens.index[user])


def test_king_cannot_answer_before_the_crowd():
    """Events started tonight can't be settled by the king tonight - the post comes first."""
    from city import storyteller
    city = _city_with()
    storyteller.schedule(city, "bandits", city.day + 1)
    run_day(city, RuleMayor(), [], [])
    a = next(e for e in city.events if e["id"] == "bandits")
    assert a.get("option") is None and not storyteller.can_respond(city, a)
    assert storyteller.choose_option(city, a, "send_guards") is None
    run_day(city, RuleMayor(), [], [])                   # after one post, the king may respond
    assert storyteller.can_respond(city, a) or a.get("option") or a not in city.events


def test_decree_vote_crowd_wins_and_king_can_overrule():
    from city import storyteller
    from city.packs import from_event
    for side, expect in ((None, "GRANARY"), ("back_walls", "WALLS")):
        city = _city_with()
        storyteller.start(city, "first_decree")
        city.pack = from_event({**storyteller.catalog()["first_decree"], "id": "first_decree"})
        assert set(city.pack["commands"]) == {"WALLS", "GRANARY"}
        votes = [{"username": f"u{i}", "text": "GRANARY" if i < 40 else "WALLS", "timestamp": i} for i in range(50)]
        run_day(city, _Fixed(side), [], votes)
        before = city.approval()
        run_day(city, _Fixed(side), [], votes)
        done = next(e for e in city.event_log if e["id"] == "first_decree")
        assert done["result"] == expect
        if side:
            assert "overruled" in done["outcome"] and city.approval() < before


class _Fixed(RuleMayor):
    """Rules king that backs a fixed side on the decree (or nothing)."""
    def __init__(self, option):
        self.option = option

    def decide(self, city):
        d = super().decide(city)
        d["event_choices"] = [{"event_id": "first_decree", "option_id": self.option, "why": ""}] if self.option else []
        return d


def test_barbarian_war_chain_runs_itself():
    from city import storyteller
    city = _city_with(120)
    storyteller.start(city, "barbarian_scouts")
    seen = set()
    for _ in range(9):
        run_day(city, RuleMayor(), [], [])
        seen |= {e["id"] for e in city.events} | {e["id"] for e in city.event_log}
    assert {"barbarian_scouts", "barbarian_raid", "barbarian_horde"} <= seen


def test_milestone_silent_when_story_already_introduced_it():
    from city import storyteller
    city = _city_with(10)
    storyteller.start(city, "varn_envoy")
    r = run_day(city, RuleMayor(), [f"x{i}" for i in range(320)], [])
    assert "rival" in city.milestones
    assert not any("Rival Crown" in n for n in r["sim"]["notes"])   # unlocked quietly: the story already did it
    city2 = _city_with(10)
    r2 = run_day(city2, RuleMayor(), [f"x{i}" for i in range(320)], [])
    assert any("Rival Crown" in n for n in r2["sim"]["notes"])      # ...but announced when it didn't


def test_deposed_lord_is_not_named_again():
    from city import effects
    city = _city_with(30)
    city.milestones.append("court")
    city.day = 7
    run_day(city, RuleMayor(), [], [])                   # day 8? lords are named on days 1, 8, 15...
    while city.day % 7 != 0:
        run_day(city, RuleMayor(), [], [])
    run_day(city, RuleMayor(), [], [])                   # a naming day
    lord = city.wards[0]["councilor"]
    assert lord is not None
    effects.apply(city, {"depose.hold": 1}, 0)
    for _ in range(7):
        run_day(city, RuleMayor(), [], [])
    assert city.wards[0]["councilor"] not in (None, lord)


def test_overruled_vote_shows_the_score():
    from city import storyteller
    from city.packs import from_event
    city = _city_with()
    storyteller.start(city, "first_decree")
    city.pack = from_event({**storyteller.catalog()["first_decree"], "id": "first_decree"})
    votes = [{"username": f"u{i}", "text": "GRANARY" if i < 40 else "WALLS", "timestamp": i} for i in range(50)]
    run_day(city, _Fixed("back_walls"), [], votes)
    run_day(city, _Fixed("back_walls"), [], votes)
    done = next(e for e in city.event_log if e["id"] == "first_decree")
    assert "GRANARY 80 to WALLS 20" in done["outcome"]
