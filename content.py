"""UNDERSTORY content layer: catalogs, validation, encounter/site generation.

Catalogs are versioned JSON under catalogs/. Every load validates; authored
censuses are pinned so silent content drift fails loudly. The engine stays
generic; everything that knows names lives here.
"""

import copy
import json
import os

import engine

CATALOG_VERSION = 1
CATALOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalogs")

# pinned censuses: change these ON PURPOSE, in the same commit as the content
CENSUS = {
    "backgrounds": 6,
    "enemies": 10,
    "weapons": 6,
    "armors": 4,
    "salvage": 10,
    "strange": 10,
    "sites": 12,
    "marks": 10,
    "names": 40,  # given + family together
}

# names are two plain string lists, not records; validated on their own terms
NAME_LISTS = ("given", "family")

ALLOWED_TRAITS = {"swift", "lurker", "brittle", "relentless", "armored", "pack"}
SITE_KINDS = ("encounter", "salvage", "strange", "breather")
DEPTH_MAX = 6
# locality rule: generic templates may not name fixed places
FORBIDDEN_IN_TEMPLATES = ("Wake",)

SITE_KIND_WEIGHTS = [("encounter", 50), ("salvage", 25), ("strange", 15), ("breather", 10)]

# What a passage tells you before you take it. Rumors are honest, because
# the senses are honest -- but the world is not obliged to be audible. A
# breather and an all-lurker ambush give the identical line, on purpose:
# quiet is either rest or teeth, and pricing that is the whole feature.
QUIET_RUMOR = "Quiet. Your own lamp is the loudest thing in it."
SALVAGE_RUMORS = [
    "A glint where nothing should be shining.",
    "Still air over the smell of oil that has not burned in an age.",
    "Shapes with corners -- made things, holding their arrangement.",
]
# single throat, two passages, three passages
FORK_SHAPES = [(1, 20), (2, 65), (3, 15)]
ORDINALS = ("first", "second", "third")

_FIELDS = {
    "backgrounds": {"name", "blurb", "priorities", "knack", "knack_text", "weapon", "armor"},
    "enemies": {"name", "blurb", "rumor", "hp", "atk", "guard", "soak", "dmg",
                "traits", "menace", "dread", "depth"},
    "weapons": {"name", "dmg", "acc", "value", "blurb"},
    "armors": {"name", "guard", "soak", "value", "heavy", "blurb"},
    "salvage": {"name", "value", "depth", "blurb"},
    "strange": {"name", "effect", "text", "rumor"},
    "sites": {"name", "kind", "depth", "text"},
    "marks": {"name", "effect", "text"},
}

# declared-optional authored keys: read with a default, never a damage shim.
# A lurker makes no sound, so it must carry no rumor at all.
_OPTIONAL_FIELDS = {"enemies": {"rumor"}}

# a fight this hard leaves a mark; see engine.MARK_EFFECTS for what they do
MARK_BLOW = 6
MARK_HP_FRAC = 3  # ... or coming out at or under a third of your hp


class CatalogError(ValueError):
    pass


def _check_records(records, section):
    fields = _FIELDS[section]
    optional = _OPTIONAL_FIELDS.get(section, set())
    names = []
    for rec in records:
        missing = fields - set(rec) - optional
        extra = set(rec) - fields
        if missing:
            raise CatalogError("%s %r missing fields %s" % (section, rec.get("name"), sorted(missing)))
        if extra:
            raise CatalogError("%s %r has unknown fields %s" % (section, rec.get("name"), sorted(extra)))
        names.append(rec["name"])
        for key in ("blurb", "text", "rumor"):
            if key in rec:
                for word in FORBIDDEN_IN_TEMPLATES:
                    if word in rec[key]:
                        raise CatalogError("%s %r violates locality: names %r" % (section, rec["name"], word))
        if "depth" in rec:
            d = rec["depth"]
            if not (isinstance(d, list) and len(d) == 2 and 1 <= d[0] <= d[1] <= DEPTH_MAX):
                raise CatalogError("%s %r has bad depth band %r" % (section, rec["name"], d))
        if "dmg" in rec:
            try:
                engine.max_dice(rec["dmg"])
            except ValueError:
                raise CatalogError("%s %r has bad dice spec %r" % (section, rec["name"], rec["dmg"]))
    if len(set(names)) != len(names):
        raise CatalogError("%s has duplicate names" % section)
    if len(records) != CENSUS[section]:
        raise CatalogError("%s census is %d, pinned %d" % (section, len(records), CENSUS[section]))


def _check_names(names):
    total = 0
    for part in NAME_LISTS:
        pool = names[part]
        if not all(isinstance(nm, str) and nm for nm in pool):
            raise CatalogError("names %s holds something that is not a name" % part)
        if len(set(pool)) != len(pool):
            raise CatalogError("names %s has duplicates" % part)
        for nm in pool:
            for word in FORBIDDEN_IN_TEMPLATES:
                if word in nm:
                    raise CatalogError("names %s violates locality: %r names %r" % (part, nm, word))
        total += len(pool)
    if total != CENSUS["names"]:
        raise CatalogError("names census is %d, pinned %d" % (total, CENSUS["names"]))


def validate_catalog(cat):
    """Full lint of the merged catalog dict. Raises CatalogError."""
    for section in CENSUS:
        if section == "names":
            _check_names(cat["names"])
            continue
        _check_records(cat[section], section)
    weapon_names = {w["name"] for w in cat["weapons"]}
    armor_names = {a["name"] for a in cat["armors"]}
    for b in cat["backgrounds"]:
        if sorted(b["priorities"]) != sorted(engine.STATS):
            raise CatalogError("background %r priorities not a permutation of stats" % b["name"])
        if b["weapon"] not in weapon_names or b["armor"] not in armor_names:
            raise CatalogError("background %r references unknown gear" % b["name"])
    for e in cat["enemies"]:
        if not set(e["traits"]) <= ALLOWED_TRAITS:
            raise CatalogError("enemy %r has unknown traits %s" % (e["name"], sorted(set(e["traits"]) - ALLOWED_TRAITS)))
        if e["menace"] < 1:
            raise CatalogError("enemy %r has menace < 1" % e["name"])
        lurker = "lurker" in e["traits"]
        if lurker and "rumor" in e:
            raise CatalogError("enemy %r is a lurker: it makes no sound and must carry no rumor"
                               % e["name"])
        if not lurker and "rumor" not in e:
            raise CatalogError("enemy %r has no rumor" % e["name"])
    for s in cat["strange"]:
        if s["effect"] not in engine.STRANGE_EFFECTS:
            raise CatalogError("strange %r has unknown effect %r" % (s["name"], s["effect"]))
    for m in cat["marks"]:
        if m["effect"] not in engine.MARK_EFFECTS:
            raise CatalogError("mark %r has unknown effect %r" % (m["name"], m["effect"]))
    for site in cat["sites"]:
        if site["kind"] not in SITE_KINDS:
            raise CatalogError("site %r has unknown kind %r" % (site["name"], site["kind"]))
    for kind in SITE_KINDS:
        for depth in range(1, DEPTH_MAX + 1):
            if not [s for s in cat["sites"] if s["kind"] == kind and s["depth"][0] <= depth <= s["depth"][1]]:
                raise CatalogError("no %s site template covers depth %d" % (kind, depth))
    for kind, section in (("encounter", "enemies"), ("salvage", "salvage")):
        for depth in range(1, DEPTH_MAX + 1):
            if not [r for r in cat[section] if r["depth"][0] <= depth <= r["depth"][1]]:
                raise CatalogError("no %s entry covers depth %d" % (section, depth))
    return cat


def load_catalog():
    """Load and validate all catalog files into one dict."""
    cat = {}
    for fname, sections in (
        ("backgrounds.json", ["backgrounds"]),
        ("enemies.json", ["enemies"]),
        ("gear.json", ["weapons", "armors"]),
        ("salvage.json", ["salvage"]),
        ("strange.json", ["strange"]),
        ("sites.json", ["sites"]),
        ("marks.json", ["marks"]),
        ("names.json", list(NAME_LISTS)),
    ):
        with open(os.path.join(CATALOG_DIR, fname), "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != CATALOG_VERSION:
            raise CatalogError("%s: version %r, expected %d" % (fname, data.get("version"), CATALOG_VERSION))
        for section in sections:
            if fname == "names.json":
                cat.setdefault("names", {})[section] = data[section]
            else:
                cat[section] = data[section]
    return validate_catalog(cat)


def by_name(records, name):
    for rec in records:
        if rec["name"] == name:
            return rec
    raise KeyError(name)


# ------------------------------------------------------------- generators

def _eligible(records, depth):
    return [r for r in records if r["depth"][0] <= depth <= r["depth"][1]]


def build_encounter(cat, depth, rng):
    """Pick an enemy group for this depth. Returns list of enemy spec dicts."""
    pool = _eligible(cat["enemies"], depth)
    budget = max(1, 1 + depth + rng.randint(-1, 1))
    group = []
    while True:
        affordable = [e for e in pool if e["menace"] <= budget]
        if not affordable:
            break
        pick = rng.choice(affordable)
        count = (2 + (1 if rng.random() < 0.5 else 0)) if "pack" in pick["traits"] else 1
        count = min(count, max(1, budget // pick["menace"]))
        for _ in range(count):
            group.append(pick)
            budget -= pick["menace"]
    if not group:
        group.append(min(pool, key=lambda e: (e["menace"], e["name"])))
    return group


def roll_salvage(cat, depth, rng):
    return rng.choice(_eligible(cat["salvage"], depth))


def rumor_for(cat, site, rng):
    """The loudest honest thing about a site, heard from outside it."""
    if site["kind"] == "encounter":
        specs = [by_name(cat["enemies"], n) for n in site["enemies"]]
        heard = [e for e in specs if "lurker" not in e["traits"]]
        if not heard:
            return QUIET_RUMOR
        return sorted(heard, key=lambda e: (-e["menace"], e["name"]))[0]["rumor"]
    if site["kind"] == "breather":
        return QUIET_RUMOR
    if site["kind"] == "salvage":
        return rng.choice(SALVAGE_RUMORS)
    return by_name(cat["strange"], site["strange"])["rumor"]


def generate_site(cat, depth, rng, exclude=()):
    """One site at this depth: template + payload + rumor. Deterministic
    per rng.

    `exclude` names templates already used this expedition; the Understory
    does not repeat itself until it runs out of rooms.
    """
    total = sum(w for _, w in SITE_KIND_WEIGHTS)
    pick = rng.randint(1, total)
    for kind, weight in SITE_KIND_WEIGHTS:
        pick -= weight
        if pick <= 0:
            break
    pool = [s for s in cat["sites"] if s["kind"] == kind
            and s["depth"][0] <= depth <= s["depth"][1]]
    fresh = [s for s in pool if s["name"] not in exclude]
    template = rng.choice(fresh or pool)
    site = {"depth": depth, "kind": kind, "name": template["name"], "text": template["text"]}
    if kind == "encounter":
        site["enemies"] = [e["name"] for e in build_encounter(cat, depth, rng)]
    elif kind == "salvage":
        items = [roll_salvage(cat, depth, rng)]
        if rng.random() < 0.4:
            items.append(roll_salvage(cat, depth, rng))
        site["salvage"] = [i["name"] for i in items]
    elif kind == "strange":
        strange = rng.choice(cat["strange"])
        site["strange"] = strange["name"]
        site["effect"] = strange["effect"]
        site["strange_text"] = strange["text"]
        if strange["effect"] in ("found_cache", "murmur_market"):
            site["salvage"] = [roll_salvage(cat, depth, rng)["name"]]
    site["rumor"] = rumor_for(cat, site, rng)
    return site


BASE_ARRAY = [3, 3, 2, 2, 2]


def roll_delver(cat, world_seed):
    """The stranger the world deals you. Deterministic in the world seed.

    No pick-of-three: a choice between three unplayed strangers is a fake
    one. The first real decision of a playthrough is what to do about
    depth 1.
    """
    rng = engine.rng_for(world_seed, "delver")
    name = "%s %s" % (rng.choice(cat["names"]["given"]), rng.choice(cat["names"]["family"]))
    bg = rng.choice(sorted(cat["backgrounds"], key=lambda b: b["name"]))
    stats = {}
    for stat, val in zip(bg["priorities"], BASE_ARRAY):
        stats[stat] = val
    stats[rng.choice(sorted(engine.STATS))] += 1
    return {
        "name": name,
        "background": bg["name"],
        "blurb": bg["blurb"],
        "knack": bg["knack"],
        "knack_text": bg["knack_text"],
        "stats": stats,
        "weapon": dict(by_name(cat["weapons"], bg["weapon"])),
        "armor": dict(by_name(cat["armors"], bg["armor"])),
    }


# ---------------------------------------------------------- expedition flow
# Game-flow rules that need the catalogs live here so session.py stays a
# thin driver and engine.py stays generic.

SUPPLY_START = 3
TRAIN_COST_PER_LEVEL = 15
STAT_CAP = 6
SCRAP = "scrap glass and fittings"
ODDS_POLICIES = ("fight_on", "surge", "withdraw")


def new_delver(candidate):
    d = dict(candidate)
    d["marks"] = []  # before the derived readers: they all consult it
    d["hp"] = engine.hp_max(d)
    d["grit"] = engine.grit_max(d)
    d["light"] = engine.light_max(d)
    d["windings"] = engine.windings_max(d)
    d["supply"] = SUPPLY_START
    d["salvage"] = []
    d["alive"] = True
    return d


def new_save(cat, world_seed):
    """A whole campaign in one shape. There is no other shape and no
    migration path to it (Charter §6)."""
    delver = new_delver(roll_delver(cat, world_seed))
    save = {
        "version": engine.SAVE_VERSION,
        "world_seed": world_seed,
        "counter": 0,
        "odds_counter": 0,
        "delver": delver,
        "expedition": {"active": False, "depth": 0, "sites": [], "pending_site": None,
                       "paused_fight": None, "free_delve": False,
                       "fork": None, "declined": []},
        "wake": {"chits": 0, "day": 1, "expeditions": 0, "commission": None},
        "history": ["Day 1: %s, %s, went down the great mouth."
                    % (delver["name"], delver["background"])],
        "last_fight": None,
    }
    save["wake"]["commission"] = draw_commission(cat, save)
    return save


# ------------------------------------------------------------- the satchel
# A hard carry limit is the turnaround the descent never had: "my bag is
# full" is a reason to climb that is not a punishment.

def take_salvage(delver, name, value):
    """Put a find in the satchel, or decide what it displaces. Returns lines."""
    if name == SCRAP:
        for carried in delver["salvage"]:
            if carried["name"] == SCRAP:  # scrap merges; it never costs a second slot
                carried["value"] += value
                return ["Scrap goes in with the rest (the lot is worth %d)." % carried["value"]]
    cap = engine.satchel_cap(delver)
    if len(delver["salvage"]) < cap:
        delver["salvage"].append({"name": name, "value": value})
        return ["Salvage taken: %s (worth %d) [satchel %d/%d]."
                % (name, value, len(delver["salvage"]), cap)]
    cheapest = min(delver["salvage"], key=lambda i: (i["value"], i["name"]))
    if value > cheapest["value"]:
        delver["salvage"].remove(cheapest)
        delver["salvage"].append({"name": name, "value": value})
        return ["The satchel is full: you drop %s (worth %d) and take %s (worth %d)."
                % (cheapest["name"], cheapest["value"], name, value)]
    return ["The satchel is full; %s (worth %d) stays where it lies." % (name, value)]


# ---------------------------------------------------------- the commission
# Wake's standing order: the reason surfacing is a payday and not a reset.

def draw_commission(cat, save):
    """The day's posting at the assay-house. A filled one pays double."""
    rng = _evt_rng(save)
    item = rng.choice(cat["salvage"])
    return {"item": item["name"], "bonus": item["value"]}


def _darkness(delver):
    return delver["light"] <= 0


def _next_depth(exp):
    """Where a step down would land. The sealed floor holds at DEPTH_MAX."""
    return exp["depth"] if exp["depth"] >= DEPTH_MAX else exp["depth"] + 1


def _draw_fork_shape(rng):
    total = sum(w for _, w in FORK_SHAPES)
    pick = rng.randint(1, total)
    for shape, weight in FORK_SHAPES:
        pick -= weight
        if pick <= 0:
            return shape
    return FORK_SHAPES[-1][0]


def fork_lines(fork):
    lines = ["The way down splits %d ways. This is what you can hear:" % len(fork)]
    for i, passage in enumerate(fork, 1):
        lines.append("  %d) %s" % (i, passage["rumor"]))
    return lines


def advance_delve(cat, save, passage=None):
    """Offer the fork, or take a passage down. Returns (site, lines).

    `site` is None when the way splits: the fork is left pending and the
    rumors are in `lines`. Nothing is spent at a split -- a rumor is only
    what you hear from where you already stand. The unchosen passages are
    gone once you move; the Understory does not hold doors open.
    """
    exp = save["expedition"]
    if exp["paused_fight"] or (exp["pending_site"] and exp["pending_site"].get("enemies")):
        raise ValueError("there is a fight in front of you; resolve it first")
    lines = []
    if not exp["active"]:
        exp.update({"active": True, "depth": 0, "sites": [], "fork": None, "declined": []})
        lines.append("You go down through the great mouth. The expedition begins.")
    if exp["fork"]:
        if passage is None:  # a reprint costs nothing and decides nothing
            return None, lines + fork_lines(exp["fork"])
        if not 1 <= passage <= len(exp["fork"]):
            raise ValueError("there are only %d passages here" % len(exp["fork"]))
        site = exp["fork"][passage - 1]
        for i, other in enumerate(exp["fork"], 1):
            if i != passage:
                exp["declined"].append({"depth": other["depth"], "rumor": other["rumor"]})
        exp["fork"] = None
        lines.append("You take the %s passage. The others close behind you."
                     % ORDINALS[passage - 1])
    else:
        if passage is not None:
            raise ValueError("the way is single here")
        rng = _evt_rng(save)
        depth = _next_depth(exp)
        used = {s["name"] for s in exp["sites"]}
        # the mouth is known ground: the first delve never stalls at a fork
        shape = 1 if not exp["sites"] else _draw_fork_shape(rng)
        if shape > 1:
            fork = []
            for _ in range(shape):
                fork.append(generate_site(cat, depth, rng,
                                          exclude=used | {p["name"] for p in fork}))
            exp["fork"] = fork
            return None, lines + fork_lines(fork)
        lines.append("The way down is single here.")
        site = generate_site(cat, depth, rng, exclude=used)
    return _enter_site(cat, save, site, lines)


def _enter_site(cat, save, site, lines):
    """Spend the light, take the step, and resolve what is waiting."""
    delver = save["delver"]
    exp = save["expedition"]
    if exp["depth"] >= DEPTH_MAX:
        lines.append("Below this the floor is one sealed pane, fathoms thick. "
                     "The Understory goes deeper; you, today, do not.")
    exp["depth"] = site["depth"]
    if exp.get("free_delve"):
        exp["free_delve"] = False
        cost = 0
        lines.append("The old stairs hold: no light spent.")
    else:
        cost = 1
    if engine.has_mark(delver, "light_leak"):
        cost += 1
        lines.append("Lamp-shy: the flame takes an extra measure on the way down.")
    delver["light"] = max(0, delver["light"] - cost)
    if _darkness(delver):
        lines.append("The lamp is dry. You move in the dark now.")
    exp["sites"].append({"depth": site["depth"], "kind": site["kind"], "name": site["name"]})
    rng = _evt_rng(save)
    if site["kind"] == "encounter":
        exp["pending_site"] = site
        lines.append("Something is here: " + ", ".join(site["enemies"]) + ".")
    elif site["kind"] == "salvage":
        for name in site["salvage"]:
            item = by_name(cat["salvage"], name)
            lines.extend(take_salvage(delver, item["name"], item["value"]))
        exp["pending_site"] = None
    elif site["kind"] == "strange":
        lines.extend(engine.apply_strange(delver, exp, site["effect"], rng))
        for name in site.get("salvage", []):
            item = by_name(cat["salvage"], name)
            lines.extend(take_salvage(delver, item["name"], item["value"]))
        exp["pending_site"] = None
    else:  # breather
        if engine.has_mark(delver, "breather_numb"):
            lines.append("A quiet room. You sit in it and get nothing back from it.")
        elif delver["grit"] < engine.grit_max(delver):
            delver["grit"] += 1
            lines.append("A moment of quiet; you gather yourself: +1 grit.")
        exp["pending_site"] = None
    return site, lines


def start_pending_fight(cat, save, stance):
    """Resolve (or pause) the pending encounter. Returns (paused, lines)."""
    exp = save["expedition"]
    site = exp["pending_site"]
    if not site or not site.get("enemies"):
        raise ValueError("no fight is pending")
    specs = [by_name(cat["enemies"], n) for n in site["enemies"]]
    seed = engine.child_seed(save["world_seed"], "fight", save["counter"])
    save["counter"] += 1
    state, result = engine.start_fight(save["delver"], specs, stance,
                                       seed, darkness=_darkness(save["delver"]))
    if result is None:
        exp["paused_fight"] = state
        return True, engine.fight_summary(state["events"])
    return False, apply_fight_result(cat, save, result)


def resume_paused_fight(cat, save, choice):
    exp = save["expedition"]
    if not exp["paused_fight"]:
        raise ValueError("no paused fight")
    result = engine.resume_fight(exp["paused_fight"], choice)
    exp["paused_fight"] = None
    return apply_fight_result(cat, save, result)


def apply_fight_result(cat, save, result):
    delver = save["delver"]
    exp = save["expedition"]
    site = exp["pending_site"]
    delver["hp"] = result["hp"]
    delver["grit"] = result["grit"]
    delver["light"] = result["light"]
    save["last_fight"] = {"outcome": result["outcome"], "site": site["name"],
                          "depth": exp["depth"], "events": result["events"]}
    lines = engine.fight_summary(result["events"])
    if result["outcome"] == "victory":
        exp["pending_site"] = None
        scrap = 2 * result["menace_defeated"]
        lines.append("You strip the field: scrap worth %d." % scrap)
        lines.extend(take_salvage(delver, SCRAP, scrap))
        rng = _evt_rng(save)
        if rng.random() < 0.7:
            item = roll_salvage(cat, exp["depth"], rng)
            lines.append("Among the wreckage: %s (worth %d)." % (item["name"], item["value"]))
            lines.extend(take_salvage(delver, item["name"], item["value"]))
        save["history"].append("Day %d, depth %d: cleared %s (%s)."
                               % (save["wake"]["day"], exp["depth"], site["name"],
                                  ", ".join(site["enemies"])))
    elif result["outcome"] == "retreated":
        exp["pending_site"] = None
        exp["depth"] = max(0, exp["depth"] - 1)
        lines.append("You fall back to the previous gallery (depth %d)." % exp["depth"])
        save["history"].append("Day %d: retreated from %s at depth %d."
                               % (save["wake"]["day"], site["name"], exp["depth"] + 1))
    else:  # down
        delver["alive"] = False
        lines.append("The expedition ends here. The Understory keeps what it takes.")
        save["history"].append("Day %d: %s went down at depth %d, in %s. The Ledger remembers."
                               % (save["wake"]["day"], delver["name"], exp["depth"], site["name"]))
    lines.extend(gain_mark(cat, save, result))
    return lines


def gain_mark(cat, save, result):
    """A fight that nearly had you leaves something behind. Returns lines."""
    delver = save["delver"]
    if result["outcome"] not in ("victory", "retreated"):
        return []
    hard = (result["worst_blow"] >= MARK_BLOW
            or result["hp"] * MARK_HP_FRAC <= engine.hp_max(delver))
    if not hard or len(delver["marks"]) >= engine.MARK_CAP:
        return []
    held = {m["name"] for m in delver["marks"]}
    pool = [m for m in cat["marks"] if m["name"] not in held]
    rng = engine.rng_for(save["world_seed"], "mark", save["counter"])
    save["counter"] += 1
    mark = dict(rng.choice(pool))
    delver["marks"].append(mark)
    delver["hp"] = min(delver["hp"], engine.hp_max(delver))
    return ["You come away with something: %s -- %s" % (mark["name"], mark["text"])]


def do_camp(cat, save):
    delver = save["delver"]
    exp = save["expedition"]
    if not exp["active"]:
        raise ValueError("you camp in the deep, not in Wake")
    if exp["paused_fight"] or (exp["pending_site"] and exp["pending_site"].get("enemies")):
        raise ValueError("you cannot camp with something watching you; resolve the fight")
    if delver["supply"] < 1:
        raise ValueError("no supply left to camp on")
    rng = _evt_rng(save)
    delver["supply"] -= 1
    delver["light"] = max(0, delver["light"] - 1)
    heal = engine.camp_heal(delver, rng)
    delver["hp"] = min(engine.hp_max(delver), delver["hp"] + heal)
    lines = ["You camp cold behind a shard-wall: +%d hp, grit restored, -1 supply, -1 light." % heal]
    if delver["marks"]:
        mark = delver["marks"].pop()
        lines.append("Dressed and splinted by lamplight: %s is behind you." % mark["name"])
    delver["grit"] = engine.grit_max(delver)
    return lines


def do_surface(cat, save):
    delver = save["delver"]
    exp = save["expedition"]
    if not exp["active"]:
        raise ValueError("you are already in Wake")
    if exp["paused_fight"] or (exp["pending_site"] and exp["pending_site"].get("enemies")):
        raise ValueError("you cannot surface mid-fight; resolve it (or withdraw at the pause)")
    rng = _evt_rng(save)
    lines = []
    cost = (exp["depth"] + 2) // 3
    short = max(0, cost - delver["light"])
    delver["light"] = max(0, delver["light"] - cost)
    if short:
        dmg = sum(engine.roll_dice("1d6", rng) for _ in range(short))
        delver["hp"] = max(1, delver["hp"] - dmg)
        lines.append("The climb outruns the lamp: %d hp lost to the dark on the way up." % dmg)
    banked = 0
    bonus = 0
    for item in delver["salvage"]:
        banked += item["value"]
        if delver["knack"] == "glasspicker" and item["name"] != SCRAP:
            bonus += 1
    banked += bonus
    commission = save["wake"]["commission"]
    filled = next((i for i in delver["salvage"] if i["name"] == commission["item"]), None)
    if filled:
        banked += commission["bonus"]
        lines.append("The standing order is filled: one %s against the posting, +%d chits."
                     % (commission["item"], commission["bonus"]))
    delver["salvage"] = []
    save["wake"]["chits"] += banked
    save["wake"]["day"] += 1
    save["wake"]["expeditions"] += 1
    reached = exp["depth"]
    exp.update({"active": False, "depth": 0, "pending_site": None, "paused_fight": None,
                "free_delve": False, "fork": None, "declined": []})
    delver["hp"] = engine.hp_max(delver)
    delver["grit"] = engine.grit_max(delver)
    delver["light"] = engine.light_max(delver)
    delver["windings"] = engine.windings_max(delver)
    delver["supply"] = SUPPLY_START
    if delver["marks"]:
        lines.append("A night above ground and a surgeon's hour: %s, all of it gone."
                     % ", ".join(m["name"] for m in delver["marks"]))
        delver["marks"] = []
    lines.append("You surface into the red light of the Ember. Banked %d chits (total %d)."
                 % (banked, save["wake"]["chits"]))
    lines.append("A day of rest in Wake: healed, refit, ready.")
    save["history"].append("Day %d: surfaced from depth %d, banked %d chits."
                           % (save["wake"]["day"], reached, banked))
    if filled:
        save["history"].append("Day %d: filled the assay-house order for %s."
                               % (save["wake"]["day"], commission["item"]))
    save["wake"]["commission"] = draw_commission(cat, save)
    lines.append("Today's posting at the assay-house: %s, paying double (%d over the list)."
                 % (save["wake"]["commission"]["item"], save["wake"]["commission"]["bonus"]))
    return lines


# ------------------------------------------------------- the reckoning drum
# Odds as an object in the world, with a meter on it. The integrity rule is
# constitutional for this feature: RESEED, NEVER PEEK. Every sample draws
# from a dedicated seed path, so asking the drum can neither change nor
# reveal the fight that is actually waiting.

def simulate_odds(cat, save, n):
    """Wind the drum once and read it. Returns a list of rows."""
    delver = save["delver"]
    exp = save["expedition"]
    if delver["windings"] < 1:
        raise ValueError("the drum is spent; only a night above ground winds it again")
    if exp["paused_fight"]:
        rows = _odds_paused(save, n)
    elif exp["pending_site"] and exp["pending_site"].get("enemies"):
        rows = _odds_pending(cat, save, n)
    else:
        raise ValueError("the drum only hears the fight in front of you, and there is none")
    delver["windings"] -= 1
    save["odds_counter"] += 1
    return rows


def _odds_row(label, results, start_light):
    n = len(results)
    wins = [r for r in results if r["outcome"] == "victory"]
    return {
        "label": label,
        "n": n,
        "victory": 100.0 * len(wins) / n,
        "retreated": 100.0 * sum(r["outcome"] == "retreated" for r in results) / n,
        "down": 100.0 * sum(r["outcome"] == "down" for r in results) / n,
        "rounds": sum(r["rounds"] for r in results) / n,
        "hp_on_win": (sum(r["hp"] for r in wins) / len(wins)) if wins else 0.0,
        "light": sum(start_light - r["light"] for r in results) / n,
    }


def _odds_seed(save, row, i):
    return engine.child_seed(save["world_seed"], "odds", save["odds_counter"], row, i)


def _odds_pending(cat, save, n):
    """One row per stance x pause policy against the encounter in front of you."""
    delver = copy.deepcopy(save["delver"])
    specs = [by_name(cat["enemies"], nm) for nm in save["expedition"]["pending_site"]["enemies"]]
    dark = _darkness(delver)
    rows = []
    for stance in sorted(engine.STANCES):
        for policy in ODDS_POLICIES:
            if policy == "surge" and delver["grit"] < 2:
                continue
            results = []
            for i in range(n):
                state, result = engine.start_fight(delver, specs, stance,
                                                   _odds_seed(save, len(rows), i), darkness=dark)
                if result is None:
                    choice = policy if policy in engine.pause_options(state) else "fight_on"
                    result = engine.resume_fight(state, choice)
                results.append(result)
            rows.append(_odds_row("%s / %s" % (stance, policy), results, delver["light"]))
    return rows


def _odds_paused(save, n):
    """One row per legal pause option, from a copy of the fight as it stands."""
    paused = save["expedition"]["paused_fight"]
    start_light = paused["delver"]["light"]
    rows = []
    for choice in sorted(engine.pause_options(paused)):
        results = []
        for i in range(n):
            sim = copy.deepcopy(paused)
            engine.reseed_state(sim, _odds_seed(save, len(rows), i))
            results.append(engine.resume_fight(sim, choice))
        rows.append(_odds_row(choice, results, start_light))
    return rows


def do_train(save, stat):
    if stat not in engine.STATS:
        raise ValueError("no such stat; stats: %s" % ", ".join(engine.STATS))
    if save["expedition"]["active"]:
        raise ValueError("training happens in Wake")
    delver = save["delver"]
    new_val = delver["stats"][stat] + 1
    if new_val > STAT_CAP:
        raise ValueError("%s is at the cap (%d)" % (stat, STAT_CAP))
    cost = TRAIN_COST_PER_LEVEL * new_val
    if save["wake"]["chits"] < cost:
        raise ValueError("training %s to %d costs %d chits; you have %d"
                         % (stat, new_val, cost, save["wake"]["chits"]))
    save["wake"]["chits"] -= cost
    delver["stats"][stat] = new_val
    if stat == "vim":
        delver["hp"] = engine.hp_max(delver)
    if stat == "nerve":
        delver["grit"] = engine.grit_max(delver)
    save["history"].append("Day %d: trained %s to %d (%d chits)."
                           % (save["wake"]["day"], stat, new_val, cost))
    return ["%s rises to %d (-%d chits, %d left)." % (stat, new_val, cost, save["wake"]["chits"])]


def do_buy(cat, save, item_name):
    if save["expedition"]["active"]:
        raise ValueError("the outfitters are in Wake")
    delver = save["delver"]
    for section, slot in (("weapons", "weapon"), ("armors", "armor")):
        for rec in cat[section]:
            if rec["name"] == item_name:
                if save["wake"]["chits"] < rec["value"]:
                    raise ValueError("%s costs %d chits; you have %d"
                                     % (item_name, rec["value"], save["wake"]["chits"]))
                save["wake"]["chits"] -= rec["value"]
                delver[slot] = dict(rec)
                save["history"].append("Day %d: bought %s (%d chits)."
                                       % (save["wake"]["day"], item_name, rec["value"]))
                return ["%s is yours (-%d chits, %d left)." % (item_name, rec["value"], save["wake"]["chits"])]
    raise ValueError("no such item in the market: %r" % item_name)


def _evt_rng(save):
    rng = engine.rng_for(save["world_seed"], "evt", save["counter"])
    save["counter"] += 1
    return rng


# ------------------------------------------------------------------ eyeball

def main():
    import argparse
    p = argparse.ArgumentParser(description="content eyeball check: sample sites per depth")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--per-depth", type=int, default=3)
    args = p.parse_args()
    cat = load_catalog()
    counts = {k: (sum(len(cat["names"][p]) for p in NAME_LISTS) if k == "names" else len(cat[k]))
              for k in CENSUS}
    print("catalog ok:", ", ".join("%s=%d" % (k, counts[k]) for k in sorted(counts)))
    for depth in range(1, DEPTH_MAX + 1):
        for i in range(args.per_depth):
            rng = engine.rng_for(args.seed, "eyeball", depth, i)
            site = generate_site(cat, depth, rng)
            extra = site.get("enemies") or site.get("salvage") or site.get("strange") or ""
            print("d%d %-12s %-22s %s" % (depth, site["kind"], site["name"], extra))
            print("      rumor: %s" % site["rumor"])


if __name__ == "__main__":
    main()
