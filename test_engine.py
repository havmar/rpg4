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
    }
    d.update(over)
    return d


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


if __name__ == "__main__":
    unittest.main()
