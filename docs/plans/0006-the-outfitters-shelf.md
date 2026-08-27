# Plan 0006 — The outfitter's shelf: kit, relics, and stances worth learning

Status: READY (implement after 0005; its exit prices and career
tournament are assumed throughout)

## Sources

docs/MECHANICS.md (the shape property: expedition-layer acquisitions must
add verbs and exceptions, not only +1s; agenda items "shape-changing
acquisitions" and the choose-one-loot remnant of "sharpen bank-or-push").
BENCHLOG 2026-08-25 plan-0003 (the haven is now reachable — 72% of crude
careers bank an upgrade — but the shelf it reaches holds six weapons and
four armors, all stat-sticks). PLAYNOTES sessions 2–3 (visible machinery
is a feature; the standing worry that mechanics stay flat).

## Design arguments (settled here; do not reopen)

- Chits currently buy two things: stats (rare, large) and gear (once,
  then never again). A shelf of small procedural purchases makes every
  surfacing a real spend decision, and — because half the shelf counters
  specific traits — it makes bestiary knowledge worth money. This is how
  "learn the monsters" graduates from picking a stance to outfitting an
  expedition.
- **Kit triggers are declared at purchase and resolve automatically.**
  Autocombat with one pause is constitutional (Charter §2); nothing here
  adds a mid-fight button. Kit is insurance you bought at the surface;
  the fight spends it for you when its condition arrives. The pause
  options do not change.
- **A relic is salvage that refuses to be money.** Relics are found, not
  bought, and every one poses the same question: bank it for a lot of
  chits, or wear it and keep its exception until you die. Equipping is
  permanent and exclusive (one slot; equipping over a relic shatters the
  old one). No stash-and-decide-later bookkeeping — the tension is the
  mechanic.
- New stances are bought knowledge. Any delver may learn them (chits,
  not stat gates); whether they fit the build is the player's read. Both
  new stances are answers to things the game already telegraphs —
  ambushes, and the light clock — so the vocabulary grows in directions
  the player has already been taught to look.
- **Declined: mechanizing Ledger knowledge** (dead delvers seeding rumors
  or free appraisals). The traces rule is settled table law: traces are
  set dressing, never hooks, never priced. What Wake learns from its dead
  lives in narration.

## Mechanics

### Kit (new catalog `catalogs/kit.json`, census 6)

`delver["kit"]`: list of held kit records (name/effect/text copies, the
marks pattern), **cap 2**, at most one of each item. Bought at Wake via
`buy <name>` (the market lists kit under its own header). Kit persists
across expeditions until consumed; lost with the delver. Effect ids in
`engine.KIT_EFFECTS`; hooks live where they live (marks precedent).

| name | value | effect id | trigger and effect |
|---|---|---|---|
| oil flask | 6 | `oil` | `use "oil flask"` mid-expedition: +3 light. |
| dressing roll | 8 | `dressing` | auto, after a fight ends with you alive at ≤ ⅓ hp_max: heal 1d6 (event RNG). |
| flash powder | 10 | `flash` | auto, at fight start when any enemy is a `lurker`: no lurker gets the round-1 ambush bonus this fight. |
| shard-hook rope | 9 | `rope` | auto, on withdraw: the exit costs no light and `swift` pursuers lose their extra strike. |
| tithe of oilbread | 7 | `oilbread` | auto, on camp: the camp costs no supply (light as normal). |
| drum key | 12 | `drumkey` | `use "drum key"` mid-expedition: +2 windings. |

Every trigger consumes the item, with its own line. `use <name>` is a new
session command (expedition only; unknown or unheld kit raises).
Blurb/text authored at implementation in SETTING tone. Fields
`{name, value, effect, text}`; validator: effects from `KIT_EFFECTS`,
names unique, census 6, locality rule.

Rope + prepared exit stack by rule text, not arithmetic: skirmish already
caps everyone at one strike; rope's swift-cap is then moot and only its
light refund applies.

### Relics (new catalog `catalogs/relics.json`, census 5)

- **Finding one:** at a salvage-kind site of depth ≥ 3, the first rolled
  item is replaced by a seeded relic pick with probability **12%** (event
  RNG; duplicates across a career allowed — a second copy is just
  money). Victory-loot and strange-site salvage never roll relics: they
  are found where salvage is the whole point, deeper than the easy
  galleries.
- A carried relic is a satchel item like any other (value below; the
  satchel's overflow rule treats it by value). Surfacing banks it like
  any salvage. Stashing stashes it.
- **`equip <name>`** — any time outside a fight, pending fight, or fork.
  Moves the relic from satchel to `delver["relic"]` (single slot, record
  stored whole). Equipping over an existing relic destroys the old one,
  with a line. There is no unequip. The equipped relic survives
  surfacing and dies with the delver.
- Effect ids in `engine.RELIC_EFFECTS`; fight-facing effects are copied
  onto the combatant at build (the light/kit pattern).

| name | value | effect id | exception |
|---|---|---|---|
| the tuning hammer | 30 | `hammer` | your landed hits crack **any** enemy with soak > 0 (not just `armored`); crits strip 3. |
| the still lamp | 25 | `still_lamp` | fight rounds never burn light; `light_max` −2. |
| the patient mirror | 35 | `mirror` | the first enemy hit that lands on you each fight is halved (before grit). |
| the pilgrim's bell | 25 | `bell` | lurkers never get the round-1 ambush bonus; every dread test is at −1 dread. |
| the assayer's seal | 40 | `seal` | commissions pay triple instead of double; `windings_max` +1. |

### Stances worth learning (`learn <stance>`)

`delver["stances"]`: always present; starts as the four base stances.
`learn brace` / `learn read` at Wake, **25 chits** each, permanent.
`content.start_pending_fight` validates the chosen stance against
`delver["stances"]`; `engine.STANCES` itself gains both entries and stays
permissive (benches drive it directly). Pause stance-switching offers
only known stances.

- **brace** `(-1, +2, +2, 0)` — the planted stance. Additionally: lurkers
  get no round-1 ambush bonus against a braced delver. The permanent
  sibling of flash powder; the anti-ambush commit.
- **read** `(-2, +1, 0, 0)` — the study stance. From round 3 on, attacks
  are at **+5** over the base (net +3): stateless bonus computed at
  strike time when `stance == "read"` and `round >= 3`, with one
  importance-1 line the first time it applies ("You have their pattern;
  it repeats."). Read wants a long fight, and long fights burn light —
  it buys accuracy with the clock, the exact opposite trade from press.

### Market and pages

`market` lists weapons, armors, kit, and unlearned stances with prices;
`status` and `ui/delver.txt` show kit held, the equipped relic, and known
stances beyond the base four.

### Save

`SAVE_VERSION` → 6 (`kit`, `relic` (None or record), `stances` on the
delver). No migration.

## Files

- `engine.py` — brace/read entries + their strike/ambush logic;
  `KIT_EFFECTS`, `RELIC_EFFECTS`; combatant kit/relic flags; hammer,
  still-lamp, mirror, bell, flash, rope hooks in the resolver;
  `light_max`/`windings_max` relic terms; SAVE_VERSION 6.
- `content.py` — kit/relic catalog load + validation (censuses 6 and 5);
  relic roll in the salvage-site path; `buy` extended to kit; `use`,
  `equip`, `learn` verbs; dressing/oilbread/seal hooks; stance-known
  validation.
- `catalogs/kit.json`, `catalogs/relics.json` — new, exactly the tables
  above.
- `session.py` — `use`, `equip`, `learn` commands; market/status output.
- `pages.py` — kit, relic, stances on the sheet.
- `test_engine.py`, `test_content.py` — see expectations.
- `bench_policy.py` — the fight-layer table picks up brace and read
  automatically from `engine.STANCES` (bench delvers know everything);
  the career tournament's committed and informed policies gain a
  shopping step (below).
- `docs/BENCHLOG.md`, `docs/PLAYBOOK.md` (one paragraph: kit fires
  itself, narrate the trigger; relics are worn, not discussed — the drum
  has no row for them).

## Test expectations (contract suites)

- One broken world per validator clause for both catalogs: bad effect id,
  duplicate name, census off, locality violation.
- Each kit item: its trigger fires exactly when specced, consumes the
  item, and does nothing when unheld; kit cap 2 and no-duplicates
  enforced at purchase; `use` raises on unheld kit and outside an
  expedition.
- Rope: withdraw burns no light and swift pursuers strike once; from
  skirmish, still once (no stacking artifact).
- Relic roll: seeded d≥3 salvage sites produce each relic across seeds;
  d1–d2 and victory loot never do; equip moves satchel → slot, equipping
  over a relic destroys the old, banking an unequipped relic pays its
  value; equipped relic survives surfacing.
- Each relic effect pinned in a seeded fight or reader: hammer cracks the
  unarmored, still lamp skips the round-4 burn and lowers `light_max`,
  mirror halves only the first landed hit, bell suppresses ambush and
  eases dread DCs, seal triples exactly one commission unit and adds a
  winding.
- brace: ambush suppressed, tuple applied; read: +5 from round 3 only
  while in read, stateless across pause switches (switching in at the
  pause gains it from the next round ≥ 3; switching out loses it).
- Stance learning: `learn` gates on chits and Wake, fights refuse unknown
  stances at the content layer, the pause offers only known stances;
  save v6 shape complete (let it raise otherwise).

## Bench targets (tune toward; record actuals in BENCHLOG)

- Stance liveness with six stances (`bench_policy.py` defaults): no
  stance is the pick in > 55% of encounters at d2–d5, and at least four
  stances are picked ≥ 10% somewhere in d1–d6. read is the pick for
  ≥ 10% of encounters somewhere at d3+ (the long-fight niche exists);
  brace for ≥ 10% somewhere lurkers spawn.
- Career tournament: give committed and informed a shopping step (buy the
  cheapest unheld kit while chits ≥ cost + 20; equip the first relic
  found). **Shoppers beat their non-shopping selves** on death % at equal
  or better median chits — the shelf must earn its prices; if it loses,
  reprice kit downward before touching effects.
- Relic sightings under the satchel policy: 0.3–1.2 per career (rare
  enough to be an event, common enough to exist).
- `tune.py` regression: ramp/satchel death rates within ±8 points of the
  post-0005 BENCHLOG entry (the shelf is optional power; crude policies
  that ignore it should barely move).

## Checklist

- [ ] catalogs/kit.json + relics.json; content validation, censuses 6 + 5
- [ ] engine.py: brace/read, kit/relic effect hooks, effect id sets, v6
- [ ] content.py: relic roll, buy/use/equip/learn, hooks, stance gate
- [ ] session.py commands + market/status; pages.py sheet lines
- [ ] bench_policy.py: six-stance table + shopping policies
- [ ] contract suites green (`python -m unittest`)
- [ ] benches re-run; BENCHLOG entry vs targets
- [ ] PLAYBOOK kit/relic paragraph
- [ ] CLAUDE.md status updated
