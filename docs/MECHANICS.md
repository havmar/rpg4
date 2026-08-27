# UNDERSTORY — Mechanics North Star

*What "mechanically good" means for this game, and the strategy for getting
there with very little human playtesting. Design sessions read this after
the charter and argue every plan against it. It interprets the charter's
pillars into testable properties; where they conflict, the charter wins.
Changes deliberately — less rarely than the charter, more rarely than a
plan.*

## The shape of the game

No spatial layer, autocombat, one player, permadeath, an expedition loop:
those constraints pick the genre for us. UNDERSTORY's strong form is a
**push-your-luck engine-management game about pricing risk under a clock** —
kin to Incan Gold and Deep Sea Adventure at the expedition layer, to
autobattlers at the fight layer, to the roguelike meta-loop at the career
layer. Three nested loops, each with its own kind of decision:

- **A fight is a bet you configure, not a puzzle you pilot.** Skill at this
  layer is pricing: knowing what an encounter will cost in hp, grit, and
  time given your build — and therefore whether to take it at all, and in
  what stance. The engine rolls; the player underwrites.
- **An expedition is a hand you play.** Light, supply, hp, and grit are the
  chips; depth is the multiplier; bank-or-push is the recurring decision
  the whole game orbits. Charter pillar 3 lives here — this is the layer
  that must be deepest.
- **A career is an engine you build.** Training, gear, and unlocks bend the
  odds the next hand is played at. Death converts a career into Ledger
  knowledge for the next one.

One asset no board game has: the DM is a coding agent. Content can be
generated and re-priced continuously, and the fiction itself can carry
odds — a rumor is a probability wearing a costume. Information design is
narration design here, which is exactly the kind of mechanic this table
can run and a cardboard one cannot.

## What "feels good" decomposes into

Four properties. Every plan states which of these it serves; every
mechanic that serves none of them is narrative dressing (allowed, but
budgeted as content, not counted as depth).

1. **Informed bets.** Before any commitment the player can estimate the
   odds well enough to own the outcome. Dying on a known 60/40 push feels
   fair — regret with hindsight is the genre's pleasure. Dying to numbers
   that were never readable is the one unforgivable feel-bad. Implies:
   telegraphs in narration, scouting and appraisal as purchasable
   information, a stable trait vocabulary so reading transfers between
   enemies, and fight logs that show *why* an outcome happened. The test
   applied to every death: could the player have known?

2. **Live decisions.** At every recurring choice point, a competent player
   sometimes picks each option. A dominant line (one choice that is always
   right) or a dominated option (never right) is a bug of the same
   severity as a crash — and it is *silent*: outcome benches don't show
   it, only policy probes do (see the instrument stack). Liveness beats
   balance: options need not be equal, they need to trade against each
   other so context decides.

3. **Decisions change shape, not just size.** Acquisitions should add
   verbs, exceptions, and couplings — things that alter what the resolver
   or the map *does* — not only +1s. The career layer is allowed its
   Diablo drip: training is numbers-get-bigger and that is an honest
   pleasure. But the expedition layer earns its depth from options that
   reconfigure play (a new stance, a kit slot, a relic with a procedural
   exception, a verb that spends one currency to move another). Universal
   Paperclips' lesson, translated: the strata should periodically change
   what game is being played — "deeper is older is stranger" is a
   phase-shift engine, not just a difficulty dial.

4. **One economy, tightly coupled.** Richness per rule comes from resource
   *couplings*, not resource count. Every currency should convert into at
   least two others under pressure; every fight and site outcome should
   touch at least two currencies. Depth is the exchange-rate dial: deeper,
   better prices, worse odds. Light is the master coupling — nothing in an
   expedition is free if it costs time and time costs light. The Fallen
   London feel of *variety* is welcome, but it lives in content skins
   (salvage names, rumor flavors, strange sites) over a small coupled
   core, never in parallel disconnected subsystems.

## Where the game stands (audit of the save-v4 engine, 2026-08-26 — see BENCHLOG same date)

Plans 0002–0004 already built a large part of what this document asks
for, and the policy probe (`bench_policy.py`) measures what remains:

- **Informed bets**: substantially real. Enemy names announce before the
  stance choice; the reckoning drum sells true Monte Carlo odds out of a
  CRAFT-metered supply (0003); forks are announced by honest rumors whose
  quiet case is deliberately ambiguous (0004), and the fork layer is
  uncomputable by settled design — nerve and appetite keep a domain the
  drum cannot price. The remaining gap is not information but the thing
  the information is about: see live decisions.
- **Live decisions**: plan 0002 fixed one dominance (press, once tempo
  cost light, became the best *committed* stance at every depth — ward's
  hp-thrift now trades against press's light-thrift, though only a career
  view can weigh that trade). The probe shows the other dominance intact:
  **skirmish survives 85–100% at every depth and the picked-stance policy
  beats "always skirmish" by ~0pp** — `_withdraw` is still v0.1, so the
  exit is free and the matchup table collapses into it. Priced exits are
  plans/0005; the career tournament that can finally weigh ward, light,
  and the hedge honestly ships in the same plan.
- **Shape**: knacks, marks, beats, and the drum are real shape; gear is
  still six weapons and four armors of stat-stick, and chits sink only
  into train/buy. The outfitter's shelf — kit with declared auto-triggers,
  relics that refuse to be money, stances worth learning — is plans/0006.
- **Coupling**: the light/supply/hp/grit web now includes fight tempo
  (0002) and carry weight (0003 satchel, with commissions as the pull
  home). Still loose: leaving a fight costs nothing (0005), and value
  cannot be committed at depth (0005's stashes — weight converted into a
  promise to come back).

## The strategy: strong mechanics with almost no human testing

Honesty first: benches prove *not broken*; only play proves *good*. The
plan is to spend machines on everything machines can measure, so the
player's rare sessions are spent only on what they can't — feel, fairness
perception, joy. Four instruments, cheapest first:

1. **Closed form at design time.** The resolver stays simple enough to
   reason about (d20 vs guard is 5% per point; TTK expectations are
   arithmetic). Complexity budget is spent on content-side exceptions
   (traits, effects, relics), never on resolver opacity. Every plan
   states its **target curves before implementation** — "fresh delver d1
   death ≤5%, d4 a coinflip" — so tuning has a spec, and BENCHLOG entries
   verify against stated intent instead of vibes.

2. **Policy tournaments** (`bench_policy.py`, the workhorse). Fixed
   policies — naive, greedy, cautious, matchup-informed, oracle-picked —
   run through fights and careers. Three health numbers fall out:
   - *Knowledge value*: informed minus naive. Must be meaningfully
     positive, or learning the game pays nothing.
   - *No dominant line*: no trivial policy tops the tournament, at either
     fight or career layer, under either utility (survival-max and
     progress-max both — a line dominant under both is certainly a bug).
   - *Skill ceiling*: oracle minus best-simple — the headroom mastery has.
   The v0.1 probe caught the skirmish hedge on its first run; this
   instrument works and stays.

3. **Agent table-tests.** Scripted probe playthroughs on disposable saves,
   played by the agent in DM-and-player mode. Agents are poor judges of
   fun, so they are not asked about fun; they are detectors for
   obvious-choice streaks, unreadable outcomes, log illegibility, tedium —
   and for joyless narration, which the charter makes a first-class design
   bug and which the DM chair *can* feel directly. Findings land in
   PLAYNOTES like any session's.

4. **The player's sessions are aimed experiments.** Each human session
   gets one question it exists to answer, agreed up front — "does death
   read as fair?", "is the pause a spike?" — and the wrap-up rite harvests
   exactly that. One expedition is a complete unit of play; short is fine.

## Content scales without testing when it composes

The player's time budget means content must mostly ship unplaytested.
Safe, because content divides in two:

- **Content on existing hooks** — new enemies from the established trait
  vocabulary, new sites, salvage, rumors, strange skins — is safe by
  construction: validators and pinned censuses gate the shape, the bench
  sweep catches curve drift, and re-pricing is a number in a JSON file.
  This is where volume lives (new strata, new epochs, wide catalogs), and
  where the Fallen London sense of a teeming world comes from.
- **New hooks** — a trait, a verb, a stance, an effect type — are design
  changes: plan file, target curves, policy probe, then volume may use
  them. The vocabulary is the game; grow it deliberately, one epoch's
  worth at a time, so each stratum re-poses the pricing problem instead
  of extending the old answer key.

## The five-point agenda, reconciled (2026-08-26)

Where each item stands after plans 0002–0004, and where the rest lives:

1. **Price the exits.** Open — the probe's confirmed dominant line.
   Specced in full as `plans/0005-the-cost-of-leaving.md`: pursuit priced
   by trait (lurkers don't chase, relentless does), withdrawing costs
   light, skirmish pays attack for its prepared exit, and the career
   policy tournament lands as the instrument that can finally weigh it.
2. **Couple fight length to the clock.** DONE — plan 0002 (rounds burn
   light every 4th, press converts risk to flat damage, armor cracks). An
   independent design session reached it from the played evidence one day
   before the probe reached it from measurement; keep both instruments.
3. **CRAFT is the knowledge axis.** DONE, better than first sketched —
   plan 0003 gave CRAFT the satchel and the drum's windings (odds as a
   rationed in-game instrument), plan 0004 gave route information as
   honest rumors. Mechanizing Ledger knowledge is DECLINED: the traces
   rule (playbook) keeps dead delvers as set dressing, never priced.
4. **Shape-changing acquisitions.** Open. Specced in full as
   `plans/0006-the-outfitters-shelf.md`: kit with auto-triggers declared
   at purchase (no mid-fight buttons — the one-pause law holds), relics
   that are worn instead of banked, brace and read as bought stances that
   answer the game's existing telegraphs.
5. **Sharpen bank-or-push.** Half done — the satchel and commissions
   (0003) are the weight and the pull home. The remainder — stashes that
   convert weight into a promise to come back — ships with 0005; the
   bank-it-or-wear-it choice on relics ships with 0006.

## The standing answer to the standing worry

The depth budget lives between fights — the charter already says so. The
fight itself only has to be a *readable, configurable bet*, so autocombat
is not the obstacle to mechanical goodness; opacity and free hedges are,
and both are measurable. The failure mode this document exists to prevent
is drift toward flat mechanics by default — additive numbers under thick
narrative — because nobody was measuring. Flat is a legitimate *choice*
for a designated subsystem (strange sites are one); it is not the fate of
the game.
