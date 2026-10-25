"""Level smoke test: Mission 1 Level 1 runs at full speed, natively, audibly and responsively.

Usage (from anywhere):
    py -3 tests/smoke/level_smoke.py --exe PATH --cue PATH [--port 4370]
                                     [--timeout 300] [--out DIR] [--game game.toml]
                                     [--autocompile on|off]

Boots into the menu, starts NEW GAME, presses through the briefing until
LEVEL.BIN is loaded, then measures inside the level: frame rate, SPU loudness,
the effect of holding UP compared with idling, and a SOAK_SECS input loop
(walk, turn, fire) during which the game must keep running. With
--autocompile off (default) the runtime DLL cache is deleted and runtime
compilation disabled, and the interpreted share of overlay dispatches over the
level window must stay below LEVEL_INTERP_MAX. Exit 0/1, one-line reason on stderr.
"""

import argparse
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flows  # noqa: E402
import psxdbg  # noqa: E402
import psxrun  # noqa: E402
import wavcheck  # noqa: E402

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
GAME_ID = "SLES-02470"
FPS_MIN = 48.0             # PAL 50 Hz with 4 % tolerance
FPS_WINDOW_SECS = 10.0
LEVEL_INTERP_MAX = 0.01
RMS_MIN = 200.0
SAMPLE_RATE = 44100
SPU_OUT_TAP = 0
MOVE_FACTOR = 1.5
SOAK_SECS = 120
IN_LEVEL_SECS = 90.0       # loading screen after LEVEL.BIN lands (>8 s when interpreted)
SOAK_STEPS = (("up", 2.0), ("right", 1.0), ("left", 1.0), ("r1", 0.3), ("square", 0.3))
SmokeFailure = psxrun.SmokeFailure


def _fail(msg):
    print(f"level_smoke: FAIL: {msg}", file=sys.stderr)
    return 1


_shot = flows.shot
_diff = flows.screen_diff


def _hold(port, names, secs):
    psxdbg.send("set_input", port=port, buttons=psxrun.mask(*names))
    try:
        time.sleep(secs)
    finally:
        psxdbg.send("clear_input", port=port)


def measure_fps(port, deadline):
    _, first = psxrun.read_frame(port, deadline)
    start = time.monotonic()
    time.sleep(FPS_WINDOW_SECS)
    _, last = psxrun.read_frame(port, deadline)
    return (last - first) / (time.monotonic() - start)


def measure_rms(port, out_dir):
    count = 2 * SAMPLE_RATE
    head = int(psxdbg.send("audio_stats", port=port)["taps"][SPU_OUT_TAP]["frames"])
    wav = os.path.join(out_dir, "level.wav").replace("\\", "/")
    reply = psxdbg.send("audio_wav", port=port, path=wav, tap=SPU_OUT_TAP,
                        start=max(0, head - count), count=count)
    if not reply.get("ok"):
        raise SmokeFailure(f"audio_wav failed: {reply.get('err', reply)}")
    return wavcheck.wav_rms(wav)


def measure_input(port, out_dir):
    """(move, idle): screen change while holding UP vs. while idling, same duration."""
    a = _shot(port, out_dir, "idle_a.png")
    time.sleep(3.0)
    b = _shot(port, out_dir, "idle_b.png")
    _hold(port, ("up",), 3.0)
    c = _shot(port, out_dir, "moved.png")
    return _diff(b, c), _diff(a, b)


def soak(proc, port, out_dir, deadline):
    end = time.monotonic() + SOAK_SECS
    next_check = time.monotonic() + 10
    next_shot = time.monotonic()
    _, last_frame = psxrun.read_frame(port, deadline)
    n = 0
    while time.monotonic() < end:
        for name, secs in SOAK_STEPS:
            _hold(port, (name,), secs)
        now = time.monotonic()
        if now >= next_check:
            psxrun.check_alive(proc)
            _, frame = psxrun.read_frame(port, deadline)
            if frame <= last_frame:
                raise SmokeFailure(f"level stalled during soak (frame {last_frame} -> {frame})")
            last_frame, next_check = frame, now + 10
        if now >= next_shot:
            _shot(port, out_dir, f"soak{n:02d}.png")
            n, next_shot = n + 1, now + 30


def check_level(proc, port, out_dir, deadline, autocompile_off):
    base = flows.boot_to_menu(proc, port, deadline)
    flows.start_new_game(port, base, deadline)
    flows.wait_until_in_level(port, out_dir, min(deadline, time.monotonic() + IN_LEVEL_SECS))
    before = flows.overlay_counters(port)

    fps = measure_fps(port, deadline)
    if fps < FPS_MIN:
        raise SmokeFailure(f"level runs at {fps:.1f} fps, need >= {FPS_MIN}")
    rms = measure_rms(port, out_dir)
    if rms < RMS_MIN:
        raise SmokeFailure(f"level audio too quiet (rms={rms:.1f})")
    move, idle = measure_input(port, out_dir)
    if move < MOVE_FACTOR * max(idle, 1.0):
        raise SmokeFailure(f"holding UP barely changed the view (move={move:.1f}, idle={idle:.1f})")
    soak(proc, port, out_dir, deadline)

    after = flows.overlay_counters(port)
    share = flows.window_share(before, after)
    insns = after["insns"] - before["insns"]
    summary = (f"fps={fps:.1f} interp={share:.4f} insns={insns} rms={rms:.1f} "
               f"move={move:.1f} idle={idle:.1f} soak={SOAK_SECS}s")
    if autocompile_off and share >= LEVEL_INTERP_MAX:
        raise SmokeFailure(f"interpreted share in the level too high; {summary}")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", required=True)
    ap.add_argument("--cue", required=True)
    ap.add_argument("--port", type=int, default=psxdbg.DEFAULT_PORT)
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--out", default="")
    ap.add_argument("--game", default=os.path.join(REPO_ROOT, "game.toml"))
    ap.add_argument("--autocompile", choices=("on", "off"), default="off")
    args = ap.parse_args(argv)

    if psxdbg.port_in_use(args.port):
        return _fail(f"port {args.port} busy - another runtime running?")
    if not os.path.isfile(args.exe):
        return _fail(f"exe not found: {args.exe}")
    out_dir = os.path.abspath(args.out or os.path.join(
        os.environ.get("TEMP", REPO_ROOT), "level-" + time.strftime("%Y%m%d-%H%M%S")))
    if not out_dir.isascii():
        return _fail(f"out dir must be an ASCII path: {out_dir}")
    os.makedirs(out_dir, exist_ok=True)

    env_extra = {}
    autocompile_off = args.autocompile == "off"
    if autocompile_off:
        cache = os.path.join(os.path.dirname(os.path.abspath(args.exe)), "cache", GAME_ID)
        shutil.rmtree(cache, ignore_errors=True)
        if os.path.exists(cache):
            return _fail(f"could not remove the runtime overlay cache (files locked?): {cache}")
        env_extra["PSX_OVERLAY_AUTOCOMPILE_OFF"] = "1"

    print(f"level_smoke: out={out_dir}")
    proc = psxrun.launch(args.exe, args.cue, args.game, args.port, out_dir, env_extra=env_extra)
    try:
        summary = check_level(proc, args.port, out_dir, time.monotonic() + args.timeout,
                              autocompile_off)
        print(f"level_smoke: OK {summary}")
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
