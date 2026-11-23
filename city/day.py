"""One day of the kingdom, start to finish. Used by both the test runner and the
live kingdom, so what you test is exactly what runs.

  1. new followers move in (from an export, or the fake audience)
  2. the post's comments are read: actions, STATUS requests, JOINs, BECOME <ANYTHING>
  3. command effects hit the subjects who commented
  4. events tick (help/hinder and decree votes from comments count here)
  5. the whole kingdom simulates a day
  6. season finale: the Reckoning (KNEEL or REVOLT)
  7. tomorrow's post is set up: scheduled events, season-plan beats, or a storyteller event
  8. the king decides policy (only on events the crowd has already weighed in on) and writes his journal
  9. reports: daily markdown, episode script, STATUS replies, next post's commands
"""
import numpy as np

from . import packs, plan, report, sim, storyteller
from .effects import DayContext
from .roles import a_job

BASICS = {"WORK": "work", "TRADE": "shop", "TRAIN": "train", "GRUMBLE": "protest"}


def default_pack():
    return {"post": "daily", "window_hours": 24, "event": None, "commands": dict(BASICS), "caption": ""}


def election_pack():
    return {"post": "the-reckoning", "window_hours": 24, "event": None,
            "commands": {"KNEEL": "vote.keep", "REVOLT": "vote.recall"}, "caption": ""}


def next_pack(city, plan_pack=None):
    """Tomorrow's words. The plan or the Reckoning can set them; otherwise they come from what's
    happening (up to two events at once). The warlord's attacks always get words."""
    sd = (city.day) % city.cfg["season_days"] + 1          # tomorrow's season day
    cat = storyteller.catalog()
    evs = [a for a in city.events if (cat.get(a["id"]) or {}).get("commands") or (cat.get(a["id"]) or {}).get("choices")]
    evs.sort(key=lambda a: (a.get("source") != "warlord", -a["started"]))
    base = plan_pack or (election_pack() if sd == city.cfg["season_days"] else None)
    if base is not None:
        war = [{**cat[a["id"]], "id": a["id"]} for a in evs if a.get("source") == "warlord"
               and a["id"] != base.get("event")]
        return packs.merge(base, war[:1]) if war else base
    if evs:
        return packs.from_events([{**cat[a["id"]], "id": a["id"]} for a in evs[:2]])
    return default_pack()


def feature(city, actions, jobs=None):
    """Picks 3 subjects worth mentioning: new lords, the angriest and happiest commenters, then
    anyone. Returns (report lines, short notes the king may mention)."""
    c = city.citizens
    lines, people, picked = [], [], set()

    def add(i, why):
        i = int(i)
        if i in picked or len(picked) >= 3:
            return
        picked.add(i)
        w = city.wards[int(c.ward[i])]
        job, rank = c.label(i), c.rank(i)
        lines.append(f"@{c.handles[i]} ({c.names[i]}, {rank} {job} of {w['name']}) {why} - "
                     f"now {report.mood_word(float(c.mood[i]))}")
        people.append(f"@{c.handles[i]}, {a_job(job)} ({rank.lower()}) of {w['name']}, {why}")
        c.log(i, city.day, why)

    for w in city.wards:   # lords named today
        i = w.get("councilor")
        if i is not None and c.story.get(int(i)) and c.story[int(i)][-1].startswith(f"day {city.day}: was named"):
            add(i, f"was named Lord of {w['name']}")
    for u, job in list((jobs or {}).items())[:1]:   # someone who changed trade today
        if u in c.index:
            add(c.index[u], f"became {a_job(job)}")
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


def run_day(city, mayor, followers, comments, pack=None, world=None):
    """world: the living world (city/living/world.py), if this kingdom has one - then comments in people's
    own words get interpreted, and the post comes with a chronicle of the last 24 hours."""
    storyteller.catalog(reload=True)  # pick up edits to content/events.yaml
    pack = pack or pack_for_today(city)
    city.day += 1
    cfg = city.cfg
    season_day = (city.day - 1) % cfg["season_days"] + 1
    if season_day == 1 and city.day > 1:
        city.season += 1
    c = city.citizens

    # 1-2. people
    jobs, free = {}, ({} if world else None)
    story, flagged = ({}, []) if world else (None, None)
    if world is not None:
        from .living.intents import muted
        comments = [cm for cm in comments if not muted(world, str(cm.get("username", "")).lower())]
    closed = []
    if world is not None and city.living.get("posts"):     # every post stays live: old posts' words still count
        pack, closed_words = packs.with_old_posts(pack, city.living["posts"], city.day,
                                                  {a["id"] for a in city.events})
        closed = [cm["username"].lower() for cm in comments if cm.get("post") and int(cm["post"]) < city.day
                  and any(f" {w} " in f" {str(cm.get('text', '')).upper()} " for w in closed_words)]
    actions, status_users, joins = packs.parse(comments, pack, jobs, free, story, flagged)
    if world is not None:
        for cm in comments:
            world.note_comment(cm)
    before = city.population()
    n_before = len(c.handles)
    c.add_many(list(followers), city.day, city.ward_for, revive=False)
    c.add_many(sorted(joins), city.day, city.ward_for, revive=True)
    if world is not None:          # every newcomer gets a house - inside the walls if there's room
        from .living import town as _town
        _town.settle(world, n_before)
    joined = city.population() - before
    from . import trades
    for u, label in jobs.items():      # BECOME <ANYTHING>
        i = c.index.get(u)
        if i is None:
            continue
        if world is not None:          # usually already done when the comment came in; then this is a no-op
            world.take_role(u, "become", label, day=city.day, quiet_same=True)
        else:
            trades.take(city, i, "become", label, city.day)
    ctx = DayContext(city)
    ctx.actions = actions

    # 3. commands (and, in the living world, people's own words)
    tallies = packs.apply(city, ctx, actions, pack)
    if world is not None:
        from .living import intents
        world.finish_crowd(free, story, flagged)   # most own-words moves were already played out during the day
        tallies.update(intents.finish_day(world, ctx, pack))
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
        sim_report["notes"].append("THE RECKONING: " + ("the king has been overthrown! Whoever takes the throne "
                                                         "starts fresh (loyalty resets to 55%)." if election["recalled"]
                                                         else "the king keeps his crown."))

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
    featured, people = feature(city, actions, jobs)
    stats = {"population": city.population(), "approval": round(city.approval(), 3),
             "treasury": round(city.treasury, 1), "tax_rate": round(city.tax_rate, 3),
             "economy": sim_report.get("economy", city.economy), "tension": round(storyteller.tension(city), 3),
             "services": {k: round(v, 3) for k, v in city.quality.items()}, "factions": city.faction_moods(),
             "wards": len(city.wards)}
    if world is not None:   # what the crowd decided today is part of the story of the last 24 hours
        for e in ended:
            if e.get("result") == "helped":   # the people who did it hear about it, and the first few get named
                heroes = list(dict.fromkeys(ctx.helpers.get(e["id"], [])))
                for k, i in enumerate(heroes):
                    world.reply(c.handles[i], f"⚔️ You helped: {e['outcome']}", "helped",
                                credit=f"helped: {e['title'][:60]}" if k < 3 else None)
            big = e.get("source") == "warlord" or e["id"].startswith("decree_") or e.get("result") not in ("timed_out",)
            world.moment("world", e["outcome"], 3 if e.get("source") == "warlord" else (2 if big else 1),
                         public=True, hold=city.wards[e["ward"]]["name"] if e.get("ward") is not None else "")
    if world is not None:          # default replies: a first-time welcome, and "counted" for a keyword
        bad = {f["user"] for f in flagged or []}
        today = [str(cm.get("username", "")).strip().lstrip("@").lower() for cm in comments]
        heard = {x["to"] for x in city.living.get("outbox", []) if x.get("day") in (city.day, city.day + 1)}
        world.welcome([u for u in today if u not in bad and u not in heard])
        world.counted({u: w for u, w in actions.items() if u not in bad}, tallies)
    chron = world.chronicle() if world is not None else None
    summary = (lines + [e["outcome"] for e in ended] + [s["title"] for s in started]
               + ([m["text"] for m in chron["top"]] if chron else [])
               + sim_report["notes"] + [f"Loyalty to the king is {stats['approval']:.0%}."])
    diary = mayor.diary(city, summary, people)
    city.mayor.setdefault("journal", []).append({"day": city.day, "diary": diary, "approval": stats["approval"]})
    city.mayor["journal"] = city.mayor["journal"][-30:]
    city.history.append({"day": city.day, **{k: stats[k] for k in ("population", "approval", "treasury",
                                                                     "tax_rate", "tension")},
                         "events": len(city.events), "joined": joined, "left": sim_report.get("left", 0)})
    city.history = city.history[-400:]
    city.pack = next_pack(city, plan_pack)
    if world is not None:                                  # remember every post's words
        posts = city.living.setdefault("posts", {})
        posts[str(city.day + 1)] = city.pack
        for k in sorted(posts, key=int)[:-60]:
            del posts[k]

    result = {"city": city.name, "day": city.day, "season": city.season, "season_day": season_day,
              "joined": joined, "tallies": tallies, "stats": stats, "sim": sim_report,
              "events_started": started, "events_ended": ended,
              "announce": list((city.plan or {}).get("announce", [])), "scheduled": list(city.scheduled),
              "events_active": list(city.events), "decision_lines": lines, "speech": speech,
              "decided_by": decision.get("_by", mayor.name), "thought": decision.get("thought", ""),
              "diary": diary, "featured": featured, "election": election, "next_pack": city.pack,
              "chronicle": chron,
              "credits": (city.living.get("credits_today", []) if world else []),
              "wanted": (__import__("city.living.things", fromlist=["wanted"]).wanted(city) if world else []),
              "outbox": (city.living.get("outbox", []) if world else []),
              "moderation": ([m for m in city.living.get("moderation", []) if m["day"] == city.day] if world else []),
              "moments": world.moments_since(city.living.get("last_post_clock", -10 ** 9)) if world else [],
              "status_replies": [{"username": c.handles[i], "reply": report.status_card(city, i)}
                                 for i in dict.fromkeys(ctx.status_requests)]
              + [{"username": u, "reply": "That one's over - but today's post is live, and you can always tell your "
                                          "character what to do in your own words."} for u in dict.fromkeys(closed)
                 if u not in actions]}
    return result
