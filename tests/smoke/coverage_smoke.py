"""Coverage smoke test: menu code runs natively without runtime autocompile.

Usage (from anywhere):
    py -3 tests/smoke/coverage_smoke.py --exe PATH --cue PATH [--port 4370]
                                        [--timeout 240] [--out DIR] [--game game.toml]
                                        [--max-interp 0.01]

Deletes the runtime's overlay DLL cache for this game, starts with
PSX_OVERLAY_AUTOCOMPILE_OFF=1, fast-forwards to the main menu and walks the
ring. Fails when the loader is not counting or runtime DLLs ran, when the
interpreted share of dispatches reaches --max-interp, or when no statically
linked overlay code ran. Finally starts NEW GAME, waits until LEVEL.BIN has
replaced SHELL.BIN at 0x80039F28 and checks the game keeps running (the static
SHELL code must not misfire on it). Exit 0/1, one-line reason on stderr.
"""

import argparse
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import menu_smoke  # noqa: E402
import moh  # noqa: E402
import psxdbg  # noqa: E402
import psxrun  # noqa: E402

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
GAME_ID = "SLES-02470"
NEW_GAME_WAIT_SECS = 15.0
LEVEL_LOAD_SECS = 120.0   # FMVs + briefing + loading took ~40 s with X every 3 s
NUDGE_SECS = 3.0
SmokeFailure = psxrun.SmokeFailure


def _fail(msg):
    print(f"coverage_smoke: FAIL: {msg}", file=sys.stderr)
    return 1


def interp_share(status, static_hits):
    """(interpreted share, native dispatches, interpreted dispatches).

    overlay_loader_status.dispatch_native only counts the runtime DLL path;
    dispatches served by the statically linked shard are reported separately
    by overlay_static_entries.total_hits.
    """
    native = int(status["dispatch_native"]) + static_hits
    interp = int(status["dispatch_interp_fallback"])
    total = native + interp
    return (interp / total if total else 1.0), native, interp


def validate_loader(status):
    """The loader must be counting, and no runtime DLL may have supplied native code."""
    if int(status.get("active", 0)) != 1:
        raise SmokeFailure("overlay loader inactive ([runtime] overlay_cache off?) - "
                           "dispatch counters would read 0 and fake full coverage")
    if int(status.get("loads", 0)) or int(status.get("dispatch_native", 0)):
        raise SmokeFailure(f"runtime overlay DLLs ran (loads={status.get('loads')}, "
                           f"dispatch_native={status.get('dispatch_native')}) - stale cache?")


def advance_until_level(port, deadline, nudge_secs=NUDGE_SECS):
    """Press X through the post-NEW GAME FMVs and briefing until LEVEL.BIN is in place."""
    last = None
    while time.monotonic() < deadline:
        try:
            last = psxrun.read_u32(port, moh.SHELL_LOAD_ADDR)
            if last == moh.LEVEL_FILE_ID:
                return
            psxrun.press(port, "cross")
        except psxrun.TRANSIENT:
            pass
        time.sleep(nudge_secs)
    seen = "unreadable" if last is None else f"0x{last:08X}"
    raise SmokeFailure(f"LEVEL.BIN never replaced SHELL.BIN at 0x{moh.SHELL_LOAD_ADDR:08X} "
                       f"(overlay word {seen})")


def check_coverage(proc, port, deadline, max_interp):
    psxrun.wait_for_ping(proc, port, deadline)
    psxdbg.send("turbo", port=port, enabled=1)
    psxrun.wait_frame(port, moh.MENU_READY_FRAME, deadline)
    psxdbg.send("turbo", port=port, enabled=0)
    base, _ = menu_smoke.walk_ring(port, deadline)

    static = psxdbg.send("overlay_static_entries", port=port)
    static_hits = int(static.get("total_hits", 0)) if static.get("ok") else 0
    status = psxdbg.send("overlay_loader_status", port=port)
    validate_loader(status)
    share, native, interp = interp_share(status, static_hits)
    summary = (f"interp={share:.4f} native={native} interp_n={interp} "
               f"static_entries={static.get('entries', 0)} static_hits={static_hits}")

    # NEW GAME replaces SHELL.BIN with LEVEL.BIN at the same base (verified in
    # RAM) after two FMVs and a three-page briefing that waits for X. The
    # static SHELL code must not misfire on it (byte guards). Wait for the swap
    # first, so a swallowed X or a stuck load cannot pass as "frames advance".
    menu_smoke.goto(port, moh.MENU_RING.index("NEW GAME"), base, deadline)
    psxrun.press(port, "cross")
    try:
        advance_until_level(port, min(deadline, time.monotonic() + LEVEL_LOAD_SECS))
    except SmokeFailure as exc:
        raise SmokeFailure(f"{exc}; {summary}") from exc
    _, before = psxrun.read_frame(port, deadline)
    time.sleep(NEW_GAME_WAIT_SECS)
    psxrun.check_alive(proc)
    _, after = psxrun.read_frame(port, deadline)
    if after <= before:
        raise SmokeFailure(f"game stalled after LEVEL.BIN loaded (frame {before} -> {after}); {summary}")
    if share >= max_interp:
        raise SmokeFailure(f"interpreted share too high; {summary}")
    if static_hits == 0:
        raise SmokeFailure(f"no statically linked overlay code ran "
                           f"({static.get('error', 'no hits')}); {summary}")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", required=True)
    ap.add_argument("--cue", required=True)
    ap.add_argument("--port", type=int, default=psxdbg.DEFAULT_PORT)
    ap.add_argument("--timeout", type=float, default=240.0)
    ap.add_argument("--out", default="")
    ap.add_argument("--game", default=os.path.join(REPO_ROOT, "game.toml"))
    ap.add_argument("--max-interp", type=float, default=0.01)
    args = ap.parse_args(argv)

    if psxdbg.port_in_use(args.port):
        return _fail(f"port {args.port} busy - another runtime running?")
    if not os.path.isfile(args.exe):
        return _fail(f"exe not found: {args.exe}")
    out_dir = os.path.abspath(args.out or os.path.join(
        os.environ.get("TEMP", REPO_ROOT), "coverage-" + time.strftime("%Y%m%d-%H%M%S")))
    if not out_dir.isascii():
        return _fail(f"out dir must be an ASCII path: {out_dir}")
    os.makedirs(out_dir, exist_ok=True)

    # DLLs compiled by earlier runs would still load without autocompile and
    # fake native coverage.
    cache = os.path.join(os.path.dirname(os.path.abspath(args.exe)), "cache", GAME_ID)
    shutil.rmtree(cache, ignore_errors=True)
    if os.path.exists(cache):
        return _fail(f"could not remove the runtime overlay cache (files locked?): {cache}")

    print(f"coverage_smoke: out={out_dir}")
    proc = psxrun.launch(args.exe, args.cue, args.game, args.port, out_dir,
                         env_extra={"PSX_OVERLAY_AUTOCOMPILE_OFF": "1"})
    try:
        summary = check_coverage(proc, args.port, time.monotonic() + args.timeout, args.max_interp)
        print(f"coverage_smoke: OK {summary}")
        return 0
    except SmokeFailure as exc:
        return _fail(str(exc))
    except Exception as exc:  # noqa: BLE001 - keep the one-line contract
        return _fail(f"unexpected error: {type(exc).__name__}: {exc}")
    finally:
        psxrun.shutdown(proc, args.port)


if __name__ == "__main__":
    sys.exit(main())
