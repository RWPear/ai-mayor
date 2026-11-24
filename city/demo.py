"""./kingdom demo - a mid-sized Emberfall to look at: about 50 people, ten days in.

Fifty made-up followers each say what they want to do on day one ("I want to be a farmer"), then every day a dozen
or so of them speak up (an extra shift, and a push toward some work: the farm, a building going up, the tavern, doing
up their own house). It runs on the rules (no model, so it takes seconds), then opens the live kingdom where it
left off, so you can watch everyone's day and comment into it.

    ./kingdom demo                       # 50 people, 10 days in, then live at http://localhost:8765/?live
    ./kingdom demo --people 80 --days 14
"""
import random

ROLES = ["farmer", "farmer", "farmer", "builder", "builder", "builder", "brewer", "baker", "guard", "bard", "smith",
         "trader", "priest", "farmer", "builder", "barkeep", "vintner", "teacher", "soldier", "farmer"]
MOVES = ["I help build whatever's going up", "I work the farm all day", "I want to brew beer", "I'll pour pints at the tavern",
         "I help Aldric with whatever he's building", "I bake bread for everyone", "I sing by the fire tonight",
         "I keep watch from the tower", "I put a new roof on my house", "I plant a garden behind my house",
         "I sell turnips at the market", "I pray at the shrine", "I teach the kids their letters",
         "I explore the new land", "I hammer horseshoes at the forge", "I help put up the palisade"]
NAMES = ["mara", "tob", "wes", "lin", "oskar", "pell", "quinn", "ada", "bram", "cora", "dov", "elsie", "finn", "gus",
         "hilde", "ivo", "jun", "kit", "lotte", "milo", "nell", "otto", "pia", "rook", "sable", "tam", "ulla", "vik",
         "wren", "yara", "zed", "bea", "cass", "dirk", "edda", "fen", "greta", "hal", "iris", "jory", "kai", "lark",
         "moss", "nico", "opal", "pim", "rhea", "sol", "tilly", "uri", "vera", "will", "xan", "yves", "zora", "abe",
         "bo", "cleo", "dash", "eli"]


def build(play, people=50, days=10, seed=3):
    """Runs a fresh kingdom forward on the rules: people join and pick lives, then make moves each day."""
    rng = random.Random(seed)
    w = play.world
    saved = (dict(w.brains), w.crowd_llm, w.voice_llm, w.director_llm)
    w.brains = {k: w.rules for k in w.brains}
    w.crowd_llm = w.voice_llm = w.director_llm = None
    handles = [(NAMES[k % len(NAMES)] + (str(k // len(NAMES)) if k >= len(NAMES) else "")) for k in range(people)]
    try:
        for d in range(days):
            if d == 0:
                for k, h in enumerate(handles):
                    play.comment(h, f"I want to be a {ROLES[k % len(ROLES)]}")
            else:
                for h in rng.sample(handles, min(len(handles), rng.randint(10, 16))):
                    play.comment(h, rng.choice(MOVES))
            play._drain()
            start = play.city.day
            while play.city.day == start:
                with play.lock:
                    play._tick()
            for r in play.replies:                       # (it's a demo: nobody needs to approve these)
                r["status"] = "approved"
    finally:
        w.brains, w.crowd_llm, w.voice_llm, w.director_llm = saved
    play._to_dawn()
    play._publish()
    return play
