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

**The models:** buildings, building stages and scaffolding, ruins, tents and store piles come from the free
KayKit *Medieval Hexagon Pack* by Kay Lousberg (CC0 - free for any use; www.kaylousberg.com), in
`viewer/assets/kaykit/` with its licence.

**The people are pips** (`viewer/js/people.js`): little faceted gumdrops in their role's colour, a shade
different each, with two bead eyes, floating nub hands, stubby feet and a hat that says what they do (a straw
hat for farmers, a helmet for guards, a hood for thieves and monks, a pointy hat for scholars, a tuft of hair
for anyone without a trade). They hop when they walk and squash when they land, swing tools, stoop to dig,
sit by the fire and blink. Aldric is a slightly bigger royal-blue pip with a moustache and a battered hat
(a crown once he's crowned). The crowd is the same pips drawn instanced, so hundreds cost a few draw calls.
A house is picked by what it's called (a smithy,
a tavern, a mill, a chapel...) and then by its shape, scaled to its lot; people's own builds use red roofs,
the king's blue. The shack, fire pits, walls, roads and bridges are still hand-built. `?assets=off` shows
the hand-built kit for everything.

**The look:** in the spirit of Thronefall, but a world you can walk around in: clean flat colours, no
textures, low-poly faceted ground, chunky trees (a few already turning orange), golden thatch and cream
walls, turquoise water, a soft cyan sky, warm sun and soft blue shadows. Bushes, flowers, pebbles and lone
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
| `overview` | the settlement: the field, the woods, the hill, the road |
| `the_field` | where the buildings go up |
| `the_camp` | the tents, filling as people arrive and emptying as houses finish |
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
