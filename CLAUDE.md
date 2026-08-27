# UNDERSTORY — Dispatcher

This repo is **UNDERSTORY** — an expedition roguelike on a dying earth,
played entirely through a coding-agent session. The agent is the DM and the
developer; deterministic Python scripts are the engine. One player (Marton),
no audience, no product.

This file is the dispatcher: it routes a session, it does not govern one.
(Body kept agent-name-free so it can be copied to another agent's
instruction filename unchanged.)

## Session start — always

1. **Verify the checkout is fresh against `origin/master`** — not against
   the branch you happen to be on. A web session starts on a freshly named
   branch, and pulling *that branch* proves nothing: it can have been cut
   from a stale base (session 3 ran an entire opening on a checkout six
   commits behind master this way). The SessionStart hook
   (`.claude/hooks/session-start.sh`) does the check mechanically — read
   its output; a line saying it fast-forwarded or could not verify is
   load-bearing. If no hook output is visible, do its job by hand:
   `git fetch origin master`, and if HEAD is strictly behind
   `origin/master` with no commits of its own, `git merge --ff-only
   origin/master`. A dirty tree is preserved and understood first, never
   pulled over. A play branch mid-playthrough is *supposed* to be behind
   master — a playthrough keeps its engine; never merge master into a
   live game.
2. Read `docs/CHARTER.md` — the constitution. It overrides habit.
3. Settle the session MODE before doing anything else:

- **Play mode** (running or testing a game): load `docs/PLAYBOOK.md`,
  `docs/SETTING.md`, the `ui/` pages, `LEDGER.md`, and the save. Nothing
  in the dev docs governs the table.
- **Dev mode** (changing the game): load `docs/ENGINE.md` first — never
  start a dev task from this dispatcher alone.

## The document system

- `docs/CHARTER.md` — vision, pillars, the vibe-design contract. Changes
  rarely and deliberately.
- `docs/MECHANICS.md` — the mechanical north star: what makes the game
  good as a game, and the low-playtest measurement strategy that keeps it
  honest. Design sessions argue every plan against it.
- `docs/SETTING.md` — the world seed and tone. Canon accretes in play;
  never contradict a committed fact.
- `docs/PLAYBOOK.md` — how the table is run: session flow, the ui/ pages
  and message protocol, settled non-numeric rules of play.
- `docs/ENGINE.md` — how the game is built: architecture, save model,
  testing/bench infrastructure, code conventions, dev process.
- `docs/BENCHLOG.md` — dated bench entries (created with the first bench).
- `docs/archive/` — provenance (RPG2 infrastructure export). Historical;
  the live docs win.
- `LEDGER.md` — the legacy ledger. The only file that survives everything.

## Hard rules (full versions in the charter)

- **The engine owns the numbers.** All rolls happen in Python with seeded
  RNG. Narrate from engine logs; never invent or override a numeric
  outcome.
- **Autocombat.** A fight resolves in one engine run, at most one
  mid-fight pause. Never round-by-round in chat.
- **No backwards compatibility, ever.** No migration code. A feature that
  breaks the save means a fresh save (a new delver). Only `LEDGER.md`
  survives wipes.
- **Git is the save system.** One playthrough per `play/<delver>` branch;
  ui/ pages committed, `save.json` untracked. Engine code and play state
  are always separate commits, on separate branches.
- **No GUI, no external services, no separate agent process.** The stack
  is this repo plus the agent session.

## Status

v0.1 playable (plan 0001, benched 2026-08-23): full expedition loop —
creation, delve, autocombat with one pause, camp, surface, bank, train,
buy — through `session.py`, with contract suites (`python -m unittest`)
and benches (`python tune.py`). The Vitric Age runs 6 depths and has a
sealed floor. Two playthroughs are on the shelf — `play/hallam-rasp`
(session 1, abandoned mid-descent, ledgered) and `play/teodor-slake`
(session 2, dead at depth 5). Both delvers died on day 1 having banked
nothing, so the haven layer is still untested. Sessions 1–2 were harvested
by the 2026-08-25 design session, which produced plans
`0002-combat-that-costs`, `0003-a-reason-to-surface`, and
`0004-the-way-splits`, and gave the playbook the advice protocol, the
traces rule, and a wrap-up rite without table questions.

Plan 0002 is DONE (save v2): stances carry a damage bonus, rounds burn
lamp oil, armor cracks as you work it, a surge goes through soak, the
fight log tags its own beats for the DM, and a hard fight leaves a mark.
Plan 0003 is DONE (save v3): `new` deals a random delver and executes the
first delve, so day 1 starts underground; the satchel caps what comes
home; Wake posts a daily commission that pays double; and the reckoning
drum (`session.py odds`) answers odds questions out of a rationed supply
of windings, on a seed path that cannot peek at the real fight.
Plan 0004 is DONE (save v4): at most depths the way down splits, and each
passage is announced only by a rumor derived from what is actually behind
it — a passage holding nothing but lurkers sounds exactly like a place to
rest. The unchosen ways close behind you; the map remembers them.

All three plans from the 2026-08-25 design session have landed. Session 3
(`play/marek-culvert`, ledgered) was played on a stale checkout — the
2026-08-23 engine — so the v4 engine remains unplayed; the freshness guard
now exists because of it.

The 2026-08-26 design session wrote `docs/MECHANICS.md` (the mechanical
north star), landed `bench_policy.py` (the policy-tournament bench the
plan-0002 benchlog caveat asked for; it confirmed the skirmish hedge
survives 0002–0004 untouched), and produced plans
`0005-the-cost-of-leaving` and `0006-the-outfitters-shelf`, both READY.
Next milestone: implement 0005 then 0006, then a playthrough on the
resulting engine (save v6). Update this status as milestones land.
