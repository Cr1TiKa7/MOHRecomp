#pragma once
/* Mouse-look arithmetic for Medal of Honor: mouse counts -> 16.16 yaw delta
 * and aim-mode pitch rate. No runtime dependencies (unit-tested on its own,
 * tests/native/test_mouselook.c). All calls on the emulation thread. */
#include <stdint.h>

#define MOH_LOOK_SENS_MIN 1
#define MOH_LOOK_SENS_MAX 200
#define MOH_LOOK_FIXED_PER_COUNT 1024   /* 16.16 yaw per mouse count at sensitivity 1 */
#define MOH_LOOK_STALE_VBLANKS 4        /* yaw hook older than this: not in gameplay */
#define MOH_LOOK_YAW_MAX (2048 << 16)   /* at most half a turn per game frame */
/* The game adds rate >> 3 to the crosshair and shifts that left by 7 before
 * clamping it, so a rate beyond this would overflow its 32-bit arithmetic. */
#define MOH_LOOK_RATE_MAX 15728640

typedef struct MohLook {
    int sensitivity;
    int invert_y;
    int rate_per_fixed;      /* aim rate units per 16.16 look-angle unit */
    double pend_x, pend_y;   /* mouse counts since the last yaw take */
    double rem_yaw, rem_rate;
    int32_t rate_ready;      /* pitch rate waiting for the aim hook */
    int rate_taken;          /* the aim hook took rate_ready since the last yaw take */
} MohLook;

void    moh_look_init(MohLook *look, int sensitivity, int invert_y, int rate_per_fixed);
void    moh_look_set(MohLook *look, int sensitivity, int invert_y);   /* live option change */
void    moh_look_reset(MohLook *look);                                /* mouse policy RESET */
void    moh_look_motion(MohLook *look, double dx, double dy);         /* mouse policy MOTION */
/* At the yaw store, once per game frame: the 16.16 yaw delta. Also turns the
 * vertical motion into the next pitch rate, replacing one the aim hook did
 * not take (the aim hook only runs in aim mode). */
int32_t moh_look_take_yaw(MohLook *look);
/* At the aim-rate load: the rate to add (negative = look up), then 0. */
int32_t moh_look_take_pitch_rate(MohLook *look);
int     moh_look_eligible(uint32_t overlay_word, int paused, uint32_t vblank_now,
                          uint32_t vblank_hook, int hook_seen);
