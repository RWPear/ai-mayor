# The 3D world and the recorders

Emberfall plays back in the browser in 3D, from the scene file every post writes (`docs/SCENE.md`).
Code: `viewer/` (three.js, no build step). Python side: `city/recorder.py`.

```
./kingdom test --scenario scenarios/frontier_viral.yaml --reports     # make some days
./kingdom serve                                                       # open http://localhost:8765
./kingdom record                                                      # timelapse videos, one per recorder
./kingdom view                                                        # export a static folder to host anywhere
```

`serve` listens on every interface, so on brainbox you can open `http://192.168.1.23:8765` from your laptop
or phone.

## Being in the world

| Camera | How it works |
|---|---|
| **Follow Aldric** (1) | the camera stays with him; drag to look around him, scroll to zoom |
| **Director** (2) | sit back: it cuts between Aldric up close, wide shots of the valley, settlers at work, and whatever's happening (anything with drama gets the camera) |
| **Walk around** (3) | first person at eye height: WASD or arrows, drag (or click to grab the mouse) to look, Shift to run. You walk on the real terrain, through the grass, up to the buildings |
| **From above** (4) | straight down like Prison Architect: drag or WASD to pan, scroll to zoom |
| **Free camera** (5) | orbit anywhere |
| **Recorders** (6, R) | stand where each recorder stands |

Space plays or pauses. The arrows (or `[` `]`) change day; with "keep playing into the next day" ticked,
it plays a whole run straight through. H hides the HUD. Hover over anything (a building, a person, a pile)
to see what it is. Click a line in the feed to jump there.

## What you see

**The models:** buildings, building stages and scaffolding, ruins, tents and store piles come from the free
KayKit *Medieval Hexagon Pack* by Kay Lousberg (CC0 - free for any use; www.kaylousberg.com), in
`viewer/assets/kaykit/` with its licence.

**The people are pips** (`viewer/js/people.js`): little faceted gumdrops in their role's colour, a shade
different each, with two bead eyes, floating nub hands, stubby feet and a hat that says what they do (a straw
hat for farmers, a helmet for guards, a hood for thieves and monks, a pointy hat for scholars, a tuft of hair
for anyone without a trade). They hop when they walk and squash when they land, swing tools, stoop to dig,
sit by the fire and blink. Aldric is a slightly bigger royal-blue pip with a moustache and a battered hat
(a crown once he's crowned). The crowd is the same pips drawn instanced, so hundreds cost a few draw calls.
`?people=kit` brings back the KayKit humans (*Character Pack: Adventures*, still in the repo). A house is picked by what it's called (a smithy,
a tavern, a mill, a chapel...) and then by its shape, scaled to its lot; people's own builds use red roofs,
the king's blue. The shack, fire pits, walls, roads and bridges are still hand-built. `?assets=off` shows
the hand-built kit for everything.

**The look:** in the spirit of Thronefall, but a world you can walk around in: clean flat colours, no
textures, low-poly faceted ground, chunky trees (a few already turning orange), golden thatch and cream
walls, turquoise water, a soft cyan sky, warm sun and soft blue shadows. Bushes, flowers, pebbles and lone
trees dot the meadow. `?style=textured` brings back the older painted look (planks, stones, thatch
textures, dense grass).

- **The valley:** Emberfall sits on a broad valley floor. A mountain range climbs to snow behind it in the
  north, with pine forests on its lower slopes; a broken ridge walls the west, and the river comes down
  through a gorge in it; low hills roll away east; the valley opens south, where the old road leaves through
  a gap and the river widens into a lake. Near the field, the rocky hill is a crag: cliffs all round, a flat
  top, and one long grassy ramp down toward the field. It's where a castle belongs.
- **The land:**
  - real terrain: the field and the shack sit flat, the rocky hill rises with outcrops, and the river cuts a
    bed with sandy banks
  - the country rolls out to blue hills on the horizon
  - tufts of grass sway in the wind; they grow everywhere except paths, the river, building lots and the
    hilltop
- **Paths wear in where people walk:** settlers between home and work, Aldric between the places he keeps
  going. The more feet, the wider and browner.
- **The woods thin out** as wood is cut (the trees nearest the shack go first, leaving stumps). The loose
  stone on the hill disappears as it's hauled.
- **Buildings:** every shape from the simulation, built from stone plinths, timber-framed plaster, plank,
  brick and slate, thick thatch, doors, shuttered windows and chimneys.
  - shoddy ones lean
  - projects stand as scaffolding (poles, ledgers, a ladder, stacked planks) and rise with their progress
    through the day
  - finished buildings appear at the moment they were finished
  - collapses leave scorched ruins
  - Aldric's fixes show on the shack as he makes them: a proper thatched roof, a door that shuts, a chimney;
    his fire pit, drying rack or bench stand beside it
  - people's own builds stand by their homes, with their name in the tooltip
  - the crowned king's hall flies his banner
- **The camp:** canvas tents in rows by the road, with campfires.
- **The stores:** heaps by the shack (or the storehouse): log stacks, stone, clay, thatch bundles, sacks and
  crates. They grow and shrink hour by hour.
- **People, low-poly:**
  - a six-sided tunic in their role's colours, a big faceted head, block legs that step when they walk, and
    little floating hands (a nod to Prison Architect)
  - hats and tools say who they are and what they're doing: Aldric's battered hat becomes a crown when he's
    crowned; there's a smith's apron, a guard's helmet, a thief's hood, a farmer's straw hat, a wizard's
    point
  - they chop, mine, dig, hammer, fish, forage, eat, sit, talk, sleep and dance
  - settlers walk to work at about 7 and home at about 7 in the evening (each a little early or late).
    At work they go to real spots: a standing tree in the woods, a rock on the hill, a place on the river
    bank, a side of the scaffolding, a row in a garden. They work there an hour or so, facing it, then walk
    to the next, and stop for a bite at midday. Only so many fit on one building (the same crew limit the
    simulation uses), and each garden row has one person. They only bob when they walk.
  - people with their own build work on it in the evening, by their home
  - people in tents sit around the camp fires after dark
  - the jester strolls about the court, stopping to perform
  - whoever is in a story that day walks to where it happened
- **Time and weather:** sun and shadows across the day, warm light at dawn and dusk, stars at night,
  clouds, rain, fog and wind. Windows glow at night, chimneys smoke in the morning and evening, and
  campfires and forges light their surroundings.

Quality: `?quality=high` (the default on a computer) adds ambient occlusion and bloom, sharper shadows,
denser grass and a bigger crowd. `?quality=low` (the default on phones) keeps it smooth.

## Recorders: watching the town grow

The recorders are fixed cameras listed in `content/recorders.yaml`:

| Recorder | What it watches |
|---|---|
| `overview` | the whole valley |
| `the_field` | where the buildings go up |
| `the_camp` | the tents, full after arrival day and emptying as houses finish |
| `the_woods` | the trees coming down |
| `top` | the plan of the place, Prison Architect style |
| `king` | over Aldric's shoulder |

Each one has a position, a target, a lens and the times of day it takes a picture.

`./kingdom record`:
1. Opens the viewer in headless Chrome.
2. For every day of the run and every time a recorder lists, shows that moment from that recorder and saves
   a frame (`runs/<run>/recordings/<recorder>/00001_day001_0800.png`...).
3. Stitches each recorder's frames into `recordings/<recorder>.mp4`.

A month from the `overview` recorder is the whole story: a shack in a field, the woods shrinking, paths
wearing in, the camp filling and emptying, apartment blocks going up.

| Option | |
|---|---|
| `--recorders overview,top` | only these |
| `--every 30` | a frame every 30 game minutes from 06:00 to 20:00, for a smooth day-by-day timelapse |
| `--first 1 --last 7` / `--day 8` | some days (`--day` adds to the existing frames: use it after each post) |
| `--size 1920x1080 --fps 12` | the video |
| `--quality low` / `--cpu` | faster, or no GPU (software rendering: slow, but works anywhere) |

To add a recorder, add an entry to the YAML. Positions are `[x east, height, z north]` in metres, with the
shack at 0, 0. Use the viewer's Recorders mode to check the framing.

**Setup on brainbox** (once): `pip install playwright && python -m playwright install chromium`, and
`sudo apt install ffmpeg`. With the GPU, a 1280x720 frame takes about a second. Without it (`--cpu`), it's
tens of seconds.
