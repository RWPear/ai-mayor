"""Who subjects are.

A new subject's job comes from their handle (same handle, same job, every time),
so following is enough to get a life in the kingdom. Anyone can change job by
commenting BECOME <JOB> (e.g. "BECOME BLACKSMITH") on any post.

Rank is earned by deeds: Peasant -> Freeman -> Squire -> Knight. Lords are
appointed by the king (one per hold). Epithets come from what you actually do:
grumble a lot and you become "the Grumbler".
"""
import hashlib

# job -> (faction, base daily wage in gold)
JOBS = {
    # commoners: the people who keep everyone fed
    "farmer": ("commoners", 110), "fisher": ("commoners", 100), "miner": ("commoners", 140),
    "woodcutter": ("commoners", 105), "miller": ("commoners", 120), "shepherd": ("commoners", 90),
    "bard": ("commoners", 70),
    # guilds: crafts and trade
    "blacksmith": ("guilds", 170), "merchant": ("guilds", 210), "mason": ("guilds", 160),
    "innkeeper": ("guilds", 150), "alchemist": ("guilds", 190), "tailor": ("guilds", 130),
    "baker": ("guilds", 125),
    # army: the crown's swords
    "soldier": ("army", 120), "archer": ("army", 125), "guard": ("army", 115), "scout": ("army", 110),
    "sailor": ("army", 105),
}
JOB_NAMES = list(JOBS)
FACTIONS = ["commoners", "guilds", "army"]
FACTION_LABEL = {"commoners": "Commoners", "guilds": "Guilds", "army": "Army"}

FIRST = ["Aldo", "Brienne", "Cedric", "Dara", "Edric", "Freya", "Gareth", "Hilde", "Ivo", "Jora", "Kael",
         "Lyra", "Magnus", "Nell", "Osric", "Petra", "Quill", "Rowena", "Soren", "Tamsin", "Ulric", "Vera",
         "Wynn", "Yara", "Zeke", "Ansel", "Bryn", "Cora", "Dmitri", "Elspeth", "Fenn", "Greta", "Halvard",
         "Isolde", "Jasper", "Kira", "Leif", "Maren", "Nadia", "Oona"]
LAST = ["Ashdown", "Blackwood", "Coldbrook", "Dunmore", "Emberly", "Fairweather", "Greyhame", "Hollowell",
        "Ironside", "Juniper", "Kettleby", "Longstride", "Marsh", "Northwood", "Oakheart", "Pennywhistle",
        "Quickwater", "Redfern", "Stonebridge", "Thistle", "Underhill", "Vance", "Whitlock", "Yarrow",
        "Brightwater", "Crowley", "Dawson", "Elmsworth", "Foxglove", "Goodbarrow"]


def a_job(job):
    """'a blacksmith', 'an innkeeper'."""
    return ("an " if job[0] in "aeiou" else "a ") + job


def the(name):
    """'the Royal Granary', but 'The Crown & Tankard' stays as it is."""
    return name if name.lower().startswith("the ") else f"the {name}"


def _h(handle, salt=""):
    return int(hashlib.sha256((salt + handle.lower()).encode()).hexdigest()[:12], 16)


def identity(handle):
    """Name and job for a new subject, stable for the same handle."""
    h = _h(handle)
    name = f"{FIRST[h % len(FIRST)]} {LAST[(h // 97) % len(LAST)]}"
    job = JOB_NAMES[(h // 7919) % len(JOB_NAMES)]
    return name, job


def job_from_word(word):
    """'BLACKSMITH' / 'blacksmiths' / 'Smith' -> 'blacksmith' (or None)."""
    w = str(word).strip().lower()
    if w in JOBS:
        return w
    if w.endswith("s") and w[:-1] in JOBS:
        return w[:-1]
    aliases = {"smith": "blacksmith", "warrior": "soldier", "fisherman": "fisher",
               "trader": "merchant", "cook": "baker", "builder": "mason", "hunter": "scout",
               "musician": "bard", "sailer": "sailor", "lumberjack": "woodcutter"}
    return aliases.get(w)


# ranks earned from deeds: (rank, min actions, min battles)
RANKS = [("Knight", 25, 3), ("Squire", 12, 0), ("Freeman", 5, 0), ("Peasant", 0, 0)]


def rank_for(counts):
    for rank, actions, battles in RANKS:
        if counts.get("commands", 0) >= actions and counts.get("battles", 0) >= battles:
            return rank
    return "Peasant"


# epithets earned from behaviour: (counter, threshold, epithet)
TITLES = [
    ("protest", 8, "the Grumbler"), ("work", 10, "the Tireless"), ("shop", 8, "the Big Spender"),
    ("volunteer", 6, "the Helpful"), ("donate", 5, "the Generous"), ("support", 6, "the Loyal"),
    ("oppose", 6, "Thorn in the King's Side"), ("train", 8, "the Drillmaster"), ("battles", 4, "the Brave"),
]


def title_for(counts):
    best, score = "", 0
    for key, need, title in TITLES:
        c = counts.get(key, 0)
        if c >= need and c / need > score:
            best, score = title, c / need
    return best
