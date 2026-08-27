"""UNDERSTORY session driver: a thin CLI over engine/content/pages.

All campaign state lives in save.json (untracked) between invocations. This
driver adds no game logic of its own; rules live in engine.py and
content.py, and the numbers live in the catalogs.

    python session.py new                    # roll a delver; day 1 starts underground
    python session.py delve                  # one step deeper (or hear the fork)
    python session.py delve 2                 # take the second passage
    python session.py fight --stance press   # resolve the pending fight
    python session.py fight --resume surge   # answer a mid-fight pause
    python session.py odds                   # wind the drum: odds on this fight
    python session.py camp | surface | status | market | log
    python session.py train edge | buy "salvage axe"
    python session.py sheet -m "message"     # rewrite + commit ui/ pages
"""

import argparse
import json
import os
import sys

import content
import engine
import pages

SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")


def load_save():
    if not os.path.exists(SAVE_PATH):
        raise SystemExit("no save.json -- start with: python session.py new")
    with open(SAVE_PATH, "r", encoding="utf-8") as f:
        save = json.load(f)
    if save.get("version") != engine.SAVE_VERSION:
        raise SystemExit("save version %r != engine version %d -- no backcompat, ever: "
                         "delete save.json and raise a new delver"
                         % (save.get("version"), engine.SAVE_VERSION))
    return save


def write_save(save):
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(save, f, indent=1)
    pages.write_pages(save)


def say(lines):
    for line in lines:
        print(line)


def require_alive(save):
    if not save["delver"]["alive"]:
        raise SystemExit("%s is dead. The Ledger remembers; the save is done. "
                         "Start anew: delete save.json, then session.py new"
                         % save["delver"]["name"])


# ------------------------------------------------------------------ commands

def cmd_new(cat, args):
    """Deal a stranger and put them underground. No parade of candidates:
    a choice between three unplayed strangers is a fake one."""
    if os.path.exists(SAVE_PATH) and not args.force:
        raise SystemExit("save.json already exists; pass --force to abandon it")
    world_seed = args.seed if args.seed is not None else engine.child_seed(os.urandom(8).hex())
    save = content.new_save(cat, world_seed)
    d = save["delver"]
    print("%s, %s.  (world seed %d)" % (d["name"], d["background"], world_seed))
    print(d["blurb"])
    print("  " + "  ".join("%s %d" % (s.upper(), d["stats"][s]) for s in engine.STATS))
    print("  hp %d/%d  grit %d/%d  light %d  supply %d  satchel 0/%d  windings %d"
          % (d["hp"], engine.hp_max(d), d["grit"], engine.grit_max(d), d["light"],
             d["supply"], engine.satchel_cap(d), d["windings"]))
    print("  %s (%s, acc %+d) / %s (guard +%d, soak %d)"
          % (d["weapon"]["name"], d["weapon"]["dmg"], d["weapon"]["acc"],
             d["armor"]["name"], d["armor"]["guard"], d["armor"]["soak"]))
    print("  knack: %s" % d["knack_text"])
    print("  standing order at the assay-house: %s, paying double."
          % save["wake"]["commission"]["item"])
    print("")
    _delve(cat, save)
    write_save(save)


def cmd_status(cat, args):
    save = load_save()
    d = save["delver"]
    exp = save["expedition"]
    where = ("depth %d" % exp["depth"]) if exp["active"] else ("Wake, day %d" % save["wake"]["day"])
    print("%s the %s -- %s%s" % (d["name"], d["background"], where,
                                 "" if d["alive"] else " -- DEAD"))
    print("hp %d/%d  grit %d/%d  light %d  supply %d  chits %d"
          % (d["hp"], engine.hp_max(d), d["grit"], engine.grit_max(d),
             d["light"], d["supply"], save["wake"]["chits"]))
    print("satchel %d/%d  windings %d/%d  standing order: %s (pays +%d)"
          % (len(d["salvage"]), engine.satchel_cap(d), d["windings"],
             engine.windings_max(d), save["wake"]["commission"]["item"],
             save["wake"]["commission"]["bonus"]))
    if d["salvage"]:
        print("carrying: " + ", ".join("%s(%d)" % (i["name"], i["value"]) for i in d["salvage"]))
    for mark in d["marks"]:
        print("mark: %s -- %s" % (mark["name"], mark["text"]))
    if exp["fork"]:
        say(content.fork_lines(exp["fork"]))
        print("Take one with: python session.py delve <n>")
    if exp["paused_fight"]:
        print("A FIGHT HANGS PAUSED. Options:")
        for key, desc in sorted(engine.pause_options(exp["paused_fight"]).items()):
            print("  --resume %-9s %s" % (key, desc))
    elif exp["pending_site"] and exp["pending_site"].get("enemies"):
        print("A fight is pending at %s: %s" % (exp["pending_site"]["name"],
                                                ", ".join(exp["pending_site"]["enemies"])))


def _delve(cat, save, passage=None):
    site, lines = content.advance_delve(cat, save, passage)
    if site is None:  # the way splits; nothing is spent until you choose
        say(lines)
        print("Take one with: python session.py delve <n>")
        return
    print("DEPTH %d -- %s [%s]" % (site["depth"], site["name"], site["kind"]))
    print(site["text"])
    if site["kind"] == "strange":
        print(site["strange_text"])
    say(lines)


def cmd_delve(cat, args):
    save = load_save()
    require_alive(save)
    _delve(cat, save, args.passage)
    write_save(save)


def _pct(value):
    """Never round a near-certainty up to a certainty, or a real chance
    down to none: the drum's one job is not lying about the odds."""
    if 0.0 < value < 0.05:
        return " <0.1%"
    if 99.95 <= value < 100.0:
        return " 99.9%"
    return "%5.1f%%" % value


def cmd_odds(cat, args):
    """The reckoning drum. Its table is printed as the engine makes it;
    the playbook forbids editorial on top of it."""
    save = load_save()
    require_alive(save)
    rows = content.simulate_odds(cat, save, args.n)
    print("THE RECKONING DRUM -- %d windings left, %d runs a line"
          % (save["delver"]["windings"], args.n))
    print("  %-22s   win  retreat    dead   rounds  hp on win  light" % "line")
    for r in rows:
        print("  %-22s %s %s %s   %6.1f     %6.1f  %5.1f"
              % (r["label"], _pct(r["victory"]), _pct(r["retreated"]), _pct(r["down"]),
                 r["rounds"], r["hp_on_win"], r["light"]))
    write_save(save)


def cmd_fight(cat, args):
    save = load_save()
    require_alive(save)
    if args.resume:
        say(content.resume_paused_fight(cat, save, args.resume))
    else:
        paused, lines = content.start_pending_fight(cat, save, args.stance)
        say(lines)
        if paused:
            print("")
            print("THE FIGHT PAUSES. Choose (session.py fight --resume <option>):")
            for key, desc in sorted(engine.pause_options(save["expedition"]["paused_fight"]).items()):
                print("  %-9s %s" % (key, desc))
    write_save(save)


def cmd_camp(cat, args):
    save = load_save()
    require_alive(save)
    say(content.do_camp(cat, save))
    write_save(save)


def cmd_surface(cat, args):
    save = load_save()
    require_alive(save)
    say(content.do_surface(cat, save))
    write_save(save)


def cmd_train(cat, args):
    save = load_save()
    require_alive(save)
    say(content.do_train(save, args.stat))
    write_save(save)


def cmd_buy(cat, args):
    save = load_save()
    require_alive(save)
    say(content.do_buy(cat, save, args.item))
    write_save(save)


def cmd_market(cat, args):
    save = load_save()
    print("THE OUTFITTERS' ROW, WAKE (chits: %d)" % save["wake"]["chits"])
    for w in cat["weapons"]:
        print("  %-22s %3d chits  (%s, acc %+d)  %s" % (w["name"], w["value"], w["dmg"], w["acc"], w["blurb"]))
    for a in cat["armors"]:
        print("  %-22s %3d chits  (guard +%d, soak %d%s)  %s"
              % (a["name"], a["value"], a["guard"], a["soak"], ", heavy" if a["heavy"] else "", a["blurb"]))
    print("training: raising a stat to N costs %d*N chits (cap %d)"
          % (content.TRAIN_COST_PER_LEVEL, content.STAT_CAP))
    com = save["wake"]["commission"]
    print("standing order: the assay-house pays double for %s (+%d chits on the first one in)"
          % (com["item"], com["bonus"]))


def cmd_log(cat, args):
    save = load_save()
    lf = save.get("last_fight")
    if not lf:
        print("no fight on record")
        return
    for imp, text, beat in lf["events"]:
        print(("* " if imp else "  ") + text + (("  [%s]" % beat) if beat else ""))


def cmd_sheet(cat, args):
    save = load_save()
    pages.write_pages(save)
    print(pages.sheet_commit(args.message or "table: %s, day %d"
                             % (save["delver"]["name"], save["wake"]["day"])))


def main(argv=None):
    cat = content.load_catalog()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="roll a delver and take the first step down")
    s.add_argument("--seed", type=int, default=None, help="world seed (omit for a random one)")
    s.add_argument("--force", action="store_true", help="abandon an existing save.json")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("odds", help="wind the reckoning drum: simulated odds on this fight")
    s.add_argument("--n", type=int, default=2000, help="runs per line")
    s.set_defaults(fn=cmd_odds)

    s = sub.add_parser("delve", help="one step deeper (costs 1 light), or hear where the way splits")
    s.add_argument("passage", nargs="?", type=int, default=None,
                   help="which passage to take when the way splits (1-based)")
    s.set_defaults(fn=cmd_delve)

    for name, fn, msg in (("status", cmd_status, "where things stand"),
                          ("camp", cmd_camp, "heal and steady (1 supply, 1 light)"),
                          ("surface", cmd_surface, "climb out, bank salvage, rest in Wake"),
                          ("market", cmd_market, "what Wake sells"),
                          ("log", cmd_log, "print the full last-fight log")):
        s = sub.add_parser(name, help=msg)
        s.set_defaults(fn=fn)

    s = sub.add_parser("fight", help="resolve the pending encounter (autocombat, one pause)")
    s.add_argument("--stance", default="measure", choices=sorted(engine.STANCES))
    s.add_argument("--resume", default=None, help="answer a paused fight with an option key")
    s.set_defaults(fn=cmd_fight)

    s = sub.add_parser("train", help="raise a stat in Wake (costs chits)")
    s.add_argument("stat", choices=engine.STATS)
    s.set_defaults(fn=cmd_train)

    s = sub.add_parser("buy", help="buy gear in Wake")
    s.add_argument("item")
    s.set_defaults(fn=cmd_buy)

    s = sub.add_parser("sheet", help="rewrite ui/ pages and commit them (one commit per message)")
    s.add_argument("-m", "--message", default=None)
    s.set_defaults(fn=cmd_sheet)

    args = p.parse_args(argv)
    try:
        args.fn(cat, args)
    except ValueError as exc:
        raise SystemExit("cannot: %s" % exc)


if __name__ == "__main__":
    main()
