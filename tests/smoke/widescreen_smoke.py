"""Widescreen smoke test: 16:9 native-wide only in gameplay, 4:3 elsewhere.

Prints one line: widescreen_smoke: OK ... or widescreen_smoke: FAIL: <reason>.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pngcheck  # noqa: E402

DARK_BELOW = 8   # a pixel is dark when every channel is below this


def band_dark_fraction(png_path, nw_extra):
    """Share of dark pixels in the left and right outer bands (nw_extra // 2 wide each)."""
    w, h, bpp, rows = pngcheck.read_pixels(png_path)
    band = nw_extra // 2
    result = []
    for x0 in (0, w - band):
        dark = 0
        for row in rows:
            for x in range(x0, x0 + band):
                if max(row[x * bpp:x * bpp + 3]) < DARK_BELOW:
                    dark += 1
        result.append(dark / (band * h))
    return tuple(result)


def present_entry(event):
    """One present_ring event: [seq, frame, path, present_w, disp_w, disp_h, game_mode,
    native_43, fellback, tag_delta, nw_extra, gte_verts, ovh_prims, bd_veto]."""
    return {"path": event[2], "present_w": event[3], "nw_extra": event[10]}


def latest_present(reply):
    return present_entry(reply["events"][-1])


# --------------------------------------------------------------------------
# Runtime checks
# --------------------------------------------------------------------------

import argparse  # noqa: E402
import time  # noqa: E402

import flows  # noqa: E402
import modstate  # noqa: E402
import moh  # noqa: E402
import psxdbg  # noqa: E402
import psxrun  # noqa: E402

SmokeFailure = psxrun.SmokeFailure
REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PACKAGE = ("moh.enhancement.widescreen", "widescreen", {})
INTRO_FRAME = 900         # the intro film is running by then (intro_smoke)
SETTLE_SECS = 1.0
LEVEL_SECS = 300.0


def _fail(msg):
    print(f"widescreen_smoke: FAIL: {msg}")
    return 1


def wide_state(port):
    """gpu_state.ws plus the latest present: {"path", "present_w", "nw_extra", "ws": {...}}."""
    entry = latest_present(psxdbg.send("present_ring", port=port, n=1, timeout=10.0))
    entry["ws"] = psxdbg.send("gpu_state", port=port, timeout=10.0).get("ws", {})
    return entry


def expect_path(port, out_dir, label, wide):
    time.sleep(SETTLE_SECS)
    state = wide_state(port)
    shot = flows.shot(port, out_dir, label + ".png")
    if (state["path"] == "wide") != wide:
        raise SmokeFailure(f"{label}: present path {state['path']!r}, expected "
                           f"{'wide' if wide else 'not wide'} (nw_extra {state['nw_extra']})")
    return state, shot


def check_on(proc, port, out_dir, deadline):
    psxrun.wait_for_ping(proc, port, deadline)
    psxrun.wait_frame(port, INTRO_FRAME, deadline)
    expect_path(port, out_dir, "intro_film", False)
    base = flows.boot_to_menu(proc, port, deadline)
    expect_path(port, out_dir, "menu", False)
    flows.goto(port, moh.MENU_RING.index("NEW GAME"), base, deadline)
    psxrun.press(port, "cross")
    flows.advance_until_level(port, deadline)
    expect_path(port, out_dir, "poster", False)
    flows.wait_until_in_level(port, out_dir, deadline)
    time.sleep(2.0)
    state, shot = expect_path(port, out_dir, "level", True)
    if state["nw_extra"] != moh.WS_NW_EXTRA:
        raise SmokeFailure(f"level: nw_extra {state['nw_extra']}, expected {moh.WS_NW_EXTRA}")
    width = pngcheck.read_pixels(shot)[0]
    if width != moh.WS_WIDE_WIDTH:
        raise SmokeFailure(f"level screenshot is {width} wide, expected {moh.WS_WIDE_WIDTH}")
    psxrun.hold_buttons(port, "r2")
    expect_path(port, out_dir, "aim", True)
    psxrun.release(port)
    psxrun.press(port, "start")
    expect_path(port, out_dir, "pause", moh.WS_PAUSE_PATH == "wide")
    psxrun.press(port, "start")
    expect_path(port, out_dir, "resumed", True)
    return f"level wide={width}x{state['nw_extra']} pause={moh.WS_PAUSE_PATH}"


def check_off(proc, port, out_dir, deadline):
    base = flows.boot_to_menu(proc, port, deadline)
    flows.start_new_game(port, base, deadline)
    flows.wait_until_in_level(port, out_dir, deadline)
    time.sleep(2.0)
    expect_path(port, out_dir, "level_off", False)
    return "off=4:3"


def run(args, label, check, package):
    out_dir = os.path.join(args.out_root, label)
    os.makedirs(out_dir, exist_ok=True)
    build_dir = os.path.dirname(os.path.abspath(args.exe))
    ctx = modstate.enabled(build_dir, None, features=[PACKAGE]) if package else _Nothing()
    with ctx:
        proc = psxrun.launch(args.exe, args.cue, args.game, args.port, out_dir)
        try:
            return check(proc, args.port, out_dir, time.monotonic() + LEVEL_SECS)
        finally:
            try:
                psxdbg.send("clear_input", port=args.port, timeout=2.0)
            except ConnectionError:
                pass
            psxrun.shutdown(proc, args.port)


class _Nothing:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", required=True)
    ap.add_argument("--cue", required=True)
    ap.add_argument("--port", type=int, default=psxdbg.DEFAULT_PORT)
    ap.add_argument("--out", default="")
    ap.add_argument("--game", default=os.path.join(REPO_ROOT, "game.toml"))
    args = ap.parse_args(argv)
    if psxdbg.port_in_use(args.port):
        return _fail(f"port {args.port} busy - another runtime running?")
    if not os.path.isfile(args.exe):
        return _fail(f"exe not found: {args.exe}")
    args.out_root = os.path.abspath(args.out or os.path.join(
        os.environ.get("TEMP", REPO_ROOT), "widescreen-" + time.strftime("%Y%m%d-%H%M%S")))
    print(f"widescreen_smoke: out={args.out_root}", flush=True)
    try:
        parts = [run(args, "on", check_on, True), run(args, "off", check_off, False)]
        print("widescreen_smoke: OK " + " ".join(parts))
        return 0
    except SmokeFailure as exc:
        return _fail(str(exc))
    except Exception as exc:  # noqa: BLE001 - keep the one-line contract
        return _fail(f"unexpected error: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    sys.exit(main())
