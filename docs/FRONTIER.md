# The frontier: a kingdom from nothing

The living world now starts on the frontier (`start: frontier`, the default). Aldric isn't a king. He's a
man with a leaky one-room shack in a field, a dull axe and 15 coins. Everything gets built by hand,
starting with his own. The old castle start is still there (`start: kingdom` in `content/balance.yaml` or a
scenario's `balance:`).

Code: `city/living/frontier.py` (the land, materials, pricing, building, the road, labour, food, stages)
and `city/living/frontier_tools.py` (what he can do, what he sees, his rule-based instincts).

## The land

| Place | What's there |
|---|---|
| the shack | a straw mat, a cold fire pit, a roof that leaks |
| the field | grass for thatch, wild onions, room to build |
| the woods | wood, vines and bark for rope, mushrooms |
| the river | clay, reeds, fish |
| the rocky hill | stone |
| the old road | where travellers (and the peddler) come from |

The places grow: a big gathering place he builds (a meeting hall, a tavern) becomes somewhere you can walk
to, and the tent camp appears the first time people have nowhere to sleep.

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
- The old weekly road is still there with `frontier_arrivals: weekly`: followers wait on the road, a
  traveller warns him three days before, and everyone arrives together on arrival day (day 7, then every 7
  days). On the road they can only send things ahead, write him a letter, or choose who they'll be.

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
  rumours, then smoke in the north a few days later.
- The corners of the settlement are Riverside, Hillfoot and Woodedge, and that's where raids land.

## What the post shows

The caption carries a status line, then the usual call to action:

> 🏚️ 6 settlers · 3 beds (0 free) · 3 in tents · stores: 21 wood, 5 thatch, 14 food

The call to action asks people to follow to set off for Emberfall, tell their character what to do, send
Aldric something, or suggest what he should build. A quiet day alone still has a story: a summary just
before the post ("Aldric's day: he gathered 18 wood and 6 thatch and put 4 hours into building. The small
cottage is 60% done.").

## Settings (`content/balance.yaml`)

| Setting | Default | |
|---|---|---|
| `start` | frontier | or `kingdom` for the castle start |
| `frontier_gold` | 15 | coins at the start |
| `frontier_arrivals` | instant | `weekly` for the old road: everyone arrives together on arrival day |
| `frontier_arrival_every` | 7 | days between arrival days (weekly only) |
| `frontier_warn_days` | 3 | how early the traveller warns him |
| `frontier_passive_hours` / `frontier_work_hours` | 1.5 / 5 | a settler's hours on an ordinary day / when they comment |
| `frontier_crown_at` | 10 | settlers before the crowning vote |
| `frontier_warlord_pop` | 15 | settlers before Skarn comes |

## Try it

```
./kingdom test --scenario scenarios/frontier.yaml --reports            # a slow-growing account, 30 days
./kingdom test --scenario scenarios/frontier_viral.yaml --reports      # hundreds on the road in week 2
OLLAMA_URL=http://192.168.1.23:11434 ./kingdom test --scenario scenarios/frontier.yaml --king llm --days 8 --reports
```
