"""The frontier start: one man, a leaky shack, and everything built by hand."""
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
    for i in range(followers):
        w.note_comment({"username": f"u{i}", "id": f"c{i}", "post": city.day})
    return city, w


def _days(w, n, followers=None, comments=None):
    from city.mayor import RuleMayor
    out = []
    for _ in range(n):
        out.append(w.post(RuleMayor(), followers or [], comments or []))
    return out


def test_he_starts_with_nothing_and_people_are_on_the_road():
    city, w = _world()
    L = F.land(w)
    assert w.frontier and w.agent("king")["location"] in F.places(w)
    assert city.treasury <= 20 and F.capacity(city) == 0 and not L["crowned"]
    assert F.settled(city) == 0 and F.on_road(city) == 5              # followers are travelling, not living there
    assert {"shack", "woods", "river", "hill", "field", "road"} <= set(F.places(w))
    assert "throne_room" not in F.places(w)


def test_gathering_is_where_the_stuff_is():
    city, w = _world()
    me = w.agent("king")
    assert FT.gather(w, me, {"material": "stone"}) is None and "rocky hill" in me["nudge"]
    me["location"] = "woods"
    FT.gather(w, me, {"material": "wood", "how": "dragging deadfall"})
    assert F.land(w)["stock"]["wood"] >= 1


def test_ideas_are_priced_once_by_what_they_are():
    city, w = _world()
    cottage = F.design(w, "a little cottage with a thatched roof")
    assert cottage["kind"] == "housing" and 2 <= cottage["capacity"] <= 4 and "thatching" in cottage["know"]
    flats = F.design(w, "a tall apartment building of stone and timber")
    assert flats["scale"] == "huge" and flats["capacity"] >= 60 and "multi-storey building" in flats["know"]
    assert sum(flats["needs"].values()) > 10 * sum(cottage["needs"].values())
    assert flats["hours"] / flats["capacity"] < cottage["hours"] / cottage["capacity"]   # bigger is more efficient
    assert F.design(w, "a storehouse for food")["kind"] == "storage"
    assert F.design(w, "a row of timber houses")["scale"] == "large"
    assert not F.design(w, "a flying castle")["possible"]
    assert F.design(w, "a little cottage with a thatched roof") is cottage                # decided once


def test_the_model_says_what_it_is_and_the_code_says_what_it_costs():
    class Voice:
        def json(self, system, user, schema, **kw):
            return {"possible": True, "why_not": "", "name": "a mansion for everyone", "kind": "housing",
                    "scale": "small", "material": "wood", "capacity": 9999, "techniques": [], "boosts": "",
                    "look": "a long low house"}

        def chat(self, *a, **k):
            return "ok"

    city, w = _world(voice=Voice())
    d = F.design(w, "a mansion for literally everyone")
    assert d["capacity"] <= 4                                  # a small building can't house 9999 people


def test_building_uses_materials_and_teaches():
    city, w = _world()
    me = w.agent("king")
    L = F.land(w)
    me["location"] = "field"
    FT.plan(w, me, {"idea": "a small cottage with a thatched roof"})
    p = next(x for x in L["projects"] if "cottage" in x["name"])
    for m in p["needs"]:
        L["stock"][m] = 0
    assert FT.build(w, me, {"project": p["name"]}) is not None and p["progress"] == 0   # nothing to build with
    for m, n in p["needs"].items():
        L["stock"][m] = n + 1
    city.rng.random = lambda: 0.01                                          # it goes well
    for k in range(20):
        if p.get("done"):
            break
        me["life"]["needs"]["energy"] = 1.0
        p["hours_day"] = k                                  # a new day each time (one man can only do so much a day)
        FT.build(w, me, {"project": p["name"]})
    assert p.get("done") and F.capacity(city) >= 2 and "thatching" in L["know"]
    assert L["stock"]["wood"] < 5


def test_arrival_day_beds_then_tents_then_moving_in():
    city, w = _world(followers=6)
    L = F.land(w)
    L["buildings"].append({"id": "bx", "name": "a cottage", "kind": "housing", "scale": "small", "capacity": 2,
                           "place": "field", "quality": "good", "day": 1})
    L["next_arrival"] = city.day + 1
    F.arrive(w)
    c = city.citizens
    assert F.settled(city) == 6 and F.housed(city) == 2 and F.tents(city) == 4 and "camp" in F.places(w)
    texts = [x["text"] for x in city.living["outbox"] if x["kind"] == "arrived"]
    assert sum("tent" in t for t in texts) == 4
    L["buildings"].append({"id": "by", "name": "a longhouse", "kind": "housing", "scale": "medium", "capacity": 8,
                           "place": "field", "quality": "good", "day": 2})
    assert F.rehouse(w) == 4 and F.tents(city) == 0
    assert any(x["kind"] == "moved_in" for x in city.living["outbox"])
    assert int((c.walled[c.active()] >= 0).sum()) == 6


def test_word_comes_three_days_before():
    city, w = _world(followers=8)
    L = F.land(w)
    L["next_arrival"] = city.day + 1 + 3
    F.forecast(w)
    assert L["forecast"] and L["forecast"]["est"] >= 1
    assert any("on the road" in m["text"] for m in city.living["moments"][-3:])


def test_settlers_work_on_his_projects():
    city, w = _world(followers=10)
    L = F.land(w)
    L["next_arrival"] = city.day + 1
    F.arrive(w)
    me = w.agent("king")
    me["location"] = "field"
    FT.plan(w, me, {"idea": "a small cottage with a thatched roof"})
    p = L["projects"][0]
    for m, n in p["needs"].items():
        L["stock"][m] = n
    before = p["progress"]
    lazy = F._hours_today(w)[0]
    L["workers_today"] = [f"u{i}" for i in range(10)]
    keen = F._hours_today(w)[0]
    assert keen > 2 * lazy                                     # commenting WORK really matters
    F.labor(w, 1.0)
    assert p["progress"] > before or p.get("done")


def test_hungry_nights_drive_people_away():
    city, w = _world(followers=10)
    L = F.land(w)
    L["next_arrival"] = city.day + 1
    F.arrive(w)
    for _ in range(3):
        L["stock"]["food"] = 0
        F.meals(w)
    assert F.settled(city) < 10


def test_nobody_calls_him_king_until_he_is_crowned():
    city, w = _world()
    assert F.title(city, "The king walked to the river.") == "Aldric walked to the river."
    F.land(w)["crowned"] = True
    assert F.title(city, "The king walked to the river.") == "The king walked to the river."


def test_the_settlers_vote_on_a_crown():
    city, w = _world(followers=12)
    L = F.land(w)
    L["next_arrival"] = city.day + 1
    F.arrive(w)
    F.after_post(w)
    assert any(a["id"].startswith("crowning_") for a in city.events)
    a = next(a for a in city.events if a["id"].startswith("crowning_"))
    city.events.remove(a)
    city.event_log.append({**a, "winner": "CROWN", "crowd": "CROWN"})
    F.after_post(w)
    assert L["crowned"]


def test_people_on_the_road_can_send_things_and_write():
    from city.living import intents
    city, w = _world()
    out = intents.process(w, {"u1": "I send the king a sharp iron axe", "u2": "you should build near the river",
                              "u3": "I punch @u4"}, None, 0)
    replies = {x["to"]: x["text"] for x in city.living["outbox"]}
    assert any("axe" in t["name"] for t in F.land(w)["tools"])
    assert "letter" in replies["u2"] and "road" in replies["u3"].lower()
    assert len(out) == 3


def test_skarn_waits_until_there_is_something_to_raid():
    city, w = _world(followers=3)
    _days(w, 9)
    assert not city.living["warcamp"].get("arrived")


def test_a_week_alone_then_people_and_houses():
    city, w = _world(followers=4)
    rs = _days(w, 8)
    assert F.settled(city) == 4
    assert any(b["kind"] == "housing" for b in F.land(w)["buildings"])     # he got a roof up in the first week
    assert all(r["frontier"] for r in rs) and rs[0]["frontier"]["stage"] == "alone"
    assert not any(r.get("election") for r in rs)


def test_the_king_thinks_in_two_steps_on_the_frontier():
    from city.living.agents import LLMBrain

    class Mind:
        n = 0

        def json(self, system, user, schema, **kw):
            Mind.n += 1
            if "focus" in schema["properties"]:
                assert "shack" in user or "nothing" in user.lower()
                return {"thought": "I need a roof.", "focus": "building", "intention": "plan a hut",
                        "new_goal": "a dry place to sleep"}
            return {"tool": "plan", "args": {"idea": "a hut of branches and mud", "place": "the field"}}

    city, w = _world(llm=LLMBrain(Mind()))
    F.land(w)["projects"] = []
    Mind.n = 0
    me = w.agent("king")
    tool, args = w.brains["king"].choose(w, "king", __import__("city.living.tools", fromlist=["x"]).available(w, "king"))
    assert tool == "plan" and "hut" in args["idea"] and Mind.n == 2
    assert "nobody has crowned you" in FT.identity({**me, "_crowned": False})


def test_the_peddler_sells_tools():
    city, w = _world()
    me = w.agent("king")
    me["location"] = "road"
    F.peddler(w, force=True)
    L = F.land(w)
    L["peddler"]["goods"] = ["an iron axe"]
    city.treasury = 40
    FT.trade(w, me, {"buy": "iron axe"})
    assert F.tool_x(city, "wood") == 2.0 and city.treasury == 15


def test_ambition_grows_with_the_place():
    city, w = _world(followers=0)
    L = F.land(w)
    assert F.max_scale(w) == "small"                                # one man alone: cottages, not tenements
    p, why = F.start_project(w, "a tall apartment building of stone and timber", "field")
    assert p is None and "far too much" in why or "comes close" in why
    L["buildings"].append({"id": "b9", "name": "a cottage", "kind": "housing", "scale": "small", "capacity": 3,
                           "place": "field", "quality": "good", "day": 1})
    assert F.max_scale(w) == "small"                                # experience alone isn't enough without hands
    c = city.citizens
    c.add_many([f"s{i}" for i in range(12)], city.day, city.ward_for)
    assert F.max_scale(w) == "medium"                               # hands, but he's only ever built small
    L["buildings"].append({"id": "b10", "name": "a longhouse", "kind": "housing", "scale": "medium", "capacity": 8,
                           "place": "field", "quality": "good", "day": 2})
    assert F.max_scale(w) == "large"
    me = w.agent("king")
    out = FT.plan(w, me, {"idea": "a tall apartment building of stone and timber"})
    assert out and "laughed at himself" in out["text"]


def test_even_a_crowd_takes_days_on_a_big_building():
    city, w = _world(followers=0)
    L = F.land(w)
    p = {"id": "px", "name": "a tenement", "place": "field", "progress": 0.0, "hours": F.SCALES["huge"]["hours"],
         "needs": {"wood": 10}, "used": {}, "kind": "housing", "scale": "huge", "capacity": 90, "know": [],
         "boosts": "", "look": "", "missing": [], "helpers": []}
    L["projects"].append(p)
    L["stock"]["wood"] = 1000
    F.work(w, p, 5000, who="settlers")                      # 500 people for 10 hours: still only one crew's worth
    assert 0 < p["progress"] < 0.6 and not p.get("done")


def test_the_first_days_show_something():
    city, w = _world(followers=4)
    _days(w, 3)
    L = F.land(w)
    built = [b for b in L["buildings"] if b["id"] != "b0"]
    assert len(built) >= 2                                   # a fire pit or a roof on day one, then a cottage
    assert any(b["kind"] == "housing" for b in built)        # a man alone gets a cottage up in a day or two
    n = w.agent("king")["life"]["needs"]
    assert n["company"] > 0.2                               # alone by choice: loneliness doesn't eat his days


def _settlers(n=4):
    city, w = _world(followers=n)
    L = F.land(w)
    L["buildings"].append({"id": "bx", "name": "a cottage", "kind": "housing", "scale": "small", "capacity": n,
                           "place": "field", "quality": "good", "day": 1,
                           "lot": {"pos": [30, 0], "size": [6, 5, 3.6], "rot": 0, "shape": "cottage"}})
    L["next_arrival"] = city.day + 1
    F.arrive(w)
    return city, w, L


def test_a_settler_asks_to_start_a_garden_and_the_king_says_yes():
    from city.living import intents, personal, scene, tools
    city, w, L = _settlers()
    out = intents.process(w, {"u1": "I want to start a vegetable garden behind my house"}, None, 0)
    assert out[0]["action"] == "build_own"
    case = personal.pending(city, "u1")
    assert case and "garden" in case["idea"]
    me = w.agent("king")
    me["location"] = L["court_place"]
    tools.hold_court(w, me, {"case": case["id"], "verdict": "grant", "words": "Grow us some turnips."})
    p = personal.of(w, "u1")
    assert p and p["lot"] and p["lot"]["shape"] == "plot"
    home = scene.home_pos(w, "u1")
    assert abs(p["lot"]["pos"][0] - home[0]) + abs(p["lot"]["pos"][1] - home[1]) < 30      # by their house
    assert any(x["kind"] == "court" and "said yes" in x["text"] for x in city.living["outbox"] if x["to"] == "u1")
    for _ in range(20):                                      # evenings, then a keen day
        personal.daily(w)
        if not personal.of(w, "u1"):
            break
    b = next(b for b in L["buildings"] if b.get("owner") == "u1")
    assert b["name"].startswith("@u1's") and b["kind"] == "food"
    ex = scene.export(w)
    assert any(x.get("owner") == "u1" for x in ex["buildings"])


def test_commenting_about_your_build_speeds_it_up_and_nobody_saying_no_means_yes():
    from city.living import intents, life, personal
    city, w, L = _settlers()
    intents.process(w, {"u2": "I'd like to build a little beehive by my cottage"}, None, 0)
    case = personal.pending(city, "u2")
    case["day"] = city.day - 2                               # the king never got to it
    life.age_docket(w)
    p = personal.of(w, "u2")
    assert p and not personal.pending(city, "u2")
    city.living["acted_today"] = []
    intents.process(w, {"u2": "I spend the day on my beehive, smoking out the wasps first"}, None, 0)
    assert p["progress"] >= personal.KEEN / p["hours"] - 1e-6 or p.get("done")


def test_too_big_to_build_alone_becomes_a_petition():
    from city.living import intents, personal
    city, w, L = _settlers()
    intents.process(w, {"u3": "I want to build a great stone tower with a hall for the whole village"}, None, 0)
    assert not personal.pending(city, "u3")
    assert any(k["kind"] == "petition" and k["who"] == "u3" for k in city.living["docket"])
