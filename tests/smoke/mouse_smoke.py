"""Mouse-look smoke test: the mouse package turns and aims the player, nothing else.

The runtime's mouse capture is off under debug input, so the test feeds mouse
counts through the plugin's debug command (mod_cmd moh_mouse "move dx dy"),
which drains on VBlank exactly where policy motion lands. Three runs, each
from boot with its own memory cards:

1. Package on, Mission 1 Level 1: exact yaw per count; in aim mode (R2) each
   crosshair coordinate moves by an eighth of its rate and, past its limit,
   the view turns (X) or the camera tilts (Y); releasing R2 centres the
   crosshair and, as the game does for an analog pad, keeps the tilt;
   vertical motion outside aim mode, and any motion during the pause, is
   dropped; all three hook sites run natively.
2. Package on, split screen: no hook fires, motion is dropped.
3. Package off, Mission 1 Level 1: motion does nothing.

Pad 1 goes through the virtual host gamepad while the package is on (see
psxrun.input_layer). Prints one line: mouse_smoke: OK ... or FAIL: <reason>.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flows  # noqa: E402
import modstate  # noqa: E402
import moh  # noqa: E402
import mp_smoke  # noqa: E402
import psxdbg  # noqa: E402
import psxrun  # noqa: E402

SmokeFailure = psxrun.SmokeFailure
REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SENSITIVITY = 40
RATE_MAX = 15728640       # MOH_LOOK_RATE_MAX in src/mouse/mouselook.h
SETTLE_SECS = 1.0         # long enough for a few game frames at 25 Hz
AIM_SECS = 0.5
RELEASE_SECS = 1.5
PAUSE_SECS = 1.5
LEVEL_SECS = 300.0
HOOK_SPAN = 0x40          # dirty_ram_stats window around each hook site
HOOKS = ("yaw", "aim_x", "aim_y")


def s32(value):
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


def expected_yaw(counts, sens):
    return counts * sens * 1024


def _aim_rate(counts, sens, per_fixed):
    return max(-RATE_MAX, min(RATE_MAX, counts * sens * 1024 * per_fixed))


def expected_x_rate(counts, sens):
    return _aim_rate(counts, sens, moh.AIM_X_RATE_PER_FIXED)


def expected_y_rate(counts, sens):
    return _aim_rate(counts, sens, moh.AIM_Y_RATE_PER_FIXED)


def crosshair_after(pitch, rate):
    return pitch + (rate >> 3)


def _fail(msg):
    print(f"mouse_smoke: FAIL: {msg}")
    return 1


def player(port):
    owner = psxrun.read_u32(port, moh.PLAYER_OWNER_PTR_ADDR)
    return psxrun.read_u32(port, owner + moh.PLAYER_PTR_OFFSET)


def read_s32(port, addr):
    return s32(psxrun.read_u32(port, addr))


def counter(port, name):
    reply = psxdbg.send("mod_counters", port=port, timeout=10.0)
    return next((c["count"] for c in reply.get("counters", []) if c["name"] == name), 0)


def move(port, dx, dy):
    reply = psxdbg.send("mod_cmd", port=port, name="moh_mouse", args=f"move {dx} {dy}", timeout=10.0)
    if reply.get("result") != 0:
        raise SmokeFailure(f"mod_cmd moh_mouse refused: {reply}")


def expect(what, got, want):
    if got != want:
        raise SmokeFailure(f"{what}: got {got}, expected {want}")


def into_level(proc, port, out_dir, deadline):
    base = flows.boot_to_menu(proc, port, deadline)
    flows.start_new_game(port, base, deadline)
    flows.wait_until_in_level(port, out_dir, deadline)
    time.sleep(3.0)
    return player(port)


def check_on(proc, port, out_dir, deadline):
    pl = into_level(proc, port, out_dir, deadline)
    yaw_addr, pitch_addr, tilt_addr = (pl + moh.PLAYER_YAW_OFFSET, pl + moh.PLAYER_PITCH_OFFSET,
                                       pl + moh.PLAYER_TILT_OFFSET)
    yaw0 = read_s32(port, yaw_addr)
    time.sleep(SETTLE_SECS)
    expect("yaw at rest", read_s32(port, yaw_addr), yaw0)

    move(port, 100, 0)
    time.sleep(SETTLE_SECS)
    expect("yaw after move 100 0", s32(read_s32(port, yaw_addr) - yaw0), expected_yaw(100, SENSITIVITY))
    yaw1 = read_s32(port, yaw_addr)

    aim_x_addr = pl + moh.PLAYER_AIM_X_OFFSET
    psxrun.hold_buttons(port, "r2")
    time.sleep(AIM_SECS)
    expect("crosshair entering aim mode", read_s32(port, pitch_addr), 0)
    tilt0, aim_x0 = read_s32(port, tilt_addr), read_s32(port, aim_x_addr)
    move(port, 0, -20)
    time.sleep(SETTLE_SECS)
    pitch = crosshair_after(0, expected_y_rate(-20, SENSITIVITY))
    expect("crosshair after move 0 -20", read_s32(port, pitch_addr), pitch)
    expect("camera tilt within the crosshair limit", read_s32(port, tilt_addr), tilt0)
    move(port, 0, -100000)
    time.sleep(SETTLE_SECS)
    expect("crosshair after a big upward move", read_s32(port, pitch_addr), moh.PITCH_MIN)
    tilt = tilt0 - (expected_y_rate(-100000, SENSITIVITY) >> 1)
    expect("camera tilt past the crosshair limit", read_s32(port, tilt_addr), tilt)
    move(port, 0, 20)
    time.sleep(SETTLE_SECS)
    expect("crosshair after move 0 20", read_s32(port, pitch_addr),
           crosshair_after(moh.PITCH_MIN, expected_y_rate(20, SENSITIVITY)))
    expect("yaw while aiming without x motion", read_s32(port, yaw_addr), yaw1)
    move(port, 20, 0)
    time.sleep(SETTLE_SECS)
    aim_x = crosshair_after(aim_x0, expected_x_rate(20, SENSITIVITY))
    expect("crosshair X after move 20 0", read_s32(port, aim_x_addr), aim_x)
    expect("yaw within the crosshair X limit", read_s32(port, yaw_addr), yaw1)
    move(port, 100000, 0)
    time.sleep(SETTLE_SECS)
    expect("yaw past the crosshair X limit", s32(read_s32(port, yaw_addr) - yaw1),
           expected_x_rate(100000, SENSITIVITY))

    psxrun.release(port)
    time.sleep(RELEASE_SECS)
    expect("crosshair after releasing R2", read_s32(port, pitch_addr), 0)
    # With an analog pad the game keeps the tilt after aiming (a digital pad
    # recentres it); the package presents an analog pad.
    expect("camera tilt after releasing R2", read_s32(port, tilt_addr), tilt)

    move(port, 0, 50)
    time.sleep(SETTLE_SECS)
    psxrun.hold_buttons(port, "r2")
    time.sleep(AIM_SECS)
    expect("crosshair after vertical motion outside aim mode", read_s32(port, pitch_addr), 0)
    expect("camera tilt after vertical motion outside aim mode", read_s32(port, tilt_addr), tilt)
    psxrun.release(port)
    time.sleep(SETTLE_SECS)

    yaw2 = read_s32(port, yaw_addr)
    dropped = counter(port, "moh_mouse.dropped")
    psxrun.press(port, "start")
    time.sleep(PAUSE_SECS)
    move(port, 300, 0)
    time.sleep(SETTLE_SECS)
    if counter(port, "moh_mouse.dropped") <= dropped:
        raise SmokeFailure("motion during the pause was not dropped (moh_mouse.dropped unchanged)")
    psxrun.press(port, "start")
    time.sleep(PAUSE_SECS)
    expect("yaw after the pause", read_s32(port, yaw_addr), yaw2)

    for name, pc in (("yaw", moh.YAW_STORE_PC), ("aim x", moh.AIM_X_RATE_PC), ("aim y", moh.AIM_Y_RATE_PC)):
        reply = psxdbg.send("dirty_ram_stats", port=port, lo="0x%08X" % (pc - HOOK_SPAN),
                            hi="0x%08X" % (pc + HOOK_SPAN), timeout=10.0)
        if reply.get("per_pc"):
            raise SmokeFailure(f"{name} hook site runs interpreted: {reply['per_pc'][:3]}")
    hooks = [counter(port, f"moh_mouse.{n}_hook") for n in HOOKS]
    if not all(hooks):
        raise SmokeFailure(f"hook counters {'/'.join(HOOKS)} = {hooks}")
    return (f"yaw=+{expected_yaw(100, SENSITIVITY)} crosshair={pitch}/{moh.PITCH_MIN} "
            f"tilt=+{tilt - tilt0} aim_x={aim_x - aim_x0} hooks={'/'.join(map(str, hooks))}")


def check_split(proc, port, out_dir, deadline):
    base = flows.boot_to_menu(proc, port, deadline)
    mp_smoke.plug_in_pad2(port)
    flows.goto(port, moh.MENU_RING.index("MULTIPLAYER"), base, deadline)
    psxrun.press(port, "cross")
    time.sleep(mp_smoke.MENU_SECS)
    flows.advance_until_level(port, deadline, file_id=moh.LEVEL2P_FILE_ID)
    flows.wait_until_in_level(port, out_dir, deadline)
    dropped = counter(port, "moh_mouse.dropped")
    move(port, 500, 0)
    time.sleep(SETTLE_SECS)
    for name in HOOKS:
        expect(f"{name} hooks in the split screen", counter(port, f"moh_mouse.{name}_hook"), 0)
    if counter(port, "moh_mouse.dropped") <= dropped:
        raise SmokeFailure("split-screen motion was not dropped")
    return "split=no hook"


def check_off(proc, port, out_dir, deadline):
    pl = into_level(proc, port, out_dir, deadline)
    yaw_addr = pl + moh.PLAYER_YAW_OFFSET
    yaw0 = read_s32(port, yaw_addr)
    move(port, 300, 0)
    time.sleep(SETTLE_SECS)
    expect("yaw with the package off", read_s32(port, yaw_addr), yaw0)
    names = [c["name"] for c in psxdbg.send("mod_counters", port=port, timeout=10.0).get("counters", [])]
    if any(n.startswith("moh_mouse.") for n in names):
        raise SmokeFailure(f"package off but plugin counters exist: {names}")
    return "off=inert"


def run(args, label, check, package):
    out_dir = os.path.join(args.out_root, label)
    os.makedirs(out_dir, exist_ok=True)
    build_dir = os.path.dirname(os.path.abspath(args.exe))
    layer = psxrun.INPUT_LAYER
    with (modstate.enabled(build_dir, {"sensitivity": SENSITIVITY, "invert_y": False}) if package
          else _nothing()):
        psxrun.INPUT_LAYER = "host" if package else None
        proc = psxrun.launch(args.exe, args.cue, args.game, args.port, out_dir)
        try:
            return check(proc, args.port, out_dir, time.monotonic() + LEVEL_SECS)
        finally:
            try:
                psxdbg.send("clear_input", port=args.port, timeout=2.0)
            except ConnectionError:
                pass
            psxrun.shutdown(proc, args.port)
            psxrun.INPUT_LAYER = layer


class _nothing:
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
        os.environ.get("TEMP", REPO_ROOT), "mouse-" + time.strftime("%Y%m%d-%H%M%S")))
    print(f"mouse_smoke: out={args.out_root}", flush=True)
    try:
        parts = [run(args, "on", check_on, True),
                 run(args, "split", check_split, True),
                 run(args, "off", check_off, False)]
        print("mouse_smoke: OK " + " ".join(parts))
        return 0
    except SmokeFailure as exc:
        return _fail(str(exc))
    except Exception as exc:  # noqa: BLE001 - keep the one-line contract
        return _fail(f"unexpected error: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    sys.exit(main())
