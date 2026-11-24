# Emberfall: a kingdom that grows on People Power

Aldric starts alone in a leaky shack on an old floating island above the clouds. Everyone who follows walks in
the same day and gets a little house of their own on the town's streets. From then on the kingdom runs on its
people: **every follower works a shift a day**, and what gets built - and whether it runs - depends on how many
turn up. The goal is growth. (The code still calls this "the frontier"; it's the only game.)

Code: `city/living/frontier.py` (People Power, buildings, gold, wants, houses, stages, the island),
`content/buildings.yaml` (what can be built: crews, work, tiers by gold - tune it there),
`city/living/frontier_tools.py` (what Aldric can do, what he sees, his rule-based instincts),
`city/living/routine.py` (everyone's day and the little things between people) and `city/living/wonders.py`.

## People Power

- **Everyone works one shift a day**, whether or not they say anything. People who **comment** work an extra
  shift that day (two), and what they say steers where: "I'll help at the farm", "I want to be a brewer", "I help
  build the tavern". Comments don't control exactly what you do - they nudge (and the nudge sticks a little).
- **A building only runs if its crew turns up.** A farm needs 10 people a day, a brewery 4, a tavern 3 (finer
  versions need more). Short of that it stands **idle** that day - it earns nothing, serves nobody, and if it
  stays idle it falls into **disrepair**. Some need others running: no beer from an idle brewery, no tavern.
- **A building only gets built by builders.** Each has a number of person-days of work: a farm is 24, a tavern
  36. Thirty-six people finish a tavern in a day; one person takes five weeks. Nobody works on the blacksmith,
  the blacksmith never goes up. It's counted once a day, so a day at the least.
- **Who goes where**, each day: crews for the standing buildings first (most needed first, and the ones Aldric
  rallied today): people who asked for that work, then people who've become it, then anyone free; then
  builders on what's going up; whoever's left does odd jobs about town (and tells Aldric there's room for
  something new). The count is in the evening (18:00) and goes in the feed:
  > People Power today: 64 shifts (12 from people who spoke up). Ran: a vegetable patch (10/10), a brew shed (4/4).
  > Stood idle: a beer tent (0 of 3 came). Going up: a forge 89%. +29.9 gold.
- **Becoming what you do.** Four days running at the same kind of work and you're Emberfall's newest farmer,
  brewer, barkeep or builder - you hear about it, and that's where you go first from then on.

## Gold

The one thing you can count. Running buildings earn it (a market more than a well), happy people pay a little
tax, odd jobs pay a little, and followers can give theirs ("I leave 50 coins at Aldric's door" - only what their
character actually has). **Building costs no gold - but the gold Aldric puts into a building decides which one you
get**: the same work makes a beer tent (0 gold), a tavern (50) or a beer hall (250). Some only exist above a price
(a wine cellar starts at 60). Gold put into a standing building later makes it the next version up - and that
takes builders again (half the work per step).

People earn too: **a coin a shift**, theirs to keep. With it they can do up their own house ("I put a new roof on
my house"): a hut, then a cottage (25), a house with a garden (80), a fine townhouse (250).

## What the people want

Food and water from the start, then a pint (8 people), somewhere to drink together (10), proper tools (12), fresh
bread and safety at night (15), music and somewhere to pray (20), a market (30), wine (40), a school (60), hot baths
(80). A share of the people want each one, and **running** buildings serve it (a farm feeds 25, more as it grows).
How well the wants are met is the town's **happiness**: it drifts everyone's mood, it's the tax, and the
unhappiest don't always turn up for their shift. Aldric sees what's missing and decides what's next.

## The town

Every house is a lot on a grid of streets spiralling out from the keep, nearest first; every building takes a
whole block. Lots are kept forever, so the town grows ring by ring like a real one (it skips the river, the road,
the crag and the island's edge, and only eats into the woods when there's nowhere else). Once the town is big, new
streets are rowhouses. The square next to the keep has the fire the first streets eat supper at. A palisade, when
it's built, rings the whole town.

## Aldric decides, the people build

His tools: **plan** (what gets built next and how much gold goes into it), **invest** (gold into a standing
building), **rally** (everyone's backs into one thing today: it gets its people first), **build** (work a shift on
it himself - two, the way he does it), plus talk, proclaim, hold court, summon, appoint and decree as the place
grows. At most a few things go up at once (one more for every 20 people). On his instincts (no model) he builds
what the people want most and have least of, the cheapest prerequisite first, and never a twin of a building that's
standing idle (that needs people, not a twin). The keep is his own: the shack, then Aldric's hall (60 gold), the
keep (300), the castle (1,200).

## Everyone's day, and the little things in it

Everyone keeps the same simple day, each person a few minutes earlier or later than the next:

| time | what | where |
|---|---|---|
| 06:00 | up | at home |
| 06:30 | breakfast | on the doorstep (neighbours over the fence) |
| 07:30 | work | today's job: the farm, the brewery, a building site, odd jobs about town |
| 12:00 | lunch | where they work |
| 13:00 | work | |
| 17:30 | their own time | the tavern, the stage or the chapel once there is one; a friend's door; fishing |
| 19:00 | supper | the square for the first streets, at home further out |
| 21:30 | bed | home |

Every half hour, people in the same place bump into each other and something small happens: they share bread,
swap gossip (about whatever's really going on: a wonder, new land, a building that'll never get finished, how much
gold Aldric is sitting on), help hold a wall straight, show each other how to pour a pint, argue about the well,
catch someone napping under the scaffolding, start a song. Every pair keeps a score (comments feed it too), and it
adds up into **friends**, **inseparable**, **a feud** and **a fight** - stories that happen while nobody's
commenting. The bard sees each commenter's people, so a friend can turn up in their reply and a rival in their way.

## The island grows

New land rises out of the clouds at the rim every time Emberfall grows a stage (hamlet, village, town, city), when
the island event "the ground is shaking at the edge" is helped along, and when the director decides something
should. Everyone hears about it, and the 3D view rebuilds the island around it.

## Wonders: real, and never free

The island says "yes, and..." to wild claims. "I ride my dragon in": there IS a dragon - maybe a hatchling the size
of a cat that eats three gold of food a morning. Each wonder belongs to whoever conjured it, is in what the narrator
sees from then on, and costs something every morning (hungry ones eat gold, mischief knocks a building about, noisy
ones wake the street). One conjuring per person every few days.

## Stages, the crown, and Skarn

alone -> hamlet (1+) -> village (10+) -> town (50+) -> city (200+). The jester turns up at the hamlet stage, the
steward at the village. At 10 people the people vote on crowning Aldric. Skarn the Red camps on a crag to the north
once the place is worth raiding; a raid that gets through costs gold and batters a building.

## Try it

```
./kingdom demo                                                         # 50 people, ten days in: watch it live
./kingdom demo --people 200 --days 20
./kingdom test --scenario scenarios/frontier.yaml --reports            # a slow-growing account, 30 days
./kingdom test --scenario scenarios/frontier_viral.yaml --reports      # hundreds walk in during week 2
```
