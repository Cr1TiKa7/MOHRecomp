"""Level sweep: jump into every single-player level and check it loads and runs.

Usage (from anywhere):
    py -3 tests/smoke/sweep_smoke.py --exe PATH --cue PATH [--port 4370] [--out DIR]
                                     [--mission N] [--bonus] [--per-level-timeout 300]
                                     [--game game.toml]

Each level gets its own runtime instance (runtime autocompile off, DLL cache
deleted): boot into the menu, NEW GAME with the persistent game state set to
the level (flows.start_level), wait until the level view is up, then a
LOOP_SECS input loop. A level passes when the game read that level's data
files (and none of Mission 1 Level 1's unless it is M1L1), kept running with a
changing picture, and less than INTERP_MAX of the overlay dispatches in the
level window were interpreted. One line per level, then "sweep: N/M levels OK".
Exit 0 when all selected levels pass.
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
IN_LEVEL_SECS = 120.0
LOOP_SECS = 30
SHOT_EVERY_SECS = 10
INTERP_MAX = 0.01
FROZEN_DIFF = 1.0
SmokeFailure = psxrun.SmokeFailure


def select_levels(mission, bonus):
    levels = moh.BONUS_LEVELS if bonus else moh.LEVELS
    return [entry for entry in levels if mission is None or entry[0] == mission]


def run_all(levels, check):
    """Run check(mission, level) for every level; never stop early."""
    lines, failures = [], 0
    for mission, level, _ in levels:
        tag = f"M{mission}L{level}"
        try:
            lines.append(f"{tag}: OK {check(mission, level)}")
        except SmokeFailure as exc:
            failures += 1
            lines.append(f"{tag}: FAIL {exc}")
        except Exception as exc:  # noqa: BLE001 - report and carry on with the next level
            failures += 1
            lines.append(f"{tag}: FAIL unexpected error: {type(exc).__name__}: {exc}")
        print(lines[-1], flush=True)
    lines.append(f"sweep: {len(levels) - failures}/{len(levels)} levels OK")
    return lines, failures


def check_level(proc, port, out_dir, mission, level, deadline):
    lbas = moh.level_lbas(mission, level)
    base = flows.boot_to_menu(proc, port, deadline)
    mark = flows.start_level(port, base, mission, level, deadline)
    flows.wait_until_in_level(port, out_dir, min(deadline, time.monotonic() + IN_LEVEL_SECS))
    before = flows.overlay_counters(port)
    shots = flows.input_loop(proc, port, out_dir, LOOP_SECS, deadline, shot_every=SHOT_EVERY_SECS)
    after = flows.overlay_counters(port)
    flows.shot(port, out_dir, f"M{mission}L{level}.png")

    word = psxrun.read_u32(port, moh.SHELL_LOAD_ADDR)
    if word != moh.LEVEL_FILE_ID:
        raise SmokeFailure(f"left the level during the loop (overlay word 0x{word:08X})")
    if len(shots) < 2:
        raise SmokeFailure(f"input loop ended after {len(shots)} screenshot(s): no freeze check possible")
    own = flows.cd_reads_in(port, mark, lbas)
    if not own:
        raise SmokeFailure(f"no reads of M{mission}L{level} data (LBA {lbas[0]}-{lbas[1]})")
    if (mission, level) != (1, 1):
        stray = flows.cd_reads_in(port, mark, moh.M1_LVL1_LBAS)
        if stray:
            raise SmokeFailure(f"read Mission 1 Level 1 data {stray}: the jump did not take")
    diffs = [flows.screen_diff(a, b) for a, b in zip(shots, shots[1:])]
    if any(d < FROZEN_DIFF for d in diffs):
        raise SmokeFailure("picture stopped changing (shot diffs " + ", ".join(f"{d:.1f}" for d in diffs) + ")")
    share = flows.window_share(before, after)
    summary = f"interp={share:.4f} insns={after['insns'] - before['insns']} lbas={own[:2]}"
    if share >= INTERP_MAX:
        raise SmokeFailure(f"interpreted share too high; {summary}")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", required=True)
    ap.add_argument("--cue", required=True)
    ap.add_argument("--port", type=int, default=psxdbg.DEFAULT_PORT)
    ap.add_argument("--out", default="")
    ap.add_argument("--mission", type=int, default=None)
    ap.add_argument("--bonus", action="store_true")
    ap.add_argument("--per-level-timeout", type=float, default=300.0)
    ap.add_argument("--game", default=os.path.join(REPO_ROOT, "game.toml"))
    args = ap.parse_args(argv)

    if psxdbg.port_in_use(args.port):
        print(f"sweep_smoke: FAIL: port {args.port} busy - another runtime running?", file=sys.stderr)
        return 1
    if not os.path.isfile(args.exe):
        print(f"sweep_smoke: FAIL: exe not found: {args.exe}", file=sys.stderr)
        return 1
    levels = select_levels(args.mission, args.bonus)
    if not levels:
        print(f"sweep_smoke: FAIL: no levels for mission {args.mission}", file=sys.stderr)
        return 1
    out_root = os.path.abspath(args.out or os.path.join(
        os.environ.get("TEMP", REPO_ROOT), "sweep-" + time.strftime("%Y%m%d-%H%M%S")))
    if not out_root.isascii():
        print(f"sweep_smoke: FAIL: out dir must be an ASCII path: {out_root}", file=sys.stderr)
        return 1
    cache = os.path.join(os.path.dirname(os.path.abspath(args.exe)), "cache", GAME_ID)
    print(f"sweep_smoke: out={out_root} levels={len(levels)}", flush=True)

    def check(mission, level):
        out_dir = os.path.join(out_root, f"M{mission}L{level}")
        os.makedirs(out_dir, exist_ok=True)
        shutil.rmtree(cache, ignore_errors=True)
        if os.path.exists(cache):
            raise SmokeFailure(f"could not remove the runtime overlay cache: {cache}")
        proc = psxrun.launch(args.exe, args.cue, args.game, args.port, out_dir,
                             env_extra={"PSX_OVERLAY_AUTOCOMPILE_OFF": "1"})
        try:
            return check_level(proc, args.port, out_dir, mission, level,
                               time.monotonic() + args.per_level_timeout)
        finally:
            try:
                psxdbg.send("clear_input", port=args.port, timeout=2.0)
            except ConnectionError:
                pass
            psxrun.shutdown(proc, args.port)

    lines, failures = run_all(levels, check)
    print(lines[-1])
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
