"""Every subject (citizen) is a row in a set of numpy arrays, so the daily update is a
handful of vector operations whether there are 50 people or 100,000.
No language model ever looks at an individual citizen.
"""
import json

import numpy as np

from .roles import FACTIONS, JOBS, JOB_NAMES, _h, a_job, identity, rank_for, title_for

COUNTERS = ["work", "protest", "shop", "volunteer", "donate", "support", "oppose", "commands", "train",
            "battles", "steal", "fight", "heal", "bless", "craft"]   # the last five are reputation (city/trades.py)
ACTIVE, LEFT, ROAD = 0, 1, 2      # ROAD: on the frontier, travelling to Emberfall (arrive weekly)


class Citizens:
    def __init__(self):
        self.handles, self.names = [], []
        self.index = {}
        z = lambda dt: np.zeros(0, dtype=dt)
        self.job, self.faction, self.ward = z(np.int16), z(np.int8), z(np.int32)
        self.wealth, self.mood, self.loyalty, self.activism = z(np.float32), z(np.float32), z(np.float32), z(np.float32)
        self.low_days, self.status = z(np.int16), z(np.int8)
        self.temper = z(np.float32)   # personal outlook: some people are just grumpier (stable per handle)
        self.walled = z(np.int8)      # 1 = house inside the town walls, 0 = outside, -1 = no house (homeless)
        self.burned = z(np.int16)     # day their house burned down (0 = it's standing)
        self.joined, self.last_cmd = z(np.int32), z(np.int32)
        self.counts = {k: z(np.int32) for k in COUNTERS}
        self.today = {}          # per-day command flags, rebuilt each day
        self.story = {}          # idx -> last few things that happened to them
        self.roles = {}          # idx -> their own role label ("thief", "rat catcher") if not one of the 19 trades
        self.role_book = {}      # role label -> its mechanics (city/trades.py), shared by everyone with that role
        self.role_day = {}       # idx -> day they last changed role (one new life a day)

    def __len__(self):
        return len(self.handles)

    # ------------------------------------------------------------------ joining
    def add_many(self, handles, day, ward_for, revive=True):
        """Adds new handles. Known handles are skipped; people who left come back only if revive=True
        (an explicit JOIN or command - just still following doesn't undo moving away)."""
        new, back, seen = [], [], set()
        for h in handles:
            h = h.strip().lstrip("@").lower()
            if not h or h in seen:
                continue
            seen.add(h)
            i = self.index.get(h)
            if i is None:
                new.append(h)
            elif self.status[i] == LEFT and revive:
                back.append(i)
        for i in back:
            self.status[i] = ACTIVE
            self.mood[i] = max(self.mood[i], 0.45)
            self.low_days[i] = 0
            self.log(i, day, "moved back to the city")
        if not new:
            return np.array(back, dtype=np.int64)
        start = len(self.handles)
        n = len(new)
        jobs, facs, names = [], [], []
        for h in new:
            name, job = identity(h)
            names.append(name)
            jobs.append(JOB_NAMES.index(job))
            facs.append(FACTIONS.index(JOBS[job][0]))
        wards = ward_for(n)
        self.handles += new
        self.names += names
        for k, h in enumerate(new):
            self.index[h] = start + k
        cat = np.concatenate
        self.job = cat([self.job, np.array(jobs, np.int16)])
        self.faction = cat([self.faction, np.array(facs, np.int8)])
        self.ward = cat([self.ward, np.array(wards, np.int32)])
        self.wealth = cat([self.wealth, np.full(n, 500.0, np.float32)])
        self.mood = cat([self.mood, np.full(n, 0.6, np.float32)])
        self.loyalty = cat([self.loyalty, np.full(n, 0.55, np.float32)])
        self.activism = cat([self.activism, np.zeros(n, np.float32)])
        self.low_days = cat([self.low_days, np.zeros(n, np.int16)])
        self.temper = cat([self.temper, np.array([(_h(h, "temper") % 1000) / 1000 * 0.3 - 0.15 for h in new],
                                                 np.float32)])
        self.status = cat([self.status, np.zeros(n, np.int8)])
        self.walled = cat([self.walled, np.zeros(n, np.int8)])
        self.burned = cat([self.burned, np.zeros(n, np.int16)])
        self.joined = cat([self.joined, np.full(n, day, np.int32)])
        self.last_cmd = cat([self.last_cmd, np.full(n, -1, np.int32)])
        for k in COUNTERS:
            self.counts[k] = cat([self.counts[k], np.zeros(n, np.int32)])
        return np.concatenate([np.arange(start, start + n), np.array(back, dtype=np.int64)])

    # ------------------------------------------------------------------ helpers
    def active(self):
        return self.status == ACTIVE

    def wage(self):
        from .trades import INCOME
        table = np.array([JOBS[j][1] for j in JOB_NAMES], np.float32)
        w = table[self.job]
        for i, lab in self.roles.items():
            rec = self.role_book.get(lab) or {}
            w[i] = INCOME.get(rec.get("income"), 60) * (1.2 if rec.get("knack") == "crafty" else 1.0)
        return w

    def label(self, i):
        """What they are, in their words: 'rat catcher', or one of the trades."""
        return self.roles.get(int(i)) or JOB_NAMES[int(self.job[i])]

    def role(self, i):
        """The mechanics of their role (None for the 19 standard trades)."""
        lab = self.roles.get(int(i))
        return self.role_book.get(lab) if lab else None

    def homeless(self, i):
        return int(self.walled[i]) == -1

    def log(self, i, day, text):
        s = self.story.setdefault(int(i), [])
        s.append(f"day {day}: {text}")
        del s[:-5]

    def counts_of(self, i):
        return {k: int(v[i]) for k, v in self.counts.items()}

    def title(self, i):
        return title_for(self.counts_of(i))

    def rank(self, i):
        return rank_for(self.counts_of(i))

    def set_job(self, i, job, day):
        """BECOME <JOB>: a new trade (and maybe a new faction). Returns True if it changed."""
        j = JOB_NAMES.index(job)
        had_role = self.roles.pop(int(i), None)
        if int(self.job[i]) == j and not had_role:
            return False
        self.job[i] = j
        self.faction[i] = FACTIONS.index(JOBS[job][0])
        if int(self.walled[i]) == -1:            # a trade comes with a roof: a hut outside the walls
            self.walled[i] = 0
        self.role_day[int(i)] = day
        self.log(i, day, f"became {a_job(job)}")
        return True

    def set_role(self, i, label, rec, day):
        """Any role at all (city/trades.py). rec is its mechanics from the role book."""
        if rec.get("job"):
            return self.set_job(i, rec["job"], day)
        i = int(i)
        if self.roles.get(i) == label:
            return False
        self.roles[i] = label
        self.role_book.setdefault(label, rec)
        base = rec.get("base") if rec.get("base") in JOBS else "farmer"
        self.job[i] = JOB_NAMES.index(base)
        self.faction[i] = FACTIONS.index(rec.get("faction")) if rec.get("faction") in FACTIONS else 0
        if rec.get("homeless"):
            self.walled[i] = -1
        elif int(self.walled[i]) == -1:
            self.walled[i] = 0
        self.role_day[i] = day
        self.log(i, day, f"took up the life of {a_job(label)}")
        return True

    # ------------------------------------------------------------------ save / load
    def save(self, path):
        arrays = {k: getattr(self, k) for k in ("job", "faction", "ward", "wealth", "mood", "loyalty", "activism",
                                                "low_days", "status", "joined", "last_cmd", "temper", "walled", "burned")}
        arrays.update({f"count_{k}": v for k, v in self.counts.items()})
        np.savez_compressed(path / "citizens.npz", **arrays)
        (path / "citizens.json").write_text(json.dumps({"handles": self.handles, "names": self.names,
                                                        "story": self.story, "roles": self.roles,
                                                        "role_book": self.role_book, "role_day": self.role_day}))

    @classmethod
    def load(cls, path):
        c = cls()
        meta = json.loads((path / "citizens.json").read_text())
        c.handles, c.names = meta["handles"], meta["names"]
        c.story = {int(k): v for k, v in meta.get("story", {}).items()}
        c.roles = {int(k): v for k, v in meta.get("roles", {}).items()}
        c.role_book = meta.get("role_book", {})
        c.role_day = {int(k): v for k, v in meta.get("role_day", {}).items()}
        c.index = {h: i for i, h in enumerate(c.handles)}
        data = np.load(path / "citizens.npz")
        for k in ("job", "faction", "ward", "wealth", "mood", "loyalty", "activism", "low_days", "status",
                  "joined", "last_cmd"):
            setattr(c, k, data[k])
        c.counts = {k: (data[f"count_{k}"] if f"count_{k}" in data else np.zeros(len(c.handles), np.int32))
                    for k in COUNTERS}
        c.walled = data["walled"] if "walled" in data else np.zeros(len(c.handles), np.int8)
        c.burned = data["burned"] if "burned" in data else np.zeros(len(c.handles), np.int16)
        c.temper = data["temper"] if "temper" in data else np.array(
            [(_h(h, "temper") % 1000) / 1000 * 0.3 - 0.15 for h in c.handles], np.float32)
        return c
