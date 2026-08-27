"""Bench: single-fight outcome distributions by depth and stance.

A fresh stock delver against generated encounters. Fights that pause are
resumed with fight_on, so these are floor numbers: a real player answers
the pause better than "keep at it". Sims understate the player.

    python bench_combat.py [--runs 300]
"""

import argparse

import content
import engine
from test_engine import stock_delver


def bench(runs):
    cat = content.load_catalog()
    print("depth stance    victory retreat  down   avg_rounds avg_hp_lost pause%")
    for depth in range(1, content.DEPTH_MAX + 1):
        for stance in sorted(engine.STANCES):
            wins = flees = downs = rounds = hplost = paused = 0
            for i in range(runs):
                rng = engine.rng_for("bench", depth, stance, i)
                group = content.build_encounter(cat, depth, rng)
                delver = stock_delver()
                state, result = engine.start_fight(delver, group, stance,
                                                   engine.child_seed("benchfight", depth, stance, i))
                if result is None:
                    paused += 1
                    result = engine.resume_fight(state, "fight_on")
                wins += result["outcome"] == "victory"
                flees += result["outcome"] == "retreated"
                downs += result["outcome"] == "down"
                rounds += result["rounds"]
                hplost += delver["hp"] - result["hp"]
            print("  d%-3d %-9s %5.0f%%  %5.0f%%  %5.0f%%   %6.1f     %6.1f    %4.0f%%"
                  % (depth, stance, 100.0 * wins / runs, 100.0 * flees / runs,
                     100.0 * downs / runs, rounds / runs, hplost / runs, 100.0 * paused / runs))


def _axe_delver():
    """The plan-0001 test delver with the salvage axe: the reference body."""
    from test_engine import stock_delver
    cat = content.load_catalog()
    d = stock_delver()
    d["weapon"] = dict(content.by_name(cat["weapons"], "salvage axe"))
    return d


def bench_armor(runs):
    """The anti-armor arc: how long the reference delver needs on a watchman."""
    cat = content.load_catalog()
    watchman = content.by_name(cat["enemies"], "vitrified watchman")
    print("rounds to kill a vitrified watchman (soak 4, armored), %d seeds" % runs)
    for stance in sorted(engine.STANCES):
        wins = rounds = 0
        for i in range(runs):
            state, result = engine.start_fight(_axe_delver(), [watchman], stance,
                                               engine.child_seed("armorbench", stance, i))
            if result is None:
                result = engine.resume_fight(state, "fight_on")
            if result["outcome"] == "victory":
                wins += 1
                rounds += result["rounds"]
        print("  %-9s victory %4.0f%%   mean rounds on a win %5.2f"
              % (stance, 100.0 * wins / runs, rounds / max(1, wins)))


def bench_stances(runs):
    """Stance diversity: is any one stance simply the answer?

    Two readings, because they disagree. "Survival" counts a retreat as
    surviving, which hands skirmish every hard matchup by declining it;
    the second column asks which stance is best among the three that
    actually stay and fight.
    """
    cat = content.load_catalog()
    survival, committed = {}, {}
    print("matchup grid (%d seeds each): survival %% by stance" % runs)
    for enemy in cat["enemies"]:
        alive = {}
        for stance in sorted(engine.STANCES):
            lived = 0
            for i in range(runs):
                state, result = engine.start_fight(_axe_delver(), [enemy], stance,
                                                   engine.child_seed("divbench", enemy["name"], stance, i))
                if result is None:
                    result = engine.resume_fight(state, "fight_on")
                lived += result["outcome"] != "down"
            alive[stance] = lived
        best = max(sorted(alive), key=lambda s: alive[s])
        stay = [s for s in sorted(alive) if s != "skirmish"]
        best_stay = max(stay, key=lambda s: alive[s])
        survival[best] = survival.get(best, 0) + 1
        committed[best_stay] = committed.get(best_stay, 0) + 1
        print("  %-22s %s" % (enemy["name"],
                              "  ".join("%s %3.0f%%" % (s, 100.0 * alive[s] / runs) for s in sorted(alive))))
    n = len(cat["enemies"])
    print("  best-survival share:  " + "  ".join("%s %.0f%%" % (s, 100.0 * survival[s] / n)
                                                 for s in sorted(survival)))
    print("  best among stances that stay: " + "  ".join("%s %.0f%%" % (s, 100.0 * committed[s] / n)
                                                         for s in sorted(committed)))


def bench_surge(runs):
    """Surge must never feel like a wasted button: EV through heavy armor."""
    import random
    total = lo = 10 ** 9
    total = 0
    for i in range(runs):
        rng = random.Random(engine.child_seed("surgebench", i))
        state = {"events": [], "first_blood": True}
        info = engine._attack(state, rng, "You", 4, "1d10", "target", 12, 4, surge=True)
        total += info["dmg"]
        lo = min(lo, info["dmg"])
    print("surge vs soak 4 (1d10 weapon, %d samples): mean %.2f, minimum %d"
          % (runs, total / runs, lo))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=300)
    args = p.parse_args()
    bench(args.runs)
    print()
    bench_armor(args.runs)
    print()
    bench_stances(args.runs)
    print()
    bench_surge(2000)
