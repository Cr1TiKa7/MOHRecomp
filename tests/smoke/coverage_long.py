"""Long coverage test (spec M3): about --minutes each in videos, menus and levels.

Usage (from anywhere):
    py -3 tests/smoke/coverage_long.py --exe PATH --cue PATH [--minutes 10]
                                       [--port 4370] [--out DIR] [--game game.toml]

Runtime autocompile is off and the DLL cache deleted, so overlay code runs
either from the static shard or interpreted. Three phases, each measured as the
sum of its own windows (never since-boot totals):
  videos - boot without turbo (EA logo + intro film), then BRIEFING replayed
  menus  - main-menu ring, OPTIONS / WAR RECORDS / GALLERY opened and browsed
  levels - M1L1, M3L1 and M7L1 (jumped to via the game state), input loop
Each phase must stay below MAX_SHARE interpreted overlay dispatches.
Exit 0/1, one line per phase plus a FAIL line naming the phases over the limit.
"""

import argparse
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flows  # noqa: E402
import moh  # noqa: E402
import psxdbg  # noqa: E402
import psxrun  # noqa: E402

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
GAME_ID = "SLES-02470"
MAX_SHARE = 0.01
LEVELS = ((1, 1), (3, 1), (7, 1))
BRIEFING_SECS = 30.0
SUBMENUS = ("OPTIONS", "WAR RECORDS", "GALLERY")
SmokeFailure = psxrun.SmokeFailure
KEYS = ("native", "static", "interp", "insns")


def accumulate(segments):
    """Sum (phase, before, after) counter deltas per phase."""
    totals = {}
    for phase, before, after in segments:
        acc = totals.setdefault(phase, {k: 0 for k in KEYS})
        for k in KEYS:
            acc[k] += after[k] - before[k]
    return totals


def share(delta):
    total = delta["native"] + delta["static"] + delta["interp"]
    return delta["interp"] / total if total else 1.0


def _launch(args, out_dir):
    cache = os.path.join(os.path.dirname(os.path.abspath(args.exe)), "cache", GAME_ID)
    shutil.rmtree(cache, ignore_errors=True)
    if os.path.exists(cache):
        raise SmokeFailure(f"could not remove the runtime overlay cache: {cache}")
    os.makedirs(out_dir, exist_ok=True)
    return psxrun.launch(args.exe, args.cue, args.game, args.port, out_dir,
                         env_extra={"PSX_OVERLAY_AUTOCOMPILE_OFF": "1"})


def videos_and_menus(args, out_root, window, segments):
    proc = _launch(args, os.path.join(out_root, "menus"))
    port = args.port
    try:
        deadline = time.monotonic() + 3 * window + 600
        psxrun.wait_for_ping(proc, port, deadline)
        c0 = flows.overlay_counters(port)                       # videos: boot intro, no turbo
        end = time.monotonic() + window
        psxrun.wait_frame(port, moh.MENU_READY_FRAME, deadline)
        base, _, _ = flows.walk_ring(port, deadline)
        while time.monotonic() < end:                           # ... then BRIEFING replays
            flows.goto(port, moh.MENU_RING.index("BRIEFING"), base, deadline)
            psxrun.press(port, "cross")
            time.sleep(BRIEFING_SECS)
            base, _, _ = flows.walk_ring(port, deadline)
        segments.append(("videos", c0, flows.overlay_counters(port)))

        c0 = flows.overlay_counters(port)                       # menus
        end = time.monotonic() + window
        while time.monotonic() < end:
            base, _, _ = flows.walk_ring(port, deadline)
            for name in SUBMENUS:
                flows.goto(port, moh.MENU_RING.index(name), base, deadline)
                psxrun.press(port, "cross")
                time.sleep(5.0)
                for _ in range(3):
                    psxrun.press(port, "right")
                    time.sleep(1.5)
                for _ in range(2):
                    psxrun.press(port, "triangle")
                    time.sleep(3.0)
                base, _, _ = flows.walk_ring(port, deadline)
        segments.append(("menus", c0, flows.overlay_counters(port)))
    finally:
        psxrun.shutdown(proc, port)


def levels(args, out_root, window, segments):
    per_level = window / len(LEVELS)
    for mission, level in LEVELS:
        out_dir = os.path.join(out_root, f"M{mission}L{level}")
        proc = _launch(args, out_dir)
        try:
            deadline = time.monotonic() + per_level + 600
            base = flows.boot_to_menu(proc, args.port, deadline)
            flows.start_level(args.port, base, mission, level, deadline)
            flows.wait_until_in_level(args.port, out_dir, min(deadline, time.monotonic() + 120))
            c0 = flows.overlay_counters(args.port)
            flows.input_loop(proc, args.port, out_dir, per_level, deadline, shot_every=60)
            segments.append(("levels", c0, flows.overlay_counters(args.port)))
        finally:
            try:
                psxdbg.send("clear_input", port=args.port, timeout=2.0)
            except ConnectionError:
                pass
            psxrun.shutdown(proc, args.port)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", required=True)
    ap.add_argument("--cue", required=True)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--port", type=int, default=psxdbg.DEFAULT_PORT)
    ap.add_argument("--out", default="")
    ap.add_argument("--game", default=os.path.join(REPO_ROOT, "game.toml"))
    args = ap.parse_args(argv)

    if psxdbg.port_in_use(args.port):
        print(f"coverage_long: FAIL: port {args.port} busy - another runtime running?", file=sys.stderr)
        return 1
    if not os.path.isfile(args.exe):
        print(f"coverage_long: FAIL: exe not found: {args.exe}", file=sys.stderr)
        return 1
    out_root = os.path.abspath(args.out or os.path.join(
        os.environ.get("TEMP", REPO_ROOT), "coverage-long-" + time.strftime("%Y%m%d-%H%M%S")))
    print(f"coverage_long: out={out_root}", flush=True)
    window = args.minutes * 60.0
    segments = []
    try:
        videos_and_menus(args, out_root, window, segments)
        levels(args, out_root, window, segments)
    except SmokeFailure as exc:
        print(f"coverage_long: FAIL: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - keep the one-line contract
        print(f"coverage_long: FAIL: unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    totals = accumulate(segments)
    over = []
    for phase in ("videos", "menus", "levels"):
        delta = totals.get(phase, {k: 0 for k in KEYS})
        s = share(delta)
        print(f"coverage_long: {phase}: interp={s:.4f} insns={delta['insns']} "
              f"dispatches={delta['native'] + delta['static'] + delta['interp']}")
        if s >= MAX_SHARE:
            over.append(phase)
    if over:
        print(f"coverage_long: FAIL: interpreted share >= {MAX_SHARE} in {', '.join(over)}", file=sys.stderr)
        return 1
    print("coverage_long: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
