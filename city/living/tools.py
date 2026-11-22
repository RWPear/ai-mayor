"""What the king and the warlord can do between posts.

Each tool: who can use it, a one-line description (the minds read these), its
arguments, an optional unlock condition, and what it does. Tools start small
and open up through the world: the king gets spies when watchtowers go up, the
warlord gets the full horde when his camp is strong enough. Each unlock is
announced as a moment - a story beat of its own.

Every effect here is small and bounded. The big swings still come from events
the crowd fights over in the comments.
"""
import re

import numpy as np

from .. import effects, storyteller
from ..roles import JOB_NAMES
from . import warcamp

KING_PLACES = ["throne room", "war room", "treasury", "royal gardens", "city walls", "chapel"]

# what an invented decree's options can do: small, fixed packages (the king picks words and a flavour)
FLAVORS = {
    "walls":     {"service.defense": 0.07},
    "food":      {"service.food": 0.07},
    "roads":     {"service.roads": 0.07},
    "festival":  {"service.festivals": 0.07, "treasury_pc": -2},
    "tax_cut":   {"loyalty.guilds": 0.04, "mood": 0.02, "treasury_pc": -3},
    "tax_raise": {"treasury_pc": 4, "loyalty": -0.04},
    "army":      {"mood.army": 0.05, "loyalty.army": 0.02},
    "commoners": {"mood.commoners": 0.05, "loyalty.commoners": 0.02},
    "guilds":    {"mood.guilds": 0.05, "loyalty.guilds": 0.02},
    "vanity":    {"service.festivals": 0.03, "loyalty": -0.02, "treasury_pc": -2},
    "harsh":     {"service.defense": 0.04, "mood": -0.03},
    "nothing":   {},
}


def _hold_names(world):
    return [w["name"] for w in world.city.wards]


def _word(x, default):
    w = re.sub(r"[^A-Z]", "", str(x or "").upper())[:14]
    return w or default


# ---------------------------------------------------------------------------- king
def go(world, me, args):
    place = str(args.get("place") or "").strip().lower()
    holds = {n.lower(): n for n in _hold_names(world)}
    tavern = next((holds[h] for h in holds if h in place), None)
    if tavern:
        me["location"] = f"tavern in {tavern}"
        return world.moment("king", f"The king slipped into the tavern in {tavern} in a cheap disguise.", 1,
                            public=False, place=me["location"])
    place = next((p for p in KING_PLACES if p in place or place in p), None) if place else None
    if not place or place == me.get("location"):
        return None
    me["location"] = place
    return world.moment("king", f"The king went to the {place}.", 0, public=False, place=place)


def proclaim(world, me, args):
    text = str(args.get("text") or args.get("say") or "").strip()[:240]
    if not text:
        return None
    world.city.living["last_proclamation"] = {"day": world.city.day, "text": text}
    return world.moment("king", f'The king proclaimed: "{text}"', 1, public=True, place=me.get("location"))


def summon(world, me, args):
    c = world.city.citizens
    h = str(args.get("handle") or "").lstrip("@").strip().lower()
    i = c.index.get(h)
    if i is None:   # summon a lord or a loud commenter instead of failing
        lords = [w["councilor"] for w in world.city.wards if w.get("councilor") is not None]
        i = world.city.rng.choice(lords) if lords else None
    if i is None or c.status[i] != 0:
        return None
    why = str(args.get("why") or "").strip()[:160]
    reply = world.voice_subject(int(i), f"The king summoned you to the {me.get('location', 'throne room')}"
                                        + (f" because: {why}" if why else "") + ". What do you tell him?")
    good = float(c.mood[i]) > 0.5
    c.loyalty[i] = float(np.clip(c.loyalty[i] + (0.06 if good else -0.03), 0, 1))
    c.log(int(i), world.city.day, "was summoned before the king")
    return world.moment("king", f"The king summoned @{c.handles[i]} ({JOB_NAMES[int(c.job[i])]} of "
                                f"{world.city.wards[int(c.ward[i])]['name']})"
                                + (f" ({why.rstrip('.')})" if why else "") + f'. They said: "{reply}"',
                        2, public=True, place=me.get("location"), handles=[c.handles[i]])


def decree(world, me, args):
    """The king writes a brand-new decree vote for tomorrow's post, in his own words."""
    city = world.city
    if any(a["id"].startswith("decree_") for a in city.events) or \
            city.living.get("last_decree_day", -9) >= city.day:
        return None   # one invented decree at a time, at most one a day
    q = str(args.get("question") or "").strip()[:140]
    a_w, b_w = _word(args.get("a_word"), "YES"), _word(args.get("b_word"), "NO")
    if not q or a_w == b_w:
        return None
    fa = args.get("a_flavor") if args.get("a_flavor") in FLAVORS else "nothing"
    fb = args.get("b_flavor") if args.get("b_flavor") in FLAVORS else "nothing"
    eid = f"decree_{city.day}_{len(city.living.get('custom_events', {}))}"
    ev = {"id": eid, "title": q, "scope": "city", "planned_only": True, "days": 2,
          "choices": {a_w: {"text": str(args.get("a_text") or f"{a_w} it is.")[:160], **FLAVORS[fa]},
                      b_w: {"text": str(args.get("b_text") or f"{b_w} it is.")[:160], **FLAVORS[fb]}},
          "options": [{"id": f"back_{a_w.lower()}", "label": f"Back {a_w}", "side": a_w, "cost_pc": 0,
                       "text": f"The king backs {a_w}."},
                      {"id": f"back_{b_w.lower()}", "label": f"Back {b_w}", "side": b_w, "cost_pc": 0,
                       "text": f"The king backs {b_w}."}],
          "invented_by": "king"}
    city.living.setdefault("custom_events", {})[eid] = ev
    storyteller.register(ev)
    side = _word(args.get("back"), "")
    a = storyteller.start(city, eid, source="king", extra={"started": city.day + 1})
    if a and side in (a_w, b_w):
        a["side"] = side
    city.living["last_decree_day"] = city.day
    world.notify(f"The king invented a decree: {q} [{a_w} / {b_w}]")
    return world.moment("king", f"The king issued a new decree: {q} {a_w} or {b_w}?"
                        + (f" He wants {side}." if side in (a_w, b_w) else ""), 2, public=True)


def spend(world, me, args):
    city = world.city
    what = str(args.get("what") or "").lower()
    pop = max(1, city.population())
    if what.startswith("feast"):
        wi = world.ward_index(what.replace("feast", "")) if what.replace("feast", "").strip() else None
        cost = 1.5 * pop
        if city.treasury < cost:
            return None
        city.treasury -= cost
        effects.apply(city, {"mood.hold" if wi is not None else "mood": 0.05}, wi)
        where = city.wards[wi]["name"] if wi is not None else "the capital"
        return world.moment("king", f"The king threw a feast in {where} ({cost:,.0f} gold).", 1, public=True)
    from ..sim import available_projects
    proj = next((p for p in available_projects(city) if p["id"] == what or p["name"].lower() == what), None)
    if not proj or city.treasury < proj["cost_pc"] * pop:
        return None
    from ..mayor import apply_decision
    lines, _ = apply_decision(city, {"project": proj["id"]})
    return world.moment("king", lines[0] if lines else f"The king ordered {proj['name']}.", 1, public=True) \
        if lines else None


def rest(world, me, args):
    me["energy"] = min(1.0, me.get("energy", 1) + 0.3)
    return None


def spy(world, me, args):
    """Unlocked by watchtowers: learn what the warlord is up to (or how a hold really feels)."""
    target = str(args.get("target") or "north").lower()
    city = world.city
    if "north" in target or "camp" in target or "warlord" in target:
        c = warcamp.camp(city)
        seen = {"warriors": int(c["warriors"] * city.rng.uniform(0.8, 1.2)), "food": round(c["food"]),
                "morale": round(c["morale"], 1), "day": city.day}
        me.setdefault("intel", {})["north"] = seen
        return world.moment("king", f"The king's spies counted about {seen['warriors']} warriors in "
                                    f"{c['name']}.", 1, public=False)
    wi = world.ward_index(target)
    if wi is None:
        return None
    w = city.ward_stats()[wi]
    me.setdefault("intel", {})[w["name"]] = {"mood": round(w["mood"], 2), "unrest": round(w["unrest"] or 0, 2)}
    return world.moment("king", f"The king's spies reported on {w['name']}: the mood is "
                                f"{'sour' if w['mood'] < 0.45 else 'fine'}.", 0, public=False)


def garrison(world, me, args):
    """Unlocked after the first raid: station soldiers in a hold for a week. Raids there are much harder."""
    city = world.city
    wi = world.ward_index(args.get("hold"))
    cost = 2 * max(1, city.population())
    if wi is None or city.treasury < cost or city.wards[wi].get("garrison_until", -1) >= city.day:
        return None
    city.treasury -= cost
    city.wards[wi]["garrison_until"] = city.day + 7
    effects.apply(city, {"mood.hold": 0.03}, wi)
    return world.moment("king", f"The king stationed soldiers in {city.wards[wi]['name']} for a week.", 1, public=True)


# ---------------------------------------------------------------------------- warlord
def scout(world, me, args):
    city = world.city
    wi = world.ward_index(args.get("hold"))
    if wi is None:
        wi = city.rng.randrange(len(city.wards))
    w = city.wards[wi]
    st = city.ward_stats()[wi]
    intel = {"pop": st["pop"], "mood": round(st["mood"] or 0.5, 2), "garrison": w.get("garrison_until", -1) >= city.day,
             "defense": round(city.quality["defense"], 2), "day": city.day,
             "raid_strength_with_all_warriors": round(warcamp.strength(city, warcamp.camp(city)["warriors"], wi), 2)}
    warcamp.camp(city)["intel"][w["name"]] = intel
    return world.moment("warlord", f"{me['name'].split()[0]}'s scouts crept around {w['name']}. "
                                   + ("Soldiers are stationed there." if intel["garrison"] else "No garrison."),
                        0, public=False)


def raid(world, me, args):
    city = world.city
    c = warcamp.camp(city)
    if c.get("active_raid") or any(a["id"] in ("warlord_raid", "warlord_horde") for a in city.events):
        return None
    wi = world.ward_index(args.get("hold"))
    if wi is None:
        return None
    try:
        sent = int(float(args.get("warriors") or c["warriors"] * 0.6))
    except ValueError:
        sent = int(c["warriors"] * 0.6)
    sent = int(np.clip(sent, 5, c["warriors"]))
    a = storyteller.start(city, "warlord_raid", wi, source="warlord",
                          strength=warcamp.strength(city, sent, wi), extra={"warriors_sent": sent, "started": city.day + 1})
    if not a:
        return None
    c["active_raid"] = a["uid"]
    world.notify(f"{me['name']} is raiding {city.wards[wi]['name']} with {sent} warriors")
    return world.moment("warlord", f"{me['name']} sent {sent} raiders screaming down on {city.wards[wi]['name']}!",
                        3, public=True)


def march(world, me, args):
    """Unlocked when the camp is strong: the whole horde marches on the capital."""
    city = world.city
    c = warcamp.camp(city)
    if c.get("active_raid") or any(a["id"] in ("warlord_raid", "warlord_horde") for a in city.events):
        return None
    a = storyteller.start(city, "warlord_horde", None, source="warlord",
                          strength=warcamp.strength(city, c["warriors"]),
                          extra={"warriors_sent": c["warriors"], "started": city.day + 1})
    if not a:
        return None
    c["active_raid"] = a["uid"]
    world.notify(f"{me['name']} is marching the whole horde ({c['warriors']}) on Emberfall")
    return world.moment("warlord", f"{me['name']} blew the war horn. {int(c['warriors'])} warriors are marching "
                                   f"on Emberfall.", 3, public=True)


def recruit(world, me, args):
    c = warcamp.camp(world.city)
    cost = 15
    room = warcamp.cap(c, world.city.day) - c["warriors"]
    if c["food"] < cost or room <= 0:
        return None
    c["food"] -= cost
    new = min(room, int(2 + 6 * c["morale"] * world.city.rng.uniform(0.6, 1.3)))
    c["warriors"] += new
    return world.moment("warlord", f"{new} wild-eyed recruits joined {c['name']}.", 0, public=False)


def hunt(world, me, args):
    c = warcamp.camp(world.city)
    got = int(15 + c["warriors"] * 0.25 * world.city.rng.uniform(0.5, 1.4))
    c["food"] += got
    return world.moment("warlord", f"The hunters of {c['name']} dragged back {got} sacks of meat.", 0, public=False)


def taunt(world, me, args):
    text = str(args.get("text") or "").strip()[:240]
    if not text:
        return None
    world.agent("king").setdefault("letters", []).append({"day": world.city.day, "from": me["name"], "text": text})
    return world.moment("warlord", f'A letter from {me["name"]} arrived at the castle: "{text}"', 2, public=True)


def feast(world, me, args):
    c = warcamp.camp(world.city)
    if c["food"] < 20:
        return None
    c["food"] -= 20
    c["morale"] = min(1.0, c["morale"] + 0.08)
    return world.moment("warlord", f"{c['name']} feasted and sang until dawn.", 0, public=False)


def sabotage(world, me, args):
    """Unlocked after two successful raids: a night-time fire in a hold's granary. Nobody knows who did it."""
    city = world.city
    wi = world.ward_index(args.get("hold"))
    if wi is None:
        return None
    effects.apply(city, {"service.food": -0.05, "mood.hold": -0.05}, wi)
    world.moment("world", f"A granary in {city.wards[wi]['name']} burned down in the night. Nobody saw who did it.",
                 2, public=True)
    return world.moment("warlord", f"{me['name']}'s men set the fire in {city.wards[wi]['name']}.", 1, public=False)


# ---------------------------------------------------------------------------- the tool table
ARG = {"place": "where to go: one of the castle rooms, or 'tavern in <hold>' to go in disguise",
       "text": "the words, in your voice", "handle": "a subject's @handle", "why": "why (a few words)",
       "question": "the decree question", "a_word": "one-word choice A", "a_text": "what happens if A wins",
       "a_flavor": "what A does: " + ", ".join(FLAVORS), "b_word": "one-word choice B",
       "b_text": "what happens if B wins", "b_flavor": "what B does", "back": "the word you want to win (optional)",
       "what": "a project id from the brief, or 'feast <hold>'", "target": "'north' (the war camp) or a hold",
       "hold": "a hold's name", "warriors": "how many warriors to send"}

TOOLS = {
    "king": {
        "go":        (go, "walk somewhere in the castle, or visit a hold's tavern in disguise to hear what people say", ["place"], None),
        "proclaim":  (proclaim, "make a public proclamation to the kingdom", ["text"], None),
        "summon":    (summon, "summon a subject (a real person) to talk to them", ["handle", "why"], None),
        "decree":    (decree, "invent a new decree for the people to vote on tomorrow (one a day)",
                      ["question", "a_word", "a_text", "a_flavor", "b_word", "b_text", "b_flavor", "back"], None),
        "spend":     (spend, "pay for a building project or a feast", ["what"], None),
        "rest":      (rest, "rest, sulk, or sleep", [], None),
        "spy":       (spy, "send spies north to the war camp, or into a hold", ["target"], "built('watchtower')"),
        "garrison":  (garrison, "station soldiers in a hold for a week (raids there get much harder)", ["hold"],
                      "happened('warlord_raid')"),
    },
    "warlord": {
        "scout":     (scout, "send scouts to study a hold's defenses", ["hold"], None),
        "raid":      (raid, "raid a hold (only one raid at a time)", ["hold", "warriors"], "day >= 3"),
        "recruit":   (recruit, "recruit more warriors (costs food)", [], None),
        "hunt":      (hunt, "hunt for food", [], None),
        "taunt":     (taunt, "send the king an insulting letter (everyone will hear about it)", ["text"], None),
        "feast":     (feast, "feast with your warriors (morale)", [], None),
        "march":     (march, "march the WHOLE horde on the capital", [],
                      "day >= 10 and camp_warriors >= 120 and camp_morale >= 0.55 and camp_raids_won >= 1"),
        "sabotage":  (sabotage, "secretly burn a hold's granary at night", ["hold"], "camp_raids_won >= 2"),
    },
}


def unlocked(world, who):
    """The tools this mind can use right now."""
    out = {}
    for name, (fn, desc, args, cond) in TOOLS[who].items():
        if cond is None or world.condition(cond):
            out[name] = (fn, desc, args)
    return out
