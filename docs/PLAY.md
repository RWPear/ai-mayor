# Playing it live (`./kingdom play`)

A live kingdom in your browser, so you can be the followers and see whether it's fun to interact with
before Instagram is connected.

```
./kingdom play --fresh                 # a new kingdom: Aldric alone in his field, at dawn on day 1
./kingdom play --fresh --king llm      # the same with the model (brainbox) - this is where the variety is
./kingdom play                         # pick up where you left off (saved in data/play)
./kingdom play --fresh --crowd 15      # plus 15 made-up followers commenting in the background
```

Then open the address it prints (`http://<brainbox>:8765/?live`).

## The clock

The simulation runs on a real clock in half-hour ticks. A day takes 24 minutes by default: fast enough to
see a day go by in a sitting, slow enough to read what happens and answer it. Change it in the panel
(48 min / 24 min / 6 min / about a minute per day), pause it, or step one tick at a time while paused.
The 3D world follows the clock as it goes.

Today's post closes at 19:00 game time, as it will on Instagram: the day's tallies, the crowning vote, the
chronicle and tomorrow's words all happen then. **Close today's post** runs straight to 19:00 and closes
it.

## Commenting

Type any handle and a comment. A new handle follows on the spot (on the frontier they set off up the old
road like everyone else). Comments play out on the next tick, and own-words moves ("I chop wood all
morning", "I want to start a garden behind my house") within the game hour. The **Ideas** list has some to
try.

On the frontier, newcomers arrive together on arrival day, a week away. **Bring the road in** brings
everyone on the road in now, so you don't wait a week of game time to test settlers.

## Replies wait for you

Every reply the kingdom would send shows up under **Replies** as pending. Approve it, reject it, or edit it
and approve. Nothing is posted anywhere (in the Instagram version, this is where the approval step goes).
**What happened** is the running log: your comments, Aldric's moves, arrivals and the post closing.
"Only mine" filters both to the handle you're commenting as.

## Aldric's mind

The third tab shows what the king is thinking and why:

- **Who he is:** each new kingdom gets a different man: who he was before (a shipwright's son, a monk who
  lost his faith, a poacher...), his temper, what he loves and can't stand, sometimes a technique from his
  old trade. Plus his goal, the goals he's set himself, who he's becoming, his last thought and his needs.
- **What he chose:** every decision, marked `model` or `rules` (no model, model out of budget, or the model's
  answer didn't work), with the arguments and his thought.
- **What the model was asked, and what it said:** every call (the king's two steps, designs, the crowd, the
  narrator), with the exact system prompt and situation it was given, its raw answer, how long it took and
  the temperature. This is where to look when he's predictable: if the prompt hands him an example, he'll
  usually take it.

## Under the hood

`city/play.py`: the world ticks in a background thread; comments go into a queue that's drained before
each tick; the scene, state and feed are cached after each tick, so the browser never waits on the model.
The day's reports are saved in `data/play/days` like any run, so `./kingdom serve --days data/play/days`
and `./kingdom record --days data/play/days` work on a live kingdom too.
