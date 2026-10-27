#pragma once
/* Mouse-look arithmetic for Medal of Honor: mouse counts -> 16.16 yaw delta
 * (normal play), the normal-play tilt rate (free look) and the two aim-mode
 * rates (R2 held). No runtime dependencies (unit-tested on its own,
 * tests/native/test_mouselook.c). All calls on the emulation thread. Each
 * game frame runs either the yaw store and the tilt rate load (normal play)
 * or the aim function (aim mode), and those hooks take all pending motion. */
#include <stdint.h>

#define MOH_LOOK_SENS_MIN 1
#define MOH_LOOK_SENS_MAX 200
#define MOH_LOOK_FIXED_PER_COUNT 1024   /* 16.16 yaw per mouse count at sensitivity 1 */
/* Hook older than this (240 ms): not in gameplay, the policy releases the
 * mouse. Wide enough for slow game frames and R2 transitions; a pause or
 * menu still ends gameplay within a quarter second. */
#define MOH_LOOK_STALE_VBLANKS 12
#define MOH_LOOK_YAW_MAX (2048 << 16)   /* at most half a turn per game frame */
/* The game adds rate >> 3 to a crosshair coordinate and shifts that left by
 * 7 or 8 before clamping it, so a rate beyond this would overflow its 32-bit
 * arithmetic. */
#define MOH_LOOK_RATE_MAX 15728640

typedef struct MohLook {
    int sensitivity;
    int invert_y;
    int free_look;           /* normal play: vertical motion tilts the camera */
    int y_rate_per_fixed;    /* vertical aim rate units per 16.16 look-angle unit */
    double pend_x, pend_y;   /* mouse counts not taken yet */
    double rem_x, rem_y;     /* sub-unit remainders */
} MohLook;

void    moh_look_init(MohLook *look, int sensitivity, int invert_y, int y_rate_per_fixed);
void    moh_look_set(MohLook *look, int sensitivity, int invert_y);   /* live option change */
void    moh_look_set_free_look(MohLook *look, int on);                /* off after init */
void    moh_look_reset(MohLook *look);                                /* mouse policy RESET */
void    moh_look_motion(MohLook *look, double dx, double dy);         /* mouse policy MOTION */
/* Normal play, at the yaw store: the 16.16 yaw delta. Vertical motion stays
 * for the tilt rate load with free look, and is dropped without it. */
int32_t moh_look_take_yaw(MohLook *look);
/* Aim mode, at the rate loads: the horizontal rate (one unit per 16.16 yaw
 * unit; the game turns by the full rate past the crosshair limit) and the
 * vertical rate (negative = look up; the game tilts by half the rate). The
 * normal-play tilt rate (right stick) has the same scale, so free look takes
 * moh_look_take_aim_y there too. */
int32_t moh_look_take_aim_x(MohLook *look);
int32_t moh_look_take_aim_y(MohLook *look);
int     moh_look_eligible(uint32_t overlay_word, int paused, uint32_t vblank_now,
                          uint32_t vblank_hook, int hook_seen);
