"""Medal of Honor (PAL, SLES-02470) facts the smoke tests rely on.

Found on the dev build (2026-10-25); see docs/superpowers/plans/2026-10-25-moh-m1-menu.md.
"""

# Unaided boot reaches the main menu around frame 5500 (50 frames/s).
MENU_READY_FRAME = 5700

# Main-menu ring in RIGHT order. BRIEFING plays a ~108 s film and returns with
# NEW GAME selected, as do OPTIONS / WAR RECORDS / GALLERY on TRIANGLE (GALLERY
# holds films too: HISTORY, MAKING OF). After ~30 s idle in the main menu an
# attract film starts (verified 2026-10-26).
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
LEVEL2P_FILE_ID = 6

# MULTIPLAYER opens its own room; START GAME is preselected and needs a pad in
# port 2 ("NOT ALL CONTROLLERS PLUGGED IN..." otherwise). X on it loads
# LEVEL2P.BIN straight away; the split screen shows player 1 on top and player
# 2 below. The default arena is /DATA/MSN12/LVL4, the player models and
# weapons come from /DATA/TWOPLAYR/ (verified 2026-10-26).
TWOPLAYR_LBAS = (134948, 139527)  # /DATA/TWOPLAYR/{PLAYERS,WEAPONS}/*

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
# /DATA/MSN12/LVL1-7: three files per level only: the multiplayer arenas. The
# split screen loads its default arena from LVL4, and NEW GAME with mission
# index 11 loads LEVEL2P.BIN instead of LEVEL.BIN (sweep --bonus: 0/7, overlay
# word 6 every time), so they are not playable in single player.
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

# Player view angles (M4, found 2026-10-26 in M1L1 with wtrace/disasm; see
# docs/DEVELOPMENT.md "Blickwinkel und Zielmodus"). The player struct is
# *(*(PLAYER_OWNER_PTR_ADDR) + PLAYER_PTR_OFFSET), 0x800EEC2C in M1L1.
PLAYER_OWNER_PTR_ADDR = 0x8009DC44
PLAYER_PTR_OFFSET = 0x388
# Yaw: 16.16 fixed point, upper half = angle with YAW_UNITS_PER_TURN per turn,
# never wrapped (+4096 << 16 gives the same picture, +1024 << 16 a quarter turn).
PLAYER_YAW_OFFSET = 0x184
YAW_UNITS_PER_TURN = 4096
# LEVEL.BIN's yaw integration: SW $v0, 388($s0) in the delay slot of
# JAL 0x800762D8, after $v0 = yaw + turn rate. Runs once per game frame
# (25 Hz), only for the player, and not while the game is paused. SHELL.BIN
# and LEVEL2P.BIN hold other words at this address.
YAW_STORE_PC = 0x800801E0
YAW_STORE_WORD = 0xAE020184
# Aim mode (R2 held). LEVEL.BIN's aim function then replaces the yaw store
# above and treats both axes alike: it loads a rate from 16($sp) (after the
# pad's speed modifiers), moves a crosshair coordinate by rate >> 3 within its
# limit, and past the limit turns the view instead.
# - Horizontal: crosshair X at +0x188; past it yaw += rate (SW at 0x8007FD7C),
#   so the rate is in 16.16 yaw units (AIM_X_RATE_PER_FIXED = 1).
# - Vertical: crosshair Y ("pitch") at +0x17C, 0 = centre, negative = up,
#   clamped to PITCH_MIN..PITCH_MAX; past it the camera tilt (+0x178, 16.16,
#   positive = up, TILT_MIN..TILT_MAX = 0xFD560000..0x02AA0000, about 60
#   degrees) moves by -(rate >> 1), so AIM_Y_RATE_PER_FIXED = 2.
# Releasing R2 writes pitch 0 (0x80080028). A digital pad then recentres the
# tilt within about a second; an analog pad (the mouse package) keeps it, and
# with an analog pad the stick aims instead of the d-pad.
# Outside aim mode the game has no pitch (EASY AIM aims vertically).
PLAYER_AIM_X_OFFSET = 0x188
PLAYER_PITCH_OFFSET = 0x17C
PLAYER_TILT_OFFSET = 0x178
PITCH_MIN = -983040
PITCH_MAX = 983040
TILT_MIN = -44695552
TILT_MAX = 44695552
AIM_X_RATE_PER_FIXED = 1
AIM_Y_RATE_PER_FIXED = 2
# The two rate loads, LW $v0/$a0, 16($sp); every aim-mode frame, with or
# without pad input, horizontal first. Only LEVEL.BIN has these words here.
AIM_X_RATE_PC = 0x8007FC94
AIM_X_RATE_WORD = 0x8FA20010
AIM_Y_RATE_PC = 0x8007FE7C
AIM_Y_RATE_WORD = 0x8FA40010
AIM_RATE_SP_OFFSET = 16
# Normal play (R2 not held): the right stick's tilt rate, LW $v1, 16($sp) in
# the player control function 0x8007F8E8; the game then does tilt -= rate >> 1
# and clamps to TILT_MIN..TILT_MAX, and keeps the tilt when the stick is
# released. Shots follow the tilt (M4 free look, bullet holes at the screen
# centre, measured at -56, -17 and +17 degrees, 2026-10-27). L3 held
# recentres the view and skips this load; mouse_smoke checks that nothing
# piles up then.
TILT_RATE_PC = 0x80080470
TILT_RATE_WORD = 0x8FA30010


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
    """LBA range of a single-player level or an MSN12 folder (BONUS_LEVELS); KeyError if it does not exist."""
    for m, l, lbas in LEVELS + BONUS_LEVELS:
        if (m, l) == (mission, level):
            return lbas
    raise KeyError(f"no level M{mission}L{level} on the disc")


def count_shots(magazine_samples):
    """Number of decrements in a series of magazine readings (reloads go up)."""
    return sum(1 for a, b in zip(magazine_samples, magazine_samples[1:]) if b < a)

# Widescreen (M5, moh.enhancement.widescreen). Native-wide 16:9 widens the
# 512-wide display by 170 pixels (85 per side); screenshots are 682 wide.
# The gameplay gate is the plugin's world-scene predicate (yaw store or aim-X
# rate load ran in the last 12 VBlanks; a game.toml gameplay_state gate never
# engaged, see the M5 ledger).
WS_NW_EXTRA = 170
WS_WIDE_WIDTH = 682
WS_GAMEPLAY_GATE = "plugin world-scene predicate"
WS_PAUSE_PATH = "native43"   # filled in from the first run (Task 1 step 5)
# HUD boxes in 4:3 screenshots (512 wide) of M1L1: compass ring, ammo counter
# (icon + digits), crosshair (aim mode). In native-wide the compass belongs at
# the left edge (shift 0), the ammo counter at the right (170), the crosshair
# in the centre (85). Packet facts: src/mouse/moh_addrs.h and the M5 ledger.
WS_HUD_COMPASS_BOX = (20, 15, 100, 57)
WS_HUD_AMMO_BOX = (390, 6, 490, 20)
WS_CROSSHAIR_BOX = (236, 128, 272, 152)
# The box is searched from -20 to 250 px; a match costs at most this mean
# difference per channel (found boxes 2.8-5.5, the next-best place 16.9-34.4
# in the 2026-10-27 runs).
WS_HUD_SEARCH = (-20, 250)
WS_HUD_MAX_COST = 12.0
# ws_tag_stats: HUD and sky tags expire 2 vblanks after the hook; draws that
# found their tag fresh, per tag call (review item 4). Measured 1.03-1.99 for
# both in M1L1/M3L1/M7L1 (above 1: a tagged packet is looked up per pass);
# expired tags would push it toward 0.
WS_TAG_MIN_DRAWN = 0.9
# Edge culling (M5 Task 3): views where 4:3 culling dropped big polygons in the
# wide bands (dark share before the fix .827 / .216 / .115). The yaw is the
# absolute 12-bit angle; the level is entered from its start position.
WS_EDGE_VIEWS = ((1, 1, 3811, "left"), (3, 1, 1221, "left"), (7, 1, 1024, "right"))
WS_EDGE_MAX_DARK = 0.05
WS_MARGIN_MAX_DIFF = 2.0
# Sky (M5 Task 2): LEVEL.BIN draws it as 8 gouraud strips 512 wide (packets
# 0x800B7E40 + i * 0x24, linked into the OT by SW $v1, 0($s0) at 0x8008A098);
# moh.widescreen tags them as background so they stretch over the side bands.
# Upper-half dark share per band: 4:3 edges at most .145, so .195 allows .05.
WS_SKY_BASE_YAW = 1251    # M1L1 start direction
WS_SKY_MAX_DARK = 0.195
# PGXP (M5 Task 5): share of triangles drawn with PGXP precision (fully or
# partly) over 2 s of turning and 2 s of walking in M1L1, with this
# (non-PGXP-variant) runtime at the framework's default tolerance 0.5: 0.248
# measured; the check allows 5 points less.
PGXP_MIN_CORRECTED = 0.198
