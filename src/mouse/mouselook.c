#include "mouselook.h"

#include <math.h>

static int clamp_sens(int sensitivity) {
    if (sensitivity < MOH_LOOK_SENS_MIN) return MOH_LOOK_SENS_MIN;
    if (sensitivity > MOH_LOOK_SENS_MAX) return MOH_LOOK_SENS_MAX;
    return sensitivity;
}

/* value + *rem truncated toward zero; the fraction stays in *rem. A result
 * beyond +-max is clamped and its fraction dropped with the excess. */
static int32_t convert(double value, double *rem, double max) {
    const double v = value + *rem;
    if (v > max || v < -max) {
        *rem = 0.0;
        return (int32_t)(v > 0 ? max : -max);
    }
    const double whole = trunc(v);
    *rem = v - whole;
    return (int32_t)whole;
}

void moh_look_init(MohLook *look, int sensitivity, int invert_y, int y_rate_per_fixed) {
    look->y_rate_per_fixed = y_rate_per_fixed;
    look->free_look = 0;
    moh_look_set(look, sensitivity, invert_y);
    moh_look_reset(look);
}

void moh_look_set(MohLook *look, int sensitivity, int invert_y) {
    look->sensitivity = clamp_sens(sensitivity);
    look->invert_y = invert_y != 0;
}

void moh_look_set_free_look(MohLook *look, int on) {
    look->free_look = on != 0;
}

void moh_look_reset(MohLook *look) {
    look->pend_x = look->pend_y = 0.0;
    look->rem_x = look->rem_y = 0.0;
}

void moh_look_motion(MohLook *look, double dx, double dy) {
    look->pend_x += dx;
    look->pend_y += dy;
}

static double per_count(const MohLook *look) {
    return (double)look->sensitivity * MOH_LOOK_FIXED_PER_COUNT;
}

int32_t moh_look_take_yaw(MohLook *look) {
    const int32_t yaw = convert(look->pend_x * per_count(look), &look->rem_x, MOH_LOOK_YAW_MAX);
    look->pend_x = 0.0;
    if (!look->free_look) {
        look->pend_y = 0.0;
        look->rem_y = 0.0;
    }
    return yaw;
}

int32_t moh_look_take_aim_x(MohLook *look) {
    const int32_t rate = convert(look->pend_x * per_count(look), &look->rem_x, MOH_LOOK_RATE_MAX);
    look->pend_x = 0.0;
    return rate;
}

int32_t moh_look_take_aim_y(MohLook *look) {
    const double sign = look->invert_y ? -1.0 : 1.0;
    const int32_t rate = convert(sign * look->pend_y * per_count(look) * look->y_rate_per_fixed,
                                 &look->rem_y, MOH_LOOK_RATE_MAX);
    look->pend_y = 0.0;
    return rate;
}

int moh_look_eligible(uint32_t overlay_word, int paused, uint32_t vblank_now,
                      uint32_t vblank_hook, int hook_seen) {
    return overlay_word == 5 && !paused && hook_seen &&
           (uint32_t)(vblank_now - vblank_hook) <= MOH_LOOK_STALE_VBLANKS;
}
