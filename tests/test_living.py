"""The living world: clock, minds, war camp, people's own words, invented decrees."""
import json

from city import config, storyteller
from city.day import pack_for_today
from city.living import tools, warcamp
from city.living.agents import LLMBrain
from city.living.world import World
from city.mayor import RuleMayor
from city.model import City


def _world(n=60, seed=3):
    city = City(config.load(), seed=seed)
    w = World(city)
    w.post(RuleMayor(), [f"u{i}" for i in range(n)], [])
    return city, w


def test_clock_runs_between_posts_and_minds_act():
    city, w = _world()
    assert city.day == 1 and w.clock == w.next_post_clock() - 1440 + 0 or w.clock <= w.next_post_clock()
    before = len(city.living["moments"])
    w.post(RuleMayor(), [], [])
    assert city.day == 2
    assert len(city.living["moments"]) > before
    assert any(k.startswith("king.") for k in w.stats) and any(k.startswith("warlord.") for k in w.stats)


def test_raid_waits_for_its_first_post_and_feeds_the_camp():
    city, w = _world(80)
    city.day = 5   # past the warlord's grace period
    a = tools.raid(w, w.agent("warlord"), {"hold": city.wards[0]["name"], "warriors": "20"})
    assert a and warcamp.camp(city)["active_raid"]
    raid = next(e for e in city.events if e["id"] == "warlord_raid")
    assert not storyteller.can_respond(city, raid)
    city.pack = pack_for_today(city)
    from city.day import next_pack
    city.pack = next_pack(city)
    assert "FIGHT" in city.pack["commands"] and city.pack["commands"]["FIGHT"].startswith("event.help")
    fighters = [{"username": f"u{i}", "text": "FIGHT", "timestamp": i} for i in range(80)]
    uid = raid["uid"]
    w.post(RuleMayor(), [], fighters)
    assert raid in city.events and raid["progress"] == 0      # day one: the post about it just went up
    w.post(RuleMayor(), [], fighters)
    done = next(e for e in city.event_log if e.get("uid") == uid)
    assert done["result"] == "helped"
    w.tick()
    assert warcamp.camp(city)["raids_lost"] >= 1


def test_own_words_become_actions_and_stories():
    city, w = _world(40)
    comments = [{"username": "u1", "text": "I train with my sword all day in the yard", "timestamp": 1},
                {"username": "u2", "text": "I bake bread and sell it at the market", "timestamp": 2},
                {"username": "u3", "text": "WORK", "timestamp": 3}]
    r = w.post(RuleMayor(), [], comments)
    assert any(k.startswith("(own words)") for k in r["tallies"])
    c = city.citizens
    assert any("their sword" in s for s in c.story.get(c.index["u1"], []))
    assert int(c.counts["train"][c.index["u1"]]) >= 1


def test_king_invents_a_decree_that_survives_save_and_load(tmp_path):
    city, w = _world()
    for a in [a for a in city.events if a["id"].startswith("decree_")]:   # the rules king may have made one already
        storyteller.end(city, a["id"])
    city.living["last_decree_day"] = -9
    m = tools.decree(w, w.agent("king"), {"question": "Ban all bards?", "a_word": "BAN", "a_flavor": "harsh",
                                          "b_word": "SING", "b_flavor": "festival", "back": "BAN"})
    assert m and m["drama"] == 2
    eid = next(iter(city.living["custom_events"]))
    from city.day import next_pack
    assert {"BAN", "SING"} <= set(next_pack(city)["commands"])
    assert tools.decree(w, w.agent("king"), {"question": "Again?", "a_word": "X", "b_word": "Y"}) is None  # 1/day
    city.save(tmp_path)
    storyteller.CUSTOM.clear()
    storyteller.catalog(reload=True).pop(eid, None)
    city2 = City.load(tmp_path, config.load())
    World(city2)
    assert eid in storyteller.catalog()


def test_tools_unlock_as_the_world_changes():
    city, w = _world()
    assert "spy" not in tools.unlocked(w, "king")
    city.projects.append({"id": "watchtower", "name": "Watchtowers", "status": "done", "days_left": 0})
    w.tick()
    assert "spy" in city.living["unlocked"]["king"]
    assert any("New power" in m["text"] and "spies" in m["text"] for m in city.living["moments"])


class FakeLLM:
    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def json(self, system, user, schema, max_tokens=900, temperature=0.8):
        self.calls += 1
        return json.loads(self.answer) if isinstance(self.answer, str) else self.answer

    def chat(self, *a, **k):
        return "Your majesty, the bread is stale."


def test_llm_mind_uses_its_tool_and_falls_back_when_confused():
    city, w = _world()
    brain = LLMBrain(FakeLLM({"thought": "x", "tool": "proclaim", "args": {"text": "Kneel, peasants!"},
                              "new_goal": "be adored"}))
    tool, args = brain.choose(w, "king", tools.unlocked(w, "king"))
    assert tool == "proclaim" and args["text"] == "Kneel, peasants!"
    assert "be adored" in w.agent("king")["goals"]
    bad = LLMBrain(FakeLLM({"thought": "x", "tool": "nuke_the_north", "args": {}, "new_goal": ""}))
    tool, _ = bad.choose(w, "warlord", tools.unlocked(w, "warlord"))
    assert tool in tools.TOOLS["warlord"]


def test_chronicle_is_a_summary():
    city, w = _world(120)
    for _ in range(3):
        r = w.post(RuleMayor(), [], [])
    assert len(r["chronicle"]["top"]) <= 3
    assert len(r["moments"]) > len(r["chronicle"]["top"])
