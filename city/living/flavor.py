"""Variety for the model's prompts. Fixed examples in a prompt become the model's answers ("a fire pit, a
patched roof" -> it builds a fire pit and patches the roof, every time). So examples are drawn at random from
wide pools, the king is a different man in every kingdom, and every so often he notices something in the world
that he could take up - or ignore.
"""
import random

# ---------------------------------------------------------------- who he was before (one per kingdom)
PAST = ["a shipwright's son from the coast", "a soldier who walked away from a lost war", "a monk who lost his faith",
        "a smith's apprentice who never finished", "a merchant who went bankrupt twice", "a shepherd from the high "
        "pastures", "a stonemason who worked on a cathedral he never saw finished", "a poacher with a price on his head",
        "a minstrel who got tired of other people's songs", "a scribe who copied laws for a cruel duke",
        "a miller's third son with no inheritance", "a cook in a lord's kitchen", "a bridge builder's labourer",
        "a gravedigger", "a fisherman whose boat sank", "a tanner who hated the smell", "a disgraced knight's squire",
        "a beekeeper", "a carpenter who built ships' cabins", "a hedge-school teacher", "a horse trader",
        "a wandering herbalist", "a quarryman", "a forester for a king who never visited his own woods"]
TEMPER = ["patient", "restless", "proud", "gentle", "stubborn", "playful", "anxious", "practical", "dreamy", "blunt",
          "curious", "orderly", "reckless", "warm", "suspicious", "funny", "solemn", "generous"]
LOVES = ["the sound of running water", "old songs", "carving small animals", "the stars", "bread fresh from the oven",
         "fixing broken things", "tall stone towers", "gardens", "a good argument", "early mornings", "horses",
         "maps", "the smell of cut timber", "storms", "being alone with his thoughts", "a crowded table", "bells",
         "boats", "bright colours", "clever machines"]
HATES = ["waste", "being idle", "cold feet", "liars", "crowds", "mud", "being laughed at", "the dark", "debts",
         "rushing", "nobles", "silence", "rats", "the sea", "rain on a roof he built badly"]
KNOWS = {"shipwright": "carpentry", "stonemason": "stone foundations", "quarryman": "stone foundations",
         "carpenter": "carpentry", "smith": "metalwork", "fisherman": "knots", "shepherd": "thatching",
         "bridge": "timber framing", "cook": "kiln firing", "miller": "timber framing", "beekeeper": "thatching",
         "horse": "knots", "forester": "timber framing", "poacher": "knots"}


def character(rng):
    past, temper = rng.choice(PAST), rng.sample(TEMPER, 2)
    loves, hates = rng.choice(LOVES), rng.choice(HATES)
    text = (f"Before this you were {past}. You're {temper[0]} and {temper[1]}. You love {loves} and can't stand "
            f"{hates}.")
    know = next((t for k, t in KNOWS.items() if k in past), None)
    return text, know


# ---------------------------------------------------------------- examples, drawn fresh each time
SMALL_JOBS = ["a fire pit", "a drying rack", "a bench by the door", "a woodpile under cover", "a rain barrel",
              "a latrine", "a chopping block", "a fence for a herb patch", "a smoking rack for fish",
              "a proper door", "a shelf for tools", "a path of flat stones", "a lean-to for firewood", "a bread oven",
              "a sundial", "a scarecrow", "a hitching post", "a little bridge over the ditch", "a beehive",
              "a well cover", "a sign for the road", "a lookout post", "a goat pen", "a clay pit"]
BY_SCALE = {
    "tiny": ["a bed", "a stone axe", "a fish trap", "a beehive", "a bread oven", "a scarecrow", "a well cover",
             "a lookout post", "a goat pen", "a rain barrel"],
    "small": ["a cottage", "a garden", "a shed", "a smokehouse", "a chicken coop", "a workshop", "a well",
              "a little dock", "a root cellar", "a shrine", "a woodshed", "a kiln", "a hut on the crag"],
    "medium": ["a longhouse", "a barn", "a mill", "a smithy", "a granary", "a meeting hall", "a bathhouse",
               "a watchtower", "a bridge", "an inn", "a chapel", "a ropewalk"],
    "large": ["a row of houses", "a great hall", "a palisade", "a market square", "a stone bridge", "a harbour",
              "a quarry works", "a brewery", "a school", "a stable yard"],
    "huge": ["a tenement block", "a stone keep", "a castle on the crag", "a town wall", "a cathedral",
             "a great granary", "a canal"],
}
DOINGS = ["eat", "sleep", "rest", "explore", "sing", "carve", "wash in the river", "practise something", "fish",
          "climb the crag", "sketch plans in the dirt", "talk to himself", "count his stores", "pray", "whittle",
          "walk the boundary", "cook something", "mend his clothes", "watch the clouds", "skip stones",
          "sharpen the axe", "pick berries", "lie in the grass", "hum an old tune"]


def some(pool, n=3, rng=random):
    return ", ".join(rng.sample(pool, min(n, len(pool))))


# ---------------------------------------------------------------- things he notices
NOTICE = {
    "any": ["A fox is watching you from the edge of the woods.", "Geese fly over, heading south.",
            "Your back aches from yesterday.", "You catch yourself humming a song you'd forgotten.",
            "A crow has been following you around all morning.", "You find an old rusted horseshoe in the grass.",
            "The wind smells of rain.", "You think about home, and what was wrong with it.",
            "A stray dog has started sleeping near the shack.", "Someone carved initials into a stone here, long ago.",
            "You wonder what the settlers will think of the place.", "Your hands are getting harder.",
            "The crag catches the evening light; from up there you could see the whole valley.",
            "Smoke from your fire drifts toward the mountains.", "You realise you haven't spoken out loud in a while.",
            "Wild garlic grows thick along the shady side of the field.", "The mountain snow looks closer today."],
    "woods": ["There's a fallen oak in the woods, already seasoned.", "Mushrooms everywhere after the rain.",
              "Deer tracks lead deeper into the woods.", "A tree here has a hollow big enough to sleep in."],
    "river": ["The clay on the riverbank is good and sticky.", "Trout are rising in the slow water.",
              "There's a shallow ford here where the river spreads out.", "Reeds grow thick along the bend."],
    "hill": ["From the crag you can see the lake and the road out of the valley.", "Some of the rock splits cleanly in "
             "flat slabs.", "There's a flat ledge near the top, sheltered from the wind."],
    "field": ["The soil turns up dark and rich where the field dips.", "Bees work the clover all afternoon.",
              "A ring of old stones half buried in the grass - someone was here before."],
    "road": ["Cart ruts in the old road, not that old.", "A milestone with the name worn off."],
}


def notice(rng, place=None):
    pool = NOTICE["any"] + NOTICE.get(place or "", []) * 2
    return rng.choice(pool)
