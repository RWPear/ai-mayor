# AI Mayor

**You live here. Comment to change your city.**

An AI mayor runs a city whose citizens are real followers. Following moves you
in. Comments on each post are that day's controls (WORK, PROTEST, SHOP...,
or ATTACK / DEFEND when there's a war). The mayor has to keep the city happy,
solvent and in one piece - and at the end of every 30-day season, the people
vote on whether to recall it.

- **One brain, many people.** Only the mayor uses a language model (about 2 calls a day). Citizens are
  numpy arrays: 100,000 of them simulate a day in well under a second.
- **Comments are commands.** Each post gets a *command pack* - 2-4 words and what they do. Change them
  any time; packs are YAML, no code.
- **Wards.** Neighbourhoods of up to 500 people, each with its own mood, unrest, protests and an
  elected councilor. New wards open as the city grows.
- **A storyteller.** Events (floods, strikes, scandals, a rival city's trade war...) arrive when the city
  gets too calm, ramping up toward each season's finale.
- **Milestones** unlock as the city grows (council, transit, newspaper, rival city, stadium, subway...).
- **STATUS** - anyone can comment STATUS and get a reply card for their citizen. No website needed.

## Layout

```
city/            the engine
  day.py         one day, start to finish (same code for test and live)
  sim.py         economy, services, moods, protests, projects, milestones, petitions
  citizens.py    the citizens (numpy arrays)
  packs.py       comment parsing + command packs
  effects.py     what commands do + declarative city effects
  storyteller.py events, follow-ups, scheduling and pacing
  plan.py        season plans (beats, conditions, calendar)
  checker.py     validates content before it runs
  mayor.py       the AI mayor (Ollama) and the rule-based test mayor
  report.py      daily report, episode script for the video, STATUS cards
  sources/       fake audience (test) and Instagram follower export reader (live)
content/         events, projects, milestones, mayor persona, balance overrides (all YAML)
seasons/         season plans: season1.yaml (written), season2.yaml (outline)
docs/            EVENTS.md (writing events), SEASONS.md (where this is going)
packs/           command packs for posts
scenarios/       test scenarios
tests/           python -m pytest -q
```

## Setup (brainbox)

```bash
git clone https://github.com/RWPear/ai-mayor.git ~/ai-mayor-dev
cd ~/ai-mayor-dev
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

## The test city (play with it freely)

Run a whole season in seconds with a fake audience:

```bash
.venv/bin/python -m city.run test --scenario scenarios/season1.yaml     # Season 1 as planned
.venv/bin/python -m city.run test --scenario scenarios/baseline.yaml
.venv/bin/python -m city.run test --scenario scenarios/revolt.yaml      # audience turns on the mayor
.venv/bin/python -m city.run test --scenario scenarios/collapse.yaml    # worst case
.venv/bin/python -m city.run test --scenario scenarios/viral.yaml       # 80 -> ~13,000 people
.venv/bin/python -m city.run test --scenario scenarios/mega.yaml        # 100,000 people
.venv/bin/python -m city.run test --scenario scenarios/river_war.yaml   # a hand-written war pack
```

Add `--mayor llm` to use the real AI mayor (needs Ollama; set `OLLAMA_URL=http://192.168.1.23:11434`),
and `--reports` to write each day's report, episode script and STATUS replies into `runs/`.

**Season plans:** `seasons/season1.yaml` is the planned path through Season 1. See it as a calendar with
`python -m city.run plan --plan seasons/season1.yaml`, and play it out with
`python -m city.run test --scenario scenarios/season1.yaml`. The big picture is in `docs/SEASONS.md`.

**Events:** write them in `content/events.yaml` (guide: `docs/EVENTS.md`), then `python -m city.run check`.
Start, schedule or end events by hand with `python -m city.run event ...` - works on test runs and the live city.

**Balancing:** change `content/balance.yaml` (or a scenario's `balance:` block), rerun, compare.
**New event:** add it to `content/events.yaml`. **New comment words:** write a pack in `packs/`.
**New kind of effect** (code): add it to `city/effects.py`, test it here first.

## The live city (hands off)

The live city runs one day at a time with real inputs:

```bash
.venv/bin/python -m city.run day --state data/live \
    --followers ~/exports/instagram-export.zip \
    --comments  comments/day-14.json \
    --pack      packs/daily.yaml \
    --plan      seasons            # only the first time - the city remembers its plan
```

- `--followers`: Instagram's own **Download your information** export (Followers and following, JSON).
  Point it at the zip, the folder, or `followers_1.json`. New followers move in; people who left only come
  back if they comment.
- `--comments`: the post's comments as `[{"username", "text", "timestamp"}]`. (Phase 2 fetches these
  from the Instagram API automatically; until then they can be exported by hand.)
- `--pack`: optional. If left out, the city uses the pack it suggested yesterday (an event's words,
  the recall vote on the finale, or the daily basics).

Each day writes `data/live/days/dayNNN.md` (report), `.episode.json` (script for the video) and
`.replies.json` (STATUS replies to post).

Look up anyone: `.venv/bin/python -m city.run status --state data/live --user somehandle`

## Test vs live

| | Test (`~/ai-mayor-dev`, branch `dev`) | Live (`~/ai-mayor-live`, a release tag) |
|---|---|---|
| Changes | anything, any time | only tested releases |
| Data | `runs/` - throw away | `data/live/` - backed up on every deploy |
| Audience | fake | real |

**Releasing:**
1. Work on `dev`, run scenarios and tests until it's right.
2. Merge to `main` and tag it: `git tag v0.2.0 && git push --tags`.
3. On the live checkout: `./scripts/deploy.sh v0.2.0` (backs up `data/live`, switches code, runs tests).

The live checkout is a separate clone: `git clone https://github.com/RWPear/ai-mayor.git ~/ai-mayor-live`
then `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` there too.

## Roadmap

1. **Engine + test city** - this.
2. **Instagram:** fetch each post's comments and post STATUS replies via the Instagram API
   (creator/business account + a Meta app), so a day runs with no manual steps.
3. **Episode video:** episode script -> city timelapse + the mayor's voice (CosyVoice) + captions
   (ffmpeg) -> sent to your phone for approval (n8n).
4. **Public page** (static, on Cloudflare) for anyone who wants their citizen's full story.
