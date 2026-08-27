# UNDERSTORY — Engine & Development Guide

*Required reading before any dev work (Charter and CLAUDE.md govern always;
this doc governs how the game is built). Adapted from the RPG2 infrastructure
export (`docs/archive/RPG2_EXPORT.txt`); where they differ, this doc wins.*

## Architecture: a library, not a loop

The game is two halves:

- **Python scripts are a library** of mechanics primitives and content:
  the combat resolver, rest/recovery, stratum and encounter generators,
  catalogs, the character model. They own all the numbers.
- **The agent (DM) calls those primitives on purpose**, in whatever order
  the story wants, and narrates over the results. There is deliberately no
  autopilot for pacing: nothing in code forces an expedition leg to end or
  a camp to happen; the DM decides when to call things. Some calls may be
  automated later; for now, manual on purpose.

Part of the game lives in instructions, not code. Judgement calls,
improvised scenes, and when-to-call-what live in `docs/PLAYBOOK.md`. When a
rule of play is settled that isn't a pure number, write it into the playbook
rather than forcing it into the engine.

The point of an AI-run game is not that the AI narrates — it's that the DM
is a coding agent: subsystems called deliberately, content generated where
needed, coherence kept by the agent, no central game loop required.

## The session driver and save model

- One thin CLI driver, `session.py`, sits over the engine/content modules
  and keeps ALL campaign state (delver, expedition clock, inventory, world)
  in a single `save.json` between invocations. The driver adds no game
  logic; `--help` lists every subcommand with its rules.
- `save.json` is plain JSON on purpose: committable when a playthrough is
  worth keeping, and hand-editable. Editing the save between commands is
  the DM's **override surface** for things no command provides. Convention:
  use it for story reasons, never to edit away an outcome merely disliked.
  Every command reloads the file fresh.
- `save.json` stays untracked by default. During development, saves are
  disposable: wreck them with test games, start over, move on. A keeper
  playthrough is a named exception committed explicitly.
- Every module exposes a standalone eyeball check
  (`python <module>.py --seed N ...` prints a sample) so generators and
  content can be inspected without a full game.

## Intended layout (firm up as code lands; update this list in the same commit)

- `engine.py` — self-contained stdlib-only mechanics core; everything else
  imports it, it imports nothing of ours.
- `content.py` + `catalogs/*.json` — authored content, kept out of the
  engine so the engine stays generic.
- generator modules (strata, encounters, relics, delvers) — self-validating.
- `session.py` — the thin CLI driver.
- `ui/` — committed player-facing pages (rules in the playbook).
- `test_<system>.py`, `bench_*.py`, `tune.py`, `docs/BENCHLOG.md`.
- `LEDGER.md` — the legacy ledger (see playbook; survives everything).

## No backwards compatibility — ever (constitutional)

One player, who is also the project's owner. The loop is: playtest until
something big surfaces, change the game, start a new delver. Therefore:

- Save compatibility is never a design input. No migration shims, lazy
  upgrades, or missing-key fallbacks whose only purpose is loading an old
  save. When a better state shape wins, take it and let old saves break.
- Never add old-save round-trip tests; delete any found when touching
  their files.
- Optimize for the good game. A change that improves play and breaks every
  save is simply better. Refactor freely inside the codebase too — tests
  and benches are the safety net, not frozen interfaces.
- **Corollary — let it raise.** Never soften a reader for a state the code
  cannot produce. A getter returning a neutral 1.0 / 0 / empty list when a
  record it depends on is missing hides a bug. If the constructor always
  builds the record, the missing case is a bug — let it raise. The tell: a
  fallback whose only caller is a test. A test that needs an impossible
  state should build a legal one instead. Declared-optional AUTHORED
  schema keys read with a default are fine — that's reading a schema, not
  tolerating damage.

## Testing and measurement

- **Contract suites**: each shipped system gets `test_<system>.py`
  (plain unittest, `python -m unittest -v test_x.py`) describing the
  model, not the sessions that built it: pinned distributions, determinism
  (same seed → same world), save round-trips within a version, display-page
  invariants, deliberately-unreachable content. Standard trick: **one
  broken world per validator clause** — for every lint the validator
  enforces, one test builds a world violating exactly that clause and
  asserts rejection.
- **Self-validating generation**: constructors call their own validators on
  every build (`validate_world` after worldgen, `validate_catalog` on
  catalog load, import-time validation of record constructors). Authored-
  content censuses are pinned as constants the validator checks, so silent
  content drift fails loudly.
- **Bench suites**: standalone `bench_*.py` scripts measure outcome
  distributions (expedition clear/death rates, economy flow, stratum
  censuses, delver-career sims) over many seeds — and decision health:
  `bench_policy.py` runs competing policies to measure what knowledge and
  choices are worth, because dominant lines and dead options are invisible
  in outcome distributions (rationale in `docs/MECHANICS.md`). After every change that
  could move numbers, re-run and append a dated entry to
  `docs/BENCHLOG.md` — including "nothing moved, byte-identical" entries;
  they are the proof a change is bench-neutral. `tune.py` does the
  outcome-distribution sweep + resource-pressure check in one run.
- **Tuning principle**: the sims understate the player. Batch policies use
  fixed schedules and crude thresholds; a real player paces and times. Sim
  clear rates run below played clear rates, so harsher sim numbers than
  "feels fair" are acceptable — tune for the felt game.
- Benches are also the *vibe-design instrument*: balance is tuned against
  measured distributions, not against the player's patience. When the
  player says a feeling is off, the bench log is where the investigation
  starts.

## Code conventions

- **Stdlib only.** No dependencies, nothing to install.
- **Determinism everywhere**: stable derived child seeds (BLAKE2 off the
  parent's identity); the seeded RNG carried in the save; derived rolls
  keyed off a record's own identity so the answer is the same whenever it
  is asked and survives the save; explicit deterministic ordering for
  pathfinding and tie-breaks — no hash order anywhere.
- **Recomputing readers over stored state**: read surfaces store nothing
  and roll nothing — every answer recomputed from what generation stamped.
  New stored fields are rare and called out as such in the commit.
- Combat entities use identity hashing (`dataclass(eq=False)`) because
  they live in sets; don't switch to value equality.
- Runtime output stays ASCII-safe; on Windows shells pipe with
  `PYTHONIOENCODING=utf-8`.
- JSON catalogs carry a version number the validator checks first;
  obsolete schema keys are actively rejected so old shapes cannot creep
  back.
- **Content locality**: nothing in a shared catalog may name a specific
  place or neighbour — a template must be true everywhere its fit-tags
  admit it. Fixed geography and name pools live beside the map that owns
  them.

## The session cycle (meta-process)

Development runs as separate sessions with distinct jobs. The repo, not the
chat, carries context between them.

- **Design sessions** (frontier model). Harvest `docs/PLAYNOTES.md`, argue
  the design against `docs/MECHANICS.md`, and produce a *plan file*:
  `docs/plans/NNNN-<slug>.md`, a full spec ready to implement with no
  further design decisions — file list, behavior, formulas, catalog
  content, test expectations, target outcome curves stated before
  implementation, and an implementation checklist. Header carries `Status: READY / IN PROGRESS /
  DONE`. A DONE plan is history: never edit it, write a new one.
- **Implementation sessions** (cheaper model). Read ENGINE.md and exactly
  one plan file; implement, tick the plan's checklist, flip its status,
  run tests and benches, commit. For a plan too big for one context, run
  sequential subagent rounds: each round one coherent chunk, tests green
  at the end of each round, the next round started only when the previous
  reports done. The orchestrating session stays thin; the plan file is
  the shared context, and each round updates the checklist so a dead
  session loses nothing.
- **Review sessions** (separate, for bigger changes). Review the diff
  against the plan file — the plan is the review contract.
- **Play sessions** (Opus, on a `play/<delver>` branch). Governed by the
  playbook only. Every play session ends with the wrap-up rite
  (playbook), which is how play feeds back into design.

**The feedback loop**: play wrap-ups append structured notes to
`docs/PLAYNOTES.md`, mirrored to the main branch (same rite as the
Ledger). A design session starts by reading PLAYNOTES, marks each item
HARVESTED (with the plan file that answers it) or DECLINED (with one line
why), and never deletes entries.

## Working with the player (dev sessions)

UNDERSTORY inverts the RPG2 arrangement: the player sets feelings and hard
constraints; the agent designs the details (Charter, "The contract").

- Don't ask the player mechanical-detail questions. Decide, document,
  implement, and report. The player pushes back on feelings; the agent
  proposes the concrete change.
- Real feedback flows both ways, actively: say when something feels weird,
  non-optimal, or joyless from the designer's chair — including when a
  player request would hurt the game. Argue; don't silently comply.
- Post-implementation summaries are the place to be thorough: what
  changed, where, why, measured numbers before and after, what was tried
  and rejected. An over-terse summary that forces follow-up questions
  costs more than a long one.
- No "working as designed" filler in test sessions — just show it working.
- When transcribing chat notes into docs, rewrite into clean prose; never
  paste raw brainstorm wording into permanent docs.
- Docs update in the same commit as the change they describe. Flag any
  doc/code conflict noticed rather than leaving it.
- Commit engine/dev changes and play state separately, always.
