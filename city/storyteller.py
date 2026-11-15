"""The storyteller (RimWorld-style director). It watches how tense the city is
and, when things get too calm for this point in the season, starts an event
from content/events.yaml. Tension is meant to ramp up toward each season's
finale, then reset.

Events run for a few days. Citizens can help or hinder through that day's
comment words; the mayor can pick one of the event's options. If enough of the
city helps, the event resolves well; if it runs out, it times out.
"""
import numpy as np

from . import effects
from .model import SERVICES, load_yaml
from .roles import FACTIONS

EVENTS = None


def catalog():
    global EVENTS
    if EVENTS is None:
        EVENTS = {e["id"]: e for e in load_yaml("events.yaml")}
    return EVENTS


def stats_ns(city):
    fm = city.faction_moods()
    ns = {"pop": city.population(), "approval": city.approval(), "treasury": city.treasury,
          "tax": city.tax_rate, "economy": city.economy, "day": city.day,
          "season_day": (city.day - 1) % city.cfg["season_days"] + 1,
          "unrest": max([w["unrest"] for w in city.wards] or [0]),
          "has": lambda m: m in city.milestones}
    ns.update({f"q_{s}": city.quality[s] for s in SERVICES})
    ns.update({f"faction_{f}": (fm.get(f) if fm.get(f) is not None else 0.5) for f in FACTIONS})
    return ns


def condition_ok(city, expr):
    if not expr:
        return True
    # content files are your own; eval runs with no builtins and only city stats in scope
    try:
        return bool(eval(expr, {"__builtins__": {}, "min": min, "max": max}, stats_ns(city)))
    except Exception:  # noqa: BLE001
        return False


def tension(city):
    """0 = sleepy, 1 = on fire."""
    a = city.citizens.active()
    if not a.any():
        return 0.0
    mood = float(city.citizens.mood[a].mean())
    unrest = float(np.mean([w["unrest"] for w in city.wards])) if city.wards else 0
    money = 0.3 if city.treasury < 0 else 0.0
    events = 0.18 * len(city.events)
    return float(np.clip((0.6 - mood) * 1.2 + unrest * 0.8 + money + events, 0, 1))


def target(city):
    cfg = city.cfg
    sd = (city.day - 1) % cfg["season_days"]
    frac = sd / max(1, cfg["season_days"] - 1)
    return cfg["tension_target_start"] + (cfg["tension_target_end"] - cfg["tension_target_start"]) * frac


def maybe_start_event(city):
    if len(city.events) >= city.cfg["max_active_events"] or city.population() < 5:
        return None
    last = max([e["started"] for e in city.events + city.event_log[-3:]] or [-99])
    if city.day - last < city.cfg["event_cooldown_days"]:
        return None
    t, goal = tension(city), target(city)
    # the further below the target, the likelier an event; a small chance of surprises even when tense
    chance = 0.1 if t >= goal else min(0.9, 0.25 + (goal - t) * 2)
    if city.rng.random() > chance:
        return None
    recent = {e["id"] for e in city.event_log[-6:]} | {e["id"] for e in city.events}
    pool = [e for e in catalog().values() if e["id"] not in recent and condition_ok(city, e.get("when"))]
    if not pool:
        return None
    ev = city.rng.choices(pool, weights=[e.get("weight", 1) for e in pool])[0]
    return start(city, ev)


def start(city, ev):
    ward = None
    if ev.get("scope") == "ward" and city.wards:
        prefer = [i for i, w in enumerate(city.wards) if w["trait"] == ev.get("ward_trait")]
        ward = city.rng.choice(prefer or list(range(len(city.wards))))
    wname = city.wards[ward]["name"] if ward is not None else ""
    active = {"id": ev["id"], "title": ev["title"].format(ward=wname), "ward": ward, "started": city.day,
              "days_left": ev.get("days", 3), "progress": 0.0, "option": None, "outcome": None}
    effects.apply(city, ev.get("on_start"), ward)
    city.events.append(active)
    return active


def tick(city, ctx):
    """Runs every active event for one day. Returns list of resolved events."""
    done = []
    pop = max(1, city.population())
    for a in list(city.events):
        ev = catalog().get(a["id"])
        if not ev:
            city.events.remove(a)
            continue
        effects.apply(city, ev.get("while"), a["ward"], ctx, daily=True)
        votes = ctx.event_votes.get(a["id"], {"help": 0, "hinder": 0})
        if "*" in ctx.event_votes:  # pack without a named event: help counts for every active event
            for k in ("help", "hinder"):
                votes[k] = votes.get(k, 0) + ctx.event_votes["*"][k]
        need = ev.get("help_needed", 0.5)
        # progress: share of the whole city helping, minus hinderers, measured against what's needed
        a["progress"] = float(np.clip(a["progress"] + (votes["help"] - 0.7 * votes["hinder"]) / (pop * need * 0.6),
                                      0, 1.5))
        a["days_left"] -= 1
        wname = city.wards[a["ward"]]["name"] if a["ward"] is not None else ""
        if a["progress"] >= 1.0:
            out = ev.get("on_help", {})
            effects.apply(city, out, a["ward"])
            a["outcome"] = (out.get("text") or "The city pulled together.").format(ward=wname)
            a["result"] = "helped"
        elif a["days_left"] <= 0:
            out = ev.get("on_timeout", {})
            effects.apply(city, out, a["ward"])
            a["outcome"] = (out.get("text") or "It passed.").format(ward=wname)
            a["result"] = "timed_out"
        else:
            continue
        a["ended"] = city.day
        city.events.remove(a)
        city.event_log.append(a)
        done.append(a)
    city.event_log = city.event_log[-200:]
    return done


def choose_option(city, active, option_id):
    """The mayor's response to an active event."""
    ev = catalog().get(active["id"])
    opt = next((o for o in (ev or {}).get("options", []) if o["id"] == option_id), None)
    if not opt or active.get("option"):
        return None
    pop = max(1, city.population())
    cost = float(opt.get("cost_pc", 0)) * pop
    if cost > 0 and city.treasury - cost < -city.cfg["debt_limit_pc"] * pop:
        return None  # can't afford it
    city.treasury -= cost
    effects.apply(city, opt.get("effects"), active["ward"])
    wname = city.wards[active["ward"]]["name"] if active["ward"] is not None else ""
    active["option"] = option_id
    active["option_text"] = opt.get("text", opt["label"]).format(ward=wname)
    if opt.get("ends"):
        active["outcome"] = active["option_text"]
        active["result"] = "mayor"
        active["ended"] = city.day
        city.events.remove(active)
        city.event_log.append(active)
    return active
