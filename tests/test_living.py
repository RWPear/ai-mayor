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
    assert any(k.startswith("king.") for k in w.stats)
    assert not any(k.startswith("warlord.") for k in w.stats)        # he hasn't arrived yet


def test_the_warlord_arrives_after_a_few_days():
    city, w = _world()
    from city.living import warcamp
    for _ in range(5):
        w.post(RuleMayor(), [], [])
    texts = [m["text"] for m in city.living["moments"]]
    assert any("shepherd" in t for t in texts) and any("smoke rose over the northern hills" in t.lower() for t in texts)
    assert warcamp.camp(city)["arrived"] == 3
    assert any(k.startswith("warlord.") for k in w.stats)


def test_raid_waits_for_its_first_post_and_feeds_the_camp():
    city, w = _world(80)
    city.day = 5   # past the warlord's arrival
    city.living["warcamp"]["arrived"] = 3
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


class SeqLLM(FakeLLM):
    """Answers in order (for multi-step decisions)."""
    def __init__(self, answers):
        self.answers, self.calls, self.prompts = list(answers), 0, []

    def json(self, system, user, schema, max_tokens=900, temperature=0.8):
        self.prompts.append((system, user))
        self.calls += 1
        return self.answers.pop(0)


def test_the_king_decides_in_two_steps():
    city, w = _world()
    w.city.living["budget"]["left"] = 99
    king = w.agent("king")
    king["location"] = "kitchens"
    king["life"]["needs"]["hunger"] = 0.1
    mind = SeqLLM([{"thought": "My stomach growls.", "focus": "myself", "intention": "eat something warm",
                    "new_goal": "be adored"},
                   {"tool": "do", "args": {"what": "eat a bowl of the cooks' stew by the hearth"}}])
    tool, args = LLMBrain(mind).choose(w, "king", tools.available(w, "king"))
    assert tool == "do" and "stew" in args["what"]
    first, second = mind.prompts
    assert "- myself:" in first[0] and "- court:" not in first[0]         # no docket -> no court choice
    assert "stew pot" in second[1]                                        # step 2 sees what the kitchens offer
    assert "garrison" not in second[0]                                    # ...and only the tools for that focus
    assert "be adored" in king["goals"] and w.stats["focus.myself"] == 1


def test_llm_mind_falls_back_when_confused():
    city, w = _world()
    bad = LLMBrain(FakeLLM({"thought": "x", "tool": "nuke_the_north", "args": {}, "new_goal": ""}))
    tool, _ = bad.choose(w, "warlord", tools.unlocked(w, "warlord") or {"hunt": tools.TOOLS["warlord"]["hunt"][:3]})
    assert tool in tools.TOOLS["warlord"]
    w.city.living["budget"]["left"] = 99
    tool, _ = LLMBrain(FakeLLM({"focus": "flying"})).choose(w, "king", tools.available(w, "king"))
    assert tool in tools.TOOLS["king"] and w.stats["fallbacks"] >= 1


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
        tools.do(w, king, {"what": "whittle little boats by the river"})
    life.reflect(w, king, None)
    assert "whittle little boats" in king["self"]["passions"]
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
    LLMBrain(Spy({"thought": "x", "tool": "walk", "args": {}, "new_goal": ""})).choose(w, "king", tools.unlocked(w, "king"))
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


# ---------------------------------------------------------------- events nobody wrote
def test_the_director_invents_a_consequence_capped_by_the_season():
    from city.living import director
    city, w = _world(60)
    story = {"happen": True, "title": "The king's new dam burst and drowned half the sheep",
             "kind": "crisis", "where": city.wards[0]["name"], "days": 2, "help_words": ["SALVAGE", "status"],
             "hinder_words": ["LOOT"], "difficulty": "hard",
             "at_start": {"text": "", "consequence": "food_loss", "size": 3},
             "if_helped": {"text": "The town saved what it could.", "consequence": "mood_gain", "size": 1},
             "if_not": {"text": "Emberfall is starving.", "consequence": "food_loss", "size": 3},
             "choices": [], "king_options": [{"label": "Buy grain", "text": "The king bought grain.", "cost": "large",
                                              "consequence": "food_gain", "size": 2, "helps": True}]}
    w.city.living["budget"]["left"] = 99
    a = director.consider(w, FakeLLM(story))
    assert a and "dam burst" in a["title"]
    ev = storyteller.catalog()[a["id"]]
    assert set(ev["commands"]) == {"SALVAGE", "LOOT"}          # reserved words (STATUS) are dropped
    assert ev["on_timeout"]["service.food"] == -0.04            # tier 1 on day 1: a size-3 disaster is capped at 1
    assert ev["options"][0]["effects"]["progress"] == 0.3
    assert any("New event" in n["text"] for n in city.living["notifications"])
    assert director.consider(w, FakeLLM({**story, "happen": False})) is None


def test_with_a_director_the_hand_written_list_stays_quiet():
    city = City(config.load(), seed=4)
    w = World(city, director_llm=FakeLLM({"happen": False}))
    assert city.living["director"] and storyteller.maybe_start_event(city) is None


def test_he_can_do_anything_and_the_world_answers():
    from city.living import tools
    city, w = _world(60)
    king = w.agent("king")
    w.voice_llm = FakeLLM({"outcome": "The king ran three laps of the walls and threw up behind the chapel.",
                           "activity": "running", "minutes": 300, "hunger": -0.9, "energy": -0.4, "company": 0,
                           "fun": 0.2, "learned": "", "found": "a muddy coin", "made": "", "drama": 2})
    w.city.living["budget"]["left"] = 99
    before = king["life"]["needs"]["energy"]
    m = tools.do(w, king, {"what": "go for a long run around the town"})
    assert "threw up" in m["text"] and m["drama"] == 2
    assert king["life"]["needs"]["energy"] < before
    assert any(g["item"] == "a muddy coin" for g in king["life"]["inventory"])
    assert king["next_act"] == w.clock + 240                    # the world's numbers are clamped (300 -> 240)


# ---------------------------------------------------------------- houses, walls, fire
def test_newcomers_get_houses_and_walls_protect_them():
    from city.living import town as T
    city, w = _world(40)
    c = city.citizens
    assert int((c.walled == 1).sum()) == 0                      # no walls at the start
    T.build_walls(w, "success")
    assert int((c.walled == 1).sum()) == 40 and city.living["town"]["walls"]["capacity"] >= 60
    w.post(RuleMayor(), [f"u{i}" for i in range(40)] + [f"n{i}" for i in range(80)], [])
    cap = city.living["town"]["walls"]["capacity"]
    assert int((c.walled == 1).sum()) == cap and int((c.walled == 0).sum()) == 120 - cap   # the rest live outside
    hit = T.burn_houses(w, int(c.ward[c.index["n79"]]), 30)
    assert hit and all(c.walled[c.index[h]] == 0 for h in hit)  # only houses outside the walls burn


def test_old_posts_stay_live():
    city, w = _world(30)
    w.post(RuleMayor(), [], [])
    old_day = city.day                                         # a post whose words were WORK/TRADE/...
    city.living["posts"][str(old_day)] = {"commands": {"WORK": "work", "FIGHT": "event.help:gone_event"}, "event": None}
    r = w.post(RuleMayor(), [], [{"username": "u1", "text": "WORK", "timestamp": 1, "post": old_day},
                                 {"username": "u2", "text": "FIGHT", "timestamp": 2, "post": old_day}])
    assert r["tallies"].get("WORK", 0) >= 1
    assert any(x["username"] == "u2" and "over" in x["reply"] for x in r["status_replies"])


# ---------------------------------------------------------------- lessons from the first real run
def test_no_talking_in_circles():
    from city.living import tools
    city, w = _world(60)
    king = w.agent("king")
    outs = [tools.talk(w, king, {"person": "@u1", "text": f"Question {k}?"}) for k in range(4)]
    assert "excused themselves" in outs[2]["text"] and "excused themselves" in outs[3]["text"]


def test_the_menu_only_offers_what_makes_sense():
    from city.living import tools
    city, w = _world(80)
    city.day = 6
    city.living["warcamp"]["arrived"] = 3
    assert "raid" in tools.available(w, "warlord")
    tools.raid(w, w.agent("warlord"), {"hold": city.wards[0]["name"], "warriors": "20"})
    assert "raid" not in tools.available(w, "warlord")            # one raid at a time - don't even offer it
    w.agent("warlord").setdefault("last_used", {})["taunt"] = w.clock
    assert "taunt" not in tools.available(w, "warlord")           # no letter spam
    w.agent("king")["location"] = "kings_street"
    assert "hold_court" not in tools.available(w, "king") and "work_on" not in tools.available(w, "king")


def test_a_meal_fills_him_up_even_if_the_narrator_is_stingy():
    from city.living import tools
    city, w = _world(60)
    king = w.agent("king")
    king["life"]["needs"]["hunger"] = 0.1
    w.voice_llm = FakeLLM({"outcome": "The king ate a bowl of stew.", "activity": "eating stew", "minutes": 30,
                           "hunger": 0.05, "energy": 0, "company": 0, "fun": 0, "learned": "", "found": "",
                           "made": "", "drama": 0})
    w.city.living["budget"]["left"] = 99
    tools.do(w, king, {"what": "eat some stew"})
    assert king["life"]["needs"]["hunger"] >= 0.6


def test_ignored_petitioners_give_up():
    from city.living import life
    city, w = _world(60)
    city.living["docket"] = []
    life.add_case(city, "petition", "u3", "@u3 wants a new roof")
    before = float(city.citizens.loyalty[city.citizens.index["u3"]])
    city.day += 2
    gone = life.age_docket(w)
    assert gone and not city.living["docket"]
    assert float(city.citizens.loyalty[city.citizens.index["u3"]]) < before


# ---------------------------------------------------------------- followers hear what they did
def test_send_the_king_a_gift_and_hear_when_he_uses_it():
    from city.living import intents, tools
    city, w = _world(30)
    w.note_comment({"username": "u4", "id": "c123", "post": 1})
    intents.process(w, {"u4": "I send the king a lute so he can learn to play"}, None, 0)
    inv = w.agent("king")["life"]["inventory"]
    assert any(g["item"].startswith("lute") and g["from"] == "u4" for g in inv)
    tools.do(w, w.agent("king"), {"what": "try to play the lute in the garden"})
    out = [x for x in city.living["outbox"] if x["to"] == "u4"]
    assert any(x["kind"] == "your_move" for x in out) and any(x["kind"] == "gift_used" for x in out)
    assert out[-1]["comment_id"] == "c123"                     # replies go to their comment
    assert city.living["impact"]["u4"][-1]["text"].startswith("the king used their gift")


def test_the_king_takes_up_a_followers_idea():
    from city.living import intents, tools
    city, w = _world(30)
    city.treasury = 10 ** 6
    w.note_comment({"username": "u5", "id": "c9", "post": 1})
    intents.process(w, {"u5": "I suggest the king builds a bridge over the river"}, None, 0)
    king = w.agent("king")
    king["location"] = "river"
    tools.start_work(w, king, {"name": "a stone bridge across the river", "size": "large"})
    assert any(x["kind"] == "idea_used" and x["to"] == "u5" for x in city.living["outbox"])
    r = w.post(RuleMayor(), [], [])
    from city import report
    assert any(t.startswith("@u5 the king took up their idea") for t in report.shoutouts(r))
    assert "Your doing today" in report.caption(r)
    card = report.status_card(city, city.citizens.index["u5"])
    assert "Your mark on Emberfall" in card


def test_no_reply_to_people_who_never_commented():
    city, w = _world(30)
    w.reply("u7", "something happened", "done_to_you", credit="was there")
    assert not any(x["to"] == "u7" for x in city.living.get("outbox", []))   # nothing to reply to
    assert city.living["impact"]["u7"]                                        # but it's on their record
