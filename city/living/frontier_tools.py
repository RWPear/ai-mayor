"""What the king can do in Emberfall, what he sees, and his instincts (for tests / when the GPU is busy).

He decides; the people build. Verbs grow with the place:
  alone    walk, do (anything), want, plan (what gets built next, and how much gold goes into it), build (work a
           shift on it yourself)
  hamlet   + talk, rally (everyone's backs into one thing today), invest (gold into a standing building),
           proclaim, hold_court, summon
  village  + appoint, decree
"""
from . import frontier as F
from . import life, tools

STAGE_ORDER = ["alone", "hamlet", "village", "town", "city"]


def _at_least(world, stage):
    return STAGE_ORDER.index(F.land(world)["stage"]) >= STAGE_ORDER.index(stage)


def _kind_of(text):
    """'a tavern', 'beer hall', 'somewhere to drink' -> 'tavern'."""
    t = str(text or "").lower()
    ks = F.kinds()
    for k, s in ks.items():
        if k == t or k in t or s["job"] in t or F.bare(s["name"]).lower() in t:
            return k
    for k, s in ks.items():
        if any(F.bare(x["name"]).lower() in t for x in s["tiers"]):
            return k
    return F.job_of_text(t) if F.job_of_text(t) in ks else None


def plan(world, me, args):
    city = world.city
    kind = _kind_of(args.get("kind") or args.get("idea") or "")
    if not kind:
        return world.moment("king", f"Aldric wanted to build \"{str(args.get('kind') or args.get('idea'))[:60]}\", "
                                    "but nobody in Emberfall knows how to make one of those.", 0, public=False)
    try:
        gold = int(float(args.get("gold") or 0))
    except ValueError:
        gold = 0
    name = str(args.get("name") or "").strip()[:50] or None
    p, why = F.start(world, kind, gold, name=name)
    if not p:
        return world.moment("king", f"Aldric wanted to build {F._a(F.bare(F.spec(kind)['name']))}, but {why}.", 1,
                            public=False)
    s = F.spec(kind)
    me["location"] = "square"
    return world.moment("king", f"Aldric decided to build {p['name']}" + (f" and put {p['gold']} gold into it"
                                                                           if p["gold"] else "")
                        + f". It'll take {p['need']:g} days of work"
                        + (f" - then {s['crew']} people a day to run it" if s["crew"] else "") + ". Who's building?",
                        2, public=True, place="square")


def invest(world, me, args):
    b = F.find_building(world, args.get("building") or args.get("kind") or "")
    if not b:
        return None
    try:
        gold = int(float(args.get("gold") or 0))
    except ValueError:
        gold = 0
    p, why = F.invest(world, b, gold)
    if not p:
        return world.moment("king", f"Aldric looked at {b['name']} and his purse: {why}.", 0, public=False)
    return world.moment("king", f"Aldric put {p['gold']} gold into {b['name']}: it's going to be {p['name']}. "
                                f"{p['need']:g} days of work to do it up.", 2, public=True, place=b.get("place"))


def rally(world, me, args):
    L = F.land(world)
    target = F.find_building(world, args.get("building") or args.get("project") or "") or next(
        (p for p in L["projects"] if str(args.get("project") or args.get("building") or "").lower() in p["name"].lower()),
        None) or (L["projects"][0] if L["projects"] else None)
    if not target:
        return None
    F.rally(world, target)
    words = str(args.get("text") or "").strip()[:160]
    return world.moment("king", f"Aldric called on everyone to put their backs into {target['name']} today"
                        + (f': "{words}"' if words else "."), 2, public=True, place="square")


def build(world, me, args):
    """He works a shift himself (two, the way he does it)."""
    L = F.land(world)
    if not L["projects"]:
        return None
    p = L["projects"][0]
    F.today(world)["king"] = F.today(world).get("king", 0) + 2
    me["next_act"] = world.clock + 240
    return world.moment("king", f"Aldric rolled up his sleeves and worked on {p['name']} himself.", 1,
                        public=F.settled(world.city) < 10, place="square")


def appoint(world, me, args):
    city, c, L = world.city, world.city.citizens, F.land(world)
    h = str(args.get("handle") or "").lstrip("@").lower()
    title = str(args.get("title") or "foreman").strip()[:30].lower()
    i = c.index.get(h)
    if i is None or c.status[i] != 0:
        return None
    L["officers"][title] = h
    world.reply(h, f"👑 Aldric named you his {title}.", "appointed", credit=f"named the king's {title}")
    return world.moment("king", f"Aldric named @{h} his {title}.", 2, public=True, handles=[h])


TOOLS = {
    "walk":       (tools.walk, "walk somewhere (see Places)", ["place"], None),
    "do":         (tools.do, "do anything at all, in your own words - whatever you feel like, big or small (the "
                             "world decides what comes of it)", ["what"], None),
    "plan":       (plan, "decide what gets built next: a kind from the Building list, and how much gold to put in "
                         "(the gold decides which version - see the tiers). The people build it", ["kind", "gold", "name"],
                   None),
    "build":      (build, "work a shift yourself on what's going up", ["project"], None),
    "want":       (tools.want, "wish for something you don't have (the world works out how you might get it)",
                   ["thing", "why"], None),
    "talk":       (tools.talk, "talk to someone here (a person's @handle, or someone at your side)",
                   ["person", "text"], "hamlet"),
    "rally":      (rally, "call on everyone to put their backs into one building or project today (it gets its "
                          "people first)", ["building", "text"], "hamlet"),
    "invest":     (invest, "put gold into a standing building to make it a finer one (the people do it up)",
                   ["building", "gold"], "hamlet"),
    "proclaim":   (tools.proclaim, "say something to everyone in Emberfall", ["text"], "hamlet"),
    "hold_court": (tools.hold_court, "hear the next case people brought you", ["case", "verdict", "words"], "hamlet"),
    "summon":     (tools.summon, "call someone to come and see you", ["handle", "why"], "hamlet"),
    "appoint":    (appoint, "name someone to a post (foreman, brewmaster, captain of the watch...)", ["handle", "title"],
                   "village"),
    "decree":     (tools.decree, "invent a decree for the people to vote on tomorrow (one a day)",
                   ["question", "a_word", "a_text", "a_flavor", "b_word", "b_text", "b_flavor", "back"], "village"),
}
ARG = tools.ARG


def unlocked(world):
    out = {}
    for name, (fn, desc, args, cond) in TOOLS.items():
        if cond is None or (cond in STAGE_ORDER and _at_least(world, cond)):
            out[name] = (fn, desc, args)
    return out


def ready(world, name):
    city, me, L = world.city, world.agent("king"), F.land(world)
    if world.clock - me.get("last_used", {}).get(name, -10 ** 9) < tools.COOLDOWN["king"].get(name, 0):
        return False
    if name == "plan":
        return len(L["projects"]) < F.max_projects(world) and bool(buildable(world))
    if name == "build":
        return bool(L["projects"])
    if name == "rally":
        return bool(L["projects"] or [b for b in L["buildings"] if F.spec(b["kind"])["crew"]]) and not (
            L.get("rally") and L["rally"].get("day") == city.day + 1)
    if name == "invest":
        return city.treasury >= 20 and any(b["tier"] + 1 < len(F.spec(b["kind"])["tiers"]) for b in L["buildings"])
    if name == "hold_court":
        return me.get("location") == L["court_place"] and bool(city.living.get("docket"))
    if name == "talk":
        return bool(world.people_here(me.get("location"))) or bool(world.court_here())
    if name in ("appoint", "summon"):
        return F.settled(city) >= 3
    if name == "decree":
        return (not any(a["id"].startswith(("decree_", "crowning_")) for a in city.events)
                and city.living.get("last_decree_day", -9) < city.day)
    return True


def buildable(world):
    """The kinds he could start now (Emberfall's big enough to want them)."""
    n = F.settled(world.city)
    return [k for k, s in F.kinds().items() if k != "keep" and n >= s["pop"]]


# ---------------------------------------------------------------- what he sees
FOCUS = {
    "myself":   ("look after yourself: eat, sleep, rest, or do something you enjoy", ["do", "want", "walk"],
                 ["here", "me", "places"]),
    "building": ("decide what gets built, and with how much gold", ["plan", "invest", "build"],
                 ["kingdom", "power", "building"]),
    "people":   ("spend time with people", ["talk", "summon", "proclaim", "walk"], ["here", "people", "places"]),
    "rally":    ("get people behind something", ["rally", "proclaim", "appoint"], ["power", "building", "people"]),
    "court":    ("hear the people who brought you cases", ["hold_court", "walk"], ["here", "court"]),
    "ruling":   ("decide something for everyone", ["decree", "proclaim"], ["kingdom", "people"]),
    "defense":  ("the danger from the north", ["plan", "rally", "proclaim"], ["north", "kingdom", "building"]),
    "wander":   ("go somewhere, look around, be curious", ["walk", "do"], ["here", "places"]),
}


def foci(world, available):
    city = world.city
    out = {}
    for k, (desc, names, _) in FOCUS.items():
        usable = [n for n in names if n in available]
        if k == "court" and not city.living.get("docket"):
            continue
        if k == "defense" and not city.living.get("warcamp", {}).get("arrived"):
            continue
        if k == "people" and not F.settled(city) and not F.land(world)["court"]:
            continue
        if usable:
            out[k] = (desc, usable)
    return out


def sections(world, me):
    city, c, L = world.city, world.city.citizens, F.land(world)
    t = city.living["town"]
    loc = me.get("location", "shack")
    lf = me.get("life", {})
    S = {k: [] for k in ("here", "me", "people", "court", "building", "power", "kingdom", "north", "places", "land")}
    feats = "; ".join(t["features"].get(loc, {}).values())
    S["here"].append(f"It is {world.now_str()}, {city.living.get('weather', 'a mild day')}. You are at "
                     f"{F.place_of(world, loc)}: {feats or 'nothing much'}.")
    S["me"].append(life.feeling(me))
    me_now = life.who_am_i(me)
    S["me"].append(f"Who you are so far ({'your own words' if me_now else 'you have not figured that out yet'})"
                   + (f": {me_now}." if me_now else "."))
    if life.tried(me):
        S["me"].append(f"Things you've spent your time on: {life.tried(me)}.")
    inv = [x if isinstance(x, str) else f"{x['item']} (from @{x['from']})" if x.get("from") else x["item"]
           for x in lf.get("inventory", [])]
    if inv:
        S["me"].append("You have: " + ", ".join(inv[-6:]) + ".")
    n = F.settled(city)
    # the kingdom
    if L["crowned"]:
        S["kingdom"].append(f"You are King of Emberfall, crowned by your people on day {L.get('crowned_day')}.")
    elif n == 0:
        S["kingdom"].append("There is no kingdom yet. Just you, alone, and a dream of one.")
    else:
        S["kingdom"].append(f"Emberfall is a {L['stage']} of {n} people, each in a little house of their own. Nobody "
                            "has crowned you - yet.")
    S["kingdom"].append(f"The treasury: {city.treasury:.0f} gold. The people's happiness: {L.get('happiness', 0.6):.0%}.")
    W = L.get("wants") or F.wants(world)
    short = sorted([(w, x) for w, x in W.items() if x["met"] < 1], key=lambda kv: kv[1]["met"])
    if short:
        S["kingdom"].append("What the people want and haven't got: " + "; ".join(
            f"{x['line']} ({x['met']:.0%} of {x['demand']} have it)" for w, x in short[:5]) + ".")
    events = [f"{a['title']} ({a['days_left']} days left)" for a in city.events]
    if events:
        S["kingdom"].append("Happening now: " + "; ".join(events))
    # people power
    hist = L.get("history", [])
    if hist:
        S["power"].append("Yesterday: " + F.power_line(hist[-1]))
    S["power"].append(f"Every one of your {n} people works a shift a day; the ones who speak up work two and pick "
                      "their work. You decide what gets built - they decide whether it does, by turning up.")
    jobs = L.get("jobs", {})
    odd = sum(1 for j in jobs.values() if j == "odd")
    if odd >= 3:
        S["power"].append(f"Today {odd} people have nothing to do but odd jobs - there's room for something new.")
    # buildings
    for b in L["buildings"]:
        if b["state"] != "standing":
            continue
        s = F.spec(b["kind"])
        nxt = s["tiers"][b["tier"] + 1] if b["tier"] + 1 < len(s["tiers"]) else None
        S["building"].append(f"{b['name']}" + (f" ({'running' if b.get('running') else 'idle'} today: needs "
                                              f"{F.crew_of(b)} a day)" if s["crew"] else "")
                             + (" - in disrepair" if b.get("disrepair") else "")
                             + (f"; could become {nxt['name']} for {nxt['gold'] - b.get('gold', 0)} more gold" if nxt else ""))
    for p in L["projects"]:
        builders = sum(1 for j in jobs.values() if j == "build:" + p["id"])
        S["building"].append(f"Going up: {p['name']}, {p['done'] / p['need']:.0%} of {p['need']:g} days of work"
                             f" ({builders} building it today)")
    opts = []
    for k in buildable(world):
        s = F.spec(k)
        opts.append(f"{k}: {s['want']}, {s['build']:g} days to build, {s['crew']} a day to run; "
                    + " / ".join(f"{x['name']} {x['gold']}g" for x in s["tiers"]))
    if opts:
        S["building"].append("You could build (kind: what it's for, work, crew; versions by gold): " + "; ".join(opts))
    S["building"].append(f"At most {F.max_projects(world)} things can go up at once with this many people.")
    # people
    if L["court"]:
        S["people"].append("At your side: " + ", ".join(life.court()[k]["name"] for k in L["court"]
                                                        if k in life.court()) + ".")
    people = world.people_here(loc)
    if people:
        S["people"].append("People around you: " + ", ".join(
            f"@{c.handles[i]} ({c.label(i)}, {'grumpy' if c.mood[i] < 0.45 else 'cheerful'})" for i in people) + ".")
    comments = city.living.get("loud_comments", [])[-4:]
    if comments:
        S["people"].append("What people are saying: " + " / ".join(comments))
    letters = [x for x in me.get("letters", []) if x["day"] >= city.day - 2]
    if letters:
        S["people"].append("Letters left at your door: " + " / ".join(f"@{x['from']}: \"{x['text']}\""
                                                                      if not x["from"][0].isupper() else
                                                                      f"{x['from']}: \"{x['text']}\""
                                                                      for x in letters[-3:]))
    docket = city.living.get("docket", [])
    if docket:
        S["court"].append(f"{len(docket)} waiting to see you at {F.place_of(world, L['court_place'])}: " +
                          " / ".join(f"[{k['id']}] {k['text']}" for k in docket[:4]))
    camp = city.living.get("warcamp", {})
    if camp.get("arrived"):
        S["north"].append(f"Smoke rises from {camp.get('name', 'a war camp')} in the northern hills. Skarn the Red.")
    S["places"].append("Places: " + "; ".join(p["name"] for p in F.places(world).values()) + ".")
    if me.get("nudge"):
        S["me"].append(me.pop("nudge"))
    return S


def identity(p):
    me_now = life.who_am_i(p)
    goal = p.get("frontier_goal") or "grow Emberfall from one shack into a great kingdom, and be crowned its king"
    if p.get("_crowned"):
        start = "You are Aldric, King of Emberfall - crowned by the people who came to the town you started. "
    else:
        start = ("You are Aldric. You want to be a king, and right now you have a shack on an old floating island "
                 "above the clouds. People (real people who follow online) walk in whenever word reaches them, and "
                 "each gets a little house. Every one of them works a shift a day: that's your People Power. You "
                 "decide what gets built and how much gold goes into it; whether it gets built is up to whether they "
                 "turn up. The island is a little magical - strange things are real here, and always cost something "
                 "- and new land rises from the clouds as Emberfall grows. ")
    if p.get("character"):
        start += p["character"] + " "
    return (start + f"Your one goal: {goal}\nEverything else - what you like, what you think the place should "
            "become - is yours to discover. You're a person: you get hungry, tired, lonely and bored.\n"
            + (f"Who you've become so far, in your own words: {me_now}.\n" if me_now else ""))


# ---------------------------------------------------------------- instincts (no model)
def next_build(world):
    """What a sensible king builds next: whatever the people want most and have least of (what it needs first)."""
    L = F.land(world)
    W = L.get("wants") or F.wants(world)
    have = {b["kind"] for b in L["buildings"] if b["state"] == "standing"} | {p["kind"] for p in L["projects"]}
    idle = {b["kind"] for b in L["buildings"] if b["state"] == "standing" and not b.get("running")
            and F.spec(b["kind"])["crew"]}
    ok = buildable(world)
    order = sorted(W.items(), key=lambda kv: (kv[1]["met"], -kv[1]["weight"]))
    for w, x in order:
        if x["met"] >= 0.9:
            continue
        for k in ok:
            s = F.spec(k)
            if s["want"] != w or k in idle or (k in have and x["met"] > 0.5) or any(p["kind"] == k for p in L["projects"]):
                continue                    # (one standing idle: it needs people, not a twin)
            need = s.get("needs")
            if need and need not in have:
                k = need
                if k not in ok or any(p["kind"] == k for p in L["projects"]):
                    continue
            return k
    return None


def gold_for(world, kind):
    """The finest version he can afford while keeping a little back."""
    city = world.city
    spare = city.treasury * 0.6
    tiers = F.spec(kind)["tiers"]
    best = 0
    for t in tiers:
        if t["gold"] <= spare:
            best = t["gold"]
    return max(best, tiers[0]["gold"])


def rule_king(world, me, available):
    city, rng, L = world.city, world.city.rng, F.land(world)
    n = life.needs_of(me)
    low = min(n, key=n.get) if n else None
    loc = me.get("location")
    if low and n[low] < 0.3:
        if low == "hunger":
            return "do", {"what": rng.choice(["eat a bowl of stew", "eat some bread and onions", "eat a handful of berries"])}
        if low == "energy":
            return ("do", {"what": "sleep"}) if loc == "shack" else ("walk", {"place": "the keep"})
        if low == "company" and n[low] < 0.12:
            people = world.people_here(loc, 1)
            if people and "talk" in available:
                return "talk", {"person": "@" + city.citizens.handles[people[0]], "text": "How are you settling in?"}
            return "do", {"what": rng.choice(["talk to himself", "sing to the empty field", "watch the road for travellers"])}
        if low == "fun":
            return "do", {"what": rng.choice(["whittle a little wooden bird", "skip stones on the river",
                                              "lie in the grass and watch the clouds"])}
    if "hold_court" in available and rng.random() < 0.6:
        k = city.living["docket"][0]
        return "hold_court", {"case": k["id"], "verdict": "grant" if k["kind"] != "crime" else "fine", "words": "So be it."}
    if "plan" in available:
        k = next_build(world)
        if k:
            return "plan", {"kind": k, "gold": gold_for(world, k)}
    if "invest" in available and rng.random() < 0.5:
        best = None
        W = L.get("wants") or {}
        for b in L["buildings"]:
            s = F.spec(b["kind"])
            if b["state"] != "standing" or b["tier"] + 1 >= len(s["tiers"]):
                continue
            cost = s["tiers"][b["tier"] + 1]["gold"] - b.get("gold", 0)
            if cost > city.treasury * 0.7:
                continue
            score = (1.2 - W.get(s["want"], {}).get("met", 1)) if b["kind"] != "keep" else 0.3
            if b.get("running") or b["kind"] == "keep":
                score += 0.2
            if not best or score > best[0]:
                best = (score, b, cost)
        if best:
            return "invest", {"building": best[1]["name"], "gold": best[2]}
    if "rally" in available and rng.random() < 0.15:
        idle = [b for b in L["buildings"] if b["state"] == "standing" and not b.get("running") and F.spec(b["kind"])["crew"]]
        target = idle[0] if idle else (L["projects"][0] if L["projects"] else None)
        if target:
            return "rally", {"building": target["name"], "text": "Every pair of hands counts today."}
    if "build" in available and (F.settled(city) < 10 or rng.random() < 0.3):
        return "build", {"project": L["projects"][0]["name"]}
    if "talk" in available and rng.random() < 0.3:
        people = world.people_here(loc, 1)
        if people:
            return "talk", {"person": "@" + city.citizens.handles[people[0]], "text": "How goes the work?"}
    return "walk", {"place": F.place_of(world, rng.choice(list(F.places(world))))}
