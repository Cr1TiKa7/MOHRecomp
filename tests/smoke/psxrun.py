"""Shared helpers for driving a running Medal_of_Honor_PAL_Recompiled instance (stdlib only).

Launching, liveness, frame counter, pad input, RAM reads and shutdown, used by
every smoke test. All remote calls go through psxdbg (one request per TCP
connection).
"""

import os
import subprocess
import time
import zlib

import psxdbg

POLL_SECS = 0.5
# Errors a cold-starting or busy runtime can produce for a single request;
# callers retry them until their deadline instead of aborting the run.
TRANSIENT = (ConnectionError, ValueError, KeyError, OSError, IndexError, zlib.error)

# PS1 digital pad bits; the debug server takes them inverted (0 = pressed).
BUTTONS = {
    "select": 0x0001, "l3": 0x0002, "r3": 0x0004, "start": 0x0008,
    "up": 0x0010, "right": 0x0020, "down": 0x0040, "left": 0x0080,
    "l2": 0x0100, "r2": 0x0200, "l1": 0x0400, "r1": 0x0800,
    "triangle": 0x1000, "circle": 0x2000, "cross": 0x4000, "square": 0x8000,
}


class SmokeFailure(Exception):
    pass


def mask(*names):
    held = 0
    for name in names:
        held |= BUTTONS[name]
    return 0xFFFF & ~held


def check_alive(proc):
    if proc.poll() is not None:
        raise SmokeFailure(f"runtime exited early with code {proc.returncode}")


def launch(exe, cue, game, port, out_dir, env_extra=None):
    """Start the runtime hidden with its own memory cards under out_dir.

    The runtime's cwd is the exe's directory, so every path is made absolute.
    stdout/stderr go to out_dir/runtime.log. SDL's dummy audio driver keeps the
    game silent on the host (PSX_HOST_MUTE is not read by this runtime); the
    SPU/CD/host audio taps that intro_smoke measures are recorded before the
    device, so they are unaffected.
    """
    _host_armed.discard(port)
    memcards = os.path.join(os.path.abspath(out_dir), "memcards")
    os.makedirs(memcards, exist_ok=True)
    cmd = [os.path.abspath(exe), "--game", os.path.abspath(game),
           "--disc", os.path.abspath(cue),
           "--no-launcher", "--hidden-window", "--debug-port", str(port),
           "--memcard-dir", memcards]
    env = dict(os.environ, SDL_AUDIODRIVER="dummy", **(env_extra or {}))
    with open(os.path.join(out_dir, "runtime.log"), "wb") as log:
        return subprocess.Popen(cmd, cwd=os.path.dirname(os.path.abspath(exe)),
                                stdout=log, stderr=subprocess.STDOUT, env=env)


def wait_for_ping(proc, port, deadline):
    while time.monotonic() < deadline:
        check_alive(proc)
        try:
            return psxdbg.send("ping", port=port, timeout=2.0)
        except ConnectionError:
            time.sleep(POLL_SECS)
    raise SmokeFailure("debug port never answered")


def read_frame(port, deadline):
    last = "no reply"
    while time.monotonic() < deadline:
        try:
            reply = psxdbg.send("frame", port=port)
            return reply, int(reply["frame"])
        except TRANSIENT as exc:
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(POLL_SECS)
    raise SmokeFailure(f"frame command never answered ({last})")


def wait_frame(port, frame, deadline):
    while time.monotonic() < deadline:
        try:
            current = int(psxdbg.send("frame", port=port)["frame"])
            if current >= frame:
                return current
        except TRANSIENT:
            pass
        time.sleep(POLL_SECS)
    raise TimeoutError(f"frame {frame} not reached before deadline")


# Centred sticks for every pad-1 input. Without explicit axes the debug
# override copies the d-pad onto the left stick of an analog P1 (the mouse
# package presents one), so the game would see each direction twice.
CENTRED = {"lx": 128, "ly": 128, "rx": 128, "ry": 128}
HOST_PRESS_MARGIN_SECS = 0.02


def input_layer(environ):
    """Pad-1 input path: None = plain debug override (default), "host" = the
    virtual host gamepad, which runs through the normal input chain. With the
    mouse package on, the plain override counts every menu step twice (the
    runtime's override and the package's analog P1 do not mix); the host
    gamepad counts once, like a real pad. Set MOH_SMOKE_PAD_LAYER=host then."""
    layer = environ.get("MOH_SMOKE_PAD_LAYER") or None
    if layer not in (None, "host"):
        raise ValueError(f"MOH_SMOKE_PAD_LAYER must be empty or 'host', not {layer!r}")
    return layer


INPUT_LAYER = input_layer(os.environ)
# Ports whose runtime has the virtual gamepad plugged in. Its first request
# connects it, and an input sent with that request was lost once, so the pad
# is first armed neutral and given HOST_ARM_SECS. launch() forgets the port.
HOST_ARM_SECS = 0.5
_host_armed = set()


def _host_input(port, buttons):
    if port not in _host_armed:
        psxdbg.send("set_input", port=port, layer="host", buttons=0xFFFF, **CENTRED)
        time.sleep(HOST_ARM_SECS)
        _host_armed.add(port)
    psxdbg.send("set_input", port=port, layer="host", buttons=buttons, **CENTRED)


def press(port, *names, frames=4):
    if INPUT_LAYER == "host":
        _host_input(port, mask(*names))
        time.sleep(frames / 50 + HOST_PRESS_MARGIN_SECS)
        _host_input(port, 0xFFFF)
        return
    psxdbg.send("press", port=port, buttons=mask(*names), frames=frames, **CENTRED)


def release(port):
    """Let go of every pad-1 button. Pad 2 stays plugged in; so does the
    virtual gamepad (clear_input would unplug it)."""
    if INPUT_LAYER == "host":
        _host_input(port, 0xFFFF)
        return
    psxdbg.send("clear_input", port=port, payload={"port": 1})


def hold_buttons(port, *names):
    """Hold the named pad-1 buttons until release()."""
    if INPUT_LAYER == "host":
        _host_input(port, mask(*names))
        return
    psxdbg.send("set_input", port=port, buttons=mask(*names), **CENTRED)


def read_bytes(port, addr, n):
    reply = psxdbg.send("read_ram", port=port, addr="0x%08X" % addr, len=n)
    return bytes.fromhex(reply["hex"])


def read_u8(port, addr):
    return read_bytes(port, addr, 1)[0]


def read_u32(port, addr):
    return int.from_bytes(read_bytes(port, addr, 4), "little")


def wait_u32(port, addr, value, deadline):
    """Poll the little-endian word at addr until it equals value."""
    last = None
    while time.monotonic() < deadline:
        try:
            last = read_u32(port, addr)
            if last == value:
                return
        except TRANSIENT:
            pass
        time.sleep(POLL_SECS)
    seen = "unreadable" if last is None else f"0x{last:08X}"
    raise TimeoutError(f"word at 0x{addr:08X} never became 0x{value:08X} (last {seen})")


def shutdown(proc, port):
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
