"""Shared Medal of Honor game flows for the smoke tests (stdlib only).

Main-menu navigation, the way from boot into the menu and from NEW GAME into
Mission 1 Level 1, and the overlay dispatch counters used for coverage.
"""

import functools
import os
import struct
import time
import tomllib

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
NEW_GAME_SETTLE_FRAMES = 150   # 3 s at 50 Hz: NEW GAME has reset the game state by then (first FMV running)
IN_LEVEL_DIFF = 10.0      # poster vs. poster < 1 (progress bar); poster vs. level 34-104 (M1L2/M1L1)
BIOS_PROFILES = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              "..", "..", "psxrecomp", "bios"))


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

def advance_until_level(port, deadline, nudge_secs=NUDGE_SECS, file_id=moh.LEVEL_FILE_ID):
    """Press X through FMVs and briefing until the overlay file_id (default LEVEL.BIN) is in place."""
    last = None
    while time.monotonic() < deadline:
        try:
            last = psxrun.read_u32(port, moh.SHELL_LOAD_ADDR)
            if last == file_id:
                return
            psxrun.press(port, "cross")
        except psxrun.TRANSIENT:
            pass
        time.sleep(nudge_secs)
    seen = "unreadable" if last is None else f"0x{last:08X}"
    raise SmokeFailure(f"overlay {file_id} never replaced SHELL.BIN at 0x{moh.SHELL_LOAD_ADDR:08X} "
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
    The settle time counts guest frames, because the game resets its state on
    its own clock; a slow guest would otherwise overwrite the jump.
    """
    goto(port, moh.MENU_RING.index("NEW GAME"), base, deadline)
    psxrun.press(port, "cross")
    _, frame = psxrun.read_frame(port, deadline)
    psxrun.wait_frame(port, frame + NEW_GAME_SETTLE_FRAMES, deadline)
    cells = ((moh.STATE_MISSION_ADDR, mission - 1), (moh.STATE_LEVEL_ADDR, level - 1))
    for addr, value in cells:
        psxdbg.send("write_ram", port=port, addr="0x%08X" % addr, val=value)
        if psxrun.read_u32(port, addr) != value:
            raise SmokeFailure(f"could not set game state at {addr:#010x} to {value}")
    mark = cd_reads_total(port)
    advance_until_level(port, min(deadline, time.monotonic() + LEVEL_LOAD_SECS))
    got = [psxrun.read_u32(port, addr) for addr, _ in cells]
    if got != [value for _, value in cells]:
        raise SmokeFailure(f"game loaded M{got[0] + 1}L{got[1] + 1} instead of M{mission}L{level}: "
                           "the jump was overwritten")
    return mark


def start_new_game(port, base, deadline):
    """Select NEW GAME and press through FMVs and briefing until LEVEL.BIN is loaded."""
    goto(port, moh.MENU_RING.index("NEW GAME"), base, deadline)
    psxrun.press(port, "cross")
    advance_until_level(port, min(deadline, time.monotonic() + LEVEL_LOAD_SECS))


# --------------------------------------------------------------------------
# In-level input loop
# --------------------------------------------------------------------------

LOOP_STEPS = (("up", 2.0), ("right", 1.5), ("left", 0.5), (moh.FIRE_BUTTON, 0.3))
FRAME_READ_SECS = 10.0


def plug_pad2(port, buttons=0xFFFF):
    """Plug a digital pad into port 2 (held until clear_input) with the given buttons word."""
    psxdbg.send("set_input", port=port, buttons=buttons, payload={"port": 2, "connected": 1})


def hold(port, name, secs, pads=(1,)):
    """Hold one button on the given pads, then release it.

    Pad 1 is released with clear_input for port 1 only: a bare clear_input also
    ends the port-2 injection, which unplugs pad 2. Pad 2 is released by
    driving it with no buttons pressed.
    """
    for pad in pads:
        if pad == 2:
            plug_pad2(port, psxrun.mask(name))
        else:
            psxrun.hold_buttons(port, name)
    time.sleep(secs)
    for pad in pads:
        if pad == 2:
            plug_pad2(port)
        else:
            psxdbg.send("clear_input", port=port, payload={"port": 1})


def input_loop(proc, port, out_dir, secs, deadline, shot_every=10, prefix="loop", pads=(1,)):
    """Walk/turn/fire for secs on the given pads; the game must stay alive and keep counting frames.

    Returns the screenshots taken every shot_every seconds (for freeze checks);
    fewer than two make the freeze check meaningless, which callers must reject.
    """
    end = min(time.monotonic() + secs, deadline)
    _, last_frame = psxrun.read_frame(port, time.monotonic() + FRAME_READ_SECS)
    shots, next_shot, n = [], time.monotonic(), 0
    while time.monotonic() < end:
        for name, secs_held in LOOP_STEPS:
            hold(port, name, secs_held, pads)
        psxrun.check_alive(proc)
        # Own short deadline: the last round may end past the caller's deadline.
        _, frame = psxrun.read_frame(port, time.monotonic() + FRAME_READ_SECS)
        if frame <= last_frame:
            raise SmokeFailure(f"level stalled (frame {last_frame} -> {frame})")
        last_frame = frame
        if time.monotonic() >= next_shot:
            shots.append(shot(port, out_dir, f"{prefix}{n:03d}.png"))
            n, next_shot = n + 1, time.monotonic() + shot_every
    return shots


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

# The game's Psy-Q libapi patches a few kernel-RAM words at runtime (the
# _patch_card stub at 0x281C, installed on the first card access, runs once per
# exception). The BIOS profile declares them as install slots and the runtime
# interprets exactly those words by design (psxrecomp/docs/
# dynamic_handler_install.md); they are kernel code, not overlay code, so the
# overlay share leaves their interpreted entries out (verified 2026-10-26: in
# the main menu they were 5199 of 5205 interpreted dispatches). That is only
# sound while every slot entry is also an interpreted overlay dispatch (the
# dirty-RAM interpreter asks the overlay loader first, which counts the miss),
# so delta_share fails instead of subtracting when the two are not nested.
SLOT_SKEW = 64   # entries the slot rows may run ahead: they are read after overlay_loader_status

@functools.lru_cache(maxsize=None)
def install_slots(image_id, profile_dir=BIOS_PROFILES):
    """((lo, hi), ...) kernel-RAM install slots the BIOS profile with [program] id == image_id declares.

    No matching profile means no slots: nothing is left out of the share.
    """
    for name in sorted(os.listdir(profile_dir)):
        if not name.endswith(".toml"):
            continue
        with open(os.path.join(profile_dir, name), "rb") as f:
            profile = tomllib.load(f)
        if profile.get("program", {}).get("id") == image_id:
            slots = profile.get("recompiler", {}).get("install_slots", [])
            return tuple((int(s["ram_addr"], 16), int(s["ram_addr"], 16) + int(s["len"], 16)) for s in slots)
    return ()


def slot_entries(port, slots):
    """Interpreted entries at PCs inside the install slots (dirty_ram_stats per_pc, since boot)."""
    total = 0
    for lo, hi in slots:
        reply = psxdbg.send("dirty_ram_stats", port=port, lo="0x%08X" % lo, hi="0x%08X" % hi)
        total += sum(int(row["entries"]) for row in reply.get("per_pc", []))
    return total


def overlay_counters(port):
    """DLL-native, static-shard and interpreted overlay dispatches, interpreted insns,
    and the interpreted entries at the BIOS install slots ("slot", part of "interp")."""
    slots = install_slots(psxdbg.send("bios_info", port=port).get("image_id", ""))
    status = psxdbg.send("overlay_loader_status", port=port)
    slot = slot_entries(port, slots)
    static = psxdbg.send("overlay_static_entries", port=port)
    dirty = psxdbg.send("dirty_ram_stats", port=port)
    return {
        "native": int(status.get("dispatch_native", 0)),
        "static": int(static.get("total_hits", 0)) if static.get("ok") else 0,
        "interp": int(status.get("dispatch_interp_fallback", 0)),
        "insns": int(dirty.get("insns_run", 0)),
        "slot": slot,
    }


def delta_share(delta):
    """Interpreted share of the overlay dispatches in a counter delta, install-slot entries left out."""
    slot = delta.get("slot", 0)
    if slot > delta["interp"] + max(SLOT_SKEW, slot // 1000):
        raise SmokeFailure(f"{slot} install-slot entries but only {delta['interp']} interpreted "
                           "dispatches: the runtime counters are no longer nested")
    interp = max(0, delta["interp"] - slot)
    total = delta["native"] + delta["static"] + interp
    return interp / total if total else 1.0


def window_share(before, after):
    """Interpreted share of overlay dispatches between two overlay_counters() samples."""
    return delta_share({k: after[k] - before[k] for k in after})
