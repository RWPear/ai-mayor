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


def test_rebuilding_a_ruined_room_unlocks_a_tool(monkeypatch):
    from city.living import life, tools
    monkeypatch.setitem(life.SUCCESS, "small", 1.0)
    monkeypatch.setitem(life.SETBACK, "small", 0.0)
    city, w = _world()
    assert "spy" not in tools.unlocked(w, "king")
    king = w.agent("king")
    king["location"] = "spymaster_tower"
    m = tools.start_work(w, king, {"size": "small"})
    assert m and "rebuilding the spymaster's tower" in m["text"]
    for _ in range(2 * 48 + 2):
        w.tick()
    assert city.living["town"]["rooms"]["spymaster_tower"]
    assert "spy" in city.living["unlocked"]["king"]
    assert any("New power" in m["text"] for m in city.living["moments"])


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


# ---------------------------------------------------------------- the crowd acting on each other
def _crowd(world, moves):
    from city.living import intents
    return {r["user"]: r for r in intents.process(world, moves, None, 0)}


def test_steal_fight_gift_and_nobody_dies():
    city, w = _world(60)
    c = city.citizens
    c.wealth[c.index["u2"]] = 500
    before = float(c.wealth[c.index["u4"]])
    out = _crowd(w, {"u1": "I rob @u2 while he sleeps", "u3": "I challenge @u5 to a duel and try to kill him",
                     "u6": "I give @u4 50 gold for his trouble", "u7": "I beg the king for a job as his food taster"})
    assert out["u1"]["action"] == "steal" and out["u3"]["action"] == "attack" and out["u6"]["action"] == "gift"
    from city.living.intents import condition
    loser = "u5" if "WON" in out["u3"]["outcome"] else "u3"
    assert condition(city, loser)["state"] in ("wounded", "jailed")   # wounded (maybe also arrested), never dead
    assert all(cs["state"] in ("wounded", "jailed") for cs in city.living["conditions"].values())
    assert float(c.wealth[c.index["u4"]]) == before + 50
    assert any(k["kind"] == "petition" and k["who"] == "u7" for k in city.living["docket"])


def test_one_target_cant_be_dogpiled_and_the_jailed_sit_out():
    city, w = _world(60)
    out = _crowd(w, {f"u{i}": "I attack @u0" for i in range(1, 7)})
    blocked = [r for r in out.values() if "guards were already watching" in r["outcome"]]
    assert len(blocked) >= 4
    from city.living.intents import set_condition
    set_condition(city, "u20", "jailed", 2, "test")
    city.living["acted_today"] = []
    out = _crowd(w, {"u20": "I work at the forge all day"})
    assert "locked up" in out["u20"]["outcome"]


def test_the_king_judges_criminals_at_court():
    from city.living import tools
    city, w = _world(60)
    city.living["docket"] = []
    from city.living import life
    life.add_case(city, "crime", "u9", "@u9 was caught stealing from @u8")
    w.agent("king")["location"] = "throne_room"
    m = tools.hold_court(w, w.agent("king"), {"verdict": "jail", "words": "Off with his... freedom."})
    assert "JAIL" in m["text"] and "@u9" in m["text"]
    from city.living.intents import condition
    assert condition(city, "u9")["state"] == "jailed"


# ---------------------------------------------------------------- the king's own life
def test_nobody_hands_him_ideas():
    """He sees the mud. Whether he thinks of paving it is up to him."""
    from city.living.agents import perceive
    city, w = _world(60)
    w.agent("king")["location"] = "kings_street"
    view = perceive(w, "king")
    assert "mud" in view
    assert "pave" not in view.lower() and "stone road" not in view.lower() and "could improve" not in view.lower()


def test_his_projects_can_succeed_be_shoddy_or_fail():
    from city.living import life, tools
    results = []
    for seed in range(12):
        city, w = _world(60, seed=seed)
        city.treasury = 10 ** 7
        city.living["town"]["works"] = []
        king = w.agent("king")
        king["location"] = "kings_street"
        assert tools.start_work(w, king, {"name": "paving the street with stone", "size": "large", "purpose": "roads"})
        for _ in range(9 * 48):
            w.tick()
            done = [o for o in king["life"]["outcomes"] if o["name"] == "paving the street with stone"]
            if done:
                results.append(done[0]["result"])
                break
    assert set(results) >= {"success", "failed"} or set(results) >= {"success", "shoddy"}
    feats = city.living["town"]["features"]["kings_street"]
    assert any("paving the street with stone" in v for v in feats.values())


def test_his_own_ideas_are_bounded():
    from city.living import tools
    city, w = _world(60)
    city.treasury = 10 ** 6
    king = w.agent("king")
    king["location"] = "river"
    m = tools.start_work(w, king, {"name": "a giant golden duck statue", "size": "colossal", "purpose": "tax_raise"})
    work = city.living["town"]["works"][-1]
    assert work["size"] == "small" and work["flavor"] == "nothing"   # unknown size/purpose -> smallest, harmless
    assert m and "golden duck" in m["text"]
    assert tools.start_work(w, king, {"name": "another thing"}) is None   # one project per place at a time


def test_a_blank_king_grows_a_self():
    from city.living import life, tools
    from city.living.agents import LLMBrain
    city, w = _world(60)
    king = w.agent("king")
    assert not life.who_am_i(king)                                   # nobody in particular yet
    for _ in range(3):
        tools.pastime(w, king, {"activity": "Whittling little boats", "title": "Boat", "description": "Lopsided."})
    life.reflect(w, king, None)
    assert "whittling little boats" in king["self"]["passions"]
    mind = FakeLLM({"traits": ["curious", "stubborn"], "likes": ["the river"], "dislikes": ["mud"],
                    "passions": ["whittling"], "wants": ["a bridge over the river"], "fears": ["the warlord"],
                    "becoming": "a king who builds things with his own hands"})
    w.city.living["budget"]["left"] = 99
    life.reflect(w, king, mind)
    assert king["self"]["wants"] == ["a bridge over the river"] and "builds" in king["self"]["becoming"]
    grab = {}

    class Spy(FakeLLM):
        def json(self, system, user, schema, **k):
            grab["system"] = system
            return super().json(system, user, schema)
    LLMBrain(Spy({"thought": "x", "tool": "rest", "args": {}, "new_goal": ""})).choose(w, "king", tools.unlocked(w, "king"))
    assert "Nobody has told you who to be" in grab["system"] and "builds things" in grab["system"]
    assert "vain" not in grab["system"].lower() and "flaw" not in grab["system"].lower()


# ---------------------------------------------------------------- one budget, two kinds of day
class CrowdLLM:
    def json(self, system, user, schema, max_tokens=900, temperature=0.8):
        hs = [line.split(" ")[0].lstrip("@").rstrip(":") for line in user.splitlines() if line.startswith("@")]
        if "action" in schema["properties"]["results"]["items"]["properties"]:
            return {"results": [{"handle": h, "action": "work", "target": ""} for h in hs]}
        return {"results": [{"handle": h, "outcome": f"@{h} worked hard.", "drama": 0} for h in hs]}


def test_a_viral_day_hands_the_gpu_to_the_crowd():
    city = City(config.load(), seed=5)
    city.cfg["gpu_calls_per_hour"] = 24
    w = World(city, crowd_llm=CrowdLLM())
    w.post(RuleMayor(), [f"u{i}" for i in range(2000)], [])
    quiet_king = sum(v for k, v in w.stats.items() if k.startswith("king."))
    w.stats.clear()
    words = [{"username": f"u{i}", "text": "I work all day at the mill for my family", "timestamp": i} for i in range(2000)]
    w.post(RuleMayor(), [], words)
    busy_king = sum(v for k, v in w.stats.items() if k.startswith("king."))
    assert w.stats.get("pace.viral", 0) > 0 and w.stats["crowd_moves"] >= 1900
    assert busy_king < quiet_king                                   # the king steps back when the crowd shows up
