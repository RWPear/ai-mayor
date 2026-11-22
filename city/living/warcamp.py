"""The warlord's side of the map: a war camp in the frozen north.

The camp is a small economy of its own. Warriors eat food. Food comes from
hunting and from raiding Emberfall. Morale rises with victories and falls with
defeats and hunger. The warlord reads all of this and decides when and where to
strike - nobody schedules the war.

A raid starts a real event in the kingdom (the same events the crowd fights in
the comments). How strong it is depends on how many warriors he sends and
whether the hold has a garrison. When the event resolves, the camp feels it.
"""
import numpy as np

START = {"name": "the Frostfang camp", "warriors": 40, "food": 120, "morale": 0.6, "intel": {},
         "raids_won": 0, "raids_lost": 0, "active_raid": None, "last_result_seen": 0, "defeated": False}


def camp(city):
    return city.living["warcamp"]


def strength(city, warriors, ward=None):
    """How hard a raid is to fight off: warriors against the size of the kingdom (or the hold), its
    defense, and a garrison. 1.0 = an ordinary event; 2.0 = brutal."""
    pop = max(30, city.population())   # anyone in the kingdom can come to a hold's defense
    ratio = warriors / (pop * 0.4)
    # sqrt: twice the warriors is a lot harder, not twice as hard; luck: no battle is a sure thing
    s = (0.55 + 0.55 * ratio ** 0.5) * (1.15 - 0.15 * city.quality["defense"]) * city.rng.uniform(0.85, 1.15)
    if ward is not None and city.wards[ward].get("garrison_until", -1) >= city.day:
        s *= 0.75
    return float(np.clip(s, 0.5, 2.0))


def cap(c, day=0):
    """How many warriors the camp can hold: tribes drift in over the season, and word of victories brings more."""
    return max(40, int(50 + 2 * day + 25 * c["raids_won"] - 10 * c["raids_lost"]))


def daily_upkeep(city):
    """Once a day: warriors eat; hunger costs morale and deserters; morale drifts back toward normal."""
    c = camp(city)
    c["morale"] += (0.5 - c["morale"]) * 0.1
    eat = c["warriors"] * 0.5
    if c["food"] >= eat:
        c["food"] -= eat
    else:
        short = (eat - c["food"]) / max(1, eat)
        c["food"] = 0
        c["morale"] = max(0.0, c["morale"] - 0.15 * short)
        c["warriors"] = max(5, int(c["warriors"] * (1 - 0.1 * short)))
        return f"Hunger in {c['name']}. {int(c['warriors'])} warriors left, and they are angry."
    return None


def settle(city):
    """Called every tick: if one of the warlord's raids just resolved, the camp feels it. Returns a moment text."""
    c = camp(city)
    rid = c.get("active_raid")
    if not rid:
        return None
    done = next((e for e in reversed(city.event_log) if e.get("uid") == rid), None)
    if not done:
        if not any(e.get("uid") == rid for e in city.events):
            c["active_raid"] = None
        return None
    c["active_raid"] = None
    sent = done.get("warriors_sent", 0)
    if done["result"] in ("helped", "mayor"):
        lost = int(sent * (0.6 if done["id"] == "barbarian_horde" else 0.35))
        c["warriors"] = max(5, c["warriors"] - lost)
        c["morale"] = max(0.0, c["morale"] - (0.35 if done["id"] == "barbarian_horde" else 0.15))
        c["raids_lost"] += 1
        if done["id"] == "barbarian_horde":
            c["defeated"] = c["warriors"] < 25
        return (f"The raid failed. {lost} warriors never came home to {c['name']}. "
                f"The warlord broke a table.")
    loot = sent * 1.0
    c["food"] += loot
    c["warriors"] += int(sent * 0.1)
    c["morale"] = min(1.0, c["morale"] + 0.15)
    c["raids_won"] += 1
    return f"The raiders came home with {loot:.0f} sacks of grain and {int(sent * 0.1)} new recruits. The camp feasts."
