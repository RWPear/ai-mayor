"""The minds: King Aldric (protagonist) and the warlord (antagonist).

Each time a mind wakes up it gets a short picture of its world - where it is,
what it knows, what just happened, its goals and recent memories - and picks
ONE tool. It can also set itself a new goal. That's the whole loop; everything
interesting comes from two characters with opposite wants sharing one world,
plus a crowd that keeps changing it.

RuleBrain picks tools with simple heuristics (fast, free - for tests).
LLMBrain asks the model, and falls back to the rules if the answer is unusable.
"""
import json
from pathlib import Path

import yaml

from ..config import CONTENT
from ..roles import JOB_NAMES
from . import life, tools, warcamp
from . import town as T


def persona(who):
    f = CONTENT / ("ruler.yaml" if who == "king" else "warlord.yaml")
    return yaml.safe_load(f.read_text()) if f.exists() else {"name": who.title()}


def _ago(world, m):
    mins = world.clock - m["clock"]
    return f"{mins // 60}h ago" if mins >= 60 else "just now"


def king_view(world, me):
    """Where he is and what he sees there, how he feels, what's on his plate, the kingdom, the war."""
    from ..sim import available_projects
    city, c = world.city, world.city.citizens
    t = city.living["town"]
    loc = me.get("location", "throne_room")
    lines = [f"It is {world.now_str()}, {city.living.get('weather', 'a mild day')}. You are in "
             f"{T.place_of(loc, t)}. You see: {T.describe(t, loc)}.",
             f"Emberfall: {T.summary(world)}."]
    court = life.court()
    here = world.court_here()
    if here:
        lines.append("Here with you: " + ", ".join(court[k]["name"] for k in here) + ".")
    people = world.people_here(loc)
    if people:
        lines.append("Subjects around you: " + ", ".join(
            f"@{c.handles[i]} ({JOB_NAMES[int(c.job[i])]}, {'grumpy' if c.mood[i] < 0.45 else 'cheerful'})"
            for i in people) + ".")
    if loc == "tavern":
        heard = [m["text"] for m in world.moments_since(world.clock - 24 * 60) if m["who"].startswith("@")][-3:]
        lines.append("In disguise, you overhear: " + (" / ".join(heard) if heard else "grumbling about bread prices."))
    works = t["works"]
    if works:
        lines.append("Being built: " + "; ".join(f"{w['name']} at {T.PLACES[w['place']]['name']} "
                                                f"({w['progress']:.0%})" for w in works))
    outcomes = me.get("life", {}).get("outcomes", [])[-3:]
    if outcomes:
        lines.append("How your projects turned out: " + "; ".join(f"{o['name']}: {o['result']}" for o in outcomes))
    ruins = [T.ROOMS[r]["name"] for r in T.ruins(t)]
    if ruins:
        lines.append("Parts of your castle are ruins: " + ", ".join(ruins) + ".")
    lines.append(f"Project costs right now: small {T.cost('small', city.population()):,.0f} gold, medium "
                 f"{T.cost('medium', city.population()):,.0f}, large {T.cost('large', city.population()):,.0f}.")
    docket = city.living.get("docket", [])
    if docket:
        if loc == "throne_room":
            lines.append("Waiting at court: " + " / ".join(f"[{k['id']}] {k['text']}" for k in docket[:3]))
        else:
            lines.append(f"{len(docket)} people are waiting for you at court (the throne room).")
    lines.append(life.feeling(me))
    me_now = life.who_am_i(me)
    lines.append(f"Who you are so far ({'your own words' if me_now else 'you have not figured that out yet'})"
                 + (f": {me_now}." if me_now else "."))
    t_ = life.tried(me)
    if t_:
        lines.append(f"Things you've spent your time on: {t_}.")
    lf = me.get("life", {})
    if lf.get("knowledge"):
        lines.append("Things you've learned: " + "; ".join(lf["knowledge"][-4:]) + ".")
    if lf.get("inventory"):
        lines.append("You have: " + ", ".join(lf["inventory"][-5:]) + ".")
    lines.append(f"Kingdom: {city.population()} subjects, loyalty {city.approval():.0%}, treasury "
                 f"{city.treasury:,.0f} gold, tax {city.tax_rate:.0%}. The Reckoning (the vote on your crown) is in "
                 f"{city.cfg['season_days'] - (city.day % city.cfg['season_days'])} days.")
    letters = [x for x in me.get("letters", []) if x["day"] >= city.day - 1]
    if letters:
        lines.append("Letters: " + " / ".join(f"from {x['from']}: \"{x['text']}\"" for x in letters[-2:]))
    if me.get("intel"):
        lines.append("Your spies' reports: " + json.dumps(me["intel"]))
    comments = city.living.get("loud_comments", [])[-4:]
    if comments:
        lines.append("What subjects are saying: " + " / ".join(comments))
    events = [f"{a['title']} ({a['days_left']} days left)" for a in city.events]
    if events:
        lines.append("Happening now: " + "; ".join(events))
    projs = [f"{p['id']} ({p['cost_pc'] * city.population():,.0f} gold)" for p in available_projects(city)][:5]
    if projs:
        lines.append("Kingdom building projects (spend): " + ", ".join(projs))
    return lines


def perceive(world, who):
    """What this mind knows right now, as plain text."""
    city, me = world.city, world.agent(who)
    if who == "king":
        lines = king_view(world, me)
    else:
        c = warcamp.camp(city)
        lines = [f"It is {world.now_str()}. You are in {c['name']}."]
        lines.append(f"Your camp: {c['warriors']} warriors, {c['food']:.0f} food (they eat "
                     f"{c['warriors'] * 0.5:.0f} a day), morale {c['morale']:.2f}. Raids won {c['raids_won']}, "
                     f"lost {c['raids_lost']}." + (" A raid is underway right now." if c.get("active_raid") else ""))
        lines.append(f"Emberfall: {city.population()} people, its walls/guards at {city.quality['defense']:.2f}. "
                     "Holds: " + ", ".join(w["name"] for w in city.wards))
        if c["intel"]:
            lines.append("What your scouts found: " + json.dumps(c["intel"]))
        news = [m["text"] for m in world.moments_since(world.clock - 24 * 60)
                if m["public"] and m["who"] in ("king", "world")][-3:]
        if news:
            lines.append("News from the south: " + " / ".join(news))
    mine = [m for m in world.moments_since(world.clock - 36 * 60) if m["who"] == who][-6:]
    if mine:
        lines.append("What you did recently: " + " / ".join(f"({_ago(world, m)}) {m['text']}" for m in mine))
    if me.get("goals"):
        lines.append("Your goals: " + "; ".join(me["goals"]))
    return "\n".join(lines)


def schema(names, argnames):
    return {"type": "object", "properties": {
        "thought": {"type": "string"},
        "tool": {"type": "string", "enum": names},
        "args": {"type": "object", "properties": {a: {"type": "string"} for a in argnames}},
        "new_goal": {"type": "string"}},
        "required": ["thought", "tool", "args", "new_goal"]}


TEST_IDEAS = [("a new roof for this place", "small", "commoners"), ("stone paving", "medium", "roads"),
              ("a proper wall", "large", "walls"), ("a little garden", "small", "festival")]

RULE_DECREES = [
    {"question": "Should the king hold a grand feast in his own honor?", "a_word": "FEAST",
     "a_text": "The feast is on. The king is delighted.", "a_flavor": "vanity", "b_word": "BREAD",
     "b_text": "The gold goes to bread instead.", "b_flavor": "food", "back": "FEAST"},
    {"question": "Every subject must train with the army once a week. Agreed?", "a_word": "DRILL",
     "a_text": "Emberfall drills. The walls have never looked so busy.", "a_flavor": "harsh", "b_word": "REFUSE",
     "b_text": "The people refused. The army sulks.", "b_flavor": "commoners", "back": "DRILL"},
    {"question": "Tax the guilds to pay for new roads?", "a_word": "ROADS", "a_text": "New roads it is.",
     "a_flavor": "roads", "b_word": "NOTAX", "b_text": "The guilds keep their gold.", "b_flavor": "guilds"},
]


class RuleBrain:
    """Plausible behaviour from simple rules, so the living world can be tested in seconds."""
    name = "rules"

    def choose(self, world, who, available):
        city, rng = world.city, world.city.rng
        me = world.agent(who)
        if who == "warlord":
            c = warcamp.camp(city)
            holds = [w["name"] for w in city.wards]
            if c["food"] < c["warriors"] * 1.2:
                if "raid" in available and not c.get("active_raid") and rng.random() < 0.6 and c["warriors"] >= 25:
                    return "raid", {"hold": self._weakest(city, c, holds), "warriors": str(int(c["warriors"] * 0.6))}
                return "hunt", {}
            busy = c.get("active_raid") or any(a["id"] in ("warlord_raid", "warlord_horde") for a in city.events)
            if "march" in available and not busy and rng.random() < 0.15:
                return "march", {}
            if "raid" in available and not busy and c["warriors"] >= 45 and rng.random() < 0.12:
                return "raid", {"hold": self._weakest(city, c, holds), "warriors": str(int(c["warriors"] * 0.6))}
            if "sabotage" in available and rng.random() < 0.08:
                return "sabotage", {"hold": rng.choice(holds)}
            fresh = [h for h in holds if c["intel"].get(h, {}).get("day", -9) < city.day - 2]
            if not fresh and rng.random() < 0.7:
                fresh = []
            food_rich = c["food"] > c["warriors"] * 6
            pick = rng.choices(["scout", "recruit", "hunt", "taunt", "feast"],
                               [3 if fresh else 0.2, 4, 0.5 if food_rich else 3, 1, 2 if food_rich else 1])[0]
            if pick == "scout" and fresh:
                return "scout", {"hold": rng.choice(fresh)}
            if pick == "taunt":
                return "taunt", {"text": rng.choice(["Your walls are made of bread, little king.",
                                                     "I am coming for your chair.",
                                                     "Your soldiers fight like your poets."])}
            return pick, {"hold": rng.choice(holds)}
        return self._king(world, me, available)

    def _king(self, world, me, available):
        """Test-only instincts: needs first, then whatever's in front of him, then being king.
        (The real king has no list of ideas - these few exist so the rule-based tests have something to do.)"""
        city, rng = world.city, world.city.rng
        t = city.living["town"]
        loc = me.get("location")
        n = me.get("life", {}).get("needs", {})
        low = min(n, key=n.get) if n else None
        if low and n[low] < 0.3:
            if low == "hunger":
                return ("do", {"what": "eat something hot"}) if loc in ("kitchens", "great_hall", "tavern") \
                    else ("walk", {"place": "kitchens"})
            if low == "energy":
                return ("do", {"what": "take a nap"}) if loc == "bedchamber" else ("walk", {"place": "bedchamber"})
            if low == "company":
                who = rng.choice(world.court_here() or ["steward"])
                if who not in world.court_here() and loc != "throne_room":
                    return "walk", {"place": "throne room"}
                return "talk", {"person": who, "text": rng.choice(["What do people say about me?",
                                                                    "Tell me something true.", "Well?"])}
            if low == "fun":
                return "do", {"what": rng.choice(["paint the view", "whittle a little boat", "sing to himself",
                                                  "go fishing", "read an old book", "go for a run"])}
        raid = any(a["id"] in ("warlord_raid", "warlord_horde") for a in city.events)
        open_holds = [w["name"] for w in city.wards if w.get("garrison_until", -1) < city.day]
        if raid and "garrison" in available and open_holds and rng.random() < 0.4:
            return "garrison", {"hold": rng.choice(open_holds)}
        if loc == "throne_room" and city.living.get("docket") and rng.random() < 0.7:
            k = city.living["docket"][0]
            verdict = ("jail" if k["kind"] == "crime" and rng.random() < 0.6 else
                       rng.choice(["grant", "deny", "reward"]) if k["kind"] != "crime" else "pardon")
            return "hold_court", {"case": k["id"], "verdict": verdict, "words": "So it is decreed."}
        if any(w["place"] == loc for w in t["works"]) and rng.random() < 0.5:
            return "work_on", {}
        busy_here = any(w["place"] == loc for w in t["works"])
        if not busy_here and rng.random() < 0.12 and city.treasury > 2 * T.cost("medium", city.population()):
            idea = rng.choice(TEST_IDEAS)
            return "start_work", {"name": idea[0], "size": idea[1], "purpose": idea[2]}
        r = rng.random()
        if r < 0.08 and "spy" in available:
            return "spy", {"target": "north"}
        if r < 0.15 and city.living.get("last_decree_day", -9) < city.day - 3:
            return "decree", rng.choice(RULE_DECREES)
        if r < 0.25:
            people = world.people_here(loc, 1)
            if people:
                return "talk", {"person": "@" + city.citizens.handles[people[0]], "text": "How goes it?"}
        if r < 0.3 and "feast" in available and city.treasury > 25 * city.population():
            return "feast", {}
        if city.living.get("docket") and loc != "throne_room" and r < 0.45:
            return "walk", {"place": "throne room"}
        return "walk", {"place": T.PLACES[rng.choice(list(T.PLACES))]["name"]}

    @staticmethod
    def _weakest(city, c, holds):
        intel = c["intel"]
        known = [h for h in holds if h in intel and not intel[h].get("garrison")]
        return min(known, key=lambda h: intel[h]["raid_strength_with_all_warriors"]) if known else city.rng.choice(holds)


class LLMBrain:
    name = "llm"

    def __init__(self, llm):
        self.llm = llm
        self.fallback = RuleBrain()

    def choose(self, world, who, available):
        p = world.agent(who)
        names = list(available)
        argnames = sorted({a for _, _, args in available.values() for a in args})
        tool_lines = "\n".join(f"- {n}({', '.join(args)}): {desc}" for n, (_, desc, args) in available.items())
        arg_lines = "\n".join(f"  {a}: {tools.ARG[a]}" for a in argnames)
        if who == "king":
            me_now = life.who_am_i(p)
            identity = (f"You are {p['name']}, the new king of Emberfall. Your subjects are real people who follow the "
                        f"kingdom online. Nobody has told you who to be. Your one goal: {p.get('goal', '')}\n"
                        "Everything else - what you like, what you care about, how you rule, what you do with your "
                        "days, what you think should change - is yours to discover. You're a person, not a legend: "
                        "you get hungry, tired, lonely and bored, and your ideas can fail.\n"
                        + (f"Who you've become so far, in your own words: {me_now}.\n" if me_now else ""))
        else:
            me_now = life.who_am_i(p)
            identity = (f"You are {p['name']}, a warlord who has just made camp ({p.get('camp', 'the war camp')}) in the "
                        "frozen hills north of Emberfall, a kingdom whose people are real followers online. Nobody has "
                        f"told you who to be. Your one goal: {p.get('goal', '')}\n"
                        + (f"Who you've become so far, in your own words: {me_now}.\n" if me_now else ""))
        system = (identity +
                  "You live in this world in real time. Every so often you choose ONE thing to do next.\n"
                  f"Your tools:\n{tool_lines}\nArguments:\n{arg_lines}\n"
                  "Reply with JSON: thought (one private sentence, in character), tool, args (only what that tool "
                  "needs), new_goal (a new personal goal if your situation changed, else \"\"). Act like yourself "
                  "and don't repeat yourself.")
        try:
            out = self.llm.json(system, perceive(world, who), schema(names, argnames), max_tokens=350)
            tool = out.get("tool")
            if tool not in available:
                raise ValueError(tool)
            goal = str(out.get("new_goal") or "").strip()[:120]
            goals = p.setdefault("goals", [])
            if goal and goal.lower() not in (g.lower() for g in goals):
                goals.append(goal)
                del goals[:-3]
            p["last_thought"] = str(out.get("thought", ""))[:200]
            return tool, {k: v for k, v in (out.get("args") or {}).items() if v not in (None, "")}
        except Exception as e:
            world.stats["fallbacks"] = world.stats.get("fallbacks", 0) + 1
            world.stats["last_fallback"] = f"{who}: {type(e).__name__}: {e}"[:200]
            return self.fallback.choose(world, who, available)
