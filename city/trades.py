"""Open roles: a subject can be anything.

Anyone can take up any life in their own words - "BECOME THIEF", "I become a rat catcher", "I'm going to be a
fortune teller", "i am a thief!" - and the label is theirs, word for word. Underneath, every role is mapped
(once, then remembered for everyone) onto a few mechanics:

  faction   commoners / guilds / army (who they side with)
  income    none / low / normal / high - and whether it's ILLEGAL (illegal pay comes with the guards)
  place     where you'd find them (the tavern, the chapel, King's Street...) - where the king bumps into them
  knack     one thing they're good at, which changes their dice (sneaky, strong, crafty, charming, holy,
            healing, learned, wild)
  skills    crafts they actually know (smithing, brewing, healing...). Try one you don't know and it goes
            wrong: a thief who sneaks into the smithy to forge a sword burns his hand on the tongs.
  homeless  a situation more than a job: no house (nothing for raiders to burn, nothing worth stealing),
            sleeps at the chapel, and cold nights wear the mood down

Three things you can't just say:
  - earned titles (knight, lord, king, prince...) come from battles or the king, not from a comment
  - silly ones (dragon, god) aren't something a person in Emberfall can be
  - reputation: "I am a thief!" from someone who has never stolen anything gets laughed at. Steal three times
    and the kingdom knows you as a thief - and so do the guards.

The model maps roles it hasn't seen before (one short call); without it, the ROLE_BOOK and some keyword guesses do.
"""
import re

FACTIONS = ("commoners", "guilds", "army")
INCOME = {"none": 0, "low": 60, "normal": 115, "high": 190}
PLACES = ("market_square", "tavern", "kings_street", "smithy", "chapel", "river", "fields", "city_walls",
          "castle_yard", "kitchens", "royal_gardens")
PLACE_LABEL = {"market_square": "the market square", "tavern": "the tavern", "kings_street": "King's Street",
               "smithy": "the smithy", "chapel": "the chapel", "river": "the river", "fields": "the fields",
               "city_walls": "the edge of town", "castle_yard": "the castle yard", "kitchens": "the castle kitchens",
               "royal_gardens": "the royal gardens"}

PLACE_AT = {"market_square": "in the market square", "tavern": "at the tavern", "kings_street": "on King's Street",
            "smithy": "at the smithy", "chapel": "at the chapel", "river": "down by the river",
            "fields": "out in the fields", "city_walls": "at the edge of town", "castle_yard": "in the castle yard",
            "kitchens": "in the castle kitchens", "royal_gardens": "in the royal gardens"}

KNACKS = {
    "sneaky": "quick hands - better odds when you steal, and you're caught less",
    "strong": "strong arms - you're hard to beat in a fight",
    "crafty": "clever hands - your work pays better, and what you make impresses",
    "charming": "a silver tongue - friendships count double, and your cons get caught less",
    "holy": "the chapel's blessing - bless someone (I BLESS @name) and their spirits lift",
    "healing": "healing hands - you can patch up a wounded subject (I HEAL @name)",
    "learned": "letters and learning - your petitions go to the top of the king's list",
    "wild": "at home outdoors - hunting and foraging bring something home",
    "none": "",
}

# skill -> (what trying it looks like, what goes wrong if you don't know how, consequence of the mishap)
# the mishap reads after "they..." or "you..." (second_person() turns their -> your)
# consequence: hurt = wounded a day, caught = a night in the stocks, flop = just embarrassing
SKILLS = {
    "smithing": (r"\b(forge[sd]?|forging|smelt|anvil|hammer(ed|ing)? out|(make|makes|made|craft|crafts|forge)s? "
                 r"(a|an|my|me a|some|the)? ?(new )?(sword|axe|blade|dagger|helm|helmet|armou?r|horseshoe|shield|nails))\b",
                 "grabbed the hot end of the tongs and burned their hand", "hurt"),
    "brewing": (r"\b(brew|brews|brewed|brewing|potion|elixir|poison|tincture|concoct)\w*",
                "mixed the wrong things - the pot went off with a bang and took their eyebrows with it", "hurt"),
    "masonry": (r"\b(lay(ing)? (the )?stones?|mortar|carve (the |a )?stone|chisel|build (a|the) (stone )?wall)\b",
                "stacked the stones with confidence; the wall leaned, then fell on their foot", "hurt"),
    "riding": (r"\b(ride|rides|riding|rode|gallop\w*|mount(ed)? (a|the|my) horse|break in (a|the) horse)\b",
               "got on the wrong way round, and the horse threw them into a ditch in front of half the town", "hurt"),
    "baking": (r"\b(bake|bakes|baked|baking|knead\w*|pastry|pastries|pies?)\b",
               "turned the dough into a brick and nearly set the oven on fire", "flop"),
    "healing": (r"\b(heal|heals|healed|healing|bandage\w*|stitch(es)? up|set (his|her|their|the) bone|cure|treat "
                r"(his|her|their|the) wounds?|tend (to )?(his|her|their|the) wounds?)\b",
                "fumbled the bandages so badly the patient feels worse than before", "flop"),
    "sailing": (r"\b(sail|sails|sailed|sailing|steer (the|a|my) (boat|ship)|row (out|across))\b",
                "capsized within sight of the dock and swam back soaked", "flop"),
    "archery": (r"\b((shoot|shoots|shot|fire|loose)s? (an |my |a )?(arrow|bow)|archery|bullseye|bow and arrow)\b",
                "missed the target, the barn behind it, and hit a merchant's hat", "flop"),
    "tailoring": (r"\b(sew|sews|sewed|sewing|knit\w*|weav(e|es|ing)|tailor (a|my|the))\b",
                  "sewed the sleeve to their own trousers", "flop"),
    "music": (r"\b((play|plays|strum|strums)s? (the |a |my )?(lute|harp|flute|drum|fiddle)|sing (a|the) ballad|"
              r"compose|serenade)\b", "played so badly the crowd threw cabbages - and kept the cabbages coming", "flop"),
    "letters": (r"\b(write|writes|wrote) (a |an |the |my )?(scroll|book|treatise|letter to the king)|scribe|"
                r"(read|study|studies|translate)s? (the |an )?(old |ancient )?(texts?|books?|scrolls?|runes)\b",
                "stared at the page for an hour; the letters wouldn't sit still", "flop"),
    "hunting": (r"\b(hunt|hunts|hunted|hunting|snare|set (a )?traps?|track (a|the) (deer|boar|wolf|stag)|forag\w*)\b",
                "came back with nothing but burrs and wet boots", "flop"),
    "lockpicking": (r"\b(pick (the|a|his|her) lock|picks? locks?|sneak(s|ed)? into|break(s)? into|climb(s|ed)? "
                    r"(in|through) (the |a )?window|slip(s|ped)? past the guards?|burgle)\b",
                    "made as much noise as a cart full of pans - the guards came running", "caught"),
    "magic": (r"\b(cast(s|ing)? (a )?(spell|fireball|curse|hex)|spell|fireball|enchant\w*|summon(s|ed)? (a|the) "
              r"(demon|spirit|dragon)|magic|sorcery|teleport\w*)\b",
              "waved their arms and chanted for a good while. A goat watched, unimpressed. Nothing happened", "flop"),
}
SKILL_LABEL = {"smithing": "the forge", "brewing": "brewing", "masonry": "stonework", "riding": "horses",
               "baking": "baking", "healing": "healing", "sailing": "boats", "archery": "the bow",
               "tailoring": "needle and thread", "music": "music", "letters": "reading and writing",
               "hunting": "hunting", "lockpicking": "locks"}
SKILL_ORDER = ["magic", "smithing", "brewing", "masonry", "riding", "healing", "baking", "sailing", "archery",
               "tailoring", "music", "letters", "hunting", "lockpicking"]
NOBODY = {"magic"}           # there's no real magic in Emberfall - wizards included

JOB_SKILLS = {"blacksmith": ["smithing"], "baker": ["baking"], "innkeeper": ["baking", "brewing"],
              "alchemist": ["brewing", "healing", "letters"], "mason": ["masonry"], "tailor": ["tailoring"],
              "sailor": ["sailing"], "fisher": ["sailing"], "archer": ["archery"],
              "scout": ["archery", "hunting", "riding"], "soldier": ["riding"], "bard": ["music", "letters"],
              "merchant": ["letters"], "shepherd": ["hunting"], "woodcutter": ["hunting"], "miner": ["masonry"],
              "miller": ["baking"], "farmer": ["riding"], "guard": []}
JOB_KNACK = {"soldier": "strong", "miner": "strong", "woodcutter": "strong", "blacksmith": "crafty",
             "mason": "crafty", "tailor": "crafty", "alchemist": "learned", "merchant": "charming",
             "bard": "charming", "innkeeper": "charming", "scout": "wild", "shepherd": "wild", "fisher": "wild"}
KNACK_SKILLS = {"sneaky": ["lockpicking"], "healing": ["healing"], "wild": ["hunting"], "learned": ["letters"]}

# a hand-written start; the model fills in the rest (and everything gets remembered in the kingdom's role book)
_R = lambda fac, inc, place, knack, skills=(), base="farmer", illegal=False, homeless=False: {
    "faction": fac, "income": inc, "place": place, "knack": knack, "skills": list(skills), "base": base,
    "illegal": illegal, "homeless": homeless, "kind": "role"}
ROLE_BOOK = {
    "thief": _R("commoners", "low", "kings_street", "sneaky", ["lockpicking"], "merchant", True),
    "pickpocket": _R("commoners", "low", "market_square", "sneaky", ["lockpicking"], "merchant", True),
    "cutpurse": _R("commoners", "low", "market_square", "sneaky", ["lockpicking"], "merchant", True),
    "burglar": _R("commoners", "low", "kings_street", "sneaky", ["lockpicking"], "merchant", True),
    "smuggler": _R("guilds", "high", "river", "sneaky", ["sailing", "lockpicking"], "sailor", True),
    "pirate": _R("commoners", "normal", "river", "strong", ["sailing"], "sailor", True),
    "bandit": _R("commoners", "low", "fields", "strong", ["riding"], "scout", True),
    "highwayman": _R("commoners", "normal", "fields", "strong", ["riding"], "scout", True),
    "con artist": _R("guilds", "normal", "tavern", "charming", [], "merchant", True),
    "swindler": _R("guilds", "normal", "tavern", "charming", [], "merchant", True),
    "assassin": _R("army", "normal", "tavern", "sneaky", ["lockpicking"], "scout", True),
    "spy": _R("army", "normal", "tavern", "sneaky", ["lockpicking", "letters"], "scout"),
    "beggar": _R("commoners", "none", "chapel", "charming", [], "farmer", homeless=True),
    "homeless": _R("commoners", "none", "chapel", "none", [], "farmer", homeless=True),
    "vagrant": _R("commoners", "none", "chapel", "wild", ["hunting"], "farmer", homeless=True),
    "drifter": _R("commoners", "none", "tavern", "wild", ["hunting"], "farmer", homeless=True),
    "street urchin": _R("commoners", "none", "market_square", "sneaky", ["lockpicking"], "farmer", homeless=True),
    "hermit": _R("commoners", "none", "fields", "wild", ["hunting"], "shepherd", homeless=True),
    "priest": _R("commoners", "low", "chapel", "holy", ["letters", "healing"], "bard"),
    "monk": _R("commoners", "none", "chapel", "holy", ["letters", "brewing"], "bard"),
    "nun": _R("commoners", "none", "chapel", "holy", ["letters", "healing"], "bard"),
    "friar": _R("commoners", "low", "chapel", "holy", ["brewing"], "bard"),
    "cleric": _R("commoners", "low", "chapel", "holy", ["healing", "letters"], "bard"),
    "healer": _R("guilds", "normal", "chapel", "healing", ["healing", "brewing"], "alchemist"),
    "herbalist": _R("guilds", "low", "fields", "healing", ["healing", "brewing", "hunting"], "alchemist"),
    "physician": _R("guilds", "high", "chapel", "healing", ["healing", "letters"], "alchemist"),
    "doctor": _R("guilds", "high", "chapel", "healing", ["healing", "letters"], "alchemist"),
    "barber": _R("guilds", "normal", "kings_street", "healing", ["healing"], "tailor"),
    "witch": _R("commoners", "low", "fields", "healing", ["brewing", "healing"], "alchemist"),
    "wizard": _R("guilds", "low", "tavern", "learned", ["letters", "brewing"], "alchemist"),
    "mage": _R("guilds", "low", "tavern", "learned", ["letters", "brewing"], "alchemist"),
    "sorcerer": _R("guilds", "low", "tavern", "learned", ["letters"], "alchemist"),
    "fortune teller": _R("commoners", "low", "tavern", "charming", [], "bard"),
    "seer": _R("commoners", "low", "chapel", "charming", [], "bard"),
    "rat catcher": _R("commoners", "low", "kings_street", "wild", ["hunting"], "farmer"),
    "hunter": _R("commoners", "normal", "fields", "wild", ["hunting", "archery"], "scout"),
    "trapper": _R("commoners", "normal", "fields", "wild", ["hunting"], "scout"),
    "cook": _R("guilds", "normal", "kitchens", "crafty", ["baking", "brewing"], "baker"),
    "chef": _R("guilds", "normal", "kitchens", "crafty", ["baking", "brewing"], "baker"),
    "brewer": _R("guilds", "normal", "tavern", "crafty", ["brewing"], "innkeeper"),
    "butcher": _R("guilds", "normal", "market_square", "strong", [], "merchant"),
    "carpenter": _R("guilds", "normal", "kings_street", "crafty", ["masonry"], "mason"),
    "scribe": _R("guilds", "normal", "chapel", "learned", ["letters"], "merchant"),
    "scholar": _R("guilds", "low", "chapel", "learned", ["letters"], "alchemist"),
    "teacher": _R("guilds", "low", "chapel", "learned", ["letters"], "bard"),
    "librarian": _R("guilds", "low", "chapel", "learned", ["letters"], "bard"),
    "jester": _R("commoners", "low", "tavern", "charming", ["music"], "bard"),
    "minstrel": _R("commoners", "low", "tavern", "charming", ["music"], "bard"),
    "juggler": _R("commoners", "low", "market_square", "charming", [], "bard"),
    "mercenary": _R("army", "normal", "tavern", "strong", ["riding"], "soldier"),
    "sellsword": _R("army", "normal", "tavern", "strong", ["riding"], "soldier"),
    "warrior": _R("army", "normal", "castle_yard", "strong", ["riding"], "soldier"),
    "gravedigger": _R("commoners", "low", "chapel", "strong", [], "farmer"),
    "stablehand": _R("commoners", "low", "castle_yard", "strong", ["riding"], "farmer"),
    "squire": _R("army", "low", "castle_yard", "strong", ["riding"], "soldier"),
    "potter": _R("guilds", "normal", "market_square", "crafty", [], "mason"),
    "jeweler": _R("guilds", "high", "market_square", "crafty", ["smithing"], "merchant"),
    "shopkeeper": _R("guilds", "normal", "market_square", "charming", ["letters"], "merchant"),
    "tavern wench": _R("commoners", "low", "tavern", "charming", ["brewing"], "innkeeper"),
    "barmaid": _R("commoners", "low", "tavern", "charming", ["brewing"], "innkeeper"),
    "bartender": _R("guilds", "normal", "tavern", "charming", ["brewing"], "innkeeper"),
    "lumberjack": _R("commoners", "normal", "fields", "strong", [], "woodcutter"),
    "farmhand": _R("commoners", "low", "fields", "strong", [], "farmer"),
    "peasant": _R("commoners", "low", "fields", "none", [], "farmer"),
}
EARNED = {"knight", "lord", "lady", "king", "queen", "prince", "princess", "duke", "duchess", "baron", "baroness",
          "count", "countess", "earl", "emperor", "empress", "ruler", "monarch", "noble", "nobleman", "noblewoman",
          "royal", "royalty", "heir", "sir", "dame", "general", "captain", "steward", "chancellor"}
SILLY = {"god", "goddess", "dragon", "demon", "angel", "vampire", "werewolf", "unicorn", "ghost", "elf", "dwarf",
         "orc", "giant", "wizard king", "deity", "immortal", "superhero", "alien", "robot", "cat", "dog", "horse",
         "goat", "chicken", "billionaire", "millionaire"}

# what doing a role actually looks like, so claims can be checked: label -> the counter that proves it
DEED_OF = {"thief": "steal", "pickpocket": "steal", "cutpurse": "steal", "burglar": "steal", "bandit": "steal",
           "highwayman": "steal", "pirate": "steal", "smuggler": "steal", "con artist": "steal", "swindler": "steal",
           "robber": "steal", "assassin": "fight", "warrior": "fight", "fighter": "fight", "brawler": "fight",
           "mercenary": "fight", "sellsword": "fight", "champion": "fight", "duelist": "fight",
           "healer": "heal", "doctor": "heal", "physician": "heal", "nurse": "heal", "medic": "heal",
           "priest": "bless", "monk": "bless", "nun": "bless", "cleric": "bless", "friar": "bless"}
DEED_WORD = {"steal": "stolen so much as a turnip", "fight": "won a single fight", "heal": "patched up a single soul",
             "bless": "blessed a single soul", "craft": "made a single thing"}
REPUTE = [("steal", 3, "a known thief"), ("fight", 4, "a brawler people step around"),
          ("heal", 3, "a healer people trust"), ("bless", 4, "a holy soul"), ("craft", 5, "good with their hands")]

STOP = {"today", "now", "and", "to", "for", "in", "at", "because", "so", "but", "then", "who", "that", "from",
        "of", "with", "instead", "again", "forever", "please", "lol", "haha", "too"}


# ---------------------------------------------------------------- words -> a role label
def normalize(phrase):
    """'A RAT CATCHERS!' -> 'rat catcher'; 'the greatest thief in Emberfall' -> 'greatest thief'."""
    w = re.findall(r"[a-z']+", str(phrase or "").lower())
    while w and w[0] in ("a", "an", "the", "now", "just", "officially", "gonna", "going", "to", "be", "become"):
        w = w[1:]
    out = []
    for x in w:
        if x in STOP:
            break
        out.append(x)
        if len(out) == 3:
            break
    if not out:
        return ""
    last = out[-1]
    irregular = {"thieves": "thief", "wolves": "wolf", "elves": "elf", "dwarves": "dwarf", "witches": "witch",
                 "men": "man", "women": "woman"}
    if last in irregular:
        last = irregular[last]
    elif last.endswith("s") and not last.endswith(("ss", "us", "is")) and len(last) > 3:
        last = last[:-1]
    out[-1] = last
    return " ".join(out)


def head(label):
    """The noun that decides what a role is: 'greatest thief' -> 'thief', 'royal rat catcher' -> 'rat catcher'."""
    if label in ROLE_BOOK or label in EARNED or label in SILLY:
        return label
    words = label.split()
    for k in range(len(words)):
        tail = " ".join(words[k:])
        if tail in ROLE_BOOK or tail in EARNED or tail in SILLY or tail in DEED_OF:
            return tail
    return words[-1] if words else label


BECOME = re.compile(r"\b(?:become|becoming|became|want to be|wanna be|going to be|gonna be|will be|take up the life "
                    r"of|start working as|now work as|retrain as|train to be|apply to be|turn to a life as|am now|"
                    r"i'?m now|im now|switch to being|quit and become)\s+(?:an?\s+|the\s+)?([a-z][a-z' -]{1,40})", re.I)
CLAIM = re.compile(r"^\W*(?:i\s+am|i'?m|im|i\s+be)\s+(?:an?\s+|the\s+)?([a-z][a-z' -]{1,40})", re.I)


def parse(text):
    """-> (how, label, pure) or None. how = 'become' (I choose this life) or 'claim' (I say I already am).
    pure = the comment is only that (nothing else to play out)."""
    t = str(text or "").strip()
    m = BECOME.search(t)
    how = "become"
    if not m:
        m = CLAIM.search(t)
        how = "claim"
        if m and re.match(r"(going|gonna|trying|about|so|very|not|here|back|tired|hungry|sad|happy|bored|sorry|"
                          r"done|ready|sure|out|in|at|on|off|the king's|your|loyal|with)\b", m.group(1), re.I):
            return None          # "i'm going to the market", "i'm tired" - not a role
    if not m:
        return None
    label = normalize(m.group(1))
    if not label:
        return None
    rest = (t[:m.start()] + " " + t[m.end():]).strip()
    rest_words = re.findall(r"[A-Za-z']+", rest)
    extra = len(re.findall(r"[A-Za-z']+", m.group(1))) - len(label.split())
    pure = len(rest_words) + max(0, extra) <= 4 and not re.search(r"\band (i |then )", m.group(1), re.I)
    if how == "claim" and not pure and len(t.split()) > 25:
        return None
    return how, label, pure


# ---------------------------------------------------------------- label -> mechanics
SCHEMA = {"type": "object", "properties": {
    "kind": {"type": "string", "enum": ["role", "earned", "silly"]},
    "faction": {"type": "string", "enum": list(FACTIONS)}, "income": {"type": "string", "enum": list(INCOME)},
    "illegal": {"type": "boolean"}, "homeless": {"type": "boolean"},
    "place": {"type": "string", "enum": list(PLACES)}, "knack": {"type": "string", "enum": list(KNACKS)},
    "skills": {"type": "array", "items": {"type": "string", "enum": [s for s in SKILLS if s not in NOBODY]}},
    "base": {"type": "string"}},
    "required": ["kind", "faction", "income", "illegal", "homeless", "place", "knack", "skills", "base"]}
SYSTEM = """A subject of a medieval kingdom (no real magic) wants to live as the role below. Map it onto the game:
kind: role (anything a real medieval person could be: thief, beggar, rat catcher, monk, wizard who can't really do
  magic...), earned (a title given by birth, battle or the king: knight, lord, prince, general...), silly (not a person:
  a dragon, a god, a cat, a billionaire).
faction: commoners (common folk, outcasts), guilds (crafts, trade, learning) or army (fighting for pay).
income: none, low, normal or high. illegal: true if the money comes from crime.
homeless: true if this life means no house (beggar, vagrant, hermit).
place: where you'd usually find them. knack: the ONE thing they're best at (or none).
skills: crafts they'd really know (often none or one). base: the closest of: {jobs}."""


def lookup(label, book, llm=None, jobs=()):
    """The mechanics for a role label. Remembered in `book` so the same role works the same for everyone."""
    label = normalize(label)
    if label in book:
        return book[label]
    h = head(label)
    rec = None
    if h in EARNED or label in EARNED:
        rec = {"kind": "earned"}
    elif h in SILLY or label in SILLY:
        rec = {"kind": "silly"}
    elif h in ROLE_BOOK:
        rec = dict(ROLE_BOOK[h])
    elif h in jobs:
        rec = {"kind": "role", "job": h}
    elif llm is not None:
        try:
            d = llm.json(SYSTEM.format(jobs=", ".join(jobs)), f"Role: {label}", SCHEMA, max_tokens=300,
                         temperature=0.2)
            rec = _clean(d, jobs)
        except Exception:
            rec = None
    if rec is None:
        rec = _guess(label, jobs)
    book[label] = rec
    return rec


def _clean(d, jobs):
    kind = d.get("kind") if d.get("kind") in ("role", "earned", "silly") else "role"
    if kind != "role":
        return {"kind": kind}
    return {"kind": "role", "faction": d.get("faction") if d.get("faction") in FACTIONS else "commoners",
            "income": d.get("income") if d.get("income") in INCOME else "low",
            "illegal": bool(d.get("illegal")), "homeless": bool(d.get("homeless")),
            "place": d.get("place") if d.get("place") in PLACES else "market_square",
            "knack": d.get("knack") if d.get("knack") in KNACKS else "none",
            "skills": [s for s in (d.get("skills") or []) if s in SKILLS and s not in NOBODY][:3],
            "base": d.get("base") if d.get("base") in jobs else "farmer"}


def _guess(label, jobs):
    """No model: a few keyword families, else a plain low-paid commoner in the market."""
    t = label
    fams = [(r"thie|rob|crook|outlaw|rogue|cutthroat|bandit|smuggl", ROLE_BOOK["thief"]),
            (r"beg|homeless|tramp|hobo|vagabond|wander", ROLE_BOOK["beggar"]),
            (r"priest|monk|holy|pray|church|saint|pilgrim|preach", ROLE_BOOK["priest"]),
            (r"heal|doctor|medic|nurse|herb|apothecar", ROLE_BOOK["healer"]),
            (r"wizard|mage|witch|warlock|sorcer|necromanc|druid|alchem", ROLE_BOOK["wizard"]),
            (r"smith|armou?rer|weaponsmith|metal", {**ROLE_BOOK["carpenter"], "skills": ["smithing"], "base": "blacksmith"}),
            (r"cook|chef|bak|brew|kitchen", ROLE_BOOK["cook"]),
            (r"fight|warrior|sword|mercenar|knight|guard|soldier|barbarian|gladiator|berserk", ROLE_BOOK["warrior"]),
            (r"hunt|trap|ranger|forest|wood|rat", ROLE_BOOK["hunter"]),
            (r"sing|music|bard|poet|jest|perform|danc|actor|juggl|storytell", ROLE_BOOK["minstrel"]),
            (r"scribe|schol|teach|book|writ|histor|sage", ROLE_BOOK["scholar"]),
            (r"sail|fish|boat|ship", {**ROLE_BOOK["smuggler"], "illegal": False, "income": "normal"}),
            (r"trade|sell|merchant|shop|peddl|vendor", ROLE_BOOK["shopkeeper"]),
            (r"farm|field|shepherd|goat|pig|cow|chicken|crop|garden", ROLE_BOOK["farmhand"]),
            (r"spy|assassin|shadow|ninja", ROLE_BOOK["spy"])]
    for pat, rec in fams:
        if re.search(pat, t):
            return dict(rec)
    for j in jobs:
        if j in t:
            return {"kind": "role", "job": j}
    return {"kind": "role", "faction": "commoners", "income": "low", "illegal": False, "homeless": False,
            "place": "market_square", "knack": "none", "skills": [], "base": "farmer"}


# ---------------------------------------------------------------- what someone can do
def skills_of(rec, job):
    if not rec or rec.get("kind") != "role" or rec.get("job"):
        job = (rec or {}).get("job") or job
        return set(JOB_SKILLS.get(job, [])) | set(KNACK_SKILLS.get(JOB_KNACK.get(job, ""), []))
    return set(rec.get("skills", [])) | set(KNACK_SKILLS.get(rec.get("knack", ""), []))


def knack_of(rec, job):
    if not rec or rec.get("job"):
        return JOB_KNACK.get((rec or {}).get("job") or job, "none")
    return rec.get("knack", "none")


def needed(text):
    """Skills a move tries to use, in order of how much they matter."""
    t = str(text or "").lower()
    return [s for s in SKILL_ORDER if re.search(SKILLS[s][0], t)]


def reputation(counts):
    """What the kingdom knows you as, from what you've actually done."""
    return [label for key, need, label in REPUTE if counts.get(key, 0) >= need]


def backed(label, counts, current, deeds):
    """Does the record back up 'I am a <label>'?"""
    h = head(label)
    deed = DEED_OF.get(h)
    if deed:
        return counts.get(deed, 0) >= 1
    return current is not None and head(current) == h and deeds >= 3


# ---------------------------------------------------------------- what people hear
MOCK = ["Sure you are. And I shit piles of gold.",
        "A {label}? The baker laughed so hard she dropped a whole tray of rolls.",
        "Big words. You've never {deed} in your life.",
        "Everyone in {hold} heard you. Nobody believed you.",
        "The town crier repeated it, then couldn't keep a straight face.",
        "A {label}. Right. And the king's goat lays golden eggs.",
        "Half the tavern raised a mug to the great {label}. The other half are still laughing."]
MOCK_EARNED = ["Bold. The guards laughed so hard one of them dropped his spear. {path}",
               "You stood in the square and announced it. A pigeon was the only one who bowed. {path}",
               "And I'm the Queen of the Moon. {path}"]
PATH = {"knight": "Knights are made on the battlefield - three battles and the deeds to match.",
        "lord": "Lords are named by the king, one per hold.", "king": "There's one king, and he's not you. Yet.",
        "queen": "There's one throne, and you're not on it.", "general": "The army promotes from the front line."}
MOCK_SILLY = ["You told the whole market you're a {label}. A child believed you; nobody else did.",
              "A {label}. Sure. The chickens are terrified.",
              "You flapped your arms in the square for a while. Still a person."]
BACKED = {"steal": ["Everyone knows. Shopkeepers pull their purses closer when you walk past.",
                    "No argument there - the guards have your face memorised."],
          "fight": ["Nobody argues with you. Nobody dares.", "The tavern goes quiet when you walk in. They know."],
          "heal": ["They know - half the hold owes you a stitch or two.", "Nobody doubts it. Ask anyone you've patched up."],
          "bless": ["The chapel knows it. So do the people you've blessed."]}


def plural(label):
    words = label.split()
    w = words[-1]
    irregular = {"thief": "thieves", "wolf": "wolves", "elf": "elves", "man": "men", "woman": "women",
                 "fish": "fish", "sheep": "sheep"}
    if w in irregular:
        w = irregular[w]
    elif w.endswith(("s", "x", "ch", "sh")):
        w += "es"
    elif w.endswith("y") and w[-2:-1] not in "aeiou":
        w = w[:-1] + "ies"
    else:
        w += "s"
    return " ".join(words[:-1] + [w])


def a_(label):
    return ("an " if label[:1] in "aeiou" else "a ") + label


def perk_line(rec, job=None):
    """What a role gives you, in one or two sentences."""
    knack = knack_of(rec, job)
    bits = []
    if KNACKS.get(knack):
        bits.append(KNACKS[knack][0].upper() + KNACKS[knack][1:] + ".")
    sk = sorted(skills_of(rec, job) - ({"lockpicking"} if knack == "sneaky" else set()))
    if sk:
        names = [SKILL_LABEL.get(x, x) for x in sk]
        bits.append("You know " + (", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0])
                    + "; anything else you'd be learning the hard way.")
    else:
        bits.append("No craft to speak of - try something you don't know and it'll go wrong.")
    if rec and rec.get("illegal"):
        bits.append("It's not honest money: the guards may come knocking.")
    if rec and rec.get("homeless"):
        bits.append("No house: nothing for raiders to burn, nothing worth stealing, but cold nights wear you down.")
    return " ".join(bits)


def welcome_line(label, rec, hold, job=None):
    place = PLACE_AT.get((rec or {}).get("place", ""), "")
    pay = (rec or {}).get("income")
    pay = {"none": "You'll earn next to nothing.", "low": "The pay is poor.", "high": "It pays well."}.get(pay, "")
    return (f"From today you're {a_(label)} in {hold}. {perk_line(rec, job)}"
            + (f" You'll be found {place}." if place else "") + (f" {pay}" if pay else ""))


# ---------------------------------------------------------------- taking up a role
def take(city, i, how, label, day, llm=None, quiet_same=False):
    """Someone says they become / already are <label>. Returns {changed, text, kind}.
    kind: role (new life), mocked (said it, record doesn't back it; still takes it up), backed, same,
    earned / silly (nothing changes), wait (already changed today)."""
    from .roles import JOB_NAMES
    c = city.citizens
    rng = city.rng
    label = normalize(label)
    if not label:
        return {"changed": False, "text": "", "kind": "none"}
    w = city.wards[int(c.ward[i])]
    hold = w["name"]
    rec = lookup(label, c.role_book, llm, JOB_NAMES)
    counts = c.counts_of(i)
    h = head(label)
    if rec["kind"] == "earned":
        really = (h in ("knight", "sir", "dame") and c.rank(i) == "Knight") or (
            h in ("lord", "lady") and w.get("councilor") == i)
        if really:
            return {"changed": False, "text": "Nobody would dare say otherwise.", "kind": "backed"}
        return {"changed": False, "kind": "earned", "text": rng.choice(MOCK_EARNED).format(
            path=PATH.get(h, "Titles like that are given, not taken."))}
    if rec["kind"] == "silly":
        return {"changed": False, "kind": "silly", "text": rng.choice(MOCK_SILLY).format(label=label)}
    current = c.label(i)
    deed = DEED_OF.get(h)
    if head(current) == h or (rec.get("job") and rec["job"] == current):
        if how == "claim":
            if backed(label, counts, current, int(counts.get("commands", 0))):
                return {"changed": False, "kind": "backed", "text": rng.choice(BACKED.get(deed, ["Nobody argues."]))}
            return {"changed": False, "kind": "mocked", "text": _mock(rng, label, deed, hold)}
        return {"changed": False, "kind": "same", "text": "" if quiet_same else f"You already are {a_(label)}."}
    if c.role_day.get(int(i)) == day:
        return {"changed": False, "kind": "wait", "text": "One new life a day - sleep on it and try again tomorrow."}
    c.set_role(i, label if not rec.get("job") else rec["job"], rec, day)
    job = JOB_NAMES[int(c.job[i])]
    if how == "claim" and not backed(label, counts, None, 0):
        return {"changed": True, "kind": "mocked",
                "text": _mock(rng, label, deed, hold) + f" Fine - from today you're {a_(label)}. Prove it."}
    return {"changed": True, "kind": "role", "text": welcome_line(label, c.role(i), hold, job)}


def _mock(rng, label, deed, hold):
    lines = [m for m in MOCK if "{deed}" not in m or deed]
    return rng.choice(lines).format(label=label, deed=DEED_WORD.get(deed, ""), hold=hold)


def has_skill(c, i, skill):
    if skill in NOBODY:
        return False
    from .roles import JOB_NAMES
    return skill in skills_of(c.role(i), JOB_NAMES[int(c.job[i])])


def knack(c, i):
    from .roles import JOB_NAMES
    return knack_of(c.role(i), JOB_NAMES[int(c.job[i])])


def second_person(phrase):
    t = " " + phrase + " "
    for a, b in ((" their ", " your "), (" them ", " you "), (" they ", " you "), (" themselves ", " yourself ")):
        t = t.replace(a, b)
    return t.strip()
