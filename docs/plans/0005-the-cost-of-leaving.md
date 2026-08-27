# Plan 0005 — The cost of leaving: pursuit, the prepared exit, stashes, and the career tournament

Status: READY

## Sources

BENCHLOG 2026-08-25 plan-0002 caveat (skirmish takes 60% of best-survival
matchups by declining them; no stance-number tuning can move it; "the
honest instrument is a career bench that prices light — building one is a
design decision"). BENCHLOG 2026-08-26 policy probe on the v4 engine
(skirmish survives 85–100% at every depth; the picked-stance policy beats
the best fixed stance by ~0pp everywhere — the learnable matchup table
collapses into "skirmish unless trivial"). PLAYNOTES session 3 (the
player's own read: "I'll learn which monsters need which stance?").
docs/MECHANICS.md (the live-decisions property; agenda item "price the
exits").

## Design arguments (settled here; do not reopen)

- The hedge is structural, not numeric. `_withdraw` is byte-identical to
  v0.1: every living enemy gets one parting blow, swift two, and nothing
  else happens — no clock, no pursuit, no difference between fleeing a
  patient thing and fleeing a fast one. Under permadeath, a cheap exit is
  close to a dominant strategy, and the probe measured exactly that. The
  fix prices the exit in the same trait vocabulary the player already
  reads: what is chasing you decides what leaving costs.
- Skirmish keeps its identity and pays for it. It is the stance that
  plans its exit — so it keeps the auto-withdraw and gets the *prepared
  exit* (reduced pursuit), but fights worse: insurance you buy with
  attack, not a free option bolted to every fight.
- Leaving costs time, like everything else since plan 0002: one light on
  any withdraw. Deaths *during* flight stay rare from sane hp — the price
  of a flee is economic (light, lost loot, lost depth), not a coinflip
  execution; dying mid-flee should mean you left far too late.
- **Declined: dropping carried salvage on a flee.** Double jeopardy with
  the satchel's own overflow rules, and grim bookkeeping besides. The
  satchel already prices greed; the exit prices time and blood.
- Stashes are push-your-luck plumbing, not banking. Plan 0003 settled
  that only surfacing banks and dying loses everything; both stand. A
  stash converts satchel weight into a *promise to come back* — value at
  a depth, safe from pursuit, worthless unless you return. It dies with
  the delver like everything else (the Ledger stays whole; traces stay
  set dressing).
- The career tournament is the second half of the plan and not optional:
  the fight-layer bench cannot see ward's value (hp preserved across an
  expedition) or the hedge's true cost (light and forgone loot), both of
  which this plan moves. Plan 0002's caveat asked for the instrument;
  this plan builds it.

## Mechanics

### Pursuit (engine `_withdraw` rework)

Per living enemy, parting strikes by trait (first match top-down):

- `lurker`: **0 strikes** — it does not chase; it waits for the next one.
- `swift`: **2 strikes** (as today).
- otherwise: 1 strike.
- `relentless`: its parting strikes are at **+2 atk** (it pursues).

The withdraw itself costs **1 light** (floor 0; a fight already in
darkness burns nothing), before the strikes, with its own line: "You
spend lamp and breath getting clear: -1 light." No new beat tags. The
existing event line and outcome handling stay; the stalemate valve at
round 50 goes through the same (priced) path.

### The prepared exit (skirmish rework)

- `STANCES["skirmish"]`: `(-1, +1, 0, 0)` → **`(-2, +1, 0, 0)`**.
- When the withdraw happens **from skirmish stance** (auto-flee or chosen
  at the pause): every pursuer is capped at **one strike** and
  `relentless` gets **no** +2 — you mapped the way out. Lurkers still 0.
- Auto-flee threshold unchanged (40% hp; `flee_late` mark still 25%).

Tuning levers if targets miss, in order: flee threshold 40% → 35%;
skirmish attack back to −1; withdraw light cost to 2. Touch one at a time
and re-run.

### Stashes

- `session.py stash` — legal only mid-expedition with no pending fight,
  fork, or paused fight. Moves the **entire satchel contents** into
  `save["stashes"]` as one record `{"depth": d, "items": [...]}` (merged
  into an existing record at the same depth). Lines name what was left.
  Stashing nothing is a `ValueError` ("the satchel is empty").
- **Recovery is automatic**: on arriving at a depth with a stash — by
  taking a passage there, or by falling back there after a retreat — the
  stash empties into the satchel, capacity permitting, most valuable
  first, with the satchel's usual keep-the-more-valuable overflow rule;
  what does not fit stays stashed. Lines narrate the recovery.
- Stashes persist across surfacings (that is the point: value waiting at
  depth is the pull back down). They are lost with the delver. `surface`
  does not touch them; `ui/map.txt` prints `..stash: <n> items` under
  each depth that holds one, and `ui/delver.txt` gains a stash summary
  line when any exist.

### The career tournament (`bench_policy.py --careers N`)

The existing fight-layer table stays the default run. With `--careers N`,
also run whole careers (10-expedition cap, plan-0003 save constructor)
under five policies:

- **ramp** and **satchel** — the two existing `bench_expedition` policies,
  reused as baselines.
- **hedge** — always skirmish; every pause answers withdraw; camp when
  hp < 50% with supply; surface when the satchel is full or light ≤
  climb cost + 1.
- **committed** — press at hp ≥ 60% of max, else ward; pause: surge if
  grit ≥ 2, else fight_on at hp ≥ 35%, else withdraw; camp and surface
  as the hedge policy.
- **informed** — per pending encounter, pick the stance by simulating 40
  seeded fights per stance from a deep-copied delver (survival first,
  victory second — the drum's method, bench-side); pause rule as
  committed. Run fewer careers for this policy (N/5, min 20) and print
  the n; it is ~40× the fights.

Per policy report: careers, death %, mean expeditions, mean and median
chits banked per career, mean max depth, mean light burned per
expedition, flees per career. Then two health lines: **knowledge value**
(informed minus ramp, on death % and median chits) and **dominance**
(name any policy that is best on both survival and median chits — the
line the design wants to print is "none").

Forks: all career policies take passage 1 (the plan-0004 convention).

### Save

`SAVE_VERSION` → 5 (`save["stashes"]` always present, list). No
migration.

## Files

- `engine.py` — `_withdraw` pursuit rules + light cost + prepared-exit
  cap; skirmish tuple; SAVE_VERSION 5.
- `content.py` — `stash` verb + automatic recovery on arrival (delve and
  retreat paths); `stashes` in `new_save`.
- `session.py` — `stash` command; `status` shows stashes.
- `pages.py` — map stash lines; sheet stash summary.
- `bench_policy.py` — `--careers` tournament as specced.
- `test_engine.py`, `test_content.py` — see expectations.
- `docs/BENCHLOG.md` — entry with the targets below.
- `docs/PLAYBOOK.md` — one paragraph: pursuit is narrated from traits
  (what chases, what waits), and a stash is the delver's own — never
  someone else's to find (traces stay set dressing).

## Test expectations (contract suites)

- Pursuit: seeded withdraws pin lurker 0 / swift 2 / relentless +2 /
  plain 1; from skirmish, everyone capped at 1 and no relentless bonus;
  lurker-only groups let you leave untouched from any stance.
- Withdraw burns exactly 1 light, floors at 0, burns nothing when the
  fight started dark; the light appears in `result["light"]` and lands
  back on the delver.
- Skirmish tuple change shows in the combatant build and in
  `_switch_stance` deltas; auto-flee still triggers at `flee_frac`.
- Stalemate valve still terminates and pays the same exit prices.
- Stash: stash/recover round-trip preserves items and values; recovery
  respects satchel cap with most-valuable-first and leaves the remainder
  stashed; same-depth stashes merge; stash with a pending fight or empty
  satchel raises; stashes survive `surface` and appear in the v5 save
  shape (let it raise when absent).
- Determinism: a seeded career that stashes and recovers replays
  byte-identical.
- Career tournament: deterministic under a fixed seed; every policy
  produces the full report row; the informed policy's sims draw no seed
  from the real fight path (reuse the plan-0003 reseed-never-peek pin
  pattern).

## Bench targets (tune toward; record actuals in BENCHLOG)

- Fight layer (`bench_policy.py` defaults): skirmish survival ≤ 85% at
  d4–d6 (from 88–89%), and it stays the best-survival stance — the flee
  tool must keep its job, at a price. Picked-vs-best-fixed ≥ +3pp
  survival at two or more depths (the matchup table stops collapsing).
- Flee deaths: withdrawing at ≥ 40% hp dies ≤ 10% of the time in
  committed stances, ≤ 5% in skirmish, at every depth.
- Career layer: **hedge is not dominant** — it may keep the best
  survival, but banks ≤ 60% of committed's median chits; the dominance
  line prints "none". Knowledge value (informed vs ramp) is positive on
  chits or survival, stated in the entry.
- `tune.py` regression: ramp and satchel death rates within ±8 points of
  the plan-0004 baseline (70% / 79% at n=1000) — this plan prices exits,
  it does not re-tune fights.

## Checklist

- [ ] engine.py: pursuit table, withdraw light, prepared exit, skirmish tuple, v5
- [ ] content.py: stash verb, arrival recovery, new_save key
- [ ] session.py stash command + status; pages.py map/sheet lines
- [ ] bench_policy.py --careers tournament (five policies, report, health lines)
- [ ] contract suites green (`python -m unittest`)
- [ ] benches re-run (`tune.py`, `bench_policy.py`, `--careers`); BENCHLOG entry vs targets
- [ ] PLAYBOOK pursuit-and-stash paragraph
- [ ] CLAUDE.md status updated
