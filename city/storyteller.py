"""The storyteller (RimWorld-style director) plus everything about events.

Events come from three places:
  1. the season plan  - beats you wrote ("day 8: bandits")          -> see city/plan.py
  2. you, by hand     - `python -m city.run event start bandits`    -> schedule()/start()
  3. the storyteller  - when the kingdom gets too calm for this point in the season
And one more: follow-ups. An event's outcome (or the king's option) can name a
`next` event a few days later, so stories branch on what the crowd did.

Two kinds of event:
  - help/hinder events: subjects help or hinder with the post's words; the king can
    pick one of the event's options. Enough help -> on_help. Out of time -> on_timeout.
  - decree votes (`choices:`): the comment words ARE the vote (WALLS vs GRANARY).
    When it closes the crowd's pick wins - unless the king backed the other side
    (an option with `side:`), in which case the king wins and the people remember.

The king only gets to respond after an event has had at least one post, so the
crowd always gets the first say.

Text placeholders: {hold}, {lord} (that hold's lord's @handle), {resident} (a
random subject's @handle, from the hold if there is one). {ward}/{councilor} still work.
"""
import numpy as np

from . import effects
from .model import SERVICES, load_yaml
from .roles import FACTIONS

EVENTS = None


def _normalise(e):
    """Content may say hold/hold_trait; the engine says ward/ward_trait."""
    if e.get("scope") == "hold":
        e["scope"] = "ward"
    if e.get("hold_trait") and not e.get("ward_trait"):
        e["ward_trait"] = e["hold_trait"]
    if e.get("choices"):
        e["choices"] = {str(k).upper(): (v or {}) for k, v in e["choices"].items()}
    return e


CUSTOM = {}   # events the minds invented (decrees written by the king) - stored in the save, merged in here


def catalog(reload=False):
    global EVENTS
    if EVENTS is None or reload:
        EVENTS = {e["id"]: _normalise(e) for e in load_yaml("events.yaml")}
    EVENTS.update(CUSTOM)
    return EVENTS


def register(ev):
    """Adds an invented event to the catalog (it must already be validated)."""
    CUSTOM[ev["id"]] = _normalise(ev)
    catalog()[ev["id"]] = CUSTOM[ev["id"]]
    return CUSTOM[ev["id"]]


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
    camp = (getattr(city, "living", None) or {}).get("warcamp") or {}
    ns.update({f"camp_{k}": camp.get(k, 0) for k in ("warriors", "food", "morale", "raids_won", "raids_lost")})
    ns["camp_arrived"] = camp.get("arrived") or 999
    rooms = ((getattr(city, "living", None) or {}).get("town") or {}).get("rooms", {})
    ns["room"] = lambda r: bool(rooms.get(r))
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
    if (getattr(city, "living", None) or {}).get("director"):
        return None          # the living world's director invents events instead of drawing from the list
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
    names = {"ward": city.wards[ward]["name"] if ward is not None else "the kingdom"}
    if ward is not None and city.wards[ward].get("councilor") is not None:
        names["councilor"] = "@" + c.handles[city.wards[ward]["councilor"]]
    else:
        lords = [w["councilor"] for w in city.wards if w.get("councilor") is not None]
        names["councilor"] = "@" + c.handles[city.rng.choice(lords)] if lords else "a lord"
    mask = c.active() & (c.ward == ward) if ward is not None else c.active()
    pool = np.where(mask)[0]
    names["resident"] = "@" + c.handles[int(city.rng.choice(pool.tolist()))] if len(pool) else "a subject"
    names["hold"], names["lord"] = names["ward"], names["councilor"]
    living = getattr(city, "living", None) or {}
    names["warlord"] = (living.get("agents", {}).get("warlord") or {}).get("name", "the warlord")
    return names


def fmt(text, active):
    try:
        return str(text).format(**active.get("names", {"ward": "the kingdom", "hold": "the kingdom"}))
    except (KeyError, IndexError, ValueError):
        return str(text)


def start(city, ev, ward=None, source="storyteller", strength=1.0, extra=None):
    """Starts an event now. ev is an event dict or id. ward: index or name (else picked).
    strength scales how much help it needs (a raid with more warriors is harder to beat)."""
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
        if any(k in str(ev.get("title", "")) for k in ("{lord}", "{councilor}")):   # a story about a lord
            prefer = [i for i, w in enumerate(city.wards) if w.get("councilor") is not None] or prefer
        ward = city.rng.choice(prefer or list(range(len(city.wards))))
    active = {"id": ev["id"], "ward": ward, "started": city.day, "source": source,
              "days_left": ev.get("days", 3), "progress": 0.0, "option": None, "outcome": None,
              "uid": f"{ev['id']}-{city.day}-{len(city.event_log) + len(city.events)}", "strength": float(strength)}
    active.update(extra or {})
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
    """`next: {event: barbarian_horde, in_days: 0, hold: same}` (or just `next: barbarian_horde`)."""
    if not nxt:
        return
    if isinstance(nxt, str):
        nxt = {"event": nxt}
    ward = nxt.get("hold", nxt.get("ward", "same"))
    if ward == "same":
        ward = city.wards[active["ward"]]["name"] if active["ward"] is not None else None
    schedule(city, nxt["event"], city.day + 1 + int(nxt.get("in_days", 1)), ward, source=f"after {active['id']}")


# ---------------------------------------------------------------------------- running
def _close(city, a, text, result):
    a["outcome"] = str(text)
    a["result"] = result
    a["ended"] = city.day
    city.events.remove(a)
    city.event_log.append(a)


def _score(tally):
    """'WALLS 33 to GRANARY 18' - the whole vote, every day it was open."""
    return " to ".join(f"{w} {n:.0f}" for w, n in sorted(tally.items(), key=lambda kv: -kv[1]))


def _resolve_vote(city, ev, a, ctx):
    """A decree vote closes: the crowd's pick wins unless the king backed the other side."""
    cfg, c = city.cfg, city.citizens
    tally = a.get("tally", {})
    crowd = max(tally, key=tally.get) if tally and max(tally.values()) > 0 else None
    side = a.get("side")
    winner = side or crowd or ev.get("default") or next(iter(ev["choices"]))
    out = dict(ev["choices"].get(winner) or {})
    effects.apply(city, out, a["ward"])
    scope = "loyalty.ward" if a["ward"] is not None else "loyalty"
    text = fmt(out.get("text") or f"{winner} it is.", a)
    if side and crowd and side == crowd:
        effects.apply(city, {scope: cfg["heed_bonus"]}, a["ward"])
        text += f" The king heeded his people ({_score(tally)})."
    elif not side and crowd:
        text += f" The people decided ({_score(tally)})."
    elif side and crowd:
        effects.apply(city, {scope: -cfg["overrule_penalty"]}, a["ward"])
        losers = [c.index[u] for u, w in ctx.actions.items() if w == crowd and u in c.index]
        if losers:
            idx = np.array(losers, np.int64)
            c.loyalty[idx] = np.clip(c.loyalty[idx] - cfg["overrule_penalty"], 0, 1)
        text += f" The people voted {crowd} ({_score(tally)}). The king overruled them."
    a["winner"], a["crowd"] = winner, crowd
    _close(city, a, text, winner)
    return out.get("next")


def tick(city, ctx):
    """Runs every active event for one day. Returns list of resolved events."""
    done = []
    pop = max(1, city.population())
    c = city.citizens
    for a in list(city.events):
        ev = catalog().get(a["id"])
        if not ev:
            city.events.remove(a)
            continue
        if a["started"] >= city.day:   # began after today's post went up: its first post is tomorrow
            continue
        effects.apply(city, ev.get("while"), a["ward"], ctx, daily=True)
        votes = dict(ctx.event_votes.get(a["id"], {"help": 0, "hinder": 0, "choices": {}}))
        if "*" in ctx.event_votes:  # pack without a named event: help counts for every active event
            for k in ("help", "hinder"):
                votes[k] = votes.get(k, 0) + ctx.event_votes["*"][k]
        a["days_left"] -= 1
        a["last_votes"] = {"help": round(votes.get("help", 0)), "hinder": round(votes.get("hinder", 0))}

        if ev.get("choices"):                                        # ---- decree vote
            tally = a.setdefault("tally", {w: 0 for w in ev["choices"]})
            for w, n in (votes.get("choices") or {}).items():
                tally[w] = tally.get(w, 0) + n
            if a["days_left"] > 0:
                continue
            nxt = _resolve_vote(city, ev, a, ctx)
            _follow_up(city, nxt, a)
            done.append(a)
            continue

        if ev.get("champions"):                                      # ---- battle deeds
            helped = ctx.helpers.get(a["id"], [])
            if helped:
                idx = np.array(helped, np.int64)
                c.counts["battles"][idx] += 1
        need = ev.get("help_needed", 0.5) * a.get("strength", 1.0)
        # progress: share of the whole kingdom helping, minus hinderers, measured against what's needed
        a["progress"] = float(np.clip(a["progress"] + (votes["help"] - 0.7 * votes["hinder"])
                                      / (pop * need * city.cfg["event_effort"]), 0, 1.5))
        scope = "loyalty.ward" if a["ward"] is not None else "loyalty"
        if a["progress"] >= 1.0:
            out = ev.get("on_help", {})
            effects.apply(city, out, a["ward"])
            effects.apply(city, {scope: city.cfg["helped_bonus"]}, a["ward"])
            _close(city, a, fmt(out.get("text") or "The kingdom pulled together.", a), "helped")
        elif a["days_left"] <= 0:
            out = ev.get("on_timeout", {})
            effects.apply(city, out, a["ward"])
            if not a.get("option"):  # nobody fixed it and the king never responded
                effects.apply(city, {scope: -city.cfg["timeout_penalty"] * (2 if a["ward"] is not None else 1)},
                              a["ward"])
            _close(city, a, fmt(out.get("text") or "It passed.", a), "timed_out")
        else:
            continue
        _follow_up(city, out.get("next"), a)
        done.append(a)
    city.event_log = city.event_log[-300:]
    return done


def can_respond(city, active):
    """The king answers only after the crowd has had at least one post on it."""
    return active.get("started", city.day) < city.day and not active.get("option")


def choose_option(city, active, option_id):
    """The king's response to an active event."""
    ev = catalog().get(active["id"])
    opt = next((o for o in (ev or {}).get("options", []) if o["id"] == option_id), None)
    if not opt or not can_respond(city, active):
        return None
    pop = max(1, city.population())
    cost = float(opt.get("cost_pc", 0)) * pop
    if cost > 0 and city.treasury - cost < -city.cfg["debt_limit_pc"] * pop:
        return None  # can't afford it
    city.treasury -= cost
    effects.apply(city, opt.get("effects"), active["ward"])
    prog = (opt.get("effects") or {}).get("progress")
    if prog:
        active["progress"] = float(np.clip(active.get("progress", 0) + float(prog), 0, 1.5))
    active["option"] = option_id
    active["option_text"] = fmt(opt.get("text", opt["label"]), active)
    if opt.get("side"):
        active["side"] = str(opt["side"]).upper()
    if opt.get("ends") and not ev.get("choices"):
        _close(city, active, active["option_text"], "mayor")
    _follow_up(city, opt.get("next"), active)
    return active
