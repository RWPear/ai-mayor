"""Two kinds of effects:

1. Command effects - what a comment does to the commenter's citizen (work,
   grumble, trade, train...). Packs give these comment words; new effects are
   new functions here (and get tested in the test kingdom before going live).
2. Kingdom effects - the small declarative dictionaries in content/*.yaml used
   by events, the king's options and projects (e.g. {service.food: 0.1, mood.commoners: -0.03}).
   "hold" and "ward" mean the same thing in effect keys (mood.hold == mood.ward).
"""
import numpy as np

from .citizens import LEFT
from .model import SERVICES
from .roles import FACTIONS


class DayContext:
    """Per-day scratch space: who did what today, plus temporary modifiers."""

    def __init__(self, city):
        n = len(city.citizens)
        self.n = n
        self.flags = {k: np.zeros(n, bool) for k in
                      ("work", "protest", "shop", "volunteer", "donate", "strike", "support", "oppose",
                       "train")}
        self.mood_offset = np.zeros(n, np.float32)   # added to today's mood target
        self.economy_offset = 0.0
        self.status_requests = []                    # citizen indexes who asked for their card
        self.event_votes = {}                        # event id -> {"help": n, "hinder": n, "choices": {word: n}}
        self.helpers = {}                            # event id -> citizen indexes who helped (for battle deeds)
        self.word = None                             # the comment word being applied right now
        self.actions = {}                            # username -> comment word, for today's post
        self.election_votes = {"keep": 0, "recall": 0}
        self.notes = []


# ---------------------------------------------------------------------------- command effects
def _flag(name, counter=None):
    def fn(city, idx, ctx, arg=None):
        ctx.flags[name][idx] = True
        city.citizens.counts[counter or name][idx] += 1
    return fn


def leave(city, idx, ctx, arg=None):
    c = city.citizens
    c.status[idx] = LEFT
    for i in idx:
        c.log(i, city.day, "moved out of the city")


def status(city, idx, ctx, arg=None):
    ctx.status_requests.extend(int(i) for i in idx)


def _votes(ctx, arg):
    return ctx.event_votes.setdefault(arg or "*", {"help": 0, "hinder": 0, "choices": {}})


def event_help(city, idx, ctx, arg=None):
    """Counts toward the event. If the event has `champions: army`, that faction's help counts extra."""
    from .storyteller import catalog
    n = float(len(idx))
    champ = (catalog().get(arg) or {}).get("champions")
    if champ in FACTIONS:
        n += (city.cfg["champion_weight"] - 1) * float((city.citizens.faction[idx] == FACTIONS.index(champ)).sum())
    _votes(ctx, arg)["help"] += n
    ctx.helpers.setdefault(arg or "*", []).extend(int(i) for i in idx)


def event_hinder(city, idx, ctx, arg=None):
    _votes(ctx, arg)["hinder"] += len(idx)


def event_choice(city, idx, ctx, arg=None):
    """A decree vote: the comment word itself is the vote (WALLS vs GRANARY)."""
    ch = _votes(ctx, arg)["choices"]
    ch[ctx.word] = ch.get(ctx.word, 0) + len(idx)


def vote_keep(city, idx, ctx, arg=None):
    ctx.election_votes["keep"] += len(idx)
    ctx.flags["support"][idx] = True
    city.citizens.counts["support"][idx] += 1


def vote_recall(city, idx, ctx, arg=None):
    ctx.election_votes["recall"] += len(idx)
    ctx.flags["oppose"][idx] = True
    city.citizens.counts["oppose"][idx] += 1


COMMAND_EFFECTS = {
    "work": _flag("work"),
    "protest": _flag("protest"),
    "shop": _flag("shop"),
    "volunteer": _flag("volunteer"),
    "train": _flag("train"),
    "donate": _flag("donate"),
    "strike": _flag("strike", "protest"),
    "support": _flag("support"),
    "oppose": _flag("oppose"),
    "leave": leave,
    "status": status,
    "event.help": event_help,
    "event.hinder": event_hinder,
    "event.choice": event_choice,
    "vote.keep": vote_keep,
    "vote.recall": vote_recall,
}


# ---------------------------------------------------------------------------- city effects
def _members(city, target, ward):
    """Boolean mask of active citizens a key applies to: all / a faction / the event's ward."""
    c = city.citizens
    a = c.active()
    if target in (None, "", "all"):
        return a
    if target in ("ward", "hold"):
        return a & (c.ward == ward) if ward is not None else a
    if target in FACTIONS:
        return a & (c.faction == FACTIONS.index(target))
    return np.zeros(len(c), bool)


def apply(city, effects, ward=None, ctx=None, daily=False):
    """Applies a dict like {service.food: 0.1, mood.commoners: -0.03, treasury_pc: -4}.
    daily=True means it's an ongoing 'while' effect: mood/economy become today's offsets."""
    c = city.citizens
    pop = max(1, city.population())
    for key, val in (effects or {}).items():
        if key in ("text", "next", "progress") or val is None:
            continue
        head, _, target = key.partition(".")
        if head == "treasury_pc":
            city.treasury += float(val) * pop
        elif head == "treasury":
            city.treasury += float(val)
        elif head == "economy":
            if daily and ctx is not None:
                ctx.economy_offset += float(val)
            else:
                city.economy = float(np.clip(city.economy + float(val), 0.4, 1.8))
        elif head == "service" and target in SERVICES:
            city.quality[target] = float(np.clip(city.quality[target] + float(val), 0.0, 1.5))
        elif head == "mood":
            m = _members(city, target, ward)
            if daily and ctx is not None:
                ctx.mood_offset[m] += float(val)
            else:
                c.mood[m] = np.clip(c.mood[m] + float(val), 0, 1)
        elif head == "loyalty":
            m = _members(city, target, ward)
            c.loyalty[m] = np.clip(c.loyalty[m] + float(val), 0, 1)
        elif head == "wealth_pc":
            m = _members(city, target, ward)
            c.wealth[m] += float(val)
        elif head == "depose" and ward is not None and val:
            city.wards[ward]["councilor"] = None   # the hold's lord loses the title
        elif head == "unrest" and ward is not None:
            w = city.wards[ward]
            w["unrest"] = float(np.clip(w["unrest"] + float(val), 0, 1))
