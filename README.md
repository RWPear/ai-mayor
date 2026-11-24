# AI Kingdom  (repo: ai-mayor)

**An AI is building a kingdom on a floating island. Follow and you live there. Comment to change it.**

Aldric starts alone in a leaky shack on an old floating island above the clouds. He wants to be king. Followers are
the people of Emberfall: following walks you in and gives you a little house of your own on the town's streets, and
every comment is your character doing something. The kingdom grows on **People Power**: every follower works a
shift a day, and buildings only get built - and only run - if enough people turn up.

```bash
./kingdom play --fresh --king llm      # play it live in your browser: comment as anyone, approve every reply
./kingdom demo                         # a 50-person kingdom ten days in, to watch
```

- **People Power.** Everyone works one shift a day; people who comment work two, and what they say steers where
  ("I'll work the farm", "I help build the tavern"). A farm only runs on days ten people work it; a brewery is 30
  days of building work - thirty people do it in a day, nobody never does. Keep turning up at the same work and you
  become it: a farmer, a brewer, a builder.
- **Gold decides how fine.** Building costs people, not gold - but the gold Aldric puts in decides whether it's a beer
  tent or a beer hall. Running buildings earn gold; your shifts earn you a coin each, to do up your own house.
- **The people want things** (food, water, a pint, music, a chapel, wine...) and how well they're met is the town's
  happiness. Aldric decides what gets built next; whether it gets built is up to whether you turn up.
- **Comments are moves.** Your first real attempt each day is your move; questions and jokes are talk (answered in
  the world). Every reply waits for approval before it goes anywhere. Each person's story so far, and their friends
  and feuds, go to the narrator, so threads carry on.
- **The town lives on its own.** Everyone keeps a simple day (work, lunch, the tavern, supper, bed), and wherever two
  people meet something small happens - shared bread, gossip, an argument about the well. It adds up into
  friendships, feuds and fights while nobody's commenting.
- **Wonders.** Claim a dragon and there IS one - a hatchling that eats three gold of food a day. Wonders persist and
  cost something every day.
- **The island grows.** New land rises from the clouds at the rim as Emberfall grows, and the island throws things at
  it: sky-whales, falling stars, a door in the hill. **Skarn the Red** raids once there's something worth taking.
- **In 3D,** Thronefall-style: a grid town of little orange houses round a keep, fields and a windmill, a striped
  beer tent, tiny people going about their day, bubbles when they meet. Fixed recorders make timelapses.

Guides: [docs/PLAY.md](docs/PLAY.md) (playing it live), [docs/FRONTIER.md](docs/FRONTIER.md) (how Emberfall
works), [docs/WORLD.md](docs/WORLD.md) (the 3D view and recordings), [docs/SCENE.md](docs/SCENE.md) (the 3D data),
[docs/ROLES.md](docs/ROLES.md) (BECOME anything), [docs/COMMENTS.md](docs/COMMENTS.md) (how comments are read).

## Setup (brainbox)

```bash
git clone https://github.com/RWPear/ai-mayor.git ~/ai-mayor-dev
cd ~/ai-mayor-dev
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
chmod +x kingdom          # once: enables the ./kingdom shortcut
```

The minds run on Ollama (qwen3:14b by default). `./kingdom` finds it on this machine by itself; if it's
elsewhere, or for any other setting, copy `.env.example` to `.env` next to `./kingdom`. `.env` is never committed.

**Optional - a hosted model for the comments.** The replies are what people read, and a bigger model writes them
better. Put `COMMENT_MODEL=claude-sonnet-5-5` and `ANTHROPIC_API_KEY=...` (or an OpenAI-compatible model with
`OPENAI_API_KEY`) in `.env`: reading comments, writing replies, talk and narration go to it; Aldric's own thinking
stays local. It falls back to the local model if the API fails or `COMMENT_MAX_CALLS` (a day) runs out.

## Commands

```bash
./kingdom play --fresh --king llm                                # live, in the browser (docs/PLAY.md)
./kingdom demo                                                   # a 50-person kingdom ten days in, live
./kingdom test --scenario scenarios/frontier.yaml --reports      # a month with a made-up audience, in seconds
./kingdom test --scenario scenarios/frontier_viral.yaml          # ...and the account blowing up
./kingdom serve                                                  # walk around the last test run in 3D
./kingdom record                                                 # timelapses from the recorders (docs/WORLD.md)
./kingdom live --state data/live --inbox inbox --king llm        # the real thing, in real time
./kingdom day --state data/live --followers export.zip --comments comments.json   # or one day at a time
./kingdom status --state data/live --user somehandle             # a person's card
./kingdom event list --state runs/latest/state                   # start / schedule / end events by hand
```

Tuning lives in `content/balance.yaml`; island events in `content/events.yaml`; the court in `content/court.yaml`.

## Layout

```
kingdom              ./kingdom <command>  ==  .venv/bin/python -m city.run <command>
city/run.py          the commands
city/play.py         live play: the clock, comments, replies to approve, the mind tab
city/demo.py         ./kingdom demo: a mid-sized kingdom built on the rules
city/day.py          one day: the post closes, the next one opens
city/llm.py          the model client (Ollama, or optionally a hosted model for the comments)
city/storyteller.py  events: starting, ticking, what the comments did to them
city/living/         the living world
  world.py           the clock, every tick, replies
  frontier.py        People Power: jobs, crews, building, gold, wants, houses, stages, the crown, new land
  frontier_tools.py  what Aldric can do, sees and wants
  agents.py          the minds (Aldric, Skarn): two-step decisions
  intents.py         reading comments -> the game decides -> the narrator writes the reply; talk
  wonders.py         wonders: wild claims made real, at a cost
  routine.py         everyone's day, and the little things between people (friends, feuds)
content/buildings.yaml  what can be built: crews, days of work, versions by gold, what people want
  director.py        invents events from what's been happening
  scene.py           everything the 3D view needs
viewer/              the 3D view (three.js, no build step)
content/             events, court, balance, recorders, personas
tests/               pytest
```

## Test vs live

| | Test (`~/ai-mayor-dev`, branch `dev`) | Live (`~/ai-mayor-live`, a release tag) |
|---|---|---|
| Changes | anything, any time | only tested releases |
| Data | `runs/`, `data/play/` - throw away | `data/live/` - backed up on every deploy |
| Audience | made up, or you in `./kingdom play` | real |

Releasing: work on `dev`; merge to `main` and tag (`git tag v0.3.0 && git push --tags`); on the live checkout,
`./scripts/deploy.sh v0.3.0` (backs up `data/live`, switches code, runs the tests).

## Roadmap

1. **Instagram:** fetch each post's comments through the Instagram API, and send the approved replies (the approval
   step is the Replies panel in `./kingdom play` today; n8n to your phone later).
2. **The daily video:** a recorder timelapse + Aldric's journal as narration + captions.

