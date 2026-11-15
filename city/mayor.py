"""The mayor: the only part that uses a language model.

Each day the mayor reads a short brief (city numbers, faction moods, the
loudest petitions, active events and their options, what's buildable, and its
own recent journal) and returns one decision: taxes, budget, event responses,
petition answers, maybe a project, a public statement. At night it writes a
diary entry, which becomes the narration for the day's video.

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
from .roles import FACTION_LABEL, FACTIONS
from .sim import available_projects

log = logging.getLogger("mayor")


def persona():
    f = CONTENT / "mayor.yaml"
    return yaml.safe_load(f.read_text()) if f.exists() else {"name": "Mayor Vale"}


# ---------------------------------------------------------------------------- the brief
def brief(city):
    events = []
    for a in city.events:
        ev = storyteller.catalog().get(a["id"], {})
        events.append({"event_id": a["id"], "title": a["title"], "days_left": a["days_left"],
                       "progress": round(a["progress"], 2), "already_chose": a.get("option"),
                       "options": [{"option_id": o["id"], "label": o["label"],
                                    "cost": round(o.get("cost_pc", 0) * city.population())}
                                   for o in ev.get("options", [])]})
    projects = [{"id": p["id"], "name": p["name"], "cost": round(p["cost_pc"] * city.population()),
                 "days": p["days"]} for p in available_projects(city)]
    building = [f'{p["name"]} ({p["days_left"]} days left)' for p in city.projects if p["status"] == "building"]
    wards = sorted(city.ward_stats(), key=lambda w: -(w["unrest"] or 0))[:5]
    return {
        "day": city.day, "season": city.season,
        "season_day": (city.day - 1) % city.cfg["season_days"] + 1, "season_days": city.cfg["season_days"],
        "population": city.population(), "approval": round(city.approval(), 3),
        "treasury": round(city.treasury), "tax_rate": round(city.tax_rate, 3), "spend_ratio": city.spend_ratio,
        "economy": round(city.economy, 3), "budget": {s: round(v, 2) for s, v in city.budget.items()},
        "services": {s: round(v, 2) for s, v in city.quality.items()},
        "faction_moods": city.faction_moods(),
        "wards_most_unrest": [{k: w[k] for k in ("name", "pop", "mood", "unrest", "protest")} for w in wards],
        "petitions": city.petitions, "events": events, "projects_available": projects,
        "projects_building": building, "milestones": city.milestones,
        "recent": city.history[-5:],
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
        if a and not a.get("option"):
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
        if city.treasury - cost > -0.5 * cost:
            city.treasury -= cost
            city.projects.append({"id": proj["id"], "name": proj["name"], "status": "building",
                                  "days_left": proj["days"], "started": city.day})
            lines.append(f'Construction started on the {proj["name"]} (${cost:,.0f}).')
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
        elif b["approval"] < 0.45 or fm.get("business", 0.5) < 0.4:
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
            if e["already_chose"] or not e["options"]:
                continue
            affordable = [o for o in e["options"] if o["cost"] <= max(0, city.treasury) * 0.3]
            if not affordable:
                affordable = [o for o in e["options"] if o["cost"] <= 0]
            if not affordable:
                continue
            pick = min(affordable, key=lambda o: abs(o["cost"]))
            choices.append({"event_id": e["event_id"], "option_id": pick["option_id"], "why": "rules"})
        answers = []
        for p in b["petitions"]:
            answers.append({"petition_id": p["id"], "answer": "accept" if p["signatures"] > b["population"] * 0.3
                            else "defer", "words": ""})
        project = ""
        if b["projects_available"] and not b["projects_building"]:
            cheap = sorted(b["projects_available"], key=lambda p: p["cost"])
            if cheap and city.treasury > cheap[0]["cost"] * 1.5:
                project = cheap[0]["id"]
        spend = 0.85 if city.treasury < 0 else (1.1 if city.treasury > 40 * max(1, b["population"]) else 1.0)
        return {"thought": f"Focus on {FACTION_LABEL[unhappiest]}.", "tax_rate": tax, "spend_ratio": spend,
                "budget": budget, "event_choices": choices, "petition_answers": answers, "project": project,
                "speech": f"We hear you, {FACTION_LABEL[unhappiest]}. More {SERVICE_LABEL[favorite].lower()} is coming."}

    def diary(self, city, day_summary):
        return (f"Day {city.day}. Approval {city.approval():.0%}. " + " ".join(day_summary[:3])).strip()


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
        lines = [f"You are {p.get('name')}, the mayor of {city.name}. {p.get('personality', '')}",
                 f"Your ambition: {p.get('ambition', '')} Your flaw: {p.get('flaw', '')}",
                 "The citizens are real people who follow the city online. They comment to work, protest, shop "
                 "and vote. At the end of each 30-day season they vote on whether to recall you."]
        if journal:
            lines.append("Your recent journal:")
            lines += [f"- Day {j['day']}: {j['diary'][:300]}" for j in journal]
        promises = city.mayor.get("promises", [])[-4:]
        if promises:
            lines.append("Promises you've made publicly: " + "; ".join(promises))
        return "\n".join(lines)

    def decide(self, city):
        b = brief(city)
        system = self._identity(city) + """

Decide today's policy. Reply with JSON only:
- "thought": your private reasoning in one or two sentences.
- "tax_rate": 0.0-0.45 (it can only move 5 points a day).
- "spend_ratio": 0.6-1.3 (spending as a share of today's tax revenue; above 1 drains the treasury).
- "budget": shares for safety, housing, transit, culture (they get normalised).
- "event_choices": for active events you haven't responded to, pick one option_id (or leave the event out to wait).
- "petition_answers": accept, reject or defer each petition, with a few words in your voice.
- "project": an id from projects_available to start building, or "".
- "speech": one or two sentences you say publicly today, in character."""
        try:
            d = json.loads(self._chat(system, json.dumps(b, indent=1), DECISION_SCHEMA))
            d["_by"] = "llm"
            return d
        except Exception as e:  # noqa: BLE001
            log.warning("mayor model failed (%s) - using rules today", e)
            d = self.fallback.decide(city)
            d["_by"] = "rules (fallback)"
            return d

    def diary(self, city, day_summary):
        system = self._identity(city) + "\n\nIt's late. Write today's diary entry: 4-6 sentences, first person, " \
                                        "in character, honest about how you feel and what you'll do next. Mention " \
                                        "specific events and any residents named. No headings."
        user = "What happened today:\n" + "\n".join(f"- {s}" for s in day_summary)
        try:
            return self._chat(system, user, max_tokens=400)
        except Exception as e:  # noqa: BLE001
            log.warning("diary failed (%s)", e)
            return self.fallback.diary(city, day_summary)


def make(kind):
    return LLMMayor() if kind == "llm" else RuleMayor()
