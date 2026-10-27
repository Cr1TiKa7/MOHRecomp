"""PGXP smoke test: with the PGXP package on, enough triangles get sub-pixel precision; 4K holds.

Prints one line: pgxp_smoke: OK ... or pgxp_smoke: FAIL: <reason>.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SCALE_4K = 9   # 2160 lines / 240 reference lines, rounded up


def _tris(reply):
    p = reply["pgxp"]
    return p["tri_precise"], p["tri_mixed"], p["tri_native"]


def corrected_share(after, before=None):
    """Share of triangles with PGXP precision (precise or mixed) in geom_correction
    replies; with `before`, only the triangles drawn between the two replies."""
    precise, mixed, native = _tris(after)
    if before is not None:
        b = _tris(before)
        precise, mixed, native = precise - b[0], mixed - b[1], native - b[2]
    total = precise + mixed + native
    if total <= 0:
        raise ValueError("no triangles drawn in the window")
    return (precise + mixed) / total


def is_4k(video_info):
    return video_info.get("effective_scale") == SCALE_4K and video_info.get("gl_clamp_reason") == 0


# --------------------------------------------------------------------------
# Runtime check
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
# PGXP is left to its default (the title ships it on); only the resolution is chosen.
FEATURES = [("psx.enhancement.internal-resolution", "internal-resolution", {"resolution": "4k"})]
MOVE_SECS = 2.0


def _fail(msg):
    print(f"pgxp_smoke: FAIL: {msg}")
    return 1


def check(proc, port, out_dir, deadline):
    base = flows.boot_to_menu(proc, port, deadline)
    flows.start_new_game(port, base, deadline)
    flows.wait_until_in_level(port, out_dir, deadline)
    time.sleep(2.0)
    info = psxdbg.send("video_info", port=port, timeout=10.0)
    if not is_4k(info):
        raise SmokeFailure(f"4K not reached: effective_scale {info.get('effective_scale')}, "
                           f"gl_clamp_reason {info.get('gl_clamp_reason')}")
    before = psxdbg.send("geom_correction", port=port, timeout=10.0)
    for button in ("right", "up"):
        psxrun.hold_buttons(port, button)
        time.sleep(MOVE_SECS)
        psxrun.release(port)
    after = psxdbg.send("geom_correction", port=port, timeout=10.0)
    try:
        share = corrected_share(after, before)
    except ValueError:
        raise SmokeFailure("no PGXP-corrected or native triangles counted: PGXP is off") from None
    if share < moh.PGXP_MIN_CORRECTED:
        raise SmokeFailure(f"corrected share {share:.3f} < {moh.PGXP_MIN_CORRECTED}")
    flows.shot(port, out_dir, "pgxp_4k.png")
    return f"share={share:.3f} scale={info['effective_scale']}"


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
    out_dir = os.path.abspath(args.out or os.path.join(
        os.environ.get("TEMP", REPO_ROOT), "pgxp-" + time.strftime("%Y%m%d-%H%M%S")))
    os.makedirs(out_dir, exist_ok=True)
    print(f"pgxp_smoke: out={out_dir}", flush=True)
    with modstate.enabled(os.path.dirname(os.path.abspath(args.exe)), None, features=FEATURES):
        proc = psxrun.launch(args.exe, args.cue, args.game, args.port, out_dir,
                             env_extra={"PSX_OVERLAY_AUTOCOMPILE_OFF": "1"})
        try:
            print("pgxp_smoke: OK " + check(proc, args.port, out_dir, time.monotonic() + 600))
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
