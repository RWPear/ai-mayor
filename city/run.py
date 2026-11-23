"""Command line. `./kingdom ...` is a shortcut for `.venv/bin/python -m city.run ...`.

TEST KINGDOM - run a whole scenario with a fake audience:
    ./kingdom test --scenario scenarios/season1.yaml              (newest run is always runs/latest)
    ./kingdom test --scenario scenarios/viral.yaml --king llm --days 10

PLANNING:
    ./kingdom plan --plan seasons/season1.yaml         the season calendar (what to prep)
    ./kingdom check                                    validate content, packs and plans

LIVE KINGDOM - run exactly one day with real inputs:
    ./kingdom day --state data/live --followers ~/exports/instagram.zip --comments comments.json
    ./kingdom status --state data/live --user somehandle

EVENTS BY HAND (test or live state):
    ./kingdom event list     --state runs/latest/state
    ./kingdom event start    --state runs/latest/state bandits --hold Millbrook     # tomorrow's post
    ./kingdom event schedule --state runs/latest/state barbarian_scouts --day 12
    ./kingdom event end      --state runs/latest/state bandits
    ./kingdom event cancel   --state runs/latest/state barbarian_scouts
"""
import argparse
import json
import logging
import time
from pathlib import Path

import yaml

from . import checker, config, plan, report, storyteller
from .day import next_pack, pack_for_today, run_day
from .mayor import make
from .model import City
from .packs import load as load_pack
from .sources.fake import FakeAudience
from .sources.instagram_export import read_comments, read_followers


def cmd_test(args):
    scen = yaml.safe_load(Path(args.scenario).read_text())
    cfg = config.load()
    cfg.update(scen.get("balance") or {})
    days = args.days or scen.get("days", 30)
    city = City(cfg, scen.get("kingdom", scen.get("city", "Emberfall")), seed=args.seed)
    if args.plan or scen.get("plan"):
        plan.attach(city, args.plan or scen["plan"])
    for e in scen.get("events") or []:   # events you schedule by hand in a scenario
        storyteller.schedule(city, e["event"], e["day"], e.get("hold", e.get("ward")), source="scenario")
    audience = FakeAudience(scen, seed=args.seed)
    mayor = make(args.mayor)
    world = make_world(city, args.mayor) if (args.living or scen.get("living")) else None
    out = Path(args.out or f"runs/{Path(args.scenario).stem}-{int(time.time())}")
    forced = {int(d): load_pack(p) for d, p in (scen.get("packs") or {}).items()}
    print(f"{'day':>4} {'pop':>7} {'joined':>6} {'loyal':>6} {'gold':>12} {'tax':>5} {'tension':>7}  happenings")
    t0 = time.time()
    for _ in range(days):
        d = city.day + 1
        pack = forced.get(d) or pack_for_today(city)
        followers = audience.followers_on(d)
        comments = audience.comments_on(d, pack, city)
        if world:   # comments trickle in through the day while the king and the warlord live their lives
            r = world.post(mayor, followers, comments, pack)
        else:
            r = run_day(city, mayor, followers, comments, pack)
        s = r["stats"]
        first = [report.headline(r)] if r.get("election") else []
        if world and r.get("chronicle"):
            first += [m["text"] for m in r["chronicle"]["top"] if m["drama"] >= 2][:2]
        what = "; ".join((first + [f"NEW {e['title']}" for e in r["events_started"]] +
                          [f"END {e['outcome'][:60]}" for e in r["events_ended"]] + r["sim"]["notes"])[:3])
        print(f"{r['day']:>4} {s['population']:>7} {r['joined']:>6} {s['approval']:>6.0%} {s['treasury']:>12,.0f} "
              f"{s['tax_rate']:>5.0%} {s['tension']:>7.2f}  {what[:140]}")
        if args.reports:
            report.save(city, r, out / "days")
    city.save(out / "state")
    latest = out.parent / "latest"
    try:   # runs/latest always points at the newest run
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(out.name)
    except OSError:
        pass
    final = city.history[-1]
    print(f"\n{days} days in {time.time() - t0:.1f}s · holds: {len(city.wards)} · milestones: {city.milestones}")
    print(f"final loyalty {final['approval']:.0%}, treasury {final['treasury']:,.0f} gold, "
          f"events run: {len(city.event_log)}, projects: {[p['name'] for p in city.projects]}")
    print(f"saved to {out}  (also {latest})  try: ./kingdom event list --state {latest}/state")
    if world:
        camp = city.living["warcamp"]
        print(f"war camp: {camp['warriors']} warriors, {camp['food']:.0f} food, morale {camp['morale']:.2f}, "
              f"raids won {camp['raids_won']} / lost {camp['raids_lost']}")
        print("tools unlocked: king " + ", ".join(city.living["unlocked"]["king"]) +
              " | warlord " + ", ".join(city.living["unlocked"]["warlord"]))
        print("actions: " + ", ".join(f"{k} {v}" for k, v in sorted(world.stats.items()) if not k.startswith("last_")))
        for k in ("last_error", "last_fallback"):
            if world.stats.get(k):
                print(f"{k.replace('_', ' ')}: {world.stats[k]}")
        evs = list(city.living["custom_events"].values())
        decrees = [e["title"] for e in evs if e["id"].startswith("decree_")]
        stories = [e["title"] for e in evs if e.get("invented_by") == "director"]
        if decrees:
            print(f"decrees the king wrote ({len(decrees)}): " + " | ".join(decrees[:6]))
        if stories:
            print(f"events the director invented ({len(stories)}): " + " | ".join(stories[:8]))
        king = city.living["agents"]["king"]
        if king.get("self", {}).get("becoming"):
            print(f"who the king is becoming: {king['self']['becoming']}")


def make_world(city, kind):
    from .living.agents import LLMBrain
    from .living.world import World
    if kind == "llm":
        from .llm import LLM
        main, crowd = LLM(), LLM(crowd=True)
        return World(city, LLMBrain(main), LLMBrain(main), crowd_llm=crowd, voice_llm=crowd, director_llm=main)
    return World(city)


def cmd_live(args):
    """The live kingdom, in real time: ticks forever, closes a post every day at 19:00."""
    from .living import world as W
    from .sources.instagram_export import read_followers
    cfg = config.load()
    state = Path(args.state)
    city = City.load(state, cfg) if (state / "city.json").exists() else City(cfg, args.name)
    if args.plan:
        plan.attach(city, args.plan)
    world = make_world(city, args.mayor)
    mayor = make(args.mayor)
    inbox = Path(args.inbox)
    inbox.mkdir(parents=True, exist_ok=True)
    print(f"{city.name} is alive. {world.now_str()}. Next post closes at {world.now_str(world.next_post_clock())}.")
    print(f"Comments go in {inbox}/comments-dayN.json, one file per post (N = the post's day). Every post stays "
          f"live: keep appending to any of them and new comments play out within the hour. A follower export can go "
          f"in {inbox}/followers.")
    seen, arrived = {}, []
    while True:
        # every post stays live: read all posts' comment files, and play out whatever is new
        for f in sorted(inbox.glob("comments-day*.json")):
            try:
                post = int(f.stem.split("day")[-1])
                comments = json.loads(f.read_text())
            except (ValueError, json.JSONDecodeError):
                continue
            new = [{**cm, "post": post} for cm in comments[seen.get(f.name, 0):]]
            if new:
                world.queue_comments(new, spread=False)
                arrived += new
                seen[f.name] = len(comments)
        if world.clock + W.TICK > world.next_post_clock():
            d = city.day + 1
            fol = inbox / "followers"
            followers = read_followers(fol) if fol.exists() else []
            r = world.post(mayor, followers, arrived, None, already_queued=True)
            arrived = []
            report.save(city, r, state / "days")
            print(f"\n=== POST {d} closed: {report.headline(r)}  ->  next words: "
                  f"{', '.join(r['next_pack']['commands'])}\n")
        else:
            n = len(city.living["moments"])
            world.tick()
            for m in city.living["moments"][n:]:
                print(f"{m['time']}  {'' if m['public'] else '(secret) '}[{m['who']}] {m['text']}")
        city.save(state)
        if args.speed > 0:
            time.sleep(W.TICK * 60 / args.speed)


def cmd_day(args):
    cfg = config.load()
    state = Path(args.state)
    city = City.load(state, cfg) if (state / "city.json").exists() else City(cfg, args.name)
    if args.plan:
        plan.attach(city, args.plan)
    followers = read_followers(args.followers) if args.followers else []
    comments = read_comments(args.comments) if args.comments else []
    pack = load_pack(args.pack) if args.pack else None
    r = run_day(city, make(args.mayor), followers, comments, pack)
    city.save(state)
    report.save(city, r, state / "days")
    print(report.markdown(city, r))


def cmd_status(args):
    city = City.load(Path(args.state), config.load())
    i = city.citizens.index.get(args.user.lstrip("@").lower())
    print(report.status_card(city, i) if i is not None else "not a subject")


def cmd_plan(args):
    cfg = config.load()
    if args.state and (Path(args.state) / "city.json").exists():
        city = City.load(Path(args.state), cfg)
    else:
        city = City(cfg)
    if args.plan:
        plan.attach(city, args.plan)
    if not city.plan:
        print("No plan attached. Use --plan seasons/season1.yaml (or a folder of seasonN.yaml files).")
        return
    data, rows = plan.calendar(city, args.season)
    print(f"SEASON {args.season or city.season}: {data.get('title', '')}")
    if data.get("theme"):
        print(f"  {data['theme']}")
    print(f"  storyteller between beats: {data.get('storyteller', 'fill')}\n")
    for r in rows:
        ev = r["event"] or "-"
        cond = f"  IF {r['if']} ELSE {r['else'] or 'nothing'}" if r["if"] else ""
        print(f"Day {r['day']:>2}  {ev}{cond}")
        if r["commands"] or (r["pack"] and r["pack"] != "auto"):
            print(f"        commands: {r['commands'] or r['pack']}")
        for k in ("announce", "agenda", "note"):
            if r[k]:
                print(f"        {k}: {r[k]}")
    if city.scheduled:
        print("\nAlso scheduled: " + ", ".join(f"{s['event']} (day {s['day']})" for s in city.scheduled))


def cmd_event(args):
    cfg = config.load()
    state = Path(args.state) if args.state else None
    cat = storyteller.catalog()
    if args.action == "list" and not state:
        for e in cat.values():
            words = e.get("choices") or e.get("commands") or {}
            kind = "vote" if e.get("choices") else "event"
            plan_only = " (season plans only)" if e.get("planned_only") else ""
            print(f"{e['id']:<20} {kind:<5} {e['title']}  [{', '.join(str(w).upper() for w in words)}]{plan_only}")
        return
    city = City.load(state, cfg)
    if args.action == "list":
        print(f"Day {city.day} (season {city.season})")
        print("Active: " + (", ".join(f"{a['id']} - {a['title']} ({a['days_left']} days left)"
                                      for a in city.events) or "none"))
        print("Scheduled: " + (", ".join(f"{s['event']} on day {s['day']} ({s['source']})"
                                         for s in city.scheduled) or "none"))
        print("\nAvailable events:")
        for e in cat.values():
            ok = storyteller.condition_ok(city, e.get("when"))
            print(f"  {'  ' if ok else 'x '}{e['id']:<18} {e['title']}" + ("" if ok else f"   (when: {e['when']})"))
        print("\n(x = its 'when' condition isn't met right now; start/schedule still work)")
        return
    if args.id not in cat and args.action in ("start", "schedule"):
        raise SystemExit(f"unknown event '{args.id}'. See: python -m city.run event list")
    if args.action == "start":
        a = storyteller.start(city, args.id, args.hold, source="you")
        if not a:
            raise SystemExit("couldn't start it (already running?)")
        city.pack = next_pack(city)
        print(f"Started: {a['title']}. It's the subject of the next post: {', '.join(city.pack['commands'])}")
    elif args.action == "schedule":
        storyteller.schedule(city, args.id, args.day, args.hold, source="you")
        print(f"Scheduled {args.id} for day {args.day}'s post.")
    elif args.action == "end":
        a = storyteller.end(city, args.id)
        if not a:
            raise SystemExit("that event isn't active")
        city.pack = next_pack(city)
        print(f"Ended: {a['title']}")
    elif args.action == "cancel":
        before = len(city.scheduled)
        city.scheduled = [s for s in city.scheduled if s["event"] != args.id]
        print(f"Removed {before - len(city.scheduled)} scheduled '{args.id}'.")
    city.save(state)


def cmd_check(args):
    problems, summary = checker.check_all(args.plan)
    for line in summary:
        print(line)
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print("  - " + p)
        raise SystemExit(1)
    print("\nAll good.")


def cmd_view(args):
    """Exports the 3D world as a static folder (the viewer, its scripts, the run's days, the recorders) that
    any web host can serve - or open with ./kingdom serve instead, which needs no export."""
    import json as _json
    import shutil as _shutil
    from .config import ROOT
    from .recorder import recorders, scenes_index
    days = Path(args.days)
    index = scenes_index(days)
    if args.first or args.last:
        index = [d for d in index if (not args.first or d["day"] >= args.first) and (not args.last or d["day"] <= args.last)]
    if not index:
        print(f"No scene files in {days} - run a frontier scenario with --reports first.")
        return
    out = Path(args.out or days.parent / "world")
    if out.exists():
        _shutil.rmtree(out)
    _shutil.copytree(ROOT / "viewer", out)
    (out / "days").mkdir()
    for d in index:
        _shutil.copy(days / d["file"], out / "days" / d["file"])
    (out / "days" / "scenes.json").write_text(_json.dumps(index))
    (out / "recorders.json").write_text(_json.dumps(recorders()))
    print(f"{out}  ({len(index)} days; host the folder anywhere, or: python -m http.server -d {out})")


def cmd_serve(args):
    from .recorder import serve
    serve(args.days, args.port)


def cmd_play(args):
    from .play import Play, serve
    serve(Play(args.state, mayor=args.mayor, fresh=args.fresh, speed=args.speed, crowd=args.crowd, seed=args.seed),
          args.port)


def cmd_record(args):
    from .recorder import record
    record(args.days, names=args.recorders.split(",") if args.recorders else None, every=args.every, size=args.size,
           quality=args.quality, fps=args.fps, out=args.out, only_day=args.day, gpu=not args.cpu, three=args.three,
           first=args.first, last=args.last)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # keep the day table readable
    p = argparse.ArgumentParser(prog="city")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("test", help="run a scenario with a fake audience")
    t.add_argument("--scenario", required=True)
    t.add_argument("--plan", help="season plan file or folder (overrides the scenario's)")
    t.add_argument("--days", type=int)
    t.add_argument("--king", "--mayor", dest="mayor", default="rules", choices=["rules", "llm"])
    t.add_argument("--seed", type=int, default=1)
    t.add_argument("--out")
    t.add_argument("--reports", action="store_true", help="write a report + episode script for every day")
    t.add_argument("--living", action="store_true", help="run the living world between posts (king + warlord)")
    lv = sub.add_parser("live", help="the live kingdom in real time (ticks forever)")
    lv.add_argument("--state", required=True)
    lv.add_argument("--name", default="Emberfall")
    lv.add_argument("--plan", help="attach a season plan (only needed once)")
    lv.add_argument("--inbox", default="inbox", help="where each day's comments (and follower export) are dropped")
    lv.add_argument("--king", "--mayor", dest="mayor", default="llm", choices=["rules", "llm"])
    lv.add_argument("--speed", type=float, default=1.0, help="1 = real time, 60 = an hour a minute, 0 = no waiting")
    d = sub.add_parser("day", help="run one real day")
    d.add_argument("--state", required=True)
    d.add_argument("--name", default="Emberfall")
    d.add_argument("--plan", help="attach a season plan (only needed once)")
    d.add_argument("--followers")
    d.add_argument("--comments")
    d.add_argument("--pack")
    d.add_argument("--king", "--mayor", dest="mayor", default="llm", choices=["rules", "llm"])
    s = sub.add_parser("status", help="print a subject card")
    s.add_argument("--state", required=True)
    s.add_argument("--user", required=True)
    pl = sub.add_parser("plan", help="show a season's calendar")
    pl.add_argument("--plan")
    pl.add_argument("--state")
    pl.add_argument("--season", type=int)
    e = sub.add_parser("event", help="list/start/schedule/end events by hand")
    e.add_argument("action", choices=["list", "start", "schedule", "end", "cancel"])
    e.add_argument("id", nargs="?")
    e.add_argument("--state")
    e.add_argument("--hold", "--ward", dest="hold")
    e.add_argument("--day", type=int)
    sv = sub.add_parser("serve", help="open the 3D world in your browser (http://localhost:8765)")
    sv.add_argument("--days", default="runs/latest/days", help="a run's days folder")
    sv.add_argument("--port", type=int, default=8765)
    py = sub.add_parser("play", help="a live kingdom in your browser: comment as any follower, approve replies")
    py.add_argument("--state", default="data/play", help="where it's saved (picks up where it left off)")
    py.add_argument("--fresh", action="store_true", help="start a new kingdom (the king alone in his field)")
    py.add_argument("--king", "--mayor", dest="mayor", default="rules", choices=["rules", "llm"])
    py.add_argument("--speed", default="normal", choices=["slow", "normal", "fast", "faster"],
                    help="a day takes 48 / 24 / 6 / about 1 minute (change it in the browser too)")
    py.add_argument("--crowd", type=int, default=0, help="made-up followers commenting in the background")
    py.add_argument("--seed", type=int, default=1)
    py.add_argument("--port", type=int, default=8765)
    rc = sub.add_parser("record", help="timelapse videos from the recorders in content/recorders.yaml")
    rc.add_argument("--days", default="runs/latest/days", help="a run's days folder")
    rc.add_argument("--recorders", help="comma-separated names (default: all)")
    rc.add_argument("--every", type=int, help="a frame every N game minutes from 06:00 to 20:00 (default: each "
                                              "recorder's own times)")
    rc.add_argument("--day", type=int, help="only this day (adds to the existing frames)")
    rc.add_argument("--first", type=int, help="first day to record")
    rc.add_argument("--last", type=int, help="last day to record")
    rc.add_argument("--size", default="1280x720")
    rc.add_argument("--quality", default="high", choices=["high", "low"])
    rc.add_argument("--fps", type=int, default=10)
    rc.add_argument("--out", help="default: the run's recordings/ folder")
    rc.add_argument("--cpu", action="store_true", help="render without the GPU (slow, but works anywhere)")
    rc.add_argument("--three", help="a local copy of the three npm package (offline machines)")
    v = sub.add_parser("view", help="export the 3D world as a static folder you can host anywhere")
    v.add_argument("--days", default="runs/latest/days", help="a run's days folder")
    v.add_argument("--first", type=int, help="first day to include")
    v.add_argument("--last", type=int, help="last day to include")
    v.add_argument("--out", help="default: the run's world/ folder")
    c = sub.add_parser("check", help="validate events, projects, milestones, packs and plans")
    c.add_argument("--plan", default="seasons")
    args = p.parse_args()
    {"test": cmd_test, "day": cmd_day, "status": cmd_status, "plan": cmd_plan, "event": cmd_event,
     "check": cmd_check, "live": cmd_live, "view": cmd_view, "serve": cmd_serve, "record": cmd_record, "play": cmd_play}[args.cmd](args)


if __name__ == "__main__":
    main()
