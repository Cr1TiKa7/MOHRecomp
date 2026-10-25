"""Menu smoke test: the main-menu ring and the Options submenu respond to the pad.

Usage (from anywhere):
    py -3 tests/smoke/menu_smoke.py --exe PATH --cue PATH [--port 4370]
                                    [--timeout 180] [--out DIR] [--game game.toml]

Fast-forwards to the main menu, waits until a RIGHT visibly moves the ring
(presses during transitions are swallowed), walks all six entries back to the
start, checks the game has accessed the memory card, opens OPTIONS with X and
leaves it with TRIANGLE (the game then
selects NEW GAME again). The current entry is
read from RAM (moh.MENU_ITEM_PTR_ADDR). Exit 0/1, one-line reason on stderr.
"""

import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import moh  # noqa: E402
import pngcheck  # noqa: E402
import psxdbg  # noqa: E402
import psxrun  # noqa: E402

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
STEP_SECS = 1.5
ACTIVATION_TRIES = 10
OPTIONS_INDEX = moh.MENU_RING.index("OPTIONS")
RETURN_INDEX = moh.MENU_RING.index("NEW GAME")
SCREEN_CHANGED = 20.0
SmokeFailure = psxrun.SmokeFailure


def _fail(msg):
    print(f"menu_smoke: FAIL: {msg}", file=sys.stderr)
    return 1


def entry_ptr(port):
    return struct.unpack("<I", psxrun.read_bytes(port, moh.MENU_ITEM_PTR_ADDR, 4))[0]


def menu_index(port, base):
    return moh.menu_index_from_ptr(entry_ptr(port), base)


def _step_right(port):
    psxrun.press(port, "right")
    time.sleep(STEP_SECS)
    return entry_ptr(port)


def walk_ring(port, deadline):
    """Wait until RIGHT moves the ring, walk it once.

    Returns (base, index): the entry-array base learned from the walk (lowest
    pointer = NEW GAME) and the index the ring ended on.
    """
    ring = len(moh.MENU_RING)
    start = None
    for _ in range(ACTIVATION_TRIES):
        if time.monotonic() > deadline:
            break
        before = entry_ptr(port)
        after = _step_right(port)
        if moh.is_ring_step(before, after):
            start = after
            break
    if start is None:
        raise SmokeFailure(f"menu never reacted to RIGHT within {ACTIVATION_TRIES} tries")
    seen = {start}
    ptr = start
    for _ in range(ring):
        nxt = _step_right(port)
        if not moh.is_ring_step(ptr, nxt):
            raise SmokeFailure(f"RIGHT moved the entry pointer {ptr:#010x} -> {nxt:#010x}")
        seen.add(nxt)
        ptr = nxt
    if ptr != start or len(seen) != ring:
        raise SmokeFailure(f"ring did not cycle through {ring} entries back to the start")
    base = min(seen)
    return base, moh.menu_index_from_ptr(ptr, base)


def goto(port, index, base, deadline):
    for _ in range(len(moh.MENU_RING)):
        if menu_index(port, base) == index:
            return
        if time.monotonic() > deadline:
            break
        _step_right(port)
    if menu_index(port, base) != index:
        raise SmokeFailure(f"could not reach menu entry {index}")


def check_memcard_probed(sio):
    """The game itself talked to the memory card (the runtime only formats the file)."""
    if int(sio.get("mc_probes", 0)) + int(sio.get("mc_reads", 0)) == 0:
        raise SmokeFailure("game never accessed the memory card (sio_state mc_probes/mc_reads = 0)")


def _shot(port, out_dir, name):
    path = os.path.join(out_dir, name).replace("\\", "/")
    psxdbg.send("screenshot", port=port, path=path)
    return path


def _screen_changed(a, b):
    try:
        return pngcheck.mean_abs_diff(a, b) > SCREEN_CHANGED
    except ValueError:  # different display size: definitely another screen
        return True


def check_menu(proc, port, out_dir, deadline):
    psxrun.wait_for_ping(proc, port, deadline)
    psxdbg.send("turbo", port=port, enabled=1)
    psxrun.wait_frame(port, moh.MENU_READY_FRAME, deadline)
    psxdbg.send("turbo", port=port, enabled=0)
    base, _ = walk_ring(port, deadline)
    check_memcard_probed(psxdbg.send("sio_state", port=port))
    goto(port, OPTIONS_INDEX, base, deadline)
    menu_png = _shot(port, out_dir, "menu.png")
    psxrun.press(port, "cross")
    time.sleep(5.0)
    options_png = _shot(port, out_dir, "options.png")
    if not _screen_changed(menu_png, options_png):
        raise SmokeFailure("X on OPTIONS did not change the screen")
    psxrun.press(port, "triangle")
    time.sleep(4.0)
    back_png = _shot(port, out_dir, "back.png")
    if not _screen_changed(options_png, back_png):
        raise SmokeFailure("TRIANGLE did not leave the Options screen")
    # The game returns from Options to the ring with NEW GAME selected.
    back = menu_index(port, base)
    if back != RETURN_INDEX:
        raise SmokeFailure(f"TRIANGLE from Options left the menu at entry {back}, expected {RETURN_INDEX}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", required=True)
    ap.add_argument("--cue", required=True)
    ap.add_argument("--port", type=int, default=psxdbg.DEFAULT_PORT)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--out", default="")
    ap.add_argument("--game", default=os.path.join(REPO_ROOT, "game.toml"))
    args = ap.parse_args(argv)

    if psxdbg.port_in_use(args.port):
        return _fail(f"port {args.port} busy - another runtime running?")
    if not os.path.isfile(args.exe):
        return _fail(f"exe not found: {args.exe}")
    out_dir = os.path.abspath(args.out or os.path.join(
        os.environ.get("TEMP", REPO_ROOT), "menu-" + time.strftime("%Y%m%d-%H%M%S")))
    if not out_dir.isascii():
        return _fail(f"out dir must be an ASCII path: {out_dir}")
    os.makedirs(out_dir, exist_ok=True)

    print(f"menu_smoke: out={out_dir}")
    proc = psxrun.launch(args.exe, args.cue, args.game, args.port, out_dir)
    try:
        check_menu(proc, args.port, out_dir, time.monotonic() + args.timeout)
        print(f"menu_smoke: OK ring={len(moh.MENU_RING)} options=entered")
        return 0
    except SmokeFailure as exc:
        return _fail(str(exc))
    except Exception as exc:  # noqa: BLE001 - keep the one-line contract
        return _fail(f"unexpected error: {type(exc).__name__}: {exc}")
    finally:
        psxrun.shutdown(proc, args.port)


if __name__ == "__main__":
    sys.exit(main())
