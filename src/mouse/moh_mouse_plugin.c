/* Mouse look for Medal of Honor: trusted static plugin "moh.mouse-look" of the
 * mod package moh.input.mouse-keyboard (feature "mouse-look"). The runtime's
 * local mouse policy delivers raw motion; the arithmetic is in mouselook.c.
 * Everything except the debug command runs on the emulation thread. */
#include <math.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cpu_state.h"
#include "mod_plugins.h"
#include "moh_addrs.h"
#include "mouselook.h"

#define PLUGIN_ID  "moh.mouse-look"
#define PACKAGE_ID "moh.input.mouse-keyboard"
#define FEATURE_ID "mouse-look"
#define PAD_MODE_ANALOG 1      /* PSXRecompV4::PAD_MODE_ANALOG (runtime main.cpp) */
#define INBOX_SCALE 1000.0     /* debug "move" counts are queued in thousandths */

static MohLook g_look;
static uint32_t g_vblanks, g_hook_vblank;
static int g_hook_seen;
/* Debug "move" counts: filled by the debug-server thread, moved to g_debug_*
 * on VBlank while in gameplay and handed to g_look by the frame's first hook.
 * They stay out of g_look until then because the policy, never capturing
 * under debug input, sends RESET on every update. */
static _Atomic long long g_inbox_x, g_inbox_y;
static double g_debug_x, g_debug_y;

static int option_text(const char *option_id, char *out, uint32_t size) {
    return psx_mod_option_value(PACKAGE_ID, FEATURE_ID, option_id, out, size);
}

static int option_sensitivity(void) {
    char buf[16];
    return option_text("sensitivity", buf, sizeof buf) ? atoi(buf) : 40;
}

static int option_invert_y(void) {
    char buf[16];
    return option_text("invert_y", buf, sizeof buf) && strcmp(buf, "true") == 0;
}

static int in_gameplay(void) {
    return moh_look_eligible(psx_mod_read_word(MOH_OVERLAY_ADDR), 0, g_vblanks,
                             g_hook_vblank, g_hook_seen);
}

static int policy_eligible(uint32_t native_buttons) {
    (void)native_buttons;
    return in_gameplay();
}

static void policy_event(const PSXModMouseEvent *event) {
    if (event->type == PSX_MOD_MOUSE_MOTION)
        moh_look_motion(&g_look, event->dx, event->dy);
    else if (event->type == PSX_MOD_MOUSE_RESET)
        moh_look_reset(&g_look);
    else if (event->type == PSX_MOD_MOUSE_ACQUIRED)
        psx_mod_counter_add("moh_mouse.acquired", 1);   /* playtests: how often a click recaptured */
}

static void policy_sample(uint64_t now_ns, PSXModMouseOutput *output) {
    (void)now_ns;
    output->override_right = 0;   /* the angles are written directly, never via the stick */
}

static const PSXModMousePolicy k_policy = {
    sizeof(PSXModMousePolicy), PSX_MOD_MOUSE_HOLD_NONE,
    policy_eligible, policy_event, policy_sample,
};

static void on_vblank(void) {
    g_vblanks++;
    const long long dx = atomic_exchange(&g_inbox_x, 0);
    const long long dy = atomic_exchange(&g_inbox_y, 0);
    if (!dx && !dy) return;
    if (in_gameplay()) {
        g_debug_x += dx / INBOX_SCALE;
        g_debug_y += dy / INBOX_SCALE;
    } else
        psx_mod_counter_add("moh_mouse.dropped", 1);
}

/* The hook sites exist only in LEVEL.BIN (the registered word is checked
 * too); the store also has to be the player's, not another actor's. */
static int is_player(const struct CPUState *cpu) {
    if (psx_mod_read_word(MOH_OVERLAY_ADDR) != MOH_LEVEL_FILE_ID) return 0;
    const uint32_t owner = psx_mod_read_word(MOH_PLAYER_OWNER_PTR_ADDR);
    return owner && cpu->gpr[MOH_REG_S0] == psx_mod_read_word(owner + MOH_PLAYER_PTR_OFFSET);
}

/* First hook of a game frame (yaw store or horizontal aim rate): hand over
 * the staged debug counts and note that gameplay is running. */
static void frame_hook(void) {
    if (g_debug_x != 0.0 || g_debug_y != 0.0) {
        moh_look_motion(&g_look, g_debug_x, g_debug_y);
        g_debug_x = g_debug_y = 0.0;
    }
    g_hook_vblank = g_vblanks;
    g_hook_seen = 1;
}

/* The aim rate sits in 16($sp) and is loaded by the hooked instruction. */
static void add_to_aim_rate(struct CPUState *cpu, int32_t rate) {
    if (!rate) return;
    const uint32_t slot = cpu->gpr[MOH_REG_SP] + MOH_AIM_RATE_SP_OFFSET;
    psx_mod_write_word(slot, psx_mod_read_word(slot) + (uint32_t)rate);
}

/* Normal play, before SW $v0, 388($s0): $v0 = yaw + the game's own turn rate. */
static void on_yaw_store(struct CPUState *cpu, uint32_t address) {
    (void)address;
    if (!is_player(cpu)) return;
    frame_hook();
    cpu->gpr[MOH_YAW_STORE_REG] += (uint32_t)moh_look_take_yaw(&g_look);
    psx_mod_counter_add("moh_mouse.yaw_hook", 1);
}

/* Aim mode, before LW $v0, 16($sp): the horizontal aim rate. */
static void on_aim_x(struct CPUState *cpu, uint32_t address) {
    (void)address;
    if (!is_player(cpu)) return;
    frame_hook();
    add_to_aim_rate(cpu, moh_look_take_aim_x(&g_look));
    psx_mod_counter_add("moh_mouse.aim_x_hook", 1);
}

/* Aim mode, before LW $a0, 16($sp): the vertical aim rate. */
static void on_aim_y(struct CPUState *cpu, uint32_t address) {
    (void)address;
    if (!is_player(cpu)) return;
    add_to_aim_rate(cpu, moh_look_take_aim_y(&g_look));
    psx_mod_counter_add("moh_mouse.aim_y_hook", 1);
}

static void on_activate(void) {
    moh_look_init(&g_look, option_sensitivity(), option_invert_y(), MOH_AIM_Y_RATE_PER_FIXED);
    g_vblanks = g_hook_vblank = 0;
    g_hook_seen = 0;
    atomic_store(&g_inbox_x, 0);
    atomic_store(&g_inbox_y, 0);
    g_debug_x = g_debug_y = 0.0;
    /* The mouse policy only captures for an analog P1. */
    psx_mod_set_controller_mode_override(0, PAD_MODE_ANALOG);
    if (psx_mod_set_local_mouse_policy(&k_policy))
        psx_mod_set_local_mouse_persistent_capture(1);
    psx_mod_counter_add("moh_mouse.activate", 1);
}

static int on_option_changed(const char *option_id, const char *value) {
    if (strcmp(option_id, "sensitivity") == 0)
        moh_look_set(&g_look, atoi(value), g_look.invert_y);
    else if (strcmp(option_id, "invert_y") == 0)
        moh_look_set(&g_look, g_look.sensitivity, strcmp(value, "true") == 0);
    else
        return 0;
    return 1;
}

/* {"cmd":"mod_cmd","name":"moh_mouse","args":"move <dx> <dy>"}: queue mouse
 * counts as if they came from the mouse (tests; the policy is off under
 * debug input). */
static int cmd_moh_mouse(const char *args, char *reply, int cap) {
    double dx, dy;
    if (!args || sscanf(args, "move %lf %lf", &dx, &dy) != 2 || !isfinite(dx) || !isfinite(dy)) {
        snprintf(reply, cap, "usage: move <dx> <dy>");
        return -1;
    }
    atomic_fetch_add(&g_inbox_x, llround(dx * INBOX_SCALE));
    atomic_fetch_add(&g_inbox_y, llround(dy * INBOX_SCALE));
    snprintf(reply, cap, "queued %g %g", dx, dy);
    return 0;
}

PSX_MOD_CONSTRUCTOR(moh_mouse_register) {
    psx_mod_register_activation_plugin(PLUGIN_ID, on_activate);
    psx_mod_register_instruction_plugin(PLUGIN_ID, MOH_YAW_STORE_PC, MOH_YAW_STORE_WORD, on_yaw_store);
    psx_mod_register_instruction_plugin(PLUGIN_ID, MOH_AIM_X_RATE_PC, MOH_AIM_X_RATE_WORD, on_aim_x);
    psx_mod_register_instruction_plugin(PLUGIN_ID, MOH_AIM_Y_RATE_PC, MOH_AIM_Y_RATE_WORD, on_aim_y);
    psx_mod_register_vblank_plugin(PLUGIN_ID, on_vblank);
    psx_mod_register_option_changed_plugin(PLUGIN_ID, on_option_changed);
    psx_mod_register_command("moh_mouse", cmd_moh_mouse);
}
