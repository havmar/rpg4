"""UNDERSTORY engine core: seeds, dice, delver math, autocombat, site effects.

Self-contained and stdlib-only. Everything else imports this module; it
imports nothing of ours. All randomness flows through rng_for/child_seed.
Runtime output stays ASCII-safe.
"""

import hashlib
import json
import random
import re

SAVE_VERSION = 4

STATS = ["edge", "iron", "vim", "nerve", "craft"]

STANCES = {
    # atk, guard, soak, dmg
    "measure": (0, 0, 0, 0),
    "press": (2, -2, 0, 2),
    "ward": (-2, 3, 1, 0),
    "skirmish": (-1, 1, 0, 0),
}

PAUSE_HP_FRAC = 0.6
SKIRMISH_FLEE_FRAC = 0.4
FLEE_LATE_FRAC = 0.25
LIGHT_CLOCK_ROUNDS = 4

# Marks: small named conditions a hard fight leaves on you. The catalog
# (catalogs/marks.json) names them; the engine owns what they do.
MARK_EFFECTS = [
    "atk-1", "guard-1", "soak-1", "nerve-2", "grit_max-1", "hp_max-3",
    "camp_heal_half", "light_leak", "breather_numb", "flee_late",
]
MARK_CAP = 3


# ---------------------------------------------------------------- rng / dice

def child_seed(*parts):
    """Stable derived seed off a path of identity parts."""
    text = "\x1f".join(str(p) for p in parts)  # separator no identity part contains
    return int.from_bytes(hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest(), "big")


def rng_for(*parts):
    return random.Random(child_seed(*parts))


_DICE_RE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$")


def roll_dice(spec, rng):
    m = _DICE_RE.match(spec)
    if not m:
        raise ValueError("bad dice spec: %r" % spec)
    n, size, mod = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    return sum(rng.randint(1, size) for _ in range(n)) + mod


def max_dice(spec):
    m = _DICE_RE.match(spec)
    if not m:
        raise ValueError("bad dice spec: %r" % spec)
    return int(m.group(1)) * int(m.group(2)) + int(m.group(3) or 0)


# ------------------------------------------------------------- delver math
# Readers recompute from stored state, marks included. A delver always
# carries a "marks" list (possibly empty); a missing one is a bug, not a
# case to soften.

def has_mark(delver, effect):
    if effect not in MARK_EFFECTS:
        raise ValueError("unknown mark effect: %r" % effect)
    return any(m["effect"] == effect for m in delver["marks"])


def hp_max(delver):
    return 8 + 3 * delver["stats"]["vim"] - (3 if has_mark(delver, "hp_max-3") else 0)


def grit_max(delver):
    base = 1 + delver["stats"]["nerve"] + (1 if delver["knack"] == "archivist" else 0)
    return max(1, base - (1 if has_mark(delver, "grit_max-1") else 0))


def attack_bonus(delver):
    b = 2 * delver["stats"]["edge"] + delver["weapon"]["acc"]
    if delver["knack"] == "cutter":
        b += 1
    if delver["armor"].get("heavy"):
        b -= 1
    if has_mark(delver, "atk-1"):
        b -= 1
    return b


def guard(delver):
    return 8 + delver["stats"]["iron"] + delver["armor"]["guard"] - (1 if has_mark(delver, "guard-1") else 0)


def soak(delver):
    return max(0, delver["armor"]["soak"] - (1 if has_mark(delver, "soak-1") else 0))


def nerve_bonus(delver):
    base = 2 * delver["stats"]["nerve"] + (2 if delver["knack"] == "salvage-priest" else 0)
    return base - (2 if has_mark(delver, "nerve-2") else 0)


def light_max(delver):
    return 10 + (2 if delver["knack"] == "lamplighter" else 0)


def satchel_cap(delver):
    """How much salvage comes home with you. CRAFT is provisioning."""
    return 4 + delver["stats"]["craft"]


def windings_max(delver):
    """Reckoning-drum windings per expedition. CRAFT again."""
    return 1 + delver["stats"]["craft"]


def camp_heal(delver, rng):
    heal = roll_dice("2d6", rng) + delver["stats"]["vim"] + (3 if delver["knack"] == "surgeons-runner" else 0)
    if has_mark(delver, "camp_heal_half"):
        heal //= 2
    return heal


# ------------------------------------------------------------- fight state

def _combatant_from_delver(delver, stance, darkness):
    st = STANCES[stance]
    return {
        "name": delver["name"],
        "hp": delver["hp"],
        "hp_max": hp_max(delver),
        "atk": attack_bonus(delver) + st[0] + (-2 if darkness else 0),
        "guard": guard(delver) + st[1],
        "soak": soak(delver) + st[2],
        "dmg": delver["weapon"]["dmg"],
        "dmg_bonus": st[3],
        "grit": delver["grit"],
        "nerve": nerve_bonus(delver),
        "shaken": False,
        "light": delver["light"],
        "flee_frac": FLEE_LATE_FRAC if has_mark(delver, "flee_late") else SKIRMISH_FLEE_FRAC,
        "worst_blow": 0,
    }


def _enemy_instance(spec, tag):
    return {
        "id": tag,
        "name": spec["name"],
        "hp": spec["hp"],
        "hp_max": spec["hp"],
        "atk": spec["atk"],
        "guard": spec["guard"],
        "soak": spec["soak"],
        "dmg": spec["dmg"],
        "traits": list(spec["traits"]),
        "menace": spec["menace"],
        "dread": spec.get("dread", 0),
    }


def start_fight(delver, enemy_specs, stance, seed, darkness=False):
    """Build fight state and run until pause or end.

    enemy_specs: list of enemy catalog dicts (copies are taken).
    Returns (state, result): exactly one of the two is None.
    """
    if stance not in STANCES:
        raise ValueError("unknown stance: %r" % stance)
    rng = random.Random(seed)
    enemies = []
    counts = {}
    for spec in enemy_specs:
        counts[spec["name"]] = counts.get(spec["name"], 0) + 1
        enemies.append(_enemy_instance(spec, "%s#%d" % (spec["name"], counts[spec["name"]])))
    state = {
        "delver": _combatant_from_delver(delver, stance, darkness),
        "enemies": enemies,
        "stance": stance,
        "darkness": darkness,
        "round": 0,
        "pause_used": False,
        "surge": False,
        "withdrawing": False,
        "first_blood": False,
        "events": [],
        "rng_state": None,
    }
    if darkness:
        _ev(state, 1, "The lamp is out. This happens in the dark.")
    _dread_test(state, rng)
    _save_rng(state, rng)
    return _run(state)


def resume_fight(state, choice, seed_unused=None):
    """Apply a pause choice to a serialized fight state and run to the end."""
    rng = _load_rng(state)
    d = state["delver"]
    options = pause_options(state)
    if choice not in options:
        raise ValueError("choice %r not available; options: %s" % (choice, sorted(options)))
    _ev(state, 1, "You choose: %s." % options[choice])
    if choice in STANCES:
        _switch_stance(state, choice)
    elif choice == "steady":
        d["grit"] -= 1
        d["shaken"] = False
        _ev(state, 1, "You steady your breath. The shaking stops.")
    elif choice == "surge":
        d["grit"] -= 2
        state["surge"] = True
    elif choice == "withdraw":
        state["withdrawing"] = True
    elif choice == "fight_on":
        pass
    _save_rng(state, rng)
    state2, result = _run(state)
    assert state2 is None, "fight paused twice"
    return result


def pause_options(state):
    """Legal pause choices -> short description."""
    d = state["delver"]
    opts = {"fight_on": "keep at it, unchanged"}
    for s in sorted(STANCES):
        if s != state["stance"]:
            opts[s] = "switch stance to %s" % s
    if d["shaken"] and d["grit"] >= 1:
        opts["steady"] = "spend 1 grit: shake off the fear"
    if d["grit"] >= 2:
        opts["surge"] = "spend 2 grit: next attack cannot miss and strikes double"
    opts["withdraw"] = "pull out (every foe still up gets a parting blow)"
    return opts


def _switch_stance(state, new_stance):
    old = STANCES[state["stance"]]
    new = STANCES[new_stance]
    d = state["delver"]
    d["atk"] += new[0] - old[0]
    d["guard"] += new[1] - old[1]
    d["soak"] += new[2] - old[2]
    d["dmg_bonus"] += new[3] - old[3]
    state["stance"] = new_stance


def _save_rng(state, rng):
    s = rng.getstate()
    state["rng_state"] = [s[0], list(s[1]), s[2]]


def _load_rng(state):
    rng = random.Random()
    s = state["rng_state"]
    rng.setstate((s[0], tuple(s[1]), s[2]))
    return rng


def _ev(state, importance, text, beat=None):
    """One log line. `beat` is the engine's own word for what just happened;
    the DM narrates every beat and compresses everything unlabeled."""
    state["events"].append([importance, text, beat])


def reseed_state(state, seed):
    """Replace a serialized fight's RNG with a fresh seeded one.

    The reckoning drum's simulations use this: a resumed sim never draws
    the real fight's stream, so consulting the drum cannot peek at (or
    disturb) the outcome that is actually waiting.
    """
    _save_rng(state, random.Random(seed))


def _living(state):
    return [e for e in state["enemies"] if e["hp"] > 0]


def _dread_test(state, rng):
    dread = max([e["dread"] for e in state["enemies"]], default=0)
    if state["darkness"] and dread > 0:
        dread += 2
    if dread <= 0:
        return
    d = state["delver"]
    roll = rng.randint(1, 20)
    total = roll + d["nerve"]
    dc = 10 + 2 * dread
    if total >= dc:
        _ev(state, 1, "Something here is wrong, but you hold your nerve (%d+%d vs %d)." % (roll, d["nerve"], dc))
    else:
        d["shaken"] = True
        d["atk"] -= 2
        d["guard"] -= 1
        _ev(state, 1, "Fear gets its hook in: SHAKEN (-2 attack, -1 guard) (%d+%d vs %d)." % (roll, d["nerve"], dc))


def _attack(state, rng, att_name, atk, dmg_spec, tgt_name, tgt_guard, tgt_soak,
            flat_bonus=0, surge=False):
    """Resolve one attack and return what happened.

    The caller logs it: only the caller knows whether the blow finished
    anyone, and that decides the beat.
    """
    roll = rng.randint(1, 20)
    crit = roll == 20
    verb_hit, verb_miss = ("hit", "miss") if att_name == "You" else ("hits", "misses")
    hit = True if surge else (roll != 1 and (crit or roll + atk >= tgt_guard))
    if not hit:
        return {"hit": False, "dmg": 0, "crit": False, "surge": False, "floored": False,
                "short": tgt_guard - (roll + atk),
                "text": "%s %s %s (%d%+d vs %d)." % (att_name, verb_miss, tgt_name, roll, atk, tgt_guard)}
    if surge:
        # a surge goes through armor, not into it
        raw, against = roll_dice(dmg_spec, rng) + roll_dice(dmg_spec, rng), 0
    elif crit:
        raw, against = max_dice(dmg_spec), tgt_soak
    else:
        raw, against = roll_dice(dmg_spec, rng), tgt_soak
    dmg = max(1, raw + flat_bonus - against)
    tag = " CRIT!" if crit else (" SURGE!" if surge else "")
    return {"hit": True, "dmg": dmg, "crit": crit, "surge": surge, "short": 0,
            "floored": against > 0 and raw + flat_bonus - against < 1,
            "text": "%s %s %s for %d%s (%d%+d vs %d)."
                    % (att_name, verb_hit, tgt_name, dmg, tag, roll, atk, tgt_guard)}


def _hit_beat(state, info, tgt_hp_max, killed, by_delver):
    """The engine's own word for a landed blow. First match wins."""
    if not state["first_blood"]:
        return "first-blood"
    if killed:
        return "finisher"
    if info["dmg"] * 2 >= tgt_hp_max:
        return "stagger"
    if by_delver and info["floored"]:
        return "turned"
    if info["surge"]:
        return "surge"
    if info["crit"]:
        return "crit"
    return None


def _delver_strike(state, rng):
    d = state["delver"]
    living = _living(state)
    if not living:
        return
    target = min(living, key=lambda e: (e["hp"], e["id"]))
    flat = d["dmg_bonus"] + (2 if "brittle" in target["traits"] else 0)
    surge = state["surge"]
    info = _attack(state, rng, "You", d["atk"], d["dmg"], target["id"],
                   target["guard"], target["soak"], flat_bonus=flat, surge=surge)
    state["surge"] = False
    if not info["hit"]:
        overreach = state["stance"] == "press" and info["short"] >= 5
        _ev(state, 0, info["text"], "overreach" if overreach else None)
        return
    target["hp"] -= info["dmg"]
    killed = target["hp"] <= 0
    _ev(state, 1 if (info["crit"] or surge) else 0, info["text"],
        _hit_beat(state, info, target["hp_max"], killed, by_delver=True))
    state["first_blood"] = True
    if killed:
        _ev(state, 1, "%s goes down." % target["id"])
    elif "armored" in target["traits"] and target["soak"] > 0 and not surge:
        target["soak"] = max(0, target["soak"] - (2 if info["crit"] else 1))
        _ev(state, 1, "Armor gives where you worked it: %s is down to soak %d."
            % (target["id"], target["soak"]), "crack")


def _enemy_strike(state, rng, enemy, free=False):
    d = state["delver"]
    if enemy["hp"] <= 0 or d["hp"] <= 0:
        return
    atk = enemy["atk"]
    if "relentless" in enemy["traits"] and d["hp"] * 2 < d["hp_max"]:
        atk += 2
    if state["round"] == 1 and "lurker" in enemy["traits"]:
        atk += 4
    if state["darkness"]:
        atk += 2
    info = _attack(state, rng, enemy["id"], atk, enemy["dmg"], "you", d["guard"], d["soak"])
    if not info["hit"]:
        _ev(state, 0, info["text"])
        return
    # resolve the grit auto-spend before logging, so the blow's own line can
    # say whether it was the one that finished you
    dmg = info["dmg"]
    halved = []
    while dmg >= d["hp"] and d["grit"] > 0:
        d["grit"] -= 1
        dmg = dmg // 2
        halved.append("You grit through it: damage halved to %d (1 grit spent)." % dmg)
        if dmg == 0:
            break
    killed = dmg >= d["hp"]
    _ev(state, 1 if info["crit"] else 0, info["text"],
        _hit_beat(state, info, d["hp_max"], killed, by_delver=False))
    state["first_blood"] = True
    for line in halved:
        _ev(state, 1, line, "close-call")
    d["worst_blow"] = max(d["worst_blow"], dmg)
    d["hp"] -= dmg
    if d["hp"] <= 0:
        _ev(state, 1, "You are down.")
    elif d["hp"] * 3 <= d["hp_max"]:
        _ev(state, 1, "You are badly hurt (%d/%d)." % (d["hp"], d["hp_max"]))


def _burn_light(state):
    """The light clock: rounds cost lamp oil, so tempo is a real currency."""
    d = state["delver"]
    if d["light"] <= 0:  # a fight that began in the dark burns nothing
        return
    d["light"] -= 1
    if d["light"] > 0:
        _ev(state, 1, "The lamp burns down while you work: %d light left." % d["light"], "lamp-low")
    else:
        _ev(state, 1, "The lamp dies. This ends in the dark.", "lamp-out")
        state["darkness"] = True
        d["atk"] -= 2


def _finish(state, outcome):
    d = state["delver"]
    result = {
        "outcome": outcome,  # victory | retreated | down
        "hp": max(0, d["hp"]),
        "grit": d["grit"],
        "light": d["light"],
        "worst_blow": d["worst_blow"],
        "rounds": state["round"],
        "kills": [e["id"] for e in state["enemies"] if e["hp"] <= 0],
        "events": state["events"],
        "menace_defeated": sum(e["menace"] for e in state["enemies"] if e["hp"] <= 0),
    }
    labels = {"victory": "the field is yours", "retreated": "you got out", "down": "the dark takes you"}
    _ev(state, 1, "FIGHT ENDS after round %d: %s." % (state["round"], labels[outcome]))
    return None, result


def _withdraw(state, rng):
    _ev(state, 1, "You break away; parting blows come.")
    for enemy in list(_living(state)):
        strikes = 2 if "swift" in enemy["traits"] else 1
        for _ in range(strikes):
            _enemy_strike(state, rng, enemy)
    if state["delver"]["hp"] <= 0:
        return _finish(state, "down")
    return _finish(state, "retreated")


def _run(state):
    """Advance the fight until pause or end. Returns (state, None) or (None, result)."""
    rng = _load_rng(state)
    d = state["delver"]
    if state["withdrawing"]:
        return _withdraw(state, rng)
    while True:
        state["round"] += 1
        r = state["round"]
        _ev(state, 0, "-- round %d --" % r)
        living = _living(state)
        # order: lurkers (round 1 only) and swift enemies act before the delver
        early = [e for e in living if ("swift" in e["traits"]) or (r == 1 and "lurker" in e["traits"])]
        late = [e for e in living if e not in early]
        for enemy in early:
            _enemy_strike(state, rng, enemy)
        if d["hp"] <= 0:
            return _finish(state, "down")
        _delver_strike(state, rng)
        if not _living(state):
            return _finish(state, "victory")
        for enemy in late:
            _enemy_strike(state, rng, enemy)
        if d["hp"] <= 0:
            return _finish(state, "down")
        if r % LIGHT_CLOCK_ROUNDS == 0:
            _burn_light(state)
        if state["stance"] == "skirmish" and d["hp"] < d["flee_frac"] * d["hp_max"]:
            _ev(state, 1, "Skirmish stance: this is the moment you planned to leave.")
            return _withdraw(state, rng)
        if (not state["pause_used"]) and r >= 2 and d["hp"] <= PAUSE_HP_FRAC * d["hp_max"]:
            state["pause_used"] = True
            _save_rng(state, rng)
            _ev(state, 1, "PAUSE: the fight hangs in the balance.")
            return state, None
        if r >= 50:
            # stalemate valve; should not happen with sane numbers
            return _withdraw(state, rng)


def fight_summary(events):
    """Short log: the flagged lines, plus every line the engine gave a beat."""
    return [text for imp, text, beat in events if imp >= 1 or beat]


# --------------------------------------------------------- strange effects

STRANGE_EFFECTS = [
    "found_cache", "oil_seep", "bad_air", "whispering_glass", "kind_stranger",
    "collapse", "reflection_gift", "time_slip", "murmur_market", "old_stairs",
]


def apply_strange(delver, expedition, effect, rng):
    """Apply a strange-site effect. Returns log lines. Mutates delver/expedition."""
    lines = []
    if effect not in STRANGE_EFFECTS:
        raise ValueError("unknown strange effect: %r" % effect)
    if effect == "oil_seep":
        delver["light"] += 2
        lines.append("You draw off good oil: +2 light.")
    elif effect == "bad_air":
        dmg = roll_dice("1d4", rng)
        delver["hp"] = max(1, delver["hp"] - dmg)
        lines.append("Bad air; you get clear coughing: -%d hp." % dmg)
    elif effect == "kind_stranger":
        heal = roll_dice("1d6", rng)
        delver["hp"] = min(hp_max(delver), delver["hp"] + heal)
        lines.append("Unexpected kindness in a dark place: +%d hp." % heal)
    elif effect == "collapse":
        dmg = roll_dice("1d3", rng)
        delver["hp"] = max(1, delver["hp"] - dmg)
        delver["light"] = max(0, delver["light"] - 1)
        lines.append("A ceiling lets go: -%d hp, -1 light." % dmg)
    elif effect == "whispering_glass":
        roll = rng.randint(1, 20)
        nb = nerve_bonus(delver)
        if roll + nb >= 14:
            lines.append("The glass whispers; you decline to listen (%d+%d vs 14)." % (roll, nb))
        else:
            delver["grit"] = max(0, delver["grit"] - 1)
            lines.append("The glass whispers and you listened too long: -1 grit (%d+%d vs 14)." % (roll, nb))
    elif effect == "reflection_gift":
        delver["grit"] += 1
        lines.append("Your reflection hands something back: +1 grit.")
    elif effect == "time_slip":
        lost = roll_dice("1d2", rng)
        delver["light"] = max(0, delver["light"] - lost)
        lines.append("The hour goes missing: -%d light." % lost)
    elif effect == "old_stairs":
        expedition["free_delve"] = True
        lines.append("Sound old stairs, going down: the next delve costs no light.")
    elif effect in ("found_cache", "murmur_market"):
        # caller (content layer) supplies the salvage item; engine just notes it
        lines.append("There is something here worth carrying out.")
    return lines


# ------------------------------------------------------------------ eyeball

def main():
    import argparse
    p = argparse.ArgumentParser(description="engine eyeball check: one demo fight")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--stance", default="measure", choices=sorted(STANCES))
    args = p.parse_args()
    delver = {
        "name": "Testfell",
        "stats": {"edge": 2, "iron": 2, "vim": 2, "nerve": 2, "craft": 2},
        "knack": "cutter",
        "weapon": {"name": "salvage axe", "dmg": "1d10", "acc": -1},
        "armor": {"name": "quilted coat", "guard": 1, "soak": 1},
        "hp": 14, "grit": 3, "light": 10, "marks": [],
    }
    hound = {"name": "glasshound", "hp": 6, "atk": 3, "guard": 12, "soak": 0,
             "dmg": "1d6", "traits": ["swift"], "menace": 2}
    state, result = start_fight(delver, [hound, hound], args.stance, args.seed)
    while result is None:
        print("(pause reached; auto-choosing fight_on for the demo)")
        result = resume_fight(state, "fight_on")
    for imp, text, beat in result["events"]:
        print(("* " if imp else "  ") + text + (("  [%s]" % beat) if beat else ""))
    print("outcome:", result["outcome"],
          json.dumps({k: result[k] for k in ("hp", "grit", "light", "rounds", "worst_blow")}))


if __name__ == "__main__":
    main()
