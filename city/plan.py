"""Season plans: the path through a season, so every post isn't a guess.

A plan is a list of beats keyed by season day. Each beat can:
  event:    start an event so it's the subject of that day's post (optionally `hold:`)
  pack:     the post's commands: a pack file, inline {WORD: effect}, or "auto" (the event's own words)
  if/else:  only happen if a condition holds, otherwise do the `else:` beat instead
  agenda:   a note put in front of the king that day ("The guilds want an answer on the caravan")
  announce: a line that goes into the day's report and video script
  note:     prep notes for YOU (what to film, what to say) - shown in the calendar, never in the city

Between beats the storyteller fills gaps with random events (storyteller: fill), runs freely (on),
or stays quiet (off). Follow-up events from outcomes still happen either way.

    title: "The Crowning"
    storyteller: fill
    beats:
      - {day: 1, event: coronation, announce: "The gates are open!", note: "Launch post"}
      - {day: 5, event: first_decree, pack: auto}
      - {day: 12, if: "faction_commoners < 0.5", event: miners_strike, else: {event: tournament}}

A plan path can be one file (used every season) or a folder with season1.yaml, season2.yaml, ...
Plans are re-read every day, so you can edit the live plan and it takes effect tomorrow.
"""
from pathlib import Path

import yaml

from . import storyteller
from .config import ROOT


def _plan_file(city, season):
    if not city.plan or not city.plan.get("path"):
        return None
    p = Path(city.plan["path"])
    if not p.is_absolute():
        p = ROOT / p
    if p.is_dir():
        f = p / f"season{season}.yaml"
        return f if f.exists() else None
    return p if p.exists() else None


def load(city, season=None):
    f = _plan_file(city, season or city.season)
    if not f:
        return {"beats": []}
    data = yaml.safe_load(f.read_text()) or {}
    data.setdefault("beats", [])
    return data


def attach(city, path, storyteller_mode=None):
    """Points the city at a plan file or folder."""
    city.plan = {"path": str(path), "done": [], "agenda": [], "announce": []}
    data = load(city, city.season)
    city.plan["storyteller"] = storyteller_mode or data.get("storyteller", "fill")
    city.plan["title"] = data.get("title", "")


def season_and_day(city, absolute_day):
    sd = city.cfg["season_days"]
    return (absolute_day - 1) // sd + 1, (absolute_day - 1) % sd + 1


def beats_for(city, absolute_day):
    season, sday = season_and_day(city, absolute_day)
    data = load(city, season)
    out = []
    for i, b in enumerate(data["beats"]):
        if int(b.get("day", 0)) != sday:
            continue
        key = f"{season}:{sday}:{i}"
        if key in (city.plan or {}).get("done", []):
            continue
        if b.get("if") and not storyteller.condition_ok(city, b["if"]):
            b = dict(b.get("else") or {}, day=sday)
        out.append((key, b))
    return out


def quiet(city):
    """True if the plan has an event coming in the next two days (so random events hold off)."""
    for d in (city.day + 1, city.day + 2):
        if any(b.get("event") for _, b in beats_for(city, d)):
            return True
    return False


def prepare(city, absolute_day):
    """Applies the beats for `absolute_day`'s post: starts events, picks the pack, sets the agenda.
    Returns (pack or None, list of started events)."""
    if not city.plan:
        return None, []
    data = load(city, season_and_day(city, absolute_day)[0])
    city.plan["storyteller"] = data.get("storyteller", city.plan.get("storyteller", "fill"))
    city.plan["title"] = data.get("title", city.plan.get("title", ""))
    city.plan["agenda"], city.plan["announce"] = [], []
    pack, started = None, []
    from . import packs
    for key, b in beats_for(city, absolute_day):
        city.plan["done"].append(key)
        ev_active = None
        if b.get("event"):
            ev_active = storyteller.start(city, b["event"], b.get("hold", b.get("ward")), source="plan")
            if ev_active:
                started.append(ev_active)
        p = b.get("pack")
        if p == "auto" or (p is None and ev_active):
            ev = storyteller.catalog().get(b.get("event", ""))
            if ev and (ev.get("commands") or ev.get("choices")):
                pack = packs.from_event(ev)
        elif isinstance(p, dict):
            pack = {"post": f"plan-day{absolute_day}", "window_hours": 24, "event": b.get("event"),
                    "commands": {str(k).upper(): v for k, v in p.items()}, "caption": b.get("caption", "")}
        elif isinstance(p, str):
            pp = Path(p) if Path(p).is_absolute() else ROOT / p
            pack = packs.load(pp)
        if b.get("agenda"):
            city.plan["agenda"].append(b["agenda"])
        if b.get("announce"):
            city.plan["announce"].append(b["announce"])
    city.plan["done"] = city.plan["done"][-500:]
    return pack, started


def calendar(city, season=None):
    """Rows for the planner view: what's planned for each day of a season."""
    season = season or city.season
    data = load(city, season)
    rows = []
    for d in range(1, city.cfg["season_days"] + 1):
        for b in [x for x in data["beats"] if int(x.get("day", 0)) == d]:
            ev = storyteller.catalog().get(b.get("event", ""), {})
            alt = b.get("else") or {}
            rows.append({
                "day": d,
                "event": ev.get("title", b.get("event", "")),
                "if": b.get("if", ""),
                "else": storyteller.catalog().get(alt.get("event", ""), {}).get("title", alt.get("event", "")),
                "pack": (", ".join(str(k).upper() for k in b["pack"]) if isinstance(b.get("pack"), dict)
                         else b.get("pack", "auto" if b.get("event") else "")),
                "commands": ", ".join(w.upper() for w in (ev.get("commands") or {})) if b.get("event") else "",
                "announce": b.get("announce", ""), "agenda": b.get("agenda", ""), "note": b.get("note", ""),
            })
    return data, rows
