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
from . import life, tools, warcamp


def persona(who):
    f = CONTENT / ("ruler.yaml" if who == "king" else "warlord.yaml")
    return yaml.safe_load(f.read_text()) if f.exists() else {"name": who.title()}


def _ago(world, m):
    mins = world.clock - m["clock"]
    return f"{mins // 60}h ago" if mins >= 60 else "just now"


def king_sections(world, me):
    """Everything the king could know right now, in sections - so each decision only sees what it needs."""
    from . import frontier_tools
    return frontier_tools.sections(world, me)


def king_view(world, me):
    S = king_sections(world, me)
    return [line for k in ("here", "me", "land", "people", "court", "building", "kingdom", "north")
            for line in S.get(k, [])]


def focus_table(world):
    from . import frontier_tools
    return frontier_tools.FOCUS


def foci(world, available):
    """The focus choices that make sense right now (each needs at least one usable tool)."""
    from . import frontier_tools
    return frontier_tools.foci(world, available)


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
        from . import frontier_tools
        return frontier_tools.rule_king(world, me, available)

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

    @staticmethod
    def _identity(p, who):
        me_now = life.who_am_i(p)
        if who == "king":
            from . import frontier_tools
            return frontier_tools.identity(p)
        return (f"You are {p['name']}, a warlord who has just made camp ({p.get('camp', 'the war camp')}) in the "
                "frozen hills north of Emberfall, a kingdom whose people are real followers online. Nobody has "
                f"told you who to be. Your one goal: {p.get('goal', '')}\n"
                + (f"Who you've become so far, in your own words: {me_now}.\n" if me_now else ""))

    def _keep_goal(self, p, out):
        goal = str(out.get("new_goal") or "").strip()[:120]
        goals = p.setdefault("goals", [])
        if goal and goal.lower() not in (g.lower() for g in goals):
            goals.append(goal)
            del goals[:-3]

    def _two_step(self, world, p, available):
        """1) what to focus on, seeing the big picture; 2) exactly what to do, seeing only what's relevant."""
        S = king_sections(world, p)
        options = foci(world, available)
        table = focus_table(world)
        from . import frontier
        p["_crowned"] = frontier.land(world).get("crowned")
        overview = [*S["here"], *S["me"][:2], *S.get("land", [])[:1], *S["kingdom"]]
        if S["court"]:
            overview.append(S["court"][0].split(":")[0] + ".")
        if S["north"]:
            overview += S["north"][:1]
        if S["building"][:1]:
            overview.append(S["building"][0])
        if S["people"]:
            overview.append(S["people"][0])
        if p.get("goals"):
            overview.append("Your own goals: " + "; ".join(p["goals"]))
        from . import flavor                   # what he's been doing (so he doesn't loop), and something to notice
        mine = [d for d in world.decisions if d["who"] == "king"][-6:]
        if mine:
            overview.append("Lately you: " + "; ".join(
                d["tool"] + (f" ({next(iter(d['args'].values()))[:50]})" if d["args"] else "") for d in mine) + ".")
        if world.city.rng.random() < 0.6:
            p["_noticed"] = flavor.notice(world.city.rng, p.get("location"))
            overview.append("You notice: " + p["_noticed"])
        else:
            p["_noticed"] = ""
        schema1 = {"type": "object", "properties": {
            "thought": {"type": "string"}, "focus": {"type": "string", "enum": list(options)},
            "intention": {"type": "string"}, "new_goal": {"type": "string"}},
            "required": ["thought", "focus", "intention", "new_goal"]}
        menu = "\n".join(f"- {k}: {d}" for k, (d, _) in options.items())
        one = self.llm.json(self._identity(p, "king") + "You live in this world in real time. What do you want to "
                            "focus on next?\n" + menu + "\nReply with JSON: thought (one private sentence), focus, "
                            "intention (what you mean to do, in your own words), new_goal (a new personal goal if "
                            "your situation changed, else \"\").", "\n".join(overview), schema1, max_tokens=400,
                            temperature=1.0)
        focus = one.get("focus")
        if focus not in options:
            raise ValueError(f"focus {focus}")
        self._keep_goal(p, one)
        p["last_thought"] = str(one.get("thought", ""))[:200]
        world.spend_calls(1)
        names = options[focus][1]
        argnames = sorted({a for n in names for a in available[n][2]})
        detail = [line for k in table[focus][2] for line in S.get(k, [])]
        if p.get("_noticed"):
            detail.append("You noticed: " + p["_noticed"])
        tool_lines = "\n".join(f"- {n}({', '.join(available[n][2])}): {available[n][1]}" for n in names)
        arg_lines = "\n".join(f"  {a}: {tools.ARG[a]}" for a in argnames)
        two = self.llm.json(self._identity(p, "king") + f"You've decided to focus on: {options[focus][0]}. You "
                            f"intend: {one.get('intention', '')}\nNow decide exactly what you do. Your options:\n"
                            f"{tool_lines}\nArguments:\n{arg_lines}\nReply with JSON: tool, args (only what that "
                            "tool needs - be specific and concrete, in your own words). Don't repeat yourself.",
                            "\n".join(detail), {"type": "object", "properties": {
                                "tool": {"type": "string", "enum": names},
                                "args": {"type": "object", "properties": {a: {"type": "string"} for a in argnames}}},
                                "required": ["tool", "args"]}, max_tokens=450, temperature=0.95)
        tool = two.get("tool")
        if tool not in available:
            raise ValueError(f"tool {tool}")
        world.stats[f"focus.{focus}"] = world.stats.get(f"focus.{focus}", 0) + 1
        return tool, {k: v for k, v in (two.get("args") or {}).items() if v not in (None, "")}

    def choose(self, world, who, available):
        p = world.agent(who)
        if who == "king":
            from . import frontier
            p["_crowned"] = frontier.land(world).get("crowned")
        if who == "king" and world.can_think(2):
            try:
                return self._two_step(world, p, available)
            except Exception as e:
                world.stats["fallbacks"] = world.stats.get("fallbacks", 0) + 1
                world.stats["last_fallback"] = f"king: {type(e).__name__}: {e}"[:200]
                return self.fallback.choose(world, who, available)
        names = list(available)
        argnames = sorted({a for _, _, args in available.values() for a in args})
        tool_lines = "\n".join(f"- {n}({', '.join(args)}): {desc}" for n, (_, desc, args) in available.items())
        arg_lines = "\n".join(f"  {a}: {tools.ARG[a]}" for a in argnames)
        identity = self._identity(p, who)
        system = (identity +
                  "You live in this world in real time. Every so often you choose ONE thing to do next.\n"
                  f"Your tools:\n{tool_lines}\nArguments:\n{arg_lines}\n"
                  "Reply with JSON: thought (one private sentence, in character), tool, args (only what that tool "
                  "needs), new_goal (a new personal goal if your situation changed, else \"\"). Act like yourself "
                  "and don't repeat yourself.")
        try:
            out = self.llm.json(system, perceive(world, who), schema(names, argnames), max_tokens=500)
            tool = out.get("tool")
            if tool not in available:
                raise ValueError(tool)
            self._keep_goal(p, out)
            p["last_thought"] = str(out.get("thought", ""))[:200]
            return tool, {k: v for k, v in (out.get("args") or {}).items() if v not in (None, "")}
        except Exception as e:
            world.stats["fallbacks"] = world.stats.get("fallbacks", 0) + 1
            world.stats["last_fallback"] = f"{who}: {type(e).__name__}: {e}"[:200]
            return self.fallback.choose(world, who, available)
