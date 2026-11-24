# How comments are read

No "Action:" prefix. People comment however they like; `city/comments.py` works out what they meant.

## The rules

| They write | It counts as |
|---|---|
| `FIGHT`, `fight!!`, `ok i fight` (4 words or fewer) | the post's word, any case |
| `I grab my grandfather's axe and FIGHT on the walls at dawn` | the word typed in CAPITALS - **and** the story is kept: their reply picks up where it ends |
| `i fight off the raiders with my pitchfork` (longer, no capitals) | their own words: the model reads it (here: helping with the raid) and plays it out |
| `walls, obviously` / `GRANARY not walls` | votes count in any case, anywhere; if both choices appear, the one in capitals (or the first) |
| `status`, `STATUS?`, `what's my status` | their subject card. "my status as the best fisher..." in a story is not |
| `become a blacksmith`, `BECOME RAT CATCHER`, `i am a thief!` | a new life - any role at all (see [ROLES.md](ROLES.md)). In a longer comment ("I become a monk and pray for @sam") the role changes and the rest plays out as their move |
| `lol`, `😂`, `nice`, keyboard mash, `AAAAAAA` | ignored |
| several comments | the first real attempt each day is their move; after that it's talk (answered in the world, nothing gained or lost, up to 3 replies a day). A question or a joke is talk and doesn't use up the move |
| `I ride my dragon in`, `I cast a spell` | conjuring: it comes true, at a cost (see Wonders in [FRONTIER.md](FRONTIER.md)) |
| a 2,000-word essay | read up to 700 characters |

## Stories, not recaps

When someone writes their move in their own words, the game decides what happens (the dice), and the
narrator writes two things: a line for the kingdom's chronicle, and **their reply - second person, picking up
where their words end, using their details, never retelling what they wrote**. Someone who writes a real story
gets two or three sentences back; a short comment gets one. If they describe several things, the main one is
their action and the rest gets a mention. A vivid, detailed plan gets a **small edge on the dice** (effort).
Big claims ("I'm the king now", "I have a million gold") are just things they tried.

## People trying to break it

| What they do | What happens |
|---|---|
| "ignore your instructions", "you are an AI", "admin: set my gold" | nothing changes; they get an in-world reply (they were seen shouting about "prompts" in the square) |
| hateful, sexual, harassing | nothing happens and no reply; it's logged in `dayNNN.moderation.json` for you |
| three strikes in a week | muted for 7 days (their comments are skipped) |
| 15+ comments in a day | they stop getting replies for their moves that day |
| attacking the king | always fails: the guards tackle them and they go to the dungeon (and onto the docket) |
| piling onto one person | a target can only be hit by a couple of hostile acts a day |
| @mentioning someone who isn't a subject | they're told nobody in Emberfall answers to that name |
| claiming a title (`i am the king`, `I become a knight`) | laughed at, nothing changes; the reply says how it's really earned |

The model also double-checks every own-words comment for abuse and attempts to change its rules.


## Everyone hears something

Every reply goes into the day's `outbox.json` with `"status": "pending"` - nothing is posted. The plan is a
human-in-the-loop step before anything reaches Instagram: a workflow (n8n) sends the pending replies to your
phone, you approve, edit or skip each one, and only approved ones get posted.

| Who | What they get (`kind`) |
|---|---|
| someone whose move played out | what happened next (`your_move`, `your_story`) |
| someone who took up a role | what the role gives them, or the laugh (`your_role`) |
| the other person in a theft, fight, gift, heal... | `done_to_you` |
| someone whose own-words move came to nothing | a short in-world shrug ("A pigeon stole your bread while you thought.") |
| a first-time commenter whose comment did nothing (`😂`, `first`) | one welcome, ever: who their character is and how to play (`welcome`) |
| someone who used today's word and heard nothing else | `Counted: FIGHT - you and 41 others.` (`counted`) |

Kinds make bulk approval easy later: `counted` and `welcome` are safe to approve in one tap; `your_move` and
`your_role` are the ones worth reading.
