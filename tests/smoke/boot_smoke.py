"""Boot smoke test: start the runtime hidden, wait for a real frame, quit.

Usage (from anywhere):
    py -3 tests/smoke/boot_smoke.py --exe PATH --cue PATH [--port 4370]
                                    [--timeout 90] [--out DIR] [--game game.toml]

Exit 0 when the frame counter advances and a screenshot with at least
MIN_COLORS distinct colors was captured; exit 1 otherwise (one-line reason
on stderr). The runtime instance started here is always shut down.
"""

import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pngcheck  # noqa: E402
import psxdbg  # noqa: E402

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
MIN_COLORS = 16
POLL_SECS = 0.5
SHOT_EVERY_SECS = 2.0


class SmokeFailure(Exception):
    pass


def _fail(msg):
    print(f"boot_smoke: FAIL: {msg}", file=sys.stderr)
    return 1


def _wait_for_ping(proc, port, deadline):
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SmokeFailure(f"runtime exited early with code {proc.returncode}")
        try:
            return psxdbg.send("ping", port=port, timeout=2.0)
        except ConnectionError:
            time.sleep(POLL_SECS)
    raise SmokeFailure("debug port never answered")


def _check_frames_advance(port):
    # "ping" is answered by the server's I/O thread without a frame counter;
    # "frame" goes through the emulation thread and reports emulated frames.
    first = psxdbg.send("frame", port=port)
    time.sleep(2.0)
    second = psxdbg.send("frame", port=port)
    if second["frame"] <= first["frame"]:
        raise SmokeFailure(f"frame counter stuck at {first['frame']}")
    return second


def _wait_for_real_frame(proc, port, out_dir, deadline):
    n = 0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SmokeFailure(f"runtime exited early with code {proc.returncode}")
        shot = os.path.join(out_dir, f"shot-{n:03d}.png").replace("\\", "/")
        reply = psxdbg.send("screenshot", port=port, path=shot)
        if reply.get("ok") and os.path.isfile(shot):
            colors = pngcheck.distinct_colors(shot, limit=MIN_COLORS)
            if colors >= MIN_COLORS:
                return shot, reply
        n += 1
        time.sleep(SHOT_EVERY_SECS)
    raise SmokeFailure(f"no non-trivial frame (>= {MIN_COLORS} colors) within timeout")


def _shutdown(proc, port):
    if proc.poll() is None:
        try:
            psxdbg.send("quit", port=port, timeout=2.0)
        except ConnectionError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", required=True)
    ap.add_argument("--cue", required=True)
    ap.add_argument("--port", type=int, default=psxdbg.DEFAULT_PORT)
    ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--out", default="")
    ap.add_argument("--game", default=os.path.join(REPO_ROOT, "game.toml"))
    args = ap.parse_args(argv)

    if psxdbg.port_in_use(args.port):
        return _fail(f"port {args.port} busy - another runtime running?")
    if not os.path.isfile(args.exe):
        return _fail(f"exe not found: {args.exe}")

    out_dir = args.out or os.path.join(
        os.environ.get("TEMP", REPO_ROOT), "smoke-" + time.strftime("%Y%m%d-%H%M%S"))
    memcards = os.path.join(out_dir, "memcards")
    os.makedirs(memcards, exist_ok=True)

    cmd = [os.path.abspath(args.exe), "--game", os.path.abspath(args.game), "--disc", args.cue,
           "--no-launcher", "--hidden-window", "--debug-port", str(args.port),
           "--memcard-dir", memcards]
    env = dict(os.environ, PSX_HOST_MUTE="1")
    print(f"boot_smoke: out={out_dir}")
    with open(os.path.join(out_dir, "runtime.log"), "wb") as log:
        proc = subprocess.Popen(cmd, cwd=os.path.dirname(os.path.abspath(args.exe)),
                                stdout=log, stderr=subprocess.STDOUT, env=env)
        try:
            deadline = time.monotonic() + args.timeout
            first = _wait_for_ping(proc, args.port, deadline)
            print(f"boot_smoke: first ping {first}")
            later = _check_frames_advance(args.port)
            shot, reply = _wait_for_real_frame(proc, args.port, out_dir, deadline)
            print(f"boot_smoke: OK frame={later['frame']} "
                  f"shot={shot} size={reply.get('width')}x{reply.get('height')}")
            return 0
        except SmokeFailure as exc:
            return _fail(str(exc))
        finally:
            _shutdown(proc, args.port)


if __name__ == "__main__":
    sys.exit(main())
