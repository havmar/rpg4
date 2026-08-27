# Plan 0003 — A reason to surface: the satchel, commissions, the drum, and a faster start

Status: DONE (2026-08-25)

## Sources

PLAYNOTES sessions 1–2 (haven layer never played; CRAFT dead; site
templates repeated; no stat legend; Monte Carlo should be a first-class
command with a reseed-never-peek constraint) and session-2 chat feedback
(fully random delver, start already delving; DM odds/advice should be
either absent or deliberately designed — leaning in, as a rationed in-game
resource; the market advice overreach; the dead-delver line that read as a
quest hook).

## Design arguments (settled here; do not reopen)

- Two delvers died on day 1 with full coats and empty accounts because
  every decision gradient pointed down: salvage value scales with depth,
  and surfacing only ever bought a reset. The fix is pull, not punishment:
  a hard carry limit makes "my bag is full" a natural turnaround, and a
  standing commission makes surfacing a payday instead of a concession.
- **Declined:** banking a fraction of carried salvage on death. Dying with
  thirty-seven chits on you is the tragedy; softening it would hollow out
  the Ledger (Charter §6).
- CRAFT becomes the expedition-logistics stat: satchel size and drum
  windings. Both are preparation-shaped, which is what a wits stat should
  buy in a game where real decisions live between fights (Charter §3).
- Character creation offered a pick-of-three with nothing to base the pick
  on — a fake choice, and a slow open. The game now deals you a stranger,
  already underground. First real choice of a playthrough: what to do
  about depth 1.
- The odds question is settled by leaning in, diegetically. The DM's urge
  to compute is real and useful (session 2's Monte Carlo was the best tool
  at the table); unmetered, it trivialises every numeric decision. So the
  computation becomes an object in the world with a meter on it — the
  reckoning drum — and the DM's own voice stays object-level (playbook
  change, already landed with this plan's design session).

## Mechanics

### Fast, fully random start

- `session.py new [--seed N] [--force]` — no name argument, no `--pick`,
  no candidate parade. One delver is rolled: name from the new names
  catalog (given + family, seeded draw), background drawn from all 6,
  stats by background priorities over `[3,3,2,2,2]` plus one seeded +1,
  gear from the background. `content.delver_candidates` is replaced by
  `content.roll_delver(cat, world_seed)`.
- The same command then begins the expedition and executes the first
  delve: the save opens at depth 1 with a generated site (pending fight,
  salvage, strange, or breather — whatever the seed deals). Output: a
  compact sheet block, then the site. Day 1 starts underground; the DM
  introduces the delver in media res.
- New catalog `catalogs/names.json` (`"version": 1`): `given` (20) and
  `family` (20), census pinned as `names: 40`, all names locality-clean.
  Tone: Wake names sound like worn tools — two syllables, consonant
  edges (the existing canon: Hallam Rasp, Teodor Slake, Odile Rasp).

### The satchel (carry limit; CRAFT job #1)

- Capacity: `4 + CRAFT` salvage items.
- "scrap glass and fittings" stacks: all scrap merges into one carried
  entry whose value accumulates; it occupies one slot total.
- On a find with a full satchel: keep the more valuable — the engine
  auto-drops the lowest-value carried item if the new find beats it,
  otherwise the find is left behind. Lines narrate what was dropped or
  left. No mid-delve prompt (the save is the DM's override surface for
  the rare story exception).
- `status` and `ui/delver.txt` show `satchel n/cap`.

### Commissions (the pull)

- `save["wake"]["commission"]` — always present: `{"item": <salvage
  name>, "bonus": <int>}` where `bonus == item value` (a filled
  commission pays double). Drawn seeded at save creation and re-drawn on
  every surfacing (the new day's posting); any salvage item may be drawn.
- On `surface`: if carrying one or more of the commissioned item, exactly
  one unit banks at `value + bonus`, with its own line and a history
  entry; then the new commission is drawn and announced.
- `market` and `status` show the standing commission.

### The reckoning drum (odds as an in-game resource; CRAFT job #2)

- Fiction (seeded in SETTING.md): a Lattice-epoch instrument the
  assay-house rents to delvers; wind it and it clicks out odds for a
  question shaped like a wager. It only answers about the fight in front
  of you — that is all it can hear.
- `delver["windings"]`: starts at `1 + CRAFT`, resets on surfacing. Each
  `odds` call burns one; at 0 the command refuses ("the drum is spent").
- `session.py odds [--n 2000]`:
  - With a pending encounter: one row per stance × pause policy from
    `{fight_on, surge, withdraw}` (surge rows only if grit ≥ 2). Each row
    simulates `--n` fights of a deep-copied delver against the pending
    specs.
  - With a paused fight (`odds` at the pause): one row per legal pause
    option, simulated from a deep copy of the paused state.
  - Output per row: win / retreat / dead %, mean rounds, mean hp
    remaining on win, mean light burned. Plain table; the DM copies it
    verbatim (playbook rule: the drum's output gets no editorial on top).
- **Integrity (constitutional for this feature): reseed, never peek.**
  Simulation seeds derive from a dedicated `save["odds_counter"]` path —
  `child_seed(world_seed, "odds", odds_counter, row, i)` — and resumed
  simulations replace the stored `rng_state` with a per-sample seeded
  RNG. The real fight's seed path (`"fight"`/`counter`, or the stored
  `rng_state`) is never drawn, so consulting the drum cannot change or
  reveal the actual outcome. Pinned by test.

### Site templates don't repeat within an expedition

- `generate_site` takes the set of template names already used this
  expedition (from `exp["sites"]`) and excludes them from the template
  pool; if exclusion would empty the pool for that kind/depth, repeats
  are allowed (fallback, not failure).

### The stat legend (session-1 debt)

`ui/delver.txt` gains, under the stat line:

```
  EDGE   swing      (attack rolls)
  IRON   stand      (guard)
  VIM    endure     (hp)
  NERVE  hold       (grit, fear)
  CRAFT  provision  (satchel size, drum windings)
  grit: luck you spend    light: time underground    supply: nights of camp
```

### Save

`SAVE_VERSION` → 3 (windings, commission, odds_counter, satchel shape).
No migration.

## Files

- `content.py` — `roll_delver`; satchel cap + scrap stacking + overflow in
  salvage-gain paths; commission draw/fill in `do_surface` and save
  creation; site no-repeat; names catalog validation (census `names: 40`);
  windings reset on surface.
- `catalogs/names.json` — new.
- `session.py` — `new` reworked (rolls + first delve); `odds` command;
  `status`/`market` additions.
- `engine.py` — nothing (odds simulation drives existing entry points).
- `pages.py` — legend, satchel line, windings, commission on the sheet.
- `test_content.py`, `test_engine.py` — see expectations.
- `bench_expedition.py`, `tune.py`, `docs/BENCHLOG.md` — see targets.
- `docs/SETTING.md` — already carries the drum seed (landed with the
  design session); extend only if implementation needs a term.
- `docs/PLAYBOOK.md` — drum table-rules paragraph (checklist).

## Test expectations (contract suites)

- `roll_delver` determinism: same seed → same delver, name included; all
  six backgrounds and both name lists reachable across seeds.
- `new` produces an active expedition at depth 1 with a site, in one
  command; save version 3 shape complete (marks, windings, commission,
  odds_counter all present — let it raise otherwise).
- Names catalog: one broken world per validator clause (census off,
  duplicate, locality violation).
- Satchel: overflow keeps the more valuable item and reports the drop;
  the find is left when it is the cheapest; scrap stacks to one slot;
  cap tracks CRAFT.
- Commission: surfacing with the item banks exactly one unit at double
  value; surfacing without it banks normally; either way a new commission
  is drawn (the posting is daily). Test both paths.
- Drum: `odds` before a fight leaves the eventual fight byte-identical to
  a no-odds run (the reseed-never-peek pin); windings decrement and
  refuse at 0; reset on surface; `odds --n 50` table row percentages sum
  to 100.
- Site no-repeat: seeded expedition never repeats a template name until
  the pool for that kind/depth is exhausted.

## Bench targets (tune toward; record actuals in BENCHLOG)

- Add a batch policy "turn back when the satchel is full or hp < 40%".
  Under it, median banked chits per expedition > 0 and median career
  (delver until death) banks enough to buy at least one gear upgrade —
  the haven layer must be reachable by a crude policy, because sims
  understate the player.
- Day-1 career deaths under the new policy < 50% of runs.
- Commission uptake: in sims that surface carrying 3+ items, the
  commission fills in ≥ 20% of surfacings (sanity that the draw isn't
  unfillable).

## Checklist

- [x] catalogs/names.json + validation; roll_delver; new = roll + first delve
- [x] satchel (cap, scrap stack, overflow) + sheet/status lines
- [x] commissions (draw, fill, redraw) + market/status lines
- [x] odds command + windings + odds_counter; reseed-never-peek test pinned
- [x] site no-repeat
- [x] delver.txt legend
- [x] SAVE_VERSION 3; fresh save plays clean end-to-end
- [x] contract suites green; benches re-run; BENCHLOG entry appended
- [x] PLAYBOOK drum-rules paragraph added
- [x] CLAUDE.md status updated

## Implementation notes (deviations, recorded for review)

- **`content.new_save(cat, world_seed)` is new.** The save shape was being
  hand-built in three places (`session.cmd_new`, the content suite, the
  career bench) and this plan adds three keys to it. One constructor is
  the only way a no-migration save shape stays honest; the hand-built
  copies are gone.
- **`satchel_cap` and `windings_max` live in `engine.py`**, beside
  `light_max`, not in `content.py`. They are derived readings off
  `delver["stats"]`, which is what the engine's delver-math section is
  for, and it keeps `pages.py` importing nothing but the engine. The
  plan's "engine.py — nothing" line is about the odds simulation, which
  is indeed content-side.
- **`simulate_odds` lives in `content.py`; `session.py` only prints it.**
  ENGINE.md: the driver adds no game logic of its own. The command,
  its flags and the table layout are the driver's.
- **The delver is deep-copied once per `odds` call, not once per sample.**
  `engine.start_fight` never mutates the delver it reads (it builds a
  combatant from it), so per-sample copies would buy nothing at 24,000
  samples a table.
- **Pause-policy fallback.** A row's policy can become illegal by the time
  its sample reaches the pause — `surge` after the grit auto-spend ate
  the grit. Such a sample falls back to `fight_on` rather than raising, so
  a surge row reads "surge if you still can, else keep at it", which is
  what the player would actually be able to do.
- **The commission is drawn on the standard event-RNG path**
  (`_evt_rng`, counter bumped): it is an ordinary seeded world event.
  Only the drum uses the separate `odds_counter` path, because only the
  drum must be unable to disturb the fight stream.
- The `satchel` bench policy dies *more* than `ramp`, not less; see the
  BENCHLOG entry for why that is a crude-policy artifact rather than the
  carry limit being lethal.
