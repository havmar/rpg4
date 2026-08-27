"""Contract suite for engine.py: the model, not the sessions that built it."""

import json
import random
import re
import unittest

import engine


def stock_delver(**over):
    d = {
        "name": "Testfell",
        "stats": {"edge": 2, "iron": 2, "vim": 2, "nerve": 2, "craft": 2},
        "knack": "none",
        "weapon": {"name": "pick-hammer", "dmg": "1d8", "acc": 0},
        "armor": {"name": "quilted delver's coat", "guard": 1, "soak": 1},
        "hp": 14, "grit": 3,
        "light": 10, "supply": 3, "salvage": [], "marks": [], "alive": True,
        # a bench delver knows every stance and carries nothing it did not buy
        "kit": [], "relic": None, "stances": sorted(engine.STANCES),
    }
    d.update(over)
    return d


def with_kit(*effects, **over):
    return stock_delver(kit=[{"name": e, "effect": e, "value": 1, "text": "t"} for e in effects],
                        **over)


def wearing(effect, **over):
    return stock_delver(relic={"name": effect, "effect": effect, "value": 1, "text": "t"}, **over)


HOUND = {"name": "glasshound", "hp": 6, "atk": 3, "guard": 12, "soak": 0,
         "dmg": "1d6", "traits": ["swift"], "menace": 2, "dread": 0}
BRUTE = {"name": "glazier's remnant", "hp": 18, "atk": 5, "guard": 13, "soak": 2,
         "dmg": "2d6", "traits": ["relentless"], "menace": 5, "dread": 2}


def run_to_end(delver, enemies, stance, seed, choice="fight_on"):
    state, result = engine.start_fight(delver, enemies, stance, seed)
    if result is None:
        result = engine.resume_fight(state, choice)
    return result


class TestSeedsAndDice(unittest.TestCase):
    def test_child_seed_stable_and_distinct(self):
        self.assertEqual(engine.child_seed("a", 1), engine.child_seed("a", 1))
        self.assertNotEqual(engine.child_seed("a", 1), engine.child_seed("a", 2))
        self.assertNotEqual(engine.child_seed("a", 1), engine.child_seed("a/1"))

    def test_dice_bounds(self):
        rng = random.Random(7)
        for _ in range(200):
            self.assertTrue(3 <= engine.roll_dice("2d6+1", rng) <= 13)
        self.assertEqual(engine.max_dice("2d6+1"), 13)
        with self.assertRaises(ValueError):
            engine.roll_dice("d6", rng)
        with self.assertRaises(ValueError):
            engine.max_dice("2d6+1d4")

    def test_rng_for_deterministic(self):
        self.assertEqual(engine.rng_for("x", 1).random(), engine.rng_for("x", 1).random())


class TestDelverMath(unittest.TestCase):
    def test_derived(self):
        d = stock_delver()
        self.assertEqual(engine.hp_max(d), 14)
        self.assertEqual(engine.grit_max(d), 3)
        self.assertEqual(engine.attack_bonus(d), 4)
        self.assertEqual(engine.guard(d), 11)
        self.assertEqual(engine.soak(d), 1)

    def test_knacks(self):
        self.assertEqual(engine.grit_max(stock_delver(knack="archivist")), 4)
        self.assertEqual(engine.attack_bonus(stock_delver(knack="cutter")), 5)
        self.assertEqual(engine.light_max(stock_delver(knack="lamplighter")), 12)
        self.assertEqual(engine.nerve_bonus(stock_delver(knack="salvage-priest")), 6)

    def test_heavy_armor_attack_penalty(self):
        d = stock_delver(armor={"name": "plate", "guard": 2, "soak": 3, "heavy": True})
        self.assertEqual(engine.attack_bonus(d), 3)


class TestFight(unittest.TestCase):
    def test_deterministic(self):
        a = run_to_end(stock_delver(), [HOUND, HOUND], "measure", 11)
        b = run_to_end(stock_delver(), [HOUND, HOUND], "measure", 11)
        self.assertEqual(a["events"], b["events"])
        self.assertEqual(a["outcome"], b["outcome"])

    def test_outcomes_and_state_bounds(self):
        for seed in range(30):
            r = run_to_end(stock_delver(), [HOUND, BRUTE], "measure", seed)
            self.assertIn(r["outcome"], ("victory", "retreated", "down"))
            self.assertTrue(0 <= r["hp"] <= 14)
            self.assertTrue(0 <= r["grit"] <= 3)
            if r["outcome"] == "victory":
                self.assertEqual(len(r["kills"]), 2)

    def find_pausing_seed(self):
        for seed in range(200):
            state, result = engine.start_fight(stock_delver(), [BRUTE], "measure", seed)
            if result is None:
                return seed, state
        self.fail("no seed pauses vs the brute; pause heuristic is broken")

    def test_pause_serializes_and_resumes_deterministically(self):
        seed, state = self.find_pausing_seed()
        blob = json.dumps(state)
        r1 = engine.resume_fight(json.loads(blob), "fight_on")
        r2 = engine.resume_fight(json.loads(blob), "fight_on")
        self.assertEqual(r1["events"], r2["events"])
        for key in ("outcome", "hp", "grit", "light", "worst_blow", "rounds"):
            self.assertEqual(r1[key], r2[key], key)

    def test_pause_options_and_withdraw(self):
        seed, state = self.find_pausing_seed()
        opts = engine.pause_options(state)
        self.assertIn("fight_on", opts)
        self.assertIn("withdraw", opts)
        for stance in engine.STANCES:
            if stance != state["stance"]:
                self.assertIn(stance, opts)
        r = engine.resume_fight(json.loads(json.dumps(state)), "withdraw")
        self.assertIn(r["outcome"], ("retreated", "down"))

    def test_bad_resume_choice_raises(self):
        seed, state = self.find_pausing_seed()
        with self.assertRaises(ValueError):
            engine.resume_fight(state, "surrender")

    def test_pauses_at_most_once(self):
        # resuming with fight_on must run to an outcome, never re-pause
        seed, state = self.find_pausing_seed()
        r = engine.resume_fight(state, "fight_on")
        self.assertIn(r["outcome"], ("victory", "retreated", "down"))

    def test_unknown_stance_raises(self):
        with self.assertRaises(ValueError):
            engine.start_fight(stock_delver(), [HOUND], "berserk", 1)


class TestStrange(unittest.TestCase):
    def test_unknown_effect_raises(self):
        with self.assertRaises(ValueError):
            engine.apply_strange(stock_delver(), {}, "free_lunch", random.Random(1))

    def test_oil_seep(self):
        d = stock_delver()
        engine.apply_strange(d, {}, "oil_seep", random.Random(1))
        self.assertEqual(d["light"], 12)

    def test_kind_stranger_caps_at_max(self):
        d = stock_delver(hp=14)
        engine.apply_strange(d, {}, "kind_stranger", random.Random(1))
        self.assertEqual(d["hp"], 14)

    def test_old_stairs_sets_flag(self):
        exp = {}
        engine.apply_strange(stock_delver(), exp, "old_stairs", random.Random(1))
        self.assertTrue(exp["free_delve"])


# --------------------------------------------------------- plan 0002 pieces
# A wall to work against: it cannot kill you, so a fight against it isolates
# whatever is being measured (armor, light, surge) from luck.
def wall(**over):
    w = {"name": "wall", "hp": 200, "atk": -30, "guard": 5, "soak": 10,
         "dmg": "1d2", "traits": [], "menace": 1, "dread": 0}
    w.update(over)
    return w


HIT_RE = re.compile(r"^You (hit|miss) \S+.*\((\d+)([+-]\d+) vs (\d+)\)")
CRACK_RE = re.compile(r"^Armor gives where you worked it: .* down to soak (\d+)\.$")
DMG_RE = re.compile(r"^You hit \S+ for (\d+)")


def beats(result):
    return [beat for _, _, beat in result["events"] if beat]


def texts(result, needle):
    return [text for _, text, _ in result["events"] if needle in text]


class TestStances(unittest.TestCase):
    def test_stances_are_four_tuples_with_damage(self):
        for stance, mods in engine.STANCES.items():
            self.assertEqual(len(mods), 4, stance)
        self.assertEqual(engine.STANCES["press"][3], 2)
        self.assertEqual(engine.STANCES["ward"][3], 0)

    def test_press_damage_bonus_reaches_the_target(self):
        soft = wall(soak=0, hp=400)
        plain = run_to_end(stock_delver(), [soft], "measure", 5)
        pressed = run_to_end(stock_delver(), [soft], "press", 5)
        # same seed, same dice: press hits land exactly 2 harder
        p = [int(DMG_RE.match(t).group(1)) for t in texts(plain, "You hit") if DMG_RE.match(t)]
        q = [int(DMG_RE.match(t).group(1)) for t in texts(pressed, "You hit") if DMG_RE.match(t)]
        self.assertTrue(p and q)
        self.assertEqual(q[0] - p[0], 2)

    def test_switching_stance_carries_the_damage_bonus(self):
        seed, state = TestFight().find_pausing_seed()
        before = state["delver"]["dmg_bonus"]
        engine._switch_stance(state, "press")
        self.assertEqual(state["delver"]["dmg_bonus"], before + 2)


class TestSurgePierces(unittest.TestCase):
    def surge_fight(self, seed, enemy):
        """A delver already at the pause line: round 2 pauses, then surges."""
        d = stock_delver(hp=8, grit=3, weapon={"name": "shiv", "dmg": "1d4", "acc": 0})
        state, result = engine.start_fight(d, [enemy], "measure", seed)
        self.assertIsNone(result, "expected a pause at seed %d" % seed)
        return engine.resume_fight(state, "surge")

    def test_surge_ignores_soak_and_never_falls_under_two(self):
        seen = []
        for seed in range(40):
            r = self.surge_fight(seed, wall())
            line = [t for t in texts(r, "SURGE!")]
            self.assertEqual(len(line), 1, line)
            dmg = int(DMG_RE.match(line[0]).group(1))
            seen.append(dmg)
        # 2d4 through soak 10: without the pierce every one of these is 1
        self.assertGreaterEqual(min(seen), 2)
        self.assertLessEqual(max(seen), 8)
        self.assertGreater(len(set(seen)), 1)

    def test_surge_carries_the_surge_beat(self):
        r = self.surge_fight(0, wall())
        self.assertIn("surge", beats(r))

    def test_surge_does_not_crack_armor(self):
        r = self.surge_fight(0, wall(traits=["armored"], soak=3))
        surge_at = [i for i, (_, t, _) in enumerate(r["events"]) if "SURGE!" in t][0]
        after = r["events"][surge_at + 1]
        self.assertIsNone(CRACK_RE.match(after[1]), "a surge went through the armor, not into it")


class TestCrackingArmor(unittest.TestCase):
    def test_armor_cracks_down_to_zero_and_stops(self):
        r = run_to_end(stock_delver(hp=200), [wall(traits=["armored"], soak=3, hp=400)], "measure", 4)
        soaks = [int(CRACK_RE.match(t).group(1)) for t in texts(r, "Armor gives") if CRACK_RE.match(t)]
        self.assertTrue(soaks)
        self.assertEqual(soaks, sorted(soaks, reverse=True))
        self.assertEqual(len(set(soaks)), len(soaks), "soak must strictly decrease")
        self.assertEqual(soaks[-1], 0)
        self.assertGreaterEqual(soaks[0], 1)

    def test_crit_strips_two(self):
        found = False
        for seed in range(60):
            r = run_to_end(stock_delver(hp=200), [wall(traits=["armored"], soak=9, hp=800)],
                           "measure", seed)
            soak = 9
            for _, text, _ in r["events"]:
                crit = "CRIT!" in text and text.startswith("You hit")
                m = CRACK_RE.match(text)
                if m:
                    self.assertEqual(int(m.group(1)), soak - (2 if crit_pending else 1))
                    soak = int(m.group(1))
                    found = found or crit_pending
                crit_pending = crit
            if found:
                return
        self.fail("no crit landed on an armored target in 60 seeds")

    def test_unarmored_soak_never_moves(self):
        r = run_to_end(stock_delver(hp=200), [wall(soak=3, hp=400)], "measure", 4)
        self.assertEqual(texts(r, "Armor gives"), [])


class TestLightClock(unittest.TestCase):
    def long_fight(self, light=10, darkness=False):
        d = stock_delver(hp=200, light=light, weapon={"name": "shiv", "dmg": "1d4", "acc": 0})
        state, result = engine.start_fight(d, [wall()], "measure", 3, darkness=darkness)
        self.assertIsNotNone(result, "the wall should never pause the fight")
        return result

    def test_burns_one_light_every_fourth_round(self):
        r = self.long_fight()
        burns = [i for i, (_, _, beat) in enumerate(r["events"]) if beat in ("lamp-low", "lamp-out")]
        self.assertEqual(len(burns), 10, "10 light should buy exactly 10 burns")
        self.assertEqual(r["light"], 0)
        rounds = []
        cur = 0
        for _, text, beat in r["events"]:
            if text.startswith("-- round "):
                cur = int(text.split()[2])
            if beat in ("lamp-low", "lamp-out"):
                rounds.append(cur)
        self.assertEqual(rounds[:3], [4, 8, 12])
        self.assertEqual(rounds[-1], 40)

    def test_a_fight_that_starts_dark_burns_nothing(self):
        r = self.long_fight(light=0, darkness=True)
        self.assertEqual(r["light"], 0)
        self.assertEqual([b for b in beats(r) if b in ("lamp-low", "lamp-out")], [])

    def test_lamp_out_flips_the_modifiers(self):
        r = self.long_fight()
        before, after, out = [], [], False
        for _, text, beat in r["events"]:
            if beat == "lamp-out":
                out = True
                continue
            m = HIT_RE.match(text)
            if m:
                (after if out else before).append(int(m.group(3)))
        self.assertTrue(before and after)
        self.assertEqual(set(after), {min(before) - 2})
        self.assertEqual(len(set(before)), 1)


class TestBeats(unittest.TestCase):
    def test_pinned_beat_sequence(self):
        r = run_to_end(stock_delver(), [HOUND, BRUTE], "measure", 7)
        self.assertEqual(beats(r), [
            "first-blood", "finisher", "lamp-low", "turned", "stagger", "close-call",
            "turned", "stagger", "close-call", "finisher", "close-call",
        ])

    def test_summary_carries_every_beat_line(self):
        r = run_to_end(stock_delver(), [HOUND, BRUTE], "press", 7)
        summary = engine.fight_summary(r["events"])
        for imp, text, beat in r["events"]:
            if beat:
                self.assertIn(text, summary)

    def test_events_serialize_as_triples(self):
        r = run_to_end(stock_delver(), [HOUND], "measure", 2)
        for ev in r["events"]:
            self.assertEqual(len(ev), 3)
        self.assertEqual(json.loads(json.dumps(r["events"])), r["events"])


# --------------------------------------------------------- plan 0005 pieces
# Harmless pursuers, so the price of leaving is measured and not survived:
# a wall can only touch you on a natural 20, and then only for 1.
PARTING_RE = re.compile(r"^(\S+) (hits|misses) you \((\d+)([+-]\d+) vs (\d+)\)")

# vim 6 puts the pause line (60%) well clear of the relentless in-fight
# clause (half hp), so a parting-strike bonus is the only thing measured.
TOUGH = {"edge": 2, "iron": 2, "vim": 6, "nerve": 2, "craft": 2}


def pursuer(name, traits):
    return wall(name=name, traits=list(traits), hp=400)


def parting(result):
    """(attacker, attack modifier) for every blow struck after the break."""
    out, leaving = [], False
    for _, text, _ in result["events"]:
        if text.startswith("You break away"):
            leaving = True
        elif leaving:
            m = PARTING_RE.match(text)
            if m:
                out.append((m.group(1), int(m.group(4))))
    return out


class TestTheCostOfLeaving(unittest.TestCase):
    """Pursuit: what is chasing you decides what leaving costs."""

    def leave(self, enemies, stance="measure", seed=1, darkness=False, **over):
        """Pause at round 2 with hp to spare, then pull out."""
        d = stock_delver(stats=dict(TOUGH), hp=15, **over)
        state, result = engine.start_fight(d, enemies, stance, seed, darkness=darkness)
        self.assertIsNone(result, "expected a pause, got %r" % (result and result["outcome"]))
        r = engine.resume_fight(state, "withdraw")
        self.assertEqual(r["outcome"], "retreated")
        self.assertGreaterEqual(r["hp"] * 2, engine.hp_max(d),
                                "the harmless pursuers did real damage; the fixture is wrong")
        return r

    def strikes(self, result):
        counts = {}
        for who, _ in parting(result):
            counts[who] = counts.get(who, 0) + 1
        return counts

    def test_the_pursuit_table(self):
        r = self.leave([pursuer("lurker", ["lurker"]), pursuer("swift", ["swift"]),
                        pursuer("plain", [])])
        # the lurker does not chase: it waits for the next one through
        self.assertEqual(self.strikes(r), {"swift#1": 2, "plain#1": 1})

    def test_relentless_parting_blows_come_at_a_bonus(self):
        plain = self.leave([pursuer("plain", [])])
        chase = self.leave([pursuer("plain", ["relentless"])])
        self.assertEqual([mod for _, mod in parting(plain)], [-30])
        self.assertEqual([mod for _, mod in parting(chase)],
                         [-30 + engine.RELENTLESS_PURSUIT_ATK])

    def test_a_swift_relentless_thing_gets_both(self):
        r = self.leave([pursuer("hunter", ["swift", "relentless"])])
        self.assertEqual([mod for _, mod in parting(r)], [-28, -28])

    def test_the_prepared_exit_caps_every_pursuer_at_one(self):
        enemies = [pursuer("lurker", ["lurker"]), pursuer("swift", ["swift"]),
                   pursuer("hunter", ["relentless"])]
        r = self.leave(enemies, stance="skirmish")
        self.assertEqual(self.strikes(r), {"swift#1": 1, "hunter#1": 1})
        self.assertEqual({mod for _, mod in parting(r)}, {-30})  # and no pursuit bonus

    def test_a_room_of_lurkers_lets_you_walk_out_of_any_stance(self):
        for stance in sorted(engine.STANCES):
            r = self.leave([pursuer("waiting", ["lurker"]), pursuer("patient", ["lurker"])],
                           stance=stance)
            self.assertEqual(parting(r), [], stance)

    def test_leaving_costs_one_light(self):
        r = self.leave([pursuer("plain", [])], light=10)
        self.assertEqual(r["light"], 10 - engine.WITHDRAW_LIGHT_COST)
        self.assertEqual(len(texts(r, "You spend lamp and breath getting clear")), 1)

    def test_a_fight_that_started_dark_has_no_lamp_left_to_spend(self):
        r = self.leave([pursuer("plain", [])], light=0, darkness=True)
        self.assertEqual(r["light"], 0)
        self.assertEqual(texts(r, "You spend lamp and breath getting clear"), [])

    def test_the_stalemate_valve_pays_the_same_prices(self):
        d = stock_delver(hp=200, light=200, weapon={"name": "shiv", "dmg": "1d2", "acc": 0})
        state, result = engine.start_fight(d, [wall(hp=4000)], "measure", 3)
        self.assertIsNone(state, "the valve must end the fight, not pause it")
        self.assertEqual(result["outcome"], "retreated")
        self.assertEqual(result["rounds"], 50)
        self.assertEqual(len(parting(result)), 1)
        self.assertEqual(result["light"],
                         200 - 50 // engine.LIGHT_CLOCK_ROUNDS - engine.WITHDRAW_LIGHT_COST)


class TestThePreparedExit(unittest.TestCase):
    """Skirmish keeps the exit and pays for it with attack."""

    def test_the_skirmish_tuple(self):
        self.assertEqual(engine.STANCES["skirmish"], (-2, 1, 0, 0))

    def test_the_combatant_build_carries_it(self):
        d = stock_delver()
        c = engine._combatant_from_delver(d, "skirmish", False)
        self.assertEqual(c["atk"], engine.attack_bonus(d) - 2)
        self.assertEqual(c["guard"], engine.guard(d) + 1)
        self.assertEqual(c["soak"], engine.soak(d))
        self.assertEqual(c["dmg_bonus"], 0)

    def test_switching_into_skirmish_moves_attack_by_two(self):
        seed, state = TestFight().find_pausing_seed()  # stance: measure
        before = state["delver"]["atk"]
        engine._switch_stance(state, "skirmish")
        self.assertEqual(state["delver"]["atk"], before - 2)
        self.assertEqual(state["delver"]["guard"], engine.guard(stock_delver()) + 1)

    def test_the_auto_flee_still_fires_at_the_flee_line(self):
        # hp tracks the constant: just under the flee line, wherever it is set
        under = int(engine.SKIRMISH_FLEE_FRAC * engine.hp_max(stock_delver()))
        below = run_to_end(stock_delver(hp=under), [wall(hp=400)], "skirmish", 1)
        self.assertEqual(below["outcome"], "retreated")
        self.assertEqual(below["rounds"], 1)
        self.assertTrue(texts(below, "this is the moment you planned to leave"))

    def test_above_the_flee_line_it_pauses_instead(self):
        state, result = engine.start_fight(stock_delver(hp=8), [wall(hp=400)], "skirmish", 1)
        self.assertIsNone(result)
        self.assertEqual(state["delver"]["hp"], 8)  # nothing crossed the line


class TestMarkEffects(unittest.TestCase):
    def marked(self, effect):
        return stock_delver(marks=[{"name": "test mark", "effect": effect, "text": "t"}])

    def test_every_effect_moves_its_reading(self):
        base = stock_delver()
        self.assertEqual(engine.attack_bonus(self.marked("atk-1")), engine.attack_bonus(base) - 1)
        self.assertEqual(engine.guard(self.marked("guard-1")), engine.guard(base) - 1)
        self.assertEqual(engine.soak(self.marked("soak-1")), engine.soak(base) - 1)
        self.assertEqual(engine.nerve_bonus(self.marked("nerve-2")), engine.nerve_bonus(base) - 2)
        self.assertEqual(engine.grit_max(self.marked("grit_max-1")), engine.grit_max(base) - 1)
        self.assertEqual(engine.hp_max(self.marked("hp_max-3")), engine.hp_max(base) - 3)
        self.assertEqual(engine.camp_heal(self.marked("camp_heal_half"), random.Random(4)),
                         engine.camp_heal(base, random.Random(4)) // 2)

    def test_floors_hold(self):
        d = self.marked("soak-1")
        d["armor"] = {"name": "rags", "guard": 0, "soak": 0}
        self.assertEqual(engine.soak(d), 0)
        d = self.marked("grit_max-1")
        d["stats"]["nerve"] = 0
        self.assertEqual(engine.grit_max(d), 1)

    def test_flee_late_moves_the_skirmish_exit(self):
        plain = engine._combatant_from_delver(stock_delver(), "skirmish", False)
        late = engine._combatant_from_delver(self.marked("flee_late"), "skirmish", False)
        self.assertEqual(plain["flee_frac"], engine.SKIRMISH_FLEE_FRAC)
        self.assertEqual(late["flee_frac"], engine.FLEE_LATE_FRAC)

    def test_unknown_effect_raises(self):
        with self.assertRaises(ValueError):
            engine.has_mark(stock_delver(), "invincibility")

    def test_carried_marks_reach_the_fight(self):
        marked = self.marked("atk-1")
        a = run_to_end(stock_delver(), [wall(hp=400)], "measure", 9)
        b = run_to_end(marked, [wall(hp=400)], "measure", 9)
        mods_a = {int(HIT_RE.match(t).group(3)) for t in texts(a, "You ") if HIT_RE.match(t)}
        mods_b = {int(HIT_RE.match(t).group(3)) for t in texts(b, "You ") if HIT_RE.match(t)}
        self.assertEqual(mods_b, {m - 1 for m in mods_a})


# --------------------------------------------------------- plan 0006 pieces
DREAD_RE = re.compile(r"^(?:Something here is wrong|Fear gets its hook in).* vs (\d+)\)\.$")


def lurker_wall():
    """A thing that waits. Harmless except for what round 1 hands it."""
    return wall(name="waiter", traits=["lurker"], hp=400)


def enemy_mods(result, prefix):
    """Every attack modifier an enemy struck with, in order."""
    out = []
    for _, text, _ in result["events"]:
        m = PARTING_RE.match(text)
        if m and m.group(1).startswith(prefix):
            out.append(int(m.group(4)))
    return out


def my_mods_by_round(result):
    """(round, attack modifier) for every swing you took."""
    out, cur = [], 0
    for _, text, _ in result["events"]:
        if text.startswith("-- round "):
            cur = int(text.split()[2])
        m = HIT_RE.match(text)
        if m:
            out.append((cur, int(m.group(3))))
    return out


def dread_dc(result):
    for _, text, _ in result["events"]:
        m = DREAD_RE.match(text)
        if m:
            return int(m.group(1))
    raise AssertionError("no dread test in this fight")


class TestTheLearnedStances(unittest.TestCase):
    """Two stances bought with chits: the anti-ambush commit, and the one
    that buys accuracy with the clock."""

    def long_fight(self, delver, stance, seed=3):
        state, result = engine.start_fight(delver, [wall(hp=400)], stance, seed)
        self.assertIsNotNone(result, "the wall should never pause the fight")
        return result

    def test_the_tuples(self):
        self.assertEqual(engine.STANCES["brace"], (-1, 2, 2, 0))
        self.assertEqual(engine.STANCES["read"], (-2, 1, 0, 0))
        self.assertEqual(sorted(engine.BASE_STANCES),
                         sorted(s for s in engine.STANCES if s not in ("brace", "read")))

    def test_brace_carries_its_tuple_onto_the_combatant(self):
        d = stock_delver()
        c = engine._combatant_from_delver(d, "brace", False)
        self.assertEqual((c["atk"], c["guard"], c["soak"], c["dmg_bonus"]),
                         (engine.attack_bonus(d) - 1, engine.guard(d) + 2, engine.soak(d) + 2, 0))

    def test_a_lurker_gets_no_ambush_on_a_braced_delver(self):
        plain = run_to_end(stock_delver(hp=200, light=200), [lurker_wall()], "measure", 3)
        braced = run_to_end(stock_delver(hp=200, light=200), [lurker_wall()], "brace", 3)
        self.assertEqual(enemy_mods(plain, "waiter")[0], -30 + engine.LURKER_AMBUSH_ATK)
        self.assertEqual(enemy_mods(braced, "waiter")[0], -30)
        self.assertEqual(set(enemy_mods(braced, "waiter")), {-30})

    def test_read_strikes_at_plus_five_from_round_three_and_not_before(self):
        base = engine.attack_bonus(stock_delver())
        plain = self.long_fight(stock_delver(hp=200, light=200), "measure")
        reading = self.long_fight(stock_delver(hp=200, light=200), "read")
        self.assertEqual({mod for _, mod in my_mods_by_round(plain)}, {base})
        early = {mod for rnd, mod in my_mods_by_round(reading) if rnd < engine.READ_ROUND}
        late = {mod for rnd, mod in my_mods_by_round(reading) if rnd >= engine.READ_ROUND}
        self.assertEqual(early, {base - 2})
        self.assertEqual(late, {base - 2 + engine.READ_ATK_BONUS})
        self.assertEqual(len(texts(reading, "You have their pattern")), 1)

    def test_the_pattern_line_never_comes_up_in_a_short_read(self):
        short = run_to_end(stock_delver(), [wall(hp=1, soak=0)], "read", 2)
        self.assertEqual(texts(short, "You have their pattern"), [])

    def test_read_is_stateless_across_a_pause_switch_both_ways(self):
        seed, state = TestFight().find_pausing_seed()  # paused in measure
        state["round"] = engine.READ_ROUND + 2
        self.assertEqual(engine._read_bonus(state), 0)
        engine._switch_stance(state, "read")
        self.assertEqual(engine._read_bonus(state), engine.READ_ATK_BONUS)
        engine._switch_stance(state, "measure")
        self.assertEqual(engine._read_bonus(state), 0)
        state["round"] = engine.READ_ROUND - 1  # ... and it is the round that decides
        engine._switch_stance(state, "read")
        self.assertEqual(engine._read_bonus(state), 0)

    def test_the_pause_offers_only_stances_this_delver_knows(self):
        seed, state = TestFight().find_pausing_seed()
        state["delver"]["stances"] = ["measure", "ward"]
        opts = engine.pause_options(state)
        self.assertIn("ward", opts)
        for stance in ("brace", "read", "press", "skirmish"):
            self.assertNotIn(stance, opts)
        with self.assertRaises(ValueError):
            engine.resume_fight(state, "brace")


class TestKitInTheFight(unittest.TestCase):
    """Kit is insurance bought at the surface; the fight spends it for you."""

    def leave(self, enemies, stance="measure", seed=1, **over):
        """Pause at round 2 with hp to spare, then pull out."""
        d = stock_delver(stats=dict(TOUGH), hp=15, **over)
        state, result = engine.start_fight(d, enemies, stance, seed)
        self.assertIsNone(result, "expected a pause, got %r" % (result and result["outcome"]))
        r = engine.resume_fight(state, "withdraw")
        self.assertEqual(r["outcome"], "retreated")
        return r

    def strikes(self, result):
        counts = {}
        for who, _ in parting(result):
            counts[who] = counts.get(who, 0) + 1
        return counts

    def test_flash_powder_takes_the_ambush_and_is_gone(self):
        r = run_to_end(with_kit("flash", hp=200, light=200), [lurker_wall()], "measure", 3)
        self.assertEqual(enemy_mods(r, "waiter")[0], -30)
        self.assertEqual(r["kit_used"], ["flash"])
        self.assertEqual(len(texts(r, "flash powder")), 1)

    def test_flash_powder_is_not_spent_where_nothing_is_waiting(self):
        r = run_to_end(with_kit("flash", hp=200, light=200), [wall(hp=400)], "measure", 3)
        self.assertEqual(r["kit_used"], [])
        self.assertEqual(texts(r, "flash powder"), [])

    def test_without_the_powder_the_ambush_lands(self):
        r = run_to_end(stock_delver(hp=200, light=200), [lurker_wall()], "measure", 3)
        self.assertEqual(enemy_mods(r, "waiter")[0], -30 + engine.LURKER_AMBUSH_ATK)
        self.assertEqual(r["kit_used"], [])

    def test_the_rope_pays_the_lights_share_and_slows_the_swift(self):
        enemies = [pursuer("swift", ["swift"]), pursuer("plain", [])]
        plain = self.leave(enemies, light=10)
        roped = self.leave(enemies, light=10, kit=[{"name": "shard-hook rope", "effect": "rope",
                                                    "value": 9, "text": "t"}])
        self.assertEqual(self.strikes(plain), {"swift#1": 2, "plain#1": 1})
        self.assertEqual(plain["light"], 10 - engine.WITHDRAW_LIGHT_COST)
        self.assertEqual(self.strikes(roped), {"swift#1": 1, "plain#1": 1})
        self.assertEqual(roped["light"], 10)
        self.assertEqual(roped["kit_used"], ["rope"])

    def test_the_rope_leaves_a_relentless_pursuer_its_bonus(self):
        r = self.leave([pursuer("hunter", ["relentless"])], light=10,
                       kit=[{"name": "shard-hook rope", "effect": "rope", "value": 9, "text": "t"}])
        self.assertEqual([mod for _, mod in parting(r)], [-30 + engine.RELENTLESS_PURSUIT_ATK])

    def test_the_rope_and_the_prepared_exit_do_not_stack_into_anything_odd(self):
        enemies = [pursuer("swift", ["swift"]), pursuer("hunter", ["relentless"])]
        r = self.leave(enemies, stance="skirmish", light=10,
                       kit=[{"name": "shard-hook rope", "effect": "rope", "value": 9, "text": "t"}])
        self.assertEqual(self.strikes(r), {"swift#1": 1, "hunter#1": 1})
        self.assertEqual({mod for _, mod in parting(r)}, {-30})
        self.assertEqual(r["light"], 10)  # skirmish caps the strikes; the rope refunds the lamp

    def test_kit_you_do_not_hold_does_nothing(self):
        r = self.leave([pursuer("swift", ["swift"])], light=10)
        self.assertEqual(r["light"], 10 - engine.WITHDRAW_LIGHT_COST)
        self.assertEqual(r["kit_used"], [])


class TestRelicsInTheFight(unittest.TestCase):
    """One slot, worn until you die, and every one of them an exception."""

    def test_the_hammer_cracks_the_unarmored(self):
        target = wall(soak=3, hp=400)  # no `armored` trait: nothing else would crack it
        plain = run_to_end(stock_delver(hp=200), [target], "measure", 4)
        hammered = run_to_end(wearing("hammer", hp=200), [target], "measure", 4)
        self.assertEqual(texts(plain, "Armor gives"), [])
        soaks = [int(CRACK_RE.match(t).group(1)) for t in texts(hammered, "Armor gives")]
        self.assertEqual(soaks, [2, 1, 0])

    def test_a_hammer_crit_strips_three(self):
        for seed in range(60):
            r = run_to_end(wearing("hammer", hp=200), [wall(soak=9, hp=800)], "measure", seed)
            soak, crit_pending, seen = 9, False, False
            for _, text, _ in r["events"]:
                m = CRACK_RE.match(text)
                if m:
                    self.assertEqual(int(m.group(1)), max(0, soak - (3 if crit_pending else 1)))
                    soak = int(m.group(1))
                    seen = seen or crit_pending
                crit_pending = "CRIT!" in text and text.startswith("You hit")
            if seen:
                return
        self.fail("no crit landed on a soaking target in 60 seeds")

    def test_the_still_lamp_never_burns_a_round_and_costs_you_two_light(self):
        d = wearing("still_lamp", hp=200, light=10, weapon={"name": "shiv", "dmg": "1d4", "acc": 0})
        state, r = engine.start_fight(d, [wall(hp=12, soak=0)], "measure", 2)
        self.assertIsNone(state)
        self.assertEqual(r["outcome"], "victory")  # no withdraw: the lamp is the only cost here
        self.assertGreater(r["rounds"], engine.LIGHT_CLOCK_ROUNDS)
        self.assertEqual(r["light"], 10)
        self.assertEqual([b for b in beats(r) if b in ("lamp-low", "lamp-out")], [])
        self.assertEqual(engine.light_max(wearing("still_lamp")), engine.light_max(stock_delver()) - 2)

    def test_the_mirror_halves_the_first_landed_hit_and_no_other(self):
        puncher = wall(name="puncher", atk=30, dmg="1d6", hp=60)
        plain = run_to_end(stock_delver(hp=400, grit=0, light=400), [puncher], "measure", 6)
        mirrored = run_to_end(wearing("mirror", hp=400, grit=0, light=400), [puncher], "measure", 6)
        first = int(re.match(r"^puncher#1 hits you for (\d+)", texts(plain, "hits you for")[0]).group(1))
        lines = texts(mirrored, "patient mirror")
        self.assertEqual(len(lines), 1)
        self.assertIn("at %d." % (first // 2), lines[0])
        self.assertEqual(mirrored["hp"] - plain["hp"], first - first // 2)

    def test_the_bell_stops_the_waiting_and_eases_the_dread(self):
        r = run_to_end(wearing("bell", hp=200, light=200), [lurker_wall()], "measure", 3)
        self.assertEqual(enemy_mods(r, "waiter")[0], -30)
        plain = run_to_end(stock_delver(), [BRUTE], "measure", 7)
        belled = run_to_end(wearing("bell"), [BRUTE], "measure", 7)
        self.assertEqual(dread_dc(plain), 10 + 2 * BRUTE["dread"])
        self.assertEqual(dread_dc(belled), 10 + 2 * (BRUTE["dread"] - 1))

    def test_the_seal_winds_the_drum_one_further(self):
        self.assertEqual(engine.windings_max(wearing("seal")),
                         engine.windings_max(stock_delver()) + 1)

    def test_an_unknown_relic_effect_is_not_a_reading(self):
        with self.assertRaises(ValueError):
            engine.has_relic(stock_delver(), "invulnerability")
        with self.assertRaises(ValueError):
            engine.has_kit(stock_delver(), "a bigger sword")


if __name__ == "__main__":
    unittest.main()
