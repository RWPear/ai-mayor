"""One day of the city, start to finish. Used by both the test runner and the
live city, so what you test is exactly what runs.

  1. new followers move in (from an export, or the fake audience)
  2. the post's comments are read: actions, STATUS requests, JOINs
  3. command effects hit the citizens who commented
  4. events tick (help/hinder from comments counts here)
  5. the whole city simulates a day
  6. season finale: recall vote
  7. tomorrow's post is set up: scheduled events, season-plan beats, or a storyteller event
  8. the mayor decides tomorrow's policy and writes a diary
  9. reports: daily markdown, episode script, STATUS replies, next post's commands
"""
import numpy as np

from . import packs, plan, report, sim, storyteller
from .effects import DayContext
from .roles import JOB_NAMES

BASICS = {"WORK": "work", "PROTEST": "protest", "SHOP": "shop", "VOLUNTEER": "volunteer"}


def default_pack():
    return {"post": "daily", "window_hours": 24, "event": None, "commands": dict(BASICS), "caption": ""}


def election_pack():
    return {"post": "recall-vote", "window_hours": 24, "event": None,
            "commands": {"KEEP": "vote.keep", "RECALL": "vote.recall"}, "caption": ""}


def next_pack(city, plan_pack=None):
    if plan_pack:
        return plan_pack
    sd = (city.day) % city.cfg["season_days"] + 1          # tomorrow's season day
    if sd == city.cfg["season_days"]:
        return election_pack()
    if city.events:
        newest = max(city.events, key=lambda e: e["started"])
        ev = storyteller.catalog().get(newest["id"])
        if ev and ev.get("commands"):
            extra = {"WORK": "work", "PROTEST": "protest"}
            return packs.from_event({**ev, "id": newest["id"]}, extra)
    return default_pack()


def feature(city, actions):
    """Picks 3 residents worth mentioning: the angriest and happiest commenters, new councilors,
    people who just left or came back. Returns (report lines, short notes the mayor may mention)."""
    c = city.citizens
    lines, people, picked = [], [], set()

    def add(i, why):
        i = int(i)
        if i in picked or len(picked) >= 3:
            return
        picked.add(i)
        w = city.wards[int(c.ward[i])]
        lines.append(f"@{c.handles[i]} ({c.names[i]}, {JOB_NAMES[int(c.job[i])]} in {w['name']}) {why} - "
                     f"now {report.mood_word(float(c.mood[i]))}")
        people.append(f"@{c.handles[i]}, a {JOB_NAMES[int(c.job[i])]} in {w['name']}, {why}")
        c.log(i, city.day, why)

    for w in city.wards:   # councilors elected today
        i = w.get("councilor")
        if i is not None and c.story.get(int(i)) and c.story[int(i)][-1].startswith(f"day {city.day}: became"):
            add(i, f"was elected councilor of {w['name']}")
    commenters = np.array([c.index[u] for u in actions if u in c.index], dtype=np.int64)
    if len(commenters):
        m = c.mood[commenters]
        lo, hi = int(commenters[np.argmin(m)]), int(commenters[np.argmax(m)])
        if c.mood[lo] < 0.45:
            add(lo, f"chose {actions[c.handles[lo]]} and is fed up")
        if c.mood[hi] > 0.6:
            add(hi, f"chose {actions[c.handles[hi]]} and is thriving")
        rest = [i for i in commenters.tolist() if i not in picked]
        for i in city.rng.sample(rest, min(3 - len(picked), len(rest))):
            add(i, f"chose {actions[c.handles[i]]}")
    return lines, people


def pack_for_today(city):
    """The pack for the post about to be judged. On the very first day, applies the plan's day-1 beats."""
    if city.day == 0 and city.plan and not city.plan.get("done"):
        p, _ = plan.prepare(city, 1)
        if p:
            city.pack = p
    return city.pack or default_pack()


def run_day(city, mayor, followers, comments, pack=None):
    storyteller.catalog(reload=True)  # pick up edits to content/events.yaml
    pack = pack or pack_for_today(city)
    city.day += 1
    cfg = city.cfg
    season_day = (city.day - 1) % cfg["season_days"] + 1
    if season_day == 1 and city.day > 1:
        city.season += 1
    c = city.citizens

    # 1-2. people
    actions, status_users, joins = packs.parse(comments, pack)
    before = city.population()
    c.add_many(list(followers), city.day, city.ward_for, revive=False)
    c.add_many(sorted(joins), city.day, city.ward_for, revive=True)
    joined = city.population() - before
    ctx = DayContext(city)

    # 3. commands
    tallies = packs.apply(city, ctx, actions, pack)
    for u in status_users:
        i = c.index.get(u)
        if i is not None:
            ctx.status_requests.append(i)

    # 4. events
    ended = storyteller.tick(city, ctx)

    # 5. simulate
    sim_report = sim.simulate(city, ctx)

    # 6. recall vote on the season finale
    election = None
    if season_day == cfg["season_days"]:
        a = c.active()
        silent = a.copy()
        voted = 0
        for u, w in actions.items():
            i = c.index.get(u)
            if i is not None and pack["commands"].get(w, "").startswith("vote."):
                silent[i] = False
                voted += 1
        w = cfg["silent_vote_weight"]
        silent_recall = int((c.loyalty[silent] < 0.45).sum()) * w
        recall = ctx.election_votes["recall"] + silent_recall
        total = max(1, ctx.election_votes["keep"] + ctx.election_votes["recall"] + int(silent.sum()) * w)
        election = {"keep_votes": ctx.election_votes["keep"], "recall_votes": ctx.election_votes["recall"],
                    "silent": int(silent.sum()), "recall_share": recall / total, "keep_share": 1 - recall / total}
        election["recalled"] = election["recall_share"] > cfg["recall_threshold"]
        if election["recalled"]:
            city.mayor["recalled_day"] = city.day
            city.mayor["term"] = city.mayor.get("term", 1) + 1
            c.loyalty[a] = 0.55  # fresh start for whoever comes next
        sim_report["notes"].append("RECALL VOTE: " + ("the mayor was removed!" if election["recalled"]
                                                      else "the mayor survives."))

    # 7. tomorrow's post: things you scheduled, then the season plan, then (maybe) the storyteller
    started = storyteller.start_due(city)
    plan_pack, plan_started = plan.prepare(city, city.day + 1) if city.plan else (None, [])
    started += plan_started
    if not started:
        s = storyteller.maybe_start_event(city, quiet=plan.quiet(city) if city.plan else False)
        if s:
            started.append(s)

    # 8. mayor
    log_before = len(city.event_log)
    decision = mayor.decide(city)
    from .mayor import apply_decision
    lines, speech = apply_decision(city, decision)
    # events the mayor settled outright today count as ended today too
    for e in city.event_log[log_before:]:
        if e.get("result") == "mayor":
            e["outcome"] = f'{e["title"]}: {e.get("option_text", "").rstrip(".")}.'
            ended.append(e)
    if speech:
        city.mayor.setdefault("speeches", []).append({"day": city.day, "text": speech})
        city.mayor["speeches"] = city.mayor["speeches"][-30:]

    # featured residents: the most interesting people today, not just random commenters
    featured, people = feature(city, actions)
    stats = {"population": city.population(), "approval": round(city.approval(), 3),
             "treasury": round(city.treasury, 1), "tax_rate": round(city.tax_rate, 3),
             "economy": sim_report.get("economy", city.economy), "tension": round(storyteller.tension(city), 3),
             "services": {k: round(v, 3) for k, v in city.quality.items()}, "factions": city.faction_moods(),
             "wards": len(city.wards)}
    summary = (lines + [e["outcome"] for e in ended] + [s["title"] for s in started]
               + sim_report["notes"] + [f"Approval is {stats['approval']:.0%}."])
    diary = mayor.diary(city, summary, people)
    city.mayor.setdefault("journal", []).append({"day": city.day, "diary": diary, "approval": stats["approval"]})
    city.mayor["journal"] = city.mayor["journal"][-30:]
    city.history.append({"day": city.day, **{k: stats[k] for k in ("population", "approval", "treasury",
                                                                     "tax_rate", "tension")},
                         "events": len(city.events), "joined": joined})
    city.history = city.history[-400:]
    city.pack = next_pack(city, plan_pack)

    result = {"city": city.name, "day": city.day, "season": city.season, "season_day": season_day,
              "joined": joined, "tallies": tallies, "stats": stats, "sim": sim_report,
              "events_started": started, "events_ended": ended,
              "announce": list((city.plan or {}).get("announce", [])), "scheduled": list(city.scheduled),
              "events_active": list(city.events), "decision_lines": lines, "speech": speech,
              "decided_by": decision.get("_by", mayor.name), "thought": decision.get("thought", ""),
              "diary": diary, "featured": featured, "election": election, "next_pack": city.pack,
              "status_replies": [{"username": c.handles[i], "reply": report.status_card(city, i)}
                                 for i in dict.fromkeys(ctx.status_requests)]}
    return result
