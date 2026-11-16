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
    comments = [{"username": "a", "text": "PROTEST!", "timestamp": 1},
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
    storyteller.schedule(city, "heatwave", city.day + 2)
    run_day(city, RuleMayor(), [], [])                   # end of this day -> starts for tomorrow's post
    assert any(e["id"] == "heatwave" for e in city.events)
    assert "COOL" in city.pack["commands"]


def test_follow_up_chain():
    from city import storyteller
    city = _city_with()
    a = storyteller.start(city, "rival_arrives")
    a["days_left"] = 1                                   # make it time out today
    run_day(city, RuleMayor(), [], [])
    assert any(s["event"] == "rival_poaching" for s in city.scheduled)


def test_plan_beats_and_conditions(tmp_path):
    from city import plan
    f = tmp_path / "plan.yaml"
    f.write_text("storyteller: off\nbeats:\n"
                 "  - {day: 1, event: grand_opening}\n"
                 "  - {day: 3, if: 'pop > 100000', event: tech_hq, else: {event: heatwave}}\n")
    city = City(config.load())
    plan.attach(city, f)
    from city.day import pack_for_today
    p = pack_for_today(city)
    assert "CELEBRATE" in p["commands"]
    for _ in range(2):
        run_day(city, RuleMayor(), [f"u{i}" for i in range(50)], [])
    assert any(e["id"] == "heatwave" for e in city.events)   # condition false -> else branch


def test_placeholders_use_real_handles():
    from city import storyteller
    city = _city_with()
    city.wards[0]["councilor"] = 0
    a = storyteller.start(city, "councilor_scandal", city.wards[0]["name"])
    assert a["title"].startswith("Leaked texts: @" + city.citizens.handles[0])


def test_content_checks_clean():
    from city.checker import check_all
    problems, _ = check_all("seasons")
    assert problems == []
