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

# Single-player levels in campaign order: (mission, level, (first LBA, last LBA))
# of the level's data files (inclusive, directory sector excluded). Missions 6
# and 8 do not exist on the disc; MSN9 has no LVL3.
LEVELS = (
    (1, 1, (1713, 6290)), (1, 2, (6292, 10935)), (1, 3, (10937, 15207)),
    (2, 1, (24692, 28821)), (2, 2, (28823, 33079)), (2, 3, (33081, 37434)), (2, 4, (37436, 41863)),
    (3, 1, (41866, 46673)), (3, 2, (46675, 51546)), (3, 3, (51548, 56581)), (3, 4, (56583, 60949)),
    (4, 1, (60952, 65835)), (4, 2, (65837, 70358)), (4, 3, (70360, 74809)),
    (5, 1, (74812, 79140)), (5, 2, (79142, 83430)), (5, 3, (83432, 87646)), (5, 4, (87648, 92104)),
    (7, 1, (92107, 96662)), (7, 2, (96664, 101218)), (7, 3, (101220, 108049)),
    (9, 1, (108052, 112028)), (9, 2, (112030, 116060)), (9, 4, (116062, 118325)),
)
# /DATA/MSN12/LVL1-7: three files per level only; probably bonus/secret levels.
BONUS_LEVELS = (
    (12, 1, (15210, 15788)), (12, 2, (15790, 16376)), (12, 3, (16378, 16979)),
    (12, 4, (16981, 17610)), (12, 5, (17612, 23592)), (12, 6, (23594, 24155)),
    (12, 7, (24157, 24689)),
)

# Persistent game state (boot EXE memory, survives overlay swaps). LEVEL.BIN's
# start-up copies mission index +1 / level index +1 from here into the
# variables its path builder uses ("data\msn%ld\lvl%ld\..."). Writing both
# indexes after NEW GAME starts any level.
STATE_MISSION_ADDR = 0x800387F8   # 0-based mission index
STATE_LEVEL_ADDR = 0x800387FC     # 0-based level index

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


def level_lbas(mission, level):
    """LBA range of a single-player or bonus level; KeyError if it does not exist."""
    for m, l, lbas in LEVELS + BONUS_LEVELS:
        if (m, l) == (mission, level):
            return lbas
    raise KeyError(f"no level M{mission}L{level} on the disc")


def count_shots(magazine_samples):
    """Number of decrements in a series of magazine readings (reloads go up)."""
    return sum(1 for a, b in zip(magazine_samples, magazine_samples[1:]) if b < a)
