"""What the king can do on the frontier, what he sees, and his instincts (for tests / when the GPU is busy).

Verbs grow with the place:
  alone    walk, do (anything), gather, plan (an idea of his own -> the world prices it), build, want
  hamlet   + talk, ask_help (everyone pitches in today), proclaim, hold_court, summon
  village  + organize (crews for a few days), appoint (a settler as foreman / forager / ...), decree
  any time the peddler is on the road: trade
"""
import re

from . import frontier as F
from . import life, tools

STAGE_ORDER = ["alone", "hamlet", "village", "town", "city"]


def _at_least(world, stage):
    return STAGE_ORDER.index(F.land(world)["stage"]) >= STAGE_ORDER.index(stage)


# ---------------------------------------------------------------- tools
def gather(world, me, args):
    m = str(args.get("material") or "").strip().lower().rstrip("s")
    m = {"log": "wood", "timber": "wood", "branche": "wood", "rock": "stone", "reed": "thatch", "grass": "thatch",
         "straw": "thatch", "berrie": "food", "fish": "food", "mushroom": "food", "vine": "rope"}.get(m, m)
    loc = me.get("location")
    here = F.places(world).get(loc, {}).get("resources", [])
    if m not in F.RATES or m == "iron":
        me["nudge"] = "You can gather wood, stone, clay, thatch, rope or food."
        return None
    if m not in here:
        where = [F.place_of(world, p) for p in F.where_to_get(world, m)]
        me["nudge"] = f"There's no {m} here. You'd find it at: {', '.join(where)}."
        return None
    city, L = world.city, F.land(world)
    how = str(args.get("how") or "").strip()[:120]
    hours = city.rng.uniform(1.0, 2.0)
    n = life.needs_of(me)
    practice = L["practice"].get(m, 0)
    rate = (F.RATES[m] * F.tool_x(city, m) * min(1.6, 1 + 0.04 * practice) * (0.5 + n.get("energy", 0.6))
            * (0.75 if "rain" in city.living.get("weather", "") else 1.0))
    got = max(1, round(rate * hours))
    L["stock"][m] = L["stock"].get(m, 0) + got
    L["practice"][m] = practice + 1
    F.day_log(world, "king", m, got)
    from . import scene
    scene.harvested(world, m, got)
    out = world.narrate_activity(me, f"gather {m} by hand" + (f": {how}" if how else ""))
    for need in life.NEEDS:
        life.satisfy(me, need, out.get(need, 0.0))
    life.satisfy(me, "energy", -0.05 * hours)
    life.satisfy(me, "hunger", -0.04 * hours)
    me["next_act"] = world.clock + int(hours * 60)
    first = practice == 0
    text = out["outcome"].rstrip(".") + f". (+{got} {F.UNIT[m]})"
    return world.moment("king", F.title(city, text), max(int(out.get("drama", 0)), 1 if first else 0),
                        public=first or int(out.get("drama", 0)) >= 1, place=loc)


def plan(world, me, args):
    idea = str(args.get("idea") or args.get("name") or "").strip()[:100]
    if not idea:
        return None
    p, why = F.start_project(world, idea, args.get("place"))
    if not p:
        if why and ("far too much" in why or "comes close" in why):
            me["nudge"] = f"You paced out {idea} in the field, then stopped: {why}."
            return world.moment("king", f"Aldric paced out {idea} in the field, then stopped and laughed at himself: "
                                        f"{why}.", 1, public=True)
        if why and "too many" not in why and why != "no idea":
            return world.moment("king", f"Aldric dreamed up {idea} - but {why}.", 1, public=True)
        me["nudge"] = f"You can't start that: {why}."
        return None
    needs = ", ".join(f"{n} {F.UNIT[m]}" for m, n in p["needs"].items())
    gap = (f" He doesn't know {', '.join(p['missing'])} yet - he'll have to figure it out as he goes."
           if p["missing"] else "")
    cap = f" Room for {p['capacity']}." if p["capacity"] else ""
    world.notify(f"New idea: {p['name']} ({needs}, ~{p['hours']:.0f}h)")
    tools._credit_ideas(world, idea)
    return world.moment("king", f"Aldric decided to build {p['name']} at {F.place_of(world, p['place'])}. It'll "
                                f"take {needs} and about {p['hours']:.0f} hours of work.{cap}{gap}",
                        2, public=True, place=p["place"])


def build(world, me, args):
    L = F.land(world)
    loc = me.get("location")
    want = str(args.get("project") or "").lower()
    here = [p for p in L["projects"] if p["place"] == loc]
    p = next((p for p in here if want and want in p["name"].lower()), here[0] if here else None)
    if not p:
        return None
    city = world.city
    hours = city.rng.uniform(1.5, 2.5)
    rate = F.build_x(city) * min(1.5, 1 + 0.05 * L.get("builds", 0)) * (0.5 + life.needs_of(me).get("energy", 0.6))
    before = p["progress"]
    df, blocked = F.work(world, p, hours * rate)
    if df > 0:
        F.day_log(world, "king", "build_hours", hours)
    me["next_act"] = world.clock + int(hours * 60)
    life.satisfy(me, "energy", -0.06 * hours)
    life.satisfy(me, "hunger", -0.04 * hours)
    life.satisfy(me, "fun", 0.1)
    if p.get("done"):
        return None                                     # finish() already told the story
    if df <= 0:
        short = F.short_of(world, p)
        me["nudge"] = f"You can't get on with {p['name']}: you need " + ", ".join(
            f"{n} more {F.UNIT[m]}" for m, n in short.items()) + "."
        return world.moment("king", f"Aldric stood looking at {p['name']}. Not enough "
                            + " or ".join(F.UNIT[m] for m in blocked) + " to go on.", 0, public=False, place=loc)
    text = (f"Aldric worked on {p['name']} for {hours:.0f} hours ({before:.0%} -> {p['progress']:.0%})."
            + (" Then he ran out of " + " and ".join(F.UNIT[m] for m in blocked) + "." if blocked else ""))
    mark = int(p["progress"] * 4) > int(before * 4)           # a quarter done, half done, nearly there
    return world.moment("king", text, 1, public=mark, place=loc)


def ask_help(world, me, args):
    L, city = F.land(world), world.city
    if L.get("help") and L["help"].get("day") == city.day + 1:
        return None
    words = str(args.get("text") or "").strip()[:200]
    L["help"] = {"day": city.day + 1}
    if L.get("asked_days", 0) >= 2:
        from .. import effects
        effects.apply(city, {"mood": -0.01})
    L["asked_days"] = L.get("asked_days", 0) + 1
    return world.moment("king", f'Aldric went round the settlers asking for help today' + (f': "{words}"' if words
                                else ".") + " More hands on everything.", 1, public=True)


def organize(world, me, args):
    L, city = F.land(world), world.city
    task = str(args.get("task") or "").lower()
    try:
        people = int(float(args.get("people") or 5))
    except ValueError:
        people = 5
    people = max(1, min(people, F.settled(city)))
    proj = next((p for p in L["projects"] if p["name"].lower() in task or task in p["name"].lower()), None)
    mat = next((m for m in F.RATES if m in task and m != "iron"), None)
    if proj:
        key, what = f"build:{proj['id']}", f"building {proj['name']}"
    elif mat:
        key, what = f"gather:{mat}", f"gathering {mat}"
    else:
        return None
    L["crews"] = [x for x in L.get("crews", []) if x["task"] != key] + [{"task": key, "people": people,
                                                                        "until": city.day + 3}]
    return world.moment("king", f"Aldric put {people} settlers on {what} for the next three days.", 1, public=True)


def appoint(world, me, args):
    L, c = F.land(world), world.city.citizens
    h = str(args.get("handle") or "").lstrip("@").lower()
    i = c.index.get(h)
    title = str(args.get("title") or "foreman").strip().lower()[:30]
    if i is None or c.status[i] != 0:
        return None
    slot = ("builder" if re.search(r"build|foreman|carpent|mason|architect", title) else
            "forager" if re.search(r"food|hunt|farm|forag|cook|fish", title) else "gatherer")
    L["officers"][slot] = h
    c.log(int(i), world.city.day + 1, f"was named {title} by Aldric")
    world.reply(h, f"📜 Aldric named your character {title} of Emberfall. People will look to you now.", "appointed",
                credit=f"named {title}")
    return world.moment("king", f"Aldric named @{h} ({c.label(i)}) {title} of Emberfall.", 2, public=True,
                        handles=[h])


def trade(world, me, args):
    city, L = world.city, F.land(world)
    if not F.peddler_here(world) or me.get("location") != "road":
        return None
    goods = {g[0]: g for g in F.PEDDLER if g[0] in L["peddler"]["goods"]}
    said = []
    sell = str(args.get("sell") or "")
    m = re.search(r"(\d+)\s*([a-z]+)", sell.lower())
    if m:
        n, mat = int(m.group(1)), m.group(2).rstrip("s")
        if mat in F.SELL and L["stock"].get(mat, 0) >= 1:
            n = min(n, int(L["stock"][mat]))
            L["stock"][mat] -= n
            gold = round(n * F.SELL[mat])
            city.treasury += gold
            said.append(f"sold {n} {F.UNIT[mat]} for {gold} gold")
    buy = str(args.get("buy") or "").lower()
    pick = next((g for name, g in goods.items() if buy and (buy in name or name.split()[-1] in buy)), None)
    if pick:
        name, price, eff = pick
        if city.treasury >= price:
            city.treasury -= price
            L["peddler"]["goods"].remove(name)
            if "stock" in eff:
                L["stock"][eff["stock"][0]] = L["stock"].get(eff["stock"][0], 0) + eff["stock"][1]
            if "tool" in eff or "build" in eff or "food_day" in eff:
                L["tools"].append({"name": name, **{k: v for k, v in eff.items() if k != "comfort"}})
            if eff.get("comfort"):
                life.satisfy(me, "fun", 0.2)
            said.append(f"bought {name} for {price} gold")
        else:
            said.append(f"couldn't afford {name} ({price} gold - he has {city.treasury:.0f})")
    if not said:
        return None
    return world.moment("king", "At the peddler's cart, Aldric " + " and ".join(said) + ".", 1, public=True,
                        place="road")


TOOLS = {
    "walk":       (tools.walk, "walk somewhere (see Places)", ["place"], None),
    "do":         (tools.do, "do anything at all, in your own words - whatever you feel like, big or small (the "
                             "world decides what comes of it)", ["what"], None),
    "gather":     (gather, "gather a material here by hand (wood, stone, clay, thatch, rope or food)",
                   ["material", "how"], None),
    "plan":       (plan, "decide to build something - your own idea, in your own words. The world works out what it "
                         "takes", ["idea", "place"], None),
    "build":      (build, "work on a project where you are (uses up materials from your stores)", ["project"], None),
    "want":       (tools.want, "wish for something you don't have (the world works out how you might get it)",
                   ["thing", "why"], None),
    "talk":       (tools.talk, "talk to someone here (a settler's @handle, or someone at your side)",
                   ["person", "text"], "hamlet"),
    "ask_help":   (ask_help, "ask the settlers to pitch in harder today", ["text"], "hamlet"),
    "proclaim":   (tools.proclaim, "say something to everyone in Emberfall", ["text"], "hamlet"),
    "hold_court": (tools.hold_court, "hear the next case people brought you", ["case", "verdict", "words"], "hamlet"),
    "summon":     (tools.summon, "call a settler to come and see you", ["handle", "why"], "hamlet"),
    "organize":   (organize, "put a crew of settlers on one job for three days (gathering a material, or a project)",
                   ["task", "people"], "village"),
    "appoint":    (appoint, "name a settler to a job (foreman, forager, quarry master...)", ["handle", "title"],
                   "village"),
    "decree":     (tools.decree, "invent a decree for the people to vote on tomorrow (one a day)",
                   ["question", "a_word", "a_text", "a_flavor", "b_word", "b_text", "b_flavor", "back"], "village"),
    "trade":      (trade, "trade with the peddler on the old road: buy something, or sell materials ('20 wood')",
                   ["buy", "sell"], None),
}
ARG = tools.ARG       # argument descriptions live with the other tools

def unlocked(world):
    out = {}
    for name, (fn, desc, args, cond) in TOOLS.items():
        if cond is None or (cond == "peddler" and F.peddler_here(world)) or (cond in STAGE_ORDER and
                                                                             _at_least(world, cond)):
            out[name] = (fn, desc, args)
    return out


def ready(world, name):
    city, me, L = world.city, world.agent("king"), F.land(world)
    loc = me.get("location")
    if world.clock - me.get("last_used", {}).get(name, -10 ** 9) < tools.COOLDOWN["king"].get(name, 0):
        return False
    if name == "gather":
        return bool(F.places(world).get(loc, {}).get("resources"))
    if name == "build":
        return any(p["place"] == loc for p in L["projects"])
    if name == "plan":
        return len(L["projects"]) < 3
    if name == "trade":
        return loc == "road" and F.peddler_here(world)
    if name == "hold_court":
        return loc == L["court_place"] and bool(city.living.get("docket"))
    if name == "talk":
        return bool(world.people_here(loc)) or bool(world.court_here())
    if name == "ask_help":
        return bool(L["projects"]) and not (L.get("help") and L["help"].get("day") == city.day + 1)
    if name in ("organize", "appoint", "summon"):
        return F.settled(city) >= 3
    if name == "decree":
        return (not any(a["id"].startswith(("decree_", "crowning_")) for a in city.events)
                and city.living.get("last_decree_day", -9) < city.day)
    return True


# ---------------------------------------------------------------- what he sees
FOCUS = {
    "myself":   ("look after yourself: eat, sleep, rest, or do something you enjoy", ["do", "want", "walk"],
                 ["here", "me", "land", "places"]),
    "gather":   ("gather materials", ["gather", "walk"], ["here", "land", "building", "places"]),
    "building": ("plan or build something", ["plan", "build", "walk"], ["here", "land", "building", "kingdom",
                                                                        "places"]),
    "people":   ("spend time with people", ["talk", "summon", "proclaim", "walk"], ["here", "people", "places"]),
    "organize": ("organize the settlers' work", ["ask_help", "organize", "appoint"], ["land", "building", "kingdom",
                                                                                     "people"]),
    "court":    ("hear the people who brought you cases", ["hold_court", "walk"], ["here", "court"]),
    "ruling":   ("decide something for everyone", ["decree", "proclaim"], ["kingdom", "people"]),
    "trade":    ("trade with the peddler", ["trade", "walk"], ["here", "land", "building"]),
    "defense":  ("the danger from the north", ["plan", "build", "proclaim", "walk"], ["north", "kingdom", "building"]),
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
        if k == "trade" and "trade" not in available and not F.peddler_here(world):
            continue
        if k == "people" and not F.settled(city) and not F.land(world)["court"]:
            continue                     # nobody to spend time with yet
        if usable:
            out[k] = (desc, usable)
    return out


def sections(world, me):
    city, c, L = world.city, world.city.citizens, F.land(world)
    t = city.living["town"]
    loc = me.get("location", "shack")
    lf = me.get("life", {})
    S = {k: [] for k in ("here", "me", "people", "court", "building", "kingdom", "north", "places", "land")}
    P = F.places(world).get(loc, {})
    feats = "; ".join(t["features"].get(loc, {}).values())
    S["here"].append(f"It is {world.now_str()}, {city.living.get('weather', 'a mild day')}. You are at "
                     f"{F.place_of(world, loc)}: {feats or 'nothing much'}.")
    if P.get("resources"):
        S["here"].append("Here you can gather: " + ", ".join(P["resources"]) + ".")
    if loc == "road" and F.peddler_here(world):
        S["here"].append("A peddler's cart is here selling: " + ", ".join(
            f"{g[0]} ({g[1]} gold)" for g in F.PEDDLER if g[0] in L["peddler"]["goods"])
                         + f". You have {city.treasury:.0f} gold.")
    S["me"].append(life.feeling(me))
    me_now = life.who_am_i(me)
    S["me"].append(f"Who you are so far ({'your own words' if me_now else 'you have not figured that out yet'})"
                   + (f": {me_now}." if me_now else "."))
    if life.tried(me):
        S["me"].append(f"Things you've spent your time on: {life.tried(me)}.")
    S["me"].append("Techniques you know: " + (", ".join(L["know"]) if L["know"] else "none yet - you've never built "
                                                                                       "anything"))
    inv = [x if isinstance(x, str) else f"{x['item']} (from @{x['from']})" if x.get("from") else x["item"]
           for x in lf.get("inventory", [])]
    if inv:
        S["me"].append("You have: " + ", ".join(inv[-6:]) + ".")
    S["land"].append(F.stock_line(city))
    S["land"].append("Your tools: " + ", ".join(x["name"] for x in L["tools"][-6:]) + ".")
    for p in L["projects"]:
        short = F.short_of(world, p)
        S["building"].append(
            f"Project: {p['name']} at {F.place_of(world, p['place'])}, {p['progress']:.0%} done"
            + (f", room for {p['capacity']}" if p["capacity"] else "")
            + (f"; still needs {', '.join(f'{n} {F.UNIT[m]}' for m, n in short.items())} more than you have"
               if short else "; you have everything it needs - it just needs work")
            + (f"; you don't know {', '.join(p['missing'])} (risky)" if p["missing"] else "") + ".")
    built = [b for b in L["buildings"] if b["id"] != "b0"]
    if built:
        S["building"].append("What you've built: " + "; ".join(
            f"{b['name']} ({b['quality']}" + (f", room for {b['capacity']}" if b.get("capacity") else "") + ")"
            for b in built[-8:]) + ".")
    fails = [o for o in lf.get("outcomes", []) if o["result"] == "failed"][-2:]
    if fails:
        S["building"].append("What fell down: " + ", ".join(o["name"] for o in fails) + ".")
    n, road = F.settled(city), F.on_road(city)
    if L["crowned"]:
        S["kingdom"].append(f"You are King of Emberfall, crowned by your settlers on day {L.get('crowned_day')}.")
    elif n == 0:
        S["kingdom"].append("There is no kingdom yet. Just you, alone, and a dream of one.")
    else:
        S["kingdom"].append(f"Emberfall is a {L['stage']} of {n} settler{'s' if n > 1 else ''}. Nobody has crowned "
                            f"you - yet.")
    S["kingdom"].append(f"Beds: {F.capacity(city)} ({F.free_beds(city)} free). People in tents: {F.tents(city)}.")
    new = len(city.living.get("just_arrived") or {})
    S["kingdom"].append("Newcomers walk up the old road whenever word reaches them - any day, any hour."
                        + (f" {new} arrived in the last day." if new else ""))
    cap = F.max_scale(world)
    S["building"].append(f"The biggest thing you could realistically take on now: something {cap} "
                         f"({F.example(cap, world.city.rng)}). Bigger needs more hands, and you get there by building bigger "
                         f"one step at a time.")
    if L.get("builds", 0) < 2 and not n:
        from . import flavor
        S["building"].append(f"Small jobs count ({flavor.some(flavor.SMALL_JOBS, 3, world.city.rng)}...) - an hour or "
                             "two each, and the place looks a little more lived-in by tonight. A cottage alone is about "
                             "a day.")
    if L.get("idle_yesterday", 0) >= 5:
        S["kingdom"].append(f"Yesterday the settlers had {L['idle_yesterday']} hours with nothing to do - nothing "
                            "of yours left to build or gather for.")
    if n:
        S["kingdom"].append(f"The settlers work on your projects every day (more on days they're keen) and gather what "
                            f"those projects need - but only you decide what gets built.")
    events = [f"{a['title']} ({a['days_left']} days left)" for a in city.events]
    if events:
        S["kingdom"].append("Happening now: " + "; ".join(events))
    if L["court"]:
        S["people"].append("At your side: " + ", ".join(life.court()[k]["name"] for k in L["court"]
                                                        if k in life.court()) + ".")
    people = world.people_here(loc)
    if people:
        S["people"].append("Settlers around you: " + ", ".join(
            f"@{c.handles[i]} ({c.label(i)}{', in a tent' if int(c.walled[i]) == -2 else ''}, "
            f"{'grumpy' if c.mood[i] < 0.45 else 'cheerful'})" for i in people) + ".")
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
    S["places"].append("Places: " + "; ".join(f"{p['name']}" + (f" ({', '.join(p['resources'])})" if p.get("resources")
                                                                  else "") for p in F.places(world).values()) + ".")
    if me.get("nudge"):
        S["me"].append(me.pop("nudge"))
    return S


def identity(p):
    city_crowned = p.get("_crowned")
    me_now = life.who_am_i(p)
    goal = p.get("frontier_goal") or "build a kingdom out of nothing, and be crowned its king"
    if city_crowned:
        start = ("You are Aldric, King of Emberfall - crowned by the settlers who came to the town you built with your "
                 "own hands. ")
    else:
        start = ("You are Aldric. You want to be a king, but right now you have nothing: a leaky one-room shack in a "
                 "field, a dull axe, the clothes you're wearing. No subjects, no court, no gold to speak of, and "
                 "nobody has crowned you. Everything has to be built by hand, starting with your own. People (real "
                 "people who follow online) arrive once a week - if there's something to come to. ")
    if p.get("character"):
        start += p["character"] + " "
    return (start + f"Your one goal: {goal}\nEverything else - what you like, how you build, what you think the place "
            "should become - is yours to discover. You're a person: you get hungry, tired, lonely and bored, your "
            "ideas can fail, and you learn by doing.\n"
            + (f"Who you've become so far, in your own words: {me_now}.\n" if me_now else ""))


# ---------------------------------------------------------------- instincts (no model)
TEST_LADDER = [("small", 3, "a small cottage with a thatched roof"), ("medium", 10, "a longhouse for the newcomers"),
               ("large", 30, "a row of timber houses"), ("huge", 90, "a tall apartment building of stone and timber")]
TEST_FIRST = ["a stone fire pit by the shack", "a new roof for the shack"]     # day one: quick wins
TEST_OTHERS = [ "a vegetable garden", "a stone axe", "a storehouse for food",
               "a fish trap in the river", "a meeting hall", "a well"]


def rule_king(world, me, available):
    city, rng, L = world.city, world.city.rng, F.land(world)
    loc = me.get("location")
    n = life.needs_of(me)
    low = min(n, key=n.get) if n else None
    if low and n[low] < 0.3:
        if low == "hunger":
            if L["stock"].get("food", 0) >= 1:
                return "do", {"what": rng.choice(["eat a bowl of thin stew", "eat some bread and onions",
                                                  "eat a handful of berries"])}
            if "food" in F.places(world).get(loc, {}).get("resources", []):
                return "gather", {"material": "food", "how": "foraging"}
            return "walk", {"place": "the woods"}
        if low == "energy":
            return ("do", {"what": "sleep on the straw mat"}) if loc == "shack" else ("walk", {"place": "the shack"})
        if low == "company" and n[low] < 0.12:
            people = world.people_here(loc, 1)
            if people and "talk" in available:
                return "talk", {"person": "@" + city.citizens.handles[people[0]], "text": "How are you settling in?"}
            return "do", {"what": rng.choice(["talk to himself while he works", "sing to the empty field",
                                              "watch the old road for travellers"])}
        if low == "fun":
            return "do", {"what": rng.choice(["whittle a little wooden bird", "skip stones on the river",
                                              "lie in the grass and watch the clouds"])}
    if "trade" in available and city.treasury >= 25 and not any("iron" in x["name"] for x in L["tools"]):
        return "trade", {"buy": "iron axe", "sell": "20 wood"}
    if "hold_court" in available and rng.random() < 0.6:
        k = city.living["docket"][0]
        return "hold_court", {"case": k["id"], "verdict": "grant" if k["kind"] != "crime" else "fine",
                              "words": "So be it."}
    if "ask_help" in available and rng.random() < 0.15:
        return "ask_help", {"text": "Every pair of hands counts today."}
    if "organize" in available and rng.random() < 0.08 and L["projects"]:
        return "organize", {"task": L["projects"][0]["name"], "people": str(max(2, F.settled(city) // 3))}
    if "appoint" in available and not L["officers"].get("builder") and rng.random() < 0.05:
        c = city.citizens
        import numpy as np
        pool = np.where(c.active())[0]
        if len(pool):
            return "appoint", {"handle": c.handles[int(rng.choice(pool.tolist()))], "title": "foreman"}
    if "plan" in available and (not L["projects"] or (len(L["projects"]) < 2 and rng.random() < 0.1)):
        idea = _next_idea(world)
        if idea:
            return "plan", {"idea": idea, "place": "the field"}
    if L["projects"]:
        p = L["projects"][0]
        short = F.short_of(world, p)
        short.pop("iron", None)
        if not short:
            return ("build", {"project": p["name"]}) if loc == p["place"] else ("walk", {"place": F.place_of(world, p["place"])})
        m = max(short, key=short.get)
        where = F.where_to_get(world, m)
        if where:
            return (("gather", {"material": m, "how": "steadily"}) if loc in where
                    else ("walk", {"place": F.place_of(world, rng.choice(where))}))
    if rng.random() < 0.5:
        res = F.places(world).get(loc, {}).get("resources", [])
        if res:
            return "gather", {"material": rng.choice(res), "how": "for the stores"}
    return "walk", {"place": F.place_of(world, rng.choice(list(F.places(world))))}


def _next_idea(world):
    """Tests only: something sensible to build next (the real king has his own ideas)."""
    city, L = world.city, F.land(world)
    names = {b["name"].lower() for b in L["buildings"]} | {p["name"].lower() for p in L["projects"]}
    tried = {p.lower() for p in L.get("tried", [])}
    if city.day == 0 and F.settled(city) == 0:
        first = next((i for i in TEST_FIRST if i not in tried), None)
        if first:
            L.setdefault("tried", []).append(first)
            return first
    expected = 2                                   # newcomers arrive any time
    gap = expected + F.tents(city) - F.free_beds(city)
    if gap > 0 or not any(b["kind"] == "housing" for b in L["buildings"]):
        cap = F.ORDER.index(F.max_scale(world))
        fits = [(s, n, i) for s, n, i in TEST_LADDER if F.ORDER.index(s) <= cap]
        idea = next((i for s, n, i in fits if max(1, gap) <= n), fits[-1][2])     # the biggest he can manage
        open_ = sum(p.get("capacity", 0) for p in L["projects"])
        if any(p["idea"] == idea for p in L["projects"]) or (open_ and open_ >= gap):
            return None                          # already building enough
        return idea
    for idea in TEST_OTHERS:
        if not _norm_in(idea, names):
            return idea
    return None


def _norm_in(idea, names):
    return any(n and (n in idea.lower() or idea.lower() in n) for n in names)
