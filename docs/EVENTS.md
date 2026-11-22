# Writing events

Events live in `content/events.yaml`. After editing, always run:

```bash
./kingdom check        # catches typos, bad keys, broken follow-ups
```

Then try it in the test kingdom (see "Testing an event" below).

## Two kinds of event

**Help/hinder events** - something happens, the crowd helps or makes it worse, the king can respond.
Bandits, fires, the barbarian horde.

**Decree votes** - an A-vs-B question. The comment words *are* the vote (WALLS vs GRANARY). When the
vote closes, the crowd's pick wins - unless the king backed the other side, in which case he wins and
everyone who voted against him loses loyalty. "The king just overruled you" is one of the best hooks
you have.

Either way, **the king can't respond on the day an event starts**. The crowd always gets the first post;
the king answers the next day, knowing how they voted.

## Template: help/hinder

```yaml
- id: troll_bridge                    # unique, lowercase_with_underscores
  title: "A troll has taken the bridge into {hold}"
  scope: hold                         # city (the whole kingdom) or hold
  hold_trait: forest                  # optional: prefer holds with this trait
  planned_only: false                 # true = never random; only from plans, you, or follow-ups
  when: "pop >= 50"                   # optional: when the storyteller may pick it at random
  weight: 2                           # how likely, compared with other events (random picks only)
  days: 3                             # how many posts it runs for
  champions: army                     # optional: soldiers' help counts double, helpers earn battle deeds
  on_start: {mood.hold: -0.05}        # once, when it starts
  while: {economy: -0.02}             # every day it's running
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
- id: royal_wedding
  title: "Varn offers a royal marriage. ACCEPT or REFUSE?"
  scope: city
  days: 2                             # 2+ days, so the king can back a side after the first post
  choices:                            # the words are the vote; each has its own outcome
    ACCEPT: {text: "The wedding is set. Peace with Varn, for now.", economy: 0.05, mood.army: -0.03}
    REFUSE: {text: "Varn has been refused. Their envoy left furious.", mood.army: 0.04,
             next: {event: varn_war, in_days: 2}}
  options:
    - {id: yes, label: "The king wants the marriage", side: ACCEPT, cost_pc: 0, text: "The king will marry."}
    - {id: no, label: "The king refuses", side: REFUSE, cost_pc: 0, text: "The king will not be sold."}
```

If the king backs the side the crowd picked: +loyalty ("The king heeded his people"). If he backs the
other side: he wins anyway, and loyalty drops (more for the people who voted against him). If he backs
nothing, the crowd's pick wins. Tune the size of these in `content/balance.yaml` (`heed_bonus`,
`overrule_penalty`). In conditions, `result('royal_wedding') == 'ACCEPT'` tells you who won.

## Effect keys

| Key | What it does | Example |
|---|---|---|
| `treasury_pc` | gold per subject (+ or -) | `treasury_pc: -4` |
| `treasury` | flat gold | `treasury: 5000` |
| `economy` | economy level (in `while`: just for today) | `economy: 0.05` |
| `service.defense` / `.food` / `.roads` / `.festivals` | walls & guards, granaries, roads & trade, taverns & festivals | `service.food: -0.1` |
| `mood` / `mood.commoners` / `mood.guilds` / `mood.army` / `mood.hold` | mood (in `while`: today's mood) | `mood.army: 0.04` |
| `loyalty` (+ same targets) | loyalty to the king - this is what the Reckoning is decided on | `loyalty.hold: -0.05` |
| `wealth_pc` (+ same targets) | gold in each subject's purse | `wealth_pc.guilds: 30` |
| `unrest.hold` | that hold's unrest | `unrest.hold: 0.1` |
| `depose.hold` | that hold loses its lord (a new one is named next week) | `depose.hold: 1` |
| `progress` | options only: pushes a help/hinder event toward done | `progress: 0.3` |
| `text` | what the report and video say happened | |
| `next` | a follow-up event | `next: {event: x, in_days: 2, hold: same}` |

Big moments should hit hard: ±0.08 to ±0.12 loyalty for a war won or lost, ±0.03 for small stuff.

## Placeholders (in titles and texts)

- `{hold}` - the hold it's happening in ("the kingdom" for city events)
- `{lord}` - that hold's lord, as a real **@handle** (events with `{lord}` in the title pick a hold that has one)
- `{resident}` - a random subject of that hold, as a real **@handle**

Putting real followers into the story is the best hook you have.

## Conditions (`when`, plan `if`, milestone `silent_if`)

Python-style: `pop >= 100 and approval < 0.5`. Names you can use:
`pop, approval (loyalty), treasury, tax, economy, day, season, season_day, unrest, q_defense, q_food,
q_roads, q_festivals, faction_commoners, faction_guilds, faction_army`, plus
`has('court')` (milestone unlocked), `happened('bandits')`, `result('first_decree') == 'WALLS'`,
`result('bandits') == 'helped'`, `active('barbarian_horde')`, `built('walls')`.

## Patterns

- **Arcs:** chain events with `next`. Branch on what the crowd did: `on_help` / `on_timeout` (or each
  decree choice) leads somewhere different. See the barbarian war (scouts -> raid -> horde), treason
  (PARDON -> spies), Varn, and the dragon.
- **Inevitable but shaped:** both outcomes lead to the next step, but the losing one makes it worse
  (the barbarians come either way; ignoring the scouts costs defense).
- **Story-only events:** `planned_only: true` keeps them out of the random pool.
- **The king's vanity:** events that poke his pride (the mocking bard, the statue) give the AI great lines.

## Testing an event

```bash
# schedule it in a scenario: add this to any scenarios/*.yaml
events:
  - {event: troll_bridge, day: 3, hold: Millbrook}

# or poke a saved test kingdom directly
./kingdom event start troll_bridge --state runs/latest/state
./kingdom event list --state runs/latest/state
```
