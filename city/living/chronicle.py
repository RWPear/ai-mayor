"""The daily post is a summary, not a log.

Out of everything that happened since the last post, pick the 3 most dramatic
moments (no more than 2 from the same character), plus one "meanwhile in the
north" line the king doesn't know about - the audience gets to see both sides.
Everything else stays in the full log and on people's STATUS cards.
"""


def pick(moments, top=3):
    pool = [m for m in moments if m["drama"] >= 1 and (m["who"] != "warlord" or m["public"])]
    pool.sort(key=lambda m: (-m["drama"], -m["clock"]))
    chosen, per, kinds = [], {}, set()
    for m in pool:
        actor = "subjects" if m["who"].startswith("@") else m["who"]
        kind = m.get("kind", "world")
        if per.get(actor, 0) >= 2 or any(m["text"] == c["text"] for c in chosen) or \
                (kind in kinds and not actor == "subjects"):   # one summons a day is plenty
            continue
        kinds.add(kind)
        chosen.append(m)
        per[actor] = per.get(actor, 0) + 1
        if len(chosen) == top:
            break
    chosen.sort(key=lambda m: m["clock"])
    secret = [m for m in moments if m["who"] == "warlord" and not m["public"]]
    secret.sort(key=lambda m: (-m["drama"], -m["clock"]))
    return {"top": [{"time": m["time"], "who": m["who"], "text": m["text"], "drama": m["drama"]} for m in chosen],
            "meanwhile": secret[0]["text"] if secret else None}
