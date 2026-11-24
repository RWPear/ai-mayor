"""Emberfall as a whole: Aldric's purse, the corners of the settlement, events and history - plus the living
world (city.living) and everyone in it (city.citizens). Saved as one JSON file next to the people arrays.

(In the code a corner of the settlement is a "ward": Riverside, Hillfoot, Woodedge - where raids land.)
"""
import json
import random
from pathlib import Path

import numpy as np
import yaml

from .citizens import Citizens
from .config import CONTENT

SERVICES = ["defense", "food", "roads", "festivals"]
SERVICE_LABEL = {"defense": "Walls & guards", "food": "Granaries", "roads": "Roads & trade",
                 "festivals": "Taverns & festivals"}

# how much each faction cares about each service, and how much taxes hurt them
FACTION_WANTS = {
    "commoners": {"food": 0.4, "defense": 0.25, "festivals": 0.2, "roads": 0.15},
    "guilds": {"roads": 0.4, "defense": 0.3, "festivals": 0.15, "food": 0.15},
    "army": {"defense": 0.45, "food": 0.3, "festivals": 0.15, "roads": 0.1},
}
TAX_PAIN = {"commoners": 1.0, "guilds": 1.6, "army": 0.8}

WARD_NAMES = ["Millbrook", "Stonehollow", "Ashford", "Thornwick", "Greywater", "Oakridge", "Ravenmoor",
              "Kettle Hill", "Wolfden", "Saltmarsh", "Highcrag", "Briarwood", "Fenwick", "Ironmere", "Goldfield",
              "Frostvale", "Duskwood", "Copperhold", "Elderglen", "Kingsreach"]
WARD_TRAITS = {"frontier": {"defense": -0.12}, "fertile": {"food": 0.15}, "market town": {"roads": 0.1, "defense": -0.05},
               "mining": {"food": -0.05, "roads": 0.1}, "forest": {"festivals": 0.05, "roads": -0.1},
               "coastal": {"food": 0.1, "defense": -0.05}, "fortified": {"defense": 0.12}}


def load_yaml(name):
    f = CONTENT / name
    return yaml.safe_load(f.read_text()) if f.exists() else []


class City:
    def __init__(self, cfg, name="Emberfall", seed=1):
        self.cfg = cfg
        self.name = name
        self.day = 0
        self.season = 1
        self.rng = random.Random(seed)
        self.treasury = float(cfg.get("frontier_gold", 15))     # Aldric's purse
        self.quality = {s: 0.8 for s in SERVICES}   # (only "defense" still matters: how hard raids are)
        self.economy = 1.0
        self.wards = []
        self.events = []          # active events
        self.event_log = []       # finished events
        self.history = []         # one row of stats per day
        self.mayor = {"name": "King Aldric", "term": 1}   # the ruler (AI): his journal lives here
        self.pack = None
        self.scheduled = []       # events queued by you or as follow-ups
        self.living = None        # the living world (clock, minds, war camp, moments) - see city/living/
        self.citizens = Citizens()
        for _ in range(cfg["first_wards"]):
            self.add_ward()

    # ------------------------------------------------------------------ wards
    def add_ward(self):
        i = len(self.wards)
        if i < len(WARD_NAMES):
            name = WARD_NAMES[i]
        else:  # big kingdoms: combine name parts, e.g. "North Ashford", "Upper Kettle Hill"
            pre = ["North", "South", "East", "West", "Upper", "Lower", "New", "Old", "Little", "Far"]
            base = WARD_NAMES[(i - len(WARD_NAMES)) % len(WARD_NAMES)]
            k = (i - len(WARD_NAMES)) // len(WARD_NAMES)
            name = f"{pre[k % len(pre)]} {base}" + (f" {k // len(pre) + 2}" if k >= len(pre) else "")
        trait = self.rng.choice(list(WARD_TRAITS))
        self.wards.append({"name": name, "trait": trait, "mods": dict(WARD_TRAITS[trait]), "councilor": None,
                           "unrest": 0.0, "protest": 0})

    def ward_for(self, n):
        """Assigns n newcomers to wards, filling each up to ward_cap and opening new ones as needed."""
        cap = self.cfg["ward_cap"]
        counts = list(np.bincount(self.citizens.ward[self.citizens.active()], minlength=len(self.wards)))
        out = []
        for _ in range(n):
            open_w = [w for w, c in enumerate(counts) if c < cap]
            if not open_w:
                self.add_ward()
                counts.append(0)
                open_w = [len(self.wards) - 1]
            w = min(open_w, key=lambda x: counts[x])
            counts[w] += 1
            out.append(w)
        return out

    # ------------------------------------------------------------------ stats
    def population(self):
        return int(self.citizens.active().sum())

    def approval(self):
        a = self.citizens.active()
        return float(self.citizens.loyalty[a].mean()) if a.any() else 0.5

    def faction_moods(self):
        c, a = self.citizens, self.citizens.active()
        out = {}
        for i, f in enumerate(FACTION_WANTS):
            m = a & (c.faction == i)
            out[f] = round(float(c.mood[m].mean()), 3) if m.any() else None
        return out

    def ward_stats(self):
        c, a = self.citizens, self.citizens.active()
        rows = []
        for i, w in enumerate(self.wards):
            m = a & (c.ward == i)
            n = int(m.sum())
            rows.append({"id": i, "name": w["name"], "trait": w["trait"], "pop": n,
                         "mood": round(float(c.mood[m].mean()), 3) if n else None,
                         "approval": round(float(c.loyalty[m].mean()), 3) if n else None,
                         "unrest": round(w["unrest"], 3), "protest": w["protest"],
                         "councilor": w["councilor"]})
        return rows

    # ------------------------------------------------------------------ save / load
    STATE_KEYS = ["name", "day", "season", "treasury", "quality", "economy", "wards", "events", "event_log",
                  "history", "mayor", "pack", "scheduled", "living"]

    def save(self, path):
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        state = {k: getattr(self, k) for k in self.STATE_KEYS}
        state["rng"] = self.rng.getstate()
        (path / "city.json").write_text(json.dumps(state, default=_jsonable))
        self.citizens.save(path)

    @classmethod
    def load(cls, path, cfg):
        path = Path(path)
        state = json.loads((path / "city.json").read_text())
        c = cls(cfg, state["name"])
        for k in cls.STATE_KEYS:
            if k in state:  # older saves may not have newer keys
                setattr(c, k, state[k])
        rs = state["rng"]
        c.rng.setstate((rs[0], tuple(rs[1]), rs[2]))
        c.citizens = Citizens.load(path)
        return c


def _jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, tuple):
        return list(o)
    raise TypeError(type(o))
