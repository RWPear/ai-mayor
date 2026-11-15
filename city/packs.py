"""Command packs: the comment words for one post, and what they do.

    post: day-14
    window_hours: 24
    event: rival_war            # optional: which event help/hinder words count toward
    commands:
      ATTACK: event.help
      DEFEND: event.help
      SURRENDER: event.hinder
      WORK: work

STATUS (show me my citizen) and JOIN / MOVE IN work on every post.
One action counts per person per post - their latest valid comment wins.
"""
import re
from pathlib import Path

import numpy as np
import yaml

from .effects import COMMAND_EFFECTS

ALWAYS = {"STATUS": "status", "JOIN": "join", "MOVE IN": "join", "MOVEIN": "join"}


def load(path):
    p = yaml.safe_load(Path(path).read_text())
    cmds = {str(k).upper().strip(): (v if isinstance(v, str) else v.get("effect")) for k, v in
            (p.get("commands") or {}).items()}
    for word, eff in cmds.items():
        if eff not in COMMAND_EFFECTS:
            raise ValueError(f"pack {path}: {word} uses unknown effect '{eff}'. Known: {sorted(COMMAND_EFFECTS)}")
    return {"post": p.get("post", Path(path).stem), "window_hours": p.get("window_hours", 24),
            "event": p.get("event"), "commands": cmds, "caption": p.get("caption", "")}


def from_event(event, extra=None):
    """Builds a pack from an active event's suggested commands (+ optional daily basics)."""
    cmds = {w.upper(): f"event.{v}" for w, v in (event.get("commands") or {}).items()}
    cmds.update(extra or {})
    return {"post": f"event-{event['id']}", "window_hours": 24, "event": event["id"], "commands": cmds,
            "caption": ""}


def parse(comments, pack):
    """comments: [{username, text, timestamp}] -> ({username: word}, {status users}, {join users}).
    Latest valid action per user wins. Unknown words are ignored."""
    words = dict(pack["commands"])
    actions, status, joins = {}, set(), set()
    for cm in sorted(comments, key=lambda c: c.get("timestamp", 0)):
        user = str(cm.get("username", "")).strip().lstrip("@").lower()
        text = " " + re.sub(r"[^A-Za-z ]", " ", str(cm.get("text", ""))).upper() + " "
        if not user:
            continue
        if " STATUS " in text:
            status.add(user)
        if " MOVE IN " in text or " MOVEIN " in text or " JOIN " in text:
            joins.add(user)
        for w in words:
            if f" {w} " in text:
                actions[user] = w
                joins.add(user)  # any command moves you in
                break
    return actions, status, joins


def apply(city, ctx, actions, pack):
    """Runs each command's effect on the citizens who chose it. Returns tallies {word: count}."""
    c = city.citizens
    by_word = {}
    for user, word in actions.items():
        i = c.index.get(user)
        if i is not None and c.status[i] == 0:
            by_word.setdefault(word, []).append(i)
    tallies = {}
    for word, idx in by_word.items():
        idx = np.array(idx, dtype=np.int64)
        eff = pack["commands"][word]
        COMMAND_EFFECTS[eff](city, idx, ctx, pack.get("event"))
        c.counts["commands"][idx] += 1
        c.last_cmd[idx] = city.day
        tallies[word] = len(idx)
    return tallies
