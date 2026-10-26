"""Split-screen smoke test: plug a pad into port 2 and play the two-player mode.

Usage (from anywhere):
    py -3 tests/smoke/mp_smoke.py --exe PATH --cue PATH [--port 4370] [--out DIR]
                                  [--timeout 420] [--game game.toml]

Runtime autocompile off and DLL cache deleted, as in coverage_smoke. Boot into
the menu, plug pad 2 in over the debug port, MULTIPLAYER -> START GAME. Passes
when LEVEL2P.BIN replaced SHELL.BIN, the split view came up, each pad turns
only its own half of the screen, LOOP_SECS of both players walking/turning/
firing keep the game running with a changing picture, the game read
/DATA/TWOPLAYR/ data (and none of Mission 1 Level 1's), and less than
INTERP_MAX of the overlay dispatches in the loop were interpreted.
Exit 0/1 with one result line.
"""

import argparse
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flows  # noqa: E402
import moh  # noqa: E402
import pngcheck  # noqa: E402
import psxdbg  # noqa: E402
import psxrun  # noqa: E402

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
GAME_ID = "SLES-02470"
PLUG_SECS = 5.0
MENU_SECS = 4.0
IN_LEVEL_SECS = 120.0
TURN_SECS = 1.5
MIN_TURN_DIFF = 5.0        # a 1.5 s turn changed the own half by 12.5-14.0, idle by 0.0
LOOP_SECS = 60
SHOT_EVERY_SECS = 10
INTERP_MAX = 0.01
FROZEN_DIFF = 1.0
SmokeFailure = psxrun.SmokeFailure


def split_ok(own, other):
    """A turn must change the turning player's half clearly and the other half far less."""
    return own >= MIN_TURN_DIFF and other * 3 <= own


def own_and_other(player, halves):
    """Player 1 is the upper view, player 2 the lower one."""
    top, bottom = halves
    return (top, bottom) if player == 1 else (bottom, top)


def _fail(msg):
    print(f"mp_smoke: FAIL: {msg}", file=sys.stderr)
    return 1


def pad2_connected(port):
    return bool(psxdbg.send("pad_status", port=port)["slot1"]["connected"])


def plug_in_pad2(port):
    flows.plug_pad2(port)
    end = time.monotonic() + PLUG_SECS
    while time.monotonic() < end:
        if pad2_connected(port):
            return
        time.sleep(0.2)
    raise SmokeFailure("pad 2 never showed up as connected (pad_status slot1)")


def check_split(port, out_dir):
    results = []
    for player in (1, 2):
        a = flows.shot(port, out_dir, f"turn_p{player}_a.png")
        flows.hold(port, "right", TURN_SECS, pads=(player,))
        time.sleep(0.5)
        b = flows.shot(port, out_dir, f"turn_p{player}_b.png")
        own, other = own_and_other(player, pngcheck.half_diffs(a, b))
        if not split_ok(own, other):
            raise SmokeFailure(f"turning pad {player} changed its own half by {own:.1f} "
                               f"and the other half by {other:.1f}")
        results.append(f"p{player}={own:.1f}/{other:.1f}")
    return " ".join(results)


def check_mp(proc, port, out_dir, deadline):
    base = flows.boot_to_menu(proc, port, deadline)
    plug_in_pad2(port)
    flows.goto(port, moh.MENU_RING.index("MULTIPLAYER"), base, deadline)
    psxrun.press(port, "cross")
    time.sleep(MENU_SECS)
    flows.shot(port, out_dir, "multiplayer.png")
    mark = flows.cd_reads_total(port)
    flows.advance_until_level(port, min(deadline, time.monotonic() + IN_LEVEL_SECS),
                              file_id=moh.LEVEL2P_FILE_ID)
    flows.wait_until_in_level(port, out_dir, min(deadline, time.monotonic() + IN_LEVEL_SECS))
    split = check_split(port, out_dir)

    before = flows.overlay_counters(port)
    shots = flows.input_loop(proc, port, out_dir, LOOP_SECS, deadline,
                             shot_every=SHOT_EVERY_SECS, pads=(1, 2))
    after = flows.overlay_counters(port)
    flows.shot(port, out_dir, "mp.png")

    word = psxrun.read_u32(port, moh.SHELL_LOAD_ADDR)
    if word != moh.LEVEL2P_FILE_ID:
        raise SmokeFailure(f"left the split screen during the loop (overlay word 0x{word:08X})")
    if not pad2_connected(port):
        raise SmokeFailure("pad 2 got unplugged during the loop")
    twoplayr = flows.cd_reads_in(port, mark, moh.TWOPLAYR_LBAS)
    if not twoplayr:
        raise SmokeFailure(f"no reads of /DATA/TWOPLAYR/ (LBA {moh.TWOPLAYR_LBAS[0]}-{moh.TWOPLAYR_LBAS[1]})")
    stray = flows.cd_reads_in(port, mark, moh.M1_LVL1_LBAS)
    if stray:
        raise SmokeFailure(f"read Mission 1 Level 1 data {stray}: the campaign started instead")
    diffs = [flows.screen_diff(a, b) for a, b in zip(shots, shots[1:])]
    if any(d < FROZEN_DIFF for d in diffs):
        raise SmokeFailure("picture stopped changing (shot diffs " + ", ".join(f"{d:.1f}" for d in diffs) + ")")
    share = flows.window_share(before, after)
    summary = f"{split} interp={share:.4f} insns={after['insns'] - before['insns']} twoplayr={twoplayr[:2]}"
    if share >= INTERP_MAX:
        raise SmokeFailure(f"interpreted share too high; {summary}")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", required=True)
    ap.add_argument("--cue", required=True)
    ap.add_argument("--port", type=int, default=psxdbg.DEFAULT_PORT)
    ap.add_argument("--timeout", type=float, default=420.0)
    ap.add_argument("--out", default="")
    ap.add_argument("--game", default=os.path.join(REPO_ROOT, "game.toml"))
    args = ap.parse_args(argv)

    if psxdbg.port_in_use(args.port):
        return _fail(f"port {args.port} busy - another runtime running?")
    if not os.path.isfile(args.exe):
        return _fail(f"exe not found: {args.exe}")
    out_dir = os.path.abspath(args.out or os.path.join(
        os.environ.get("TEMP", REPO_ROOT), "mp-" + time.strftime("%Y%m%d-%H%M%S")))
    if not out_dir.isascii():
        return _fail(f"out dir must be an ASCII path: {out_dir}")
    os.makedirs(out_dir, exist_ok=True)
    cache = os.path.join(os.path.dirname(os.path.abspath(args.exe)), "cache", GAME_ID)
    shutil.rmtree(cache, ignore_errors=True)
    if os.path.exists(cache):
        return _fail(f"could not remove the runtime overlay cache (files locked?): {cache}")

    print(f"mp_smoke: out={out_dir}", flush=True)
    proc = psxrun.launch(args.exe, args.cue, args.game, args.port, out_dir,
                         env_extra={"PSX_OVERLAY_AUTOCOMPILE_OFF": "1"})
    try:
        summary = check_mp(proc, args.port, out_dir, time.monotonic() + args.timeout)
        print(f"mp_smoke: OK {summary}")
        return 0
    except SmokeFailure as exc:
        return _fail(str(exc))
    except Exception as exc:  # noqa: BLE001 - keep the one-line contract
        return _fail(f"unexpected error: {type(exc).__name__}: {exc}")
    finally:
        try:
            psxdbg.send("clear_input", port=args.port, timeout=2.0)
        except ConnectionError:
            pass
        psxrun.shutdown(proc, args.port)


if __name__ == "__main__":
    sys.exit(main())
