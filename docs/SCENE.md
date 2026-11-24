# The scene file: what the 3D view reads

Every post on the frontier writes `dayNNN.scene.json` next to the report (`--reports`, and always in
`live`/`day`). It holds the 24 hours the post covers, with coordinates. The renderer reads **only** this
file: no save files, no Python. Code: `city/living/scene.py`. Schema name: `scene/2`; breaking changes
bump it.

```
./kingdom test --scenario scenarios/frontier_viral.yaml --reports
./kingdom serve                  # -> http://localhost:8765, the 3D world playing the run
```

The 3D world in `viewer/` reads these files: `./kingdom serve`. See [WORLD.md](WORLD.md) for the viewer,
its cameras and the recorders that turn a run into timelapses.

## Coordinates and time

- Metres. `x` is east and `z` is north (a ground plane); height is `y`. The shack is at `[0, 0]`. In
  three.js, the viewer maps world `(x, z)` to `(x, 0, -z)`.
- Time is in **world minutes** since the kingdom began: day `d` starts at `(d - 1) * 1440`. `start`/`end`
  bracket this post (it closes at 19:00, `post_hour`). Every `t` in the file is on that clock.
- Rotations (`rot`) are in degrees about the vertical axis: 0 or 90 for now.

## Top level

| Key | What |
|---|---|
| `schema`, `city`, `day`, `start`, `end`, `minutes_per_day`, `post_hour` | which post this is |
| `settlement` | `stage` (alone/hamlet/village/town/city), `crowned`, `settled`, `gold`, `happiness` 0-1, `houses`, `power` (yesterday's People Power count: `{shifts, people, extra, ran, idle, built, building, odd, gold}`), `wants` (`{want: {demand, supply, met, line}}`) |
| `terrain` | `ground.size`, `island {pos, r, lobes: [{id, name, pos, r, day}]}` (the old island and the land risen since), `river {path, width}` (the viewer carries it on to the rim at both ends), `road {path, width}` (to the rim), `hill {pos, r, height}`, `woods {pos, r}`. Paths are lists of `[x, z]` |
| `town` | `block` (13 m: 9 of lots and a 4 m street), `lot`, `streets` (`[[x1, z1], [x2, z2]]` segments round every block in use), `square` (the fire), `radius` |
| `places` | `{id, name, pos, r}`: the island's places, plus every building (its kind's name) |
| `trees`, `stones` | scenery: the woods `[x, z, scale]` and loose stones on the hill (`trees_felled`/`stones_hauled` are always 0 now) |
| `samples` | an hourly snapshot `{t, settled, gold, houses, progress {project id: 0-1}}`, so scaffolding rises through the day |
| `buildings` | see below. Includes the keep (`id: b0`) |
| `projects` | what's going up (or being done up), same fields plus `progress` 0-1, `need` (person-days), `builders` today, `upgrade_of` |
| `houses` | everyone's house: `[x, z, rot, tier, size, handle, t]` - rot 0 faces north, 180 south; tier 0 hut, 1 cottage, 2 with a garden, 3 townhouse |
| `weather` | `[{t, weather}]`: the weather in effect from `t` |
| `actors` | `king`, `court`, `settlers`, `crowd` (below) |
| `events` | every moment in these 24 hours: `{t, time, who, place, pos, text, drama 0-3, public, kind, handles}` |
| `routine` | `{day: [{from, what, where}], commons: [x, z]}`: the shape of everyone's day (minutes after midnight) and where the fire is |
| `encounters` | the little things between people: `{t, a, b, kind, anim, label, text, what}` - `a` and `b` are handles; for about 24 minutes from `t` they face each other and do `anim` (talk, eat, sing, dance, work, sit) with `label` in a bubble |
| `shots` | the post's three best moments: `{t, target [x, z], distance, text}` (the camera's to-do list) |
| `today` | `built` (names finished today), `arrived` |

## Buildings and projects

```json
{"id": "b5", "kind": "tavern", "shape": "tavern", "name": "a beer tent", "tier": 0, "tiers": 3, "state": "standing",
 "pos": [-26.0, -26.0], "size": [9, 9], "rot": 90, "running": true, "crew": 3, "needs_crew": 3, "job": "barkeep",
 "condition": 1.0, "disrepair": false, "look": "a striped tent, three barrels and some benches", "built_t": 4320,
 "place": "tavern"}
```

- `kind` is the catalog entry (`content/buildings.yaml`), `shape` the model family the viewer draws: `keep`,
  `farm`, `well`, `brewery`, `tavern`, `bakery`, `smithy`, `tower`, `wall` (the palisade: a ring with `radius`),
  `chapel`, `stage`, `market`, `vineyard`, `cellar`, `barracks`, `school`, `baths`. `tier` picks the version (a
  beer tent, a tavern, a beer hall) - grander each step.
- `running`: its crew turned up today (it smokes, it glows, its windmill turns). Not running: dark. `disrepair`:
  it's been idle so long it sags.
- Every building has a whole block (`size` 9 x 9, `rot` in degrees); lots are kept forever and never overlap.
- `built_t` is the minute it was finished; before that, show scaffolding.

## Actors

**King**:
- `{name, crowned, start {place, pos}, needs, becoming, track}`.
- Each track entry is `{t, place, pos, anim, dur, tool, text}`: at `t` he starts doing `anim` at `pos` for
  `dur` minutes.
- For `anim: "walk"` he walks from the previous entry's `pos` to this one over `dur` minutes; for anything
  else, he steps there in a few seconds.
- Between entries he idles. At 23:00 there's a `sleep` entry at the shack.

Animations so far:

| Group | Animations |
|---|---|
| moving | `walk`, `run`, `swim` |
| working | `hammer`, `dig`, `forage` (fields), `fish`, `chop` |
| building | `hammer` |
| talking | `talk`, `speak`, `judge`, `sing`, `trade` |
| sitting | `sit`, `read`, `eat`, `craft`, `cook` |
| other | `think`, `pray`, `dance`, `sleep`, `idle` |

**Court**: `{id, name, pos}` for whoever has turned up (the jester, the steward...), standing where he holds
court.

**Settlers**:
- Everyone (up to 1,500; the ones in today's story and encounters first):
  `{handle, name, role (their profession), job (today's, in words), home_pos, door, work, work_pos, mood,
  condition, schedule}`. `work` is where People Power sent them today: `b:<building id>`, `p:<project id>`
  (building it) or `square` (odd jobs about town).
- `schedule` is their day: `[{from, to, what, where, pos, with}]` - `what` is up / breakfast / work / lunch /
  work / free / supper / sleep; `where` is `home`, a place id, `b:`/`p:` (work, or the tavern in the evening),
  `square` or `visit` (with: a friend); `pos` is where that is (`home` is their front door). Each person's day is
  shifted up to 15 minutes either way.
- `condition` is `wounded` or `jailed` (not shown either way).

**Crowd**: empty now - everyone is drawn from `settlers`.

## What's still simple (and where it would grow)

- Settlers' own-words moves are in `events` with `handles` (they stop and talk where it happened). A later
  version can turn "@a robbed @b" into a walk and a chase.
- The warlord lives off the map (the north). His moments are in `events`; raids could get a march path.
- The castle start (`start: kingdom`) has no coordinates; the scene file is frontier-only.
