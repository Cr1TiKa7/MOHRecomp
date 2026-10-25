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
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flows  # noqa: E402
import moh  # noqa: E402
import pngcheck  # noqa: E402
import psxdbg  # noqa: E402
import psxrun  # noqa: E402

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OPTIONS_INDEX = moh.MENU_RING.index("OPTIONS")
RETURN_INDEX = moh.MENU_RING.index("NEW GAME")
SCREEN_CHANGED = 20.0
SmokeFailure = psxrun.SmokeFailure

# Menu navigation lives in flows; kept here under the names other tests use.
entry_ptr = flows.entry_ptr
menu_index = flows.menu_index
walk_ring = flows.walk_ring
goto = flows.goto


def _fail(msg):
    print(f"menu_smoke: FAIL: {msg}", file=sys.stderr)
    return 1


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
    base = flows.boot_to_menu(proc, port, deadline)
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
