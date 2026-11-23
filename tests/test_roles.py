"""Open roles: anyone can be anything - but claims get laughed at, and crafts you don't know go wrong."""
import numpy as np

from city import trades
from city.comments import route


def _world(n=30, seed=3):
    from city import config
    from city.living.world import World
    from city.mayor import RuleMayor
    from city.model import City
    city = City(config.load(), seed=seed)
    w = World(city)
    w.post(RuleMayor(), [f"u{i}" for i in range(n)], [])
    for i in range(n):
        w.note_comment({"username": f"u{i}", "id": f"c{i}", "post": city.day})
    return city, w


def _play(w, u, text):
    from city.living import intents
    w.city.living["acted_today"] = []
    w.note_comment({"username": u, "id": f"c{u}-{len(w.city.living.get('outbox', []))}-{text[:12]}",
                    "post": w.city.day + 1})                    # each play is a new comment
    before = len(w.city.living.get("outbox", []))
    intents.process(w, {u: text}, None, 0)
    return [x for x in w.city.living["outbox"][before:] if x["to"] == u]


def test_reading_role_comments():
    assert trades.parse("i am a thief!") == ("claim", "thief", True)
    assert trades.parse("BECOME RAT CATCHER") == ("become", "rat catcher", True)
    assert trades.parse("I'm going to be a fortune teller at the tavern")[:2] == ("become", "fortune teller")
    assert trades.parse("become thieves")[1] == "thief"
    assert trades.parse("i am the greatest thief in Emberfall")[1] == "greatest thief"
    assert trades.head("greatest thief") == "thief"
    for t in ("i'm going to the market", "I'm tired", "im so hungry", "I am loyal to the king"):
        assert trades.parse(t) is None, t
    p = trades.parse("i am a thief! i sneak into the blacksmiths house and forge a sword")
    assert p[:2] == ("claim", "thief") and not p[2]          # more to it: the rest plays out as their move


def test_become_anything_on_any_post():
    r = route({"username": "u", "text": "BECOME RAT CATCHER"}, {"WORK": "work"})
    assert r["kind"] == "meta" and r["job"] == "rat catcher"
    assert route({"username": "u", "text": "become a thief"}, {})["job"] == "thief"
    assert route({"username": "u", "text": "BECOME BLACKSMITH"}, {})["job"] == "blacksmith"


def test_a_claim_with_nothing_behind_it_gets_laughed_at():
    city, w = _world()
    c = city.citizens
    out = _play(w, "u1", "i am a thief!")
    assert c.label(c.index["u1"]) == "thief"                 # they get the life...
    assert "Prove it" in out[0]["text"]                       # ...and the kingdom laughs
    out = _play(w, "u1", "i am a thief!")
    assert c.label(c.index["u1"]) == "thief" and "Prove it" not in out[0]["text"]
    c.counts["steal"][c.index["u1"]] = 3                      # three real thefts later
    out = _play(w, "u1", "I am the greatest thief in Emberfall")
    assert any(x in out[0]["text"] for x in ("Everyone knows", "No argument"))
    assert "a known thief" in trades.reputation(c.counts_of(c.index["u1"]))


def test_titles_are_earned_and_nobody_is_a_dragon():
    city, w = _world()
    c = city.citizens
    was = c.label(c.index["u2"])
    for t in ("i am the king", "I become a knight", "i become a dragon"):
        out = _play(w, "u2", t)
        assert out and c.label(c.index["u2"]) == was, t


def test_a_thief_cannot_forge_a_sword():
    city, w = _world()
    c = city.citizens
    city.rng.random = lambda: 0.99                            # no beginner's luck
    _play(w, "u3", "BECOME THIEF")
    city.living["acted_today"], c.role_day = [], {}
    out = _play(w, "u3", "I sneak into the blacksmith's house and forge a sword")
    from city.living.intents import condition
    assert "not a blacksmith" in out[0]["text"] and "burned your hand" in out[0]["text"]
    assert condition(city, "u3")["state"] == "wounded"


def test_your_own_trade_pays():
    city, w = _world()
    c = city.citizens
    _play(w, "u4", "I become a rat catcher")
    gold = float(c.wealth[c.index["u4"]])
    out = _play(w, "u4", "I set traps for rats along King's Street")
    assert "your trade" in out[0]["text"] and float(c.wealth[c.index["u4"]]) > gold
    assert int(c.counts["craft"][c.index["u4"]]) == 1


def test_healers_heal_and_everyone_else_makes_it_worse():
    from city.living.intents import condition, set_condition
    city, w = _world()
    c = city.citizens
    city.rng.random = lambda: 0.99
    _play(w, "u5", "BECOME HEALER")
    set_condition(city, "u8", "wounded", 2, "lost a fight")
    _play(w, "u6", "I heal @u8")                              # not a healer
    assert condition(city, "u8")
    _play(w, "u5", "I heal @u8")
    assert condition(city, "u8") is None
    assert int(c.counts["heal"][c.index["u5"]]) == 1


def test_homeless_have_nothing_to_burn():
    from city.living import town
    city, w = _world()
    c = city.citizens
    _play(w, "u7", "i become homeless")
    i = c.index["u7"]
    assert c.homeless(i) and "sleeping rough" in town.summary(w)
    hit = town.burn_houses(w, int(c.ward[i]), 300)
    assert "u7" not in hit
    city.living["acted_today"], c.role_day = [], {}
    _play(w, "u7", "BECOME FARMER")                           # a trade comes with a roof again
    assert not c.homeless(i)


def test_one_new_life_a_day():
    city, w = _world()
    c = city.citizens
    _play(w, "u9", "I become a monk")
    out = _play(w, "u9", "I become a pirate")
    assert c.label(c.index["u9"]) == "monk" and "tomorrow" in out[0]["text"]


def test_the_model_maps_roles_nobody_has_had_and_everyone_shares_it():
    class FakeLLM:
        calls = 0

        def json(self, system, user, schema, **kw):
            FakeLLM.calls += 1
            return {"kind": "role", "faction": "guilds", "income": "normal", "illegal": False, "homeless": False,
                    "place": "fields", "knack": "wild", "skills": ["hunting", "magic"], "base": "farmer"}

    city, w = _world()
    w.crowd_llm = FakeLLM()
    c = city.citizens
    w.take_role("u10", "become", "beekeeper")
    w.take_role("u11", "become", "beekeeper")
    assert FakeLLM.calls == 1                                 # mapped once, remembered
    rec = c.role(c.index["u10"])
    assert rec["place"] == "fields" and rec["skills"] == ["hunting"]     # nobody gets magic
    assert c.index["u10"] in w.people_here("fields", 30) or not (7 <= w.hour() < 23)


def test_illegal_work_can_catch_up_with_you():
    from city.living.intents import condition
    city, w = _world()
    c = city.citizens
    _play(w, "u12", "BECOME SMUGGLER")
    city.rng.random = lambda: 0.0
    w._role_night()
    assert condition(city, "u12")["state"] == "jailed"


def test_wages_follow_the_role():
    city, w = _world()
    c = city.citizens
    _play(w, "u13", "BECOME BEGGAR")
    _play(w, "u14", "BECOME PHYSICIAN")
    wage = c.wage()
    assert wage[c.index["u13"]] == 0 and wage[c.index["u14"]] == trades.INCOME["high"]


def test_everyone_hears_something():
    city, w = _world()
    assert "nobody here answers to @ghost" in _play(w, "u15", "I rob @ghost")[0]["text"]
    assert _play(w, "u16", "I contemplate the meaning of the void")[0]["text"]
    w.city.living["welcomed"] = {}
    w.city.living["outbox"] = []
    assert w.welcome(["u17", "u17", "u18"]) == 2 and w.welcome(["u17"]) == 0
    assert "Welcome to Emberfall" in w.city.living["outbox"][0]["text"]
    assert w.city.living["outbox"][0]["status"] == "pending"   # waiting for a human to approve


def test_roles_survive_save_and_load(tmp_path):
    from city.citizens import Citizens
    city, w = _world()
    c = city.citizens
    _play(w, "u19", "BECOME RAT CATCHER")
    c.save(tmp_path)
    back = Citizens.load(tmp_path)
    assert back.label(back.index["u19"]) == "rat catcher" and back.role(back.index["u19"])["knack"] == "wild"
    assert np.array_equal(back.walled, c.walled)
