"""./kingdom demo - a mid-sized Emberfall to look at: about 50 people, ten days in.

Fifty made-up followers each pick a life on day one ("I become a woodcutter"), then every day a dozen or so of them
make a move (chop, fish, build their own cottage, help with the longhouse). It runs on the rules (no model, so it
takes seconds), then opens the live kingdom where it left off, so you can watch everyone's day and comment into it.

    ./kingdom demo                       # 50 people, 10 days in, then live at http://localhost:8765/?live
    ./kingdom demo --people 80 --days 14
"""
import random

ROLES = ["woodcutter", "woodcutter", "woodcutter", "farmer", "farmer", "farmer", "fisher", "fisher", "mason", "mason",
         "baker", "carpenter", "hunter", "herbalist", "bard", "guard", "shepherd", "brewer", "tailor", "scout"]
MOVES = ["I chop wood all morning", "I help build the roof", "I go fishing at the river", "I haul stone from the hill",
         "I cut thatch in the field", "I want to build a small cottage by my tent", "I plant onions in a garden",
         "I help Aldric with whatever he's building", "I gather mushrooms in the woods", "I mend the nets",
         "I bake bread for everyone", "I sing by the fire tonight", "I teach someone to split logs",
         "I explore the new land", "I keep watch on the old road", "I gather reeds for baskets"]
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
                    play.comment(h, f"I become a {ROLES[k % len(ROLES)]}")
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
