"""Contract suite for content.py: catalogs, validation, generators, flow.

One broken world per validator clause: every lint gets exactly one test that
builds a catalog violating it and asserts rejection.
"""

import contextlib
import copy
import io
import json
import os
import shutil
import tempfile
import unittest

import content
import engine


def cat():
    return copy.deepcopy(content.load_catalog())


def _take_first(cat, save):
    """Batch helper: when the way splits, take passage 1."""
    if save["expedition"]["fork"]:
        return content.advance_delve(cat, save, passage=1)
    return None, []


def _delve_through(cat, save):
    """One completed step down, fork or no fork. Returns (site, lines)."""
    site, lines = content.advance_delve(cat, save)
    if site is None:
        site, more = content.advance_delve(cat, save, passage=1)
        lines = lines + more
    return site, lines


class TestCatalogLoads(unittest.TestCase):
    def test_clean_load(self):
        c = content.load_catalog()
        for section, count in content.CENSUS.items():
            if section == "names":
                self.assertEqual(sum(len(c["names"][p]) for p in content.NAME_LISTS), count)
                continue
            self.assertEqual(len(c[section]), count, section)

    def test_version_clause(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "catalogs")
            shutil.copytree(content.CATALOG_DIR, dst)
            path = os.path.join(dst, "gear.json")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["version"] = 99
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            old = content.CATALOG_DIR
            content.CATALOG_DIR = dst
            try:
                with self.assertRaises(content.CatalogError):
                    content.load_catalog()
            finally:
                content.CATALOG_DIR = old


class TestBrokenWorlds(unittest.TestCase):
    def assert_rejected(self, broken):
        with self.assertRaises(content.CatalogError):
            content.validate_catalog(broken)

    def test_missing_field(self):
        c = cat()
        del c["enemies"][0]["menace"]
        self.assert_rejected(c)

    def test_unknown_field(self):
        c = cat()
        c["salvage"][0]["loot_table"] = "x"
        self.assert_rejected(c)

    def test_duplicate_name(self):
        c = cat()
        c["weapons"][1]["name"] = c["weapons"][0]["name"]
        self.assert_rejected(c)

    def test_census_mismatch(self):
        c = cat()
        c["strange"].append(dict(c["strange"][0], name="a second seep"))
        self.assert_rejected(c)

    def test_bad_depth_band(self):
        c = cat()
        c["enemies"][0]["depth"] = [3, 2]
        self.assert_rejected(c)

    def test_bad_dice_spec(self):
        c = cat()
        c["enemies"][0]["dmg"] = "one sword"
        self.assert_rejected(c)

    def test_menace_below_one(self):
        c = cat()
        c["enemies"][0]["menace"] = 0
        self.assert_rejected(c)

    def test_unknown_trait(self):
        c = cat()
        c["enemies"][0]["traits"] = ["swift", "invisible"]
        self.assert_rejected(c)

    def test_unknown_strange_effect(self):
        c = cat()
        c["strange"][0]["effect"] = "free_lunch"
        self.assert_rejected(c)

    def test_unknown_site_kind(self):
        c = cat()
        c["sites"][0]["kind"] = "boss"
        self.assert_rejected(c)

    def test_locality_violation(self):
        c = cat()
        c["sites"][0]["text"] = "A tunnel that comes out behind Wake."
        self.assert_rejected(c)

    def test_site_coverage_gap(self):
        c = cat()
        for s in c["sites"]:
            if s["kind"] == "breather":
                s["depth"] = [1, 5]  # nobody covers depth 6
        self.assert_rejected(c)

    def test_enemy_coverage_gap(self):
        c = cat()
        for e in c["enemies"]:
            e["depth"] = [1, min(e["depth"][1], 5)]
        self.assert_rejected(c)

    def test_unknown_mark_effect(self):
        c = cat()
        c["marks"][0]["effect"] = "immortality"
        self.assert_rejected(c)

    def test_duplicate_mark_name(self):
        c = cat()
        c["marks"][1]["name"] = c["marks"][0]["name"]
        self.assert_rejected(c)

    def test_mark_census_mismatch(self):
        c = cat()
        c["marks"].append(dict(c["marks"][0], name="an eleventh regret"))
        self.assert_rejected(c)

    def test_name_census_mismatch(self):
        c = cat()
        c["names"]["given"].append("Extra")
        self.assert_rejected(c)

    def test_duplicate_name_in_a_name_list(self):
        c = cat()
        c["names"]["family"][1] = c["names"]["family"][0]
        self.assert_rejected(c)

    def test_name_locality_violation(self):
        c = cat()
        c["names"]["given"][0] = "Wakeborn"
        self.assert_rejected(c)

    def test_lurker_with_a_rumor(self):
        c = cat()
        lurker = next(e for e in c["enemies"] if "lurker" in e["traits"])
        lurker["rumor"] = "Something moving, plainly audible."
        self.assert_rejected(c)

    def test_non_lurker_without_a_rumor(self):
        c = cat()
        loud = next(e for e in c["enemies"] if "lurker" not in e["traits"])
        del loud["rumor"]
        self.assert_rejected(c)

    def test_strange_entry_without_a_rumor(self):
        c = cat()
        del c["strange"][0]["rumor"]
        self.assert_rejected(c)

    def test_rumor_locality_violation(self):
        c = cat()
        c["strange"][0]["rumor"] = "A draft that smells of Wake."
        self.assert_rejected(c)

    def test_priorities_not_permutation(self):
        c = cat()
        c["backgrounds"][0]["priorities"] = ["edge"] * 5
        self.assert_rejected(c)

    def test_unknown_gear_reference(self):
        c = cat()
        c["backgrounds"][0]["weapon"] = "vorpal sword"
        self.assert_rejected(c)

    def test_unknown_kit_effect(self):
        c = cat()
        c["kit"][0]["effect"] = "a second wind"
        self.assert_rejected(c)

    def test_duplicate_kit_name(self):
        c = cat()
        c["kit"][1]["name"] = c["kit"][0]["name"]
        self.assert_rejected(c)

    def test_kit_census_mismatch(self):
        c = cat()
        c["kit"].append(dict(c["kit"][0], name="a seventh comfort"))
        self.assert_rejected(c)

    def test_kit_locality_violation(self):
        c = cat()
        c["kit"][0]["text"] = "Pressed by the lamp-wrights of Wake."
        self.assert_rejected(c)

    def test_unknown_relic_effect(self):
        c = cat()
        c["relics"][0]["effect"] = "a third arm"
        self.assert_rejected(c)

    def test_duplicate_relic_name(self):
        c = cat()
        c["relics"][1]["name"] = c["relics"][0]["name"]
        self.assert_rejected(c)

    def test_relic_census_mismatch(self):
        c = cat()
        c["relics"].append(dict(c["relics"][0], name="the sixth wonder"))
        self.assert_rejected(c)

    def test_relic_locality_violation(self):
        c = cat()
        c["relics"][0]["text"] = "Only one broker in Wake will touch it."
        self.assert_rejected(c)


class TestGenerators(unittest.TestCase):
    def setUp(self):
        self.cat = content.load_catalog()

    def test_encounters_deterministic_and_bounded(self):
        for depth in range(1, content.DEPTH_MAX + 1):
            g1 = content.build_encounter(self.cat, depth, engine.rng_for("t", depth))
            g2 = content.build_encounter(self.cat, depth, engine.rng_for("t", depth))
            self.assertEqual([e["name"] for e in g1], [e["name"] for e in g2])
            self.assertGreaterEqual(len(g1), 1)
            self.assertLessEqual(sum(e["menace"] for e in g1), 2 + 2 * depth + 1)
            for e in g1:
                self.assertTrue(e["depth"][0] <= depth <= e["depth"][1])

    def test_sites_deterministic_and_wellformed(self):
        for i in range(60):
            depth = 1 + i % content.DEPTH_MAX
            s1 = content.generate_site(self.cat, depth, engine.rng_for("s", i))
            s2 = content.generate_site(self.cat, depth, engine.rng_for("s", i))
            self.assertEqual(s1, s2)
            self.assertIn(s1["kind"], content.SITE_KINDS)
            if s1["kind"] == "encounter":
                self.assertTrue(s1["enemies"])

    def test_roll_delver_is_deterministic(self):
        a = content.roll_delver(self.cat, 42)
        self.assertEqual(a, content.roll_delver(self.cat, 42))
        self.assertNotEqual(a, content.roll_delver(self.cat, 43))
        self.assertEqual(sum(a["stats"].values()), sum(content.BASE_ARRAY) + 1)

    def test_the_deal_reaches_every_background_and_every_name(self):
        rolled = [content.roll_delver(self.cat, seed) for seed in range(600)]
        self.assertEqual({d["background"] for d in rolled},
                         {b["name"] for b in self.cat["backgrounds"]})
        given = {d["name"].split()[0] for d in rolled}
        family = {d["name"].split()[1] for d in rolled}
        self.assertEqual(given, set(self.cat["names"]["given"]))
        self.assertEqual(family, set(self.cat["names"]["family"]))


class TestExpeditionFlow(unittest.TestCase):
    """Seeded integration career: the whole loop without a chat in sight."""

    def fresh_save(self, world_seed=1234):
        c = content.load_catalog()
        return c, content.new_save(c, world_seed)

    def test_career_runs_and_save_roundtrips(self):
        c, save = self.fresh_save()
        for _ in range(8):
            if not save["delver"]["alive"]:
                break
            rng = content._evt_rng(save)
            content.advance_delve(c, save)
            _take_first(c, save)
            if save["expedition"]["pending_site"] and save["expedition"]["pending_site"].get("enemies"):
                paused, _ = content.start_pending_fight(c, save, "measure")
                if paused:
                    save = json.loads(json.dumps(save))  # pause survives the save file
                    content.resume_paused_fight(c, save, "fight_on")
            save = json.loads(json.dumps(save))
            d = save["delver"]
            self.assertTrue(0 <= d["hp"] <= engine.hp_max(d))
            self.assertGreaterEqual(d["light"], 0)
        if save["delver"]["alive"] and save["expedition"]["active"]:
            content.do_surface(c, save)
            self.assertFalse(save["expedition"]["active"])
            self.assertEqual(save["delver"]["salvage"], [])
            self.assertGreaterEqual(save["wake"]["chits"], 0)
        self.assertTrue(save["history"])

    def test_guards(self):
        c, save = self.fresh_save()
        with self.assertRaises(ValueError):
            content.do_camp(c, save)  # not underground
        with self.assertRaises(ValueError):
            content.do_surface(c, save)  # already in Wake
        with self.assertRaises(ValueError):
            content.start_pending_fight(c, save, "measure")  # nothing pending
        with self.assertRaises(ValueError):
            content.do_train(save, "luck")
        with self.assertRaises(ValueError):
            content.do_buy(c, save, "vorpal sword")

    def test_train_and_buy(self):
        c, save = self.fresh_save()
        save["wake"]["chits"] = 100
        stat = "edge"
        before = save["delver"]["stats"][stat]
        content.do_train(save, stat)
        self.assertEqual(save["delver"]["stats"][stat], before + 1)
        content.do_buy(c, save, "salvage axe")
        self.assertEqual(save["delver"]["weapon"]["name"], "salvage axe")
        self.assertLess(save["wake"]["chits"], 100)


class TestMarks(unittest.TestCase):
    """The quirky wound layer: gained by hard fights, dressed at camp."""

    def setUp(self):
        self.cat = content.load_catalog()
        self.save = TestExpeditionFlow().fresh_save()[1]
        self.save["expedition"].update({"active": True, "depth": 2,
                                        "pending_site": {"name": "a test hall"}})

    def result(self, **over):
        d = self.save["delver"]
        r = {"outcome": "victory", "hp": engine.hp_max(d), "grit": 1, "light": 5,
             "worst_blow": 0, "rounds": 3, "kills": [], "kit_used": [], "events": [],
             "menace_defeated": 1}
        r.update(over)
        return r

    def marks(self):
        return [m["name"] for m in self.save["delver"]["marks"]]

    def test_big_blow_marks_you(self):
        content.gain_mark(self.cat, self.save, self.result(worst_blow=content.MARK_BLOW))
        self.assertEqual(len(self.marks()), 1)

    def test_coming_out_low_marks_you(self):
        hpm = engine.hp_max(self.save["delver"])
        content.gain_mark(self.cat, self.save, self.result(hp=hpm // 3))
        self.assertEqual(len(self.marks()), 1)

    def test_an_easy_fight_marks_nothing(self):
        content.gain_mark(self.cat, self.save, self.result(worst_blow=content.MARK_BLOW - 1))
        self.assertEqual(self.marks(), [])

    def test_going_down_is_not_a_mark(self):
        content.gain_mark(self.cat, self.save, self.result(outcome="down", worst_blow=20))
        self.assertEqual(self.marks(), [])

    def test_cap_of_three_distinct_marks(self):
        for _ in range(8):
            content.gain_mark(self.cat, self.save, self.result(worst_blow=9))
        self.assertEqual(len(self.marks()), engine.MARK_CAP)
        self.assertEqual(len(set(self.marks())), engine.MARK_CAP)

    def test_marks_are_deterministic(self):
        other = json.loads(json.dumps(self.save))
        for save in (self.save, other):
            for _ in range(3):
                content.gain_mark(self.cat, save, self.result(worst_blow=9))
        self.assertEqual([m["name"] for m in self.save["delver"]["marks"]],
                         [m["name"] for m in other["delver"]["marks"]])

    def test_a_mark_can_cost_you_hit_points(self):
        d = self.save["delver"]
        d["marks"] = [dict(content.by_name(self.cat["marks"], "cracked rib"))]
        d["hp"] = 99
        content.gain_mark(self.cat, self.save, self.result(worst_blow=9))
        self.assertLessEqual(d["hp"], engine.hp_max(d))

    def test_camp_dresses_the_newest_mark_only(self):
        d = self.save["delver"]
        for _ in range(3):
            content.gain_mark(self.cat, self.save, self.result(worst_blow=9))
        newest = self.marks()[-1]
        self.save["expedition"]["pending_site"] = None
        content.do_camp(self.cat, self.save)
        self.assertEqual(len(self.marks()), 2)
        self.assertNotIn(newest, self.marks())

    def test_surfacing_clears_every_mark(self):
        for _ in range(3):
            content.gain_mark(self.cat, self.save, self.result(worst_blow=9))
        self.save["expedition"]["pending_site"] = None
        content.do_surface(self.cat, self.save)
        self.assertEqual(self.marks(), [])

    def test_light_leak_costs_an_extra_measure_going_down(self):
        d = self.save["delver"]
        self.save["expedition"]["pending_site"] = None
        before = d["light"]
        _delve_through(self.cat, self.save)
        plain = before - d["light"]
        d["light"] = before
        self.save["expedition"]["pending_site"] = None
        d["marks"] = [dict(content.by_name(self.cat["marks"], "lamp-shy"))]
        _delve_through(self.cat, self.save)
        self.assertEqual(before - d["light"], plain + 1)

    def test_a_numbed_breather_gives_no_grit(self):
        d = self.save["delver"]
        d["marks"] = [dict(content.by_name(self.cat["marks"], "thousand-yard glaze"))]
        d["grit"] = 0
        exp = self.save["expedition"]
        exp["pending_site"] = None
        for _ in range(40):
            site, _ = _delve_through(self.cat, self.save)
            if site["kind"] == "breather":
                break
            exp["pending_site"] = None
            exp["depth"] = 1
        else:
            self.fail("no breather in 40 sites")
        self.assertEqual(d["grit"], 0)


class TestSatchel(unittest.TestCase):
    """A hard carry limit: the turnaround the descent never had."""

    def setUp(self):
        self.cat, self.save = TestExpeditionFlow().fresh_save()
        self.d = self.save["delver"]
        self.d["salvage"] = []

    def fill(self, *values):
        for i, v in enumerate(values):
            self.d["salvage"].append({"name": "thing %d" % i, "value": v})

    def test_capacity_tracks_craft(self):
        self.d["stats"]["craft"] = 2
        self.assertEqual(engine.satchel_cap(self.d), 6)
        self.d["stats"]["craft"] = 5
        self.assertEqual(engine.satchel_cap(self.d), 9)

    def test_scrap_stacks_into_one_slot(self):
        content.take_salvage(self.d, content.SCRAP, 4)
        content.take_salvage(self.d, content.SCRAP, 6)
        self.assertEqual(len(self.d["salvage"]), 1)
        self.assertEqual(self.d["salvage"][0]["value"], 10)

    def test_scrap_stacks_even_when_the_satchel_is_full(self):
        content.take_salvage(self.d, content.SCRAP, 4)
        self.fill(*[9] * (engine.satchel_cap(self.d) - 1))
        content.take_salvage(self.d, content.SCRAP, 5)
        self.assertEqual(len(self.d["salvage"]), engine.satchel_cap(self.d))
        self.assertEqual(content.by_name(self.d["salvage"], content.SCRAP)["value"], 9)

    def test_a_full_satchel_keeps_the_more_valuable_find(self):
        cap = engine.satchel_cap(self.d)
        self.fill(*([5] * (cap - 1) + [2]))
        taken, lines = content.take_salvage(self.d, "a better thing", 9)
        self.assertTrue(taken)
        self.assertEqual(len(self.d["salvage"]), cap)
        self.assertIn("a better thing", [i["name"] for i in self.d["salvage"]])
        self.assertNotIn(2, [i["value"] for i in self.d["salvage"]])
        self.assertIn("drop", lines[0])

    def test_the_cheapest_find_is_left_behind(self):
        cap = engine.satchel_cap(self.d)
        self.fill(*[5] * cap)
        taken, lines = content.take_salvage(self.d, "a worse thing", 3)
        self.assertFalse(taken)  # the only case that reports a refusal
        self.assertEqual(len(self.d["salvage"]), cap)
        self.assertNotIn("a worse thing", [i["name"] for i in self.d["salvage"]])
        self.assertIn("stays where it lies", lines[0])


class TestStashes(unittest.TestCase):
    """A cache is a promise to come back: value at a depth, safe from
    pursuit, worth nothing unless you return for it."""

    def setUp(self):
        self.cat, self.save = TestExpeditionFlow().fresh_save()
        self.save["expedition"].update({"active": True, "depth": 3})
        self.d = self.save["delver"]
        self.d["stats"]["craft"] = 1  # satchel cap 5, whatever the deal gave
        self.d["salvage"] = []

    def fill(self, *values):
        for i, v in enumerate(values):
            self.d["salvage"].append({"name": "thing %d" % v, "value": v})

    def values(self):
        return sorted(i["value"] for i in self.d["salvage"])

    def cached(self):
        return [sorted(i["value"] for i in r["items"]) for r in self.save["stashes"]]

    def test_stashing_moves_the_whole_satchel(self):
        self.fill(4, 9)
        lines = content.do_stash(self.save)
        self.assertEqual(self.d["salvage"], [])
        self.assertEqual([r["depth"] for r in self.save["stashes"]], [3])
        self.assertEqual(self.cached(), [[4, 9]])
        self.assertTrue(any("thing 9" in line for line in lines))

    def test_a_round_trip_preserves_items_and_values(self):
        self.fill(4, 9)
        before = [dict(i) for i in self.d["salvage"]]
        content.do_stash(self.save)
        lines = content.recover_stash(self.save)
        self.assertEqual(sorted((i["name"], i["value"]) for i in self.d["salvage"]),
                         sorted((i["name"], i["value"]) for i in before))
        self.assertEqual(self.save["stashes"], [])
        self.assertTrue(lines)

    def test_recovery_takes_the_best_the_satchel_holds_and_leaves_the_rest(self):
        cap = engine.satchel_cap(self.d)
        self.assertEqual(cap, 5)
        self.fill(*range(1, cap + 4))  # 8 things, values 1..8
        content.do_stash(self.save)
        content.recover_stash(self.save)
        self.assertEqual(self.values(), [4, 5, 6, 7, 8])
        self.assertEqual(self.cached(), [[1, 2, 3]])

    def test_recovery_leaves_nothing_behind_when_it_all_fits(self):
        self.fill(1, 2)
        content.do_stash(self.save)
        content.recover_stash(self.save)
        self.assertEqual(self.values(), [1, 2])
        self.assertEqual(self.save["stashes"], [])

    def test_stashes_at_one_depth_merge_and_other_depths_do_not(self):
        self.fill(4)
        content.do_stash(self.save)
        self.fill(9)
        content.do_stash(self.save)
        self.assertEqual(self.cached(), [[4, 9]])
        self.save["expedition"]["depth"] = 4
        self.fill(2)
        content.do_stash(self.save)
        self.assertEqual([r["depth"] for r in self.save["stashes"]], [3, 4])
        self.assertEqual(self.cached(), [[4, 9], [2]])

    def test_arriving_where_there_is_no_cache_is_quiet(self):
        self.assertEqual(content.recover_stash(self.save), [])

    def test_stashing_nothing_raises(self):
        with self.assertRaises(ValueError):
            content.do_stash(self.save)

    def test_you_cannot_stash_with_something_watching_you(self):
        exp = self.save["expedition"]
        self.fill(4)
        exp["pending_site"] = {"name": "a hall", "enemies": ["glasshound"]}
        with self.assertRaises(ValueError):
            content.do_stash(self.save)
        exp["pending_site"] = None
        exp["paused_fight"] = {"delver": {"hp": 3}}
        with self.assertRaises(ValueError):
            content.do_stash(self.save)
        exp["paused_fight"] = None
        exp["fork"] = [{"depth": 4, "rumor": "quiet"}]
        with self.assertRaises(ValueError):
            content.do_stash(self.save)
        exp["fork"] = None
        content.do_stash(self.save)  # ... and with the room clear, it works

    def test_you_cannot_stash_in_wake(self):
        self.fill(4)
        self.save["expedition"]["active"] = False
        with self.assertRaises(ValueError):
            content.do_stash(self.save)

    def test_a_cache_outlives_the_climb_and_banks_nothing(self):
        self.fill(4, 9)
        content.do_stash(self.save)
        self.save["expedition"]["pending_site"] = None
        content.do_surface(self.cat, self.save)
        self.assertEqual(self.cached(), [[4, 9]])
        self.assertEqual(self.save["wake"]["chits"], 0)

    def test_the_delve_back_down_finds_the_cache(self):
        cat, save = TestExpeditionFlow().fresh_save(99)
        exp, d = save["expedition"], save["delver"]
        for _ in range(2):
            _delve_through(cat, save)
            exp["pending_site"] = None
        self.assertEqual(exp["depth"], 2)
        d["salvage"] = [{"name": "a cached thing", "value": 7}]
        content.do_stash(save)
        exp["depth"] = 1  # where a retreat would have left you
        _, lines = _delve_through(cat, save)
        self.assertEqual(exp["depth"], 2)
        self.assertEqual(save["stashes"], [])
        self.assertIn("a cached thing", [i["name"] for i in d["salvage"]])
        self.assertTrue(any("cache" in line for line in lines))

    def test_falling_back_from_a_fight_finds_the_cache(self):
        save, exp, d = self.save, self.save["expedition"], self.d
        self.fill(6)
        content.do_stash(save)  # cached at depth 3
        exp["depth"] = 4
        exp["pending_site"] = {"name": "a test hall", "enemies": ["glasshound"]}
        result = {"outcome": "retreated", "hp": 9, "grit": 1, "light": 3, "worst_blow": 0,
                  "rounds": 4, "kills": [], "kit_used": [], "events": [], "menace_defeated": 0}
        content.apply_fight_result(self.cat, save, result)
        self.assertEqual(exp["depth"], 3)
        self.assertEqual(d["light"], 3)  # the withdraw's price lands on the delver
        self.assertEqual(self.values(), [6])
        self.assertEqual(save["stashes"], [])

    def test_the_save_shape_carries_the_stashes(self):
        cat, save = TestExpeditionFlow().fresh_save()
        self.assertEqual(save["version"], engine.SAVE_VERSION)
        self.assertEqual(save["stashes"], [])
        self.assertEqual(json.loads(json.dumps(save)), save)

    def test_a_save_with_no_stashes_key_raises(self):
        """No migration, ever: a save that cannot hold a cache is a bug."""
        old = json.loads(json.dumps(self.save))
        del old["stashes"]
        with self.assertRaises(KeyError):
            content.recover_stash(old)

    def test_a_career_that_caches_replays_byte_identical(self):
        def career(seed):
            cat, save = TestExpeditionFlow().fresh_save(seed)
            d = save["delver"]
            for _ in range(10):
                if not d["alive"]:
                    break
                exp = save["expedition"]
                if exp["pending_site"] and exp["pending_site"].get("enemies"):
                    paused, _ = content.start_pending_fight(cat, save, "skirmish")
                    if paused:
                        content.resume_paused_fight(cat, save, "withdraw")
                    continue
                if d["salvage"]:
                    content.do_stash(save)
                _delve_through(cat, save)
            return json.dumps(save, sort_keys=True)
        self.assertEqual(career(4242), career(4242))
        self.assertTrue(json.loads(career(4242))["stashes"] is not None)

    def test_the_pages_show_a_cache(self):
        import pages
        self.fill(4, 9)
        content.do_stash(self.save)
        self.save["expedition"]["sites"] = [
            {"depth": 3, "kind": "salvage", "name": "a shelf of drawers"}]
        with tempfile.TemporaryDirectory() as tmp:
            old, pages.RUNS_DIR = pages.RUNS_DIR, tmp
            try:
                pages.write_map(self.save)
                pages.write_delver(self.save)
                with open(os.path.join(pages.run_dir(self.save), "map.txt"), encoding="utf-8") as f:
                    mapped = f.read()
                with open(os.path.join(pages.run_dir(self.save), "delver.txt"), encoding="utf-8") as f:
                    sheet = f.read()
            finally:
                pages.RUNS_DIR = old
        self.assertIn("..stash: 2 items", mapped)
        self.assertIn("depth 3: 2 items worth 13", sheet)


class TestTheCareerTournament(unittest.TestCase):
    """The instrument the plan-0002 benchlog asked for: it must be
    repeatable, and it must not peek at the fight that is waiting."""

    def pending_fight(self, cat, save):
        exp = save["expedition"]
        for _ in range(60):
            _delve_through(cat, save)
            if exp["pending_site"] and exp["pending_site"].get("enemies"):
                return
            exp["depth"] = 1  # stay shallow; we only want an encounter
        self.fail("no encounter in 60 delves")

    def resolve(self, cat, save):
        paused, _ = content.start_pending_fight(cat, save, "measure")
        if paused:
            content.resume_paused_fight(cat, save, "fight_on")
        return save["last_fight"]["events"]

    def test_every_policy_produces_a_full_row(self):
        import bench_policy
        keys = {"policy", "careers", "died", "expeditions", "chits_mean",
                "chits_median", "max_depth", "light", "flees"}
        for policy in bench_policy.CAREER_POLICIES:
            row = bench_policy.career_row(policy, 2, 2)
            self.assertEqual(set(row), keys, policy)
            self.assertEqual(row["careers"], 2)
            self.assertEqual(row["policy"], policy)

    def test_the_tournament_is_deterministic(self):
        import bench_policy
        self.assertEqual(bench_policy.career_row("hedge", 3, 2),
                         bench_policy.career_row("hedge", 3, 2))
        self.assertNotEqual(bench_policy.career_row("hedge", 3, 2),
                            bench_policy.career_row("committed", 3, 2))

    def test_the_shopping_step_works_the_shelf(self):
        import bench_policy
        cat, save = TestExpeditionFlow().fresh_save(7)
        save["wake"]["chits"] = 100
        bench_policy.buy_kit(cat, save)
        self.assertEqual([k["name"] for k in save["delver"]["kit"]],
                         ["oil flask", "tithe of oilbread"])  # cheapest first, one of each
        self.assertGreaterEqual(save["wake"]["chits"], bench_policy.SHOP_RESERVE)
        poor = TestExpeditionFlow().fresh_save(7)[1]
        poor["wake"]["chits"] = 5
        bench_policy.buy_kit(cat, poor)
        self.assertEqual(poor["delver"]["kit"], [])

    def test_the_shopping_step_wears_the_first_relic_only(self):
        import bench_policy
        cat, save = TestExpeditionFlow().fresh_save(7)
        save["expedition"].update({"active": True, "depth": 4})
        d = save["delver"]
        for name in ("the still lamp", "the tuning hammer"):
            rec = content.by_name(cat["relics"], name)
            d["salvage"].append({"name": rec["name"], "value": rec["value"]})
        self.assertTrue(bench_policy.wear_first_relic(cat, save))
        self.assertEqual(d["relic"]["name"], "the still lamp")
        self.assertFalse(bench_policy.wear_first_relic(cat, save))
        self.assertEqual([i["name"] for i in d["salvage"]], ["the tuning hammer"])

    def test_the_informed_sims_cannot_peek_at_the_waiting_fight(self):
        import bench_policy
        cat, save = TestExpeditionFlow().fresh_save(515)
        self.pending_fight(cat, save)
        untouched = json.loads(json.dumps(save))
        stance = bench_policy.informed_stance(cat, save)
        self.assertIn(stance, engine.STANCES)
        self.assertEqual(save, untouched)  # nothing drawn, nothing spent
        self.assertEqual(self.resolve(cat, save), self.resolve(cat, untouched))


class TestCommission(unittest.TestCase):
    """The pull: surfacing is a payday, not a concession."""

    def setUp(self):
        self.cat, self.save = TestExpeditionFlow().fresh_save()
        self.save["expedition"].update({"active": True, "depth": 2})
        self.save["delver"]["salvage"] = []
        self.save["delver"]["knack"] = "cutter"  # keep the glasspicker bonus out of the sums

    def wanted(self):
        return content.by_name(self.cat["salvage"], self.save["wake"]["commission"]["item"])

    def test_a_filled_order_pays_double_for_exactly_one(self):
        item = self.wanted()
        for _ in range(2):
            self.save["delver"]["salvage"].append({"name": item["name"], "value": item["value"]})
        drawn_at = self.save["counter"]
        content.do_surface(self.cat, self.save)
        self.assertEqual(self.save["wake"]["chits"], 3 * item["value"])
        # a new day is a new posting: the draw happened, even if it repeats
        self.assertGreater(self.save["counter"], drawn_at)
        self.assertTrue(any("order for" in h for h in self.save["history"]))

    def test_an_unfilled_order_banks_plainly_and_is_reposted(self):
        other = next(s for s in self.cat["salvage"] if s["name"] != self.wanted()["name"])
        self.save["delver"]["salvage"].append({"name": other["name"], "value": other["value"]})
        content.do_surface(self.cat, self.save)
        self.assertEqual(self.save["wake"]["chits"], other["value"])
        self.assertIn("item", self.save["wake"]["commission"])

    def test_the_bonus_is_the_list_price(self):
        com = self.save["wake"]["commission"]
        self.assertEqual(com["bonus"], content.by_name(self.cat["salvage"], com["item"])["value"])


class TestTheDrum(unittest.TestCase):
    """Odds as a rationed object in the world. Reseed, never peek."""

    def setUp(self):
        self.cat, self.save = TestExpeditionFlow().fresh_save()
        self.pending_fight(self.save)

    def pending_fight(self, save):
        exp = save["expedition"]
        for _ in range(60):
            _delve_through(self.cat, save)
            if exp["pending_site"] and exp["pending_site"].get("enemies"):
                return
            exp["depth"] = 1  # stay shallow; we only want an encounter
        self.fail("no encounter in 60 delves")

    def resolve(self, save):
        paused, _ = content.start_pending_fight(self.cat, save, "measure")
        if paused:
            content.resume_paused_fight(self.cat, save, "fight_on")
        return save["last_fight"]["events"]

    def test_consulting_the_drum_cannot_change_the_fight(self):
        untouched = json.loads(json.dumps(self.save))
        content.simulate_odds(self.cat, self.save, 25)
        self.assertEqual(self.resolve(self.save), self.resolve(untouched))

    def test_consulting_the_drum_twice_still_cannot(self):
        untouched = json.loads(json.dumps(self.save))
        content.simulate_odds(self.cat, self.save, 10)
        content.simulate_odds(self.cat, self.save, 10)
        self.assertEqual(self.resolve(self.save), self.resolve(untouched))

    def test_rows_are_whole_distributions(self):
        rows = content.simulate_odds(self.cat, self.save, 50)
        self.assertTrue(rows)
        for row in rows:
            self.assertAlmostEqual(row["victory"] + row["retreated"] + row["down"], 100.0, places=6)
            self.assertEqual(row["n"], 50)

    def test_a_winding_per_question_and_then_it_is_spent(self):
        d = self.save["delver"]
        d["windings"] = 2
        content.simulate_odds(self.cat, self.save, 5)
        self.assertEqual(d["windings"], 1)
        content.simulate_odds(self.cat, self.save, 5)
        self.assertEqual(d["windings"], 0)
        with self.assertRaises(ValueError):
            content.simulate_odds(self.cat, self.save, 5)

    def test_the_drum_hears_nothing_when_no_fight_stands_in_front_of_you(self):
        self.save["expedition"]["pending_site"] = None
        with self.assertRaises(ValueError):
            content.simulate_odds(self.cat, self.save, 5)

    def test_a_night_above_ground_winds_it_again(self):
        d = self.save["delver"]
        d["windings"] = 0
        self.save["expedition"]["pending_site"] = None
        content.do_surface(self.cat, self.save)
        self.assertEqual(d["windings"], engine.windings_max(d))

    def test_it_reads_a_paused_fight_too(self):
        save = self.save
        while True:
            paused, _ = content.start_pending_fight(self.cat, save, "measure")
            if paused:
                break
            if not save["delver"]["alive"]:
                self.fail("died before a pause")
            self.pending_fight(save)
        rows = content.simulate_odds(self.cat, save, 20)
        labels = {r["label"] for r in rows}
        self.assertEqual(labels, set(engine.pause_options(save["expedition"]["paused_fight"])))
        untouched = json.loads(json.dumps(save))
        untouched["expedition"]["paused_fight"] = json.loads(
            json.dumps(save["expedition"]["paused_fight"]))
        a = engine.resume_fight(save["expedition"]["paused_fight"], "fight_on")
        b = engine.resume_fight(untouched["expedition"]["paused_fight"], "fight_on")
        self.assertEqual(a["events"], b["events"])


class TestSitesDoNotRepeat(unittest.TestCase):
    def setUp(self):
        self.cat = content.load_catalog()

    def test_a_template_does_not_come_round_again_until_its_pool_is_spent(self):
        pools = {kind: [s["name"] for s in self.cat["sites"]
                        if s["kind"] == kind and s["depth"][0] <= 3 <= s["depth"][1]]
                 for kind in content.SITE_KINDS}
        drawn = {kind: [] for kind in content.SITE_KINDS}
        seen = set()
        for i in range(40):
            site = content.generate_site(self.cat, 3, engine.rng_for("norepeat", i), exclude=seen)
            seen.add(site["name"])
            drawn[site["kind"]].append(site["name"])
        for kind, names in drawn.items():
            head = names[:len(pools[kind])]
            self.assertEqual(len(set(head)), len(head), "%s repeated early: %s" % (kind, head))

    def test_an_expedition_repeats_only_once_a_pool_is_spent(self):
        cat, save = TestExpeditionFlow().fresh_save(77)
        exp = save["expedition"]
        for _ in range(8):
            _delve_through(cat, save)
            exp["pending_site"] = None
        used = []
        for entry in exp["sites"]:
            pool = {s["name"] for s in cat["sites"] if s["kind"] == entry["kind"]
                    and s["depth"][0] <= entry["depth"] <= s["depth"][1]}
            if entry["name"] in used:
                self.assertTrue(pool <= set(used),
                                "%r came round again with %s still unused"
                                % (entry["name"], sorted(pool - set(used))))
            used.append(entry["name"])
        self.assertGreater(len(used), 4)


class TestTheOpeningCommand(unittest.TestCase):
    """`new` deals a stranger and puts them underground in one command."""

    def test_new_writes_a_complete_v3_save_already_at_depth_one(self):
        import pages
        import session
        with tempfile.TemporaryDirectory() as tmp:
            old_save, old_runs = session.SAVE_PATH, pages.RUNS_DIR
            session.SAVE_PATH = os.path.join(tmp, "save.json")
            pages.RUNS_DIR = os.path.join(tmp, "runs")
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    session.main(["new", "--seed", "31337"])
                with open(session.SAVE_PATH, encoding="utf-8") as f:
                    save = json.load(f)
                with open(os.path.join(pages.run_dir(save), "delver.txt"), encoding="utf-8") as f:
                    sheet = f.read()
                with open(os.path.join(pages.run_dir(save), "save.json"), encoding="utf-8") as f:
                    snapshot = json.load(f)
            finally:
                session.SAVE_PATH, pages.RUNS_DIR = old_save, old_runs
        self.assertEqual(snapshot, save)
        self.assertEqual(save["version"], engine.SAVE_VERSION)
        self.assertEqual(save["odds_counter"], 0)
        self.assertTrue(save["expedition"]["active"])
        self.assertEqual(save["expedition"]["depth"], 1)
        self.assertEqual(len(save["expedition"]["sites"]), 1)
        d = save["delver"]
        self.assertEqual(d["marks"], [])
        self.assertEqual(d["windings"], engine.windings_max(d))
        self.assertEqual(len(d["name"].split()), 2)
        self.assertIn("item", save["wake"]["commission"])
        self.assertIn("CRAFT  provision", sheet)
        self.assertIn("SATCHEL", sheet)

    def test_resume_restores_the_live_save_from_the_run_snapshot(self):
        """A web container is ephemeral: the committed runs/<slug>/save.json
        snapshot is the only save that survives a session. `resume` copies
        it back into place; `new` refuses a name already on the shelf."""
        import pages
        import session
        with tempfile.TemporaryDirectory() as tmp:
            old_save, old_runs = session.SAVE_PATH, pages.RUNS_DIR
            session.SAVE_PATH = os.path.join(tmp, "save.json")
            pages.RUNS_DIR = os.path.join(tmp, "runs")
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    session.main(["new", "--seed", "31337"])
                with open(session.SAVE_PATH, encoding="utf-8") as f:
                    save = json.load(f)
                os.remove(session.SAVE_PATH)  # the container died
                with contextlib.redirect_stdout(io.StringIO()):
                    session.main(["resume", pages.run_slug(save)])
                with open(session.SAVE_PATH, encoding="utf-8") as f:
                    resumed = json.load(f)
                os.remove(session.SAVE_PATH)
                with self.assertRaises(SystemExit):  # same stranger, same shelf slot
                    with contextlib.redirect_stdout(io.StringIO()):
                        session.main(["new", "--seed", "31337"])
            finally:
                session.SAVE_PATH, pages.RUNS_DIR = old_save, old_runs
        self.assertEqual(resumed, save)


class TestRumors(unittest.TestCase):
    """Rumors are honest, because the senses are honest. The world is not
    obliged to be audible."""

    def setUp(self):
        self.cat = content.load_catalog()

    def site(self, kind, **over):
        s = {"depth": 3, "kind": kind, "name": "a room", "text": "..."}
        s.update(over)
        return s

    def rumor(self, site, seed=1):
        return content.rumor_for(self.cat, site, engine.rng_for("rumor", seed))

    def test_quiet_is_the_same_quiet(self):
        lurkers = [e["name"] for e in self.cat["enemies"] if "lurker" in e["traits"]]
        ambush = self.rumor(self.site("encounter", enemies=lurkers))
        rest = self.rumor(self.site("breather"))
        self.assertEqual(ambush, content.QUIET_RUMOR)
        self.assertEqual(ambush, rest)

    def test_an_ambush_reads_exactly_like_a_rest(self):
        lurkers = [e["name"] for e in self.cat["enemies"] if "lurker" in e["traits"]]
        ambush = self.site("encounter", enemies=lurkers, name="one room")
        rest = self.site("breather", name="another room")
        for s in (ambush, rest):
            s["rumor"] = self.rumor(s)
        self.assertEqual(content.fork_lines([ambush]), content.fork_lines([rest]))

    def test_the_loudest_thing_speaks_for_the_group(self):
        group = ["shardswarm", "saltfog strangler", "vitrified watchman"]
        self.assertEqual(self.rumor(self.site("encounter", enemies=group)),
                         content.by_name(self.cat["enemies"], "vitrified watchman")["rumor"])

    def test_a_menace_tie_breaks_alphabetically(self):
        a = content.by_name(self.cat["enemies"], "chorus pane")
        b = content.by_name(self.cat["enemies"], "glasshound")
        self.assertEqual(a["menace"], b["menace"])
        self.assertEqual(self.rumor(self.site("encounter", enemies=[b["name"], a["name"]])),
                         a["rumor"])

    def test_a_lurker_never_speaks_for_a_group(self):
        group = ["shardswarm", "mirrorling"]  # the mirrorling out-menaces the swarm
        self.assertEqual(self.rumor(self.site("encounter", enemies=group)),
                         content.by_name(self.cat["enemies"], "shardswarm")["rumor"])

    def test_salvage_rumors_come_from_the_authored_three(self):
        seen = {self.rumor(self.site("salvage", salvage=["vitric lens"]), seed=i)
                for i in range(60)}
        self.assertEqual(seen, set(content.SALVAGE_RUMORS))

    def test_strange_speaks_with_its_own_authored_line(self):
        for entry in self.cat["strange"]:
            s = self.site("strange", strange=entry["name"], effect=entry["effect"],
                          strange_text=entry["text"])
            self.assertEqual(self.rumor(s), entry["rumor"])

    def test_every_generated_site_carries_a_rumor(self):
        for i in range(80):
            site = content.generate_site(self.cat, 1 + i % content.DEPTH_MAX,
                                         engine.rng_for("carries", i))
            self.assertTrue(site["rumor"])


class TestForks(unittest.TestCase):
    """The way splits, and the only thing announcing a passage is a rumor."""

    def fresh(self, seed=2024):
        return TestExpeditionFlow().fresh_save(seed)

    def forked(self, seed_from=0):
        """A save with a fork pending, and its catalog."""
        for seed in range(seed_from, seed_from + 80):
            cat, save = self.fresh(seed)
            exp = save["expedition"]
            for _ in range(6):
                site, _ = content.advance_delve(cat, save)
                if site is None:
                    return cat, save
                exp["pending_site"] = None
            continue
        self.fail("no fork in 80 seeded expeditions")

    def test_the_first_delve_is_always_a_single_throat(self):
        for seed in range(120):
            cat, save = self.fresh(seed)
            site, _ = content.advance_delve(cat, save)
            self.assertIsNotNone(site, "seed %d stalled the mouth at a fork" % seed)
            self.assertEqual(save["expedition"]["fork"], None)

    def test_forks_are_deterministic(self):
        cat, a = self.fresh(4242)
        _, b = self.fresh(4242)
        for save in (a, b):
            for _ in range(8):
                site, _ = content.advance_delve(cat, save)
                if site is None:
                    content.advance_delve(cat, save, passage=1)
                save["expedition"]["pending_site"] = None
        self.assertEqual(a["expedition"]["sites"], b["expedition"]["sites"])
        self.assertEqual(a["expedition"]["declined"], b["expedition"]["declined"])
        self.assertEqual(a["expedition"]["fork"], b["expedition"]["fork"])

    def test_every_shape_the_table_allows_shows_up(self):
        shapes = set()
        for i in range(400):
            shapes.add(content._draw_fork_shape(engine.rng_for("shape", i)))
        self.assertEqual(shapes, {s for s, _ in content.FORK_SHAPES})

    def test_passages_are_distinct_rooms_when_the_pool_allows(self):
        """Templates are drawn per kind, so the guarantee is per kind: two
        strange passages can only differ if two strange rooms are left."""
        checked = 0
        for seed in range(40):
            cat, save = self.forked(seed_from=seed)
            exp = save["expedition"]
            used = {s["name"] for s in exp["sites"]}
            depth = exp["fork"][0]["depth"]
            by_kind = {}
            for passage in exp["fork"]:
                by_kind.setdefault(passage["kind"], []).append(passage["name"])
            for kind, names in by_kind.items():
                pool = {s["name"] for s in cat["sites"] if s["kind"] == kind
                        and s["depth"][0] <= depth <= s["depth"][1]}
                if len(pool - used) >= len(names):
                    self.assertEqual(len(set(names)), len(names), names)
                    checked += 1
        self.assertGreater(checked, 0)

    def test_reprinting_a_fork_costs_nothing_and_decides_nothing(self):
        cat, save = self.forked()
        exp, d = save["expedition"], save["delver"]
        before = (save["counter"], d["light"], exp["depth"],
                  json.dumps(exp["fork"]), len(exp["sites"]))
        site, lines = content.advance_delve(cat, save)
        self.assertIsNone(site)
        self.assertEqual(lines, content.fork_lines(exp["fork"]))
        self.assertEqual(before, (save["counter"], d["light"], exp["depth"],
                                  json.dumps(exp["fork"]), len(exp["sites"])))

    def test_taking_a_passage_spends_one_light_and_closes_the_others(self):
        for seed in range(60):
            cat, save = self.forked(seed_from=seed)
            exp, d = save["expedition"], save["delver"]
            if exp["fork"][0]["kind"] == "strange":
                continue  # strange sites move light themselves; measure elsewhere
            taken, others = exp["fork"][0], exp["fork"][1:]
            light, depth = d["light"], exp["depth"]
            site, _ = content.advance_delve(cat, save, passage=1)
            self.assertEqual(site["name"], taken["name"])
            self.assertEqual(d["light"], light - 1)
            self.assertEqual(exp["depth"], depth + 1)
            self.assertIsNone(exp["fork"])
            self.assertEqual([p["rumor"] for p in others],
                             [x["rumor"] for x in exp["declined"]])
            return
        self.fail("no non-strange fork in 60 seeds")

    def test_old_stairs_carry_you_through_a_fork_for_free(self):
        cat, save = self.forked()
        save["expedition"]["free_delve"] = True
        light = save["delver"]["light"]
        content.advance_delve(cat, save, passage=1)
        self.assertGreaterEqual(save["delver"]["light"], light)

    def test_the_way_is_single_here(self):
        cat, save = self.fresh()
        content.advance_delve(cat, save)
        save["expedition"]["pending_site"] = None
        with self.assertRaises(ValueError):
            content.advance_delve(cat, save, passage=1)

    def test_there_are_only_so_many_passages(self):
        cat, save = self.forked()
        with self.assertRaises(ValueError):
            content.advance_delve(cat, save, passage=len(save["expedition"]["fork"]) + 1)
        with self.assertRaises(ValueError):
            content.advance_delve(cat, save, passage=0)

    def test_surfacing_closes_the_fork_and_forgets_the_roads_not_taken(self):
        cat, save = self.forked()
        content.advance_delve(cat, save, passage=1)
        save["expedition"]["pending_site"] = None
        self.assertTrue(save["expedition"]["declined"])
        content.do_surface(cat, save)
        self.assertIsNone(save["expedition"]["fork"])
        self.assertEqual(save["expedition"]["declined"], [])

    def test_the_save_shape_is_complete(self):
        cat, save = self.fresh()
        self.assertEqual(save["version"], engine.SAVE_VERSION)
        for key in ("fork", "declined"):
            self.assertIn(key, save["expedition"])
        blob = json.loads(json.dumps(save))
        self.assertEqual(blob, save)

    def test_the_map_remembers_what_you_did_not_open(self):
        import pages
        cat, save = self.forked()
        content.advance_delve(cat, save, passage=1)
        with tempfile.TemporaryDirectory() as tmp:
            old, pages.RUNS_DIR = pages.RUNS_DIR, tmp
            try:
                pages.write_map(save)
                with open(os.path.join(pages.run_dir(save), "map.txt"), encoding="utf-8") as f:
                    text = f.read()
            finally:
                pages.RUNS_DIR = old
        for entry in save["expedition"]["declined"]:
            self.assertIn("..unopened: %s" % entry["rumor"], text)


class TestTheShelf(unittest.TestCase):
    """Kit: bought at the counter, declared at purchase, spent by the world."""

    def setUp(self):
        self.cat, self.save = TestExpeditionFlow().fresh_save()
        self.save["wake"]["chits"] = 100
        self.d = self.save["delver"]

    def held(self):
        return [k["name"] for k in self.d["kit"]]

    def underground(self):
        self.save["expedition"].update({"active": True, "depth": 2})

    def test_a_fresh_delver_carries_nothing_and_knows_the_four(self):
        self.assertEqual(self.d["kit"], [])
        self.assertIsNone(self.d["relic"])
        self.assertEqual(self.d["stances"], list(engine.BASE_STANCES))

    def test_buying_kit_takes_the_chits_and_hands_you_the_thing(self):
        lines = content.do_buy(self.cat, self.save, "oil flask")
        self.assertEqual(self.held(), ["oil flask"])
        self.assertEqual(self.save["wake"]["chits"], 100 - 6)
        self.assertTrue(any("oil flask" in line for line in lines))

    def test_two_pieces_of_kit_and_no_more(self):
        content.do_buy(self.cat, self.save, "oil flask")
        content.do_buy(self.cat, self.save, "drum key")
        chits = self.save["wake"]["chits"]
        with self.assertRaises(ValueError):
            content.do_buy(self.cat, self.save, "dressing roll")
        self.assertEqual(len(self.d["kit"]), content.KIT_CAP)
        self.assertEqual(self.save["wake"]["chits"], chits)  # a refusal costs nothing

    def test_one_of_each(self):
        content.do_buy(self.cat, self.save, "oil flask")
        with self.assertRaises(ValueError):
            content.do_buy(self.cat, self.save, "oil flask")
        self.assertEqual(self.held(), ["oil flask"])

    def test_the_outfitters_are_in_the_haven(self):
        self.underground()
        with self.assertRaises(ValueError):
            content.do_buy(self.cat, self.save, "oil flask")

    def test_the_flask_is_three_more_hours_of_seeing(self):
        content.do_buy(self.cat, self.save, "oil flask")
        self.underground()
        light = self.d["light"]
        content.do_use(self.save, "oil flask")
        self.assertEqual(self.d["light"], light + content.OIL_FLASK_LIGHT)
        self.assertEqual(self.held(), [])

    def test_the_drum_key_winds_the_drum(self):
        content.do_buy(self.cat, self.save, "drum key")
        self.underground()
        windings = self.d["windings"]
        content.do_use(self.save, "drum key")
        self.assertEqual(self.d["windings"], windings + content.DRUM_KEY_WINDINGS)
        self.assertEqual(self.held(), [])

    def test_you_cannot_use_what_you_are_not_carrying(self):
        self.underground()
        with self.assertRaises(ValueError):
            content.do_use(self.save, "oil flask")
        with self.assertRaises(ValueError):
            content.do_use(self.save, "a third lung")

    def test_you_cannot_use_kit_in_the_haven(self):
        content.do_buy(self.cat, self.save, "oil flask")
        with self.assertRaises(ValueError):
            content.do_use(self.save, "oil flask")
        self.assertEqual(self.held(), ["oil flask"])

    def test_kit_that_fires_itself_is_not_a_verb(self):
        content.do_buy(self.cat, self.save, "flash powder")
        self.underground()
        with self.assertRaises(ValueError):
            content.do_use(self.save, "flash powder")
        self.assertEqual(self.held(), ["flash powder"])

    def test_kit_and_relic_and_stances_survive_the_climb(self):
        content.do_buy(self.cat, self.save, "oil flask")
        content.do_learn(self.save, "brace")
        self.d["relic"] = dict(content.by_name(self.cat["relics"], "the pilgrim's bell"))
        self.underground()
        content.do_surface(self.cat, self.save)
        self.assertEqual(self.held(), ["oil flask"])
        self.assertEqual(self.d["relic"]["name"], "the pilgrim's bell")
        self.assertIn("brace", self.d["stances"])


class TestKitTriggers(unittest.TestCase):
    """Every trigger fires on its own condition, consumes the item, and does
    nothing at all when the item is not held."""

    def setUp(self):
        self.cat, self.save = TestExpeditionFlow().fresh_save()
        self.save["expedition"].update({"active": True, "depth": 2,
                                        "pending_site": {"name": "a test hall",
                                                         "enemies": ["glasshound"]}})
        self.d = self.save["delver"]

    def give(self, name):
        self.d["kit"].append(dict(content.by_name(self.cat["kit"], name)))

    def result(self, **over):
        d = self.d
        r = {"outcome": "victory", "hp": engine.hp_max(d), "grit": 1, "light": 5,
             "worst_blow": 0, "rounds": 3, "kills": [], "kit_used": [], "events": [],
             "menace_defeated": 1}
        r.update(over)
        return r

    def test_the_dressing_roll_opens_when_you_come_out_low(self):
        self.give("dressing roll")
        self.d["hp"] = engine.hp_max(self.d) // content.DRESSING_HP_FRAC
        low = self.d["hp"]
        lines = content.open_dressing(self.save, self.result(hp=low))
        self.assertTrue(lines)
        self.assertGreater(self.d["hp"], low)
        self.assertLessEqual(self.d["hp"] - low, 6)
        self.assertEqual(self.d["kit"], [])

    def test_the_dressing_roll_stays_rolled_when_you_walk_out_fine(self):
        self.give("dressing roll")
        self.d["hp"] = engine.hp_max(self.d)
        self.assertEqual(content.open_dressing(self.save, self.result()), [])
        self.assertEqual(len(self.d["kit"]), 1)

    def test_the_dressing_roll_is_no_use_to_the_dead(self):
        self.give("dressing roll")
        self.d["hp"] = 0
        self.d["alive"] = False
        self.assertEqual(content.open_dressing(self.save, self.result(outcome="down", hp=0)), [])
        self.assertEqual(len(self.d["kit"]), 1)

    def test_no_dressing_roll_no_bandage(self):
        self.d["hp"] = 1
        self.assertEqual(content.open_dressing(self.save, self.result(hp=1)), [])

    def test_what_the_fight_spent_leaves_the_satchel(self):
        self.give("flash powder")
        self.give("shard-hook rope")
        content.apply_fight_result(self.cat, self.save,
                                   self.result(outcome="retreated", kit_used=["flash"]))
        self.assertEqual([k["name"] for k in self.d["kit"]], ["shard-hook rope"])

    def test_the_tithe_pays_for_a_night_the_stores_cannot(self):
        self.save["expedition"]["pending_site"] = None
        self.give("tithe of oilbread")
        self.d["supply"] = 0
        self.d["hp"] = 1
        light = self.d["light"]
        lines = content.do_camp(self.cat, self.save)
        self.assertEqual(self.d["supply"], 0)
        self.assertEqual(self.d["light"], light - 1)  # light is paid as normal
        self.assertEqual(self.d["kit"], [])
        self.assertGreater(self.d["hp"], 1)
        self.assertTrue(any("oilbread" in line for line in lines))

    def test_without_the_tithe_an_empty_larder_is_an_empty_larder(self):
        self.save["expedition"]["pending_site"] = None
        self.d["supply"] = 0
        with self.assertRaises(ValueError):
            content.do_camp(self.cat, self.save)

    def test_the_tithe_is_still_only_one_night(self):
        self.save["expedition"]["pending_site"] = None
        self.give("tithe of oilbread")
        self.d["supply"] = 1
        self.d["hp"] = 1
        content.do_camp(self.cat, self.save)
        self.assertEqual(self.d["supply"], 1)  # the loaf went first
        self.d["hp"] = 1
        content.do_camp(self.cat, self.save)
        self.assertEqual(self.d["supply"], 0)


class TestRelicsFound(unittest.TestCase):
    """Salvage that refuses to be money, found where salvage is the point."""

    def setUp(self):
        self.cat, self.save = TestExpeditionFlow().fresh_save()
        self.save["expedition"].update({"active": True, "depth": 3})
        self.d = self.save["delver"]
        self.d["salvage"] = []

    def site(self, depth, names, kind="salvage", **over):
        s = {"depth": depth, "kind": kind, "name": "a shelf of drawers",
             "text": "drawers", "salvage": list(names), "rumor": "corners"}
        s.update(over)
        return s

    def enter(self, site):
        self.save["expedition"]["depth"] = max(1, site["depth"] - 1)
        return content._enter_site(self.cat, self.save, site, [])

    def carried(self):
        return [i["name"] for i in self.d["salvage"]]

    def test_the_roll_is_deep_only_and_rare_and_reaches_every_relic(self):
        seen = set()
        for depth in range(1, content.DEPTH_MAX + 1):
            found = [content.roll_relic(self.cat, depth, engine.rng_for("relic", depth, i))
                     for i in range(1500)]
            found = [r for r in found if r]
            if depth < content.RELIC_MIN_DEPTH:
                self.assertEqual(found, [], depth)
                continue
            rate = len(found) / 1500.0
            self.assertTrue(0.09 <= rate <= 0.15, (depth, rate))
            seen.update(r["name"] for r in found)
        self.assertEqual(seen, {r["name"] for r in self.cat["relics"]})

    def find_relic_counter(self, depth, names, start=0):
        """The first save counter at which this floor holds a relic."""
        for counter in range(start, start + 400):
            probe = json.loads(json.dumps(self.save))
            probe["counter"] = counter
            probe["delver"]["salvage"] = []
            probe["expedition"]["depth"] = max(1, depth - 1)
            content._enter_site(self.cat, probe, self.site(depth, names), [])
            if any(content.is_relic(self.cat, i["name"]) for i in probe["delver"]["salvage"]):
                return counter
        self.fail("no relic in 400 seeded floors at depth %d" % depth)

    def test_a_deep_salvage_floor_holds_a_relic_instead_of_its_first_find(self):
        names = ["watchman's eye", "annealed songbar"]
        self.save["counter"] = self.find_relic_counter(5, names)
        _, lines = self.enter(self.site(5, names))
        carried = self.carried()
        self.assertEqual(len(carried), 2)
        self.assertTrue(content.is_relic(self.cat, carried[0]))
        self.assertEqual(carried[1], "annealed songbar")  # only the FIRST find is displaced
        self.assertNotIn("watchman's eye", carried)
        self.assertTrue(any("This is not salvage" in line for line in lines))

    def test_the_easy_galleries_hold_none(self):
        for depth in (1, 2):
            for counter in range(300):
                self.save["counter"] = counter
                self.d["salvage"] = []
                self.enter(self.site(depth, ["vitric lens"]))
                self.assertEqual(self.carried(), ["vitric lens"])

    def test_a_strange_room_never_hands_you_one(self):
        entry = content.by_name(self.cat["strange"], "a delver's cache")
        for counter in range(300):
            self.save["counter"] = counter
            self.d["salvage"] = []
            self.enter(self.site(6, ["pane of true glass"], kind="strange",
                                 strange=entry["name"], effect=entry["effect"],
                                 strange_text=entry["text"]))
            for name in self.carried():
                self.assertFalse(content.is_relic(self.cat, name), name)

    def test_victory_loot_never_holds_one(self):
        exp = self.save["expedition"]
        exp["pending_site"] = {"name": "a test hall", "enemies": ["glasshound"]}
        for counter in range(200):
            self.save["counter"] = counter
            self.d["salvage"] = []
            self.d["alive"] = True
            exp["pending_site"] = {"name": "a test hall", "enemies": ["glasshound"]}
            content.apply_fight_result(self.cat, self.save, {
                "outcome": "victory", "hp": 10, "grit": 1, "light": 5, "worst_blow": 0,
                "rounds": 3, "kills": ["glasshound#1"], "kit_used": [], "events": [],
                "menace_defeated": 2})
            for name in self.carried():
                self.assertFalse(content.is_relic(self.cat, name), name)


class TestWearingARelic(unittest.TestCase):
    """One slot, no unequip, and the old one does not survive the new one."""

    def setUp(self):
        self.cat, self.save = TestExpeditionFlow().fresh_save()
        self.save["expedition"].update({"active": True, "depth": 4})
        self.d = self.save["delver"]
        self.d["salvage"] = []

    def carry(self, name):
        rec = content.by_name(self.cat["relics"], name)
        self.d["salvage"].append({"name": rec["name"], "value": rec["value"]})
        return rec

    def test_equipping_moves_it_out_of_the_satchel(self):
        rec = self.carry("the pilgrim's bell")
        content.do_equip(self.cat, self.save, rec["name"])
        self.assertEqual(self.d["salvage"], [])
        self.assertEqual(self.d["relic"], dict(rec))

    def test_equipping_over_one_destroys_it(self):
        self.carry("the pilgrim's bell")
        content.do_equip(self.cat, self.save, "the pilgrim's bell")
        self.carry("the tuning hammer")
        lines = content.do_equip(self.cat, self.save, "the tuning hammer")
        self.assertEqual(self.d["relic"]["name"], "the tuning hammer")
        self.assertEqual(self.d["salvage"], [])
        self.assertTrue(any("pilgrim's bell" in line for line in lines))

    def test_you_can_only_wear_what_you_carry(self):
        with self.assertRaises(ValueError):
            content.do_equip(self.cat, self.save, "the still lamp")
        with self.assertRaises(ValueError):
            content.do_equip(self.cat, self.save, "vitric lens")

    def test_not_with_something_watching_you_and_not_in_a_doorway(self):
        exp = self.save["expedition"]
        self.carry("the still lamp")
        exp["pending_site"] = {"name": "a hall", "enemies": ["glasshound"]}
        with self.assertRaises(ValueError):
            content.do_equip(self.cat, self.save, "the still lamp")
        exp["pending_site"] = None
        exp["paused_fight"] = {"delver": {"hp": 3}}
        with self.assertRaises(ValueError):
            content.do_equip(self.cat, self.save, "the still lamp")
        exp["paused_fight"] = None
        exp["fork"] = [{"depth": 5, "rumor": "quiet"}]
        with self.assertRaises(ValueError):
            content.do_equip(self.cat, self.save, "the still lamp")
        exp["fork"] = None
        content.do_equip(self.cat, self.save, "the still lamp")  # ... and then it works

    def test_an_unworn_relic_banks_for_its_value(self):
        rec = self.carry("the assayer's seal")
        self.save["wake"]["commission"] = {"item": "nothing anyone posted", "bonus": 0}
        self.d["knack"] = "cutter"  # keep the glasspicker bonus out of the sum
        content.do_surface(self.cat, self.save)
        self.assertEqual(self.save["wake"]["chits"], rec["value"])
        self.assertIsNone(self.d["relic"])

    def test_a_worn_relic_comes_up_with_you(self):
        self.carry("the tuning hammer")
        content.do_equip(self.cat, self.save, "the tuning hammer")
        content.do_surface(self.cat, self.save)
        self.assertEqual(self.d["relic"]["name"], "the tuning hammer")
        self.assertEqual(self.save["wake"]["chits"], 0)

    def test_the_still_lamp_shortens_the_clock_you_are_holding(self):
        self.d["light"] = engine.light_max(self.d)
        full = self.d["light"]
        self.carry("the still lamp")
        content.do_equip(self.cat, self.save, "the still lamp")
        self.assertEqual(engine.light_max(self.d), full - 2)
        self.assertEqual(self.d["light"], full - 2)

    def test_the_seal_triples_exactly_one_unit_and_winds_the_drum(self):
        item = content.by_name(self.cat["salvage"], self.save["wake"]["commission"]["item"])
        self.d["knack"] = "cutter"
        self.d["salvage"] = [{"name": item["name"], "value": item["value"]} for _ in range(2)]
        self.carry("the assayer's seal")
        seal = content.by_name(self.cat["relics"], "the assayer's seal")
        content.do_equip(self.cat, self.save, seal["name"])
        content.do_surface(self.cat, self.save)
        # two units carried: one pays triple, the other pays the list price
        self.assertEqual(self.save["wake"]["chits"], 4 * item["value"])
        self.assertEqual(self.d["windings"], engine.windings_max(self.d))
        self.assertEqual(self.d["windings"], 1 + self.d["stats"]["craft"] + 1)


class TestLearningAStance(unittest.TestCase):
    """Bought knowledge: chits, not stat gates."""

    def setUp(self):
        self.cat, self.save = TestExpeditionFlow().fresh_save()
        self.d = self.save["delver"]

    def test_the_haven_teaches_two_stances(self):
        self.assertEqual(sorted(content.LEARNABLE_STANCES), ["brace", "read"])
        for stance in content.LEARNABLE_STANCES:
            self.assertIn(stance, engine.STANCES)
            self.assertIn(stance, content.STANCE_TEXT)

    def test_learning_costs_chits_and_lasts(self):
        self.save["wake"]["chits"] = content.STANCE_COST + 1
        content.do_learn(self.save, "read")
        self.assertIn("read", self.d["stances"])
        self.assertEqual(self.save["wake"]["chits"], 1)
        with self.assertRaises(ValueError):
            content.do_learn(self.save, "read")

    def test_short_of_chits_is_short_of_a_stance(self):
        self.save["wake"]["chits"] = content.STANCE_COST - 1
        with self.assertRaises(ValueError):
            content.do_learn(self.save, "brace")
        self.assertNotIn("brace", self.d["stances"])

    def test_you_learn_it_above_ground(self):
        self.save["wake"]["chits"] = 100
        self.save["expedition"]["active"] = True
        with self.assertRaises(ValueError):
            content.do_learn(self.save, "brace")

    def test_nobody_teaches_what_is_not_on_offer(self):
        self.save["wake"]["chits"] = 100
        for stance in ("measure", "flying kick"):
            with self.assertRaises(ValueError):
                content.do_learn(self.save, stance)

    def test_a_fight_refuses_a_stance_you_have_not_learned(self):
        exp = self.save["expedition"]
        exp.update({"active": True, "depth": 2,
                    "pending_site": {"name": "a test hall", "enemies": ["glasshound"]}})
        with self.assertRaises(ValueError):
            content.start_pending_fight(self.cat, self.save, "brace")
        self.save["wake"]["chits"] = 100
        self.save["expedition"]["active"] = False
        content.do_learn(self.save, "brace")
        self.save["expedition"]["active"] = True
        content.start_pending_fight(self.cat, self.save, "brace")  # ... and now it does not

    def test_the_pause_offers_only_what_you_know(self):
        save = self.save
        exp = save["expedition"]
        for _ in range(80):
            if exp["pending_site"] and exp["pending_site"].get("enemies"):
                paused, _ = content.start_pending_fight(self.cat, save, "measure")
                if paused:
                    break
                if not save["delver"]["alive"]:
                    self.fail("died before a pause")
                exp["depth"] = 1
                continue
            _delve_through(self.cat, save)
        else:
            self.fail("no pause in 80 delves")
        opts = set(engine.pause_options(exp["paused_fight"]))
        self.assertEqual(opts & set(engine.STANCES), set(engine.BASE_STANCES) - {"measure"})

    def test_the_drum_answers_about_lines_you_can_take(self):
        save = self.save
        exp = save["expedition"]
        for _ in range(60):
            _delve_through(self.cat, save)
            if exp["pending_site"] and exp["pending_site"].get("enemies"):
                break
            exp["depth"] = 1
        else:
            self.fail("no encounter in 60 delves")
        save["delver"]["windings"] = 5
        labels = {r["label"].split(" / ")[0] for r in content.simulate_odds(self.cat, save, 3)}
        self.assertEqual(labels, set(engine.BASE_STANCES))

    def test_the_v6_save_shape_is_complete(self):
        cat, save = TestExpeditionFlow().fresh_save()
        d = save["delver"]
        self.assertEqual(save["version"], 6)
        self.assertEqual(engine.SAVE_VERSION, 6)
        self.assertEqual(d["kit"], [])
        self.assertIsNone(d["relic"])
        self.assertEqual(d["stances"], list(engine.BASE_STANCES))
        self.assertEqual(json.loads(json.dumps(save)), save)

    def test_a_delver_who_cannot_hold_kit_is_a_bug_not_a_case(self):
        """No migration, ever: the shapes below cannot be produced, so the
        readers raise instead of pretending."""
        for key in ("kit", "relic", "stances"):
            broken = json.loads(json.dumps(self.save))["delver"]
            del broken[key]
            with self.assertRaises(KeyError):
                engine._combatant_from_delver(broken, "measure", False)


if __name__ == "__main__":
    unittest.main()
