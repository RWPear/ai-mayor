"""The living world: a clock that never stops, two minds, a court, and a crowd.

Time runs in 30-minute ticks. Between posts:
  - King Aldric lives his life. He starts blank - a name and one goal - and grows a self: needs (hunger,
    energy, company, fun) push him around, he tries pastimes, has his own ideas for the town (which can
    fail), holds court, and rules. Every night at 23:00 he reflects and rewrites who he is. Sleeps to 7:00.
  - Skarn the Red runs his war camp and decides when to strike (he sleeps 10:00-16:00).
  - Works get built, the steward skims, visitors turn up at the gate, the camp eats at midnight.
  - Comments arrive through the day; people's own-words moves are played out every hour.
At 19:00 the day's post closes (city/day.py) and the chronicle picks what goes in it.

ONE GPU BUDGET (cfg gpu_calls_per_hour). Every hour the crowd gets first claim - their own-words moves -
and the minds get what's left. On a viral day the king acts every couple of hours, on the big things;
on a quiet day he gets nearly the whole budget and acts every ~30 minutes. Same code, two very
different days. Rule-based minds/crowd fill in wherever the budget runs out.

Everything lives in city.living, so it saves and loads with the kingdom.
"""
import copy
import os

import httpx
import numpy as np

from .. import packs, storyteller
from ..roles import JOB_NAMES
from . import agents, chronicle, intents, life, tools, warcamp
from . import town as T

TICK = 30            # minutes per tick
POST_HOUR = 19       # the daily post closes at 19:00
AWAKE = {"king": lambda h: 7 <= h < 23, "warlord": lambda h: not (10 <= h < 16)}


class World:
    def __init__(self, city, king_brain=None, warlord_brain=None, crowd_llm=None, voice_llm=None):
        self.city = city
        self.rules = agents.RuleBrain()
        self.brains = {"king": king_brain or self.rules, "warlord": warlord_brain or self.rules}
        self.crowd_llm = crowd_llm        # subjects' own-words moves
        self.voice_llm = voice_llm        # subjects and the court answering the king
        self.stats = {}
        self.pending = []                 # comments that arrived but haven't been played out yet
        self._hour_free = {}
        if city.living is None:
            self._new()
        self._upgrade()
        for ev in city.living.get("custom_events", {}).values():   # the king's invented decrees
            storyteller.register(ev)

    def _new(self):
        k, w = agents.persona("king"), agents.persona("warlord")
        camp = copy.deepcopy(warcamp.START)
        camp["name"] = w.get("camp", camp["name"])
        start = self.city.day * 1440 + POST_HOUR * 60 - 1440      # one full day of life before the next post
        self.city.living = {
            "clock": start,
            "agents": {"king": {**k, "location": "throne_room", "goals": [], "next_act": start},
                       "warlord": {**w, "location": camp["name"], "goals": [w.get("ambition", "")][:1],
                                   "next_act": start + 60}},
            "warcamp": camp, "moments": [], "custom_events": {}, "unlocked": {"king": [], "warlord": []},
            "loud_comments": [], "notifications": [], "last_post_clock": start}

    def _upgrade(self):
        """Fills in anything an older save doesn't have yet."""
        lv = self.city.living
        lv.setdefault("town", T.new_town())
        lv.setdefault("docket", [])
        lv.setdefault("budget", {"hour": None, "left": 0, "size": 0})
        king = lv["agents"]["king"]
        king.setdefault("life", life.new_life())
        king.setdefault("self", life.new_self())
        if king.get("location") not in T.PLACES:
            king["location"] = "throne_room"
        persona = agents.persona("king")
        for k in ("personality", "ambition", "flaw", "voice", "passions"):   # older saves had a preset personality
            if k not in persona:
                king.pop(k, None)
        king.setdefault("goal", persona.get("goal", ""))
        for who in ("king", "warlord"):
            if not lv["unlocked"].get(who):
                lv["unlocked"][who] = sorted(tools.unlocked(self, who))

    # ------------------------------------------------------------------ helpers the tools use
    @property
    def clock(self):
        return self.city.living["clock"]

    def hour(self):
        return self.clock % 1440 // 60

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
        del self.city.living["moments"][:-1000]
        return m

    def moments_since(self, clock):
        return [m for m in self.city.living["moments"] if m["clock"] > clock]

    def recent_feud(self, a, b):
        return any(m["kind"] == "world" and "feud" in m["text"] and a in m["handles"] and b in m["handles"]
                   for m in self.moments_since(self.clock - 7 * 1440))

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

    # ------------------------------------------------------------------ the GPU budget
    def _budget_hour(self):
        b = self.city.living["budget"]
        key = self.clock // 60
        if b["hour"] != key:
            size = int(self.city.cfg.get("gpu_calls_per_hour", 120))
            b.update({"hour": key, "left": size, "size": size})
        return b

    def spend_calls(self, n):
        b = self._budget_hour()
        b["left"] -= n
        self.stats["model_calls"] = self.stats.get("model_calls", 0) + n

    def can_think(self, n=1):
        return self._budget_hour()["left"] >= n

    def pace(self):
        """How the hour is going: 'quiet' (the king has the GPU), 'busy', or 'viral' (the crowd has it)."""
        b = self._budget_hour()
        share = b["left"] / max(1, b["size"])
        return "quiet" if share > 0.5 else ("busy" if share > 0.2 else "viral")

    # ------------------------------------------------------------------ voices (cheap calls)
    def voice_subject(self, i, situation):
        """A subject's reply to the king, in character (one call), or a line from their mood."""
        c, city = self.city.citizens, self.city
        job, hold = JOB_NAMES[int(c.job[i])], city.wards[int(c.ward[i])]["name"]
        if self.voice_llm and self.can_think():
            self.spend_calls(1)
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
                                    "People in my hold are scared.", "With respect, sire, the roads are a disgrace."])
        return city.rng.choice(["The hold is well, your majesty.", "Long live the king!",
                                "The harvest looks good this year.", "Is it true you paint, your majesty?"])

    def voice_npc(self, key, situation):
        npc = life.court().get(key, {})
        city = self.city
        if self.voice_llm and self.can_think():
            self.spend_calls(1)
            recent = "; ".join(m["text"] for m in self.moments_since(self.clock - 12 * 60) if m["public"])[-600:]
            try:
                return self.voice_llm.chat(
                    f"You are {npc.get('name')}, at the court of King Aldric of Emberfall: {npc.get('personality')}. "
                    f"Recently in the kingdom: {recent or 'not much'}. Treasury {city.treasury:,.0f} gold, "
                    f"loyalty {city.approval():.0%}. Answer in one or two sentences, in character.",
                    situation, max_tokens=90, temperature=0.9).strip().strip('"')[:220]
            except Exception:
                pass
        lines = {"steward": ["A magnificent idea, your majesty. Truly.", "The treasury is in excellent hands, sire."],
                 "captain": ["Skarn won't wait for us to be ready, sire.", "The walls won't hold. They never have."],
                 "jester": ["Your majesty's painting looks like a goose fell in the ink.",
                            "Long live the king - well, long-ish."]}
        return city.rng.choice(lines.get(key, ["Yes, your majesty."]))

    def court_here(self):
        """Which members of the court are where the king is right now."""
        loc = self.agent("king").get("location")
        here = [k for k, v in life.court().items() if v.get("place") == loc]
        if (self.clock // 60) % 4 == 1:          # the jester turns up now and then
            here.append("jester")
        return sorted(set(here))

    def people_here(self, pid, n=3):
        """A few real subjects you'd find at this place at this hour."""
        jobs = T.jobs_here(pid, self.hour())
        if not jobs:
            return []
        c = self.city.citizens
        mask = c.active() & np.isin(c.job, [JOB_NAMES.index(j) for j in jobs])
        idx = np.where(mask)[0]
        if not len(idx):
            return []
        return [int(i) for i in self.city.rng.sample(idx.tolist(), min(n, len(idx)))]

    # ------------------------------------------------------------------ comments through the day
    def queue_comments(self, comments, spread=True):
        """Comments for the current post. In tests they're spread across the day; live, they arrive as polled."""
        if not comments:
            return
        start, end = self.city.living.get("last_post_clock", self.clock), self.next_post_clock()
        ordered = sorted(comments, key=lambda cm: cm.get("timestamp", 0))
        for k, cm in enumerate(ordered):
            at = start + int((end - start) * (k + 0.5) / len(ordered)) if spread else self.clock
            self.pending.append((at, cm))

    def process_crowd(self, free, final=False):
        """Plays out own-words moves within the hour's budget (the crowd gets first claim)."""
        if not free:
            return []
        b = self._budget_hour()
        share = 1.0 if final else 0.85
        batches = int(max(0, b["left"] * share) // 2)            # 2 calls per batch of 8 (read + tell)
        ai_people = min(len(free), batches * 8) if self.crowd_llm else 0
        out = intents.process(self, free, self.crowd_llm, ai_people)
        lv = self.city.living
        lv["loud_comments"] = (lv.get("loud_comments", []) + [f"@{u}: {t[:120]}" for u, t in list(free.items())[:6]])[-8:]
        self.stats["crowd_moves"] = self.stats.get("crowd_moves", 0) + len(out)
        return out

    def _release_comments(self):
        due = [cm for at, cm in self.pending if at <= self.clock]
        self.pending = [(at, cm) for at, cm in self.pending if at > self.clock]
        if not due:
            return
        free = {}
        packs.parse(due, self.city.pack or {"commands": {}}, None, free)
        self._hour_free.update(free)

    def finish_crowd(self, free):
        """At the close: anyone whose own-words move hasn't been played out yet gets it now."""
        acted = set(self.city.living.get("acted_today", []))
        left = {u: t for u, t in free.items() if u not in acted}
        left.update({u: t for u, t in self._hour_free.items() if u not in acted})
        self._hour_free = {}
        self.process_crowd(left, final=True)

    # ------------------------------------------------------------------ the loop
    def tick(self):
        lv = self.city.living
        lv["clock"] += TICK
        hour = self.hour()
        self._budget_hour()
        self._release_comments()
        if self.clock % 60 == 0:                                  # on the hour: the crowd, then visitors
            hf, self._hour_free = self._hour_free, {}
            self.process_crowd(hf)
            case = life.visitors(self) if self.city.rng.random() < 0.35 else None
            if case:
                self.moment("world", f"At the castle gate: {case['text']}.", 0, public=False)
        settled = warcamp.settle(self.city)
        if settled:
            self.moment("warlord", settled, 1, public=False)
        if self.clock % 1440 == 0:
            hungry = warcamp.daily_upkeep(self.city)
            if hungry:
                self.moment("warlord", hungry, 1, public=False)
        if self.clock % 1440 == 12 * 60:
            self._steward_skims()
        self.announce_works(life.advance_works(self, TICK))
        self._check_unlocks()
        king = self.agent("king")
        life.drift(king, AWAKE["king"](hour))
        if not AWAKE["king"](hour):
            if self.clock % 1440 == 23 * 60:                     # going to sleep: who am I becoming?
                life.reflect(self, king, getattr(self.brains["king"], "llm", None))
            king["location"] = "bedchamber"
        for who in ("king", "warlord"):
            me = self.agent(who)
            if warcamp.camp(self.city).get("defeated") and who == "warlord":
                continue
            if AWAKE[who](hour) and self.clock >= me.get("next_act", 0):
                self.act(who)
                me["next_act"] = max(me.get("next_act", 0), self.clock + self._interval(who))
        p = self.pace()
        self.stats[f"pace.{p}"] = self.stats.get(f"pace.{p}", 0) + 1

    def _interval(self, who):
        """Quiet hour: the king acts every ~30 min. Viral hour: every ~2 hours. The warlord a bit slower."""
        base = {"quiet": 30, "busy": 60, "viral": 120}[self.pace()] * (1 if who == "king" else 1.5)
        return int(base * self.city.rng.uniform(0.8, 1.25))

    def act(self, who):
        me = self.agent(who)
        available = tools.unlocked(self, who)
        brain = self.brains[who]
        if brain is not self.rules:
            if self.can_think():
                self.spend_calls(1)
            else:
                brain = self.rules                                 # out of budget this hour: run on instinct
                self.stats["budget_rules"] = self.stats.get("budget_rules", 0) + 1
        tool, args = brain.choose(self, who, available)
        fn = available.get(tool, (None,))[0]
        m = None
        if fn:
            self._doing = f"{who}.{tool}"
            try:
                m = fn(self, me, args)
            except Exception as e:   # a bad argument from the model shouldn't stop the world
                self.stats["tool_errors"] = self.stats.get("tool_errors", 0) + 1
                self.stats["last_error"] = f"{who}.{tool}: {type(e).__name__}: {e}"[:200]
        self._doing = None
        self.stats[f"{who}.{tool}"] = self.stats.get(f"{who}.{tool}", 0) + 1
        return m

    def announce_works(self, finished):
        for w, result in finished:
            name = w["name"][0].upper() + w["name"][1:]
            text = {"success": f"{name} is finished, and it turned out well.",
                    "shoddy": f"{name} is finished... sort of. It's shoddy and already cracking.",
                    "failed": f"{name} FAILED. The work fell apart and {w['cost']:,.0f} gold is gone."}[result]
            self.moment("king", text, 3 if result == "failed" else 2, public=True, place=w["place"])
            self.notify(f"{w['name']}: {result}")

    def _steward_skims(self):
        if self.city.treasury <= 0:
            return
        take = round(self.city.treasury * 0.004 + 5)
        self.city.treasury -= take
        lv = self.city.living
        lv["steward_skimmed"] = lv.get("steward_skimmed", 0) + take
        self.moment("steward", f"Steward Wendell quietly pocketed {take} gold from the treasury "
                               f"({lv['steward_skimmed']} so far).", 1, public=False)

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

    def post(self, mayor, followers, comments, pack=None, already_queued=False):
        """Today's post closes: the kingdom runs its day (city/day.py) with the world attached."""
        from ..day import run_day
        if comments and not already_queued:
            self.queue_comments(comments)
        self.live_until_post()
        r = run_day(self.city, mayor, followers, comments, pack, world=self)
        self.city.living["last_post_clock"] = self.clock
        self.pending = []
        return r

    def chronicle(self):
        return chronicle.pick(self.moments_since(self.city.living.get("last_post_clock", -10 ** 9)))
