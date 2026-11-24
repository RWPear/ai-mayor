"""The king's evening: once a day he answers the events the crowd has already weighed in on, and writes his
journal (the narration for the day's video). Everything else he does - walking, gathering, building, talking -
happens hour by hour in city/living/agents.py.

RuleMayor does it with simple rules (instant, free, for test runs). LLMMayor uses the model and falls back to
the rules if it doesn't answer. (The code still says "mayor"; the persona lives in content/ruler.yaml.)
"""
import json
import logging
import os
import re
from collections import Counter

import yaml

from . import storyteller
from .config import CONTENT

log = logging.getLogger("mayor")


def persona():
    f = CONTENT / "ruler.yaml"
    return yaml.safe_load(f.read_text()) if f.exists() else {"name": "King Aldric", "title": "king"}


def open_events(city):
    """Events he can answer now (the people get the first say on anything brand new)."""
    out = []
    for a in city.events:
        ev = storyteller.catalog().get(a["id"], {})
        if not ev.get("options") or not storyteller.can_respond(city, a):
            continue
        e = {"event_id": a["id"], "title": a["title"], "days_left": a["days_left"],
             "options": [{"option_id": o["id"], "label": o["label"],
                          "cost": round(o.get("cost_pc", 0) * city.population()),
                          **({"pushes_toward_success": True} if (o.get("effects") or {}).get("progress") else {}),
                          **({"backs": o["side"]} if o.get("side") else {})}
                         for o in ev.get("options", [])]}
        if ev.get("choices"):
            e["kind"] = "vote"
            e["people_voting"] = a.get("tally", {})
        else:
            e["progress"] = round(a["progress"], 2)
        out.append(e)
    return out


def apply_decision(city, d):
    """His answers to events. Returns plain-English lines."""
    lines = []
    for ch in d.get("event_choices") or []:
        a = next((e for e in city.events if e["id"] == ch.get("event_id")), None)
        if a and storyteller.can_respond(city, a):
            r = storyteller.choose_option(city, a, ch.get("option_id"))
            if r:
                lines.append(r["option_text"])
    return lines


class RuleMayor:
    name = "rules"

    def decide(self, city):
        choices = []
        for e in open_events(city):
            if e.get("kind") == "vote":            # back whatever the people are voting for
                tally = e.get("people_voting") or {}
                lead = max(tally, key=tally.get) if tally else None
                pick = next((o for o in e["options"] if o.get("backs") == lead), None)
            else:
                affordable = [o for o in e["options"] if o["cost"] <= max(0, city.treasury) * 0.5] or \
                             [o for o in e["options"] if o["cost"] <= 0]
                helping = [o for o in affordable if o.get("pushes_toward_success")]
                pick = min(helping or affordable, key=lambda o: abs(o["cost"])) if affordable else None
            if pick:
                choices.append({"event_id": e["event_id"], "option_id": pick["option_id"], "why": "rules"})
        return {"event_choices": choices, "_by": "rules"}

    def diary(self, city, day_summary, people=None):
        return (f"Day {city.day}. " + " ".join(day_summary[:3])).strip()


EVENT_SCHEMA = {"type": "object", "properties": {
    "thought": {"type": "string"},
    "event_choices": {"type": "array", "items": {"type": "object", "properties": {
        "event_id": {"type": "string"}, "option_id": {"type": "string"}, "why": {"type": "string"}},
        "required": ["event_id", "option_id", "why"]}}},
    "required": ["thought", "event_choices"]}


def overused_phrases(entries, top=8):
    """2-3 word phrases that showed up in at least 3 recent journal entries ('i daresay', 'twice as')."""
    stop = {"the", "a", "an", "and", "of", "to", "in", "is", "it", "my", "i", "that", "for", "be", "as", "on", "with",
            "but", "this", "they", "their", "have", "has", "will", "not", "are", "was", "me", "at", "by", "so", "if"}
    seen = Counter()
    for e in entries:
        words = re.findall(r"[a-z']+", e.lower())
        grams = set()
        for n in (2, 3):
            for i in range(len(words) - n + 1):
                g = words[i:i + n]
                if (g[0] == "i" or g[0] not in stop) and sum(w not in stop for w in g) >= 1:
                    grams.add(" ".join(g))
        seen.update(grams)
    out = []
    for g in (g for g, k in seen.most_common() if k >= 3 and not g.startswith("@")):
        if not any(g in o for o in out):          # keep the longest version of overlapping phrases
            out = [o for o in out if o not in g] + [g]
    return out[:top]


class LLMMayor:
    name = "llm"

    def __init__(self):
        self.model = os.environ.get("OLLAMA_MODEL", "qwen3:14b")
        self.fallback = RuleMayor()
        self.p = persona()

    def _chat(self, system, user, schema=None, max_tokens=900):
        """Through city.llm, so it gets room to finish and shows up in the mind tab like every other call."""
        from .llm import LLM
        if not hasattr(self, "_llm"):
            self._llm = LLM(model=self.model)
        return self._llm.chat(system, user, schema, max_tokens, 0.8)

    def _identity(self, city):
        p = self.p
        lines = [f"You are {p.get('name', 'Aldric')}, who calls himself king of {city.name}, a settlement on a "
                 f"floating island that you're building from nothing."]
        king = ((city.living or {}).get("agents") or {}).get("king")
        if king:
            from .living.life import who_am_i
            me_now = who_am_i(king)
            lines.append(f"Who you've become so far, in your own words: {me_now}." if me_now else
                         "You haven't figured out who you are yet. Be honest about that.")
            if king.get("character"):
                lines.append(king["character"])
        lines.append("Your people are real people who follow Emberfall online and tell their characters what to do "
                     "in the comments.")
        journal = city.mayor.get("journal", [])[-5:]
        if journal:
            lines.append("Your recent journal:")
            lines += [f"- Day {j['day']}: {j['diary'][:300]}" for j in journal]
        return "\n".join(lines)

    def decide(self, city):
        events = open_events(city)
        if not events:                             # nothing to answer: no call
            return {"event_choices": [], "_by": "llm"}
        system = self._identity(city) + """

These matters are waiting for your answer. Reply with JSON only:
- "thought": your private reasoning in one or two sentences.
- "event_choices": for each, pick one option_id (or leave it out to wait). For a "vote", an option that "backs"
  a side puts your word behind it: if the people are voting the other way you overrule them - you win, but they
  will remember. Options with a cost come out of your purse."""
        try:
            d = json.loads(self._chat(system, json.dumps({"purse": round(city.treasury), "events": events}, indent=1),
                                      EVENT_SCHEMA))
            d["_by"] = "llm"
            return d
        except Exception as e:  # noqa: BLE001
            log.warning("king's answers failed (%s) - using rules today", e)
            d = self.fallback.decide(city)
            d["_by"] = "rules (fallback)"
            return d

    def diary(self, city, day_summary, people=None):
        system = self._identity(city) + (
            "\n\nIt's late. Write tonight's entry in your journal: 4-6 sentences, first person, in character, "
            "honest about how you feel and what you'll do next. Mention specific things that happened. Your people "
            "are real: if you mention anyone, use only the people listed below, by their @handle. Never invent "
            "names, people, groups or places. No headings.")
        user = "What happened today:\n" + "\n".join(f"- {s}" for s in day_summary)
        journal = [j["diary"] for j in city.mayor.get("journal", [])]
        if journal[-2:]:
            user += ("\n\nYour last entries (don't repeat their phrases, structure or endings - "
                     "every entry should sound fresh):\n" + "\n".join(f"- {p[:400]}" for p in journal[-2:]))
        worn = overused_phrases(journal[-6:])
        if worn:
            user += "\n\nPhrases you've worn out - do not use them again: " + "; ".join(f'"{w}"' for w in worn)
        if people:
            user += "\n\nPeople you might mention (real people):\n" + "\n".join(f"- {p}" for p in people)
        try:
            return self._chat(system, user, max_tokens=400)
        except Exception as e:  # noqa: BLE001
            log.warning("diary failed (%s)", e)
            return self.fallback.diary(city, day_summary)


def make(kind):
    return LLMMayor() if kind == "llm" else RuleMayor()
