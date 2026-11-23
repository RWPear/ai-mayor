# The living world

**An AI king and an AI warlord live in a world that never stops. Follow and you're born into it.
Comment a word to act, or tell your character what to do in your own words. Once a day: the story so far.**

## How a day works

```
19:00  yesterday's post closes ─┐
        │  every 30 minutes the world ticks:
        │   - King Aldric (awake 7:00-23:00) lives his life and rules - every 30 min to 2 hours, by budget
        │   - Skarn the Red (sleeps 10:00-16:00 - barbarians like the dark) acts about every 90 minutes
        │   - comments arrive; every hour, people's own-words moves are played out
        │   - works get built, the steward skims, visitors turn up at the gate, the camp eats at midnight
        │   - new tools unlock when the world allows it (that's a moment too)
19:00  today's post closes ─────┘
        comments are read: keywords, STATUS, BECOME <JOB>, and people's own words
        the kingdom simulates the day; the king sets policy and writes his journal
        the chronicle picks what goes in the post: 3 moments + "meanwhile in the north"
```

The post stays small. Everything that happened is in `dayNNN.log.txt` (for you), and each subject's own
story is on their STATUS card.

## One GPU budget, two kinds of day

Every hour has a budget of model calls (`gpu_calls_per_hour`, default 120 - raise it freely, the 3060
can do several hundred). **The crowd gets first claim**: people's own-words moves (2 calls per 8 people).
The minds get what's left, and their pace follows:

| The hour is... | Budget left for the minds | The king acts every | What the post is about |
|---|---|---|---|
| **quiet** | more than half | ~30 min | the king's life, his projects, the war |
| **busy** | 20-50% | ~1 hour | a mix |
| **viral** | under 20% | ~2 hours (big decisions only) | the crowd: thefts, duels, feuds, the king's court cases |

Whenever the budget runs out, the rule-based versions fill in, so nothing ever stops.

## The king's life (the quiet path)

**He starts blank.** `content/ruler.yaml` is just a name and one goal: still be king after the Reckoning.
No personality, no hobbies, no plans. Who he becomes is his:

- **Needs** - hunger, energy, company, fun. Just a body. They push him to eat, sleep (23:00-7:00), find
  someone to talk to, do something for fun.
- **Pastimes** - he can do anything for its own sake (paint, sing, carve, fish, write poems...). Whatever he
  keeps coming back to becomes a passion, and he gets better at it (skill 1-10). Nothing is pre-chosen.
- **Self** - every night at 23:00 he reflects on his day and rewrites who he is: traits, likes, dislikes,
  passions, wants, fears, and one sentence about who he's becoming. It's saved in
  `living.agents.king.self` and fed into everything he does after. Day 1 he's nobody; by day 30 he's
  someone - and you didn't write him.
- **The town** (`city/living/town.py`): the throne room, bedchamber, kitchens, castle yard, gardens, market
  square, tavern (he goes in disguise and overhears people), King's Street, smithy, chapel, river, fields,
  walls. Each place has features in a state (*"a dirt road churned into mud"*) and the real subjects you'd
  meet there at that hour. **Nothing suggests what to do about any of it.** If he thinks the road should be
  stone, that's his idea. If he never does, it stays mud.
- **His projects** can go wrong. He names it, picks a size (bigger is riskier), pays up front. Workers build
  over days; setbacks happen (storms, cracked stone, theft). When it's done it's rolled: it **turns out
  well**, comes out **shoddy** (half the benefit, "already cracking"), or **fails** - gold gone, a
  half-finished ruin left behind. Pitching in himself and experience from earlier builds help.
- **Ruins** - parts of his castle are ruins at the start (war room, spymaster's tower, great hall,
  dungeon). He isn't told what they're for. Rebuilding one quietly unlocks a power (garrison, spy, feast,
  real jail sentences) - he finds out when it's done.
- **The court** (`content/court.yaml`): Steward Wendell (flattering, quietly skims the treasury - the audience
  sees it, the king doesn't), Captain Bryn (blunt, worried about Skarn), Pip the Jester (mocks him). These
  side characters do have written personalities - they're the world he wakes up in.
- **The docket**: petitions from real comments, criminals the guards caught, visitors at the gate. In the
  throne room he rules: grant, deny, reward, pardon, fine or jail.

## Subjects acting on each other (the viral path)

Own-words comments can name another subject:

| Comment | What happens |
|---|---|
| "I rob @someone" | a roll vs the kingdom's guards (and whether the target is a soldier): gold changes hands, or the thief is caught |
| "I challenge @someone to a duel" / "I punch..." / "I try to kill..." | both characters' strength (army, battles, rank, mood) + luck. The loser is **wounded** for a day or two. **Nobody dies.** The attacker may be **arrested** |
| "I give @someone 20 gold" | gold moves, both get happier |
| "I buy @someone a drink" | they become friends |
| "I mock @someone" | their mood drops, a grudge starts |
| "I beg the king for..." | goes on the king's docket |

The model reads what people meant, **the game rolls the result**, then the model narrates it - so it can't
be talked into a win. Arrested people go to the dungeon (or the stocks) and onto the docket; the jailed and
wounded sit out. A target can only be hit by a couple of hostile acts a day (no dogpiles). Two people who
keep clashing become a **feud** - news across the kingdom.

## The warlord

| | Skarn the Red |
|---|---|
| Lives in | the Frostfang camp in the north (sleeps 10:00-16:00 - barbarians like the dark) |
| Wants | to sit on Aldric's throne |
| Starts with | scout, raid (from day 3), recruit, hunt, taunt, feast |
| Unlocks | **march** (the whole horde) once the camp is big and confident · **sabotage** after two winning raids |

His camp is a small economy: warriors eat food, food comes from hunting and raiding, morale rises with
victories and falls with defeats and hunger, and the camp only holds as many warriors as its reputation
allows. A raid's difficulty depends on how many warriors he sends, the kingdom's defenses, garrisons, and
luck. Nobody schedules the war.

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
./kingdom test --scenario scenarios/living_viral.yaml --reports      # the account blows up in week 2

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
