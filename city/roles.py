"""Who citizens are. A new citizen's job comes from their handle (same handle,
same job, every time), and their title comes from what they actually do:
comment PROTEST a lot and you become known as an Organizer.
"""
import hashlib

# job -> (faction, base daily wage)
JOBS = {
    "nurse": ("labor", 150), "barista": ("labor", 95), "teacher": ("labor", 135),
    "mechanic": ("labor", 130), "delivery driver": ("labor", 100), "electrician": ("labor", 155),
    "line cook": ("labor", 95), "bus driver": ("labor", 120), "warehouse worker": ("labor", 105),
    "software dev": ("business", 240), "shop owner": ("business", 170), "realtor": ("business", 180),
    "food truck owner": ("business", 140), "accountant": ("business", 175), "startup founder": ("business", 150),
    "student": ("residents", 40), "retiree": ("residents", 80), "artist": ("residents", 75),
    "stay-at-home parent": ("residents", 50), "musician": ("residents", 70), "librarian": ("residents", 110),
}
JOB_NAMES = list(JOBS)
FACTIONS = ["labor", "business", "residents"]
FACTION_LABEL = {"labor": "Workers", "business": "Business", "residents": "Residents"}

FIRST = ["Dana", "Marcus", "Priya", "Leo", "Ava", "Jamal", "Rosa", "Theo", "Mei", "Owen", "Zara", "Eli",
         "Nina", "Caleb", "Iris", "Mateo", "June", "Arjun", "Hana", "Felix", "Lena", "Omar", "Ruby", "Sam",
         "Tessa", "Victor", "Wren", "Yusuf", "Chloe", "Diego", "Freya", "Gus", "Ines", "Kofi", "Luz", "Nico"]
LAST = ["Ruiz", "Okafor", "Patel", "Novak", "Kim", "Brennan", "Haddad", "Silva", "Lindqvist", "Moreau",
        "Tanaka", "Walsh", "Adeyemi", "Kowalski", "Reyes", "Fischer", "Nakamura", "O'Neil", "Varga", "Duarte",
        "Ahmed", "Becker", "Costa", "Dube", "Engel", "Farrow", "Grant", "Ibarra", "Jensen", "Kaur"]


def _h(handle, salt=""):
    return int(hashlib.sha256((salt + handle.lower()).encode()).hexdigest()[:12], 16)


def identity(handle):
    """Name and job for a new citizen, stable for the same handle."""
    h = _h(handle)
    name = f"{FIRST[h % len(FIRST)]} {LAST[(h // 97) % len(LAST)]}"
    job = JOB_NAMES[(h // 7919) % len(JOB_NAMES)]
    return name, job


# titles earned from behaviour: (counter, threshold, title)
TITLES = [
    ("protest", 8, "Organizer"), ("work", 10, "Workhorse"), ("shop", 8, "Big Spender"),
    ("volunteer", 6, "Neighborhood Hero"), ("donate", 5, "Benefactor"), ("support", 6, "Loyalist"),
    ("oppose", 6, "Thorn in the Mayor's Side"),
]


def title_for(counts):
    best, score = "", 0
    for key, need, title in TITLES:
        c = counts.get(key, 0)
        if c >= need and c / need > score:
            best, score = title, c / need
    return best
