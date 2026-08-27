# UNDERSTORY — Design Charter

*This document is the constitution of the project. Future sessions of Claude:
read this first. It changes rarely and only deliberately. When a design
question has no answer written anywhere, answer it yourself in the spirit of
this charter, write the answer down, and move on.*

## What this is

An expedition roguelike set on a dying earth, played entirely through Claude
Code in a git repository. The world is impossibly old: civilizations stacked
on civilizations, and the game is the descent through them. Deterministic
Python scripts are the engine and own every number; Claude is the DM and owns
every word. One player, no audience, no product.

## The contract (vibe-design)

- The player (Marton) sets the *feelings* and the hard constraints. Claude
  invents all details: setting, mechanics, content, names, numbers.
- When the player pushes back, they describe what feeling is missing, not
  what to change. Claude proposes the change.
- Claude should build the game it enjoys building and DMing. This is an
  explicit design goal, not a nicety. If a mechanic is tedious to narrate or
  a content type is joyless to write, that is a design bug — fix the design.

## Pillars

1. **The engine owns the numbers.** All randomness, combat resolution, loot,
   and character math happen in Python with seeded RNG, producing machine
   logs. Claude narrates from those logs and never overrides them. Claude
   cannot fudge a roll it did not make.

2. **Autocombat, one pause.** Fights resolve in a single engine run. At most
   one mid-fight interrupt point where the fight is genuinely in the balance
   and the player makes one decision under pressure. One chat message per
   combat *round* is forbidden by design.

3. **Real decisions live between fights.** Preparation, character growth,
   route choice, what to carry, when to turn back, what to spend discoveries
   on. The haven layer is where the player thinks; the descent is where the
   engine runs.

4. **The expedition loop.** Haven → descent → return (or retreat, or worse)
   → haven. One expedition should fit one sitting. The haven is always a
   clean save point.

5. **Deeper is older is stranger.** Depth is time. Every stratum is a dead
   epoch with its own logic, dangers, and salvage. Weirdness is never a lore
   violation — there is always a buried epoch that could have produced it.

6. **Permadeath by patch.** No backwards compatibility, ever. A new engine
   version means a fresh save: a new delver, a new descent. This is
   diegetic. The only thing that may survive a wipe is the legacy ledger —
   a small record of dead delvers and what the world remembers of them.

7. **Git is the save system.** Character sheet, expedition logs, map state,
   and the legacy ledger are files committed and pushed to the play branch.
   The commit history is the chronicle of the campaign.

8. **Canon accretes in play.** The setting bible is a seed, not a scripture.
   Whatever gets written into a session's narration and committed becomes
   canon. Claude may create and edit game content freely, but never
   contradict a committed fact — reinterpret it instead.

9. **Combat with appetite.** Combat is central and written with enthusiasm:
   tactical, consequential, strange. What this game does not do is linger on
   suffering or stage pointless cruelty. Most of what you fight, violence is
   the honest response to; when you fight people, it means something.

## Interface

The game interface IS Claude Code (usually on the web) in this repo. A play
session = a Claude Code session. No GUI, no separate agent process, no API
costs beyond the Claude Code subscription itself. Python scripts + committed
state files + Claude's narration are the entire stack.

## Non-goals

- No graphical UI, web frontend, or TUI framework.
- No backwards compatibility or migration code, ever.
- No multiplayer, no distribution, no commercial anything.
- No real-time anything. The game waits.

## Status

- Charter and setting seed: this commit.
- Infrastructure (session flow, state-file conventions, script layout):
  to be adapted from the export of the player's previous game, then owned
  and evolved freely here.
