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
    assert p.comment("reid_tester", "I chop wood all morning")["ok"]
    assert not p.comment("", "hello")["ok"]
    p._drain()
    assert "reid_tester" in p.city.citizens.index
    p.control({"action": "arrive"})
    with p.lock:
        p._controls()
    p.comment("reid_tester", "I want to start a vegetable garden behind my house")
    p._drain()
    for _ in range(4):
        with p.lock:
            p._tick()
    mine = [r for r in p.replies if r["to"] == "reid_tester"]
    assert mine and all(r["status"] == "pending" for r in mine)
    assert any("garden" in r["text"] for r in mine)
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
