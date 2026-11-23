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

FREE_TEXT = [
    "I sneak into the castle kitchens to steal bread for my kids",
    "I sharpen my sword and stand guard on the walls all night",
    "I open my tavern and give the soldiers free ale",
    "I write a rude song about the king and sing it in the square",
    "I gather the farmers and march to the castle to demand lower taxes",
    "I offer to teach the king how to actually ride a horse",
    "I go into the forest to hunt for the hungry families in my hold",
    "I forge arrowheads all day for the army",
    "I try to sell fake dragon eggs at the market",
    "I volunteer to scout the northern pass",
    "I kneel before the king and swear my loyalty",
    "I hide my gold under the floorboards before the tax collector comes",
    "I start a betting pool on whether the king survives the Reckoning",
    "I bake a cake shaped like the king's statue and sell slices",
    "I spread a rumor that the warlord is actually afraid of geese",
    "I fix the broken bridge in my hold with my neighbors",
    "I challenge the strongest guard to an arm wrestling match",
    "I paint WALLS NOT STATUES on the castle gate at night",
    "I train the village kids to throw rocks at barbarians",
    "I ask the king for a job as his royal food taster",
    "I rob {target} while they're asleep",
    "I challenge {target} to a duel at noon",
    "I punch {target} for cheating me at dice",
    "I give {target} 20 gold to fix their roof",
    "I buy {target} a drink and become friends",
    "I loudly mock {target}'s terrible singing in the tavern",
    "I try to kill {target} for stealing my goat",
    "I send the king a lute so he can learn to play",
    "I give the king my best fishing rod",
    "I bring the king a basket of fresh apples",
    "I suggest the king builds a bridge over the river",
    "I ask the king to fix the mud on King's Street",
    # roles: becoming someone, claiming to be someone, and trying things outside your trade
    "i am a thief!",
    "I become a rat catcher",
    "I'm going to be a fortune teller at the tavern",
    "i am the king",
    "I give up farming and become a monk",
    "I sneak into the smithy at night and forge myself a sword",
    "I brew a potion to make the baker fall in love with me",
    "I cast a fireball at the warlord's camp",
    "I heal {target} after their fight",
    "I bless {target} at the chapel",
    "I bake a pie for the whole street",
    "I become a beggar and sit outside the chapel",
    # their own builds (asked at court)
    "I want to start a vegetable garden behind my house",
    "I'd like to build a little beehive by my home",
    "can I set up a bread oven next to my tent?",
    "I want to plant an orchard",
    "I'm going to build a workbench so I can make chairs",
    "I spend the evening on my garden, pulling weeds",
]

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
            words_by_effect.setdefault(eff.partition(":")[0], []).append(w)
        free_share = float(self.s.get("free_text", 0.12)) if getattr(city, "living", None) else 0.0
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
            if free_share and self.rng.random() < free_share:   # living world: some people write their own move
                text = self.rng.choice(FREE_TEXT)
                if "{target}" in text:
                    text = text.replace("{target}", "@" + self.rng.choice(self.followers or [h]))
                out.append({"username": h, "text": text, "timestamp": ts})
                continue
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
                        bias = [1 + (int(hashlib.md5(f"{pack.get('event')}{w}".encode()).hexdigest(), 16) % 100) / 40 for w in ws]
                        word = self.rng.choices(ws, bias)[0]
                    else:
                        word = self.rng.choice(ws)
            if self.rng.random() < 0.04:
                out.append({"username": h, "text": "STATUS", "timestamp": ts})
            war = "FIGHT" in pack["commands"]
            if self.rng.random() < (0.06 if war else 0.015):
                job = "soldier" if war else self.rng.choice(JOB_NAMES + ["thief", "healer", "priest", "smuggler",
                                                                          "hunter", "jester", "beekeeper"])
                out.append({"username": h, "text": f"BECOME {job.upper()}", "timestamp": ts})
            if word is None:
                if self.rng.random() < 0.3:
                    out.append({"username": h, "text": self.rng.choice(["first", "love this", "who runs this",
                                                                         "the king is sus"]), "timestamp": ts})
                continue
            out.append({"username": h, "text": word.lower() if self.rng.random() < 0.2 else word
                        + self.rng.choice(FLAVOR), "timestamp": ts})
        return out
