"""Bench: policy tournament — what are decisions and knowledge worth?

Outcome-distribution benches (bench_combat, bench_expedition) show whether
the numbers are survivable; this one shows whether the DECISIONS are alive.
For each depth it generates encounters, evaluates every stance on TRAIN
seeds, picks the per-encounter best (survival first, victory second), then
scores all fixed stances plus that picked stance on disjoint TEST seeds.

- "picked" is the ceiling of a player who has fully learned the matchup
  table; fixed "measure" is the floor of a player who ignores stances.
- knowledge value = picked minus measure. If it is near zero, matchup
  learning pays nothing; if one fixed stance sits at the picked ceiling,
  that stance is a dominant line and the choice is dead.
- The signature table shows whether the best stance is a flat lookup per
  enemy or shifts with group composition and depth.

Pauses are answered fight_on throughout (floor numbers; sims understate
the player). Run in design sessions and after changes that touch combat;
heavier than tune.py on purpose, so it stays standalone.

    python bench_policy.py [--encounters 25] [--train 60] [--test 60]
"""

import argparse

import content
import engine
from test_engine import stock_delver


def outcome_rates(group, stance, seed_ids):
    wins = downs = 0
    for i in seed_ids:
        delver = stock_delver()
        state, result = engine.start_fight(
            delver, group, stance, engine.child_seed("probe-f", stance, i))
        if result is None:
            result = engine.resume_fight(state, "fight_on")
        wins += result["outcome"] == "victory"
        downs += result["outcome"] == "down"
    n = len(seed_ids)
    return {"win": wins / n, "live": 1.0 - downs / n}


def signature(group):
    names = {}
    for e in group:
        names[e["name"]] = names.get(e["name"], 0) + 1
    return " + ".join("%dx %s" % (names[n], n) for n in sorted(names))


def bench(encounters, train, test):
    cat = content.load_catalog()
    stances = sorted(engine.STANCES)
    pick_table = {}  # signature -> set of picked stances
    print("depth | fixed-stance survival (win) on TEST seeds | picked stance | picks")
    for depth in range(1, content.DEPTH_MAX + 1):
        fixed = {s: {"live": 0.0, "win": 0.0} for s in stances}
        picked = {"live": 0.0, "win": 0.0}
        picks = {}
        for k in range(encounters):
            rng = engine.rng_for("probe-enc", depth, k)
            group = content.build_encounter(cat, depth, rng)
            train_ids = ["tr-%d-%d-%d" % (depth, k, i) for i in range(train)]
            test_ids = ["te-%d-%d-%d" % (depth, k, i) for i in range(test)]
            scores = {s: outcome_rates(group, s, train_ids) for s in stances}
            best = max(stances, key=lambda s: (scores[s]["live"], scores[s]["win"]))
            picks[best] = picks.get(best, 0) + 1
            pick_table.setdefault(signature(group), set()).add(best)
            for s in stances:
                r = outcome_rates(group, s, test_ids)
                fixed[s]["live"] += r["live"] / encounters
                fixed[s]["win"] += r["win"] / encounters
                if s == best:
                    picked["live"] += r["live"] / encounters
                    picked["win"] += r["win"] / encounters
        cells = "  ".join("%s %3.0f%%(%3.0f%%)" % (s[:5], 100 * fixed[s]["live"], 100 * fixed[s]["win"])
                          for s in stances)
        pick_str = ",".join("%s:%d" % (s[:2], picks[s]) for s in sorted(picks))
        know = 100 * (picked["live"] - fixed["measure"]["live"])
        edge_over_best = 100 * (picked["live"] - max(f["live"] for f in fixed.values()))
        print("d%d  %s | PICKED %3.0f%%(%3.0f%%) | %s" % (
            depth, cells, 100 * picked["live"], 100 * picked["win"], pick_str))
        print("     knowledge value vs measure: %+.0fpp survival; vs best fixed stance: %+.0fpp"
              % (know, edge_over_best))
    print()
    print("-- best stance by encounter signature --")
    flat = sum(1 for v in pick_table.values() if len(v) == 1)
    for sig in sorted(pick_table):
        print("  %-40s -> %s" % (sig, ", ".join(sorted(pick_table[sig]))))
    print("signatures seen: %d; context-stable (one best stance): %d" % (len(pick_table), flat))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--encounters", type=int, default=25, help="encounters per depth")
    p.add_argument("--train", type=int, default=60, help="seeds used to pick the best stance")
    p.add_argument("--test", type=int, default=60, help="disjoint seeds used to score")
    args = p.parse_args()
    bench(args.encounters, args.train, args.test)
