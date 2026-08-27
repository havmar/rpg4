"""UNDERSTORY run-page writers. A playthrough lives in its own folder,
runs/<delver-slug>/: the engine-written pages (rewritten whole on every
save), a committed snapshot of the save, and the DM-authored pages
(scene.md, chronicle.md), which are never touched here -- `sheet` only
commits them. Git is best-effort, never fatal.
"""

import json
import os
import re
import subprocess

import engine

ROOT = os.path.dirname(os.path.abspath(__file__))
RUNS_DIR = os.path.join(ROOT, "runs")


def run_slug(save):
    """The run folder name, derived from the delver's name -- never stored,
    so the save shape does not change. 'Marek Culvert' -> 'marek-culvert'."""
    return re.sub(r"[^a-z0-9]+", "-", save["delver"]["name"].lower()).strip("-")


def run_dir(save):
    return os.path.join(RUNS_DIR, run_slug(save))


def _write(save, name, text):
    d = run_dir(save)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name), "w", encoding="utf-8") as f:
        f.write(text)


def _bar(cur, top, width=20):
    filled = 0 if top <= 0 else max(0, min(width, round(width * cur / top)))
    return "[" + "#" * filled + "-" * (width - filled) + "] %d/%d" % (cur, top)


def write_delver(save):
    d = save["delver"]
    exp = save["expedition"]
    lines = []
    lines.append("=" * 52)
    lines.append("  %s -- %s of Wake%s" % (d["name"], d["background"],
                                           "" if d["alive"] else "  (DECEASED)"))
    lines.append("=" * 52)
    lines.append("")
    lines.append("  HP    " + _bar(d["hp"], engine.hp_max(d)))
    lines.append("  GRIT  " + _bar(d["grit"], engine.grit_max(d), width=8))
    lines.append("  LIGHT " + _bar(d["light"], engine.light_max(d), width=12))
    lines.append("  SUPPLY %d      WINDINGS %d/%d"
                 % (d["supply"], d["windings"], engine.windings_max(d)))
    lines.append("  SATCHEL %d/%d" % (len(d["salvage"]), engine.satchel_cap(d)))
    lines.append("")
    lines.append("  " + "  ".join("%s %d" % (s.upper(), d["stats"][s]) for s in engine.STATS))
    lines.append("")
    lines.append("  EDGE   swing      (attack rolls)")
    lines.append("  IRON   stand      (guard)")
    lines.append("  VIM    endure     (hp)")
    lines.append("  NERVE  hold       (grit, fear)")
    lines.append("  CRAFT  provision  (satchel size, drum windings)")
    lines.append("  grit: luck you spend    light: time underground    supply: nights of camp")
    lines.append("")
    lines.append("  attack %+d   guard %d   soak %d" % (engine.attack_bonus(d), engine.guard(d), engine.soak(d)))
    lines.append("  weapon: %s (%s, acc %+d)" % (d["weapon"]["name"], d["weapon"]["dmg"], d["weapon"]["acc"]))
    lines.append("  armor:  %s (guard +%d, soak %d)%s" % (d["armor"]["name"], d["armor"]["guard"],
                                                          d["armor"]["soak"],
                                                          " [heavy]" if d["armor"].get("heavy") else ""))
    lines.append("  knack:  %s -- %s" % (d["knack"], d["knack_text"]))
    lines.append("")
    if d["marks"]:
        lines.append("  MARKS (camp dresses the newest; a day in the haven clears them all)")
        for mark in d["marks"]:
            lines.append("    - %s: %s" % (mark["name"], mark["text"]))
        lines.append("")
    if exp["active"]:
        lines.append("  ON EXPEDITION -- depth %d" % exp["depth"])
    else:
        lines.append("  IN WAKE -- day %d" % save["wake"]["day"])
    lines.append("  chits banked: %d" % save["wake"]["chits"])
    com = save["wake"]["commission"]
    lines.append("  standing order: %s -- the assay-house pays +%d on the first one in"
                 % (com["item"], com["bonus"]))
    if d["salvage"]:
        lines.append("  carrying (%d/%d):" % (len(d["salvage"]), engine.satchel_cap(d)))
        for item in d["salvage"]:
            lines.append("    - %s (worth %d)" % (item["name"], item["value"]))
    if save["stashes"]:
        lines.append("  cached below (yours only if you go back for it): "
                     + "; ".join("depth %d: %d items worth %d"
                                 % (r["depth"], len(r["items"]),
                                    sum(i["value"] for i in r["items"]))
                                 for r in save["stashes"]))
    lines.append("")
    _write(save, "delver.txt", "\n".join(lines) + "\n")


def write_map(save):
    exp = save["expedition"]
    lines = ["THE DESCENT", "===========", ""]
    lines.append("  WAKE  (the mouth)" + ("" if exp["active"] else "   <-- you are here"))
    if exp["active"] and not exp["sites"]:
        lines.append("   |   <-- you are here, at the threshold")
    # roads not taken, in the order they were declined
    unopened = list(exp["declined"]) if exp["active"] else []
    cached = {r["depth"]: len(r["items"]) for r in save["stashes"]}
    for site in exp["sites"] if exp["active"] else []:
        marker = "   <-- you are here" if site["depth"] == exp["depth"] and site is exp["sites"][-1] else ""
        lines.append("   |")
        lines.append("  d%-2d %-12s %s%s" % (site["depth"], "[" + site["kind"] + "]", site["name"], marker))
        if site["depth"] in cached:  # once per depth, at its first room
            lines.append("      ..stash: %d items" % cached.pop(site["depth"]))
        while unopened and unopened[0]["depth"] == site["depth"]:
            lines.append("      ..unopened: %s" % unopened.pop(0)["rumor"])
    if exp["active"] and exp["fork"]:
        lines.append("   |")
        lines.append("  the way splits here:")
        for i, passage in enumerate(exp["fork"], 1):
            lines.append("    %d) %s" % (i, passage["rumor"]))
    if not exp["active"]:
        lines.append("   |")
        lines.append("  (the Understory waits)")
    lines.append("")
    _write(save, "map.txt", "\n".join(lines) + "\n")


def write_history(save):
    lines = ["# The story so far", ""]
    if not save["history"]:
        lines.append("*Nothing yet. Wake watches the mouth and waits.*")
    for entry in save["history"]:
        lines.append("- " + entry)
    lines.append("")
    _write(save, "history.md", "\n".join(lines) + "\n")


def _beat_line(imp, text, beat):
    """The engine's beat rides along as a [tag]: the DM narrates every one."""
    return text + (("  [%s]" % beat) if beat else "")


def write_fight(save):
    lf = save.get("last_fight")
    if not lf:
        return
    head = "LAST FIGHT -- %s (depth %d) -- %s" % (lf["site"], lf["depth"], lf["outcome"].upper())
    short = [head, "=" * len(head), ""]
    short += [_beat_line(imp, text, beat) for imp, text, beat in lf["events"]
              if imp >= 1 or beat]
    _write(save, "fight.txt", "\n".join(short) + "\n")
    full = [head, "=" * len(head), "", "(every roll; the short log is fight.txt)", ""]
    full += [("* " if imp else "  ") + _beat_line(imp, text, beat) for imp, text, beat in lf["events"]]
    _write(save, "fight_full.txt", "\n".join(full) + "\n")


def write_pages(save):
    write_delver(save)
    write_map(save)
    write_history(save)
    write_fight(save)
    # The committed snapshot is what a later session's `resume` picks up:
    # the live save.json is untracked and dies with the web container.
    _write(save, "save.json", json.dumps(save, indent=1) + "\n")


def sheet_commit(message):
    """Commit every existing run page, then push the session branch so the
    GitHub blob pages the player reads stay current. Best-effort; never
    raises -- git trouble must never kill the table."""
    try:
        subprocess.run(["git", "add", "runs"], cwd=ROOT, capture_output=True, timeout=30)
        done = subprocess.run(["git", "commit", "-m", message], cwd=ROOT,
                              capture_output=True, timeout=30, text=True)
        pushed = subprocess.run(["git", "push", "origin", "HEAD"], cwd=ROOT,
                                capture_output=True, timeout=60)
        note = "" if pushed.returncode == 0 else "  (push failed; pages are local only)"
        if done.returncode == 0:
            return "committed: " + message + note
        return "nothing new to commit" + note
    except Exception as exc:  # git trouble must never kill the table
        return "git trouble (ignored): %s" % exc
