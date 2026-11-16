# Where this is going

**You live here. Comment to change your city.** An AI mayor runs a city whose citizens are real
followers. Every post is a decree window. Every season ends with the people deciding the mayor's fate.

There's a path (season plans) and there's chaos (the storyteller, follow-up events, what the crowd
actually does). The plan decides *what the story is about*; the audience decides *how it goes*.

## How a season is built

- **30 days, one post a day.** Each day's post is about one thing: an event, a vote, a crisis.
- **Beats** (`seasons/seasonN.yaml`) are the planned days - about one every 2-3 days.
  Between beats the storyteller fills quiet stretches with random events.
- **Arcs** are chains of events that branch on the crowd's choices (`next:` in events).
  Start one with a beat; it runs itself from there.
- **Finale:** a town hall on day 28, the recall vote on day 30. The result opens next season.

See the calendar any time: `python -m city.run plan --plan seasons/season1.yaml`

## Season 1 - "Founding Days" (written: `seasons/season1.yaml`)

Teach the controls one at a time, build the mayor's character, plant the rivalry.

| Week | What happens | Why |
|---|---|---|
| 1 | Grand opening, first workday, a block party, the PARKS vs POLICE budget vote | Learn to comment; first taste of real power |
| 2 | First crisis (water main), the tech HQ decision, a branch on how happy people are, the councilor scandal (a real follower!) | Stakes; real people in the story |
| 3 | Midseason recap, heatwave, **Port Calder** mocks the city | Introduce the villain; the rival arc runs itself |
| 4 | Budget trouble or a boom, rent spike, town hall, **recall vote** | Pressure builds to the finale |

## Season 2 - "The Rival" (outline: `seasons/season2.yaml`)

Port Calder is the antagonist. Poaching, a trade war (ATTACK / DEFEND / SURRENDER), truce offers.
The city is bigger, so ward rivalries matter. If the mayor was recalled, a new mayor (new persona in
`content/mayor.yaml`) arrives with different priorities.

## Season 3 - "Boom or Bust" (idea)

Growth milestones drive it: the stadium, the newspaper digging into City Hall, a housing crisis as the
city fills up. Possible twist: the people elect one of the councilors (a real follower) as deputy mayor.

## Later seasons (ideas to pull from)

- **Election instead of recall:** two AI candidates with different personas campaign; followers vote.
- **Disaster season:** a flood/earthquake arc where wards have to cooperate or abandon each other.
- **Port Calder joins as a second city** with its own followers - the audience literally splits.
- **Corruption season:** the newspaper milestone uncovers a conspiracy over several weeks.

## Your weekly routine

1. **Sunday:** look at next week's calendar, tweak beats if the story went somewhere unexpected
   (plans are re-read daily - edit and it takes effect tomorrow).
2. **Daily:** post the video with the day's commands; reply to a few STATUS comments.
3. **When something unplanned is perfect:** `city.run event start <id>` to jump on it.
4. **New ideas:** write the event, run `city.run check`, test it in the test city, then add it to a plan.
