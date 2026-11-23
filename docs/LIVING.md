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
| **quiet** | more than half | ~20 min | the king's life, his projects, the war |
| **busy** | 20-50% | ~45 min | a mix |
| **viral** | under 20% | ~1.5 hours (big decisions only) | the crowd: thefts, duels, feuds, the king's court cases |

Whenever the budget runs out, the rule-based versions fill in, so nothing ever stops.

## The king's life (the quiet path)

**He starts blank.** `content/ruler.yaml` is just a name and one goal: still be king after the Reckoning.
No personality, no hobbies, no plans. Who he becomes is his:

- **Needs** - hunger, energy, company, fun. Just a body. They push him to eat, sleep (23:00-7:00), find
  someone to talk to, do something for fun.
- **He can do anything.** There's no menu of activities: his `do` tool takes his own words ("go for a run
  around the walls", "sit in the garden and read", "try to bake bread"). The world answers (a narrator call):
  what happened, how long it took, how his needs changed (a run tires him, reading is quiet fun), and
  anything he learned, found or made. What he learns is remembered - and reading up on something makes his
  projects about it more likely to work. Whatever he keeps coming back to becomes a passion.
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

## How the king decides (two steps)

Showing a model every tool at once confuses it, so the king decides like a person:

1. **What do I want to focus on?** He sees the big picture (where he is, how he feels, who he is, the
   kingdom, what's waiting) and a short menu of focuses that make sense right now: *myself* (eat, rest,
   enjoy something), *people*, *court* (only if someone's waiting), *building*, *ruling*, *defense* (only once
   Skarn has arrived), *wander*. He says what he intends in his own words.
2. **What exactly?** He then sees only what matters for that focus and only its tools. Hungry in the
   kitchens: he sees "the cooks' stew pot, fresh bread, and whatever's in the larder" and decides what to
   eat. At the river with a building focus: costs, his past projects, the ruins.

On top of that, the menu only ever offers things that make sense right now (no court outside the throne
room, no raid while a raid is on), tools have cooldowns, he can only talk to the same person twice a day,
and word-for-word repeats are blocked. Skarn still decides in one step - his life is simpler.

## Things: what's lying around, and what he wants

**Stock that changes.** Every place has actual things in it (`city/living/things.py`), restocked each
morning from what that kind of place would have: the kitchens nearly always have bread and stew, sometimes
carrots or honey, very rarely a jar of pickled eels. Leftovers mostly stay. New arrivals are marked
**new today!** in what he sees. Now and then a surprise turns up somewhere - with a model it can be anything
(a barrel of herring at the river, a peddler with strange blue eggs). Whatever he does with things in his own
words uses them: "eat the carrots" eats them, "take the map" puts it in his bag.

**Wants, without rerolling.** If he wants something that isn't in front of him ("I want a carrot"), the
world decides **once** how it could happen, and it becomes a want with a path and a wait:

| Path | What happens |
|---|---|
| it's somewhere in town today | he's told where - go and get it |
| traders bring it | it comes in on the farmers' cart (1 day) or a caravan (a few days) - or the cart breaks down on the north road (decided up front, not rerolled) |
| someone can make it | a **commission** from a real follower with that trade - the blacksmith makes the sword, the tailor the cloak. They hear about it, and get the credit when it's done |
| nobody here has it | it goes in the post: **"👑 The king is looking for: a telescope"** - a follower who brings it gets a reward and the credit |
| it doesn't exist here | the court gently explains (no dragons, no magic). He remembers, so he won't ask again |

Asking again just tells him where it stands. A follower sending the thing ("I bring the king a carrot")
fulfils any want, which beats waiting. Wants he never gets go stale after a week.

## Followers hear what they did (Instagram)

Like sending things to Pino - but through the comments. Everything that happens to or because of a
follower is queued as a **reply to their latest comment** (`dayNNN.outbox.json`; Instagram replies have
to hang off a comment, so this only goes to people who commented in the last 7 days):

| What happened | They get |
|---|---|
| their own-words move played out | the result ("@x tried to steal from @y and got caught...") |
| someone stole from / fought / gifted them | "Meanwhile: ..." |
| the king stopped to talk to their character, or summoned them | what he said and what they answered |
| their case was heard at court (or they waited 2 days for nothing) | the verdict |
| they sent the king a gift ("I send the king a lute") | it arrives at the gate; when he **uses** it, they hear how |
| they suggested something ("I suggest the king builds a bridge") | if he later starts something that matches, they get the credit |
| they brought something the king wanted | a reward, the credit, and "He won't forget" |
| the king commissioned something from their character | the order, then the credit when it's delivered |
| they helped beat a crisis or a raid | "You helped: ..." |
| their house burned in a raid | a note from the neighbours |

The best of it also goes **on their record** (STATUS shows "Your mark on Emberfall") and **into the post**:
the report and caption have a "Your doing today" line naming up to 3 followers whose doing made the story
(ideas taken up first, then gifts used, then heroes). The caption tells people they can send the king a gift
or suggest an idea.

Sending the replies to Instagram is the next piece (the API can reply to a comment, or send one private DM
per comment within 7 days); for now they're written to the outbox file.

## Subjects acting on each other (the viral path)

Own-words comments can name another subject:

| Comment | What happens |
|---|---|
| "I rob @someone" | a roll vs the kingdom's guards (and whether the target is a soldier): gold changes hands, or the thief is caught |
| "I challenge @someone to a duel" / "I punch..." / "I try to kill..." | both characters' strength (army, battles, rank, mood) + luck. The loser is **wounded** for a day or two. **Nobody dies.** The attacker may be **arrested** |
| "I give @someone 20 gold" | gold moves, both get happier |
| "I buy @someone a drink" | they become friends |
| "I mock @someone" | their mood drops, a grudge starts |
| "I beg the king for..." / "I suggest the king..." | goes on the king's docket (and counts as an idea) |
| "I send the king a lute" | a gift: it arrives at the castle; he may use it (and the sender hears about it) |

The model reads what people meant, **the game rolls the result**, then the model narrates it - so it can't
be talked into a win. Arrested people go to the dungeon (or the stocks) and onto the docket; the jailed and
wounded sit out. A target can only be hit by a couple of hostile acts a day (no dogpiles). Two people who
keep clashing become a **feud** - news across the kingdom.

## The warlord

Skarn the Red, like the king, is a name and one goal (`content/warlord.yaml`): take Emberfall. He doesn't
exist for the first few days (`warlord_arrives_day`, default 4) - the king has time to build. The day before,
a shepherd swears he saw riders on the northern hills (nobody believes him). Then, before dawn, smoke rises
over the hills. Raids are possible from the next day; the full horde a week after that.

His camp is a small economy: warriors eat food, food comes from hunting and raiding, morale rises with
victories and falls with defeats and hunger, and the camp only holds as many warriors as its reputation
allows. A raid's difficulty depends on how many warriors he sends, the kingdom's defenses, garrisons, how
many houses are behind walls, and luck. Nobody schedules the war. He reflects at dawn (his bedtime) like the
king does at night. Whether followers can ever join his side is undecided - for now he's the raider.

## Houses and walls

Every follower who moves in gets a house in their hold. **There are no walls at the start** - the town just
trails off into fields. If the king decides to build walls (his idea, his project), everyone living there at
the time - plus a bit of room - ends up inside. People who move in after that build outside, until he
expands them. A raid that gets through **burns houses outside the walls** - real followers' houses, named in
the post ("12 houses outside the walls of Millbrook burned - @a, @b, @c and 9 more"). Neighbours rebuild them
after three days. The town's size (houses inside / outside / burned) is part of what the king sees.

## Events nobody wrote (the director)

Twice a day (06:00 and 14:00) the director looks at what's actually happening - the king's projects and how
they turned out, what he's becoming, the crowd, the houses outside the walls, the war, the weather - and
decides whether something should happen. It prefers **consequences**: things that grow out of what people
actually did. It writes the event itself (title, comment words, what happens either way, what the king could
do). The words are free; the mechanics come from a fixed set of consequences with a size, capped by the
season:

| Days | Tier | Feels like |
|---|---|---|
| 1-7 | 1 | everyday trouble: a cart in a ditch, a stolen pig, a leaky roof |
| 8-18 | 2 | serious: a fire, a failed harvest, sick herds, a scandal |
| 19+ | 3 | disasters: "the king's new dam burst and drowned half the livestock - the town is starving" |

Nobody real dies. Every invented event is saved with the kingdom and sent as a notification. With the
director on, the hand-written list in `content/events.yaml` stays quiet; without a model it keeps the game
going, and the season plan's few beats (coronation, the Reckoning...) still happen either way.

## Every post stays live

A post from a week ago can blow up. Comments on **any** post count, the day they arrive: own-words moves
always work; an old post's words still work if what they were for is still going (WORK always does; FIGHT
only while that battle is on). Words for something that's over get a friendly reply pointing to today's
post. In live mode, each post has its own file: `inbox/comments-dayN.json`.

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
