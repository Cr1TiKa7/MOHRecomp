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
MAX_RING = 10
NUDGE_SECS = 3.0
LEVEL_LOAD_SECS = 120.0   # FMVs + briefing + loading took ~15-40 s with X every 3 s
NEW_GAME_SETTLE_SECS = 3.0   # NEW GAME has reset the game state by then (first FMV running)
IN_LEVEL_DIFF = 10.0      # poster vs. poster < 1 (progress bar); poster vs. level 34-104 (M1L2/M1L1)


# --------------------------------------------------------------------------
# Main menu
# --------------------------------------------------------------------------

def entry_ptr(port):
    return struct.unpack("<I", psxrun.read_bytes(port, moh.MENU_ITEM_PTR_ADDR, 4))[0]


def menu_index(port, base, ring_size=len(moh.MENU_RING)):
    return moh.menu_index_from_ptr(entry_ptr(port), base, ring_size)


def _step_right(port):
    psxrun.press(port, "right")
    time.sleep(STEP_SECS)
    return entry_ptr(port)


def walk_ring(port, deadline):
    """Wait until RIGHT moves the ring, walk it once and learn its size.

    Returns (base, index, size): the entry-array base (lowest pointer = entry
    0), the index the ring ended on, and the number of entries (6 on a fresh
    game, 7 after loading a save).
    """
    start = None
    for _ in range(ACTIVATION_TRIES):
        if time.monotonic() > deadline:
            break
        before = entry_ptr(port)
        after = _step_right(port)
        if moh.is_ring_step(before, after, ring_size=None):
            start = after
            break
    if start is None:
        raise SmokeFailure(f"menu never reacted to RIGHT within {ACTIVATION_TRIES} tries")
    seen = [start]
    ptr = start
    for _ in range(MAX_RING):
        nxt = _step_right(port)
        if not moh.is_ring_step(ptr, nxt, ring_size=None):
            raise SmokeFailure(f"RIGHT moved the entry pointer {ptr:#010x} -> {nxt:#010x}")
        ptr = nxt
        if ptr == start:
            break
        seen.append(ptr)
    else:
        raise SmokeFailure(f"ring did not return to its start within {MAX_RING} steps")
    size = len(seen)
    base = min(seen)
    if sorted(seen) != [base + i * moh.MENU_ITEM_STRIDE for i in range(size)]:
        raise SmokeFailure(f"ring entries are not one contiguous array: {[hex(p) for p in seen]}")
    return base, moh.menu_index_from_ptr(ptr, base, size), size


def goto(port, index, base, deadline, ring_size=len(moh.MENU_RING)):
    for _ in range(ring_size):
        if menu_index(port, base, ring_size) == index:
            return
        if time.monotonic() > deadline:
            break
        _step_right(port)
    if menu_index(port, base, ring_size) != index:
        raise SmokeFailure(f"could not reach menu entry {index}")


def goto_ptr(port, ptr, ring_size, deadline):
    """Press RIGHT until the current-entry pointer equals ptr (at most one lap)."""
    for _ in range(ring_size):
        if entry_ptr(port) == ptr:
            return
        if time.monotonic() > deadline:
            break
        _step_right(port)
    if entry_ptr(port) != ptr:
        raise SmokeFailure(f"could not reach menu entry at {ptr:#010x}")


def boot_to_menu(proc, port, deadline):
    """Fast-forward from boot into the main menu; returns the learned entry base."""
    psxrun.wait_for_ping(proc, port, deadline)
    psxdbg.send("turbo", port=port, enabled=1)
    psxrun.wait_frame(port, moh.MENU_READY_FRAME, deadline)
    psxdbg.send("turbo", port=port, enabled=0)
    base, _, size = walk_ring(port, deadline)
    if size != len(moh.MENU_RING):
        raise SmokeFailure(f"fresh main menu has {size} entries, expected {len(moh.MENU_RING)}")
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


def start_level(port, base, mission, level, deadline):
    """Start NEW GAME but jump to mission/level via the persistent game state.

    Returns the cd_read_log mark taken before the level loads, so callers can
    check which level's data was read. The briefing shown is Mission 1's.
    """
    goto(port, moh.MENU_RING.index("NEW GAME"), base, deadline)
    psxrun.press(port, "cross")
    time.sleep(NEW_GAME_SETTLE_SECS)
    for addr, value in ((moh.STATE_MISSION_ADDR, mission - 1), (moh.STATE_LEVEL_ADDR, level - 1)):
        psxdbg.send("write_ram", port=port, addr="0x%08X" % addr, val=value)
        if psxrun.read_u32(port, addr) != value:
            raise SmokeFailure(f"could not set game state at {addr:#010x} to {value}")
    mark = cd_reads_total(port)
    advance_until_level(port, min(deadline, time.monotonic() + LEVEL_LOAD_SECS))
    return mark


def start_new_game(port, base, deadline):
    """Select NEW GAME and press through FMVs and briefing until LEVEL.BIN is loaded."""
    goto(port, moh.MENU_RING.index("NEW GAME"), base, deadline)
    psxrun.press(port, "cross")
    advance_until_level(port, min(deadline, time.monotonic() + LEVEL_LOAD_SECS))


# --------------------------------------------------------------------------
# CD reads
# --------------------------------------------------------------------------

def cd_reads_total(port):
    return int(psxdbg.send("cd_read_log", port=port, tail=1, max_entries=0)["total"])


def cd_reads_in(port, since, lba_range, limit=5):
    """Start LBAs of CD reads after the mark `since` that fall into lba_range."""
    tail = max(1, cd_reads_total(port) - since)
    reply = psxdbg.send("cd_read_log", port=port, tail=tail, lba_lo=lba_range[0],
                        lba_hi=lba_range[1], max_entries=limit)
    return [entry["lba"] for entry in reply.get("entries", [])]


# --------------------------------------------------------------------------
# RAM search
# --------------------------------------------------------------------------

RAM_BASE = 0x80000000
GAME_RAM_START = 0x10000   # below: BIOS/kernel, which caches the card directory


def ram_hits(ram, needle, limit=16):
    """Addresses of needle in a main-RAM dump, ignoring the BIOS/kernel area."""
    hits, pos = [], ram.find(needle, GAME_RAM_START)
    while pos != -1 and len(hits) < limit:
        hits.append(RAM_BASE + pos)
        pos = ram.find(needle, pos + 1)
    return hits


def game_ram_hits(port, needle):
    return ram_hits(psxrun.read_bytes(port, RAM_BASE, 0x200000), needle)


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
