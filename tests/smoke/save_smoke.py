"""Save smoke test: a memory card saved after Mission 1 Level 1 loads after a restart.

Usage (from anywhere):
    py -3 tests/smoke/save_smoke.py --exe PATH --cue PATH --card FIXTURE.mcd
                                    [--port 4370] [--timeout 300] [--out DIR] [--game game.toml]

Copies the fixture card into a fresh output folder (the fixture itself is never
written), boots into the menu, checks the save's player name is NOT yet in game
RAM, then loads the save via WAR RECORDS > LOAD GAME and requires the name to
appear in game RAM, the game to have read the card and to keep running.
Exit 0/1, one-line reason on stderr.
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
    """WAR RECORDS > LOAD GAME, pressing X until the save's name is in game RAM."""
    flows.goto(port, moh.MENU_RING.index("WAR RECORDS"), base, deadline)
    psxrun.press(port, "cross")
    time.sleep(OPEN_SECS)
    for _ in range(moh.LOAD_GAME_RIGHTS):
        psxrun.press(port, "right")
        time.sleep(flows.STEP_SECS)
    for _ in range(CONFIRM_TRIES):
        psxrun.press(port, "cross")
        time.sleep(CONFIRM_SECS)
        if flows.game_ram_hits(port, needle):
            return
    raise SmokeFailure(f"save not loaded: {needle.decode()!r} never appeared in game RAM")


def check_save(proc, port, name, deadline):
    needle = name.encode("ascii")
    base = flows.boot_to_menu(proc, port, deadline)
    before = flows.game_ram_hits(port, needle)
    if before:
        raise SmokeFailure(f"{name!r} already in game RAM before loading ({before[0]:#010x}); "
                           "the check would prove nothing")
    reads_before = _mc_reads(port)
    load_save(port, base, needle, deadline)
    reads_after = _mc_reads(port)
    if reads_after <= reads_before:
        raise SmokeFailure(f"game did not read the card while loading (mc_reads {reads_before})")
    _, frame_a = psxrun.read_frame(port, deadline)
    time.sleep(2.0)
    psxrun.check_alive(proc)
    _, frame_b = psxrun.read_frame(port, deadline)
    if frame_b <= frame_a:
        raise SmokeFailure(f"game stalled after loading (frame {frame_a} -> {frame_b})")
    return f"name={name} mc_reads={reads_before}->{reads_after}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", required=True)
    ap.add_argument("--cue", required=True)
    ap.add_argument("--card", required=True)
    ap.add_argument("--port", type=int, default=psxdbg.DEFAULT_PORT)
    ap.add_argument("--timeout", type=float, default=300.0)
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
        summary = check_save(proc, args.port, name, time.monotonic() + args.timeout)
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
