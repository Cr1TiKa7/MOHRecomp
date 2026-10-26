/* Mouse look for Medal of Honor: trusted static plugin "moh.mouse-look" of the
 * mod package moh.input.mouse-keyboard (feature "mouse-look"). The runtime's
 * local mouse policy delivers raw motion; the arithmetic is in mouselook.c.
 * Everything except the debug command runs on the emulation thread. */
#include <math.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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
/* Filled by the debug-server thread, drained on the emulation thread. */
static _Atomic long long g_inbox_x, g_inbox_y;

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
    if (in_gameplay())
        moh_look_motion(&g_look, dx / INBOX_SCALE, dy / INBOX_SCALE);
    else
        psx_mod_counter_add("moh_mouse.dropped", 1);
}

static void on_activate(void) {
    moh_look_init(&g_look, option_sensitivity(), option_invert_y(), MOH_PITCH_RATE_PER_FIXED);
    g_vblanks = g_hook_vblank = 0;
    g_hook_seen = 0;
    atomic_store(&g_inbox_x, 0);
    atomic_store(&g_inbox_y, 0);
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
    psx_mod_register_vblank_plugin(PLUGIN_ID, on_vblank);
    psx_mod_register_option_changed_plugin(PLUGIN_ID, on_option_changed);
    psx_mod_register_command("moh_mouse", cmd_moh_mouse);
}
