"""Save smoke test: a memory card saved after Mission 1 Level 1 loads after a restart.

Usage (from anywhere):
    py -3 tests/smoke/save_smoke.py --exe PATH --cue PATH --card FIXTURE.mcd
                                    [--port 4370] [--timeout 420] [--out DIR] [--game game.toml]

Copies the fixture card into a fresh output folder (the fixture itself is never
written), boots into the menu and loads the save via WAR RECORDS > LOAD GAME
(the player name appearing in game RAM marks the save list). Back in the ring,
which then has an extra entry, the preselected NEXT MISSION is started: the game must
read Mission 1 Level 2's data files and none of Level 1's - a fresh game's
NEW GAME reads only Level 1. Exit 0/1, one-line reason on stderr.
"""

import argparse
import hashlib
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flows  # noqa: E402
import memcard  # noqa: E402
import moh  # noqa: E402
import psxdbg  # noqa: E402
import psxrun  # noqa: E402

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OPEN_SECS = 6.0
CONFIRM_TRIES = 6
CONFIRM_SECS = 3.0
LOADED_SECS = 6.0
BACK_PRESSES = 3
IN_LEVEL_SECS = 120.0
SmokeFailure = psxrun.SmokeFailure


def _fail(msg):
    print(f"save_smoke: FAIL: {msg}", file=sys.stderr)
    return 1


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _mc_reads(port):
    return int(psxdbg.send("sio_state", port=port).get("mc_reads", 0))


def load_save(port, base, needle, deadline):
    """WAR RECORDS > LOAD GAME > the save; returns to the main ring."""
    flows.goto(port, moh.MENU_RING.index("WAR RECORDS"), base, deadline)
    psxrun.press(port, "cross")
    time.sleep(OPEN_SECS)
    for _ in range(moh.LOAD_GAME_RIGHTS):
        psxrun.press(port, "right")
        time.sleep(flows.STEP_SECS)
    for _ in range(CONFIRM_TRIES):          # "Checking memory card" -> save list
        psxrun.press(port, "cross")
        time.sleep(CONFIRM_SECS)
        if flows.game_ram_hits(port, needle):
            break
    else:
        raise SmokeFailure(f"save list never showed {needle.decode()!r}")
    psxrun.press(port, "cross")             # select the save: "Loading game" / "Game loaded"
    time.sleep(LOADED_SECS)
    for _ in range(BACK_PRESSES):
        psxrun.press(port, "triangle")
        time.sleep(CONFIRM_SECS)


def check_save(proc, port, name, out_dir, deadline):
    needle = name.encode("ascii")
    base = flows.boot_to_menu(proc, port, deadline)
    reads_before = _mc_reads(port)
    load_save(port, base, needle, deadline)
    reads_after = _mc_reads(port)
    if reads_after <= reads_before:
        raise SmokeFailure(f"game did not read the card while loading (mc_reads {reads_before})")

    # Back in the ring the game preselects NEXT MISSION. The rebuilt ring has
    # 7 entries and NEXT MISSION is not the lowest pointer (NEW GAME stays), so
    # remember the preselected entry, learn the ring, and return to it.
    next_mission = flows.entry_ptr(port)
    _, _, size = flows.walk_ring(port, deadline)
    flows.goto_ptr(port, next_mission, size, deadline)
    mark = flows.cd_reads_total(port)
    psxrun.press(port, "cross")
    flows.advance_until_level(port, min(deadline, time.monotonic() + flows.LEVEL_LOAD_SECS))
    flows.wait_until_in_level(port, out_dir, min(deadline, time.monotonic() + IN_LEVEL_SECS))
    lvl2 = flows.cd_reads_in(port, mark, moh.M1_LVL2_LBAS)
    lvl1 = flows.cd_reads_in(port, mark, moh.M1_LVL1_LBAS)
    if not lvl2 or lvl1:
        raise SmokeFailure(f"starting NEXT MISSION after loading read Level 2 data {lvl2} and "
                           f"Level 1 data {lvl1}; a loaded save must continue with Level 2 only")
    psxrun.check_alive(proc)
    return (f"name={name} mc_reads={reads_before}->{reads_after} ring={size} "
            f"lvl2_reads={lvl2[:3]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", required=True)
    ap.add_argument("--cue", required=True)
    ap.add_argument("--card", required=True)
    ap.add_argument("--port", type=int, default=psxdbg.DEFAULT_PORT)
    # Boot, load, ring walk, briefing and Level 2 loading together take ~4-5 min.
    ap.add_argument("--timeout", type=float, default=420.0)
    ap.add_argument("--out", default="")
    ap.add_argument("--game", default=os.path.join(REPO_ROOT, "game.toml"))
    args = ap.parse_args(argv)

    if psxdbg.port_in_use(args.port):
        return _fail(f"port {args.port} busy - another runtime running?")
    if not os.path.isfile(args.exe):
        return _fail(f"exe not found: {args.exe}")
    if not os.path.isfile(args.card):
        return _fail(f"fixture card not found: {args.card}")
    try:
        saves = memcard.moh_saves(args.card)
    except ValueError as exc:
        return _fail(f"fixture card unreadable: {exc}")
    if not saves:
        return _fail(f"fixture has no MOH save: {args.card}")
    name = memcard.save_name(saves[0])

    out_dir = os.path.abspath(args.out or os.path.join(
        os.environ.get("TEMP", REPO_ROOT), "save-" + time.strftime("%Y%m%d-%H%M%S")))
    if not out_dir.isascii():
        return _fail(f"out dir must be an ASCII path: {out_dir}")
    os.makedirs(os.path.join(out_dir, "memcards"), exist_ok=True)
    fixture_hash = _sha256(args.card)
    shutil.copyfile(args.card, os.path.join(out_dir, "memcards", "card1.mcd"))

    print(f"save_smoke: out={out_dir}")
    proc = psxrun.launch(args.exe, args.cue, args.game, args.port, out_dir)
    try:
        summary = check_save(proc, args.port, name, out_dir, time.monotonic() + args.timeout)
        result = 0
    except SmokeFailure as exc:
        summary, result = str(exc), 1
    except Exception as exc:  # noqa: BLE001 - keep the one-line contract
        summary, result = f"unexpected error: {type(exc).__name__}: {exc}", 1
    finally:
        psxrun.shutdown(proc, args.port)
    if _sha256(args.card) != fixture_hash:
        return _fail(f"fixture card was modified: {args.card}")
    if result:
        return _fail(summary)
    print(f"save_smoke: OK {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
