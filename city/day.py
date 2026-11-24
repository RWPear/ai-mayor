"""One day of Emberfall, start to finish (the post closes; the next one opens). Used by the test runner, the
real daily run and live play, so what you test is exactly what runs.

  1. new followers walk in (a free bed, or a tent)
  2. the post's comments are read: own-words moves (most already played out during the day), keywords,
     STATUS, BECOME <ANYTHING>
  3. events tick (help/hinder and votes from comments count here)
  4. people: loyalty follows mood; anyone miserable for too long packs up and leaves
  5. the Reckoning, once he has a crown to lose
  6. tomorrow's post is set up: scheduled events, or a new one
  7. the king answers events and writes his journal
"""
import numpy as np

from . import packs, report, storyteller
from .effects import DayContext
from .living import frontier as F
from .living import intents
from .roles import a_job

BASICS = {"WORK": "work", "BUILD": "volunteer", "CHEER": "support", "GRUMBLE": "protest"}


def default_pack():
    return {"post": "daily", "window_hours": 24, "event": None, "commands": dict(BASICS), "caption": ""}


def election_pack():
    return {"post": "the-reckoning", "window_hours": 24, "event": None,
            "commands": {"KNEEL": "vote.keep", "REVOLT": "vote.recall"}, "caption": ""}


def reckoning_day(city, day=None):
    """The last day of a season - but only once he has a crown to lose."""
    d = (city.day if day is None else day) % city.cfg["season_days"] + 1
    return d == city.cfg["season_days"] and F.land(city).get("crowned")


def next_pack(city):
    """Tomorrow's words: the Reckoning, or what's happening (up to two events; Skarn's attacks always get words)."""
    cat = storyteller.catalog()
    evs = [a for a in city.events if (cat.get(a["id"]) or {}).get("commands") or (cat.get(a["id"]) or {}).get("choices")]
    evs.sort(key=lambda a: (a.get("source") != "warlord", -a["started"]))
    if reckoning_day(city):
        war = [{**cat[a["id"]], "id": a["id"]} for a in evs if a.get("source") == "warlord"]
        return packs.merge(election_pack(), war[:1]) if war else election_pack()
    if evs:
        return packs.from_events([{**cat[a["id"]], "id": a["id"]} for a in evs[:2]])
    return default_pack()


def feature(city, actions, jobs=None):
    """Up to 3 people worth mentioning: someone who changed trade, the unhappiest and happiest commenters, then
    anyone. Returns (report lines, short notes the king may mention)."""
    c = city.citizens
    lines, people, picked = [], [], set()

    def add(i, why):
        i = int(i)
        if i in picked or len(picked) >= 3:
            return
        picked.add(i)
        lines.append(f"@{c.handles[i]} {why} - now {report.mood_word(float(c.mood[i]))}")
        people.append(f"@{c.handles[i]}, {why}")
        c.log(i, city.day, why)

    for u, job in list((jobs or {}).items())[:1]:
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


def people(city, ctx):
    """Loyalty drifts toward mood (CHEER and GRUMBLE nudge it); anyone miserable for days on end leaves.
    (Mood itself comes from the island: food, rough nights, what happens to them.)"""
    cfg, c, f = city.cfg, city.citizens, ctx.flags
    a = c.active()
    notes = []
    if not a.any():
        return {"notes": notes, "left": 0}
    nudge = 0.05 * f["support"] - 0.05 * f["oppose"] - 0.03 * f["protest"] - cfg["approval_fatigue"]
    c.loyalty = np.where(a, np.clip(c.loyalty + (c.mood - c.loyalty) * cfg["loyalty_drift"] + nudge, 0, 1),
                         c.loyalty).astype(np.float32)
    c.low_days = np.where(a & (c.mood < cfg["leave_mood"]), c.low_days + 1, 0).astype(np.int16)
    leaving = np.where(a & (c.low_days >= cfg["leave_days"]))[0]
    for i in leaving:
        c.status[i] = 1
        c.log(i, city.day, "gave up and left Emberfall")
    if len(leaving):
        notes.append(f"{len(leaving)} {'person' if len(leaving) == 1 else 'people'} packed up and left Emberfall.")
    return {"notes": notes, "left": int(len(leaving))}


def reckoning(city, actions, pack, ctx):
    """KNEEL or REVOLT. People who stay quiet vote too, but each counts for little."""
    cfg, c = city.cfg, city.citizens
    a = c.active()
    silent = a.copy()
    for u, w in actions.items():
        i = c.index.get(u)
        if i is not None and pack["commands"].get(w, "").startswith("vote."):
            silent[i] = False
    w = cfg["silent_vote_weight"]
    recall = ctx.election_votes["recall"] + int((c.loyalty[silent] < 0.45).sum()) * w
    total = max(1, ctx.election_votes["keep"] + ctx.election_votes["recall"] + int(silent.sum()) * w)
    e = {"keep_votes": ctx.election_votes["keep"], "recall_votes": ctx.election_votes["recall"],
         "silent": int(silent.sum()), "recall_share": recall / total, "keep_share": 1 - recall / total}
    e["recalled"] = e["recall_share"] > cfg["recall_threshold"]
    if e["recalled"]:
        city.mayor["recalled_day"] = city.day
        city.mayor["term"] = city.mayor.get("term", 1) + 1
        c.loyalty[a] = 0.55                       # a fresh start for whoever comes next
    return e


def pack_for_today(city):
    return city.pack or default_pack()


def run_day(city, mayor, followers, comments, pack=None, world=None):
    storyteller.catalog(reload=True)              # pick up edits to content/events.yaml
    pack = pack or pack_for_today(city)
    city.day += 1
    cfg = city.cfg
    season_day = (city.day - 1) % cfg["season_days"] + 1
    if season_day == 1 and city.day > 1:
        city.season += 1
    c = city.citizens

    jobs, free, story, flagged = {}, {}, {}, []
    comments = [cm for cm in comments if not intents.muted(world, str(cm.get("username", "")).lower())]
    closed = []
    if city.living.get("posts"):                  # every post stays live: old posts' words still count
        pack, closed_words = packs.with_old_posts(pack, city.living["posts"], city.day, {a["id"] for a in city.events})
        closed = [cm["username"].lower() for cm in comments if cm.get("post") and int(cm["post"]) < city.day
                  and any(f" {w} " in f" {str(cm.get('text', '')).upper()} " for w in closed_words)]
    actions, status_users, joins = packs.parse(comments, pack, jobs, free, story, flagged)
    for cm in comments:
        world.note_comment(cm)
    before = city.population()
    new1 = c.add_many(list(followers), city.day, city.ward_for, revive=False)
    new2 = c.add_many(sorted(joins), city.day, city.ward_for, revive=True)
    F.join_road(world, np.concatenate([np.asarray(new1, np.int64), np.asarray(new2, np.int64)]))
    joined = city.population() - before
    for u, label in jobs.items():                 # BECOME <ANYTHING> (usually already done when the comment came in)
        if u in c.index:
            world.take_role(u, "become", label, day=city.day, quiet_same=True)
    ctx = DayContext(city)
    ctx.actions = actions

    tallies = packs.apply(city, ctx, actions, pack)
    world.finish_crowd(free, story, flagged)      # most own-words moves were already played out during the day
    tallies.update(intents.finish_day(world, ctx, pack))
    for u in status_users:
        if u in c.index:
            ctx.status_requests.append(c.index[u])

    ended = storyteller.tick(city, ctx)
    folk = people(city, ctx)
    election = reckoning(city, actions, pack, ctx) if reckoning_day(city, city.day - 1) else None
    if election:
        folk["notes"].append("THE RECKONING: " + ("the king has been overthrown! Whoever takes his place starts "
                                                   "fresh." if election["recalled"] else "the king keeps his crown."))

    started = storyteller.start_due(city)
    if not started:
        s = storyteller.maybe_start_event(city)
        if s:
            started.append(s)

    log_before = len(city.event_log)
    decision = mayor.decide(city)
    from .mayor import apply_decision
    lines = apply_decision(city, decision)
    for e in city.event_log[log_before:]:
        if e.get("result") == "mayor":
            e["outcome"] = f'{e["title"]}: {e.get("option_text", "").rstrip(".")}.'
            ended.append(e)

    featured, notes_people = feature(city, actions, jobs)
    stats = {"population": city.population(), "approval": round(city.approval(), 3),
             "treasury": round(city.treasury, 1), "tension": round(storyteller.tension(city), 3)}
    for e in ended:                               # what the crowd decided today is part of the story
        if e.get("result") == "helped":           # the people who did it hear about it; the first few get named
            heroes = list(dict.fromkeys(ctx.helpers.get(e["id"], [])))
            for k, i in enumerate(heroes):
                world.reply(c.handles[i], f"⚔️ You helped: {e['outcome']}", "helped",
                            credit=f"helped: {e['title'][:60]}" if k < 3 else None)
        big = e.get("source") == "warlord" or e["id"].startswith("decree_") or e.get("result") not in ("timed_out",)
        world.moment("world", e["outcome"], 3 if e.get("source") == "warlord" else (2 if big else 1), public=True,
                     hold=city.wards[e["ward"]]["name"] if e.get("ward") is not None else "")
    bad = {f["user"] for f in flagged or []}      # default replies: a first-time welcome, "counted" for a keyword
    today = [str(cm.get("username", "")).strip().lstrip("@").lower() for cm in comments]
    heard = {x["to"] for x in city.living.get("outbox", []) if x.get("day") in (city.day, city.day + 1)}
    world.welcome([u for u in today if u not in bad and u not in heard])
    world.counted({u: w for u, w in actions.items() if u not in bad}, tallies)
    F.after_post(world)
    chron = world.chronicle()
    summary = (lines + [e["outcome"] for e in ended] + [s["title"] for s in started]
               + [m["text"] for m in chron["top"]] + folk["notes"])
    diary = mayor.diary(city, summary, notes_people)
    city.mayor.setdefault("journal", []).append({"day": city.day, "diary": diary, "approval": stats["approval"]})
    city.mayor["journal"] = city.mayor["journal"][-30:]
    city.history.append({"day": city.day, **stats, "events": len(city.events), "joined": joined,
                         "left": folk["left"]})
    city.history = city.history[-400:]
    city.pack = next_pack(city)
    posts = city.living.setdefault("posts", {})   # remember every post's words
    posts[str(city.day + 1)] = city.pack
    for k in sorted(posts, key=int)[:-60]:
        del posts[k]

    from .living import scene, things
    return {"city": city.name, "day": city.day, "season": city.season, "season_day": season_day,
            "joined": joined, "tallies": tallies, "stats": stats, "sim": {"notes": folk["notes"], "left": folk["left"]},
            "events_started": started, "events_ended": ended, "scheduled": list(city.scheduled),
            "events_active": list(city.events), "decision_lines": lines,
            "decided_by": decision.get("_by", mayor.name), "thought": decision.get("thought", ""),
            "diary": diary, "featured": featured, "election": election, "next_pack": city.pack,
            "chronicle": chron, "frontier": F.summary(world), "scene": scene.export(world),
            "credits": city.living.get("credits_today", []), "wanted": things.wanted(city),
            "outbox": city.living.get("outbox", []),
            "moderation": [m for m in city.living.get("moderation", []) if m["day"] == city.day],
            "moments": world.moments_since(city.living.get("last_post_clock", -10 ** 9)),
            "status_replies": [{"username": c.handles[i], "reply": report.status_card(city, i)}
                               for i in dict.fromkeys(ctx.status_requests)]
            + [{"username": u, "reply": "That one's over - but today's post is live, and you can always tell your "
                                        "character what to do in your own words."} for u in dict.fromkeys(closed)
               if u not in actions]}
