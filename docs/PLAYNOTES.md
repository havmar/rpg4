# PLAYNOTES — the play → design inbox

*Appended by the wrap-up rite at the end of every play session; mirrored to
the main branch. Design sessions read this first, mark each item
`[HARVESTED → plans/NNNN]` or `[DECLINED — reason]`, and never delete.*

---

## Session 1 — 2026-08-23 — Hallam Rasp (`play/hallam-rasp`)

Reconstructed from post-session chat feedback; the wrap-up rite did not run
at the table. (Next play session: end with `/wrapup`.)

**Where the fiction stands:** Hallam Rasp, surgeon's-runner, three deep in
the Vitric Age at the glass orchard — 9/17 hp, 13 chits carried, nothing
banked. The delve-or-surface choice is live.

**DM notes:**

- CRAFT is a dead stat: it appears in the stat list, background priorities,
  and training, but no formula reads it. Chits spent training it buy
  nothing. Needs a design decision — give it a job (salvage value? light or
  supply efficiency?) or drop it. `[HARVESTED → plans/0003 — CRAFT becomes
  the expedition-logistics stat: satchel size and drum windings.]`
- The delver sheet lists the five stats without saying what they do; the
  player had to ask what VIM is. Add a short legend to `ui/delver.txt` or a
  stats note in the playbook. `[HARVESTED → plans/0003.]`

**Player notes:**

- Best moment: wanting to go deeper — the tension between surfacing to
  restock and pressing on. Light as a resource works.
- First impulse was to explore the steppe around Wake instead of
  descending (played the descent to test the game). `[DECLINED for now —
  the surface is deliberately thin; depth is the game's axis (Charter §5).
  If the steppe ever matters it is overland travel between mouths, a later
  milestone, not a second exploration layer.]`
- Worst friction: narration length. The player reads for the object level;
  the poetry accumulated. `[HARVESTED → SETTING.md §Voice + playbook
  message-protocol cut pass, settled in the same commit as this entry.]`

---

## Session 2 — 2026-08-25 — Teodor Slake (`play/teodor-slake`)

**Where the fiction stands:** Teodor Slake, cutter, dead at depth 5 in the
annealing hall of the Vitric Age, killed by a vitrified watchman he had
ground down to 5 of 14. Twelve rounds, one pause, one surge that did 1
damage. Thirty-seven chits on him, none banked, day one. The Ledger now has
two pages — Hallam Rasp's was written at the top of this session, closing
his run, and Teodor's at the bottom. Wake has buried two men who never made
it to a second day.

**DM notes:**

- **Ward is a solved axis.** It was the arithmetic favourite in all four
  stance decisions this session. Soak applies *per incoming hit*, so +1 soak
  scales with the number of blows, while −2 attack only costs tempo — and
  tempo is free, because **a fight burns no light and no other resource**.
  Nothing in the game punishes a long fight except the hp it costs, which is
  exactly what ward minimises. Fix candidates: a per-round or per-fight light
  cost; a fatigue/round clock; press granting damage rather than only
  accuracy; capping stance soak. `[HARVESTED → plans/0002 — fights burn light every
  4th round; press gains flat damage.]`
- **The damage floor (`max(1, dmg - soak)`) makes high-soak enemies a wait,
  not a threat.** Against the watchman's soak 4, a 1d10 dealt **1** on any
  roll of 1–5 — half of all landed hits. The result was twelve rounds of
  chip damage. Slow is not the same as tense. `[HARVESTED → plans/0002 — the armored
  trait now cracks: delver hits strip soak.]`
- **Surge can be a dud, and that is the worst bug of the session.** Two grit
  — the game's marquee spend, a swing that *cannot miss*, double dice — came
  up 2d10 = 2, minus soak 4, floored to **1 damage**. The one moment the
  player is promised certainty delivered the minimum. Surge should pierce
  soak, or floor well above 1, or roll damage twice and take the better. It
  must never be able to feel like a wasted button. `[HARVESTED →
  plans/0002 — surge ignores soak; minimum 2.]`
- **The haven layer has still never been played.** Two delvers, two deaths,
  both on day 1, both carrying a full coat and an empty account. Charter §3
  ("real decisions live between fights") describes a layer no session has
  reached. The cause is structural: salvage value scales with depth, the
  surface reset is only worth taking when you are already hurt, and every
  decision point therefore favours `delve`. Candidates: bank a fraction of
  carried salvage on death; a standing debt or commission that forces a
  return; diminishing returns on a single descent; supply that cannot be
  refilled without surfacing *and* fights that consume it. `[HARVESTED →
  plans/0003 — satchel carry limit + daily commissions; bank-on-death
  DECLINED — it would hollow out the Ledger.]`
- **Three dead traits and a dead stat.** `armored` (cullet crab, vitrified
  watchman) and `pack` (chorus pane, shardswarm) are in `ALLOWED_TRAITS` and
  the catalog and are read by no code in `engine.py`; only `brittle`,
  `lurker`, `relentless`, `swift` do anything. **CRAFT** is still dead,
  carried unharvested from session 1. `[HARVESTED → plans/0002 (armored
  cracks) and plans/0003 (CRAFT). Correction on review: pack is not dead —
  content.py uses it for group size; only armored was unread.]`
- **Site templates repeated inside one descent** — `watchman's rotunda` at
  depth 2 and again at depth 3. Covered diegetically (an epoch that built the
  same guard-round twice, one on top of the other) and it landed well, but by
  luck. Consider excluding a site name already used this expedition. `[HARVESTED
  → plans/0003.]`
- **`ui/delver.txt` still has no stat legend** (session 1 note, unharvested).
  I hand-wrote one into the opening scene, which worked, but it should live
  on the sheet. `[HARVESTED → plans/0003.]`
- **The Monte Carlo was the single best DM tool of the session.** Running the
  engine 4,000–6,000 times — first over the pending fight, then from the
  *actual paused state* with the real RNG swapped out — let me hand the
  player true odds at the decision that mattered. It made the pause feel
  real and kept me honest. This should be a first-class command
  (`session.py odds`, `session.py odds --resume`), not a scratch script the
  DM improvises. Note the integrity constraint: it must reseed, never peek
  at the live fight's RNG. `[HARVESTED → plans/0003 — the reckoning drum:
  session.py odds, windings = 1 + CRAFT, reseed-never-peek pinned by
  test.]`
- **The one-pause rule works.** It fired exactly once, at exactly the right
  moment, and it was the high point of the session. `[No action — keep.]`

**Player notes:**

- Answers were given in brief; the three questions were not taken in detail.
- best: the game was enjoyable, and seeing more of the mechanics was part of
  the enjoyment — the visible machinery is a feature, not a leak.
- friction: not given this session.
- wish: not given this session.

**Addendum — player feedback, chat, 2026-08-25** (given after the session
in place of the table questions; harvested by the same design session as
the notes above):

- Character creation: wants a fully random delver, no pick-of-three, and
  the game opening already underground so play starts where there is no
  choice to make. `[HARVESTED → plans/0003.]`
- The dead-delver trace line ("thirteen chits nobody has collected") read
  as a quest hook and gave pause. Traces are welcome as atmosphere if they
  never become objectives. `[HARVESTED → playbook §Ledger rite: traces are
  set dressing, never hooks, never priced.]`
- The DM overdid option analysis (the market advice; the unprompted odds
  table gave a double take). Either no advice, or lean in deliberately —
  the player suggested DM computation as an in-game resource, and the game
  needs a dimension the DM's arithmetic cannot trivialise. `[HARVESTED →
  playbook §Advice (object-level only) + plans/0003 (the reckoning drum,
  windings as the meter; nerve-and-appetite decisions stay uncomputed).]`
- Combat should generate labels-words, not just numbers, since a full
  fight is too long to narrate; a wounds-like layer added texture in a
  previous game but was too gory — wants it quirkier. `[HARVESTED →
  plans/0002 — beat vocabulary in the fight log + marks.]`
- /wrapup should not ask feedback questions; feedback comes separately,
  and design sessions analyze transcripts. `[HARVESTED → playbook
  §wrap-up rite + .claude/skills/wrapup, same commit as this entry.]`
- Process: the player sets feelings and constraints and wants the design
  details owned by the DM — "go strong." `[Noted — this is Charter §The
  contract, reaffirmed.]`

---

## Session 3 — 2026-08-26 — Marek Culvert (`play/marek-culvert`) — feedback via dev session

The wrap-up rite did not run at the table; the Ledger page and the mirror
landed, this entry did not. Marek Culvert, glasspicker, died at depth 3 on
day 1 — five shardswarms on the vitrified street, press stance, two rounds.
Note for the record: session 3 opened on a stale checkout and was played on
the 2026-08-23 engine (no light clock, no satchel, no forks); the freshness
guard exists because of it. Player feedback arrived in chat afterward and
is recorded here so the inbox stays complete.

Player notes:

- Quick death was fine; no complaint about lethality itself.
  `[HARVESTED → docs/MECHANICS.md — the "informed bets" property: deaths
  must be readable, not rarer.]`
- Asked what the intended skill is — "I'll learn which monsters need
  which stance?" — probing whether mastery is matchup memorization.
  `[HARVESTED → docs/MECHANICS.md + BENCHLOG 2026-08-26 (policy probe):
  measured — the matchup table mostly collapses into "skirmish when in
  doubt" because exits are unpriced; plans/0005 prices them. The deeper
  answer is that mastery should be pricing bets, not memorizing answers.]`
- Standing worry: whether the mechanics can *feel good* at all under
  these constraints (no spatial play, autocombat). Points at Slay the
  Spire / Diablo / Universal Paperclips (tight mathematical loops),
  autobattlers (configure-then-resolve), Fallen London (flat rules, huge
  resource variety) — and floats the fallback of flat, additive mechanics
  carried by narrative.
  `[HARVESTED → docs/MECHANICS.md — the whole document; the flat fallback
  is rejected as a default, allowed per designated subsystem.]`
- Cadence constraint: little time to play. Wants more design/dev and
  fewer test rounds, content that can ship without testing, and a
  strategy for a-priori quality — career benches, AI playthroughs.
  `[HARVESTED → docs/MECHANICS.md — the four-instrument strategy and the
  content-on-hooks scaling rule; bench_policy.py is the instrument the
  plan-0002 benchlog caveat asked for.]`
