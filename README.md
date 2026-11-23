# AI Kingdom  (repo: ai-mayor)

**You live here. Comment to change the kingdom.**

An AI king rules Emberfall, a kingdom whose subjects are real followers. Following moves you in and
gives you a trade. Comments on each post are that day's actions (WORK, TRADE, TRAIN, GRUMBLE..., or
FIGHT / FORTIFY when the barbarians come, or a decree vote like WALLS vs GRANARY). The king has to keep
the kingdom fed, defended, solvent and loyal - and at the end of every 30-day season comes the
Reckoning: the people KNEEL or REVOLT.

- **One brain, many people.** Only the king uses a language model (about 2 calls a day). Subjects are
  numpy arrays: 100,000 of them simulate a day in well under a second.
- **Comments are commands.** Each post gets a *command pack* - 2-4 words and what they do. Packs are
  YAML, no code. Always available: `STATUS` (your subject card), `JOIN`, and `BECOME <JOB>`.
- **Roles and ranks.** Commoners, guilds and the army want different things. Soldiers count double in
  battles. Deeds raise your rank (Peasant -> Freeman -> Squire -> Knight); the king names a Lord for
  each hold every week.
- **Decree votes.** The crowd votes; the king can back their pick or overrule them - and pays for it.
  The king never answers before the crowd has had a post.
- **Holds.** Regions of up to 500 people, each with its own mood, unrest, angry crowds and a lord.
  New holds open as the kingdom grows.
- **A storyteller and season plans.** A planned path through each season (`seasons/`), arcs that branch
  on what the crowd did (the barbarian war, treason, Varn, the dragon), and random events in between.
- **STATUS** - comment STATUS and get a card unique to you: name, rank, trade, hold, deeds, battles,
  how the king sees you, and how close you are to the next rank.

## The living world (new)

Between posts the kingdom keeps living. **King Aldric** (protagonist) starts blank - a name and one goal - and
grows his own self: needs push him around, he tries pastimes, has his own ideas for the town (which can fail),
rebuilds castle ruins (which quietly unlocks powers), talks with his court and judges the docket, and every
night he rewrites who he is. He can do anything in his own words ("go for a run", "sit and read") and the
world narrates what comes of it. Events come from a director that invents consequences of what actually
happened, tame at first and nastier as the season goes on. Followers get houses (outside the walls, if any);
raids burn the ones outside. Skarn shows up on day 4. Every post stays live. The king decides in two steps
(what to focus on, then exactly what). Followers hear what their character did and what came of it - replies to
their comments, gifts the king used, ideas he took up - and the post names whose doing it was. **Skarn the Red** (the barbarian warlord,
antagonist) runs his war camp and decides when to raid. Comments in people's own words give their
character a turn - including stealing from, fighting, or befriending other followers (nobody dies).
One GPU budget per hour: the crowd gets first claim, the king gets the rest - so a quiet day is about the
king's life and a viral day is about the crowd. Each post is a 3-moment summary. Guide: `docs/LIVING.md`.

```bash
./kingdom test --scenario scenarios/living.yaml                 # a living month in seconds (rule-based minds)
./kingdom test --scenario scenarios/living.yaml --king llm --days 7 --reports
./kingdom test --scenario scenarios/living_viral.yaml --reports  # the account blows up in week 2
./kingdom live --state data/live --plan seeds --king llm         # real time
```

## Layout

```
kingdom          shortcut: ./kingdom <command>  ==  .venv/bin/python -m city.run <command>
city/            the engine (theme-neutral; in the code a hold is a "ward", the king is the "mayor")
  day.py         one day, start to finish (same code for test and live)
  sim.py         economy, services, moods, angry crowds, projects, milestones, lords, petitions
  citizens.py    the subjects (numpy arrays), ranks, job changes
  roles.py       trades, factions, ranks, epithets
  packs.py       comment parsing + command packs
  effects.py     what commands do + declarative kingdom effects
  storyteller.py events, decree votes, follow-ups, scheduling and pacing
  plan.py        season plans (beats, conditions, calendar)
  checker.py     validates content before it runs
  mayor.py       the AI king (Ollama) and the rule-based test king
  report.py      daily report, episode script for the video, STATUS cards
  sources/       fake audience (test) and Instagram follower export reader (live)
  llm.py         the shared Ollama client
  living/        the living world: world.py (clock, loop, GPU budget), agents.py (the minds), tools.py,
                 town.py (places, improvements, castle rooms), life.py (needs, passions, works, court,
                 docket), warcamp.py (the warlord's economy), intents.py (own-words comments, fights,
                 thefts, gifts), chronicle.py
content/         events, projects, milestones, ruler persona, balance overrides (all YAML)
seasons/         season plans: season1.yaml (written), season2.yaml (outline)
seeds/           season plans for the living world (only the bones - the minds do the rest)
docs/            EVENTS.md (writing events), SEASONS.md (where this is going)
packs/           command packs for posts
scenarios/       test scenarios
tests/           .venv/bin/python -m pytest -q
chmod +x kingdom          # once: enables the ./kingdom shortcut
```

## Setup (brainbox)

```bash
git clone https://github.com/RWPear/ai-mayor.git ~/ai-mayor-dev
cd ~/ai-mayor-dev
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
chmod +x kingdom          # once: enables the ./kingdom shortcut
```

## The test kingdom (play with it freely)

Run a whole season in seconds with a fake audience. The newest run is always at `runs/latest`.

```bash
./kingdom test --scenario scenarios/season1.yaml        # Season 1 as planned
./kingdom test --scenario scenarios/baseline.yaml
./kingdom test --scenario scenarios/revolt.yaml         # audience turns on the king
./kingdom test --scenario scenarios/collapse.yaml       # worst case: should end in a REVOLT
./kingdom test --scenario scenarios/viral.yaml          # 80 -> ~10,000 people
./kingdom test --scenario scenarios/mega.yaml           # 100,000 people
./kingdom test --scenario scenarios/barbarian_war.yaml  # a hand-written war pack
```

Add `--king llm` to use the real AI king (needs Ollama; set `OLLAMA_URL=http://192.168.1.23:11434`),
and `--reports` to write each day's report, episode script and STATUS replies into `runs/latest/days/`.

**Season plans:** `seasons/season1.yaml` is the planned path through Season 1. See it as a calendar with
`./kingdom plan --plan seasons/season1.yaml`. The big picture is in `docs/SEASONS.md`.

**Events:** write them in `content/events.yaml` (guide: `docs/EVENTS.md`), then `./kingdom check`.
Start, schedule or end events by hand with `./kingdom event ...` - works on test runs and the live kingdom.

**Balancing:** change `content/balance.yaml` (or a scenario's `balance:` block), rerun, compare.
**New event:** add it to `content/events.yaml`. **New comment words:** write a pack in `packs/`.
**New kind of effect** (code): add it to `city/effects.py`, test it here first.

## The live kingdom (hands off)

The live kingdom runs one day at a time with real inputs:

```bash
./kingdom day --state data/live \
    --followers ~/exports/instagram-export.zip \
    --comments  comments/day-14.json \
    --pack      packs/daily.yaml \
    --plan      seasons            # only the first time - the kingdom remembers its plan
```

- `--followers`: Instagram's own **Download your information** export (Followers and following, JSON).
  Point it at the zip, the folder, or `followers_1.json`. New followers move in; people who left only come
  back if they comment.
- `--comments`: the post's comments as `[{"username", "text", "timestamp"}]`. (Phase 2 fetches these
  from the Instagram API automatically; until then they can be exported by hand.)
- `--pack`: optional. If left out, the kingdom uses the pack it suggested yesterday (an event's words,
  the Reckoning on the finale, or the daily basics).

Each day writes `data/live/days/dayNNN.md` (report), `.episode.json` (script for the video) and
`.replies.json` (STATUS replies to post).

Look up anyone: `./kingdom status --state data/live --user somehandle`

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
2. **Instagram:** fetch each post's comments via the Instagram API (professional account + a Meta app)
   and answer STATUS with a *private reply* (a DM to the commenter, once per comment, within 7 days),
   so a day runs with no manual steps and every card is personal.
3. **Episode video:** episode script -> kingdom view + the king's voice (CosyVoice) + captions
   (ffmpeg) -> sent to your phone for approval (n8n).
4. **Public page** (static, on Cloudflare) for anyone who wants their subject's full story.
