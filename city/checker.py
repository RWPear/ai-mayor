"""`python -m city.run check` - catches mistakes in content before they reach a city.

Checks events, projects, milestones, packs and season plans: missing fields, typos in
effect keys, follow-ups pointing at events that don't exist, conditions that won't
parse, placeholders that won't fill, plans pointing at missing packs.
"""
import re
import string
from pathlib import Path

import yaml

from .config import CONTENT, ROOT, load as load_cfg
from .effects import COMMAND_EFFECTS
from .model import SERVICES, WARD_TRAITS
from .roles import FACTIONS

EFFECT_HEADS = {"treasury", "treasury_pc", "economy", "service", "mood", "loyalty", "wealth_pc", "unrest"}
TARGETS = {"", "all", "ward", *FACTIONS}
PLACEHOLDERS = {"ward", "councilor", "resident"}
STAT_NAMES = {"pop", "approval", "treasury", "tax", "economy", "day", "season", "season_day", "unrest", "has",
              "happened", "result", "active", "built", "min", "max", "and", "or", "not", "None", "True", "False",
              "helped", "timed_out", "mayor"} | {f"q_{s}" for s in SERVICES} | {f"faction_{f}" for f in FACTIONS}


def _yaml(path, problems):
    try:
        return yaml.safe_load(Path(path).read_text())
    except Exception as e:  # noqa: BLE001
        problems.append(f"{path}: can't read YAML ({e})")
        return None


def _effects(where, eff, problems, event_ids=None):
    if eff is None:
        return
    if not isinstance(eff, dict):
        problems.append(f"{where}: effects should be a mapping, got {type(eff).__name__}")
        return
    for k, v in eff.items():
        if k == "text":
            _text(where, v, problems)
            continue
        if k == "next":
            nxt = v if isinstance(v, dict) else {"event": v}
            if event_ids is not None and nxt.get("event") not in event_ids:
                problems.append(f"{where}: next -> unknown event '{nxt.get('event')}'")
            continue
        head, _, target = k.partition(".")
        if head not in EFFECT_HEADS:
            problems.append(f"{where}: unknown effect '{k}' (known: {', '.join(sorted(EFFECT_HEADS))})")
        elif head == "service" and target not in SERVICES:
            problems.append(f"{where}: '{k}' - service must be one of {SERVICES}")
        elif head in ("mood", "loyalty", "wealth_pc") and target not in TARGETS:
            problems.append(f"{where}: '{k}' - target must be one of all, ward, {', '.join(FACTIONS)}")
        elif head == "unrest" and target != "ward":
            problems.append(f"{where}: '{k}' - use unrest.ward")
        if not isinstance(v, (int, float)):
            problems.append(f"{where}: '{k}' should be a number, got {v!r}")


def _text(where, text, problems):
    try:
        names = {f for _, f, _, _ in string.Formatter().parse(str(text)) if f}
    except ValueError as e:
        problems.append(f"{where}: bad text formatting ({e})")
        return
    bad = names - PLACEHOLDERS
    if bad:
        problems.append(f"{where}: unknown placeholder(s) {sorted(bad)} - use {{ward}}, {{councilor}}, {{resident}}")


def _condition(where, expr, problems):
    if not expr:
        return
    try:
        compile(str(expr), where, "eval")
    except SyntaxError as e:
        problems.append(f"{where}: condition won't parse: {expr!r} ({e.msg})")
        return
    unknown = set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", re.sub(r"'[^']*'|\"[^\"]*\"", "", str(expr)))) - STAT_NAMES
    if unknown:
        problems.append(f"{where}: condition uses unknown name(s) {sorted(unknown)}")


def check_events(problems):
    data = _yaml(CONTENT / "events.yaml", problems) or []
    ids = [e.get("id") for e in data]
    for dup in {i for i in ids if ids.count(i) > 1}:
        problems.append(f"events.yaml: duplicate id '{dup}'")
    idset = set(ids)
    for e in data:
        w = f"events.yaml [{e.get('id', '?')}]"
        for field in ("id", "title"):
            if not e.get(field):
                problems.append(f"{w}: missing {field}")
        _text(w + " title", e.get("title", ""), problems)
        if e.get("scope", "city") not in ("city", "ward"):
            problems.append(f"{w}: scope must be city or ward")
        if e.get("ward_trait") and e["ward_trait"] not in WARD_TRAITS:
            problems.append(f"{w}: ward_trait must be one of {sorted(WARD_TRAITS)}")
        if not isinstance(e.get("days", 3), int) or e.get("days", 3) < 1:
            problems.append(f"{w}: days must be a whole number >= 1")
        _condition(w + " when", e.get("when"), problems)
        for part in ("on_start", "while", "on_help", "on_timeout"):
            _effects(f"{w} {part}", e.get(part), problems, idset)
        for word, kind in (e.get("commands") or {}).items():
            if kind not in ("help", "hinder"):
                problems.append(f"{w}: command {word} must be help or hinder, got {kind!r}")
            if not re.fullmatch(r"[A-Za-z]+", str(word)):
                problems.append(f"{w}: command {word!r} should be a single word, letters only")
        if e.get("commands") and not e.get("on_help"):
            problems.append(f"{w}: has commands but no on_help - helping would do nothing")
        oids = [o.get("id") for o in e.get("options") or []]
        if len(oids) != len(set(oids)):
            problems.append(f"{w}: duplicate option ids")
        for o in e.get("options") or []:
            ow = f"{w} option {o.get('id', '?')}"
            if not o.get("id") or not o.get("label"):
                problems.append(f"{ow}: options need an id and a label")
            if not isinstance(o.get("cost_pc", 0), (int, float)):
                problems.append(f"{ow}: cost_pc must be a number")
            _effects(ow, o.get("effects"), problems, idset)
            if o.get("text"):
                _text(ow, o["text"], problems)
            if o.get("next"):
                _effects(ow, {"next": o["next"]}, problems, idset)
    return idset, len(data)


def check_all(plan_path="seasons"):
    problems = []
    event_ids, n_events = check_events(problems)
    milestones = _yaml(CONTENT / "milestones.yaml", problems) or []
    m_ids = {m.get("id") for m in milestones}
    for m in milestones:
        if not m.get("id") or not isinstance(m.get("pop"), int) or not m.get("title"):
            problems.append(f"milestones.yaml [{m.get('id', '?')}]: needs id, pop (number) and title")
    projects = _yaml(CONTENT / "projects.yaml", problems) or []
    for p in projects:
        w = f"projects.yaml [{p.get('id', '?')}]"
        for field in ("id", "name", "cost_pc", "days"):
            if p.get(field) is None:
                problems.append(f"{w}: missing {field}")
        if p.get("unlock") and p["unlock"] not in m_ids:
            problems.append(f"{w}: unlock '{p['unlock']}' isn't a milestone id")
        _effects(w, p.get("effects"), problems)
    packs = sorted((ROOT / "packs").glob("*.yaml"))
    for f in packs:
        data = _yaml(f, problems) or {}
        for word, eff in (data.get("commands") or {}).items():
            eff = eff if isinstance(eff, str) else (eff or {}).get("effect")
            if eff not in COMMAND_EFFECTS:
                problems.append(f"packs/{f.name}: {word} -> unknown effect '{eff}' "
                                f"(known: {', '.join(sorted(COMMAND_EFFECTS))})")
        if data.get("event") and data["event"] not in event_ids:
            problems.append(f"packs/{f.name}: event '{data['event']}' doesn't exist")
    plans = []
    pp = ROOT / plan_path if plan_path else None
    if pp and pp.is_dir():
        plans = sorted(pp.glob("*.yaml"))
    elif pp and pp.exists():
        plans = [pp]
    days = load_cfg()["season_days"]
    for f in plans:
        data = _yaml(f, problems) or {}
        if data.get("storyteller", "fill") not in ("on", "fill", "off"):
            problems.append(f"{f.name}: storyteller must be on, fill or off")
        for i, b in enumerate(data.get("beats") or []):
            w = f"{f.name} beat {i + 1} (day {b.get('day', '?')})"
            if not isinstance(b.get("day"), int) or not 1 <= b["day"] <= days:
                problems.append(f"{w}: day must be 1-{days}")
            for beat in (b, b.get("else") or {}):
                if beat.get("event") and beat["event"] not in event_ids:
                    problems.append(f"{w}: unknown event '{beat['event']}'")
                pk = beat.get("pack")
                if isinstance(pk, str) and pk != "auto" and not (ROOT / pk).exists():
                    problems.append(f"{w}: pack file '{pk}' not found")
                if isinstance(pk, dict):
                    for word, eff in pk.items():
                        if eff not in COMMAND_EFFECTS:
                            problems.append(f"{w}: inline pack {word} -> unknown effect '{eff}'")
            _condition(w + " if", b.get("if"), problems)
    summary = [f"events: {n_events}", f"projects: {len(projects)}", f"milestones: {len(milestones)}",
               f"packs: {len(packs)}", f"season plans: {len(plans)}"]
    return problems, summary
