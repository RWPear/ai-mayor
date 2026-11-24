# Playing it live (`./kingdom play`)

A live kingdom in your browser, so you can be the followers and see whether it's fun to interact with
before Instagram is connected.

```
./kingdom play --fresh                 # a new kingdom: Aldric alone in his field, at dawn on day 1
./kingdom play --fresh --king llm      # the same with the model (brainbox) - this is where the variety is
./kingdom play                         # pick up where you left off (saved in data/play)
./kingdom play --fresh --crowd 15      # plus 15 made-up followers commenting in the background
./kingdom demo                         # a 50-person kingdom ten days in (built on the rules in seconds), live
./kingdom demo --people 80 --days 14 --king llm
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

Type any handle and a comment. A new handle follows on the spot, walks into Emberfall and gets a little house
of their own. Their first comment gets a reply that welcomes them and plays out what they said. Comments play
out on the next tick, and own-words moves ("I work the farm all day", "I help build the tavern", "I put a new
roof on my house") within the game hour. The **Ideas** list has some to try.

**Every comment is People Power.** Everyone works a shift a day anyway; someone who comments works two, and
what they say steers them to that work (the farm, the brewery, a building going up) - you'll see them walk over
in 3D. Keep at the same work four days and you become it. The evening count ("People Power today: 64 shifts...")
is in **What happened**, and the left-hand panel shows gold, shifts, happiness and what people want.

**One move a day, then talk.** Each person's first real attempt of the day is their move: it changes
the world (chopping, building, brewing, stealing). A question or a joke ("who do I have to kill to get a
drink?") isn't a move - it's answered in the world and they can still make their move after. Once they've
moved, further comments are conversation: Aldric or a neighbour answers in the scene, nothing is gained or
lost, and trying to do something big gets set up for tomorrow. Up to 3 talk replies per person per day
(`TALK_PER_DAY` in `city/living/intents.py`); more comments than that still count, but get no reply.

**The world remembers.** Each person's last few moves, what they said, and what they were told go to the
narrator, so threads carry on (the goat that follows you, Aldric's unanswered question).


## Replies wait for you

Every reply the kingdom would send shows up under **Replies** as pending. Approve it, reject it, or edit it
and approve. Nothing is posted anywhere (in the Instagram version, this is where the approval step goes).
**What happened** is the running log: your comments, Aldric's moves, arrivals and the post closing.
"Only mine" filters both to the handle you're commenting as.

### Not spammy

- Only comments from the last game day get replies. Someone who commented a week ago doesn't hear about
  things now (it still goes on their record and can make the post).
- One comment gets at most two replies: the answer, and one "later" with whatever else happened to them.
- Anything that happens before a reply goes out is folded into it (Aldric talking to them, court, moving in);
  a newer bit of the same kind replaces the older one, so four chats with the king become one.
- One open court case per person: asking again updates it.

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
