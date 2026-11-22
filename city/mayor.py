"""The king: the only part that uses a language model. (The code still calls
the ruler "mayor" - the engine is theme-neutral; the persona lives in
content/ruler.yaml.)

Each day the king reads a short brief (kingdom numbers, faction moods, the
loudest petitions, events the crowd has already weighed in on and their
options, what's buildable, and his own recent journal) and returns one
decision: taxes, budget, event responses, petition answers, maybe a project, a
royal proclamation. At night he writes a journal entry, which becomes the
narration for the day's video.

RuleMayor makes the same kind of decisions with simple rules - instant, free,
and good for running hundreds of test days. LLMMayor falls back to it if the
model doesn't answer.
"""
import json
import logging
import os
import re

import httpx
import numpy as np
import yaml

from . import storyteller
from .config import CONTENT
from .model import SERVICE_LABEL, SERVICES
from .roles import FACTION_LABEL, FACTIONS, the
from .sim import available_projects

log = logging.getLogger("mayor")


def persona():
    for name in ("ruler.yaml", "mayor.yaml"):
        f = CONTENT / name
        if f.exists():
            return yaml.safe_load(f.read_text())
    return {"name": "King Aldric", "title": "king"}


# ---------------------------------------------------------------------------- the brief
def brief(city):
    events, brand_new = [], []
    for a in city.events:
        ev = storyteller.catalog().get(a["id"], {})
        if not storyteller.can_respond(city, a):
            if not a.get("option"):
                brand_new.append(a["title"])   # the crowd hasn't had its say yet - the king waits
            continue
        e = {"event_id": a["id"], "title": a["title"], "days_left": a["days_left"],
             "options": [{"option_id": o["id"], "label": o["label"],
                          "cost": round(o.get("cost_pc", 0) * city.population()),
                          **({"pushes_toward_success": True} if (o.get("effects") or {}).get("progress") else {}),
                          **({"backs": o["side"]} if o.get("side") else {})}
                         for o in ev.get("options", [])]}
        if ev.get("choices"):
            e["kind"] = "decree vote"
            e["people_voting"] = a.get("tally", {})
        else:
            e["progress"] = round(a["progress"], 2)
            e["yesterday_comments"] = a.get("last_votes", {})
        events.append(e)
    projects = [{"id": p["id"], "name": p["name"], "cost": round(p["cost_pc"] * city.population()),
                 "days": p["days"]} for p in available_projects(city)]
    building = [f'{p["name"]} ({p["days_left"]} days left)' for p in city.projects if p["status"] == "building"]
    wards = sorted(city.ward_stats(), key=lambda w: -(w["unrest"] or 0))[:5]
    pop = max(1, city.population())
    money = ("IN DEBT - stop building and spending until the treasury recovers" if city.treasury < 0 else
             "low - be careful" if city.treasury < 10 * pop else "healthy")
    return {
        "day": city.day, "season": city.season,
        "season_day": (city.day - 1) % city.cfg["season_days"] + 1, "season_days": city.cfg["season_days"],
        "population": city.population(), "loyalty": round(city.approval(), 3),   # what the Reckoning is decided on
        "treasury": round(city.treasury), "treasury_status": money,
        # what the king's choices did lately, so he can see consequences (e.g. high taxes drive people away)
        "last_3_days": [{"day": h["day"], "loyalty": round(h["approval"], 2), "tax": h["tax_rate"],
                         "joined": h.get("joined", 0), "left": h.get("left", 0)} for h in city.history[-3:]],
        "tax_rate": round(city.tax_rate, 3), "spend_ratio": city.spend_ratio,
        "economy": round(city.economy, 3), "budget": {s: round(v, 2) for s, v in city.budget.items()},
        "services": {s: round(v, 2) for s, v in city.quality.items()},
        "faction_moods": city.faction_moods(),
        "holds_most_unrest": [{k: w[k] for k in ("name", "pop", "mood", "unrest", "protest")} for w in wards],
        "petitions": city.petitions, "events": events,
        "just_announced": brand_new,   # too new to answer: the people get the first say
        **({"what_you_did_today": [m["text"] for m in (city.living or {}).get("moments", [])
                                   if m["who"] == "king" and m["day"] == city.day][-6:],
            "what_you_heard_today": [m["text"] for m in (city.living or {}).get("moments", [])
                                     if m["who"] != "king" and m["public"] and m["day"] == city.day][-6:]}
           if city.living else {}),
        "projects_available": projects,
        "projects_building": building, "milestones": city.milestones,
        "recent": city.history[-5:],
        "agenda": list((city.plan or {}).get("agenda", [])),
    }


# ---------------------------------------------------------------------------- applying a decision
def apply_decision(city, d):
    """Clamps and applies a decision from either mayor. Returns a list of plain-English lines."""
    lines = []
    old_tax = city.tax_rate
    try:
        t = float(d.get("tax_rate", city.tax_rate))
    except (TypeError, ValueError):
        t = city.tax_rate
    city.tax_rate = float(np.clip(t, old_tax - 0.05, old_tax + 0.05))
    city.tax_rate = float(np.clip(city.tax_rate, 0.0, city.cfg["max_tax_rate"]))
    if abs(city.tax_rate - old_tax) >= 0.005:
        lines.append(f"Taxes {'raised' if city.tax_rate > old_tax else 'cut'} to {city.tax_rate:.0%}.")
        # people react to the announcement itself, not just the bill
        from .model import TAX_PAIN
        c = city.citizens
        a = c.active()
        pain = np.array([TAX_PAIN[f] for f in FACTIONS], np.float32)[c.faction]
        delta = city.tax_rate - old_tax
        shock = -pain * delta * city.cfg["tax_shock"] if delta > 0 else -delta * 0.8
        c.loyalty = np.where(a, np.clip(c.loyalty + shock, 0, 1), c.loyalty).astype(np.float32)
    try:
        city.spend_ratio = float(np.clip(float(d.get("spend_ratio", city.spend_ratio)), 0.6, 1.3))
    except (TypeError, ValueError):
        pass
    b = d.get("budget") or {}
    vals = {s: max(0.05, float(b.get(s, city.budget[s]) or 0)) for s in SERVICES}
    total = sum(vals.values())
    new_budget = {s: vals[s] / total for s in SERVICES}
    # budgets can only shift so far in a day
    city.budget = {s: city.budget[s] + float(np.clip(new_budget[s] - city.budget[s], -0.1, 0.1)) for s in SERVICES}
    tb = sum(city.budget.values())
    city.budget = {s: v / tb for s, v in city.budget.items()}

    for ch in d.get("event_choices") or []:
        a = next((e for e in city.events if e["id"] == ch.get("event_id")), None)
        if a and storyteller.can_respond(city, a):
            r = storyteller.choose_option(city, a, ch.get("option_id"))
            if r:
                lines.append(r["option_text"])

    c = city.citizens
    for ans in d.get("petition_answers") or []:
        p = next((x for x in city.petitions if x["id"] == ans.get("petition_id")), None)
        if not p:
            continue
        m = c.active() & ((c.faction == FACTIONS.index(p["faction"])) if p["faction"] in FACTIONS
                          else (c.ward == int(p["id"].split("-w")[-1])) if "-w" in p["id"] else c.active())
        verdict = ans.get("answer", "defer")
        if verdict == "accept":
            c.loyalty[m] = np.clip(c.loyalty[m] + 0.03, 0, 1)
            for s in SERVICES:
                if s in p["ask"]:
                    city.budget[s] += 0.04
            p["answer"] = "accepted"
        elif verdict == "reject":
            c.loyalty[m] = np.clip(c.loyalty[m] - 0.02, 0, 1)
            p["answer"] = "rejected"
        else:
            p["answer"] = "deferred"
        p["words"] = str(ans.get("words", ""))[:200]
        lines.append(f'{p["from"]} asked for {p["ask"]}: {p["answer"]}.')
    tb = sum(city.budget.values())
    city.budget = {s: v / tb for s, v in city.budget.items()}

    pid = (d.get("project") or "").strip()
    proj = next((p for p in available_projects(city) if p["id"] == pid), None)
    if proj:
        cost = proj["cost_pc"] * city.population()
        if city.treasury - cost >= 0:   # no building on credit
            city.treasury -= cost
            city.projects.append({"id": proj["id"], "name": proj["name"], "status": "building",
                                  "days_left": proj["days"], "started": city.day})
            lines.append(f'Work began on {the(proj["name"])} ({cost:,.0f} gold).')
    speech = str(d.get("speech", "")).strip()[:400]
    return lines, speech


# ---------------------------------------------------------------------------- rule-based mayor
class RuleMayor:
    name = "rules"

    def decide(self, city):
        b = brief(city)
        fm = {k: (v if v is not None else 0.5) for k, v in b["faction_moods"].items()}
        tax = city.tax_rate
        if city.treasury < 0:
            tax += 0.02
        elif b["loyalty"] < 0.45 or fm.get("guilds", 0.5) < 0.4:
            tax -= 0.02
        elif city.treasury > 30 * max(1, b["population"]) * 10:
            tax -= 0.01
        unhappiest = min(fm, key=fm.get)
        from .model import FACTION_WANTS
        favorite = max(FACTION_WANTS[unhappiest], key=FACTION_WANTS[unhappiest].get)
        budget = dict(city.budget)
        budget[favorite] += 0.05
        choices = []
        for e in b["events"]:
            if not e["options"]:
                continue
            if e.get("kind") == "decree vote":   # back whatever the people are voting for
                tally = e.get("people_voting") or {}
                lead = max(tally, key=tally.get) if tally else None
                pick = next((o for o in e["options"] if o.get("backs") == lead), None)
                if pick:
                    choices.append({"event_id": e["event_id"], "option_id": pick["option_id"], "why": "rules"})
                continue
            affordable = [o for o in e["options"] if o["cost"] <= max(0, city.treasury) * 0.3]
            if not affordable:
                affordable = [o for o in e["options"] if o["cost"] <= 0]
            if not affordable:
                continue
            helping = [o for o in affordable if o.get("pushes_toward_success")]
            pick = min(helping or affordable, key=lambda o: abs(o["cost"]))
            choices.append({"event_id": e["event_id"], "option_id": pick["option_id"], "why": "rules"})
        answers = []
        for p in b["petitions"]:
            answers.append({"petition_id": p["id"], "answer": "accept" if p["signatures"] > b["population"] * 0.3
                            else "defer", "words": ""})
        project = ""
        if b["projects_available"] and not b["projects_building"]:
            cheap = sorted(b["projects_available"], key=lambda p: p["cost"])
            if cheap and city.treasury > cheap[0]["cost"] * 2.5:
                project = cheap[0]["id"]
        pop = max(1, b["population"])
        spend = (0.85 if city.treasury < 0 else 0.92 if city.treasury < 15 * pop
                 else 1.1 if city.treasury > 40 * pop else 1.0)   # save up, then spend
        return {"thought": f"Focus on {FACTION_LABEL[unhappiest]}.", "tax_rate": tax, "spend_ratio": spend,
                "budget": budget, "event_choices": choices, "petition_answers": answers, "project": project,
                "speech": f"The crown hears you, {FACTION_LABEL[unhappiest]}. Better "
                          f"{SERVICE_LABEL[favorite].lower()} are coming."}

    def diary(self, city, day_summary, people=None):
        return (f"Day {city.day}. Loyalty {city.approval():.0%}. " + " ".join(day_summary[:3])).strip()


# ---------------------------------------------------------------------------- language-model mayor
DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {"type": "string"},
        "tax_rate": {"type": "number"},
        "spend_ratio": {"type": "number"},
        "budget": {"type": "object", "properties": {s: {"type": "number"} for s in SERVICES},
                   "required": SERVICES},
        "event_choices": {"type": "array", "items": {"type": "object", "properties": {
            "event_id": {"type": "string"}, "option_id": {"type": "string"}, "why": {"type": "string"}},
            "required": ["event_id", "option_id", "why"]}},
        "petition_answers": {"type": "array", "items": {"type": "object", "properties": {
            "petition_id": {"type": "string"}, "answer": {"type": "string", "enum": ["accept", "reject", "defer"]},
            "words": {"type": "string"}}, "required": ["petition_id", "answer", "words"]}},
        "project": {"type": "string"},
        "speech": {"type": "string"},
    },
    "required": ["thought", "tax_rate", "spend_ratio", "budget", "event_choices", "petition_answers", "project",
                 "speech"],
}


def overused_phrases(entries, top=8):
    """2-3 word phrases that showed up in at least 3 recent journal entries ('i daresay', 'twice as')."""
    import re
    from collections import Counter
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
    worn = [g for g, k in seen.most_common() if k >= 3 and not g.startswith("@")]
    out = []
    for g in worn:   # keep the longest version of overlapping phrases
        if not any(g in o for o in out):
            out = [o for o in out if o not in g] + [g]
    return out[:top]


class LLMMayor:
    name = "llm"

    def __init__(self):
        self.url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        self.model = os.environ.get("OLLAMA_MODEL", "qwen3:14b")
        self.ctx = int(os.environ.get("OLLAMA_NUM_CTX", "6144"))
        self.fallback = RuleMayor()
        self.p = persona()

    def _chat(self, system, user, schema=None, max_tokens=900):
        body = {"model": self.model, "stream": False, "think": False, "keep_alive": "30m",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "options": {"temperature": 0.8, "num_ctx": self.ctx, "num_predict": max_tokens}}
        if schema:
            body["format"] = schema
        with httpx.Client(timeout=300) as cl:
            r = cl.post(f"{self.url}/api/chat", json=body)
            if r.status_code == 400:
                body.pop("think", None)
                r = cl.post(f"{self.url}/api/chat", json=body)
            r.raise_for_status()
            text = r.json()["message"]["content"]
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

    def _identity(self, city):
        p = self.p
        journal = city.mayor.get("journal", [])[-5:]
        title = p.get("title", "king")
        lines = [f"You are {p.get('name')}, the {title} of {city.name}. {p.get('personality', '')}",
                 f"Your ambition: {p.get('ambition', '')} Your flaw: {p.get('flaw', '')}",
                 f"Voice: {p.get('voice', 'theatrical and royal, with a sharp, snarky wit')}.",
                 "Your subjects are real people who follow the kingdom online. They comment to work, trade, train, "
                 "grumble and vote on decrees. At the end of each 30-day season comes the Reckoning: they vote to "
                 "KNEEL (you keep the crown) or REVOLT (you are overthrown)."]
        if journal:
            lines.append("Your recent journal:")
            lines += [f"- Day {j['day']}: {j['diary'][:300]}" for j in journal]
        promises = city.mayor.get("promises", [])[-4:]
        if promises:
            lines.append("Promises you've made publicly: " + "; ".join(promises))
        return "\n".join(lines)

    def decide(self, city):
        b = brief(city)
        system = self._identity(city) + f"""

Decide today's royal policy. Reply with JSON only:
- "thought": your private reasoning in one or two sentences.
- "tax_rate": 0.0-0.45 (it can only move 5 points a day).
- "spend_ratio": 0.6-1.3 (spending as a share of today's tax revenue; above 1 drains the treasury).
- "budget": shares for {", ".join(SERVICES)} (they get normalised).
- "event_choices": for events in the brief, pick one option_id (or leave the event out to wait). For a
  "decree vote", an option that "backs" a side puts your crown behind it: if the people are voting the
  other way you overrule them - you win, but they will remember. "just_announced" events are too new: the
  people get the first say, you can't answer those yet.
- "petition_answers": accept, reject or defer each petition, with a few words in your voice.
- "project": an id from projects_available to start building, or "". You can't build on credit.
- "speech": one or two sentences you proclaim publicly today, in character.
If the brief has an "agenda", those are pressing matters you're expected to address today.
Watch "treasury_status": a king in debt can't pay his guards."""
        try:
            d = json.loads(self._chat(system, json.dumps(b, indent=1), DECISION_SCHEMA))
            d["_by"] = "llm"
            return d
        except Exception as e:  # noqa: BLE001
            log.warning("mayor model failed (%s) - using rules today", e)
            d = self.fallback.decide(city)
            d["_by"] = "rules (fallback)"
            return d

    def diary(self, city, day_summary, people=None):
        system = self._identity(city) + (
            "\n\nIt's late. Write tonight's entry in your royal journal: 4-6 sentences, first person, in character, "
            "honest about how you feel and what you'll do next. Mention specific things that happened. Your subjects "
            "are real people: if you mention anyone, use only the subjects listed below, by their @handle. Never "
            "invent names, people, groups or places. No headings.")
        user = "What happened today:\n" + "\n".join(f"- {s}" for s in day_summary)
        journal = [j["diary"] for j in city.mayor.get("journal", [])]
        prev = journal[-2:]
        if prev:
            user += ("\n\nYour last entries (don't repeat their phrases, structure or endings - "
                     "every entry should sound fresh):\n" + "\n".join(f"- {p[:400]}" for p in prev))
        worn = overused_phrases(journal[-6:])
        if worn:
            user += "\n\nPhrases you've worn out - do not use them again: " + "; ".join(f'"{w}"' for w in worn)
        if people:
            user += "\n\nSubjects you might mention (real people):\n" + "\n".join(f"- {p}" for p in people)
        try:
            return self._chat(system, user, max_tokens=400)
        except Exception as e:  # noqa: BLE001
            log.warning("diary failed (%s)", e)
            return self.fallback.diary(city, day_summary)


def make(kind):
    return LLMMayor() if kind == "llm" else RuleMayor()
