"""./kingdom play: comment as anyone, the world answers, replies wait for approval."""
from city.play import Play


def _play(tmp_path, **kw):
    return Play(tmp_path / "play", fresh=True, **kw)


def test_a_new_kingdom_opens_at_dawn_and_publishes_a_scene(tmp_path):
    p = _play(tmp_path)
    assert p.world.clock % 1440 == 6 * 60 + 30
    import json
    st = json.loads(p.cache["state"])
    assert st["day"] == 1 and st["frontier"] and not st["paused"]
    assert json.loads(p.cache["scene"])["schema"].startswith("scene/")


def test_commenting_as_a_new_handle_follows_and_gets_a_reply_to_approve(tmp_path):
    p = _play(tmp_path)
    assert p.comment("reid_tester", "I want to start a vegetable garden behind my house")["ok"]
    assert not p.comment("", "hello")["ok"]
    p._drain()
    assert "reid_tester" in p.city.citizens.index
    for _ in range(4):
        with p.lock:
            p._tick()
    mine = [r for r in p.replies if r["to"] == "reid_tester"]
    assert mine and all(r["status"] == "pending" for r in mine)
    assert any("farm" in r["text"] or "garden" in r["text"] or "building" in r["text"] or "odd jobs" in r["text"] for r in mine)
    out = p.set_reply({"id": mine[0]["id"], "status": "approved", "text": "Edited by hand."})
    assert out["ok"] and out["reply"]["status"] == "approved" and out["reply"]["edited"]
    assert any(m.get("comment") and m["who"] == "@reid_tester" for m in p.feed()["log"])


def test_closing_the_post_runs_the_day_and_starts_the_next(tmp_path):
    p = _play(tmp_path, crowd=5)
    p.control({"action": "close"})
    with p.lock:
        p._controls()
    assert p.city.day == 1
    assert (tmp_path / "play" / "days" / "day001.scene.json").exists()
    assert any(m["who"] == "post" for m in p.log)


def test_the_model_gets_room_to_finish_and_another_go_before_rules_step_in():
    from city import llm
    m = llm.LLM.__new__(llm.LLM)
    m.model, m.ctx, m.calls, m.url = "fake", 4096, 0, "http://x"
    asked = []

    def fake(system, user, schema=None, max_tokens=900, temperature=0.8):
        asked.append(max_tokens)
        if len(asked) == 1:
            return '{"results": [{"handle": "wes", "act', "length"      # ran out of room
        if len(asked) == 2:
            return '{"results": [oops', "stop"                           # finished, but not JSON
        return '{"results": []}', "stop"
    m._chat = fake
    assert m.json("s", "u", {"type": "object"}, max_tokens=60) == {"results": []}
    assert asked[0] >= 1536 and asked[1] > asked[0]                       # plenty of room, then more
    calls = list(llm.CALLS)[-2:]
    assert calls[0].get("retried") and "asking again" in calls[0]["error"]


def test_replies_fold_together_answer_only_recent_comments_and_stop_at_two(tmp_path):
    p = _play(tmp_path)
    w = p.world
    w.note_comment({"username": "wes", "id": "c1", "post": 1})
    w.reply("wes", "You chopped wood.", "your_move")
    w.reply("wes", 'Aldric said "hello".', "king_talked")
    w.reply("wes", 'Aldric said "hello again".', "king_talked")          # replaces the older chat
    out = [x for x in w.city.living["outbox"] if x["to"] == "wes"]
    assert len(out) == 1 and "hello again" in out[0]["text"] and '"hello".' not in out[0]["text"]
    out[0]["status"] = "approved"                                       # it went out
    w.reply("wes", "Your case was heard.", "court")
    w.reply("wes", "You moved into a cottage.", "moved_in")             # folded into the follow-up
    w.reply("wes", "x", "court")
    out = [x for x in w.city.living["outbox"] if x["to"] == "wes"]
    assert len(out) == 2 and out[1]["kind"].startswith("later") and "cottage" in out[1]["text"]
    out[1]["status"] = "approved"
    w.reply("wes", "Something else.", "court")                         # two replies to one comment: that's it
    assert len([x for x in w.city.living["outbox"] if x["to"] == "wes"]) == 2
    w.city.living["clock"] += 25 * 60                                   # a day later: the comment is stale
    w.reply("wes", "Old news.", "court")
    assert len([x for x in w.city.living["outbox"] if x["to"] == "wes"]) == 2


def test_the_bard_gets_the_world_and_writes_the_reply(tmp_path):
    from city.living import intents
    p = _play(tmp_path)
    p.comment("bil", "x"); p._drain()
    seen = {}

    class Fake:
        def json(self, system, user, schema, **kw):
            if "Subjects:" in user:
                return {"results": [{"handle": "bil", "action": "work", "target": "", "item": "", "also": "",
                                     "effort": 1, "skill": "", "abuse": False}]}
            seen["system"], seen["user"] = system, user
            return {"results": [{"handle": "@bil", "outcome": "@bil split a log clean in half.",
                                 "reply": "The log split clean. Aldric clapped, once, and looked embarrassed.", "drama": 1}]}
    p.world.city.living["acted_today"] = []
    r = intents.process(p.world, {"bil": "I chop wood all morning"}, llm=Fake(), ai_people=5)
    assert "bard" in seen["system"] and "THE WORLD" in seen["user"]
    assert r[0]["reply"].startswith("The log split clean")


def test_after_the_move_they_can_keep_talking_a_few_times(tmp_path):
    from city.living import intents
    p = _play(tmp_path)
    p.comment("tal", "I chop wood all morning"); p._drain()
    for _ in range(3):
        with p.lock:
            p._tick()
    assert "tal" in p.world.city.living["acted_today"]
    for k in range(5):                               # one an hour: 5 comments, TALK_PER_DAY answers
        p.comment("tal", f"hey Aldric, what's for supper? ({k})"); p._drain()
        for _ in range(2):
            with p.lock:
                p._tick()
    talk = [r for r in p.world.city.living.get("stories", {}).get("tal", []) if r["said"].startswith("hey")]
    assert len(talk) == intents.TALK_PER_DAY


def test_talk_gets_the_world_and_their_story(tmp_path):
    from city.living import intents
    p = _play(tmp_path)
    p.comment("tal", "x"); p._drain()
    intents.remember(p.world, "tal", outcome="@tal fished and caught a boot", reply="The boot fits.", said="I fish")
    seen = {}

    class Fake:
        def json(self, system, user, schema, **kw):
            seen["user"] = user
            return {"results": [{"handle": "tal", "reply": "Aldric laughs. 'Keep the boot.'", "abuse": False}]}
    coins = p.world.city.treasury
    out = intents.talk(p.world, [("tal", "does anyone want a boot?")], Fake(), 5)
    assert out[0]["reply"].startswith("Aldric laughs") and "caught a boot" in seen["user"] and "THE WORLD" in seen["user"]
    assert p.world.city.treasury == coins


def test_a_question_is_talk_not_a_brew_or_a_fight(tmp_path):
    from city.living import intents
    assert intents.rule_read("who do I have to kill around here to get a fresh brew?", False)[0] == "talk"
    p = _play(tmp_path)
    p.comment("q", "x"); p._drain()
    r = {"user": "q", "text": "what's that smell?", "action": "talk", "target": "", "item": "", "needs": []}
    intents.resolve(p.world, r, {})
    assert "talking" in r["facts"] and "gold" not in r["facts"]


def test_settlers_learn_a_craft_by_doing_it_not_by_a_random_trade(tmp_path):
    from city.living import intents
    p = _play(tmp_path)
    p.comment("brew", "x"); p._drain()
    assert not intents.knows(p.world, "brew", "brewing")
    learned = [intents._practise(p.world, "brew", "brewing") for _ in range(intents.PRACTICE)]
    assert learned[-1] and not any(learned[:-1]) and intents.knows(p.world, "brew", "brewing")
    gold = float(p.city.citizens.wealth[p.city.citizens.index["brew"]])
    r = {"user": "brew", "text": "I brew some ale", "action": "work", "target": "", "item": "", "needs": ["brewing"]}
    intents.resolve(p.world, r, {})
    assert r.get("skilled") and "gold" not in r["facts"]
    assert float(p.city.citizens.wealth[p.city.citizens.index["brew"]]) == gold


def test_no_guards_or_dungeons_on_the_frontier(tmp_path):
    from city.living import intents
    p = _play(tmp_path)
    for h in ("thief", "mark"):
        p.comment(h, "x")
    p._drain()
    for _ in range(20):
        r = {"user": "thief", "text": "I rob @mark", "action": "steal", "target": "mark", "item": "", "needs": []}
        intents.resolve(p.world, r, {})
        text = " ".join(str(r.get(k, "")) for k in ("facts", "reply_rule", "to_target")).lower()
        assert "guard" not in text and "dungeon" not in text and "castle" not in text


def test_a_wild_claim_comes_true_at_a_cost(tmp_path):
    from city.living import intents, wonders
    p = _play(tmp_path)
    p.comment("meeee", "x"); p._drain()
    p.world.city.living["acted_today"] = []
    out = intents.process(p.world, {"meeee": "I ride my dragon into town"}, None, 0)
    w = wonders.find(p.world.city, "dragon")
    assert w and w["owner"] == "meeee" and w["cost"]
    assert "real" in out[0]["reply"].lower() and "THE WORLD" not in out[0]["reply"]
    assert "dragon" in intents._world_now(p.world)                    # the narrator sees it from now on


def test_the_goat_can_be_hunted_once_it_exists(tmp_path):
    from city.living import intents, wonders
    p = _play(tmp_path)
    for h in ("billy", "meeee"):
        p.comment(h, "x")
    p._drain()
    assert intents.rule_read("I want to kill the goat for my king", False) == ("attack", "the goat")
    p.world.city.living["acted_today"] = []
    out = intents.process(p.world, {"billy": "I want to kill the goat for my king"}, None, 0)
    assert "goat" in out[0]["reply"] and "nobody here answers" not in out[0]["reply"]
    wonders.add(p.world, "the goat that follows billy", "thread", owner="billy", what="a goat", by="thread")
    p.world.city.rng.random = lambda: 0.1                          # it goes well
    p.world.city.living["acted_today"] = []
    out = intents.process(p.world, {"billy": "I kill the goat"}, None, 0)
    assert "SUCCEEDED" in out[0]["outcome"] or "gone" in out[0]["reply"]
    assert not wonders.find(p.world.city, "goat")


def test_wonders_cost_something_every_day(tmp_path):
    from city.living import wonders
    p = _play(tmp_path)
    w = wonders.add(p.world, "dragon hatchling", "creature", owner="x", what="a hatchling", cost="eats the town's food",
                    upkeep="hungry")
    p.city.treasury = 10
    wonders.daily(p.world)
    assert p.city.treasury == 7 and w in wonders.state(p.city)["open"]


def test_the_hosted_comment_model_is_optional_and_falls_back(monkeypatch):
    import json as _json
    from city import llm
    monkeypatch.delenv("COMMENT_MODEL", raising=False)
    assert type(llm.comment_llm()) is llm.LLM                           # nothing set: all local
    monkeypatch.setenv("COMMENT_MODEL", "claude-sonnet-5-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    api = llm.comment_llm()
    assert isinstance(api, llm.APILLM) and api.anthropic

    class R:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"stop_reason": "tool_use", "content": [{"type": "tool_use", "input": {"reply": "hi"}}]}
    sent = {}
    monkeypatch.setattr(llm.httpx, "post", lambda url, json, timeout, headers: sent.update(url=url, body=json) or R())
    out = api.json("sys", "user", {"type": "object", "properties": {"reply": {"type": "string"}}})
    assert out == {"reply": "hi"} and sent["url"].endswith("/messages") and sent["body"]["tool_choice"]["name"] == "answer"

    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(llm.httpx, "post", boom)
    monkeypatch.setattr(api.local, "_chat", lambda *a, **k: (_json.dumps({"reply": "local"}), "stop"))
    assert api.json("sys", "user", {"type": "object"}) == {"reply": "local"}   # the API is down: local answers


def test_a_gift_for_the_kingdom_reaches_the_king(tmp_path):
    from city.living import intents
    p = _play(tmp_path)
    p.comment("hauler", "x")
    p._drain()
    p.world.city.living["acted_today"] = []
    out = intents.process(p.world, {"hauler": "I bring lots of resources for the kingdom to enjoy"}, None, 0)
    assert out[0]["action"] == "gift_king"
    inv = p.world.agent("king")["life"]["inventory"]
    assert inv and inv[-1]["from"] == "hauler" and "resources" in inv[-1]["item"]


def test_a_comment_is_an_extra_shift_where_it_says(tmp_path):
    from city.living import frontier as F, intents
    p = _play(tmp_path)
    for h in ("ann", "bob"):
        p.comment(h, "x")
    p._drain()
    p.city.treasury = 100
    F.start(p.world, "farm", 0)
    p.world.city.living["acted_today"] = []
    out = intents.process(p.world, {"ann": "I help build the farm today"}, None, 0)
    assert F.today(p.world)["extra"].get("ann") == 1 and F.land(p.world)["jobs"]["ann"].startswith("build:")
    assert "building" in out[0]["reply"] or "double shift" in out[0]["reply"].lower() or "farm" in out[0]["reply"]
