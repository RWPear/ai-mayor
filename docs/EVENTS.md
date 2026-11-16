# Writing events

Events live in `content/events.yaml`. After editing, always run:

```bash
.venv/bin/python -m city.run check        # catches typos, bad keys, broken follow-ups
```

Then try it in the test city (see "Testing an event" below).

## Template

```yaml
- id: power_plant_leak                 # unique, lowercase_with_underscores
  title: "Strange smell near the plant in {ward}"
  scope: ward                          # city or ward
  ward_trait: industrial               # optional: prefer wards with this trait
  planned_only: false                  # true = never random; only from plans, you, or follow-ups
  when: "pop >= 50 and q_safety < 1.0" # optional: when the storyteller may pick it at random
  weight: 2                            # how likely, compared with other events (random picks only)
  days: 3                              # how long it runs
  on_start: {mood.ward: -0.05}         # once, when it starts
  while: {economy: -0.02}              # every day it's running
  commands: {INSPECT: help, SHRUG: hinder}   # comment words for the post about it
  help_needed: 0.4                     # how much of the city needs to help (lower = easier)
  on_help:                             # enough people helped
    text: "Residents of {ward} forced an inspection. {resident} found the leak."
    mood.ward: 0.05
    next: {event: plant_cover_up, in_days: 2}      # optional follow-up
  on_timeout:                          # ran out of time
    text: "The smell went away. Nobody knows what it was."
    loyalty.ward: -0.03
  options:                             # what the mayor can choose
    - id: shut_down
      label: "Shut the plant down"
      cost_pc: 5                       # cost per citizen (scales with the city)
      ends: true                       # true = this settles the event immediately
      effects: {economy: -0.04, mood.residents: 0.05}
      text: "The mayor shut the plant down."
      next: {event: plant_layoffs, in_days: 3}     # options can have follow-ups too
```

## Effect keys

| Key | What it does | Example |
|---|---|---|
| `treasury_pc` | money per citizen (+ or -) | `treasury_pc: -4` |
| `treasury` | flat money | `treasury: 5000` |
| `economy` | economy level (in `while`: just for today) | `economy: 0.05` |
| `service.safety` / `.housing` / `.transit` / `.culture` | service quality | `service.housing: -0.1` |
| `mood` / `mood.labor` / `mood.business` / `mood.residents` / `mood.ward` | mood (in `while`: today's mood) | `mood.labor: -0.04` |
| `loyalty` (+ same targets) | approval of the mayor | `loyalty.ward: -0.03` |
| `wealth_pc` (+ same targets) | money in each citizen's pocket | `wealth_pc.business: 30` |
| `unrest.ward` | that ward's unrest | `unrest.ward: 0.1` |
| `text` | what the report and video say happened | |
| `next` | a follow-up event | `next: {event: x, in_days: 2, ward: same}` |

## Placeholders (in titles and texts)

- `{ward}` - the ward it's happening in
- `{councilor}` - that ward's councilor, as a real **@handle**
- `{resident}` - a random resident of that ward, as a real **@handle**

Putting real followers into events is one of the best hooks you have.

## Conditions (`when`, plan `if`)

Python-style: `pop >= 100 and approval < 0.5`. Names you can use:
`pop, approval, treasury, tax, economy, day, season, season_day, unrest, q_safety, q_housing, q_transit,
q_culture, faction_labor, faction_business, faction_residents`, plus
`has('rival')` (milestone unlocked), `happened('tech_hq')`, `result('tech_hq') == 'helped'`,
`active('heatwave')`, `built('stadium')`.

## Patterns

- **A vs B votes:** help word = choice A, hinder word = choice B. `on_help` = A won, `on_timeout` = B won.
  See `first_budget` (PARKS vs POLICE).
- **Arcs:** chain events with `next`. Branch on what the crowd did: `on_help` leads one way, `on_timeout`
  another. See the scandal and Port Calder arcs.
- **Story-only events:** `planned_only: true` keeps them out of the random pool.

## Testing an event

```bash
# schedule it in a scenario: add this to any scenarios/*.yaml
events:
  - {event: power_plant_leak, day: 3, ward: Brickworks}

# or poke a saved test city directly
.venv/bin/python -m city.run event start power_plant_leak --state runs/<run>/state
.venv/bin/python -m city.run event list --state runs/<run>/state
```
