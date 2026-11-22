# The living world

**An AI king and an AI warlord live in a world that never stops. Follow and you're born into it.
Comment a word to act, or tell your character what to do in your own words. Once a day: the story so far.**

## How a day works

```
19:00  yesterday's post closes ─┐
        │  every 30 minutes the world ticks:
        │   - King Aldric (awake 7:00-23:00) acts about once an hour
        │   - Skarn the Red (sleeps 10:00-16:00 - barbarians like the dark) acts about every 90 minutes
        │   - the war camp eats at midnight; raids that the crowd has fought resolve and the camp feels it
        │   - new tools unlock when the world allows it (that's a moment too)
19:00  today's post closes ─────┘
        comments are read: keywords, STATUS, BECOME <JOB>, and people's own words
        the kingdom simulates the day; the king sets policy and writes his journal
        the chronicle picks what goes in the post: 3 moments + "meanwhile in the north"
```

The post stays small. Everything that happened is in `dayNNN.log.txt` (for you), and each subject's own
story is on their STATUS card.

## The two minds

| | King Aldric (protagonist) | Skarn the Red (antagonist) |
|---|---|---|
| Lives in | the castle (and taverns, in disguise) | the Frostfang camp in the north |
| Wants | to be adored, to keep the crown at the Reckoning | to sit on Aldric's throne |
| Starts with | go, proclaim, summon (a real @handle), decree (invents a vote), spend, rest | scout, raid (from day 3), recruit, hunt, taunt, feast |
| Unlocks | **spy** when watchtowers are built · **garrison** after the first raid | **march** (the whole horde) once the camp is big and confident · **sabotage** after two winning raids |
| Persona file | `content/ruler.yaml` | `content/warlord.yaml` |

Each time a mind acts it sees a short picture of its world (where it is, what it knows, what just
happened, its goals, its recent actions) and picks one tool. It can also give itself a new goal. That's
all - the story comes from two characters with opposite wants and a crowd that keeps changing things.

The warlord's camp is a small economy: warriors eat food, food comes from hunting and raiding, morale
rises with victories and falls with defeats and hunger, and the camp can only hold as many warriors as
its reputation allows. A raid's difficulty depends on how many warriors he sends, the kingdom's defenses,
a garrison, and luck. Nobody schedules the war.

## Subjects in their own words

A comment that isn't one of the post's words - *"I sneak into the castle kitchens to steal bread for my
kids"* - is that subject's move for the day. Their character gets a turn: the model turns it into the
closest real action (work, train, protest, help or hurt the current crisis...) and writes one sentence of
what happened. The effect is the same bounded effect as the matching keyword; the sentence goes on their
STATUS card, and the boldest ones make the post. Cost scales with commenters, 8 per model call, capped
by `intents_cap` (default 400/day; anyone past the cap gets the rule-based version).

## Invented decrees

The king's `decree` tool writes a brand-new vote in his own words: a question, two one-word choices, and
what each one does - picked from a fixed list of small effect packages (`walls`, `food`, `tax_cut`,
`vanity`, ...; see `FLAVORS` in `city/living/tools.py`). One a day at most. It goes on the next post like
any decree vote, and it's saved with the kingdom.

## Notifications

Anything surprising - a raid, the horde marching, an invented decree, a new tool - is recorded in the save
(`living.notifications`) and, if `NOTIFY_URL` is set, POSTed there as JSON (point it at an n8n webhook
to get it on your phone).

## Running it

```bash
# test: a month in seconds with rule-based minds, or for real with the model
./kingdom test --scenario scenarios/living.yaml
./kingdom test --scenario scenarios/living.yaml --king llm --days 7 --reports

# live, in real time (comments for each post go in inbox/comments-dayN.json)
./kingdom live --state data/live --plan seeds --king llm
./kingdom live --state data/test-live --plan seeds --king llm --speed 60   # an hour a minute
```

`--reports` writes, per day: the report (`dayNNN.md`, with "The last 24 hours"), the full log
(`dayNNN.log.txt`, secrets marked), the episode script and STATUS replies.

Model settings: `OLLAMA_MODEL` (king and warlord, default qwen3:14b), `OLLAMA_CROWD_MODEL` (subjects; a
smaller model like qwen3:8b is fine and faster), `OLLAMA_URL`.

## Season plans in the living world

`seeds/season1.yaml` keeps only the bones every season needs: the opening, a first decree, a treason
trial, the pretender, the royal audience, the Reckoning. The war is the warlord's business. Write more
seeds (new characters, new tools) as the kingdom grows.
