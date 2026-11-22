# Where this is going

**You live here. Comment to change the kingdom.** An AI king rules Emberfall, a kingdom whose subjects
are real followers. Every post is a royal decree, a crisis or a battle. Every season ends with the
Reckoning: the people KNEEL (he keeps the crown) or REVOLT (he's overthrown).

There's a path (season plans) and there's chaos (the storyteller, follow-up events, what the crowd
actually does). The plan decides *what the story is about*; the audience decides *how it goes*.

## Why a kingdom

- **Roles that mean something.** Everyone gets a trade when they follow (farmer, blacksmith, soldier...)
  and can change it any day with `BECOME <JOB>`. Soldiers' FIGHT counts double in battles, so there's a
  reason to enlist before a war.
- **Ranks to earn.** Peasant -> Freeman -> Squire -> Knight (Knight needs battles). The king names a
  **Lord** for each hold every week from its most active, most loyal subjects. Rank shows on your
  STATUS card, with how far you are from the next one.
- **Better stories.** Barbarian hordes, treason in the court, a pretender to the throne, a dragon -
  more fun to watch than a water main.
- **Enemies are never other players.** Wars are against barbarians, Varn (an AI-run rival kingdom) or a
  dragon. Holds can compete (who sends the most fighters) but nobody fights each other.

## The ruler

The AI is king from day one - that character is the show. Later, if the account grows:
- **Crown a follower:** after a REVOLT, the people pick a follower as regent from the top-ranked knights
  and lords, and the AI becomes the scheming royal advisor narrating it.
- **Rival claimants:** two AI personas (the king vs the pretender) campaign; followers choose.

## How a season is built

- **30 days, one post a day.** Each post is about one thing: an event, a decree vote, a battle.
- **Beats** (`seasons/seasonN.yaml`) are the planned days - about one every 2-3 days.
  Between beats the storyteller fills quiet stretches with random events.
- **Arcs** are chains of events that branch on the crowd's choices (`next:` in events).
  Start one with a beat; it runs itself from there.
- **Finale:** a royal audience on day 28, the Reckoning on day 30. The result opens next season.

See the calendar any time: `./kingdom plan --plan seasons/season1.yaml`

## Season 1 - "The Crowning" (written: `seasons/season1.yaml`)

| Week | What happens | Why |
|---|---|---|
| 1 | Coronation, first workday, a harvest festival, the first decree vote (WALLS or GRANARY) | Learn to comment; first taste of power - and the king may overrule you |
| 2 | Bandits, a merchant caravan, a strike or a tournament, **treason**: a real lord (a follower) on trial - DUNGEON or PARDON | Stakes; real people in the story |
| 3 | Midseason recap, a bard mocking the king, then **the barbarian war**: scouts -> raid -> the horde at the gates | The big set piece. Soldiers matter |
| 4 | War aftermath, a **pretender** claims the throne (HEIR or KING), the royal audience, **the Reckoning** | Everything feeds the finale |

## Season 2 - "The Rival Crown" (outline: `seasons/season2.yaml`)

Varn, the kingdom beyond the mountains: an insulting envoy, poaching the guilds, a treaty vote (PEACE or
WAR), maybe a war. Midseason a dragon wakes up (sighting -> attack -> SLAY or PAY). If the king was
overthrown, a new ruler (new persona in `content/ruler.yaml`) starts the season.

## Later seasons (ideas to pull from)

- **The plague year:** holds must quarantine (and suffer) or stay open (and risk it all).
- **Succession:** the king falls ill; the people choose which lord becomes heir - a real follower.
- **The crusade:** the kingdom sails to a new land; holds compete to found the first colony.
- **Civil war:** two holds' lords (real followers) both claim the throne; everyone else picks a side.
  (Players choose sides, but the fighting is still against AI armies.)

## Your weekly routine

1. **Sunday:** look at next week's calendar, tweak beats if the story went somewhere unexpected
   (plans are re-read daily - edit and it takes effect tomorrow).
2. **Daily:** post the video with the day's words; reply to a few STATUS comments.
3. **When something unplanned is perfect:** `./kingdom event start <id>` to jump on it.
4. **New ideas:** write the event, run `./kingdom check`, test it in the test kingdom, then add it to a plan.
