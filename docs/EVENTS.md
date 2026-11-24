# Writing events

Events live in `content/events.yaml` (its header lists every key and effect). After editing, run the tests
(`.venv/bin/python -m pytest -q`) and try it in a test run (see "Testing an event" below). With `--king llm`
the director invents events from what's been happening; the list is what the island throws at Emberfall
otherwise, and where Skarn's raids are defined.

## Two kinds of event

**Help/hinder events** - something happens, the crowd helps or makes it worse, the king can respond.
A cloud storm, a falling star, Skarn's raiders.

**Decree votes** - an A-vs-B question. The comment words *are* the vote (WALLS vs GRANARY). When the
vote closes, the crowd's pick wins - unless Aldric backed the other side, in which case he wins and
everyone who voted against him loses loyalty. A door appeared in the hill: OPEN or SEAL?

Either way, **the king can't respond on the day an event starts**. The crowd always gets the first post;
the king answers the next day, knowing how they voted.

## Template: help/hinder

```yaml
- id: troll_bridge                    # unique, lowercase_with_underscores
  title: "A troll has taken the bridge into {hold}"
  scope: hold                         # city (the whole kingdom) or hold
  planned_only: false                 # true = never random; only from you or follow-ups
  when: "pop >= 50"                   # optional: when the storyteller may pick it at random
  weight: 2                           # how likely, compared with other events (random picks only)
  days: 3                             # how many posts it runs for
  champions: army                     # optional: fighters' help counts double, helpers earn battle deeds
  on_start: {mood.hold: -0.05}        # once, when it starts
  while: {mood.hold: -0.02}           # every day it's running
  commands: {FIGHT: help, RIDDLE: help, PAY: hinder}   # comment words for the post about it
  help_needed: 0.45                   # how much of the kingdom needs to help (lower = easier)
  on_help:                            # enough people helped
    text: "{resident} answered the troll's riddle. The bridge is open."
    mood.hold: 0.06
    next: {event: troll_revenge, in_days: 3, hold: same}   # optional follow-up
  on_timeout:                         # ran out of time
    text: "The troll is still there. {hold} is cut off."
    loyalty.hold: -0.05
  options:                            # what the king can do (from the second post on)
    - id: knights
      label: "Send the knights"
      cost_pc: 3                      # gold per subject (scales with the kingdom); negative = the crown earns
      effects: {progress: 0.4}        # progress pushes the event toward done
      text: "The king sent his knights to the bridge."
    - id: toll
      label: "Let the troll charge a toll and take a cut"
      cost_pc: -2
      ends: true                      # settles the event right away
      effects: {loyalty.hold: -0.08}
      text: "The king made a deal with the troll. {hold} is furious."
```

## Template: decree vote

```yaml
- id: sky_merchant_bride
  title: "A sky-merchant offers Aldric her hand - and her airship. ACCEPT or REFUSE?"
  scope: city
  days: 2                             # 2+ days, so Aldric can back a side after the first post
  choices:                            # the words are the vote; each has its own outcome
    ACCEPT: {text: "The wedding is set. Emberfall has an airship now - and a queen with opinions.", treasury: 40, mood: 0.04}
    REFUSE: {text: "The sky-merchant left furious. Her airship circled the island twice, low.", mood: -0.02,
             next: {event: trading_airship, in_days: 3}}
  options:
    - {id: yes, label: "Aldric wants the marriage", side: ACCEPT, cost_pc: 0, text: "Aldric will marry."}
    - {id: no, label: "Aldric refuses", side: REFUSE, cost_pc: 0, text: "Aldric will not be bought."}
```

If the king backs the side the crowd picked: +loyalty ("The king heeded his people"). If he backs the
other side: he wins anyway, and loyalty drops (more for the people who voted against him). If he backs
nothing, the crowd's pick wins. Tune the size of these in `content/balance.yaml` (`heed_bonus`,
`overrule_penalty`). In conditions, `result('sky_merchant_bride') == 'ACCEPT'` tells you who won.

## Effect keys

| Key | What it does | Example |
|---|---|---|
| `gold` | into (or out of) the treasury, never below zero | `gold: -15` |
| `build.<kind>` | `build.any: -1` batters a random building (it falls into disrepair until people run it again); `build.tavern: 1` leaves a new one behind | `build.any: -1` |
| `treasury` / `treasury_pc` | Aldric's purse, flat / per person (capped at 20 people's worth; never below 0) | `treasury: 25` |
| `island` | new land rises from the clouds at the rim, with a new place on it | `island: 1` |
| `wonder` | a wonder appears: `"name \| kind \| what it is \| its catch \| upkeep"` | see the griffin in events.yaml |
| `mood` / `mood.hold` | mood (in `while`: today's mood) | `mood: 0.05` |
| `loyalty` / `loyalty.hold` | loyalty to Aldric - what the crown vote and the Reckoning hang on | `loyalty: -0.05` |
| `service.defense` | how hard Skarn's raids are | `service.defense: 0.1` |
| `progress` | options only: pushes a help/hinder event toward done | `progress: 0.3` |
| `text` | what the report and video say happened | |
| `next` | a follow-up event | `next: {event: x, in_days: 2, hold: same}` |

Big moments should hit hard: ±0.08 to ±0.12 loyalty for a raid beaten or lost, ±0.03 for small stuff.

## Placeholders (in titles and texts)

- `{hold}` - the corner of the settlement it's happening in (Riverside, Hillfoot, Woodedge)
- `{resident}` - a random settler there, as a real **@handle**

Putting real followers into the story is the best hook you have.

## Conditions (`when`)

Python-style: `pop >= 5 and approval < 0.5`. Names you can use: `pop, approval (loyalty), treasury, day, season,
season_day`, plus `happened('falling_star')`, `result('door_in_the_hill') == 'OPEN'`, `active('cloud_storm')`,
`built('well')` (something with that in its name is built).

## Patterns

- **Arcs:** chain events with `next`; branch on what the comments did (`on_help` / `on_timeout`, or each vote
  choice leads somewhere different).
- **Leave something behind:** a `wonder` effect turns an event into a thread people can keep pulling (the door in
  the hill, the griffin, the wizard).
- **Story-only events:** `planned_only: true` keeps them out of the random pool (Skarn's raids are started by his
  war camp).

## Testing an event

```bash
# schedule it in a scenario: add this to any scenarios/*.yaml
events:
  - {event: troll_bridge, day: 3, hold: Riverside}

# or poke a saved test kingdom directly
./kingdom event start troll_bridge --state runs/latest/state
./kingdom event list --state runs/latest/state
```
