"""Command line.

TEST CITY - run a whole scenario with a fake audience:
    python -m city.run test --scenario scenarios/baseline.yaml
    python -m city.run test --scenario scenarios/viral.yaml --mayor llm --days 10

LIVE CITY - run exactly one day with real inputs:
    python -m city.run day --state data/live --followers ~/exports/instagram.zip --comments comments.json
    python -m city.run status --state data/live --user somehandle
"""
import argparse
import json
import logging
import time
from pathlib import Path

import yaml

from . import config, report
from .day import default_pack, run_day
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
    city = City(cfg, scen.get("city", "New Harbor"), seed=args.seed)
    audience = FakeAudience(scen, seed=args.seed)
    mayor = make(args.mayor)
    out = Path(args.out or f"runs/{Path(args.scenario).stem}-{int(time.time())}")
    forced = {int(d): load_pack(p) for d, p in (scen.get("packs") or {}).items()}
    print(f"{'day':>4} {'pop':>7} {'joined':>6} {'approv':>6} {'treasury':>12} {'tax':>5} {'tension':>7}  happenings")
    t0 = time.time()
    for _ in range(days):
        d = city.day + 1
        pack = forced.get(d) or city.pack or default_pack()
        followers = audience.followers_on(d)
        comments = audience.comments_on(d, pack, city)
        r = run_day(city, mayor, followers, comments, pack)
        s = r["stats"]
        what = "; ".join(([f"NEW {e['title']}" for e in r["events_started"]] +
                          [f"END {e['outcome'][:50]}" for e in r["events_ended"]] + r["sim"]["notes"])[:3])
        print(f"{r['day']:>4} {s['population']:>7} {r['joined']:>6} {s['approval']:>6.0%} {s['treasury']:>12,.0f} "
              f"{s['tax_rate']:>5.0%} {s['tension']:>7.2f}  {what[:110]}")
        if args.reports:
            report.save(city, r, out / "days")
    city.save(out / "state")
    final = city.history[-1]
    print(f"\n{days} days in {time.time() - t0:.1f}s · wards: {len(city.wards)} · milestones: {city.milestones}")
    print(f"final approval {final['approval']:.0%}, treasury ${final['treasury']:,.0f}, "
          f"events run: {len(city.event_log)}, projects: {[p['name'] for p in city.projects]}")
    print(f"saved to {out}")


def cmd_day(args):
    cfg = config.load()
    state = Path(args.state)
    city = City.load(state, cfg) if (state / "city.json").exists() else City(cfg, args.name)
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
    print(report.status_card(city, i) if i is not None else "not a resident")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # keep the day table readable
    p = argparse.ArgumentParser(prog="city")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("test", help="run a scenario with a fake audience")
    t.add_argument("--scenario", required=True)
    t.add_argument("--days", type=int)
    t.add_argument("--mayor", default="rules", choices=["rules", "llm"])
    t.add_argument("--seed", type=int, default=1)
    t.add_argument("--out")
    t.add_argument("--reports", action="store_true", help="write a report + episode script for every day")
    d = sub.add_parser("day", help="run one real day")
    d.add_argument("--state", required=True)
    d.add_argument("--name", default="New Harbor")
    d.add_argument("--followers")
    d.add_argument("--comments")
    d.add_argument("--pack")
    d.add_argument("--mayor", default="llm", choices=["rules", "llm"])
    s = sub.add_parser("status", help="print a citizen card")
    s.add_argument("--state", required=True)
    s.add_argument("--user", required=True)
    args = p.parse_args()
    {"test": cmd_test, "day": cmd_day, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    main()
