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

With --careers N the CAREER tournament runs too: whole-career policies over
the full loop. The fight layer cannot see what ward preserves across an
expedition, nor what a hedge really costs in light and forgone loot, so it
cannot answer "is any line dominant?" -- this can. Two of them come in a
"+shop" variant that works the outfitter's shelf (buy the cheapest unheld
kit while the chits are there to spare; wear the first relic that turns up),
so the shelf can be measured against the same policy without it.

    python bench_policy.py [--encounters 25] [--train 60] [--test 60]
    python bench_policy.py --careers 200 [--expeditions 10]
"""

import argparse
import copy

import bench_expedition
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


# --------------------------------------------------------- the career layer
# Five policies over whole careers. ramp and satchel are bench_expedition's
# own baselines, reused so there is one definition of each; hedge, committed
# and informed are this bench's question: what is a decision worth once light,
# hp and forgone loot are all on the same bill?

SHOP_SUFFIX = "+shop"
CAREER_POLICIES = ("ramp", "satchel", "hedge", "committed", "informed",
                   "committed" + SHOP_SUFFIX, "informed" + SHOP_SUFFIX)
CAREER_EXPEDITIONS = 10
INFORMED_SIMS = 40    # simulated fights per stance, per encounter
INFORMED_SHARE = 5    # ... so informed runs a fifth of the careers
INFORMED_MIN = 20
# the shopping step: a shelf that does not beat a policy's non-shopping self
# is priced wrong (plan 0006). Keep a reserve so kit never starves training.
SHOP_RESERVE = 20


def base_policy(policy):
    """'committed+shop' decides like 'committed'; the suffix only shops."""
    return policy[:-len(SHOP_SUFFIX)] if policy.endswith(SHOP_SUFFIX) else policy


def shops(policy):
    return policy.endswith(SHOP_SUFFIX)


def _informed_seed(save, stance, i):
    """A seed path of its own. RESEED, NEVER PEEK (the drum's rule): the
    sims must not be able to draw, or disturb, the waiting fight's stream."""
    return engine.child_seed("career-probe", save["world_seed"], save["counter"], stance, i)


def informed_stance(cat, save):
    """Pick a stance for the pending encounter by simulating it: survival
    first, victory second, off a deep copy of the delver."""
    delver = copy.deepcopy(save["delver"])
    specs = [content.by_name(cat["enemies"], n)
             for n in save["expedition"]["pending_site"]["enemies"]]
    dark = content._darkness(delver)
    best, best_score = None, None
    for stance in sorted(delver["stances"]):  # a career delver knows what it has learned
        live = wins = 0
        for i in range(INFORMED_SIMS):
            state, result = engine.start_fight(delver, specs, stance,
                                               _informed_seed(save, stance, i), darkness=dark)
            if result is None:
                result = engine.resume_fight(state, "fight_on")
            live += result["outcome"] != "down"
            wins += result["outcome"] == "victory"
        if best_score is None or (live, wins) > best_score:
            best, best_score = stance, (live, wins)
    return best


def career_stance(cat, save, policy):
    d = save["delver"]
    policy = base_policy(policy)
    if policy in ("ramp", "satchel"):
        return "measure"
    if policy == "hedge":
        return "skirmish"
    if policy == "committed":
        return "press" if d["hp"] >= 0.6 * engine.hp_max(d) else "ward"
    return informed_stance(cat, save)


def buy_kit(cat, save):
    """Buy the cheapest piece of kit you do not hold, while the chits are
    there to spare. Bench delvers do not read the bestiary."""
    d = save["delver"]
    lines = 0
    while len(d["kit"]) < content.KIT_CAP:
        held = {k["name"] for k in d["kit"]}
        shelf = sorted((k for k in cat["kit"] if k["name"] not in held),
                       key=lambda k: (k["value"], k["name"]))
        if not shelf or save["wake"]["chits"] < shelf[0]["value"] + SHOP_RESERVE:
            break
        content.do_buy(cat, save, shelf[0]["name"])
        lines += 1
    return lines


def wear_first_relic(cat, save):
    """Equip the first relic that comes up, and keep it: a relic in the
    satchel is banked at the next surfacing, so the choice is made below."""
    d = save["delver"]
    if d["relic"]:
        return False
    found = [i for i in d["salvage"] if content.is_relic(cat, i["name"])]
    if not found:
        return False
    content.do_equip(cat, save, found[0]["name"])
    return True


def pause_choice(save, policy):
    d = save["expedition"]["paused_fight"]["delver"]
    frac = d["hp"] / d["hp_max"]
    policy = base_policy(policy)
    if policy == "hedge":
        return "withdraw"
    if policy in ("ramp", "satchel"):
        return "withdraw" if frac < 0.35 else "fight_on"
    if d["grit"] >= 2:  # committed and informed spend grit before they leave
        return "surge"
    return "fight_on" if frac >= 0.35 else "withdraw"


def time_to_climb(save, policy):
    policy = base_policy(policy)
    if policy in ("ramp", "satchel"):
        return bench_expedition._time_to_climb(save, policy)
    d, exp = save["delver"], save["expedition"]
    climb = (exp["depth"] + 2) // 3
    return len(d["salvage"]) >= engine.satchel_cap(d) or d["light"] <= climb + 1


def run_career(world_seed, policy, max_expeditions=CAREER_EXPEDITIONS):
    cat, save = bench_expedition.fresh_save(world_seed)
    d = save["delver"]
    depths, banked, burned, flees = [], [], [], 0
    while save["wake"]["expeditions"] < max_expeditions and d["alive"]:
        start_light = d["light"]
        while d["alive"]:
            exp = save["expedition"]
            if exp["pending_site"] and exp["pending_site"].get("enemies"):
                paused, _ = content.start_pending_fight(cat, save, career_stance(cat, save, policy))
                if paused:
                    content.resume_paused_fight(cat, save, pause_choice(save, policy))
                flees += save["last_fight"]["outcome"] == "retreated"
                continue
            if shops(policy) and exp["active"] and not exp["fork"]:
                wear_first_relic(cat, save)
            if exp["active"] and time_to_climb(save, policy):
                depths.append(exp["depth"])
                burned.append(start_light - d["light"])
                before = save["wake"]["chits"]
                content.do_surface(cat, save)
                banked.append(save["wake"]["chits"] - before)
                break
            if exp["active"] and d["hp"] < 0.5 * engine.hp_max(d) and d["supply"] > 0:
                content.do_camp(cat, save)
                continue
            content.advance_delve(cat, save)
            if save["expedition"]["fork"]:  # career policies always take passage 1
                content.advance_delve(cat, save, passage=1)
        if not d["alive"]:
            burned.append(start_light - d["light"])
            break
        if shops(policy):  # the shelf gets its turn before the trainers do
            buy_kit(cat, save)
        for stat in bench_expedition.TRAIN_ROTATION:
            cost = content.TRAIN_COST_PER_LEVEL * (d["stats"][stat] + 1)
            if d["stats"][stat] < content.STAT_CAP and save["wake"]["chits"] >= cost:
                content.do_train(save, stat)
                break
    return {
        "died": not d["alive"],
        "expeditions": save["wake"]["expeditions"],
        "banked_total": sum(banked),
        "burned": burned,
        "flees": flees,
        "max_depth": max(depths) if depths else save["expedition"]["depth"],
    }


def career_row(policy, careers, max_expeditions=CAREER_EXPEDITIONS):
    """One policy's whole report row. Deterministic in (policy, careers)."""
    results = [run_career(seed, policy, max_expeditions) for seed in range(careers)]
    burns = [b for r in results for b in r["burned"]]
    return {
        "policy": policy,
        "careers": careers,
        "died": 100.0 * sum(r["died"] for r in results) / careers,
        "expeditions": sum(r["expeditions"] for r in results) / careers,
        "chits_mean": sum(r["banked_total"] for r in results) / careers,
        "chits_median": bench_expedition._median([r["banked_total"] for r in results]),
        "max_depth": sum(r["max_depth"] for r in results) / careers,
        "light": (sum(burns) / len(burns)) if burns else 0.0,
        "flees": sum(r["flees"] for r in results) / careers,
    }


def bench_careers(careers, max_expeditions):
    print("-- career tournament (cap %d expeditions per career) --" % max_expeditions)
    print("  %-15s %7s %6s %8s %10s %9s %9s %9s %7s"
          % ("policy", "careers", "died", "mean exp", "mean chits", "med chits",
             "mean maxd", "light/exp", "flees"))
    rows = {}
    for policy in CAREER_POLICIES:
        n = (max(INFORMED_MIN, careers // INFORMED_SHARE)
             if base_policy(policy) == "informed" else careers)
        r = career_row(policy, n, max_expeditions)
        rows[policy] = r
        print("  %-15s %7d %5.0f%% %8.1f %10.0f %9.0f %9.1f %9.1f %7.1f"
              % (r["policy"], r["careers"], r["died"], r["expeditions"], r["chits_mean"],
                 r["chits_median"], r["max_depth"], r["light"], r["flees"]))
    print("  (informed ran %d careers: it is %dx the fights)"
          % (rows["informed"]["careers"], len(engine.BASE_STANCES) * INFORMED_SIMS))
    inf, ramp = rows["informed"], rows["ramp"]
    print("knowledge value (informed vs ramp): %+.0fpp died, %+.0f median chits"
          % (inf["died"] - ramp["died"], inf["chits_median"] - ramp["chits_median"]))
    for policy in CAREER_POLICIES:
        if not shops(policy):
            continue
        shopper, plain = rows[policy], rows[base_policy(policy)]
        print("shelf value (%s vs %s): %+.0fpp died, %+.0f median chits"
              % (policy, base_policy(policy), shopper["died"] - plain["died"],
                 shopper["chits_median"] - plain["chits_median"]))
    safest = min(r["died"] for r in rows.values())
    richest = max(r["chits_median"] for r in rows.values())
    dominant = [p for p, r in rows.items()
                if r["died"] == safest and r["chits_median"] == richest]
    print("dominance (best on BOTH survival and median chits): %s"
          % (", ".join(dominant) if dominant else "none"))
    return rows


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--encounters", type=int, default=25, help="encounters per depth")
    p.add_argument("--train", type=int, default=60, help="seeds used to pick the best stance")
    p.add_argument("--test", type=int, default=60, help="disjoint seeds used to score")
    p.add_argument("--careers", type=int, default=0,
                   help="also run the career tournament, this many careers per policy")
    p.add_argument("--expeditions", type=int, default=CAREER_EXPEDITIONS,
                   help="expedition cap per career")
    args = p.parse_args()
    bench(args.encounters, args.train, args.test)
    if args.careers:
        print()
        bench_careers(args.careers, args.expeditions)
