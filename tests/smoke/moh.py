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
# WAR RECORDS opens a desk submenu; RIGHT browses PERSONAL RECORDS, LOAD GAME,
# SAVE GAME. X on LOAD GAME shows "Checking memory card", then the save list
# (the player name is in game RAM from here on), then "Loading game" / "Game
# loaded". Afterwards the ring has 7 entries: NEXT MISSION is added and
# preselected (NEW GAME stays, at the lowest pointer); starting NEXT MISSION
# loads Mission 1 Level 2 instead of Level 1.
LOAD_GAME_RIGHTS = 2

# First word of each overlay file: SHELL.BIN 7, LEVEL.BIN 5, LEVEL2P.BIN 6.
SHELL_FILE_ID = 7
LEVEL_FILE_ID = 5

# Disc sectors (ISO LBAs) of the per-level data files; cd_read_log logs the
# start LBA of each read, so the level a mission start loads shows up here.
M1_LVL1_LBAS = (1713, 6290)      # /DATA/MSN1/LVL1/*
M1_LVL2_LBAS = (6292, 10935)     # /DATA/MSN1/LVL2/*

# Mission 1 Level 1: X (Cross) fires; the rifle magazine counter (8 at spawn)
# lives here (8 -> 7 -> 6 on two shots).
FIRE_BUTTON = "cross"
M1L1_MAGAZINE_ADDR = 0x800EEC92


def menu_index_from_ptr(ptr, base, ring_size=len(MENU_RING)):
    """Ring index for a current-entry pointer, or None if it is not one."""
    offset = ptr - base
    if offset < 0 or offset % MENU_ITEM_STRIDE:
        return None
    index = offset // MENU_ITEM_STRIDE
    return index if index < ring_size else None


def is_ring_step(before, after, ring_size=len(MENU_RING)):
    """True if one RIGHT moved the entry pointer forward by one ring slot.

    ring_size None accepts a wrap of any whole number of slots (used while
    the ring size is still unknown).
    """
    if after - before == MENU_ITEM_STRIDE:
        return True
    back = before - after
    if ring_size is None:
        return back > 0 and back % MENU_ITEM_STRIDE == 0
    return back == (ring_size - 1) * MENU_ITEM_STRIDE


def count_shots(magazine_samples):
    """Number of decrements in a series of magazine readings (reloads go up)."""
    return sum(1 for a, b in zip(magazine_samples, magazine_samples[1:]) if b < a)
