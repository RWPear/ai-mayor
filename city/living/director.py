"""The director: events nobody wrote.

Twice a day the director looks at what's actually going on in Emberfall - what the king has been doing,
how his projects turned out, what the crowd did, the town, the weather, the war - and decides whether
something should happen, and what. It writes the event itself: the title, the comment words, what
happens if people help or don't, what the king could do about it.

The words are free. The mechanics are not: every consequence is picked from a fixed set (food lost, gold
gained, unrest...) with a size, and the size is capped by how far into the season we are:

  tier 1 (days 1-7):   everyday trouble. A cart in a ditch, a stolen pig, a leaky roof.
  tier 2 (days 8-18):  serious. A fire, a failed harvest, a scandal, a disease in the herds.
  tier 3 (days 19+):   disasters. "The king's new dam burst and drowned half the livestock - the town is
                       starving." Nobody real dies, but animals, buildings, harvests and reputations can.

It prefers consequences: things that grow out of what the king and the people actually did. Every event
it invents is validated, saved with the kingdom, and sent as a notification. Without a model (or budget)
the old hand-written events in content/events.yaml keep the game going.
"""
import re

from .. import storyteller

CONSEQUENCES = {
    "nothing": {},
    "food_loss": {"service.food": -0.04}, "food_gain": {"service.food": 0.04},
    "defense_loss": {"service.defense": -0.04}, "defense_gain": {"service.defense": 0.04},
    "roads_loss": {"service.roads": -0.04}, "roads_gain": {"service.roads": 0.04},
    "festivals_loss": {"service.festivals": -0.04}, "festivals_gain": {"service.festivals": 0.04},
    "mood_loss": {"mood": -0.03}, "mood_gain": {"mood": 0.03},
    "loyalty_loss": {"loyalty": -0.03}, "loyalty_gain": {"loyalty": 0.03},
    "gold_loss": {"treasury_pc": -2}, "gold_gain": {"treasury_pc": 2},
    "people_poorer": {"wealth_pc": -15}, "people_richer": {"wealth_pc": 15},
    "economy_loss": {"economy": -0.03}, "economy_gain": {"economy": 0.03},
    "unrest": {"unrest.hold": 0.08},
}
SIZE = {1: 1.0, 2: 2.0, 3: 3.5}
NEED = {"easy": 0.35, "normal": 0.5, "hard": 0.65}
RESERVED = {"STATUS", "JOIN", "BECOME", "MOVE", "KNEEL", "REVOLT"}

_out = {"type": "object", "properties": {"text": {"type": "string"},
                                         "consequence": {"type": "string", "enum": list(CONSEQUENCES)},
                                         "size": {"type": "integer"}}, "required": ["text", "consequence", "size"]}
SCHEMA = {"type": "object", "properties": {
    "happen": {"type": "boolean"},
    "title": {"type": "string"},
    "kind": {"type": "string", "enum": ["crisis", "vote"]},
    "where": {"type": "string"},
    "days": {"type": "integer"},
    "help_words": {"type": "array", "items": {"type": "string"}},
    "hinder_words": {"type": "array", "items": {"type": "string"}},
    "difficulty": {"type": "string", "enum": list(NEED)},
    "at_start": _out, "if_helped": _out, "if_not": _out,
    "choices": {"type": "array", "items": {"type": "object", "properties": {
        "word": {"type": "string"}, "text": {"type": "string"},
        "consequence": {"type": "string", "enum": list(CONSEQUENCES)}, "size": {"type": "integer"}},
        "required": ["word", "text", "consequence", "size"]}},
    "king_options": {"type": "array", "items": {"type": "object", "properties": {
        "label": {"type": "string"}, "text": {"type": "string"}, "cost": {"type": "string", "enum": ["none", "small", "large"]},
        "consequence": {"type": "string", "enum": list(CONSEQUENCES)}, "size": {"type": "integer"},
        "helps": {"type": "boolean"}}, "required": ["label", "text", "cost", "consequence", "size", "helps"]}}},
    "required": ["happen", "title", "kind", "where", "days", "help_words", "hinder_words", "difficulty", "at_start",
                 "if_helped", "if_not", "choices", "king_options"]}

SYSTEM = """You are the unseen storyteller of the kingdom of Emberfall, a living world followed by real people online.
Look at what has actually been happening and decide whether something should happen next, and what. Best of all:
CONSEQUENCES - things that grow out of what the king, the warlord and the people actually did (a project that
failed, a decree, a feud, houses outside the walls, a hungry winter coming). Sometimes something from outside.
Rules:
- tier {tier} of 3. tier 1 = everyday trouble, small stakes. tier 2 = serious. tier 3 = disasters. Match the tier.
- Nobody real dies (subjects are real people). Animals, buildings, harvests, gold and reputations can be lost.
- No sex, no real-world politics or real people other than the subjects' @handles you're shown.
- kind "crisis": the people help or hinder with 1-2 help_words and 0-1 hinder_words (single words, CAPITALS).
  kind "vote": two choices, each a single CAPITAL word with its own outcome.
- where: "kingdom" or one of the holds: {holds}.
- consequences come from the fixed list; size 1-{tier}.
- king_options: 0-2 things the king could do about it (cost none/small/large; helps=true if it pushes toward
  solving it).
- title: a specific headline that says what happened, to whom, where - like "Rats chewed through the granary in
  Millbrook overnight" or "The king's new archery targets collapsed on a soldier during practice". Never a vague
  title like "A Test of Strength" or "The King's First Steps".
- Don't repeat recent events: {recent}
- If nothing should happen right now (things are busy enough, or it would feel random), set happen=false."""


def tier(city):
    sd = (city.day % city.cfg["season_days"]) + 1
    return 1 if sd <= 7 else (2 if sd <= 18 else 3)


def _word(w):
    w = re.sub(r"[^A-Z]", "", str(w).upper())[:12]
    return w if len(w) >= 2 and w not in RESERVED else ""


def _effect(o, cap):
    if not isinstance(o, dict):
        return {}
    eff = CONSEQUENCES.get(o.get("consequence"), {})
    k = SIZE[max(1, min(cap, int(o.get("size") or 1)))]
    return {key: v * k for key, v in eff.items()}


def build(city, d, tier_):
    """Turns the director's answer into a real event dict. Returns None if it doesn't hold up."""
    if not d.get("happen") or not str(d.get("title") or "").strip():
        return None
    eid = f"story_{city.day}_{len(city.living.get('custom_events', {}))}"
    holds = {w["name"].lower(): w["name"] for w in city.wards}
    where = str(d.get("where") or "kingdom").strip().lower()
    hold = next((holds[h] for h in holds if h in where), None)
    ev = {"id": eid, "title": str(d["title"])[:110], "scope": "hold" if hold else "city", "planned_only": True,
          "days": max(1, min(3, int(d.get("days") or 2))), "invented_by": "director", "tier": tier_,
          "hold_name": hold}
    start = _effect(d.get("at_start"), tier_)
    if start:
        ev["on_start"] = start
    if d.get("kind") == "vote":
        choices = {}
        for ch in (d.get("choices") or [])[:2]:
            w = _word(ch.get("word"))
            if w and w not in choices:
                choices[w] = {"text": str(ch.get("text") or f"{w} it is.")[:200], **_effect(ch, tier_)}
        if len(choices) < 2:
            return None
        ev["choices"] = choices
        ev["days"] = max(2, ev["days"])
        ev["options"] = [{"id": f"back_{w.lower()}", "label": f"Back {w}", "side": w, "cost_pc": 0,
                          "text": f"The king backs {w}."} for w in choices]
    else:
        cmds = {}
        for w in (d.get("help_words") or [])[:2]:
            if _word(w):
                cmds[_word(w)] = "help"
        for w in (d.get("hinder_words") or [])[:1]:
            if _word(w) and _word(w) not in cmds:
                cmds[_word(w)] = "hinder"
        if "help" not in cmds.values():
            return None
        ev["commands"] = cmds
        ev["help_needed"] = NEED.get(d.get("difficulty"), 0.5)
        ev["on_help"] = {"text": str((d.get("if_helped") or {}).get("text") or "The kingdom pulled through.")[:220],
                         **_effect(d.get("if_helped"), tier_)}
        ev["on_timeout"] = {"text": str((d.get("if_not") or {}).get("text") or "It passed, badly.")[:220],
                            **_effect(d.get("if_not"), tier_)}
        opts = []
        for k, o in enumerate((d.get("king_options") or [])[:2]):
            eff = _effect(o, tier_)
            if o.get("helps"):
                eff["progress"] = 0.3
            opts.append({"id": f"opt{k + 1}", "label": str(o.get("label") or "Do something")[:80],
                         "text": str(o.get("text") or "The king acted.")[:200], "effects": eff,
                         "cost_pc": {"none": 0, "small": 2, "large": 6}.get(o.get("cost"), 0)})
        ev["options"] = opts
    if not hold:   # hold-only effects make no sense kingdom-wide
        for part in ("on_start", "on_help", "on_timeout"):
            if part in ev:
                ev[part] = {k: v for k, v in ev[part].items() if not k.endswith(".hold")}
    return ev


def happenings(world):
    """What the director gets to see: recent public moments, the king's projects, the town, the war."""
    city = world.city
    lines = [m["text"] for m in world.moments_since(world.clock - 30 * 60)
             if m["public"] and m["drama"] >= 1][-14:]
    king = world.agent("king")
    outs = king.get("life", {}).get("outcomes", [])[-3:]
    from . import town as T
    from .warcamp import camp
    c = camp(city)
    if world.frontier:
        from . import frontier as F
        f = F.summary(world)
        return "\n".join([
            f"Day {city.day + 1}, {world.now_str()}, {city.living.get('weather', '')}.",
            "This is a FRONTIER: Aldric (who wants to be king, not crowned "
            + ("- now crowned" if f["crowned"] else "yet") + ") is building a settlement from nothing in a field "
            "by a river, woods and a rocky hill. Events should fit that: wolves, floods, a sick goat, a fallen tree, "
            "strangers on the road, a fight over a well - not castles and holds.",
            f"Settlers: {f['settled']} ({f['tents']} in tents, {f['free']} free beds), {f['on_road']} on the road "
            f"(arriving day {f['next_arrival']}). Stores: {f['stock']}. Built: {', '.join(f['built']) or 'nothing'}. "
            f"Building: {', '.join(f['projects']) or 'nothing'}.",
            "Who lives here: " + _who_lives_here(city),
            "Happening right now: " + ("; ".join(a["title"] for a in city.events) or "nothing"),
            "Recently:\n- " + "\n- ".join(lines or ["a quiet stretch"])])
    return "\n".join([
        f"Day {city.day + 1} of the season, {world.now_str()}, {city.living.get('weather', '')}.",
        f"Emberfall: {city.population()} subjects, {T.summary(world)}, loyalty {city.approval():.0%}, treasury "
        f"{city.treasury:,.0f} gold, food {city.quality['food']:.2f}, defense {city.quality['defense']:.2f}.",
        "Holds: " + ", ".join(w["name"] for w in city.wards),
        "The king's projects: " + ("; ".join(f"{o['name']} ({o['result']})" for o in outs) or "none yet")
        + ("; building now: " + ", ".join(w["name"] for w in city.living["town"]["works"]) if city.living["town"]["works"] else ""),
        "Who the king is becoming: " + (king.get("self", {}).get("becoming") or "nobody knows yet"),
        ("The war camp in the north: " + (f"{c['warriors']} warriors" if c.get("arrived") else "nobody there yet")),
        "Happening right now: " + ("; ".join(a["title"] for a in city.events) or "nothing"),
        "Who lives here: " + _who_lives_here(city),
        "Recently:\n- " + "\n- ".join(lines or ["a quiet stretch"])])


def _who_lives_here(city):
    """The roles people chose: lots of thieves means a crime wave, lots of beggars means hard times."""
    c = city.citizens
    from collections import Counter
    own = Counter(lab for i, lab in c.roles.items() if c.status[i] == 0)
    known = int(((c.counts["steal"] >= 3) & c.active()).sum())
    rough = int((c.active() & (c.walled == -1)).sum())
    from .. import trades
    bits = [f"{n} {trades.plural(lab) if n > 1 else lab}" for lab, n in own.most_common(6)]
    if known:
        bits.append(f"{known} known thie{'ves' if known > 1 else 'f'}")
    if rough:
        bits.append(f"{rough} sleeping rough")
    return (", ".join(bits) + " - and the rest farm, fish, trade and soldier") if bits else "ordinary farmers, crafters and soldiers"


def consider(world, llm):
    """Maybe invents an event. Returns the started event or None."""
    city = world.city
    if not llm or not world.can_think():
        return None
    if world.frontier:
        from . import frontier as F
        if F.land(world)["stage"] == "alone":
            return None            # nobody to help or hinder yet: the frontier's own rough nights do the job
    non_war = [a for a in city.events if not a["id"].startswith("warlord_")]
    if len(non_war) >= city.cfg.get("max_active_events", 2):
        return None
    t = tier(city)
    world.spend_calls(1)
    try:
        recent = [e["title"] for e in city.living.get("custom_events", {}).values()
                  if e.get("invented_by") == "director"][-6:]
        d = llm.json(SYSTEM.format(tier=t, holds=", ".join(w["name"] for w in city.wards),
                                   recent="; ".join(recent) or "none yet"), happenings(world),
                     SCHEMA, max_tokens=700, temperature=0.95)
    except Exception:
        world.stats["director_fallbacks"] = world.stats.get("director_fallbacks", 0) + 1
        return None
    ev = build(city, d, t)
    recent = {e["title"].lower() for e in city.living.get("custom_events", {}).values()}
    if ev and ev["title"].lower() in recent:
        ev = None
    if not ev:
        world.stats["director_passed"] = world.stats.get("director_passed", 0) + 1
        return None
    city.living.setdefault("custom_events", {})[ev["id"]] = ev
    storyteller.register(ev)
    hold = next((i for i, w in enumerate(city.wards) if w["name"] == ev.get("hold_name")), None)
    a = storyteller.start(city, ev["id"], hold, source="director", extra={"started": city.day + 1})
    if a:
        world.notify(f"New event (tier {t}): {a['title']}")
        first = str((d.get("at_start") or {}).get("text") or "").strip()
        world.moment("world", a["title"] + (f" {first}" if first and first not in a["title"] else ""),
                     2 + (t == 3), public=True, hold=ev.get("hold_name") or "")
        world.stats["director_events"] = world.stats.get("director_events", 0) + 1
    return a
