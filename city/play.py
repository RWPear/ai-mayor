"""./kingdom play - a live kingdom you can poke at from the browser.

The simulation runs on a real clock (by default a day takes about 24 minutes), the 3D world follows it, and a
side panel lets you comment as any follower: type a handle and they follow on the spot. Comments play out on
the next tick (half an hour of game time). Every reply the kingdom would send waits in a feed for you to approve
or reject - the same approval step the Instagram version will have. Nothing is posted anywhere.

    ./kingdom play                     # a new kingdom (the king alone in his field), rule-based king
    ./kingdom play --mayor llm         # with the model (brainbox)
    ./kingdom play --state data/play   # where it's saved (it picks up where it left off)
    ./kingdom play --fresh --crowd 15  # start over, with 15 made-up followers commenting in the background

Endpoints (the viewer uses them; JSON):
    GET  /live/state                   clock, day, speed, paused, version, what's happening
    GET  /live/scene                   the 3D scene of today so far (scene/1)
    GET  /live/feed?since=N            what happened, the replies waiting for approval, everyone's handle
    POST /live/comment {handle, text}  comment as a follower (new handles follow first)
    POST /live/control {action, ...}   speed / pause / play / close (today's post, now) / arrive (the road, now)
                                       / step (one tick, while paused)
    POST /live/reply {id, status, text?}  approve / reject / edit a reply
"""
import http.server
import json
import queue
import threading
import time
import traceback
from pathlib import Path

from . import config, report
from .recorder import VIEWER, recorders

SPEEDS = {"slow": 60, "normal": 30, "fast": 7.5, "faster": 1.5}     # real seconds per half-hour tick
#   slow: a day in 48 min · normal: 24 min · fast: 6 min · faster: about a minute


class Play:
    def __init__(self, state, mayor="rules", fresh=False, speed="normal", crowd=0, name="Emberfall", seed=None):
        from .living import world as W
        from .mayor import make
        from .model import City
        from .run import make_world
        self.W = W
        cfg = config.load()
        self.state = Path(state)
        if fresh or not (self.state / "city.json").exists():
            import random
            seed = seed if seed is not None else random.randrange(1, 10 ** 9)   # a new king every time
            self.city = City(cfg, name, seed=seed)
        else:
            self.city = City.load(self.state, cfg)
        self.world = make_world(self.city, mayor)
        self.mayor = make(mayor)
        self.audience = None
        if crowd:
            from .sources.fake import FakeAudience
            self.audience = FakeAudience({"start_followers": crowd, "growth": {"daily": max(1, crowd // 8)},
                                          "engagement": 0.35, "free_text": 0.5}, seed=seed or 7)
        from . import llm
        llm.CLOCK = self.world.now_str
        self.model = llm.check() if mayor == "llm" else {"ok": False, "off": True, "error": None}
        self._model_checked = time.time()
        self.inbox = queue.Queue()
        self.lock = threading.Lock()        # the world (held through a tick, which can take a while with the model)
        self.rlock = threading.Lock()       # the replies
        self.tick_s = SPEEDS.get(speed, 30)
        self.paused = False
        self.version = 0
        self.arrived = []                   # comments since the last post closed (the post needs them all)
        self.replies = []                   # every reply, with its approval status
        self.seen_out = 0
        self.log = []                       # what happened: moments, in order
        self.n_moments = len(self.city.living.get("moments", []))
        self.cache = {"scene": b"null", "state": b"{}"}
        self.error = None
        self.pending_control = []
        self.handles = []
        self._start_crowd()
        if fresh or self.world.clock < 0:             # a new kingdom opens at dawn, not in the dark
            self._to_dawn()
        self._publish()

    def _to_dawn(self):
        """Skips the first night fast: he's asleep anyway, so instincts run it, not the model (which would take
        minutes before the page could open)."""
        w = self.world
        saved = (dict(w.brains), w.crowd_llm, w.voice_llm, w.director_llm)
        w.brains = {k: w.rules for k in w.brains}
        w.crowd_llm = w.voice_llm = w.director_llm = None
        try:
            while w.clock % 1440 != 6 * 60 + 30:
                w.tick()
        finally:
            w.brains, w.crowd_llm, w.voice_llm, w.director_llm = saved[0], saved[1], saved[2], saved[3]
        self._collect()

    # ------------------------------------------------------------------ the loop
    def run(self):
        while True:
            t0 = time.time()
            try:
                self._drain()
                with self.lock:
                    stepped = self._controls()
                    if not self.paused or stepped:
                        self._tick()
                        self._publish()
                self.error = None
            except Exception as e:      # keep the world alive; show the error in the panel
                self.error = f"{type(e).__name__}: {e}"
                traceback.print_exc()
            wait = (self.tick_s if not self.paused else 0.25) - (time.time() - t0)
            end = time.time() + max(0.05, wait)
            while time.time() < end:    # wake early for comments and buttons
                if self.pending_control or (not self.inbox.empty() and self.paused):
                    break
                time.sleep(0.1)

    def _tick(self):
        w, city = self.world, self.city
        if w.clock + self.W.TICK > w.next_post_clock():
            self._close_post()
        else:
            w.tick()
        self._collect()
        if city.living["clock"] % 120 == 0:
            city.save(self.state)

    def _close_post(self):
        w, city = self.world, self.city
        from .day import pack_for_today
        pack = pack_for_today(city)
        followers = self.audience.followers_on(city.day + 1) if self.audience else []
        self._collect()
        r = w.post(self.mayor, followers, self.arrived, pack, already_queued=True)
        self.arrived = []
        self.seen_out = 0
        report.save(city, r, self.state / "days")
        self.log.append({"n": len(self.log), "time": w.now_str(), "who": "post", "public": True, "drama": 3,
                         "text": f"Day {r['day']}'s post closed. {report.headline(r)}"})
        self._start_crowd()
        city.save(self.state)

    def _start_crowd(self):
        """Made-up followers (--crowd) comment through the day, so it isn't just you."""
        if not self.audience:
            return
        from .day import pack_for_today
        city = self.city
        pack = pack_for_today(city)
        d = city.day + 1
        if d == 1:                                   # the first followers set off right away
            self._follow(self.audience.followers_on(1))
        comments = self.audience.comments_on(d, pack, city)
        for cm in comments:
            cm.setdefault("post", d)
        self.world.queue_comments(comments, spread=True)
        self.arrived += comments

    # ------------------------------------------------------------------ your comments
    def comment(self, handle, text):
        handle = str(handle or "").strip().lstrip("@").lower()[:30]
        text = str(text or "").strip()[:500]
        if not handle or not text:
            return {"ok": False, "why": "a handle and a comment, please"}
        self.inbox.put({"username": handle, "text": text, "timestamp": time.time(),
                        "id": f"c{int(time.time() * 1000)}"})
        return {"ok": True, "at": "next tick"}

    def _drain(self):
        got = []
        while not self.inbox.empty():
            got.append(self.inbox.get())
        if not got:
            return
        with self.lock:
            self._follow([cm["username"] for cm in got])
            for cm in got:
                cm["post"] = self.city.day + 1
                self.log.append({"n": len(self.log), "time": self.world.now_str(), "who": "@" + cm["username"],
                                 "public": True, "drama": 0, "comment": True, "text": cm["text"]})
            self.world.queue_comments(got, spread=False)
            self.arrived += got
            self.version += 1
            self._publish()

    def _follow(self, handles):
        """New handles follow on the spot (on the frontier they set off up the road)."""
        import numpy as np
        c, city = self.city.citizens, self.city
        new = [h for h in dict.fromkeys(handles) if h not in c.index]
        if not new:
            return
        idx = c.add_many(new, city.day, city.ward_for, revive=True)
        if self.world.frontier:
            from .living import frontier as F
            F.join_road(self.world, np.asarray(idx, np.int64))
        else:
            from .living import town
            town.settle(self.world, len(c.handles) - len(idx))
        for h in new:
            self.log.append({"n": len(self.log), "time": self.world.now_str(), "who": "world", "public": True,
                             "drama": 1, "text": f"@{h} followed the kingdom."
                             + (" They set off up the old road." if self.world.frontier else "")})

    # ------------------------------------------------------------------ buttons
    def control(self, body):
        self.pending_control.append(body)
        return {"ok": True}

    def _controls(self):
        stepped = False
        while self.pending_control:
            b = self.pending_control.pop(0)
            a = b.get("action")
            if a == "pause":
                self.paused = True
            elif a == "play":
                self.paused = False
            elif a == "speed":
                self.tick_s = SPEEDS.get(b.get("speed"), self.tick_s)
            elif a == "step":
                stepped = True
            elif a == "close":                         # skip to 19:00 and close today's post
                while self.world.clock + self.W.TICK <= self.world.next_post_clock():
                    self.world.tick()
                    self._collect()
                self._close_post()
                self._collect()
                self._publish()
            elif a == "arrive" and self.world.frontier:  # the travellers, now (testing: no week's wait)
                from .living import frontier as F
                n = F.arrive(self.world)
                self.log.append({"n": len(self.log), "time": self.world.now_str(), "who": "world", "public": True,
                                 "drama": 2, "text": f"(test) Everyone on the road arrives now: {n}."})
                self._collect()
                self._publish()
        return stepped

    def set_reply(self, body):
        with self.rlock:                            # (not the world's lock: approving never waits on a tick)
            r = next((x for x in self.replies if x["id"] == body.get("id")), None)
            if not r:
                return {"ok": False}
            if body.get("text"):
                r["text"] = str(body["text"])[:600]
                r["edited"] = True
            if body.get("status") in ("approved", "rejected", "pending"):
                r["status"] = body["status"]
            self.version += 1
            self._publish()
            return {"ok": True, "reply": r}

    # ------------------------------------------------------------------ what the browser sees
    def _collect(self):
        lv = self.city.living
        for m in lv.get("moments", [])[self.n_moments:]:
            self.log.append({"n": len(self.log), "time": m.get("time"), "who": m.get("who"), "public": m.get("public"),
                             "drama": m.get("drama", 1), "text": m.get("text"), "place": m.get("place")})
        self.n_moments = len(lv.get("moments", []))
        out = lv.get("outbox", [])
        with self.rlock:
            for x in out[self.seen_out:]:      # the same dict: later news folded into it shows up here too
                x["id"] = f"r{len(self.replies)}"
                x.setdefault("status", "pending")
                self.replies.append(x)
        self.seen_out = len(out)
        del self.log[:-1500]
        self.version += 1

    def _publish(self):
        from .living import frontier as F
        from .living import scene
        w, city = self.world, self.city
        try:                                # (the 3D scene exists for the frontier start)
            self.cache["scene"] = json.dumps(scene.export(w) if w.frontier else None, default=str).encode()
        except Exception as e:
            self.error = f"scene: {e}"
            traceback.print_exc()
        c = city.citizens
        self.handles = sorted(c.handles)[-400:] if hasattr(c, "handles") else []
        pack = city.pack or {}
        if not self.model.get("off") and time.time() - self._model_checked > 30:     # check again now and then
            from . import llm
            self.model = llm.check(self.model["url"], self.model["model"])
            self._model_checked = time.time()
        state = {"day": city.day + 1, "model": self.model, "clock": w.clock, "time": w.now_str(), "post_closes": w.now_str(w.next_post_clock()),
                 "paused": self.paused, "tick_s": self.tick_s, "tick_min": self.W.TICK, "version": self.version,
                 "speeds": SPEEDS, "error": self.error, "frontier": w.frontier,
                 "words": list((pack.get("commands") or {}).keys())[:8],
                 "status": F.status_line(F.summary(w)) if w.frontier else "",
                 "pending": sum(1 for r in self.replies if r["status"] == "pending")}
        self.cache["state"] = json.dumps(state, default=str).encode()

    def feed(self, since=0):                        # read without waiting for the tick (the browser shouldn't hang)
        return {"log": [m for m in list(self.log) if m["n"] >= since][-300:], "replies": list(self.replies)[-300:],
                "handles": self.handles, "version": self.version}


    def mind(self, since=0):
        """What the minds chose and why: every decision (model or rules), every call to the model with what it was
        told and what it said, and who the king is right now."""
        from . import llm
        if True:                                    # (no lock: a slightly stale read beats waiting on the model)
            k = self.world.agent("king")
            from .living import life
            fr = self.world.frontier
            from .living import frontier as F
            crowned = fr and F.land(self.world).get("crowned")
            card = {"name": ("King Aldric" if crowned else "Aldric") if fr else k.get("name"),
                    "goal": k.get("frontier_goal") if fr else k.get("goal"), "goals": k.get("goals", []),
                    "character": k.get("character"), "who": life.who_am_i(k), "thought": k.get("last_thought", ""),
                    "brain": ("model" if self.model.get("ok") else "model, but it isn't answering")
                    if getattr(self.world.brains["king"], "name", "") == "llm" else "rules",
                    "needs": {a: round(b, 2) for a, b in k.get("life", {}).get("needs", {}).items()},
                    "location": k.get("location")}
            dec = [d for d in list(self.world.decisions) if d["n"] >= since][-150:]
            calls = [c for c in list(llm.CALLS) if c["n"] >= since][-60:]
            mine = [d for d in list(self.world.decisions) if d["who"] == "king"]
            ruled = [d["brain"] for d in mine if d["brain"] != "model"]
            from collections import Counter
            tally = {"model": len(mine) - len(ruled), "rules": len(ruled),
                     "why": ", ".join(f"{n}x {w}" for w, n in Counter(ruled).most_common(3)),
                     "failed": sum(1 for c in list(llm.CALLS) if c.get("error"))}
            return {"king": card, "decisions": dec, "calls": calls, "tally": tally,
                    "stats": {a: b for a, b in self.world.stats.items() if not a.startswith("focus.")}}


def serve(play, port=8765):
    class H(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            path = path.split("?", 1)[0].split("#", 1)[0]
            return str(VIEWER / (path.lstrip("/") or "index.html"))

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, *a):
            pass

        def _json(self, obj, raw=None):
            body = raw if raw is not None else json.dumps(obj, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            p, _, q = self.path.partition("?")
            if p == "/live/state":
                return self._json(None, play.cache["state"])
            if p == "/live/scene":
                return self._json(None, play.cache["scene"])
            if p == "/live/mind":
                return self._json(play.mind())
            if p == "/live/feed":
                since = int(dict(x.split("=", 1) for x in q.split("&") if "=" in x).get("since", 0) or 0)
                return self._json(play.feed(since))
            if p == "/recorders.json":
                return self._json(recorders())
            if p in ("/days/scenes.json",):
                return self._json([])
            return super().do_GET()

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                body = {}
            if self.path == "/live/comment":
                return self._json(play.comment(body.get("handle"), body.get("text")))
            if self.path == "/live/control":
                return self._json(play.control(body))
            if self.path == "/live/reply":
                return self._json(play.set_reply(body))
            self.send_error(404)

    srv = http.server.ThreadingHTTPServer(("0.0.0.0", port), H)
    threading.Thread(target=play.run, daemon=True).start()
    import socket
    try:
        so = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); so.connect(("10.255.255.255", 1))
        host = so.getsockname()[0]; so.close()
    except OSError:
        host = "localhost"
    print(f"{play.city.name} is live at http://{host}:{port}/?live  ({play.world.now_str()}; "
          f"a tick every {play.tick_s:g}s; saved in {play.state}; Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        with play.lock:
            play.city.save(play.state)
        print("\nsaved.")
