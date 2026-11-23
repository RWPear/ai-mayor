# The scene file: what the 3D view reads

Every post on the frontier writes `dayNNN.scene.json` next to the report (`--reports`, and always in
`live`/`day`). It holds the 24 hours the post covers, with coordinates. The renderer reads **only** this
file: no save files, no Python. Code: `city/living/scene.py`. Schema name: `scene/1`; breaking changes
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
| `settlement` | `stage` (alone/hamlet/village/town/city), `crowned`, `settled`, `on_road`, `beds`, `free_beds`, `tents`, `next_arrival`, `know` (techniques), `stores` {material: n}, `gold` |
| `terrain` | `ground.size`, `river {path, width}`, `road {path, width}`, `hill {pos, r, height}`, `woods {pos, r}`. Paths are lists of `[x, z]` |
| `places` | `{id, name, pos, r, resources}`: the base six, plus big gathering places he builds and `camp` once there are tents |
| `trees` | standing trees at the end of the post `[x, z, scale]`. `trees_all` is every tree in the order they get cut (nearest the shack first); `trees_felled` is how many are down. Draw `trees_all[felled:]` standing and `trees_all[:felled]` as stumps |
| `stones` | loose stones on the hill. `stones_all` / `stones_hauled` work the same way |
| `samples` | an hourly snapshot `{t, felled, hauled, tents, settled, stores, progress {project id: 0-1}}`, so the day can change as it plays (trees falling, stores growing, scaffolding rising) instead of jumping to how it ended |
| `trails` | worn paths `{from [x, z], to [x, z], wear}`: settlers between home and work, Aldric between places. More wear = a wider, browner path |
| `peddler` | `{until, goods, pos}` while the peddler's cart is on the road |
| `buildings` | see below. Includes the shack (`id: b0`) and ruins |
| `projects` | buildings under construction, same fields, `state: "scaffold"`, `progress` 0-1 |
| `tents` | tent positions `[x, z]` (about one per two people in tents) |
| `piles` | the stores as heaps: `{material, amount, pos}` (by the shack, or by the storehouse once there is one) |
| `weather` | `[{t, weather}]`: the weather in effect from `t` |
| `actors` | `king`, `court`, `settlers`, `crowd` (below) |
| `events` | every moment in these 24 hours: `{t, time, who, place, pos, text, drama 0-3, public, kind, handles}` |
| `shots` | the post's three best moments: `{t, target [x, z], distance, text}` (the camera's to-do list) |
| `today` | `built` (names finished today), `arrived` |

## Buildings and projects

```json
{"id": "b4", "name": "a tall apartment building of stone and timber", "shape": "apartments", "kind": "housing",
 "scale": "huge", "pos": [61.2, 18.0], "size": [18, 14, 16], "rot": 0, "state": "standing",
 "quality": "good", "material": "mixed", "look": "five storeys of timber over a stone ground floor",
 "built_day": 17, "capacity": 90, "residents": ["handle1", "handle2"]}
```

- `shape` picks the model family:
  - homes: `shack`, `hut`, `cottage`, `longhouse`, `rowhouses`, `apartments`
  - food and storage: `plot`, `fish_trap`, `shed`, `storehouse`
  - work and gathering: `workshop`, `hall`
  - defense: `tower`, `wall_ring` (a palisade around the settlement, with `radius`)
  - paths and water: `well`, `bridge`, `jetty`, `road`
  - other: `ruin` (with `of`: what it was meant to be)
- `size` is `[width x, depth z, height]` in metres. Lots never overlap and never sit on the river or the road.
- `state`: `standing`, `scaffold` (a project) or `ruin`. `quality: "shoddy"` buildings should **lean**.
- `look` is the model's one-line description. Use it for variation now, or for generated assets later.
- A project's lot is chosen when it's planned and is the building's lot when it's finished: scaffolding
  stands exactly where the house will.
- Buildings have `built_t`, the minute they were finished (ruins have `t`); before that, show scaffolding.
  Projects have `started_t` and `progress_at` (`[[t, progress], ...]`, hourly).

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
| gathering | `chop` (wood), `mine` (stone), `dig` (clay), `cut` (thatch), `twist` (rope), `forage`, `fish` |
| building | `hammer` |
| talking | `talk`, `speak`, `judge`, `sing`, `trade` |
| sitting | `sit`, `read`, `eat`, `craft`, `cook` |
| other | `think`, `pray`, `dance`, `sleep`, `idle` |

**Court**: `{id, name, pos}` for whoever has turned up (the jester, the steward...), standing where he holds
court.

**Settlers**:
- Everyone in today's story, the appointed officers, and about 20 others:
  `{handle, name, role, home {building | tent}, home_pos, work, work_pos, mood, condition, schedule}`.
- The schedule is simple for now: at work 07-19, at home 19-07.
- `condition` is `wounded` (lying down) or `jailed` (not shown).

**Crowd**: `day {place: count}` and `night {homes, camp}`, for drawing everyone else as background figures.

## What's still simple (and where it would grow)

- Settler schedules are coarse (work/home). Their own-words moves are in `events` with `handles`. A later
  version can turn "@a robbed @b" into a walk and a chase.
- The warlord lives off the map (the north). His moments are in `events`; raids could get a march path.
- The castle start (`start: kingdom`) has no coordinates; the scene file is frontier-only.
