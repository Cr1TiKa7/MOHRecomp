"""Medal of Honor (PAL, SLES-02470) facts the smoke tests rely on.

Found on the dev build (2026-10-25); see docs/superpowers/plans/2026-10-25-moh-m1-menu.md.
"""

# Unaided boot reaches the main menu around frame 5500 (50 frames/s).
MENU_READY_FRAME = 5700

# Main-menu ring in RIGHT order.
MENU_RING = ("NEW GAME", "WAR RECORDS", "BRIEFING", "MULTIPLAYER", "GALLERY", "OPTIONS")

# The menu keeps a pointer to the current ring entry (tools/ramdiff.py on six
# snapshots, one RIGHT apart; the other hits were stack slots near 0x801FFExx).
# The entries form an array in ring order whose base moves between runs
# (0x801A4AD8 in one, 0x801A93D8 in another), so the base is learned per run:
# it is the lowest pointer seen while walking the ring (= NEW GAME).
MENU_ITEM_PTR_ADDR = 0x801A90FC
MENU_ITEM_STRIDE = 0x274         # bytes between ring entries

# SHELL.BIN is loaded verbatim here (boot EXE: lui a1,0x8004 / addiu a1,a1,0x9F28).
SHELL_LOAD_ADDR = 0x80039F28


def menu_index_from_ptr(ptr, base):
    """Ring index 0..5 for a current-entry pointer, or None if it is not one."""
    offset = ptr - base
    if offset < 0 or offset % MENU_ITEM_STRIDE:
        return None
    index = offset // MENU_ITEM_STRIDE
    return index if index < len(MENU_RING) else None


def is_ring_step(before, after):
    """True if one RIGHT moved the entry pointer forward by one ring slot."""
    last = (len(MENU_RING) - 1) * MENU_ITEM_STRIDE
    return after - before == MENU_ITEM_STRIDE or before - after == last
