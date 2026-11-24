# Roles: anyone can be anything

Every follower starts as a plain settler: nobody on the island has a trade yet. They learn a craft by doing it
(three tries, good or bad) - or they can be **anything** they say: a thief, a beggar, a rat catcher, a fortune
teller, a monk, a smuggler. The code is `city/trades.py`. (A role is who they are; conjuring a dragon is something
else - see Wonders in [FRONTIER.md](FRONTIER.md).)

## Taking up a role

Any of these, on any post:

| Comment | What happens |
|---|---|
| `BECOME THIEF`, `become a rat catcher` | they take up that life; the reply says what it gives them |
| `I'm going to be a fortune teller at the tavern` | same |
| `i am a thief!` | they take it up too, **but the kingdom laughs**: "Sure you are. And I shit piles of gold. Fine - from today you're a thief. Prove it." |
| `i am a thief!` after three real thefts | "Everyone knows. Shopkeepers pull their purses closer when you walk past." |
| `I become a monk and pray for @sam` | the role changes quietly and the rest plays out as their move |
| `i am the king`, `I become a knight` | laughed at; nothing changes. Titles are earned (knight: three battles and the deeds) or given (lords are named by the king) |
| `i become a dragon` | "A dragon. Sure. The chickens are terrified." |

One new life a day. The label is theirs word for word ("royal rat catcher"); the kingdom files it under the
role it really is ("rat catcher").

## What a role is underneath

Each role is mapped once (by the model, or the built-in role book for ~70 common ones) and remembered, so
every thief works like every other thief:

| | |
|---|---|
| **faction** | commoners, guilds or army - who they side with when the king takes a side |
| **income** | none / low / normal / high, and whether it's **illegal** |
| **place** | where they're found: the tavern, the chapel, King's Street, the river... The king bumps into them there |
| **knack** | the one thing that bends their dice (below) |
| **skills** | the crafts they actually know: the forge, brewing, healing, stonework, horses, boats, the bow, music, reading and writing, hunting, locks |
| **homeless** | no house (see below) |

## The perks (knacks)

| Knack | Who has it | What it does |
|---|---|---|
| sneaky | thieves, pickpockets, spies, smugglers | +20% to steal, caught half as often |
| strong | soldiers, mercenaries, miners, bandits | harder to beat in a fight |
| crafty | smiths, masons, tailors, cooks, carpenters | their work pays 20% more; gifts they make for the king are hand-made |
| charming | merchants, bards, beggars, con artists, fortune tellers | friendships count double, cons caught less |
| holy | priests, monks, nuns | `I bless @name` really lifts someone's spirits (and loyalty) |
| healing | healers, herbalists, physicians, witches | `I heal @name` gets a wounded person back on their feet |
| learned | scholars, scribes, wizards, alchemists | their petitions go to the top of the king's list |
| wild | hunters, rat catchers, vagrants, scouts | at home outdoors |

Using your own trade pays: a rat catcher setting traps on King's Street "knew exactly what they were doing"
and earns a bit of gold.

## The limits (skills)

Try a craft your role doesn't know and it goes wrong (one time in five, beginner's luck saves you):

> **i am a thief! i sneak into the blacksmiths house and forge a sword**
> From today you're a thief. You're a thief, not a blacksmith. You got in without a sound - that part you
> know. Then you grabbed the hot end of the tongs and burned your hand. You'll be nursing that for a day.

Some mishaps just embarrass you (the crowd throws cabbages at your lute playing), some hurt (wounded for a
day: the forge, brewing, stonework, horses), and breaking in without knowing how lands you in the stocks.
Anyone can walk, talk, fight, steal or work - that needs no skill; thieves are just better at stealing.
**There is no real magic in Emberfall**, so even wizards get the goat: "A goat watched, unimpressed.
Nothing happened."

## Reputation

What the kingdom knows you as comes from what you've done, not what you say:

| Deeds | Known as | Effect |
|---|---|---|
| 3 thefts | a known thief | the guards watch you: worse odds, caught more |
| 4 fights won | a brawler people step around | |
| 3 heals | a healer people trust | |
| 4 blessings | a holy soul | |
| 5 good days at your trade | good with their hands | |

It's on their STATUS card, and it's what decides whether "i am a thief!" gets a laugh or a nod.

## Illegal work and sleeping rough

- **Illegal income** (thieves, smugglers, con artists) pays, but every evening there's a small chance the
  guards catch up with them: a fine, a night locked up, and a case on the king's docket. Known thieves get
  caught more, and better defenses mean more patrols.
- **Homeless** (beggars, vagrants, hermits): no house. Nothing for raiders to burn, nothing worth stealing,
  but each night without a roof wears their mood down. They sleep at the chapel, where the king might find
  them. Taking up a trade again puts a roof over their head (a hut outside the walls).

## Who sees roles

- The **director** sees who lives in the kingdom ("12 thieves, 4 beggars, 3 known thieves, 5 sleeping
  rough") when it invents events: lots of thieves can mean a crime wave.
- The **king** sees people's roles when he walks around ("@sam (beggar, no roof, grumpy)"), and petitions
  arrive labelled ("@sam (a beggar): ...").
- The **narrator** knows each subject's role and lets it colour the scene.
