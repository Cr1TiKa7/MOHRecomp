/* Widescreen for Medal of Honor: trusted static plugin "moh.widescreen" of the
 * mod package moh.enhancement.widescreen (feature "widescreen"). Native-wide
 * 16:9 (the framework renders a wider surface, nothing is squashed) during
 * gameplay only: a frame counts as gameplay when LEVEL.BIN's yaw store or its
 * aim-mode horizontal rate load ran within the last MOH_LOOK_STALE_VBLANKS,
 * the same rule the mouse plugin uses. Emulation thread only. */
#include "cpu_state.h"
#include "gpu.h"   /* gpu_ws_tag_background_prim: runtime-internal, no psx_mod_ wrapper yet */
#include "mod_plugins.h"
#include "moh_addrs.h"
#include "mouselook.h"

#define PLUGIN_ID "moh.widescreen"

static uint32_t g_vblanks, g_frame_vblank;
static int g_frame_seen;

static void on_vblank(void) { g_vblanks++; }

/* Either site runs once per game frame, depending on aim mode. */
static void on_gameplay_frame(struct CPUState *cpu, uint32_t address) {
    (void)cpu;
    (void)address;
    g_frame_vblank = g_vblanks;
    g_frame_seen = 1;
}

/* Without this the framework treats MOH's 3D levels as 2D scenes and stays
 * 4:3; with its GTE detector instead, the 4:3-built menu rooms and the
 * loading poster would go wide as well. */
static int in_gameplay(void) {
    return moh_look_eligible(psx_mod_read_word(MOH_OVERLAY_ADDR), 0, g_vblanks,
                             g_frame_vblank, g_frame_seen);
}

/* psx_mod_anchor_hud_primitive wants the word right before the GP0 command:
 * the P_TAG itself, or P_TAG + 4 when a draw-mode (E1) word comes first. */
static uint32_t command_anchor(uint32_t tag) {
    return (psx_mod_read_word(tag + 4) >> 24) == 0xE1 ? tag + 4 : tag;
}

/* Text glyphs: only the top-right HUD row (the ammo counter) moves to the
 * right edge; everything else stays where the game puts it (centred). */
static void on_text_glyph(struct CPUState *cpu, uint32_t address) {
    (void)address;
    const uint32_t entry = cpu->gpr[MOH_REG_S2];
    const int16_t x = (int16_t)psx_mod_read_half(entry + 4);
    const int16_t y = (int16_t)psx_mod_read_half(entry + 6);
    if (x >= MOH_HUD_RIGHT_MIN_X && y <= MOH_HUD_TOP_MAX_Y)
        psx_mod_anchor_hud_primitive(command_anchor(cpu->gpr[MOH_REG_S3]), +1);
}

/* The ammo icon beside the digits. */
static void on_ammo_icon(struct CPUState *cpu, uint32_t address) {
    (void)address;
    psx_mod_anchor_hud_primitive(command_anchor(cpu->gpr[MOH_REG_V1] + MOH_AMMO_ICON_OFFSET), +1);
}

/* The sky strips are exactly 512 wide, so the side bands stay black unless the
 * renderer knows they are the background and stretches them. No guest data
 * is changed; at 4:3 (or outside gameplay) nothing is tagged. */
static void on_sky_strip(struct CPUState *cpu, uint32_t address) {
    (void)address;
    if (in_gameplay())
        gpu_ws_tag_background_prim(cpu->gpr[MOH_REG_S0]);
}

static void on_activate(void) {
    g_vblanks = g_frame_vblank = 0;
    g_frame_seen = 0;
    psx_mod_set_fixed_display_aspect(16, 9);
    psx_mod_set_native_wide_projection_correction(1);
    psx_mod_set_world_scene_predicate(in_gameplay);
    psx_mod_counter_add("moh_widescreen.activate", 1);
}

PSX_MOD_CONSTRUCTOR(moh_widescreen_register) {
    psx_mod_register_activation_plugin(PLUGIN_ID, on_activate);
    psx_mod_register_vblank_plugin(PLUGIN_ID, on_vblank);
    psx_mod_register_instruction_plugin(PLUGIN_ID, MOH_YAW_STORE_PC, MOH_YAW_STORE_WORD, on_gameplay_frame);
    psx_mod_register_instruction_plugin(PLUGIN_ID, MOH_AIM_X_RATE_PC, MOH_AIM_X_RATE_WORD, on_gameplay_frame);
    psx_mod_register_instruction_plugin(PLUGIN_ID, MOH_TEXT_GLYPH_PC, MOH_TEXT_GLYPH_WORD, on_text_glyph);
    psx_mod_register_instruction_plugin(PLUGIN_ID, MOH_AMMO_ICON_PC, MOH_AMMO_ICON_WORD, on_ammo_icon);
    psx_mod_register_instruction_plugin(PLUGIN_ID, MOH_SKY_LINK_PC, MOH_SKY_LINK_WORD, on_sky_strip);
}
