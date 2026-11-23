"""What the king and the warlord can do.

Each tool: a one-line description (the minds read these), its arguments, an
optional unlock condition, and what it does. The warlord's tools open up as his
camp grows; the king's open up as he builds the rooms of his castle (a war room,
a spymaster's tower, a great hall, a dungeon) - and each unlock is a story beat.

The king's everyday life is tools too: walking the town, talking to people,
pastimes (whatever he likes), his own projects (whatever he thinks of), pitching
in on them, holding court, eating, sleeping. Nothing in here tells him what to
want - the tools are verbs, the ideas are his.

Every effect here is small and bounded. The big swings still come from events
the crowd fights over in the comments.
"""
import re

import numpy as np

from .. import effects, storyteller
from ..roles import JOB_NAMES
from . import life, warcamp
from . import town as T

# what an invented decree's (or project's) options can do: small, fixed packages
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
BUILD_FLAVORS = [f for f in FLAVORS if f not in ("tax_cut", "tax_raise")]


def _hold_names(world):
    return [w["name"] for w in world.city.wards]


def _word(x, default):
    w = re.sub(r"[^A-Z]", "", str(x or "").upper())[:14]
    return w or default


def _town(world):
    return world.city.living["town"]


# ---------------------------------------------------------------------------- the king's life
def walk(world, me, args):
    pid = T.match_place(args.get("place"))
    if not pid or pid == me.get("location"):
        return None
    me["location"] = pid
    me["next_act"] = world.clock + T.PLACES[pid]["walk"]        # walking takes a while
    name = T.place_of(pid, _town(world))
    disguise = pid == "tavern"
    return world.moment("king", f"The king {'slipped into' if disguise else 'walked to'} {name}"
                        + (" in a cheap disguise." if disguise else "."), 0, public=False, place=pid)


def talk(world, me, args):
    """Talk to a member of the court (steward, captain, jester) or to any subject (@handle)."""
    who = str(args.get("person") or "").strip()
    said = str(args.get("text") or "").strip()[:200]
    court = life.court()
    key = next((k for k, v in court.items() if k in who.lower() or v["name"].lower().split()[-1] in who.lower()), None)
    life.satisfy(me, "company", 0.35)
    if key:
        reply = world.voice_npc(key, f'The king says to you: "{said}"' if said else "The king wants to chat.")
        return world.moment("king", f'The king to {court[key]["name"]}: "{said or "Well?"}" - "{reply}"',
                            2 if key == "jester" else 1, public=True, place=me.get("location"))
    c = world.city.citizens
    h = who.lstrip("@").lower()
    i = c.index.get(h)
    if i is None or c.status[i] != 0:
        return None
    reply = world.voice_subject(int(i), f'The king, at {T.PLACES[me["location"]]["name"]}, says to you: "{said}"'
                                if said else "The king stops to talk to you.")
    c.loyalty[i] = float(np.clip(c.loyalty[i] + 0.04, 0, 1))
    c.log(int(i), world.city.day + 1, "talked with the king himself")
    return world.moment("king", f'The king stopped to talk with @{c.handles[i]}: "{said or "Hello there."}" - '
                                f'"{reply}"', 2, public=True, place=me.get("location"), handles=[c.handles[i]])


def pastime(world, me, args):
    """Anything he feels like doing for its own sake. Whatever he keeps doing becomes a passion."""
    activity = str(args.get("activity") or "").strip()
    if not activity:
        return None
    title = str(args.get("title") or "").strip() or "something"
    desc = str(args.get("description") or "").strip().rstrip(".")
    item, level, practice = life.pastime(world, me, activity, title, desc)
    first = practice == 1
    better = practice % 3 == 0
    text = (f"The king tried {item['kind']} for the first time" if first else f"The king spent time on {item['kind']}")
    if item["title"] != "something":
        text += f' and made "{item["title"]}"'
    text += (f": {desc[:140]}" if desc else "") + "."
    if better:
        text += f" He's getting better (skill {level}/10)."
    return world.moment("king", text, 2 if (first or better) else 1, public=True, place=me.get("location"))


def start_work(world, me, args):
    """His own idea, where he's standing. Nothing is suggested - and it might not work."""
    t = _town(world)
    pid = me.get("location")
    name = str(args.get("name") or "").strip()[:90]
    # a project at a ruined room rebuilds it if that's what he means (or if he doesn't say)
    ruin = pid in T.ROOMS and not t["rooms"].get(pid) and (
        not name or re.search(r"rebuil|restor|repair|fix|renovat|room|tower|hall|dungeon|roof|walls", name.lower()))
    if ruin and not name:
        name = f"rebuilding {T.ROOMS[pid]['name']}"
    if not name:
        return None
    if any(w["place"] == pid for w in t["works"]):
        return None                                   # one project per place at a time
    size = args.get("size") if args.get("size") in T.SIZES else "small"
    flavor = args.get("purpose") if args.get("purpose") in BUILD_FLAVORS else "nothing"
    wid = f"w{len(t['done']) + len(t['works']) + len(t.get('failed', [])) + 1}_{pid}"
    spec = {"id": wid, "name": name, "size": size, "flavor": flavor, "room": ruin,
            "feature": "room" if ruin else re.sub(r"[^a-z]+", "_", name.lower())[:30]}
    work, cost = life.start_work(world, spec, pid)
    if not work:
        return world.moment("king", f"The king wanted {name}, but the treasury can't pay {cost:,.0f} gold.",
                            1, public=False, place=pid)
    world.notify(f"The king started his own project at {T.PLACES[pid]['name']}: {name}")
    return world.moment("king", f"The king ordered {name} ({cost:,.0f} gold, about {work['days']} days of work).",
                        2, public=True, place=pid)


def work_on(world, me, args):
    t = _town(world)
    here = [w for w in t["works"] if w["place"] == me.get("location")]
    if not here:
        return None
    w = here[0]
    finished = life.advance_works(world, 0, boost=w["id"], by=0.12)
    world.announce_works(finished)
    life.satisfy(me, "fun", 0.2)
    life.satisfy(me, "energy", -0.15)
    if finished:
        return None
    return world.moment("king", f"The king rolled up his sleeves and worked on {w['name']} himself "
                                f"({min(100, w['progress'] * 100):.0f}% done).", 1, public=True, place=w["place"])


def hold_court(world, me, args):
    """At the throne room: rule on a case from the docket (petitioners, criminals, visitors)."""
    from .intents import set_condition
    if me.get("location") != "throne_room":
        return None
    docket = world.city.living.get("docket", [])
    case = next((k for k in docket if k["id"] == args.get("case")), docket[0] if docket else None)
    if not case:
        return None
    docket.remove(case)
    verdict = str(args.get("verdict") or "deny").lower()
    words = str(args.get("words") or "").strip()[:200]
    c, city = world.city.citizens, world.city
    i = c.index.get(case["who"])
    jail = "the dungeon" if _town(world)["rooms"].get("dungeon") else "the stocks"
    effect = ""
    if i is not None:
        if verdict in ("grant", "reward", "pardon"):
            c.loyalty[i] = float(np.clip(c.loyalty[i] + 0.1, 0, 1))
            c.mood[i] = float(np.clip(c.mood[i] + 0.08, 0, 1))
            if verdict == "reward":
                gold = 20 + 30 * city.rng.random()
                city.treasury -= gold
                c.wealth[i] += gold
                effect = f" and {gold:.0f} gold"
            if verdict == "pardon":
                city.living.get("conditions", {}).pop(case["who"], None)
        elif verdict in ("jail", "fine", "deny"):
            c.loyalty[i] = float(np.clip(c.loyalty[i] - 0.06, 0, 1))
            if verdict == "jail":
                set_condition(city, case["who"], "jailed", 2 if jail == "the dungeon" else 1, "sentenced by the king")
                effect = f" - {2 if jail == 'the dungeon' else 1} days in {jail}"
            if verdict == "fine":
                fine = min(float(c.wealth[i]) * 0.2, 80.0)
                c.wealth[i] -= fine
                city.treasury += fine
                effect = f" - fined {fine:.0f} gold"
        c.log(i, city.day + 1, f"was judged by the king: {verdict}")
    return world.moment("king", f"At court: {case['text']}. The king's verdict: {verdict.upper()}{effect}."
                        + (f' "{words}"' if words else ""), 2, public=True, place="throne_room",
                        handles=[case["who"]])


def eat(world, me, args):
    where = me.get("location")
    good = where in ("kitchens", "great_hall", "tavern")
    life.satisfy(me, "hunger", 0.7 if good else 0.4)
    if where == "tavern":
        life.satisfy(me, "company", 0.2)
    return None if not good else world.moment("king", f"The king ate at {T.PLACES[where]['name']}.", 0, public=False)


def rest(world, me, args):
    life.satisfy(me, "energy", 0.35 if me.get("location") == "bedchamber" else 0.15)
    return None


def royal_feast(world, me, args):
    """Unlocked by the great hall: a feast for the capital (or a hold)."""
    city = world.city
    hold = args.get("hold")
    wi = world.ward_index(hold) if hold else None
    cost = 1.5 * max(1, city.population())
    if city.treasury < cost:
        return None
    city.treasury -= cost
    effects.apply(city, {"mood.hold" if wi is not None else "mood": 0.05, "loyalty": 0.01}, wi)
    life.satisfy(me, "company", 0.5)
    life.satisfy(me, "hunger", 0.8)
    where = city.wards[wi]["name"] if wi is not None else "the great hall"
    return world.moment("king", f"The king threw a feast in {where} ({cost:,.0f} gold).", 2, public=True)


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
    reply = world.voice_subject(int(i), f"The king summoned you to {T.PLACES.get(me.get('location'), T.PLACES['throne_room'])['name']}"
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
    from ..sim import available_projects
    proj = next((p for p in available_projects(city) if p["id"] == what or p["name"].lower() == what), None)
    if not proj or city.treasury < proj["cost_pc"] * pop:
        return None
    from ..mayor import apply_decision
    lines, _ = apply_decision(city, {"project": proj["id"]})
    return world.moment("king", lines[0] if lines else f"The king ordered {proj['name']}.", 1, public=True) \
        if lines else None


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
    if c["food"] > c["warriors"] * 6:      # the forest is hunted out near the camp
        got //= 3
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


ARG = {"place": "where to walk: " + ", ".join(p["name"] for p in T.PLACES.values()),
       "person": "'steward', 'captain', 'jester', or a subject's @handle", "text": "the words, in your voice",
       "activity": "anything at all: what you feel like doing", "title": "a title, if you made something",
       "description": "what it is like, honestly, in one or two sentences",
       "name": "your idea for this place, in your own words",
       "size": "small (2 days), medium (4) or large (7) - bigger is riskier",
       "purpose": "what it's mainly for: " + ", ".join(BUILD_FLAVORS),
       "case": "a case id from the docket", "verdict": "grant, deny, reward, pardon, fine or jail",
       "words": "what you say", "handle": "a subject's @handle", "why": "why (a few words)",
       "question": "the decree question", "a_word": "one-word choice A", "a_text": "what happens if A wins",
       "a_flavor": "what A does: " + ", ".join(FLAVORS), "b_word": "one-word choice B",
       "b_text": "what happens if B wins", "b_flavor": "what B does", "back": "the word you want to win (optional)",
       "what": "a building project id from the list", "target": "'north' (the war camp) or a hold",
       "hold": "a hold's name", "warriors": "how many warriors to send"}

TOOLS = {
    "king": {
        "walk":       (walk, "walk somewhere in the castle or town (the tavern means going in disguise)", ["place"], None),
        "talk":       (talk, "talk to someone here: a member of your court or a subject (@handle)", ["person", "text"], None),
        "pastime":    (pastime, "do something for its own sake - anything you like (paint, sing, carve, fish...)",
                       ["activity", "title", "description"], None),
        "start_work": (start_work, "start a project of your own right where you are (it costs gold and might fail)",
                       ["name", "size", "purpose"], None),
        "work_on":    (work_on, "roll up your sleeves and help build the project where you are", [], None),
        "hold_court": (hold_court, "in the throne room: rule on the next case on the docket", ["case", "verdict", "words"], None),
        "eat":        (eat, "eat something", [], None),
        "rest":       (rest, "rest, sulk, or sleep", [], None),
        "proclaim":   (proclaim, "make a public proclamation to the kingdom", ["text"], None),
        "summon":     (summon, "summon a subject (a real person) to the castle", ["handle", "why"], None),
        "decree":     (decree, "invent a new decree for the people to vote on tomorrow (one a day)",
                       ["question", "a_word", "a_text", "a_flavor", "b_word", "b_text", "b_flavor", "back"], None),
        "spend":      (spend, "pay for one of the kingdom's building projects", ["what"], None),
        "spy":        (spy, "send spies north to the war camp, or into a hold", ["target"], "room('spymaster_tower')"),
        "garrison":   (garrison, "station soldiers in a hold for a week (raids there get much harder)", ["hold"],
                       "room('war_room')"),
        "feast":      (royal_feast, "throw a feast for the capital or a hold", ["hold"], "room('great_hall')"),
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
