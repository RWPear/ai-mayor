"""The storyteller (RimWorld-style director) plus everything about events.

Events come from three places:
  1. the season plan  - beats you wrote ("day 8: tech_hq")          -> see city/plan.py
  2. you, by hand     - `python -m city.run event start tech_hq`    -> schedule()/start()
  3. the storyteller  - when the city gets too calm for this point in the season
And one more: follow-ups. An event's outcome (or the mayor's option) can name a
`next` event a few days later, so stories branch on what the crowd did.

Events run for a few days. Citizens help or hinder with that day's comment
words; the mayor can pick one of the event's options. Enough help -> on_help.
Out of time -> on_timeout.

Text placeholders: {ward}, {councilor} (that ward's councilor's @handle),
{resident} (a random resident's @handle, from the ward if there is one).
"""
import numpy as np

from . import effects
from .model import SERVICES, load_yaml
from .roles import FACTIONS

EVENTS = None


def catalog(reload=False):
    global EVENTS
    if EVENTS is None or reload:
        EVENTS = {e["id"]: e for e in load_yaml("events.yaml")}
    return EVENTS


# ---------------------------------------------------------------------------- conditions
def stats_ns(city):
    fm = city.faction_moods()
    results = {}
    for e in city.event_log:
        results[e["id"]] = e.get("result")
    ns = {"pop": city.population(), "approval": city.approval(), "treasury": city.treasury,
          "tax": city.tax_rate, "economy": city.economy, "day": city.day,
          "season": city.season, "season_day": (city.day - 1) % city.cfg["season_days"] + 1,
          "unrest": max([w["unrest"] for w in city.wards] or [0]),
          "has": lambda m: m in city.milestones,
          "happened": lambda eid: eid in results,
          "result": lambda eid: results.get(eid),
          "active": lambda eid: any(a["id"] == eid for a in city.events),
          "built": lambda pid: any(p["id"] == pid and p["status"] == "done" for p in city.projects)}
    ns.update({f"q_{s}": city.quality[s] for s in SERVICES})
    ns.update({f"faction_{f}": (fm.get(f) if fm.get(f) is not None else 0.5) for f in FACTIONS})
    return ns


def condition_ok(city, expr):
    if not expr:
        return True
    # content files are your own; eval runs with no builtins and only city stats in scope
    try:
        return bool(eval(str(expr), {"__builtins__": {}, "min": min, "max": max}, stats_ns(city)))
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------- pacing
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


def maybe_start_event(city, quiet=False):
    """Random events. quiet=True when the season plan has something coming up soon."""
    mode = (city.plan or {}).get("storyteller", "on")
    if mode == "off" or (mode == "fill" and quiet):
        return None
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
    pool = [e for e in catalog().values() if e["id"] not in recent and not e.get("planned_only")
            and condition_ok(city, e.get("when"))]
    if not pool:
        return None
    ev = city.rng.choices(pool, weights=[e.get("weight", 1) for e in pool])[0]
    return start(city, ev, source="storyteller")


# ---------------------------------------------------------------------------- starting / scheduling
def _ward_index(city, name):
    if name is None or name == "":
        return None
    for i, w in enumerate(city.wards):
        if w["name"].lower() == str(name).lower():
            return i
    return None


def _names(city, ward):
    c = city.citizens
    names = {"ward": city.wards[ward]["name"] if ward is not None else "the city"}
    if ward is not None and city.wards[ward].get("councilor") is not None:
        names["councilor"] = "@" + c.handles[city.wards[ward]["councilor"]]
    else:
        councilors = [w["councilor"] for w in city.wards if w.get("councilor") is not None]
        names["councilor"] = "@" + c.handles[city.rng.choice(councilors)] if councilors else "a councilor"
    mask = c.active() & (c.ward == ward) if ward is not None else c.active()
    pool = np.where(mask)[0]
    names["resident"] = "@" + c.handles[int(city.rng.choice(pool.tolist()))] if len(pool) else "a resident"
    return names


def fmt(text, active):
    try:
        return str(text).format(**active.get("names", {"ward": "the city"}))
    except (KeyError, IndexError, ValueError):
        return str(text)


def start(city, ev, ward=None, source="storyteller"):
    """Starts an event now. ev is an event dict or id. ward: index or name (else picked)."""
    if isinstance(ev, str):
        ev = catalog().get(ev)
        if not ev:
            return None
    if any(a["id"] == ev["id"] for a in city.events):
        return None  # already running
    if isinstance(ward, str):
        ward = _ward_index(city, ward)
    if ev.get("scope") != "ward":
        ward = None
    elif ward is None and city.wards:
        prefer = [i for i, w in enumerate(city.wards) if w["trait"] == ev.get("ward_trait")]
        ward = city.rng.choice(prefer or list(range(len(city.wards))))
    active = {"id": ev["id"], "ward": ward, "started": city.day, "source": source,
              "days_left": ev.get("days", 3), "progress": 0.0, "option": None, "outcome": None}
    active["names"] = _names(city, ward)
    active["title"] = fmt(ev["title"], active)
    effects.apply(city, ev.get("on_start"), ward)
    city.events.append(active)
    return active


def schedule(city, event_id, day, ward=None, source="you"):
    """Queues an event so it's the subject of day `day`'s post (it starts at the end of day-1)."""
    city.scheduled.append({"event": event_id, "day": int(day), "ward": ward, "source": source})
    city.scheduled.sort(key=lambda s: s["day"])


def start_due(city):
    """Starts everything scheduled for tomorrow's post (ignores cooldowns - you asked for it)."""
    started = []
    due = [s for s in city.scheduled if s["day"] <= city.day + 1]
    for s in due:
        city.scheduled.remove(s)
        a = start(city, s["event"], s.get("ward"), source=s.get("source", "plan"))
        if a:
            started.append(a)
    return started


def end(city, event_id, text=None):
    """Ends an active event by hand (no outcome effects)."""
    a = next((e for e in city.events if e["id"] == event_id), None)
    if not a:
        return None
    a.update(outcome=text or f'{a["title"]} is over.', result="ended", ended=city.day)
    city.events.remove(a)
    city.event_log.append(a)
    return a


def _follow_up(city, nxt, active):
    """`next: {event: rival_war, in_days: 3, ward: same}` (or just `next: rival_war`)."""
    if not nxt:
        return
    if isinstance(nxt, str):
        nxt = {"event": nxt}
    ward = nxt.get("ward", "same")
    if ward == "same":
        ward = city.wards[active["ward"]]["name"] if active["ward"] is not None else None
    schedule(city, nxt["event"], city.day + 1 + int(nxt.get("in_days", 1)), ward, source=f"after {active['id']}")


# ---------------------------------------------------------------------------- running
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
        votes = dict(ctx.event_votes.get(a["id"], {"help": 0, "hinder": 0}))
        if "*" in ctx.event_votes:  # pack without a named event: help counts for every active event
            for k in ("help", "hinder"):
                votes[k] = votes.get(k, 0) + ctx.event_votes["*"][k]
        need = ev.get("help_needed", 0.5)
        # progress: share of the whole city helping, minus hinderers, measured against what's needed
        a["progress"] = float(np.clip(a["progress"] + (votes["help"] - 0.7 * votes["hinder"])
                                      / (pop * need * city.cfg["event_effort"]), 0, 1.5))
        a["days_left"] -= 1
        scope = "loyalty.ward" if a["ward"] is not None else "loyalty"
        if a["progress"] >= 1.0:
            out = ev.get("on_help", {})
            effects.apply(city, out, a["ward"])
            effects.apply(city, {scope: city.cfg["helped_bonus"]}, a["ward"])
            a["outcome"] = fmt(out.get("text") or "The city pulled together.", a)
            a["result"] = "helped"
        elif a["days_left"] <= 0:
            out = ev.get("on_timeout", {})
            effects.apply(city, out, a["ward"])
            if not a.get("option"):  # nobody fixed it and the mayor never responded
                effects.apply(city, {scope: -city.cfg["timeout_penalty"] * (2 if a["ward"] is not None else 1)},
                              a["ward"])
            a["outcome"] = fmt(out.get("text") or "It passed.", a)
            a["result"] = "timed_out"
        else:
            continue
        a["ended"] = city.day
        city.events.remove(a)
        city.event_log.append(a)
        _follow_up(city, out.get("next"), a)
        done.append(a)
    city.event_log = city.event_log[-300:]
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
    active["option"] = option_id
    active["option_text"] = fmt(opt.get("text", opt["label"]), active)
    if opt.get("ends"):
        active["outcome"] = active["option_text"]
        active["result"] = "mayor"
        active["ended"] = city.day
        city.events.remove(active)
        city.event_log.append(active)
    _follow_up(city, opt.get("next"), active)
    return active
