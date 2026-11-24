"""Turning a day into things people see: the daily report, the episode script
for the video, and STATUS subject cards (replies to comments, or private DMs).
"""
import json



def mood_word(m):
    if m < 0.2: return "furious 😡"
    if m < 0.35: return "fed up 😠"
    if m < 0.5: return "uneasy 😕"
    if m < 0.65: return "doing okay 🙂"
    if m < 0.8: return "happy 😄"
    return "thriving 🤩"


def loyalty_word(v):
    if v < 0.25: return "plotting against the crown"
    if v < 0.4: return "disloyal"
    if v < 0.55: return "wavering"
    if v < 0.7: return "loyal"
    return "devoted"


def status_card(city, i):
    """A short, personal reply to a STATUS comment (fits a comment reply or a private-reply DM)."""
    c = city.citizens
    role = c.roles.get(int(i))
    title = c.title(i)
    lines = [f"🏝️ @{c.handles[i]} - {c.names[i]}" + (f" {title}" if title else ""),
             f"⚒️ {c.rank(i)} · {role or 'settler'} · in Emberfall since day {int(c.joined[i])}",
             f"Mood: {mood_word(float(c.mood[i]))} · Toward Aldric: {loyalty_word(float(c.loyalty[i]))} · "
             f"{int(c.counts['commands'][i])} deeds"]
    from . import trades
    learned = (city.living.get("learned") or {}).get(c.handles[i])
    if learned:
        lines.append("Knows: " + ", ".join(trades.SKILL_LABEL.get(x, x) for x in learned))
    known = trades.reputation(c.counts_of(i))
    if known:
        lines.append("Known as: " + ", ".join(known))
    if int(c.walled[i]) == -2 and c.status[i] == 0:
        lines.append("⛺ Living in a tent by the old road, waiting for a house")
    elif int(c.burned[i]):
        lines.append("🔥 Your house burned down - the neighbours are helping rebuild")
    nxt = _next_rank(c, i)
    if nxt:
        lines.append(nxt)
    mark = (city.living.get("impact") or {}).get(c.handles[i], [])
    if mark:
        lines.append("Your mark on Emberfall: " + "; ".join(m["text"] for m in mark[-2:]))
    story = c.story.get(int(i))
    if story:
        lines.append("Latest: " + story[-1])
    if c.status[i] == 1:
        lines.insert(1, "(left Emberfall - comment JOIN to come back)")
    return "\n".join(lines)


def _next_rank(c, i):
    from .roles import RANKS
    counts = c.counts_of(i)
    for rank, actions, battles in reversed(RANKS):
        if counts["commands"] < actions or counts["battles"] < battles:
            need = []
            if counts["commands"] < actions:
                need.append(f"{actions - counts['commands']} more deeds")
            if counts["battles"] < battles:
                need.append(f"{battles - counts['battles']} more battles")
            return f"Next rank: {rank} ({' and '.join(need)})"
    return None


def headline(day_result):
    """The hook for the first two seconds of the video."""
    r = day_result
    if r.get("election"):
        e = r["election"]
        return (f"OVERTHROWN! {e['recall_share']:.0%} of the kingdom chose REVOLT." if e["recalled"]
                else f"The king keeps his crown ({e['keep_share']:.0%} knelt, {e['recall_share']:.0%} revolted).")
    biggest = [m for m in ((r.get("chronicle") or {}).get("top") or []) if m.get("drama", 0) >= 3]
    if biggest:
        return biggest[-1]["text"]
    helped = [e for e in r["events_ended"] if e.get("result") not in ("timed_out", "ended")]
    if helped:
        return helped[0]["outcome"]
    big_loss = [e for e in r["events_ended"] if e.get("result") == "timed_out" and _big(e)]
    if big_loss:
        return big_loss[0]["outcome"]
    if r["events_started"]:
        return r["events_started"][0]["title"]
    top = sorted((r.get("chronicle") or {}).get("top") or [], key=lambda m: -m.get("drama", 0))
    if top:                                     # the day's best moment leads
        return top[0]["text"]
    if False:
        top = sorted((r.get("chronicle") or {}).get("top") or [], key=lambda m: -m.get("drama", 0))
        if top:
            return top[0]["text"]
    if r["decision_lines"]:
        return r["decision_lines"][0]
    if r["events_ended"]:
        return r["events_ended"][0]["outcome"]
    if r["tallies"]:
        word, n = max(r["tallies"].items(), key=lambda kv: kv[1])
        return f"{n} subjects chose {word} today"
    return f"Day {r['day']} in {r['city']}"


def _big(e):
    """A timeout worth leading with: its outcome hits hard (e.g. the horde sacked the kingdom)."""
    from .storyteller import catalog
    out = (catalog().get(e["id"]) or {}).get("on_timeout") or {}
    return any(isinstance(v, (int, float)) and abs(v) >= 0.08 for k, v in out.items() if not k.startswith("treasury"))


def episode_script(city, r):
    return {
        "day": r["day"], "season": r["season"], "hook": headline(r),
        "narration": r["diary"],
        "highlights": (r["decision_lines"] + [e["outcome"] for e in r["events_ended"]]
                       + [e["title"] for e in r["events_started"]] + r["sim"]["notes"])[:6],
        "featured": r["featured"][:3],
        "last_24_hours": (r.get("chronicle") or {}).get("top", []),
        "your_doing_today": shoutouts(r),
        "the_king_wants": r.get("wanted", []),
        "meanwhile_in_the_north": (r.get("chronicle") or {}).get("meanwhile"),
        "tallies": r["tallies"],
        "stats": {k: r["stats"][k] for k in ("population", "approval", "treasury")},
        "next_pack": r["next_pack"],
        "caption": caption(r),
    }


def shoutouts(r, n=3):
    """The followers whose doing made today's story (one line each, different people)."""
    seen, out = set(), []
    order = {"idea_used": 0, "gift_used": 1, "helped": 2, "court": 3, "king_talked": 4}
    for x in sorted(r.get("credits") or [], key=lambda x: order.get(x["kind"], 9)):
        if x["to"] not in seen:
            seen.add(x["to"])
            out.append(f"@{x['to']} {x['text']}")
        if len(out) == n:
            break
    return out


def caption(r):
    from .living.frontier import status_line
    words = " · ".join(r["next_pack"]["commands"]) if r.get("next_pack") else ""
    thanks = shoutouts(r)
    return (f"Day {r['day']}: {headline(r)}\n\n{status_line(r['frontier'])}\n\n"
            + (("Your doing today: " + " · ".join(thanks) + "\n\n") if thanks else "")
            + "Follow and you walk into Emberfall today - bring a tent. "
            + f"Tell your character what to do in your own words, or comment {words}. "
              f"Send Aldric something useful. Suggest what he should build.\n"
              f"Comment STATUS to see your character. An AI is building a kingdom on a floating island. You live in it.")


def markdown(city, r):
    s = r["stats"]
    out = [f"# {r['city']} - Day {r['day']} (season {r['season']}, day {r['season_day']})",
           f"**Hook:** {headline(r)}", "",
           f"People **{s['population']}** (+{r['joined']} joined, -{r['sim'].get('left', 0)} left) · "
           f"Loyalty **{s['approval']:.0%}** · Purse **{s['treasury']:,.0f} gold** · Tension {s['tension']:.2f}", ""]
    if True:
        from .living.frontier import status_line
        f = r["frontier"]
        out += ["## Emberfall", status_line(f),
                f"Stage: **{f['stage']}**" + (" · crowned" if f["crowned"] else " · not crowned") +
                (f" · built: {', '.join(f['built'])}" if f["built"] else " · nothing built yet") +
                (f" · building: {', '.join(f['projects'])}" if f["projects"] else "") +
                (f" · knows: {', '.join(f['know'])}" if f["know"] else ""), ""]
    ch = r.get("chronicle")
    if ch and (ch["top"] or ch["meanwhile"]):
        out.append("## The last 24 hours")
        out += [f"- **{m['time'].split(', ')[1]}** {m['text']}" for m in ch["top"]]
        if ch["meanwhile"]:
            out.append(f"- *Meanwhile in the north:* {ch['meanwhile']}")
        out.append("")
    thanks = shoutouts(r, 5)
    if thanks:
        out += ["## Your doing today"] + [f"- {t}" for t in thanks] + [""]
    if r.get("wanted"):
        out += ["## The king is looking for", ", ".join(r["wanted"]), ""]
    out += ["## The people", "Today's comments: " + (", ".join(f"{w} {n}" for w, n in r["tallies"].items()) or "none")]
    out += [f"- {n}" for n in r["sim"]["notes"]]
    if r["events_started"] or r["events_ended"] or r["events_active"]:
        out.append("\n## Events")
        out += [f"- NEW: {e['title']}" for e in r["events_started"]]
        out += [f"- {_ended_label(e)}: {e['outcome']}" for e in r["events_ended"]]
        out += [f"- ongoing: {e['title']} ({e['days_left']} days left, " +
                (("vote so far: " + ", ".join(f"{w} {n:.0f}" for w, n in e["tally"].items())) if e.get("tally")
                 else f"{e['progress']:.0%} helped") + ")" for e in r["events_active"]]
    if r.get("election"):
        e = r["election"]
        out.append(f"\n## The Reckoning\nKneel {e['keep_share']:.0%} / Revolt {e['recall_share']:.0%} -> "
                   f"{'OVERTHROWN' if e['recalled'] else 'keeps the crown'} "
                   f"({e['keep_votes']} knelt and {e['recall_votes']} revolted in the comments)")
    out.append(f"\n## The king ({r['decided_by']})")
    out += [f"- {line}" for line in r["decision_lines"]] or ["- nothing to answer"]
    out.append(f"\n**His journal:** {r['diary']}")
    if r["featured"]:
        out.append("\n## Featured subjects")
        out += [f"- {f}" for f in r["featured"]]
    out.append(f"\n## Next post's commands\n{', '.join(r['next_pack']['commands'])}")
    if r.get("scheduled"):
        out.append("**Coming up:** " + ", ".join(f"{s['event']} (day {s['day']}, {s['source']})"
                                               for s in r["scheduled"][:5]))
    return "\n".join(out)


def _ended_label(e):
    res = e.get("result")
    if res == "mayor":
        return "SETTLED BY THE KING"
    if res in ("helped", "timed_out", "ended"):
        return f"ENDED ({res})"
    return f"DECREED: {res}"     # a decree vote: the winning choice


def save(city, r, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"day{r['day']:03d}.md").write_text(markdown(city, r))
    (outdir / f"day{r['day']:03d}.episode.json").write_text(json.dumps(episode_script(city, r), indent=1))
    if r["status_replies"]:
        (outdir / f"day{r['day']:03d}.replies.json").write_text(json.dumps(r["status_replies"], indent=1))
    if r.get("moderation"):
        (outdir / f"day{r['day']:03d}.moderation.json").write_text(json.dumps(r["moderation"], indent=1))
    if r.get("scene"):     # the 24 hours as a timeline with coordinates, for the 3D view (docs/SCENE.md)
        (outdir / f"day{r['day']:03d}.scene.json").write_text(json.dumps(r["scene"], separators=(",", ":")))
        from .recorder import scenes_index
        scenes_index(outdir)
    if r.get("outbox"):    # replies to followers' comments: what happened to their character because of them
        (outdir / f"day{r['day']:03d}.outbox.json").write_text(json.dumps(r["outbox"], indent=1))
    if r.get("moments"):   # the full log of the living world, for you - the post only gets the chronicle
        (outdir / f"day{r['day']:03d}.log.txt").write_text(
            "\n".join(f"{m['time']}  {'' if m['public'] else '(secret) '}[{m['who']}] {m['text']}"
                      for m in r["moments"]) + "\n")
