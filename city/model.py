"""The city as a whole: money, services, wards, factions, projects, events,
milestones and history. Saved as one JSON file next to the citizen arrays.
"""
import json
import random
from pathlib import Path

import numpy as np
import yaml

from .citizens import Citizens
from .config import CONTENT

SERVICES = ["safety", "housing", "transit", "culture"]
SERVICE_LABEL = {"safety": "Public safety", "housing": "Housing", "transit": "Transit", "culture": "Parks & culture"}

# how much each faction cares about each service, and how much taxes hurt them
FACTION_WANTS = {
    "labor": {"housing": 0.4, "safety": 0.25, "transit": 0.25, "culture": 0.1},
    "business": {"transit": 0.4, "safety": 0.35, "housing": 0.1, "culture": 0.15},
    "residents": {"culture": 0.35, "safety": 0.3, "housing": 0.2, "transit": 0.15},
}
TAX_PAIN = {"labor": 1.0, "business": 1.6, "residents": 0.8}

WARD_NAMES = ["Riverside", "Old Market", "Northgate", "Brickworks", "Hillcrest", "Union Square", "Lantern Row",
              "Foundry District", "Elm Park", "Harbor Point", "Copper Hill", "Southside", "Mill Creek",
              "Ironbridge", "Westfield", "Cedar Heights", "Canal Street", "Signal Yard", "Bellwood", "Kingsway"]
WARD_TRAITS = {"flood-prone": {"housing": -0.1}, "nightlife": {"culture": 0.15, "safety": -0.1},
               "historic": {"culture": 0.1, "transit": -0.1}, "industrial": {"housing": -0.05, "transit": 0.1},
               "leafy": {"culture": 0.1}, "busy": {"transit": 0.1, "safety": -0.05}, "quiet": {"safety": 0.1}}


def load_yaml(name):
    f = CONTENT / name
    return yaml.safe_load(f.read_text()) if f.exists() else []


class City:
    def __init__(self, cfg, name="New Harbor", seed=1):
        self.cfg = cfg
        self.name = name
        self.day = 0
        self.season = 1
        self.rng = random.Random(seed)
        self.treasury = cfg["start_treasury"]
        self.tax_rate = cfg["start_tax_rate"]
        self.spend_ratio = 1.0
        self.budget = {s: 0.25 for s in SERVICES}
        self.quality = {s: 0.8 for s in SERVICES}
        self.economy = 1.0
        self.wards = []
        self.events = []          # active events
        self.event_log = []       # finished events
        self.projects = []        # in progress / done
        self.milestones = []      # unlocked milestone ids
        self.petitions = []
        self.history = []         # one row of stats per day
        self.mayor = {"name": "Mayor Vale", "term": 1, "promises": []}
        self.pack = None
        self.scheduled = []       # events queued by you, the season plan, or follow-ups
        self.plan = None          # season plan settings + progress (see city/plan.py)
        self.citizens = Citizens()
        for _ in range(cfg["first_wards"]):
            self.add_ward()

    # ------------------------------------------------------------------ wards
    def add_ward(self):
        i = len(self.wards)
        if i < len(WARD_NAMES):
            name = WARD_NAMES[i]
        else:  # big cities: combine name parts, e.g. "North Copper", "Upper Mill Creek"
            pre = ["North", "South", "East", "West", "Upper", "Lower", "New", "Old", "Little", "Port"]
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
    STATE_KEYS = ["name", "day", "season", "treasury", "tax_rate", "spend_ratio", "budget", "quality", "economy",
                  "wards", "events", "event_log", "projects", "milestones", "petitions", "history", "mayor", "pack",
                  "scheduled", "plan"]

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
