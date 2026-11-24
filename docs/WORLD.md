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
| **Director** (2) | sit back: it cuts between Aldric up close, wide shots of the island, settlers at work, and whatever's happening (anything with drama gets the camera) |
| **Walk around** (3) | first person at eye height: WASD or arrows, drag (or click to grab the mouse) to look, Shift to run. You walk on the real terrain, through the grass, up to the buildings |
| **From above** (4) | straight down like Prison Architect: drag or WASD to pan, scroll to zoom |
| **Free camera** (5) | orbit anywhere |
| **Recorders** (6, R) | stand where each recorder stands |

Space plays or pauses. The arrows (or `[` `]`) change day; with "keep playing into the next day" ticked,
it plays a whole run straight through. H hides the HUD. Hover over anything (a building, a person, a pile)
to see what it is. Click a line in the feed to jump there.

## What you see

**The town** (`viewer/js/buildings.js`) is a grid of blocks round the keep, with dirt streets between them.
Every person's house is one of a few hundred instanced boxes - an orange-walled hut with a plank roof, then a
cottage with a chimney, a house with a garden, a two-storey townhouse with a blue roof, by the gold they've put in.
Every other building has its own silhouette you can read from across the island: fenced crop beds (a barn, then a
windmill whose sails turn when it's running) for the farm, a shed and a big vat for the brewery, a striped beer tent
then a tavern with a sign then a long beer hall, a stilted watchtower, a white chapel with a bell tower, market
stalls under striped awnings, rows of vines, a cellar door in a grassy bank, the keep growing from a shack to a hall
to a stone keep to a castle. Running buildings smoke and their windows glow at night; idle ones sit dark and sag
when neglected. Going up: a footing, walls rising with the day's work, poles round it, the roof last. Hover over
anything: a building says who's working it today ("running today: 10 farmers (needs 10)").

**The people** (`viewer/js/people.js`) are tiny: a round head on a little body, one of three shapes, coloured by
what they do. Everyone is drawn instanced - two draw calls for the whole town. They keep their day: out of the door
at six, breakfast on the doorstep, off to today's job (round the building, along the field rows, round the
scaffolding, wandering the streets on odd jobs), lunch there, the tavern or the stage in the evening, supper round
the square's fire or at home, in at half past nine. When the simulation says two people had a moment, one walks
over, they turn to each other and do it, with a bubble ("shares bread", "argues", "lends a hand"). Hover over anyone
for their job today and their whole day. Aldric (bigger, blue, a crown once he's crowned) and his court are drawn as
themselves.

**The look:** Thronefall's: deep teal grass, warm orange timber and plank roofs, cream stone and cream cliffs under
the island, lime-green pines, bright blue water, warm sun and navy shadows. No textures, low-poly faceted ground. Bushes, flowers, pebbles and lone
trees dot the meadow. `?style=textured` brings back the older painted look (planks, stones, thatch
textures, dense grass).

- **The island:** Emberfall floats above a sea of low-poly clouds. The ground is the island's own shape: the old
  round island plus every piece of land that has risen from the clouds since (each with its own tint and trees -
  a whole silver forest on the silver grove). Under the grass hangs the island's rocky red-brown underside,
  narrowing to a point, with loose rocks drifting below. The river runs off the edge at both ends in
  waterfalls; the old road ends at a wooden landing jutting out over nothing. Clouds drift past at every height.
  When new land rises during live play, the view rebuilds the island around everything else.
- **The land:** the field and the shack sit flat, the rocky hill is a crag (cliffs all round, a flat top and one
  long grassy ramp down toward the field - where a castle belongs), the river cuts a bed with sandy banks, and
  the land rounds off at the rim.

## Recorders: watching the town grow

The recorders are fixed cameras listed in `content/recorders.yaml`:

| Recorder | What it watches |
|---|---|
| `the_island` | the whole floating island from out in the clouds - the best one for watching it grow |
| `overview` | the settlement: the town, the woods, the hill, the road |
| `the_town` | the streets round the keep, filling with houses and buildings |
| `the_square` | supper round the fire (19:30) |
| `top` | the plan of the town, straight down |
| `king` | over Aldric's shoulder |

Each one has a position, a target, a lens and the times of day it takes a picture.

`./kingdom record`:
1. Opens the viewer in headless Chrome.
2. For every day of the run and every time a recorder lists, shows that moment from that recorder and saves
   a frame (`runs/<run>/recordings/<recorder>/00001_day001_0800.png`...).
3. Stitches each recorder's frames into `recordings/<recorder>.mp4`.

A month from the `the_town` recorder is the whole story: a shack, then a street of little houses, a farm, a beer
tent, block after block, the keep becoming a castle.

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
