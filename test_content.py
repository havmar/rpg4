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
             "worst_blow": 0, "rounds": 3, "kills": [], "events": [], "menace_defeated": 1}
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
        lines = content.take_salvage(self.d, "a better thing", 9)
        self.assertEqual(len(self.d["salvage"]), cap)
        self.assertIn("a better thing", [i["name"] for i in self.d["salvage"]])
        self.assertNotIn(2, [i["value"] for i in self.d["salvage"]])
        self.assertIn("drop", lines[0])

    def test_the_cheapest_find_is_left_behind(self):
        cap = engine.satchel_cap(self.d)
        self.fill(*[5] * cap)
        lines = content.take_salvage(self.d, "a worse thing", 3)
        self.assertEqual(len(self.d["salvage"]), cap)
        self.assertNotIn("a worse thing", [i["name"] for i in self.d["salvage"]])
        self.assertIn("stays where it lies", lines[0])


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
            old_save, old_ui = session.SAVE_PATH, pages.UI_DIR
            session.SAVE_PATH = os.path.join(tmp, "save.json")
            pages.UI_DIR = os.path.join(tmp, "ui")
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    session.main(["new", "--seed", "31337"])
                with open(session.SAVE_PATH, encoding="utf-8") as f:
                    save = json.load(f)
                with open(os.path.join(pages.UI_DIR, "delver.txt"), encoding="utf-8") as f:
                    sheet = f.read()
            finally:
                session.SAVE_PATH, pages.UI_DIR = old_save, old_ui
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
        self.assertEqual(save["version"], 4)
        for key in ("fork", "declined"):
            self.assertIn(key, save["expedition"])
        blob = json.loads(json.dumps(save))
        self.assertEqual(blob, save)

    def test_the_map_remembers_what_you_did_not_open(self):
        import pages
        cat, save = self.forked()
        content.advance_delve(cat, save, passage=1)
        with tempfile.TemporaryDirectory() as tmp:
            old, pages.UI_DIR = pages.UI_DIR, tmp
            try:
                pages.write_map(save)
                with open(os.path.join(tmp, "map.txt"), encoding="utf-8") as f:
                    text = f.read()
            finally:
                pages.UI_DIR = old
        for entry in save["expedition"]["declined"]:
            self.assertIn("..unopened: %s" % entry["rumor"], text)


if __name__ == "__main__":
    unittest.main()
