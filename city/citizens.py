"""Every citizen is a row in a set of numpy arrays, so the daily update is a
handful of vector operations whether there are 50 people or 100,000.
No language model ever looks at an individual citizen.
"""
import json

import numpy as np

from .roles import FACTIONS, JOBS, JOB_NAMES, _h, identity, title_for

COUNTERS = ["work", "protest", "shop", "volunteer", "donate", "support", "oppose", "commands"]
ACTIVE, LEFT = 0, 1


class Citizens:
    def __init__(self):
        self.handles, self.names = [], []
        self.index = {}
        z = lambda dt: np.zeros(0, dtype=dt)
        self.job, self.faction, self.ward = z(np.int16), z(np.int8), z(np.int32)
        self.wealth, self.mood, self.loyalty, self.activism = z(np.float32), z(np.float32), z(np.float32), z(np.float32)
        self.low_days, self.status = z(np.int16), z(np.int8)
        self.temper = z(np.float32)   # personal outlook: some people are just grumpier (stable per handle)
        self.joined, self.last_cmd = z(np.int32), z(np.int32)
        self.counts = {k: z(np.int32) for k in COUNTERS}
        self.today = {}          # per-day command flags, rebuilt each day
        self.story = {}          # idx -> last few things that happened to them

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
        self.joined = cat([self.joined, np.full(n, day, np.int32)])
        self.last_cmd = cat([self.last_cmd, np.full(n, -1, np.int32)])
        for k in COUNTERS:
            self.counts[k] = cat([self.counts[k], np.zeros(n, np.int32)])
        return np.concatenate([np.arange(start, start + n), np.array(back, dtype=np.int64)])

    # ------------------------------------------------------------------ helpers
    def active(self):
        return self.status == ACTIVE

    def wage(self):
        table = np.array([JOBS[j][1] for j in JOB_NAMES], np.float32)
        return table[self.job]

    def log(self, i, day, text):
        s = self.story.setdefault(int(i), [])
        s.append(f"day {day}: {text}")
        del s[:-5]

    def counts_of(self, i):
        return {k: int(v[i]) for k, v in self.counts.items()}

    def title(self, i):
        return title_for(self.counts_of(i))

    # ------------------------------------------------------------------ save / load
    def save(self, path):
        arrays = {k: getattr(self, k) for k in ("job", "faction", "ward", "wealth", "mood", "loyalty", "activism",
                                                "low_days", "status", "joined", "last_cmd", "temper")}
        arrays.update({f"count_{k}": v for k, v in self.counts.items()})
        np.savez_compressed(path / "citizens.npz", **arrays)
        (path / "citizens.json").write_text(json.dumps({"handles": self.handles, "names": self.names,
                                                        "story": self.story}))

    @classmethod
    def load(cls, path):
        c = cls()
        meta = json.loads((path / "citizens.json").read_text())
        c.handles, c.names = meta["handles"], meta["names"]
        c.story = {int(k): v for k, v in meta.get("story", {}).items()}
        c.index = {h: i for i, h in enumerate(c.handles)}
        data = np.load(path / "citizens.npz")
        for k in ("job", "faction", "ward", "wealth", "mood", "loyalty", "activism", "low_days", "status",
                  "joined", "last_cmd"):
            setattr(c, k, data[k])
        c.counts = {k: data[f"count_{k}"] for k in COUNTERS}
        c.temper = data["temper"] if "temper" in data else np.array(
            [(_h(h, "temper") % 1000) / 1000 * 0.3 - 0.15 for h in c.handles], np.float32)
        return c
