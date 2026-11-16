"""One day of the city, start to finish. Used by both the test runner and the
live city, so what you test is exactly what runs.

  1. new followers move in (from an export, or the fake audience)
  2. the post's comments are read: actions, STATUS requests, JOINs
  3. command effects hit the citizens who commented
  4. events tick (help/hinder from comments counts here)
  5. the whole city simulates a day
  6. season finale: recall vote
  7. the storyteller may start a new event
  8. the mayor decides tomorrow's policy and writes a diary
  9. reports: daily markdown, episode script, STATUS replies, next post's commands
"""
import numpy as np

from . import packs, report, sim, storyteller
from .effects import DayContext
from .roles import JOB_NAMES

BASICS = {"WORK": "work", "PROTEST": "protest", "SHOP": "shop", "VOLUNTEER": "volunteer"}


def default_pack():
    return {"post": "daily", "window_hours": 24, "event": None, "commands": dict(BASICS), "caption": ""}


def election_pack():
    return {"post": "recall-vote", "window_hours": 24, "event": None,
            "commands": {"KEEP": "vote.keep", "RECALL": "vote.recall"}, "caption": ""}


def next_pack(city):
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


def run_day(city, mayor, followers, comments, pack=None):
    city.day += 1
    cfg = city.cfg
    season_day = (city.day - 1) % cfg["season_days"] + 1
    if season_day == 1 and city.day > 1:
        city.season += 1
    pack = pack or city.pack or default_pack()
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

    # 7. storyteller
    started = storyteller.maybe_start_event(city)

    # 8. mayor
    decision = mayor.decide(city)
    from .mayor import apply_decision
    lines, speech = apply_decision(city, decision)
    if speech:
        city.mayor.setdefault("speeches", []).append({"day": city.day, "text": speech})
        city.mayor["speeches"] = city.mayor["speeches"][-30:]

    # featured residents: a few commenters with something to say about them
    featured = []
    rng = city.rng
    commenters = [c.index[u] for u in actions if u in c.index]
    for i in rng.sample(commenters, min(3, len(commenters))):
        w = city.wards[int(c.ward[i])]
        word = actions[c.handles[i]]
        line = (f"@{c.handles[i]} ({c.names[i]}, {JOB_NAMES[int(c.job[i])]} in {w['name']}) chose {word} - "
                f"now {report.mood_word(float(c.mood[i]))}")
        c.log(i, city.day, f"chose {word} and felt {report.mood_word(float(c.mood[i]))}")
        featured.append(line)
    for w in city.wards:
        if w["protest"]:
            for i in np.where(c.active() & (c.ward == city.wards.index(w)))[0][:200]:
                c.log(i, city.day, f"lived through a {'riot' if w['protest'] == 2 else 'protest'} in {w['name']}")

    stats = {"population": city.population(), "approval": round(city.approval(), 3),
             "treasury": round(city.treasury, 1), "tax_rate": round(city.tax_rate, 3),
             "economy": sim_report.get("economy", city.economy), "tension": round(storyteller.tension(city), 3),
             "services": {k: round(v, 3) for k, v in city.quality.items()}, "factions": city.faction_moods(),
             "wards": len(city.wards)}
    summary = (lines + [e["outcome"] for e in ended] + ([started["title"]] if started else [])
               + sim_report["notes"] + [f"Approval is {stats['approval']:.0%}."])
    diary = mayor.diary(city, summary)
    city.mayor.setdefault("journal", []).append({"day": city.day, "diary": diary, "approval": stats["approval"]})
    city.mayor["journal"] = city.mayor["journal"][-30:]
    city.history.append({"day": city.day, **{k: stats[k] for k in ("population", "approval", "treasury",
                                                                     "tax_rate", "tension")},
                         "events": len(city.events), "joined": joined})
    city.history = city.history[-400:]
    city.pack = next_pack(city)

    result = {"city": city.name, "day": city.day, "season": city.season, "season_day": season_day,
              "joined": joined, "tallies": tallies, "stats": stats, "sim": sim_report,
              "events_started": [started] if started else [], "events_ended": ended,
              "events_active": list(city.events), "decision_lines": lines, "speech": speech,
              "decided_by": decision.get("_by", mayor.name), "thought": decision.get("thought", ""),
              "diary": diary, "featured": featured, "election": election, "next_pack": city.pack,
              "status_replies": [{"username": c.handles[i], "reply": report.status_card(city, i)}
                                 for i in dict.fromkeys(ctx.status_requests)]}
    return result
