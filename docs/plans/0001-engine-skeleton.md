# Plan 0001 — Engine skeleton and first playable loop

Status: DONE (designed and implemented in the same session; this file is the
design record and the pattern for future plans)

## Goal

A delver can be created, descend into the Vitric Age, fight via autocombat
(one pause), salvage, surface, bank, train, buy gear, and die into the
Ledger — all driven through `session.py`, with ui/ pages, contract tests,
and benches. Stdlib only, deterministic, no backcompat.

## Files

- `engine.py` — seeds/RNG core, dice, delver math, the autocombat resolver
  (pause + resume), site-effect application. Self-contained, imports
  nothing of ours.
- `content.py` — catalog loading + validation (censuses pinned), the
  encounter builder, the site generator. Imports engine.
- `catalogs/*.json` — backgrounds, enemies, gear, salvage, strange, sites.
  All `"version": 1`; validator checks version first, rejects unknown keys.
- `session.py` — thin CLI driver; all state in `save.json` (untracked).
- `pages.py` — ui/ page writers (delver.txt, map.txt, history.md,
  fight.txt, fight_full.txt) + best-effort `sheet` commit.
- `test_engine.py`, `test_content.py` — contract suites.
- `bench_combat.py`, `bench_expedition.py`, `tune.py` — benches.

## Mechanics (v0.1)

**Attributes** (1–6, base 2): EDGE (offense), IRON (defense), VIM (body),
NERVE (resolve), CRAFT (wits/salvage).
Derived: `hp_max = 8 + 3*VIM`; `grit_max = 1 + NERVE` (+knack);
attack bonus `2*EDGE + weapon.acc` (+knacks, stance, shaken, darkness);
guard `8 + IRON + armor.guard + stance`; soak `armor.soak + stance`.
Heavy armor: −1 attack.

**Expedition resources**: light (10 + knack; −1 per delve; darkness at 0:
delver −2 atk, enemies +2 atk, dread +2), supply (3; camp = −1 supply −1
light, heal `2d6+VIM` (+knack), grit to max), carried salvage (lost on
death), chits (banked at Wake only).

**Autocombat**: internal rounds, seeded rng, event log with importance
flags (full log = all lines; short log = flagged lines). Attack: d20 +
bonus vs guard; nat 1 misses, nat 20 crits (max damage); damage dice −
soak, min 1 on a hit. Delver targets lowest-hp enemy. Order: lurkers first
in round 1 (+4 that round), then swift enemies, then delver, then the rest.
Traits: swift, lurker, brittle (+2 damage taken per hit), relentless
(+2 atk when delver below half), armored (statline only), pack
(builder spawns 2–3 copies), dread N.
Dread at fight start: d20 + 2*NERVE (+knack) vs 10 + 2*maxdread, fail →
shaken (−2 atk, −1 guard) until steadied.
Grit auto-spend: a hit that would drop the delver spends 1 grit to halve
that damage (repeatable while grit lasts).

**The pause**: at most once; after a round when the delver is alive, at or
under 60% hp, round ≥ 2, enemies still up. Options (filtered by state):
switch stance, steady (1 grit, if shaken), surge (2 grit: next attack
auto-hits for double dice), withdraw (each living enemy one free attack,
swift two), fight on. Fight state (enemies, round, rng state, events) is
JSON-serialized into the save; resume is deterministic — pausing and
choosing `fight_on` replays identically to an unpaused fight.

**Stances** (chosen per fight, the pre-fight decision): measure (0/0),
press (+3 atk / −2 guard), ward (−2 atk / +3 guard / +1 soak), skirmish
(−1 atk / +1 guard, auto-withdraws below 40% hp).

**Outcomes**: victory (loot: scrap chits = 2 × group menace, 70% one
salvage item from the depth band), retreated (fall back one depth, no
loot), down = dead (Ledger).

**Sites**: `delve` increments depth (capped at 6 — the Vitric Age has a
sealed floor, for now), draws site kind (encounter .50, salvage .25,
strange .15, breather .10), fills from templates fit-tagged by kind +
depth band. Encounter menace budget: `1 + depth ± 1` (bench-tuned down
from `2 + 2*depth`; see BENCHLOG 2026-08-23). Salvage sites: 1–2 items. Strange events carry an
effect id the engine applies (oil_seep, bad_air, kind_stranger, collapse,
reflection_gift, time_slip, old_stairs, whispering_glass, found_cache,
murmur_market). `surface` from depth d costs ceil(d/3) light; missing
light hurts 1d6 each.

**Wake**: rest (free full heal + refit), `train <stat>` costs `15 * new
value` chits (cap 6), `buy <item>` from the gear catalog at listed value.

**Creation**: `new <Name> [--seed S]` shows 3 candidates (distinct
backgrounds, stat array [3,3,2,2,2] assigned by background priorities, one
seeded extra +1); `--pick N` finalizes. Backgrounds carry gear + a knack:
lamplighter (+2 light), cutter (+1 atk), glasspicker (+1 chit/salvage),
salvage-priest (+2 dread tests), surgeons-runner (+3 camp heal),
archivist (+1 grit max).

**Determinism**: `child_seed(*parts)` = BLAKE2b of "/"-joined parts; save
carries `world_seed` and an event `counter`; every rolling command draws
`rng_for(world_seed, "evt", counter)` and bumps the counter. No hash
order anywhere; all ordering explicit.

## Checklist

- [x] engine.py (seeds, dice, model math, resolver, pause/resume, strange effects)
- [x] catalogs + content.py with pinned censuses and per-clause validation
- [x] session.py commands: new/status/delve/fight/camp/surface/train/buy/market/log/sheet
- [x] pages.py writers + sheet commit
- [x] contract suites green (`python -m unittest -v`)
- [x] benches run; BENCHLOG entry appended
- [x] .gitignore save.json; CLAUDE.md status updated
