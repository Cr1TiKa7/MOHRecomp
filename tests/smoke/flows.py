"""Shared Medal of Honor game flows for the smoke tests (stdlib only).

Main-menu navigation, the way from boot into the menu and from NEW GAME into
Mission 1 Level 1, and the overlay dispatch counters used for coverage.
"""

import os
import struct
import time

import moh
import pngcheck
import psxdbg
import psxrun

SmokeFailure = psxrun.SmokeFailure
STEP_SECS = 1.5
ACTIVATION_TRIES = 10
NUDGE_SECS = 3.0
LEVEL_LOAD_SECS = 120.0   # FMVs + briefing + loading took ~15-40 s with X every 3 s
IN_LEVEL_DIFF = 40.0      # bright loading poster vs. the dark night level of M1L1


# --------------------------------------------------------------------------
# Main menu
# --------------------------------------------------------------------------

def entry_ptr(port):
    return struct.unpack("<I", psxrun.read_bytes(port, moh.MENU_ITEM_PTR_ADDR, 4))[0]


def menu_index(port, base):
    return moh.menu_index_from_ptr(entry_ptr(port), base)


def _step_right(port):
    psxrun.press(port, "right")
    time.sleep(STEP_SECS)
    return entry_ptr(port)


def walk_ring(port, deadline):
    """Wait until RIGHT moves the ring, walk it once.

    Returns (base, index): the entry-array base learned from the walk (lowest
    pointer = NEW GAME) and the index the ring ended on.
    """
    ring = len(moh.MENU_RING)
    start = None
    for _ in range(ACTIVATION_TRIES):
        if time.monotonic() > deadline:
            break
        before = entry_ptr(port)
        after = _step_right(port)
        if moh.is_ring_step(before, after):
            start = after
            break
    if start is None:
        raise SmokeFailure(f"menu never reacted to RIGHT within {ACTIVATION_TRIES} tries")
    seen = {start}
    ptr = start
    for _ in range(ring):
        nxt = _step_right(port)
        if not moh.is_ring_step(ptr, nxt):
            raise SmokeFailure(f"RIGHT moved the entry pointer {ptr:#010x} -> {nxt:#010x}")
        seen.add(nxt)
        ptr = nxt
    if ptr != start or len(seen) != ring:
        raise SmokeFailure(f"ring did not cycle through {ring} entries back to the start")
    base = min(seen)
    return base, moh.menu_index_from_ptr(ptr, base)


def goto(port, index, base, deadline):
    for _ in range(len(moh.MENU_RING)):
        if menu_index(port, base) == index:
            return
        if time.monotonic() > deadline:
            break
        _step_right(port)
    if menu_index(port, base) != index:
        raise SmokeFailure(f"could not reach menu entry {index}")


def boot_to_menu(proc, port, deadline):
    """Fast-forward from boot into the main menu; returns the learned entry base."""
    psxrun.wait_for_ping(proc, port, deadline)
    psxdbg.send("turbo", port=port, enabled=1)
    psxrun.wait_frame(port, moh.MENU_READY_FRAME, deadline)
    psxdbg.send("turbo", port=port, enabled=0)
    base, _ = walk_ring(port, deadline)
    return base


# --------------------------------------------------------------------------
# NEW GAME -> Mission 1 Level 1
# --------------------------------------------------------------------------

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


def shot(port, out_dir, name):
    path = os.path.join(out_dir, name).replace("\\", "/")
    reply = psxdbg.send("screenshot", port=port, path=path)
    if not reply.get("ok") or not os.path.isfile(path):
        raise SmokeFailure(f"screenshot failed: {reply.get('error', reply)}")
    return path


def screen_diff(a, b):
    try:
        return pngcheck.mean_abs_diff(a, b)
    except ValueError:  # display size changed: a different screen altogether
        return 255.0


def wait_until_in_level(port, out_dir, deadline, poll_secs=2.0, min_diff=IN_LEVEL_DIFF):
    """Wait until the level view replaced the loading poster; returns the first in-level shot.

    Right after LEVEL.BIN lands the "On to Victory!" poster is on screen; it is
    taken as the reference of this run. The level counts as running once two
    consecutive screenshots differ from it by more than min_diff.
    """
    ref = shot(port, out_dir, "loading_ref.png")
    hits, n = 0, 0
    while time.monotonic() < deadline:
        time.sleep(poll_secs)
        current = shot(port, out_dir, f"loading{n:03d}.png")
        n += 1
        if screen_diff(ref, current) > min_diff:
            hits += 1
            if hits >= 2:
                return current
        else:
            hits = 0
    raise SmokeFailure("still on the loading screen after LEVEL.BIN was loaded")


def start_new_game(port, base, deadline):
    """Select NEW GAME and press through FMVs and briefing until LEVEL.BIN is loaded."""
    goto(port, moh.MENU_RING.index("NEW GAME"), base, deadline)
    psxrun.press(port, "cross")
    advance_until_level(port, min(deadline, time.monotonic() + LEVEL_LOAD_SECS))


# --------------------------------------------------------------------------
# Overlay dispatch counters
# --------------------------------------------------------------------------

def overlay_counters(port):
    """DLL-native, static-shard and interpreted overlay dispatches, plus interpreted insns."""
    status = psxdbg.send("overlay_loader_status", port=port)
    static = psxdbg.send("overlay_static_entries", port=port)
    dirty = psxdbg.send("dirty_ram_stats", port=port)
    return {
        "native": int(status.get("dispatch_native", 0)),
        "static": int(static.get("total_hits", 0)) if static.get("ok") else 0,
        "interp": int(status.get("dispatch_interp_fallback", 0)),
        "insns": int(dirty.get("insns_run", 0)),
    }


def window_share(before, after):
    """Interpreted share of overlay dispatches between two overlay_counters() samples."""
    delta = {k: after[k] - before[k] for k in ("native", "static", "interp")}
    total = delta["native"] + delta["static"] + delta["interp"]
    return delta["interp"] / total if total else 1.0
