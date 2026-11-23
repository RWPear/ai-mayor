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

from .. import packs, storyteller, trades
from ..roles import JOB_NAMES
from . import agents, chronicle, intents, life, things, tools, warcamp
from . import frontier as F
from . import town as T

TICK = 30            # minutes per tick
POST_HOUR = 19       # the daily post closes at 19:00
AWAKE = {"king": lambda h: 7 <= h < 23, "warlord": lambda h: not (10 <= h < 16)}


class World:
    def __init__(self, city, king_brain=None, warlord_brain=None, crowd_llm=None, voice_llm=None, director_llm=None):
        self.city = city
        self.rules = agents.RuleBrain()
        self.brains = {"king": king_brain or self.rules, "warlord": warlord_brain or self.rules}
        self.crowd_llm = crowd_llm        # subjects' own-words moves
        self.voice_llm = voice_llm        # subjects and the court answering the king, the world narrating
        self.director_llm = director_llm  # invents events from what's going on (else: the hand-written list)
        self.stats = {}
        self.pending = []                 # comments that arrived but haven't been played out yet
        self._hour_free, self._hour_story = {}, {}
        if city.living is None:
            self._new()
        self._upgrade()
        city.living["director"] = bool(director_llm)
        for ev in city.living.get("custom_events", {}).values():   # invented decrees and events
            storyteller.register(ev)

    def _new(self):
        k, w = agents.persona("king"), agents.persona("warlord")
        camp = copy.deepcopy(warcamp.START)
        camp["name"] = w.get("camp", camp["name"])
        start = self.city.day * 1440 + POST_HOUR * 60 - 1440      # one full day of life before the next post
        frontier = self.city.cfg.get("start", "frontier") == "frontier"
        if frontier:                    # he starts with nothing (city/living/frontier.py)
            self.city.treasury = float(self.city.cfg.get("frontier_gold", 15))
            for ward, name in zip(self.city.wards, ["Riverside", "Hillfoot", "Woodedge"]):
                ward["name"] = name     # the corners of a settlement, not the holds of a kingdom
            k["frontier_goal"] = k.get("frontier_goal") or "build a kingdom out of nothing, and be crowned its king"
        self.city.living = {
            "clock": start, "town": F.new_town() if frontier else T.new_town(),
            "agents": {"king": {**k, "location": "shack" if frontier else "throne_room", "goals": [],
                                "next_act": start},
                       "warlord": {**w, "location": camp["name"], "goals": [w.get("ambition", "")][:1],
                                   "next_act": start + 60}},
            "warcamp": camp, "moments": [], "custom_events": {}, "unlocked": {"king": [], "warlord": []},
            "loud_comments": [], "notifications": [], "last_post_clock": start}

    def _upgrade(self):
        """Fills in anything an older save doesn't have yet."""
        lv = self.city.living
        lv.setdefault("town", T.new_town())
        lv.setdefault("docket", [])
        if "things" not in lv:
            lv["things"] = things.new_state()
            things.restock(self)
        lv.setdefault("budget", {"hour": None, "left": 0, "size": 0})
        king = lv["agents"]["king"]
        king.setdefault("life", life.new_life())
        king.setdefault("self", life.new_self())
        if king.get("location") not in T.places(lv["town"]):
            king["location"] = "shack" if self.frontier else "throne_room"
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
    def frontier(self):
        """The king started with nothing (city/living/frontier.py) - rather than a castle and a treasury."""
        return F.is_frontier(self.city)

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
        if who == "king" or who == "world":
            text = F.title(self.city, text)
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

    # ------------------------------------------------------------------ talking back to followers
    def note_comment(self, cm):
        """Remembers each follower's latest comment, so replies can go to it (Instagram replies need a comment),
        and counts comments per day (people who post 15+ a day stop getting replies to their moves)."""
        u = str(cm.get("username", "")).strip().lstrip("@").lower()
        if u:
            lv = self.city.living
            lv.setdefault("last_comment", {})[u] = {"id": cm.get("id"), "post": cm.get("post"), "day": self.city.day + 1}
            counts = lv.setdefault("comment_counts", {})
            if counts.get("_day") != self.city.day + 1:
                counts.clear()
                counts["_day"] = self.city.day + 1
            counts[u] = counts.get(u, 0) + 1

    def reply(self, handle, text, kind, credit=None):
        """Something happened to/with a follower's character. They hear about it (a reply to their latest comment,
        if they commented in the last 7 days), and if it's their doing it goes on their record and maybe the post."""
        lv = self.city.living
        handle = str(handle).lstrip("@").lower()
        text = F.title(self.city, text)
        last = lv.get("last_comment", {}).get(handle)
        spammy = kind in ("your_move", "your_story") and lv.get("comment_counts", {}).get(handle, 0) > 15
        if last and last["day"] >= self.city.day + 1 - 7 and not spammy and not intents.muted(self, handle):
            lv.setdefault("outbox", []).append({"to": handle, "text": text[:600], "kind": kind, "time": self.now_str(),
                                                "day": self.city.day + 1, "comment_id": last.get("id"),
                                                "post": last.get("post"), "status": "pending"})
            lv.setdefault("welcomed", {}).setdefault(handle, self.city.day + 1)
        if credit:
            rec = lv.setdefault("impact", {}).setdefault(handle, [])
            rec.append({"day": self.city.day + 1, "text": credit[:140]})
            del rec[:-10]
            lv.setdefault("credits_today", []).append({"to": handle, "text": credit[:140], "kind": kind})

    def take_role(self, handle, how, label, day=None, quiet_same=False):
        """'BECOME THIEF' / 'i am a thief!': the role is theirs (or the kingdom laughs). They hear about it."""
        c = self.city.citizens
        i = c.index.get(str(handle).lstrip("@").lower())
        if i is None or c.status[i] not in (0, F.ROAD):
            return None
        llm = None
        if self.crowd_llm and trades.normalize(label) not in c.role_book and self.can_think():
            llm = self.crowd_llm                       # a role nobody's had before: one short call to map it
            self.spend_calls(1)
        day = self.city.day + 1 if day is None else day
        out = trades.take(self.city, i, how, label, day, llm, quiet_same)
        if out["text"]:
            self.reply(c.handles[i], out["text"], "your_role")
        if out["changed"]:
            lab = c.label(i)
            drama = 1 if c.role(i) and (c.role(i).get("illegal") or c.role(i).get("homeless")) else 0
            self.moment("@" + c.handles[i], f"@{c.handles[i]} took up the life of {trades.a_(lab)}.", drama,
                        public=bool(drama), hold=self.city.wards[int(c.ward[i])]["name"], handles=[c.handles[i]])
        return out

    def welcome(self, users):
        """Default reply #1: someone who's never heard from the kingdom, and whose comment did nothing,
        gets one welcome - who their character is and how to play."""
        c, lv = self.city.citizens, self.city.living
        seen = lv.setdefault("welcomed", {})
        n = 0
        for u in dict.fromkeys(users):
            i = c.index.get(u)
            if i is None or u in seen or c.status[i] not in (0, F.ROAD) or intents.muted(self, u):
                continue
            if c.status[i] == F.ROAD:
                day = F.land(self)["next_arrival"]
                self.reply(u, f"👋 You're on the road to Emberfall as {c.names[i]}, {trades.a_(c.label(i))}. Everyone "
                              f"on the road arrives together on day {day}. Until then: send Aldric something useful "
                              f"(\"I send an axe ahead\"), leave him a word of advice, or decide who you'll be when "
                              f"you get there (\"I become a mason\"). Comment STATUS to see your character.", "welcome")
                seen[u] = self.city.day + 1
                n += 1
                continue
            hold = self.city.wards[int(c.ward[i])]["name"]
            home = "with no roof over your head" if c.homeless(i) else (
                "in a house inside the walls" if int(c.walled[i]) == 1 else "in a house in the hold")
            self.reply(u, f"👋 Welcome to Emberfall! You're {c.names[i]}, {trades.a_(c.label(i))} of {hold}, living "
                          f"{home}. Tell your character what to do in your own words - \"I steal a pie from the "
                          f"market\", \"I challenge @a_friend to a duel\" - or be anyone you like: \"I become a "
                          f"thief\". Comment STATUS to see your life.", "welcome")
            seen[u] = self.city.day + 1
            n += 1
        return n

    def counted(self, actions, tallies):
        """Default reply #2 for keywords: people who used today's word and heard nothing else get a short line."""
        lv = self.city.living
        day = self.city.day
        heard = {x["to"] for x in lv.get("outbox", []) if x.get("day") in (day, day + 1)}
        c = self.city.citizens
        for u, w in actions.items():
            if u in heard or u not in c.index or c.status[c.index[u]] != 0:
                continue
            n = int(tallies.get(w, 1))
            self.reply(u, f"Counted: {w}" + (f" - you and {n - 1:,} others." if n > 1 else " - you were the only one!"),
                       "counted")

    def _role_night(self):
        """At dusk: illegal work catches up with some people, and nights without a roof wear people down."""
        city, c = self.city, self.city.citizens
        for i, lab in list(c.roles.items()):
            rec = c.role_book.get(lab) or {}
            if c.status[i] != 0:
                continue
            u = c.handles[i]
            if rec.get("illegal") and not intents.condition(city, u):
                known = int(c.counts["steal"][i]) >= 3
                p = 0.03 + 0.08 * known + 0.08 * max(0.0, city.quality["defense"] - 0.8)
                if city.rng.random() < p:
                    fine = round(min(float(c.wealth[i]) * 0.3, 100.0))
                    c.wealth[i] -= fine
                    intents.set_condition(city, u, "jailed", 1, f"caught at their trade ({lab})")
                    life.add_case(city, "crime", u, f"@{u}, {trades.a_(lab)}, was caught at it by the guards")
                    c.log(i, city.day + 1, f"was caught by the guards and fined {fine} gold")
                    self.reply(u, f"The guards finally caught up with your line of work. {fine} gold gone, and a "
                                  f"night in {'the dungeon' if city.living['town']['rooms'].get('dungeon') else 'the stocks'}"
                                  f" - the king will hear your case.", "your_role")
                    self.moment("world", f"The guards caught @{u}, {trades.a_(lab)}, red-handed.", 2, public=True,
                                handles=[u])
        out = c.active() & (c.walled == -1)
        c.mood[out] = np.maximum(0.25, c.mood[out] - 0.01)

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
        job, hold = c.label(i), city.wards[int(c.ward[i])]["name"]
        if self.voice_llm and self.can_think():
            self.spend_calls(1)
            story = "; ".join((c.story.get(int(i)) or [])[-3:])
            where = (f"a settler in Emberfall - a new settlement Aldric is building from nothing"
                     + (", living in a tent by the road" if int(c.walled[i]) == -2 else "")
                     if self.frontier else f"{trades.a_(job)} of {hold} in the kingdom of Emberfall")
            if self.frontier:
                where = f"{trades.a_(job)}, " + where
            try:
                return self.voice_llm.chat(
                    f"You are {c.names[i]}, {where}"
                    f"{' (you have no house and sleep at the chapel)' if c.homeless(i) else ''}. Mood {float(c.mood[i]):.2f} "
                    f"(0 miserable - 1 thrilled), loyalty to the king {float(c.loyalty[i]):.2f}. Recently: {story}. "
                    "Answer in one or two short sentences, in character, plain words. Don't mention numbers.",
                    situation, max_tokens=80).strip().strip('"')[:200]
            except Exception:
                pass
        if self.frontier:
            tent = int(c.walled[i]) == -2
            if tent or float(c.mood[i]) < 0.45:
                return city.rng.choice(["It's cold in the tents at night.", "When's my house coming, Aldric?",
                                        "We need more food, not more plans.", "My back's killing me from all the hauling."])
            return city.rng.choice(["It's starting to feel like a real place.", "The new house doesn't leak. Much.",
                                    "I've never worked this hard in my life. I like it.",
                                    "Do you really think you'll be king one day?"])
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
                court = ("in Emberfall, a rough new settlement Aldric is building from nothing" if self.frontier
                         else "at the court of King Aldric of Emberfall")
                return self.voice_llm.chat(
                    f"You are {npc.get('name')}, {court}: {npc.get('personality')}. "
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

    NARRATE = {"type": "object", "properties": {
        "outcome": {"type": "string"}, "activity": {"type": "string"}, "minutes": {"type": "integer"},
        "hunger": {"type": "number"}, "energy": {"type": "number"}, "company": {"type": "number"},
        "fun": {"type": "number"}, "learned": {"type": "string"}, "found": {"type": "string"},
        "made": {"type": "string"}, "drama": {"type": "integer"}},
        "required": ["outcome", "activity", "minutes", "hunger", "energy", "company", "fun", "learned", "found",
                     "made", "drama"]}

    def narrate_activity(self, me, what):
        """The world's answer to 'the king does X here, now'. Bounded numbers, free words."""
        loc = me.get("location", "throne_room")
        t = self.city.living["town"]
        where = f"{T.place_of(loc, t)} ({T.describe(t, loc)})"
        if self.voice_llm and self.can_think():
            self.spend_calls(1)
            try:
                who = ("You are the world around Aldric, a man building a settlement called Emberfall from nothing (he "
                       "wants to be king one day), narrating what happens when he does something. He has almost nothing: "
                       "rough hands, a dull axe, a leaky shack. " if self.frontier else
                       "You are the world of the kingdom of Emberfall, narrating what happens when its king does something. ")
                out = self.voice_llm.json(
                    who + "He's a person, not a hero: things can go well, badly, or funny. Be concrete and grounded in the "
                    "place, the time and the weather. outcome: 1-2 sentences, third person ('The king...'). activity: a "
                    "2-3 word label. minutes: how long it took (10-240). hunger/energy/company/fun: how his needs "
                    "changed, each -0.5 to 0.5 (running tires you, reading is quiet fun, eating fills you). learned: "
                    "something he actually learned, or "". found: an object he ended up with, or "". made: a title "
                    "if he made something, or "". drama: 0 nothing to tell, 1 nice moment, 2 people would talk, "
                    "3 the whole kingdom would hear about it.",
                    f"Where: {where}. {things.stock_line(self.city, loc)} When: {self.now_str()}, "
                    f"{self.city.living.get('weather', 'a mild day')}. "
                    f"How he feels: {life.feeling(me)}\nWhat he does: {what}", self.NARRATE, max_tokens=220,
                    temperature=0.9)
                out = {k: out.get(k) for k in self.NARRATE["properties"]}
                for k in life.NEEDS:
                    out[k] = float(np.clip(float(out.get(k) or 0), -0.5, 0.5))
                out["minutes"] = int(np.clip(int(out.get("minutes") or 30), 10, 240))
                out["drama"] = int(np.clip(int(out.get("drama") or 0), 0, 3))
                for k in ("outcome", "activity", "learned", "found", "made"):
                    out[k] = str(out.get(k) or "").strip()[:220]
                if out["outcome"]:
                    return out
            except Exception:
                self.stats["narrate_fallbacks"] = self.stats.get("narrate_fallbacks", 0) + 1
        return self._narrate_rules(what)

    def _narrate_rules(self, what):
        w = what.lower()
        out = {"outcome": f"The king decided to {what.rstrip('.')}.", "activity": what, "minutes": 40, "hunger": -0.05,
               "energy": -0.05, "company": 0.0, "fun": 0.15, "learned": "", "found": "", "made": "", "drama": 0}
        rules = [(("run", "jog", "sprint", "ride", "sword", "spar", "swim", "climb"), {"energy": -0.3, "fun": 0.2, "hunger": -0.15, "minutes": 60}),
                 (("read", "study", "book", "letters", "write"), {"fun": 0.2, "energy": 0.05, "minutes": 90,
                                                                  "learned": "a few pages of an old book"}),
                 (("eat", "lunch", "dinner", "breakfast", "snack", "bread", "feast"), {"hunger": 0.6, "fun": 0.1, "minutes": 30}),
                 (("nap", "sleep", "rest", "lie down", "doze"), {"energy": 0.35, "minutes": 60}),
                 (("talk", "chat", "drink", "tavern", "visit", "dance"), {"company": 0.3, "fun": 0.15}),
                 (("paint", "draw", "sing", "lute", "carve", "whittle", "sculpt", "poem", "bake"),
                  {"fun": 0.35, "minutes": 90, "made": "something he made today", "drama": 1}),
                 (("fish", "hunt", "forage", "garden", "plant"), {"fun": 0.25, "minutes": 120, "found": "a small catch"}),
                 (("pray", "think", "walk", "stroll", "watch", "sit"), {"fun": 0.1, "energy": 0.05, "minutes": 45})]
        for words, eff in rules:
            if any(x in w for x in words):
                out.update(eff)
                break
        return out

    def court_here(self):
        """Which members of the court are where the king is right now."""
        loc = self.agent("king").get("location")
        if self.frontier:                        # on the frontier the court is whoever has turned up
            L = F.land(self)
            here = [k for k in L["court"] if k != "jester" and loc == L["court_place"]]
            if "jester" in L["court"] and (self.clock // 60) % 4 == 1:
                here.append("jester")
            return sorted(set(here))
        here = [k for k, v in life.court().items() if v.get("place") == loc]
        if (self.clock // 60) % 4 == 1:          # the jester turns up now and then
            here.append("jester")
        return sorted(set(here))

    def people_here(self, pid, n=3):
        """A few real subjects you'd find at this place at this hour."""
        c = self.city.citizens
        if self.frontier:                        # settlers are where their work is; tents at the camp at night
            a = np.where(c.active())[0]
            if not len(a):
                return []
            day = 7 <= self.hour() < 19
            here = [int(i) for i in a[:3000] if (F.home_of(c, i) == pid if day else
                                                  (pid == "camp" and int(c.walled[i]) == -2))]
            return self.city.rng.sample(here, min(n, len(here))) if here else []
        jobs = T.jobs_here(pid, self.hour())
        mask = c.active() & np.isin(c.job, [JOB_NAMES.index(j) for j in jobs]) if jobs else np.zeros(len(c), bool)
        if c.roles:                       # people with their own roles are wherever their role takes them
            own = np.array(list(c.roles), np.int64)
            mask[own] = False
            awake = 7 <= self.hour() < 23 or pid in ("tavern", "chapel", "kings_street")
            here = np.array([i for i in own if awake and (c.role_book.get(c.roles[int(i)]) or {}).get("place") == pid],
                            np.int64)
            mask[here] = True
            mask &= c.active()
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

    def process_stories(self, story, final=False):
        """Keyword + a story around it: the reply builds on the story (within what's left of the budget)."""
        if not story or not self.crowd_llm:
            return 0
        b = self._budget_hour()
        ai = min(len(story), int(max(0, b["left"] * (1.0 if final else 0.5))) * 8)
        return intents.stories(self, story, self.city.pack, self.crowd_llm, ai)

    def _release_comments(self):
        due = [cm for at, cm in self.pending if at <= self.clock]
        self.pending = [(at, cm) for at, cm in self.pending if at > self.clock]
        if not due:
            return
        due = [cm for cm in due if not intents.muted(self, str(cm.get("username", "")).lower())]
        for cm in due:
            self.note_comment(cm)
        free, story, flagged, jobs = {}, {}, [], {}
        actions, _, _ = packs.parse(due, self.city.pack or {"commands": {}}, jobs, free, story, flagged)
        for f in flagged:
            intents.flag(self, f["user"], f["kind"], f["text"])
        for u, label in jobs.items():                 # BECOME <ANYTHING>: right away, not at the close
            self.take_role(u, "become", label)
        if self.frontier:                             # people who said they'd work today really do
            cmds = (self.city.pack or {}).get("commands", {})
            keen = [u for u, w in actions.items() if str(cmds.get(w, "")).split(":")[0] in ("work", "volunteer",
                                                                                            "event.help")]
            F.land(self).setdefault("workers_today", []).extend(keen)
        self._hour_free.update(free)
        self._hour_story.update(story)
        bad = {f["user"] for f in flagged}
        self.welcome([u for u in (str(cm.get("username", "")).lstrip("@").lower() for cm in due)
                      if u not in free and u not in story and u not in jobs and u not in bad])

    def finish_crowd(self, free, story=None, flagged=None):
        """At the close: anyone whose own-words move hasn't been played out yet gets it now."""
        for f in flagged or []:
            if not any(m["user"] == f["user"] and m["text"] == f["text"]
                       for m in self.city.living.get("moderation", [])[-50:]):
                intents.flag(self, f["user"], f["kind"], f["text"])
        acted = set(self.city.living.get("acted_today", []))
        left = {u: t for u, t in free.items() if u not in acted and not intents.muted(self, u)}
        left.update({u: t for u, t in self._hour_free.items() if u not in acted})
        self._hour_free = {}
        self.process_crowd(left, final=True)
        told = {x["to"] for x in self.city.living.get("outbox", []) if x["kind"] == "your_story"}
        rest = {u: t for u, t in {**(story or {}), **self._hour_story}.items() if u not in told}
        self._hour_story = {}
        self.process_stories(rest, final=True)

    # ------------------------------------------------------------------ the loop
    def tick(self):
        lv = self.city.living
        lv["clock"] += TICK
        hour = self.hour()
        self._budget_hour()
        self._release_comments()
        if self.clock % 60 == 0:                                  # on the hour: the crowd, then visitors
            hf, self._hour_free = self._hour_free, {}
            hs, self._hour_story = self._hour_story, {}
            self.process_crowd(hf)
            self.process_stories(hs)
            case = life.visitors(self) if self.city.rng.random() < 0.35 else None
            if case:
                self.moment("world", f"At the castle gate: {case['text']}.", 0, public=False)
        self._warlord_arrival()
        settled = warcamp.settle(self.city, self)
        if settled:
            self.moment("warlord", settled, 1, public=False)
        if self.clock % 1440 == 0:
            if T.rebuild(self):
                self.moment("world", "Neighbours helped rebuild the burned houses.", 0, public=False)
            hungry = warcamp.daily_upkeep(self.city)
            if hungry:
                self.moment("warlord", hungry, 1, public=False)
        if self.clock % 1440 == 12 * 60 and (not self.frontier or "steward" in F.land(self)["court"]):
            self._steward_skims()
        if self.frontier:
            self._frontier_tick()
        if self.clock % 1440 == 18 * 60:
            life.age_docket(self)
            self._role_night()
        if self.director_llm and self.clock % 1440 in (6 * 60, 14 * 60):
            from . import director
            director.consider(self, self.director_llm)
        if self.clock % 1440 == 6 * 60:
            things.restock(self)
        things.tick(self)
        if self.clock % 1440 == 6 * 60 or "weather" not in lv:
            lv["weather"] = self.city.rng.choice(["clear and cold", "grey drizzle", "a warm sunny day", "thick fog",
                                                  "a windy day", "heavy rain", "a crisp bright morning", "muggy heat"])
            lv["weather_log"] = (lv.get("weather_log", []) + [{"t": self.clock, "weather": lv["weather"]}])[-14:]
        self.announce_works(life.advance_works(self, TICK))
        self._check_unlocks()
        king = self.agent("king")
        life.drift(king, AWAKE["king"](hour), alone=self.frontier and F.settled(self.city) == 0)
        if not AWAKE["king"](hour):
            if self.clock % 1440 == 23 * 60:                     # going to sleep: who am I becoming?
                life.reflect(self, king, getattr(self.brains["king"], "llm", None))
                king["talks_today"] = {}
                if self.frontier:
                    from . import scene
                    king["location"] = "shack"
                    king["next_act"] = max(king.get("next_act", 0), self.clock + 8 * 60)
                    scene.record(self, "king", "sleep", {"what": "sleep"}, None)
            king["location"] = "shack" if self.frontier else "bedchamber"
        if self.clock % 1440 == 10 * 60 and warcamp.camp(self.city).get("arrived"):   # the warlord turns in at dawn
            life.reflect(self, self.agent("warlord"), getattr(self.brains["warlord"], "llm", None))
        for who in ("king", "warlord"):
            me = self.agent(who)
            camp = warcamp.camp(self.city)
            if who == "warlord" and (camp.get("defeated") or not camp.get("arrived")):
                continue
            if AWAKE[who](hour) and self.clock >= me.get("next_act", 0):
                self.act(who)
                me["next_act"] = max(me.get("next_act", 0), self.clock + self._interval(who))
        p = self.pace()
        self.stats[f"pace.{p}"] = self.stats.get(f"pace.{p}", 0) + 1

    def _interval(self, who):
        """Free time: the king acts every ~20 min. Viral hour (the crowd has the GPU): every ~1.5 hours."""
        base = {"quiet": 20, "busy": 45, "viral": 90}[self.pace()] * (1 if who == "king" else 1.5)
        return int(base * self.city.rng.uniform(0.8, 1.25))

    def act(self, who):
        me = self.agent(who)
        available = tools.available(self, who)
        if not available:
            return None
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
        said = " ".join(str(args.get(k, "")) for k in ("text", "what", "question", "name")).strip().lower()[:80]
        if said and brain is not self.rules and said in me.get("recent_said", []):   # the model repeating itself
            self.stats["repeats_blocked"] = self.stats.get("repeats_blocked", 0) + 1
            me["nudge"] = "You just tried to repeat yourself word for word. Do something different."
            fn = None
        elif said:
            me["recent_said"] = (me.get("recent_said", []) + [said])[-8:]
        if fn:
            me.setdefault("last_used", {})[tool] = self.clock
            self._doing = f"{who}.{tool}"
            try:
                m = fn(self, me, args)
            except Exception as e:   # a bad argument from the model shouldn't stop the world
                self.stats["tool_errors"] = self.stats.get("tool_errors", 0) + 1
                self.stats["last_error"] = f"{who}.{tool}: {type(e).__name__}: {e}"[:200]
        self._doing = None
        self.stats[f"{who}.{tool}"] = self.stats.get(f"{who}.{tool}", 0) + 1
        if fn and self.frontier:                  # the 3D view's track of where he was and what he did
            from . import scene
            scene.record(self, who, tool, args, m)
        return m

    def announce_works(self, finished):
        for w, result in finished:
            name = w["name"][0].upper() + w["name"][1:]
            text = {"success": f"{name} is finished, and it turned out well.",
                    "shoddy": f"{name} is finished... sort of. It's shoddy and already cracking.",
                    "failed": f"{name} FAILED. The work fell apart and {w['cost']:,.0f} gold is gone."}[result]
            self.moment("king", text, 3 if result == "failed" else 2, public=True, place=w["place"])
            self.notify(f"{w['name']}: {result}")

    def _frontier_tick(self):
        """The frontier's clockwork: arrivals, word from the road, settlers' work, meals, the peddler."""
        t = self.clock % 1440
        if t % 60 == 0:                          # the 3D view's hourly snapshot (trees, tents, stores, progress)
            from . import scene
            scene.sample(self)
        L = F.land(self)
        day = self.city.day + 1
        if t == 6 * 60:
            F.morning(self)
            F.peddler(self)
        if t == 9 * 60:
            F.forecast(self)
        if t == 3 * 60:
            F.rough_night(self)
        if t == 12 * 60 and day >= L["next_arrival"]:
            F.arrive(self)
        if t in (9 * 60, 12 * 60, 15 * 60, 18 * 60):
            F.labor(self, 0.25)
        if t == 20 * 60:
            F.meals(self)
        if t == 21 * 60:                         # evenings: people's own builds
            from . import personal
            personal.daily(self)
        if t == 18 * 60 + 30:                    # just before the post closes
            F.day_summary(self)

    def _warlord_arrival(self):
        """The antagonist doesn't exist for the first few days - then rumours, then smoke in the north.
        On the frontier he only comes once the place is worth raiding."""
        camp = warcamp.camp(self.city)
        if camp.get("arrived"):
            return
        day = self.city.day + 1                                   # the post this moment belongs to
        when = int(self.city.cfg.get("warlord_arrives_day", 4))
        if self.frontier:
            when = F.land(self).get("warlord_day") or 10 ** 9
        t = self.clock % 1440
        if day == when - 1 and t == 15 * 60:
            hold = self.city.rng.choice([w["name"] for w in self.city.wards]) if self.city.wards else "the hills"
            self.moment("world", f"A shepherd from {hold} swears he saw riders on the northern hills. Nobody believes "
                                 f"him.", 1, public=True)
        if day >= when and t == 3 * 60:
            camp["arrived"] = self.city.day
            self.moment("world", "Before dawn, smoke rose over the northern hills. Someone has made camp up there - "
                                 "a lot of someones.", 2, public=True)
            self.agent("warlord")["next_act"] = self.clock
            self.notify(f"{self.agent('warlord')['name']} has arrived in the north")

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
            have = tools.unlocked(self, who)
            for t in new:
                desc = have[t][1]
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
        self.city.living["outbox"], self.city.living["credits_today"] = [], []   # handed over in r
        self.pending = []
        return r

    def chronicle(self):
        return chronicle.pick(self.moments_since(self.city.living.get("last_post_clock", -10 ** 9)))
