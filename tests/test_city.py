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
