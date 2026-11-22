"""A fake audience for the test kingdom: followers who join over time and comment
on posts in believable patterns, so you can run a whole season in minutes.

People come in archetypes (loyal, worker, activist, shopper, troll). They pick
from whatever commands the post offers, and they react to how their citizen is
doing: an unhappy subject's owner grumbles, opposes and votes to REVOLT.
Scenario files can force behaviour ("days 12-18: 60% GRUMBLE") to stress-test.
"""
import hashlib
import random

from ..roles import JOB_NAMES

ARCHETYPES = {
    # effect -> weight. Only effects the current pack offers are used.
    "loyal":    {"support": 4, "work": 3, "volunteer": 3, "train": 3, "event.help": 5, "event.choice": 5,
                 "vote.keep": 8, "shop": 1},
    "worker":   {"work": 6, "shop": 2, "strike": 2, "train": 1, "event.help": 3, "event.choice": 4, "volunteer": 1,
                 "vote.keep": 3, "vote.recall": 3},
    "activist": {"protest": 5, "oppose": 3, "strike": 4, "event.help": 4, "event.choice": 5, "volunteer": 2,
                 "vote.recall": 6},
    "shopper":  {"shop": 6, "work": 2, "event.help": 2, "event.choice": 3, "donate": 1, "vote.keep": 3,
                 "vote.recall": 2},
    "troll":    {"event.hinder": 5, "oppose": 3, "protest": 2, "event.choice": 3, "leave": 1, "vote.recall": 4},
}
UNHAPPY = {"protest": 6, "oppose": 4, "strike": 3, "vote.recall": 8, "event.hinder": 1}
FIRST = ["alex", "sam", "jordan", "taylor", "casey", "riley", "morgan", "jamie", "drew", "quinn", "avery", "rowan",
         "skyler", "harper", "emery", "blake", "reese", "finley", "parker", "sage", "kai", "noa", "lux", "zion"]
TAIL = ["", "_", ".", "x", "_official", "irl", "_codes", "_eats", "_art", "_pgh", "fit", "tv"]
FLAVOR = ["", "", "", " lol", " 🔥", " let's go", " !!!", " for my ward", " 😤", " 💯"]


class FakeAudience:
    def __init__(self, scenario, seed=7):
        self.s = scenario
        self.rng = random.Random(seed)
        self.followers = []
        self.kind = {}
        mix = scenario.get("archetypes") or {"loyal": .3, "worker": .3, "activist": .2, "shopper": .15, "troll": .05}
        self.mix_names, self.mix_w = list(mix), list(mix.values())
        self._grow(int(scenario.get("start_followers", 50)))

    def _handle(self):
        while True:
            h = f"{self.rng.choice(FIRST)}{self.rng.choice(TAIL)}{self.rng.randint(1, 9999)}"
            if h not in self.kind:
                return h

    def _grow(self, n):
        for _ in range(n):
            h = self._handle()
            self.followers.append(h)
            self.kind[h] = self.rng.choices(self.mix_names, self.mix_w)[0]

    def followers_on(self, day):
        """The full follower list as of this day - like a fresh Instagram export."""
        g = self.s.get("growth") or {}
        add = int(g.get("daily", 5))
        for v in g.get("viral") or []:
            if v.get("day") == day:
                add += int(v.get("add", 0))
        add = max(0, int(self.rng.gauss(add, max(1, add * 0.3))))
        self._grow(add)
        return list(self.followers)

    def comments_on(self, day, pack, city):
        """Comments on the day's post. Residents whose citizen is unhappy act angrier."""
        eng = float(self.s.get("engagement", 0.12))
        words_by_effect = {}
        for w, eff in pack["commands"].items():
            words_by_effect.setdefault(eff, []).append(w)
        forced = {}
        for o in self.s.get("overrides") or []:
            lo, hi = o.get("days", [0, 0])
            if lo <= day <= hi:
                forced = {w.upper(): float(v) for w, v in (o.get("command_share") or {}).items()}
        out = []
        c = city.citizens
        ts = 0
        for h in self.followers:
            if self.rng.random() > eng:
                continue
            ts += 1
            word = None
            if forced and self.rng.random() < sum(forced.values()):
                word = self.rng.choices(list(forced), list(forced.values()))[0]
            else:
                prefs = dict(ARCHETYPES[self.kind[h]])
                i = c.index.get(h)
                if i is not None and c.mood[i] < 0.35:
                    for k, v in UNHAPPY.items():
                        prefs[k] = prefs.get(k, 0) + v
                options = [(e, wt) for e, wt in prefs.items() if e in words_by_effect]
                if options:
                    eff = self.rng.choices([e for e, _ in options], [w for _, w in options])[0]
                    ws = words_by_effect[eff]
                    if eff == "event.choice":   # each decree has a favourite, so votes aren't a coin flip
                        bias = [1 + (int(hashlib.md5(f"{day}{w}".encode()).hexdigest(), 16) % 100) / 40 for w in ws]
                        word = self.rng.choices(ws, bias)[0]
                    else:
                        word = self.rng.choice(ws)
            if self.rng.random() < 0.04:
                out.append({"username": h, "text": "STATUS", "timestamp": ts})
            war = "FIGHT" in pack["commands"]
            if self.rng.random() < (0.06 if war else 0.015):
                job = "soldier" if war else self.rng.choice(JOB_NAMES)
                out.append({"username": h, "text": f"BECOME {job.upper()}", "timestamp": ts})
            if word is None:
                if self.rng.random() < 0.3:
                    out.append({"username": h, "text": self.rng.choice(["first", "love this", "who runs this",
                                                                         "the king is sus"]), "timestamp": ts})
                continue
            out.append({"username": h, "text": word.lower() if self.rng.random() < 0.2 else word
                        + self.rng.choice(FLAVOR), "timestamp": ts})
        return out
