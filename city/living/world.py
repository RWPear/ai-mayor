"""The living world: a clock that never stops, two minds, and a crowd.

Time runs in 30-minute ticks. Between posts:
  - the king wakes (7:00-23:00) and acts about once an hour
  - the warlord acts about every 90 minutes and sleeps through the middle of the day
    (barbarians like the dark)
  - the war camp eats at midnight; raids resolve when the crowd has fought them
  - new tools unlock when the world allows it, and that's a moment of its own
At 19:00 the day's post closes: comments are read (keywords and people's own
words), the kingdom simulates the day (city/day.py), and the chronicle picks
what goes in the post.

Everything lives in city.living, so it saves and loads with the kingdom.
The same loop runs the test kingdom (fast-forward, fake crowd) and the live one
(real time, real comments).
"""
import copy
import json
import os

import httpx

from .. import storyteller
from . import agents, chronicle, tools, warcamp

TICK = 30            # minutes per tick
POST_HOUR = 19       # the daily post closes at 19:00
AWAKE = {"king": lambda h: 7 <= h < 23, "warlord": lambda h: not (10 <= h < 16)}


class World:
    def __init__(self, city, king_brain=None, warlord_brain=None, crowd_llm=None, voice_llm=None):
        self.city = city
        self.brains = {"king": king_brain or agents.RuleBrain(), "warlord": warlord_brain or agents.RuleBrain()}
        self.crowd_llm = crowd_llm        # subjects' intents
        self.voice_llm = voice_llm        # subjects answering the king when summoned
        self.stats = {}
        if city.living is None:
            self._new()
        for ev in city.living.get("custom_events", {}).values():   # the king's invented decrees
            storyteller.register(ev)

    def _new(self):
        k, w = agents.persona("king"), agents.persona("warlord")
        camp = copy.deepcopy(warcamp.START)
        camp["name"] = w.get("camp", camp["name"])
        start = self.city.day * 1440 + POST_HOUR * 60 - 1440      # one full day of life before the next post
        self.city.living = {
            "clock": start,
            "agents": {"king": {**k, "location": "throne room", "goals": [k.get("ambition", "")][:1], "next_act": start},
                       "warlord": {**w, "location": camp["name"], "goals": [w.get("ambition", "")][:1],
                                   "next_act": start + 60}},
            "warcamp": camp, "moments": [], "custom_events": {}, "unlocked": {"king": [], "warlord": []},
            "loud_comments": [], "notifications": [], "last_post_clock": start}
        for who in ("king", "warlord"):
            self.city.living["unlocked"][who] = sorted(tools.unlocked(self, who))

    # ------------------------------------------------------------------ helpers the tools use
    @property
    def clock(self):
        return self.city.living["clock"]

    def now_str(self, clock=None):
        t = self.clock if clock is None else clock
        return f"day {t // 1440 + 1}, {t % 1440 // 60:02d}:{t % 60:02d}"

    def agent(self, who):
        return self.city.living["agents"][who]

    def condition(self, expr):
        return storyteller.condition_ok(self.city, expr)

    def ward_index(self, name):
        n = str(name or "").strip().lower()
        if not n:
            return None
        for i, w in enumerate(self.city.wards):
            if w["name"].lower() == n or w["name"].lower() in n or n in w["name"].lower():
                return i
        return None

    def moment(self, who, text, drama=1, public=True, place=None, handles=None, hold=None):
        m = {"clock": self.clock, "time": self.now_str(), "day": self.city.day + 1, "who": who, "text": text,
             "drama": int(drama), "public": bool(public), "place": place, "handles": handles or [], "hold": hold or "",
             "kind": getattr(self, "_doing", None) or "world"}
        self.city.living["moments"].append(m)
        del self.city.living["moments"][:-800]
        return m

    def moments_since(self, clock):
        return [m for m in self.city.living["moments"] if m["clock"] > clock]

    def notify(self, text):
        """Anything surprising the AI did: kept in the save, printed live, and sent to NOTIFY_URL if set."""
        note = {"time": self.now_str(), "text": text}
        self.city.living["notifications"].append(note)
        del self.city.living["notifications"][:-200]
        url = os.environ.get("NOTIFY_URL")
        if url:
            try:
                httpx.post(url, json=note, timeout=5)
            except httpx.HTTPError:
                pass

    def voice_subject(self, i, situation):
        """A subject's reply to the king, in character (one call), or a line from their mood."""
        c, city = self.city.citizens, self.city
        from ..roles import JOB_NAMES
        job, hold = JOB_NAMES[int(c.job[i])], city.wards[int(c.ward[i])]["name"]
        if self.voice_llm:
            story = "; ".join((c.story.get(int(i)) or [])[-3:])
            try:
                return self.voice_llm.chat(
                    f"You are {c.names[i]}, {job} of {hold} in the kingdom of Emberfall. Mood {float(c.mood[i]):.2f} "
                    f"(0 miserable - 1 thrilled), loyalty to the king {float(c.loyalty[i]):.2f}. Recently: {story}. "
                    "Answer in one or two short sentences, in character, plain words. Don't mention numbers.",
                    situation, max_tokens=80).strip().strip('"')[:200]
            except Exception:
                pass
        if float(c.mood[i]) < 0.45:
            return city.rng.choice(["Bread costs twice what it did, your majesty.", "We need walls, not speeches.",
                                    "People in my hold are scared."])
        return city.rng.choice(["The hold is well, your majesty.", "Long live the king!",
                                "The harvest looks good this year."])

    # ------------------------------------------------------------------ the loop
    def tick(self):
        lv = self.city.living
        lv["clock"] += TICK
        hour = self.clock % 1440 // 60
        settled = warcamp.settle(self.city)
        if settled:
            self.moment("warlord", settled, 1, public=False)
        if self.clock % 1440 == 0:
            hungry = warcamp.daily_upkeep(self.city)
            if hungry:
                self.moment("warlord", hungry, 1, public=False)
        self._check_unlocks()
        for who in ("king", "warlord"):
            me = self.agent(who)
            if warcamp.camp(self.city).get("defeated") and who == "warlord":
                continue
            if AWAKE[who](hour) and self.clock >= me.get("next_act", 0):
                self.act(who)
                every = self.city.cfg.get(f"{who}_every_min", 60 if who == "king" else 90)
                me["next_act"] = self.clock + int(every * self.city.rng.uniform(0.7, 1.3))

    def act(self, who):
        me = self.agent(who)
        available = tools.unlocked(self, who)
        tool, args = self.brains[who].choose(self, who, available)
        fn = available.get(tool, (None,))[0]
        m = None
        if fn:
            self._doing = f"{who}.{tool}"
            try:
                m = fn(self, me, args)
            except Exception as e:   # a bad argument from the model shouldn't stop the world
                self.stats["tool_errors"] = self.stats.get("tool_errors", 0) + 1
                self.stats["last_error"] = f"{who}.{tool}: {e}"
        self._doing = None
        self.stats[f"{who}.{tool}"] = self.stats.get(f"{who}.{tool}", 0) + 1
        return m

    def _check_unlocks(self):
        lv = self.city.living
        for who in ("king", "warlord"):
            now = sorted(tools.unlocked(self, who))
            new = [t for t in now if t not in lv["unlocked"][who]]
            for t in new:
                desc = tools.TOOLS[who][t][1]
                name = self.agent(who)["name"]
                self.moment(who, f"New power: {name} can now {desc}.", 2 if who == "king" else 1,
                            public=(who == "king"))
                self.notify(f"{name} unlocked '{t}'")
            lv["unlocked"][who] = now

    def next_post_clock(self):
        return self.city.day * 1440 + POST_HOUR * 60

    def live_until_post(self):
        """Runs the world up to the moment today's post closes."""
        while self.clock + TICK <= self.next_post_clock():
            self.tick()

    def post(self, mayor, followers, comments, pack=None):
        """Today's post closes: the kingdom runs its day (city/day.py) with the world attached."""
        from ..day import run_day
        self.live_until_post()
        r = run_day(self.city, mayor, followers, comments, pack, world=self)
        self.city.living["last_post_clock"] = self.clock
        return r

    def chronicle(self):
        return chronicle.pick(self.moments_since(self.city.living.get("last_post_clock", -10 ** 9)))

    def dump_log(self, path):
        """The full log of the last day, for you (not the post)."""
        with open(path, "w") as f:
            for m in self.moments_since(self.city.living.get("last_post_clock", -10 ** 9)):
                f.write(json.dumps(m) + "\n")
