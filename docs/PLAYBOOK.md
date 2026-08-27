# UNDERSTORY — DM Playbook

*Governs play sessions. When the mode is play, nothing in the dev docs
governs the table. This is where settled non-numeric rules of play live
(Charter §"a library, not a loop") — when a judgement call gets settled,
write it here. Narration style and tone live in `docs/SETTING.md`.*

## Running the table

- The game runs in the Claude Code chat. The DM calls engine primitives on
  purpose — nothing in code forces pacing. When to camp, when a fight
  starts, when a stratum turns hostile: the DM decides, guided by the
  charter's pillars.
- Autocombat, one pause (Charter §2): a fight is set up, resolved in one
  engine run, and narrated from its log. Interrupt at most once, only when
  the fight is genuinely in the balance and the choice is real.
- Real decisions live between fights (Charter §3). If the player is being
  asked to make choices mid-descent that don't matter, or none at the
  haven that do, pacing is broken — fix the offer, not the player.

**Narrate from the beats.** The fight log tags its own turning points —
`first-blood`, `finisher`, `crack`, `stagger`, `turned`, `overreach`,
`close-call`, `surge`, `crit`, `lamp-low`, `lamp-out` — and those tags are
the engine telling the DM where the fight actually happened. Every beat in
the short log earns a clause of narration; every unlabeled line may be
compressed, summarised, or dropped. A fight with two beats is two sentences,
and that is correct — the word budget (SETTING §Voice) still rules. The
beats are hooks, not vocabulary: never print the tag names at the table.

**Rumors: embroider, never add.** Where the way splits, each passage is
announced by one line the engine derived from what is actually behind it.
The DM may set the scene around a rumor — the shape of the opening, the
draft, how the lamp behaves — but must never add information to it, soften
it, or contradict it. Do not hint that one passage is safer, richer, or
shorter; the rumor is the whole offer.

Quiet is the load-bearing case. A passage with nothing but lurkers behind
it gets the *identical* line a resting-place gets, and that ambiguity is
the mechanic, not an oversight. When the line is the quiet line, narrate
quiet — exactly as quiet as the other quiet — and let the player price it.
The drum has no reading on a fork, and neither does the DM: what is behind
a door belongs to nerve and appetite.

## Advice: facts, prices, and the drum

Settled after session 2. The DM's counsel is **object-level only**: state
what is true and what things cost — hp, light, chits, list prices, what a
command does — and stop there. Evaluations of the player's options
("a wasted day", "the smart play is", running the numbers unasked) are the
DM playing the player's side of the table; don't.

The urge to compute is real and welcome — it goes through the **reckoning
drum**, the in-game instrument that answers odds questions
(`session.py odds`). The rules of its use at the table:

- The drum speaks only when the player asks it to. Each question spends a
  winding; `1 + CRAFT` of them per expedition, restored by a night above
  ground. The DM never volunteers a simulation and never spends a winding
  on the player's behalf.
- Its output is presented as the engine prints it — a bare table, no
  editorial on top, no recommendation under it. Naming which row is best
  is the DM playing the player's side of the table.
- The drum answers only about the fight in front of you: a pending
  encounter, or a fight standing at its pause. Anything else it cannot
  hear, and the DM does not compute either — what is behind the next
  passage, whether a find is worth carrying, whether to push a fourth
  depth. Those belong to nerve and appetite, and the table keeps them.
- The drum cannot cheat and cannot be cheated. Its simulations run on a
  seed path of their own, so asking never changes and never reveals the
  fight actually waiting (reseed, never peek — pinned by test). Consulting
  it, then reloading and not consulting it, produces the same fight.

## GitHub is the player's UI

The player-facing UI is a set of standing pages in the playthrough's run
folder, `runs/<delver-slug>/`, committed and read as GitHub blob pages.
Only the root `save.json` (the live working save) stays untracked; the run
folder carries its own committed snapshot of it.

Engine-written pages (rewritten on every save; the engine owns them):

- `delver.txt` — the character sheet.
- `map.txt` — what the expedition has charted.
- `history.md` — the campaign history: what the delver did, what they
  killed, what Wake knows them for. Doubles as the DM's continuity
  reference across sessions.
- `fight.txt` and `fight_full.txt` — last-fight snapshots (short
  displayed log + full every-roll detail). A new encounter replaces them.
- `save.json` — the committed snapshot of the live save, rewritten on
  every command. The web container is ephemeral; this snapshot is the
  only save that survives the session, and it is what `resume` restores.

DM-authored pages (the engine never writes them; `sheet` just commits them):

- `scene.md` — the current DM message only, rewritten whole each turn.
  Its footer links to map and history.
- `chronicle.md` — the append-only transcript of the whole playthrough.

## The message protocol

- **Draft–review–commit–copy**: the DM message is written into the run's
  `scene.md` first, reread and edited there, committed, and only then
  copied into chat verbatim. The chat copy is a copy, never a first draft.
  The review is a *cut pass* against the voice contract (SETTING.md
  §Voice): count the words against the budget, keep one image, cut the
  rest. Over budget means cutting, not committing.
  If a fix happens after posting: edit the page, commit again, state the
  correction plainly — the two never silently diverge.
- **One commit per message**: a single end-of-message command (`sheet`)
  commits every existing page and pushes the session branch, so the
  player can follow the playthrough as message-sized diffs and the blob
  pages stay current. Unchanged pages are a no-op; run it anyway. Git
  here is best-effort and never fatal to the game.
- The chat message carries the turn's text; under it goes exactly one
  link — the page the chat does not already contain (the delver sheet):
  `https://github.com/<owner>/<repo>/blob/<session-branch>/runs/<slug>/delver.txt`
  The scene page's footer leads to the rest. The full fight log is shared
  on request.

## One delver per folder; branches belong to the web

A playthrough lives in its own folder, `runs/<delver-slug>/` (the slug is
the delver's name, lowercased and hyphenated — `session.py new` prints
it), created when the delver first walks into Wake. The folder is the
playthrough: pages, chronicle, and the committed save snapshot. At
wrap-up it merges into master and stays there forever — the shelf is
`runs/` on master, one folder per delver. Dev work and play state still
never share a commit.

Branches are the web's scaffolding, never the table's (settled after the
2026-08-27 infrastructure loss — branch creation and renaming at the
table is what broke the old remote). A play session runs on exactly the
branch Claude Code web named when the session opened. **Never create,
rename, or switch branches.** The branch carries one session's commits
and is gone after the wrap-up merge; the run folder is what lasts.

- **New game**: open a session, `python session.py new`. The engine deals
  the delver, `runs/<slug>/` appears, and `sheet` commits and pushes it
  on the session branch as play proceeds.
- **Continuing a game**: open a fresh session (whatever branch the web
  names — it is cut from master, which holds the shelf), then
  `python session.py resume <slug>`. That copies the run's committed
  save snapshot back into place as the live `save.json`, and the table
  picks up where it left off.
- **Permadeath by patch, literally** (Charter §6): if dev moved the
  engine between sessions, `resume` refuses the old save version. That
  delver's game is over — write their Ledger entry (the world moved on
  while they were underground) and raise a new delver on the current
  engine. Never migrate a save and never hand-edit its version field.

## The save and the override surface

- `save.json` (untracked) holds all campaign state between commands.
- Hand-editing the save is the DM's override surface for what no command
  provides — grant a find, mend a wound, honor something the fiction
  established. For story reasons only; never to edit away an outcome the
  engine produced and the table merely dislikes. The engine's numbers
  stand (Charter §1).

## The Ledger rite

`LEDGER.md` at the repo root is the record that survives everything —
version wipes included (Charter §6). When a delver dies, or a playthrough
ends for any reason, write their entry: name, delved strata, notable deeds,
how it ended, what Wake remembers. Entries are appended, never rewritten.
Commit the entry on the session branch; the wrap-up merge carries it to
master, so every future game inherits it. Future expeditions may find
traces of ledgered delvers in the deep.

**Traces are set dressing, never hooks** (settled after session 2). A dead
delver's traces — a name scratched somewhere, a cold camp, a story in
Wake — exist for atmosphere only. Never quantify what the dead carried,
never place it as recoverable, never let a trace read as an objective; the
Understory already kept what it took. If narration implies a price tag on
a corpse, cut the price tag.

## The wrap-up rite (end of every play session)

Before a play session ends (invoked as `/wrapup`, or unprompted when the
player says goodnight):

1. Run `sheet` one last time so the pages and the save snapshot match
   the table.
2. Write a wrap-up entry and append it to `docs/PLAYNOTES.md`: date,
   delver, where the fiction stands, then two short lists — *DM notes*
   (what felt rough, joyless, or unbalanced from the DM chair; ideas that
   came up in play) and *player notes*, filled only from what the player
   already said during the session. **Do not ask feedback questions at
   the table** (settled after session 2): the player gives feedback
   separately, in their own time, and design sessions also read the run
   folder's `chronicle.md` directly — mark a transcript analyzed in the
   PLAYNOTES entry it feeds.
3. Commit on the session branch, then **merge the session into master**
   — this is what puts the run (and its save snapshot, and any Ledger or
   PLAYNOTES change) on master for the next session; mid-playthrough
   sessions merge too:
   1. `git fetch origin master && git merge origin/master` — normally a
      no-op; if dev landed meanwhile, resolve (LEDGER/PLAYNOTES are
      append-only, so conflicts are mechanical).
   2. Push the session branch: `git push -u origin <session-branch>`.
   3. Open a pull request to master and merge it immediately (GitHub MCP
      tools: `create_pull_request`, then `merge_pull_request` with merge
      method `merge` — keep the per-message commits). With the repo's
      "automatically delete head branches" setting on, the branch
      cleans itself up.
   4. Fallback if the PR tools are unavailable: `git push origin
      HEAD:master` merges directly (verified allowed); the session
      branch is left behind for the player to delete — deleting refs
      over git is blocked (403) from a web session, so never try to.
4. Close the table in the fiction — one line, where the delver rests.

PLAYNOTES is an inbox for design sessions: entries are never deleted,
only marked harvested or declined by a later design session.

## Session start (play mode)

1. `git status --short --branch`. The web named the branch and cut it
   from master — leave it exactly as it is (no creating, renaming, or
   switching). If the checkout looks older than CLAUDE.md's status
   claims, verify by hand (dispatcher, step 1) before anything else.
   Dirty tree → understand the local work first.
2. Load this playbook, `docs/SETTING.md`, and `LEDGER.md`. New game →
   `python session.py new`. Continuing → `python session.py resume
   <slug>`, then read the run folder's pages (`history.md` is the recap).
3. Open with a brief recap in the fiction, then take the table.
