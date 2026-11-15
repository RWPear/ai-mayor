"""Turning a day into things people see: the daily report, the episode script
for the video, and STATUS citizen cards (replies to comments).
"""
import json

from .model import SERVICE_LABEL
from .roles import FACTION_LABEL, FACTIONS, JOB_NAMES


def mood_word(m):
    if m < 0.2: return "furious 😡"
    if m < 0.35: return "fed up 😠"
    if m < 0.5: return "uneasy 😕"
    if m < 0.65: return "doing okay 🙂"
    if m < 0.8: return "happy 😄"
    return "thriving 🤩"


def status_card(city, i):
    """A short reply to a STATUS comment. Fits easily in an Instagram comment reply."""
    c = city.citizens
    w = city.wards[int(c.ward[i])]
    job = JOB_NAMES[int(c.job[i])]
    title = c.title(i)
    lines = [f"🏙️ @{c.handles[i]} - {c.names[i]}, {job}" + (f" · {title}" if title else ""),
             f"📍 {w['name']} ({w['trait']}) · {FACTION_LABEL[FACTIONS[int(c.faction[i])]]}",
             f"Mood: {mood_word(float(c.mood[i]))} · Savings: ${c.wealth[i]:,.0f} · "
             f"Trusts the mayor: {c.loyalty[i]:.0%}",
             f"Resident since day {int(c.joined[i])} · {int(c.counts['commands'][i])} actions"]
    if w.get("councilor") == i:
        lines.append(f"⭐ Councilor for {w['name']}")
    story = c.story.get(int(i))
    if story:
        lines.append("Latest: " + story[-1])
    if c.status[i] == 1:
        lines.insert(1, "(moved away - comment JOIN to come back)")
    return "\n".join(lines)


def headline(day_result):
    """The hook for the first two seconds of the video."""
    r = day_result
    for n in r["sim"]["notes"]:
        if n.startswith("MILESTONE") or n.startswith("Riot"):
            return n.replace("MILESTONE: ", "Unlocked: ")
    if r.get("election"):
        e = r["election"]
        return "The people voted to RECALL the mayor!" if e["recalled"] else "The mayor survived the recall vote!"
    helped = [e for e in r["events_ended"] if e.get("result") in ("helped", "mayor")]
    if helped:
        return helped[0]["outcome"]
    if r["events_started"]:
        return r["events_started"][0]["title"]
    for n in r["sim"]["notes"]:
        if "protest" in n.lower() or "moved away" in n:
            return n
    if r["decision_lines"]:
        return r["decision_lines"][0]
    if r["events_ended"]:
        return r["events_ended"][0]["outcome"]
    if r["tallies"]:
        word, n = max(r["tallies"].items(), key=lambda kv: kv[1])
        return f"{n} residents chose {word} today"
    return f"Day {r['day']} in {r['city']}"


def episode_script(city, r):
    return {
        "day": r["day"], "season": r["season"], "hook": headline(r),
        "narration": r["diary"], "speech": r["speech"],
        "highlights": (r["decision_lines"] + [e["outcome"] for e in r["events_ended"]]
                       + [e["title"] for e in r["events_started"]] + r["sim"]["notes"])[:6],
        "featured": r["featured"][:3],
        "tallies": r["tallies"],
        "stats": {k: r["stats"][k] for k in ("population", "approval", "treasury", "tax_rate")},
        "next_pack": r["next_pack"],
        "caption": caption(r),
    }


def caption(r):
    words = " · ".join(r["next_pack"]["commands"]) if r.get("next_pack") else ""
    return (f"Day {r['day']}: {headline(r)}\n\n"
            f"Comment to act (one per post, latest counts): {words}\n"
            f"Comment STATUS to see your citizen. Follow to move in. 🏙️\n"
            f"An AI runs this city. You live in it.")


def markdown(city, r):
    s = r["stats"]
    out = [f"# {r['city']} - Day {r['day']} (season {r['season']}, day {r['season_day']})",
           f"**Hook:** {headline(r)}", "",
           f"Population **{s['population']}** (+{r['joined']} joined, -{r['sim'].get('left', 0)} left) · "
           f"Approval **{s['approval']:.0%}** · Treasury **${s['treasury']:,.0f}** · Tax **{s['tax_rate']:.0%}** · "
           f"Economy {s['economy']:.2f} · Tension {s['tension']:.2f}", "",
           "**Services:** " + ", ".join(f"{SERVICE_LABEL[k]} {v:.2f}" for k, v in s["services"].items()),
           "**Factions:** " + ", ".join(f"{FACTION_LABEL[k]} {v:.2f}" for k, v in s["factions"].items() if v is not None),
           "", "## The people", "Comment tallies: " + (", ".join(f"{w} {n}" for w, n in r["tallies"].items()) or "none")]
    out += [f"- {n}" for n in r["sim"]["notes"]]
    if r["events_started"] or r["events_ended"] or r["events_active"]:
        out.append("\n## Events")
        out += [f"- NEW: {e['title']}" for e in r["events_started"]]
        out += [f"- ENDED ({e['result']}): {e['outcome']}" for e in r["events_ended"]]
        out += [f"- ongoing: {e['title']} ({e['days_left']} days left, {e['progress']:.0%} helped)"
                for e in r["events_active"]]
    if r.get("election"):
        e = r["election"]
        out.append(f"\n## Recall vote\nKeep {e['keep_share']:.0%} / Recall {e['recall_share']:.0%} -> "
                   f"{'RECALLED' if e['recalled'] else 'survives'}")
    out.append(f"\n## The mayor ({r['decided_by']})")
    out += [f"- {line}" for line in r["decision_lines"]] or ["- no changes"]
    if r["speech"]:
        out.append(f"> \"{r['speech']}\"")
    out.append(f"\n**Diary:** {r['diary']}")
    if r["featured"]:
        out.append("\n## Featured residents")
        out += [f"- {f}" for f in r["featured"]]
    out.append(f"\n## Next post's commands\n{', '.join(r['next_pack']['commands'])}")
    return "\n".join(out)


def save(city, r, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"day{r['day']:03d}.md").write_text(markdown(city, r))
    (outdir / f"day{r['day']:03d}.episode.json").write_text(json.dumps(episode_script(city, r), indent=1))
    if r["status_replies"]:
        (outdir / f"day{r['day']:03d}.replies.json").write_text(json.dumps(r["status_replies"], indent=1))
