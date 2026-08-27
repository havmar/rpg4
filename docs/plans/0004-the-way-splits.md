# Plan 0004 — The way splits: forks and rumors

Status: DONE (2026-08-25)

## Sources

Designer-initiated (invited by the player after the session-2 harvest).
Charter §3 names "route choice" among the real decisions the game is
about, and v0.1 has none: `delve` deals one site, take it or leave. This
plan also serves the session-2 feedback that the game needs a dimension
the DM's arithmetic cannot trivialise: rumors are information the engine
deliberately cannot simulate odds for.

## Design arguments (settled here; do not reopen)

- The descent's one repeated verb gets a decision inside it. At most
  depths the way down splits, and each passage is announced only by a
  **rumor** — one sensory line, derived deterministically from what is
  actually behind it. The player chooses on partial information, which is
  the roguelike muscle the game has not yet asked for.
- **Rumors are honest, because the senses are honest — but the world is
  not obligated to be audible.** A rumor reports the loudest thing behind
  the passage. Lurkers make no sound: an encounter consisting only of
  lurkers gets the *identical* quiet line a breather gets. Quiet is
  either rest or ambush, and learning to price that ambiguity is the
  feature.
- The reckoning drum gets no command for forks, on purpose. Odds exist
  for the fight in front of you; what is behind a door belongs to nerve
  and appetite. This is the uncomputable layer, load-bearing by design.
- The unchosen passage is gone once you descend — the Understory does not
  hold doors open. The map remembers it as a road not taken.
- The first delve of every expedition is always a single throat: the
  mouth is known ground, and plan 0003's in-media-res opening (`new`
  executes the first delve) must never stall at a fork.

## Mechanics

### Fork generation

- On `delve` with no fork pending and no pending fight: draw the fork
  shape from the event RNG — **single throat 20%, two passages 65%,
  three passages 15%**. Exception: the first delve of an expedition
  (into depth 1) is always a single throat.
- Single throat: descend immediately, exactly as today, with the line
  "The way down is single here."
- Otherwise: generate each passage as a full site at the next depth
  (deterministic, from the same event RNG draw), respecting plan 0003's
  no-repeat rule *and* requiring distinct template names across the
  fork's passages (pool permitting; repeats allowed as fallback, never
  failure). Store the full sites in `exp["fork"]` (list); print one
  numbered rumor line per passage. No light is spent at the split — the
  rumor is what you hear from where you stand.
- `delve` with a fork pending reprints the rumors and changes nothing
  (no counter bump). `status` shows pending rumors.

### Taking a passage

- `session.py delve <n>` (1-based) takes that passage: 1 light (or the
  `free_delve` stairs), depth increments, the chosen site resolves
  exactly as a generated site does today. The unchosen passages are
  discarded from the save; for each, `{"depth", "rumor"}` is appended to
  `exp["declined"]` (new list, always present).
- `delve <n>` with no fork pending, or n out of range, is a `ValueError`
  ("the way is single here" / "there are only N passages").
- `surface` clears any pending fork and, like the rest of the expedition
  record, the declined list. Retreat after a fight cannot coexist with a
  pending fork (a fork only ever pends before a site is entered).

### Rumor derivation (deterministic; no new rolls)

- `QUIET_RUMOR = "Quiet. Your own lamp is the loudest thing in it."`
  (module constant in content.py; the string used verbatim in both cases
  below — pinned by test as identical.)
- **encounter**: the rumor of the highest-menace non-lurker enemy in the
  group (tie → alphabetical name order). If every enemy in the group is
  a lurker → `QUIET_RUMOR`.
- **breather**: `QUIET_RUMOR`.
- **salvage**: seeded pick (from the fork's generation RNG) out of
  `SALVAGE_RUMORS` (content.py constant, exactly these three):
  - "A glint where nothing should be shining."
  - "Still air over the smell of oil that has not burned in an age."
  - "Shapes with corners — made things, holding their arrangement."
- **strange**: the strange entry's authored `rumor` field.

### Catalog additions (censuses unchanged; `_FIELDS` updated)

`enemies` gain `rumor` — **required for enemies without the `lurker`
trait, forbidden for enemies with it** (validator enforces both
directions):

- shardswarm: "A dry rustling, like sleet on glass, from everywhere at once."
- glasshound: "Footfalls, four-beat, each one faintly ringing."
- cullet crab: "A slow grinding, slag on stone, unhurried and confident."
- fluxworm: "The floor hums, as if something swims through it."
- vitrified watchman: "One voice, one note, repeating a word you almost know."
- chorus pane: "Harmonics. Several. In agreement."
- glazier's remnant: "Tools being laid out one by one, with terrible care."
- custodian stray: "Machinery cycling up: something has noticed you and not yet decided."
- saltfog strangler, mirrorling: lurkers — no field.

`strange` entries gain `rumor` (required on all ten):

- an oil seep: "A slow drip, unhurried, under the smell of good oil."
- bad air: "The draft coming up tastes sweet, and should not."
- a kind stranger: "A footfall. Shod, careful, human-paced."
- a collapse: "Grit sifting down; the ceiling working through an old thought."
- whispering glass: "A murmuring of many small voices, none raised."
- a gift in reflection: "Lamplight coming back from below, a half-beat late."
- a slipped hour: "Your own steps echoed back later than they should be."
- old stairs: "A clean draft rising straight, as through a stairwell."
- a delver's cache: "A frayed rope-end round a rock, tied by someone who knew knots."
- the murmur market: "Trade-cant, softly, from behind something hanging."

### The map remembers

`ui/map.txt`: declined passages print indented under the depth where the
fork stood, as `..unopened: <rumor>`. Taken sites render as today.

### Save

`SAVE_VERSION` → 4 (`exp["fork"]`, `exp["declined"]`). No migration.

## Files

- `content.py` — fork shape draw + passage generation in `advance_delve`
  (split into offer/take paths); rumor derivation; `QUIET_RUMOR`,
  `SALVAGE_RUMORS`; validator clauses for the new `rumor` fields.
- `catalogs/enemies.json`, `catalogs/strange.json` — rumor fields above.
- `session.py` — `delve` gains an optional passage number; `status` shows
  pending rumors.
- `pages.py` — map's unopened lines.
- `engine.py` — `SAVE_VERSION` 4 only.
- `test_content.py` — see expectations.
- `bench_expedition.py`, `tune.py`, `docs/BENCHLOG.md` — see targets.
- `docs/PLAYBOOK.md` — rumor rule (checklist).

## Test expectations (contract suites)

- Determinism: same seed → same fork shapes, same passages, same rumors,
  across an expedition.
- The first delve of an expedition is always a single throat (many seeds).
- The all-lurker encounter rumor and the breather rumor are the identical
  string (`QUIET_RUMOR`), and an all-lurker fork passage is
  indistinguishable from a breather passage in every printed line.
- Mixed group → the highest-menace non-lurker's rumor; menace tie broken
  alphabetically.
- One broken world per validator clause: lurker with a `rumor` field;
  non-lurker missing it; strange entry missing it.
- Fork passages carry distinct template names when the kind/depth pool
  allows.
- `delve` with a fork pending reprints and does not bump the counter or
  spend light; taking a passage spends exactly 1 light (or consumes
  `free_delve`) and discards the others into `exp["declined"]`.
- `surface` clears fork and declined; save shape v4 complete (let it
  raise on absence).

## Bench targets (tune toward; record actuals in BENCHLOG)

- Batch policies always take passage 1. Expedition outcome distributions
  (clear/death rates, banked chits under the plan-0003 policies) stay
  within noise of the 0003 baseline — forks re-shape *decisions*, not
  odds, and the bench proves it.
- Rumor census over 10k generated forks: every authored rumor line
  reachable; `QUIET_RUMOR` frequency reported (the ambush ambiguity must
  be a real, nonzero fraction of quiet passages — if <10% of quiet lines
  hide lurkers, note it for the next design session rather than tuning
  here).

## Checklist

- [x] content.py fork offer/take + rumor derivation + validator clauses
- [x] catalog rumor fields (enemies, strange) exactly as authored above
- [x] session.py delve passage arg + status rumors
- [x] pages.py unopened map lines
- [x] SAVE_VERSION 4; fresh save plays clean end-to-end through several forks
- [x] contract suites green; benches re-run; BENCHLOG entry appended
- [x] PLAYBOOK rumor rule added (embroider but never add or contradict
      information; quiet is only ever the quiet line)
- [x] CLAUDE.md status updated

## Implementation notes (deviations, recorded for review)

- **`advance_delve` no longer takes an rng; it takes `passage=None`.** The
  plan requires that reprinting a pending fork bump no counter, and the
  driver was creating the event RNG (and bumping the counter) *before*
  calling in. Making the RNG internal is the only way the no-cost reprint
  can be true. Every caller updated; `_enter_site` draws its own event RNG
  for the site payload, because a fork's passage was generated one command
  earlier and has no live RNG to inherit.
- **Every generated site carries a `rumor`, not just fork passages.** One
  shape for all sites keeps the RNG stream uniform (the salvage rumor is a
  draw) and means a single throat and a fork passage are the same record.
- **Enemy `rumor` is a declared-optional authored key**, handled by a new
  `_OPTIONAL_FIELDS` map in the validator rather than by loosening the
  strict missing/unknown field checks. Both directions are enforced as
  their own clauses: a lurker carrying a rumor is rejected, and so is a
  non-lurker without one.
- **The map pairs declined passages with sites positionally**, consuming
  the declined queue in order as it walks `exp["sites"]`. Both lists are
  appended in the same order, so this is exact except after a retreat back
  to a depth that later forks again, where an unopened line can print
  under the earlier room at that depth. Cosmetic, on a map page, and the
  alternative is a stored index the plan's `{"depth", "rumor"}` shape does
  not carry.
- The site catalog is thin for forks (two templates per kind at most
  depths), so 7.1% of forks repeat a room name between passages via the
  documented fallback. Flagged in the BENCHLOG for a content pass rather
  than fixed by bending the kind weights.
