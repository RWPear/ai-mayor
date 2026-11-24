# Emberfall: a kingdom from nothing, on a floating island

Aldric isn't a king. He's a man with a leaky one-room shack in a field on an old floating island above the
clouds, a dull axe and 15 coins. Everything gets built by hand, starting with his own. (The code still calls
this "the frontier"; it's the only game.)

Code: `city/living/frontier.py` (the land, the island, materials, pricing, building, people arriving, labour,
food, stages), `city/living/frontier_tools.py` (what he can do, what he sees, his rule-based instincts) and
`city/living/wonders.py` (the strange things).

## The land

| Place | What's there |
|---|---|
| the shack | a straw mat, a cold fire pit, a roof that leaks |
| the field | grass for thatch, wild onions, room to build |
| the woods | wood, vines and bark for rope, mushrooms |
| the river | clay, reeds, fish - it runs off the island's edge at both ends in waterfalls |
| the rocky hill | stone |
| the old road | runs to the rim, where a wooden landing juts out over the clouds; newcomers and the peddler come this way |

The places grow: a big gathering place he builds (a meeting hall, a tavern) becomes somewhere you can walk
to, and the tent camp appears the first time people have nowhere to sleep.

## The island grows

New land rises out of the clouds at the rim - each piece with a new place on it and its own resources: the
east meadow (food, thatch), the glass cliffs (stone), the silver grove (wood), the warm springs (clay, food), the
old ruins, the crystal fields, the misty point, the sky garden. Land rises every time Emberfall grows a stage
(hamlet, village, town, city), when the island event "the ground is shaking at the edge" is helped along by the
comments (EXPLORE, ROPE), and when the director decides something should. Everyone hears about it ("Something
huge moved under the clouds all night. By morning the warm springs had risen out of them"), and the 3D view
rebuilds the island around it.

## Wonders: real, and never free

The island says "yes, and..." to wild claims. Someone comments "I ride my dragon in": there IS a dragon - maybe a
hatchling the size of a cat that eats the stores, maybe something enormous that won't be ridden. "I cast a
lightning spell": it works far too well and keeps happening on its own. Each wonder belongs to whoever conjured it,
is in what the narrator sees from then on, and costs something every morning (hungry ones eat the food, mischief
knocks the woodpile over, noisy ones wake the camp). People can hunt them, feed them, steal them ("I kill the
goat" works on the goat - if there is one). One conjuring per person every few days.

The narrator can start threads too: if a reply introduces something that should come back ("a goat that follows
you everywhere"), it becomes a small wonder, and the next comment can do something about it. Island events can
leave wonders behind (a whale-song shell, a griffin on the crag, a wizard asleep in the shack).

## He invents, the world charges him

- **Materials are real:** wood, stone, clay, thatch, rope, food and iron. He gathers them where they are.
  How much he gets depends on his tools (a dull axe, then maybe a stone axe he makes, or an iron one from
  the peddler or a follower), practice, energy and the weather.
- **He has ideas in his own words.** "A cottage with a thatched roof", "a fish trap", "a tall apartment
  building of stone and timber". The first time he has an idea, the model says *what it is*: its kind
  (housing, food, storage, workshop, tool, defense, comfort, gathering place, path), its size, its main
  material and the techniques it needs. **The code says what it costs**: materials, hours and capacity, all
  within fixed bounds, so a "small mansion for everyone" still houses at most 4. The price is decided once
  and remembered, so retrying doesn't change it.
- **Bigger buildings are more efficient per person, but need know-how.**

  | Size | Example | Holds | Rough cost |
  |---|---|---|---|
  | tiny | a fire pit, a bed, a stone axe | 1 | 8 materials, 2 hours |
  | small | cottage | 2-4 | 20 materials, 7 hours (a man alone: about a day, gathering included) |
  | medium | longhouse | 6-12 | 60 materials, 22 hours, needs timber framing |
  | large | a row of houses | 20-40 | 160 materials, 60 hours, needs stone foundations |
  | huge | an apartment building | 60-120 | 400 materials, 160 hours, needs mortar and multi-storey building |

  Only so many people fit on one building at once (a crew of 3 / 4 / 6 / 10), so even a crowd takes a day or
  two on a big one, and how big he can go grows with his hands and his experience (no tenement next to the
  shack).
- **The first days have to show something.** Day one he patches the roof or builds a fire pit (an hour or two
  each), and a cottage goes up in about a day. Loneliness bothers him less while he's alone, so he doesn't
  spend his afternoons singing to the empty field. His first house can lean, but it doesn't collapse.

- **Techniques:** thatching, timber framing, stone foundations, mortar, kiln firing, multi-storey building,
  carpentry, metalwork, knots. He can try something he doesn't know how to do yet: each missing
  technique makes it much riskier. Finishing it teaches him, and so does a collapse, half the time.
  Settlers who know a craft can show him when he talks to them (a mason teaches foundations and mortar), and
  they hear "You showed Aldric how stone foundations work."
- **Results:** good, shoddy (it leans, and holds fewer people) or failed (it collapses and the materials are
  gone). Whatever stands becomes a real building with his name for it, a description, a place and tags.
  That's what the 3D view will draw.

## People walk in the day they follow

- A new follower **arrives in Emberfall at once**. They take a free bed if there is one; otherwise they
  pitch a **tent** in the camp by the road: cold nights and low mood, but nobody dies. When a new house is
  finished, the people who've been in tents longest move in, and each of them gets a reply.
- Arriving doesn't get a reply of its own. Their first comment gets a normal reply that also welcomes them
  ("you came over the hill muddy to the knees and pitched a tent by the road...") and plays out what they
  said. Someone who follows without commenting just shows up in the camp.
- So the very first post's comments already do things: chop wood, help with the roof, start a garden.

## Everyone's day, and the little things in it

Everyone keeps the same simple day (`city/living/routine.py`), each person a few minutes earlier or later
than the next so it doesn't look like a drill:

| time | what | where |
|---|---|---|
| 06:00 | up | at home (a house, or their tent) |
| 06:30 | breakfast | **the fire** by the shack, where everyone eats |
| 07:30 | work | their job's place: the woods, the hill, the river, the field, a building going up |
| 12:00 | lunch | the fire |
| 13:00 | work | |
| 17:30 | their own time | fishing, the garden, the woods, the fire, their own build, or a friend's door |
| 19:00 | supper | the fire (songs, dancing) |
| 21:30 | bed | home |

**The little things.** Every half hour, people in the same place at the same time bump into each other and
something small happens: they share bread, swap gossip (about whatever's really going on: a wonder, new
land, Aldric, another settler), help drag a log, show each other how to split one, argue about whose turn
it is at the well, catch someone napping, start a song. A few hundred a week in a town of fifty. Each pair
keeps a running score (comments feed it too: a gift or a punch counts more than a shared loaf), and it adds
up into **stories that happen while nobody's commenting**:

- **friends** (+5), then **inseparable** (+12): a line in the feed, their names in it;
- **a feud** (-4), and if it keeps going, **a fight** (-8): someone gets a black eye and sits out a day.

A few of each a day at most; the rest wait their turn. The little things show in *What happened* (the
"little things" box hides them) and as bubbles over people's heads in 3D. The bard sees each commenter's
people ("friends with @tob - latest: they sang the one about the drowned miller") so a friend can turn up in
their reply and a rival can be in their way.

## From hands to head

- Settlers work every day. On an ordinary day they put in about 1.5 hours; on days they comment WORK or
  BUILD, or describe their work in their own words, it's about 5 hours.
- They feed everyone first, then work on **his** projects and gather what those projects are missing, then
  keep a small reserve. They never start anything themselves: only he decides what gets built. Hours with
  nothing to do show up in his view ("Yesterday the settlers had 346 hours with nothing to do"), which is a
  hint to plan bigger.
- Roles matter: woodcutters fell more trees, masons lay more stone, farmers and fishers bring in more food.
- His verbs grow with the place:
  - **alone:** walk, do (anything), gather, plan (his own idea), build, want
  - **hamlet** (1+ settlers): talk, ask for help (everyone works harder today), proclaim, hold court,
    summon
  - **village** (10+): organize crews (a few people on one job for three days), appoint someone (a
    foreman makes building faster, a forager brings in more food), decree
  - **any time the peddler's cart is on the road:** trade, buying tools, nails, seed potatoes or grain, or
    selling materials for gold

## Nobody has a trade yet

Out here there are no castle trades, guards, court or market. A settler knows a craft (brewing, masonry,
baking...) if they chose a role that has it, or after trying it 3 times (good or bad). Until then a first
try works half the time; otherwise it's a clumsy mishap that hurts nothing but their pride. Knowing a craft
means something good comes of it - not coins: the only money is Aldric's thin purse and the peddler's.
Being caught or picking a fight means a night in the stocks by the shack; going for Aldric means he sits on
you until you calm down.

## Their own builds

People can build their own small things, with his leave:

- "I want to start a vegetable garden behind my house" (or a hut, a beehive, a bread oven, a workbench, a
  stall) goes to his court as a request. He says yes or no when he holds court. If nobody answers within a
  day, nobody stopped them, so they start anyway.
- Granted, it's **their** project, on a lot by their home. They put in a couple of hours every evening, and
  five more on any day they comment about it ("I spend the evening on my garden, pulling weeds"). In 3D they
  work on it after they get home.
- Finished, it stands with their name on it ("@rowan's garden"), they get a reply and the credit, and it does
  what its kind does: a garden feeds people, a hut gives a bed (they move out of their tent), a workbench
  makes work a little faster.
- **What keeps it sane at scale:** one build per person at a time, and only tiny or small things. Anything
  bigger ("a great stone tower") becomes a petition for the king to build.

## Food and rough nights

- Everyone eats one food a day. Food buildings (a garden, a fish trap) produce some every morning. Food
  spoils if there's more than the stores can hold, so a storehouse helps.
- A hungry night drops everyone's mood. After three in a row, the unhappiest tenth pack up and leave.
- Now and then the night bites:
  - wolves at the food (if there's no storehouse)
  - a storm on a half-built frame
  - frost on the tents
  - a soaked woodpile

## Stages, the crown, and Skarn

- **Stages:** alone, then hamlet (1+), village (10+), town (50+), city (200+). The court turns up as the
  place grows: Pip the jester with the first travellers, and Steward Wendell at the village stage (who
  starts skimming the treasury, of course).
- **Nobody calls him king until he's crowned.** At 10 settlers they vote: CROWN or NOTYET. If it's not
  yet, they vote again a week later. The Reckoning on day 30 only happens if he has a crown to lose.
- **Skarn the Red** comes once there's something worth raiding: 15 settlers and day 9 or later. There are
  rumours of a black island drifting in the clouds to the north, then one morning it's there, with fires on
  it. His raiders cross on hide gliders.
- The corners of the settlement are Riverside, Hillfoot and Woodedge, and that's where raids land.

## What the post shows

The caption carries a status line, then the usual call to action:

> 🏝️ 6 settlers · 3 beds (0 free) · 3 in tents · stores: 21 wood, 5 thatch, 14 food

The call to action asks people to follow (and walk into Emberfall today), tell their character what to do, send
Aldric something, or suggest what he should build. A quiet day alone still has a story: a summary just
before the post ("Aldric's day: he gathered 18 wood and 6 thatch and put 4 hours into building. The small
cottage is 60% done.").

## Settings (`content/balance.yaml`)

| Setting | Default | |
|---|---|---|
| `frontier_gold` | 15 | coins at the start |
| `frontier_passive_hours` / `frontier_work_hours` | 1.5 / 5 | a settler's hours on an ordinary day / when they comment |
| `frontier_crown_at` | 10 | settlers before the crowning vote |
| `frontier_warlord_pop` | 15 | settlers before Skarn comes |

## Try it

```
./kingdom demo                                                         # 50 people, ten days in: watch their day, live
./kingdom test --scenario scenarios/frontier.yaml --reports            # a slow-growing account, 30 days
./kingdom test --scenario scenarios/frontier_viral.yaml --reports      # hundreds walk in during week 2
OLLAMA_URL=http://192.168.1.23:11434 ./kingdom test --scenario scenarios/frontier.yaml --king llm --days 8 --reports
```
