"""Intro smoke test: the intro FMV decodes and is audible.

Usage (from anywhere):
    py -3 tests/smoke/intro_smoke.py --exe PATH --cue PATH [--port 4370]
                                     [--timeout 150] [--out DIR] [--game game.toml]

Runs without turbo up to FMV_FRAME (inside the historical intro film), then
checks that MDEC keeps receiving video data and that the last AUDIO_SECONDS of
SPU output are louder than RMS_MIN. Exit 0/1, one-line reason on stderr.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psxdbg  # noqa: E402
import psxrun  # noqa: E402
import wavcheck  # noqa: E402

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FMV_FRAME = 2000
RMS_MIN = 200.0
AUDIO_SECONDS = 2
SAMPLE_RATE = 44100
SPU_OUT_TAP = 0  # audio_trace.h AUDIO_TAP_SPU_OUT; recorded before the host device (SDL dummy driver is fine)


def _fail(msg):
    print(f"intro_smoke: FAIL: {msg}", file=sys.stderr)
    return 1


def _mdec_words(port):
    # decode_macroblocks is reset per decoded picture; dma_in_words counts per
    # film and restarts near zero when the next film starts.
    return int(psxdbg.send("mdec_state", port=port)["dma_in_words"])


def check_intro(proc, port, out_dir, deadline):
    psxrun.wait_for_ping(proc, port, deadline)
    psxrun.wait_frame(port, FMV_FRAME, deadline)
    m1 = _mdec_words(port)
    time.sleep(2.0)
    m2 = _mdec_words(port)
    if m2 == m1:   # a drop means the next film started, which is decoding too
        raise psxrun.SmokeFailure(f"video not decoding (mdec dma_in_words {m1} -> {m2})")
    wav = os.path.join(out_dir, "intro.wav").replace("\\", "/")
    # audio_wav with start < 0 dumps from the OLDEST sample in the ring; the
    # newest window starts at the tap's head (audio_stats taps[].frames) - count.
    count = AUDIO_SECONDS * SAMPLE_RATE
    head = int(psxdbg.send("audio_stats", port=port)["taps"][SPU_OUT_TAP]["frames"])
    reply = psxdbg.send("audio_wav", port=port, path=wav, tap=SPU_OUT_TAP,
                        start=max(0, head - count), count=count)
    if not reply.get("ok"):
        raise psxrun.SmokeFailure(f"audio_wav failed: {reply.get('err', reply)}")
    rms = wavcheck.wav_rms(wav)
    if rms == 0.0:
        raise psxrun.SmokeFailure("audio tap silent (muted?)")
    if rms < RMS_MIN:
        raise psxrun.SmokeFailure(f"audio too quiet (rms={rms:.1f})")
    return m1, m2, rms


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", required=True)
    ap.add_argument("--cue", required=True)
    ap.add_argument("--port", type=int, default=psxdbg.DEFAULT_PORT)
    ap.add_argument("--timeout", type=float, default=150.0)
    ap.add_argument("--out", default="")
    ap.add_argument("--game", default=os.path.join(REPO_ROOT, "game.toml"))
    args = ap.parse_args(argv)

    if psxdbg.port_in_use(args.port):
        return _fail(f"port {args.port} busy - another runtime running?")
    if not os.path.isfile(args.exe):
        return _fail(f"exe not found: {args.exe}")
    out_dir = os.path.abspath(args.out or os.path.join(
        os.environ.get("TEMP", REPO_ROOT), "intro-" + time.strftime("%Y%m%d-%H%M%S")))
    if not out_dir.isascii():
        return _fail(f"out dir must be an ASCII path: {out_dir}")
    os.makedirs(out_dir, exist_ok=True)

    print(f"intro_smoke: out={out_dir}")
    proc = psxrun.launch(args.exe, args.cue, args.game, args.port, out_dir)
    try:
        m1, m2, rms = check_intro(proc, args.port, out_dir, time.monotonic() + args.timeout)
        print(f"intro_smoke: OK mdec dma_in_words {m1}->{m2} rms={rms:.1f}")
        return 0
    except psxrun.SmokeFailure as exc:
        return _fail(str(exc))
    except Exception as exc:  # noqa: BLE001 - keep the one-line contract
        return _fail(f"unexpected error: {type(exc).__name__}: {exc}")
    finally:
        psxrun.shutdown(proc, args.port)


if __name__ == "__main__":
    sys.exit(main())
