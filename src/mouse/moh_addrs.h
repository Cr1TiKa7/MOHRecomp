#pragma once
/* Medal of Honor (PAL, SLES-02470) player view facts for the mouse plugin.
 * Same values and sources as tests/smoke/moh.py ("Player view angles");
 * found 2026-10-26 in Mission 1 Level 1 with wtrace/disasm. */

#define MOH_OVERLAY_ADDR          0x80039F28u  /* first word = overlay file id */
#define MOH_LEVEL_FILE_ID         5u           /* LEVEL.BIN (SHELL 7, LEVEL2P 6) */

#define MOH_PLAYER_OWNER_PTR_ADDR 0x8009DC44u  /* *(this) = owner object */
#define MOH_PLAYER_PTR_OFFSET     0x388u       /* *(owner + this) = player struct */
#define MOH_PLAYER_YAW_OFFSET     0x184u       /* 16.16, 4096 angle units per turn */
#define MOH_PLAYER_PITCH_OFFSET   0x17Cu       /* aim-mode crosshair, negative = up */
#define MOH_PLAYER_TILT_OFFSET    0x178u       /* aim-mode camera tilt, 16.16, positive = up */
#define MOH_YAW_UNITS_PER_TURN    4096

/* SW $v0, 388($s0): yaw = yaw + turn rate, once per game frame, player only. */
#define MOH_YAW_STORE_PC          0x800801E0u
#define MOH_YAW_STORE_WORD        0xAE020184u
#define MOH_YAW_STORE_REG         2            /* $v0 */

/* Aim mode (R2 held): the aim function replaces the yaw store and loads one
 * rate per axis from 16($sp): crosshair += rate >> 3 within its limit, past it
 * yaw += rate (horizontal) or tilt -= rate >> 1 (vertical). */
#define MOH_AIM_X_RATE_PC         0x8007FC94u  /* LW $v0, 16($sp) */
#define MOH_AIM_X_RATE_WORD       0x8FA20010u
#define MOH_AIM_Y_RATE_PC         0x8007FE7Cu  /* LW $a0, 16($sp) */
#define MOH_AIM_Y_RATE_WORD       0x8FA40010u
#define MOH_AIM_RATE_SP_OFFSET    16u
#define MOH_AIM_Y_RATE_PER_FIXED  2            /* vertical rate units per 16.16 look-angle unit */
#define MOH_PLAYER_AIM_X_OFFSET   0x188u       /* aim-mode crosshair X */

#define MOH_PITCH_MIN             (-983040)
#define MOH_PITCH_MAX             983040
#define MOH_TILT_MIN              (-44695552)
#define MOH_TILT_MAX              44695552

/* HUD packets (M5). The ammo digits are rect glyphs from the text routine
 * 0x8005FA50; at SW $v0, 0($s3) the glyph packet is complete, $s3 is its
 * P_TAG and $s2 its text-queue entry (+4 x, +6 y, halfwords, 512-wide
 * screen). The ammo icon is a poly at 0xB8 into one of the player's two
 * draw buffers ($v1 = player or player + 0x28, $s0 = player), linked at
 * SW $a0, 184($v1). The compass lives in a fixed packet range (game.toml
 * [widescreen] nw_left_hud_packet_lo/hi). */
#define MOH_TEXT_GLYPH_PC         0x8005FC1Cu
#define MOH_TEXT_GLYPH_WORD       0xAE620000u
#define MOH_AMMO_ICON_PC          0x800807C8u
#define MOH_AMMO_ICON_WORD        0xAC6400B8u
#define MOH_AMMO_ICON_OFFSET      0xB8u
#define MOH_HUD_RIGHT_MIN_X       342          /* right third of the 512-wide screen */
#define MOH_HUD_TOP_MAX_Y         20           /* the top HUD row (ammo counter at y 10) */

/* Sky (M5): 8 gouraud strips 512 wide drawn first each frame (packets
 * 0x800B7E40 + i * 0x24, two draw buffers). SW $v1, 0($s0) links strip $s0
 * into the OT; its command words are final then. */
#define MOH_SKY_LINK_PC           0x8008A098u
#define MOH_SKY_LINK_WORD         0xAE030000u

#define MOH_REG_S0                16
#define MOH_REG_S2                18
#define MOH_REG_S3                19
#define MOH_REG_V1                3
#define MOH_REG_SP                29
