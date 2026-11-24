# AI Kingdom  (repo: ai-mayor)

**An AI is building a kingdom on a floating island. Follow and you live there. Comment to change it.**

Aldric starts with nothing: a leaky shack in a field on an old floating island above the clouds, a dull axe,
fifteen coins. He wants to be king. Followers are the people of Emberfall: following walks you in (a free bed,
or a tent by the old road), and every comment is your character doing something - chopping wood, building a
garden, stealing from a neighbour, riding in on a dragon. The game decides what happens; a narrator writes you a
reply that carries your story on. The island is a little magical: wild claims come true, at a cost, and new land
rises out of the clouds as Emberfall grows.

```bash
./kingdom play --fresh --king llm      # play it live in your browser: comment as anyone, approve every reply
```

- **Comments are moves.** Your first real attempt each day is your move; it changes the world. Questions and
  jokes are talk (answered in the world, no move used). After your move, more comments are conversation with
  Aldric and the others - up to 3 replies a day. Every reply waits for approval before it goes anywhere.
- **The world remembers.** Each person's story so far goes to the narrator, so threads carry on (the goat that
  follows you, the question Aldric asked you yesterday).
- **Wonders.** Claim a dragon and there IS one - a hatchling that eats the stores. Cast a spell and it works,
  sideways. Wonders persist, cost something every day, and can be hunted, fed or stolen.
- **Aldric lives in real time.** He gathers, builds, invents what to build, talks to people, holds court, and
  every night decides who he's becoming. At 10 settlers they vote on crowning him; once crowned, every 30 days
  comes the Reckoning: KNEEL or REVOLT.
- **The island grows.** New land rises from the clouds at the rim as Emberfall grows (the east meadow, the glass
  cliffs, the warm springs...), and the island throws things at it: sky-whales, falling stars, a door in the hill.
- **Skarn the Red** camps on a black crag floating to the north and sends raiders across on gliders once there's
  something worth taking.
- **In 3D:** a low-poly island, box-and-triangle houses, and little round-headed people who waddle about, work and chat. Fixed recorders make timelapses of the
  island growing.

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
city/day.py          one day: the post closes, the next one opens
city/llm.py          the model client (Ollama, or optionally a hosted model for the comments)
city/storyteller.py  events: starting, ticking, what the comments did to them
city/living/         the living world
  world.py           the clock, every tick, replies
  frontier.py        the island: land, stores, building, people arriving, stages, the crown, new land
  frontier_tools.py  what Aldric can do, sees and wants
  agents.py          the minds (Aldric, Skarn): two-step decisions
  intents.py         reading comments -> the game decides -> the narrator writes the reply; talk
  wonders.py         wonders: wild claims made real, at a cost
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

