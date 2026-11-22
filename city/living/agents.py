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
from . import tools, warcamp


def persona(who):
    f = CONTENT / ("ruler.yaml" if who == "king" else "warlord.yaml")
    return yaml.safe_load(f.read_text()) if f.exists() else {"name": who.title()}


def _ago(world, m):
    mins = world.clock - m["clock"]
    return f"{mins // 60}h ago" if mins >= 60 else "just now"


def perceive(world, who):
    """What this mind knows right now, as plain text."""
    city, me = world.city, world.agent(who)
    loc = me.get("location", "camp")
    lines = [f"It is {world.now_str()}. You are in {loc if loc.startswith('the ') else 'the ' + loc}."]
    if who == "king":
        lines.append(f"Kingdom: {city.population()} subjects, loyalty {city.approval():.0%}, "
                     f"treasury {city.treasury:,.0f} gold, tax {city.tax_rate:.0%}, "
                     f"defense {city.quality['defense']:.2f}, food {city.quality['food']:.2f}. "
                     f"Reckoning (the vote on your crown) in {city.cfg['season_days'] - (city.day % city.cfg['season_days'])} days.")
        lines.append("Holds: " + "; ".join(f"{w['name']} (pop {w['pop']}, mood {(w['mood'] or 0.5):.2f}, lord "
                                            f"{'@' + city.citizens.handles[w['councilor']] if w.get('councilor') is not None else 'none'})"
                                            for w in city.ward_stats()))
        if me.get("location", "").startswith("tavern in "):
            hold = me["location"][len("tavern in "):]
            heard = [m for m in world.moments_since(world.clock - 24 * 60) if m["who"].startswith("@")
                     and hold in m.get("hold", "")][-4:]
            lines.append(f"In disguise, you overhear the people of {hold}: " +
                         (" / ".join(m["text"] for m in heard) if heard else "grumbling about bread prices."))
        letters = [l for l in me.get("letters", []) if l["day"] >= city.day - 1]
        if letters:
            lines.append("Letters: " + " / ".join(f"from {l['from']}: \"{l['text']}\"" for l in letters[-2:]))
        if me.get("intel"):
            lines.append("Your spies' reports: " + json.dumps(me["intel"]))
        comments = city.living.get("loud_comments", [])[-5:]
        if comments:
            lines.append("What subjects are saying in the comments: " + " / ".join(comments))
        events = [f"{a['title']} ({a['days_left']} days left)" for a in city.events]
        if events:
            lines.append("Happening now: " + "; ".join(events))
        from ..sim import available_projects
        projs = [f"{p['id']} ({p['cost_pc'] * city.population():,.0f} gold)" for p in available_projects(city)][:6]
        if projs:
            lines.append("You could build: " + ", ".join(projs))
    else:
        c = warcamp.camp(city)
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
            pick = rng.choices(["scout", "recruit", "hunt", "taunt", "feast"], [3, 4, 3, 1, 1])[0]
            if pick == "taunt":
                return "taunt", {"text": rng.choice(["Your walls are made of bread, little king.",
                                                     "I am coming for your chair.",
                                                     "Your soldiers fight like your poets."])}
            return pick, {"hold": rng.choice(holds)}
        # the king
        raid = any(a["id"] in ("warlord_raid", "warlord_horde") for a in city.events)
        open_holds = [w["name"] for w in city.wards if w.get("garrison_until", -1) < city.day]
        if raid and "garrison" in available and open_holds and rng.random() < 0.3:
            return "garrison", {"hold": rng.choice(open_holds)}
        r = rng.random()
        if r < 0.12 and "spy" in available:
            return "spy", {"target": "north"}
        if r < 0.22:
            lords = [city.citizens.handles[w["councilor"]] for w in city.wards if w.get("councilor") is not None]
            if lords:
                return "summon", {"handle": rng.choice(lords), "why": "to hear the news from their hold"}
        if r < 0.3 and city.living.get("last_decree_day", -9) < city.day - 3:
            return "decree", rng.choice(RULE_DECREES)
        if r < 0.42:
            return "proclaim", {"text": rng.choice(["Emberfall will stand forever!", "Taxes are a privilege.",
                                                    "Whoever mocks the king will scrub the stables."])}
        if r < 0.5 and city.treasury > 20 * city.population():
            return "spend", {"what": f"feast {rng.choice([w['name'] for w in city.wards])}"}
        if r < 0.75:
            return "go", {"place": rng.choice(tools.KING_PLACES + [f"tavern in {w['name']}" for w in city.wards])}
        return "rest", {}

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
        role = ("the king of Emberfall. Your subjects are real people who follow the kingdom online"
                if who == "king" else
                f"the warlord of {p.get('camp', 'the war camp')} in the frozen north. Your enemy is King Aldric "
                "of Emberfall, a soft southern kingdom whose people are real followers online")
        system = (f"You are {p['name']}, {role}. {p.get('personality', '')}\n"
                  f"Ambition: {p.get('ambition', '')} Flaw: {p.get('flaw', '')} Voice: {p.get('voice', '')}.\n"
                  "You live in this world in real time. Every so often you choose ONE thing to do next.\n"
                  f"Your tools:\n{tool_lines}\nArguments:\n{arg_lines}\n"
                  "Reply with JSON: thought (one private sentence, in character), tool, args (only what that tool "
                  "needs), new_goal (a new personal goal if your situation changed, else \"\"). Be bold, be in "
                  "character, don't repeat yourself, and remember: the people watching love drama.")
        try:
            out = self.llm.json(system, perceive(world, who), schema(names, argnames), max_tokens=350)
            tool = out.get("tool")
            if tool not in available:
                raise ValueError(tool)
            if out.get("new_goal"):
                goals = p.setdefault("goals", [])
                goals.append(str(out["new_goal"])[:120])
                del goals[:-3]
            p["last_thought"] = str(out.get("thought", ""))[:200]
            return tool, {k: v for k, v in (out.get("args") or {}).items() if v not in (None, "")}
        except Exception as e:
            world.stats["fallbacks"] = world.stats.get("fallbacks", 0) + 1
            world.stats["last_fallback"] = f"{who}: {type(e).__name__}: {e}"[:200]
            return self.fallback.choose(world, who, available)
