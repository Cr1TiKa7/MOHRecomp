/* Unit tests for src/mouse/mouselook.c. Prints each failed check, exits 1 on any. */
#include <stdint.h>
#include <stdio.h>

#include "mouselook.h"

static int failures;
#define CHECK(cond) \
    do { if (!(cond)) { failures++; printf("FAIL %s:%d: %s\n", __func__, __LINE__, #cond); } } while (0)

static MohLook look;
static void init(int sens, int invert) { moh_look_init(&look, sens, invert, 2); }

static void yaw_exact(void) {
    init(40, 0);
    moh_look_motion(&look, 100, 0);
    CHECK(moh_look_take_yaw(&look) == 4096000);
    CHECK(moh_look_take_yaw(&look) == 0);
}

static void fraction_carries(void) {
    int32_t sum = 0;
    init(1, 0);
    for (int i = 0; i < 10; i++) { moh_look_motion(&look, 0.0001, 0); sum += moh_look_take_yaw(&look); }
    CHECK(sum == 1);
}

static void negative_carries(void) {
    int32_t sum = 0;
    init(1, 0);
    for (int i = 0; i < 10; i++) { moh_look_motion(&look, -0.0001, 0); sum += moh_look_take_yaw(&look); }
    CHECK(sum == -1);
}

static void reset_drops(void) {
    init(40, 0);
    moh_look_motion(&look, 50, 50);
    moh_look_reset(&look);
    CHECK(moh_look_take_yaw(&look) == 0);
    CHECK(moh_look_take_aim_x(&look) == 0);
    CHECK(moh_look_take_aim_y(&look) == 0);
}

static void yaw_drops_vertical(void) {
    init(40, 0);
    moh_look_motion(&look, 0, 10);
    CHECK(moh_look_take_yaw(&look) == 0);
    CHECK(moh_look_take_aim_y(&look) == 0);   /* no aim mode this frame: vertical motion is gone */
}

static void free_look_keeps_vertical(void) {
    init(40, 0);
    moh_look_set_free_look(&look, 1);
    moh_look_motion(&look, 100, 10);
    CHECK(moh_look_take_yaw(&look) == 4096000);
    CHECK(moh_look_take_aim_y(&look) == 10 * 40 * 1024 * 2);   /* the normal-play tilt rate takes it */
    moh_look_motion(&look, 0, 0.0001);                          /* 8.192 rate units: the fraction */
    CHECK(moh_look_take_yaw(&look) == 0);                       /* survives the yaw store */
    CHECK(moh_look_take_aim_y(&look) == 8);
    moh_look_set_free_look(&look, 0);
    moh_look_motion(&look, 0, 10);
    CHECK(moh_look_take_yaw(&look) == 0);
    CHECK(moh_look_take_aim_y(&look) == 0);
}

static void free_look_carries_the_fraction(void) {
    init(40, 0);
    moh_look_set_free_look(&look, 1);
    int32_t sum = 0;
    for (int i = 0; i < 10; i++) {               /* 8.192 rate units per frame */
        moh_look_motion(&look, 0, 0.0001);
        moh_look_take_yaw(&look);
        sum += moh_look_take_aim_y(&look);
    }
    CHECK(sum == 81);                            /* 80 if the yaw store dropped the remainder */
}

static void skipped_tilt_load_drops_vertical(void) {
    init(40, 0);
    moh_look_set_free_look(&look, 1);
    moh_look_motion(&look, 0, 10);
    moh_look_take_yaw(&look);                    /* frame 1: no tilt load (L3 held) */
    moh_look_motion(&look, 0, 10);
    moh_look_take_yaw(&look);                    /* frame 2: frame 1's motion is gone */
    CHECK(moh_look_take_aim_y(&look) == 0);      /* not 2 * 819200 at once */
    moh_look_motion(&look, 0, 10);
    moh_look_take_yaw(&look);                    /* frame 3: the load ran last frame */
    CHECK(moh_look_take_aim_y(&look) == 819200);
}

static void drop_y(void) {
    init(40, 0);
    moh_look_set_free_look(&look, 1);
    moh_look_motion(&look, 0, 0.0001);
    CHECK(moh_look_take_aim_y(&look) == 8);      /* leaves 0.192 */
    moh_look_motion(&look, 100, 10);
    moh_look_drop_y(&look);
    CHECK(moh_look_take_yaw(&look) == 4096000);  /* horizontal motion stays */
    moh_look_motion(&look, 0, 0.0001);
    CHECK(moh_look_take_aim_y(&look) == 8);      /* 8.192 alone: the remainder went too */
}

static void aim_x_rate(void) {
    init(40, 0);
    moh_look_motion(&look, 100, 0);
    CHECK(moh_look_take_aim_x(&look) == 4096000);
    CHECK(moh_look_take_aim_x(&look) == 0);
}

static void aim_y_rate(void) {
    init(40, 0);
    moh_look_motion(&look, 0, 10);
    CHECK(moh_look_take_aim_y(&look) == 819200);
    CHECK(moh_look_take_aim_y(&look) == 0);
}

static void aim_axes_independent(void) {
    init(40, 0);
    moh_look_motion(&look, 100, 10);
    CHECK(moh_look_take_aim_y(&look) == 819200);
    CHECK(moh_look_take_aim_x(&look) == 4096000);
}

static void mouse_up_looks_up(void) {
    init(40, 0);
    moh_look_motion(&look, 0, -10);
    CHECK(moh_look_take_aim_y(&look) == -819200);
}

static void aim_fraction_carries(void) {
    int32_t sum = 0;
    init(1, 0);
    for (int i = 0; i < 10; i++) { moh_look_motion(&look, 0, 0.0001); sum += moh_look_take_aim_y(&look); }
    CHECK(sum == 2);
}

static void invert(void) {
    init(40, 1);
    moh_look_motion(&look, 0, 10);
    CHECK(moh_look_take_aim_y(&look) == -819200);
    moh_look_motion(&look, 100, 0);
    CHECK(moh_look_take_aim_x(&look) == 4096000);   /* X is never inverted */
}

static void rate_clamp(void) {
    init(40, 0);
    moh_look_motion(&look, 1e6, 1e6);
    CHECK(moh_look_take_aim_x(&look) == MOH_LOOK_RATE_MAX);
    CHECK(moh_look_take_aim_y(&look) == MOH_LOOK_RATE_MAX);
    moh_look_motion(&look, -1e6, -1e6);
    CHECK(moh_look_take_aim_x(&look) == -MOH_LOOK_RATE_MAX);
    CHECK(moh_look_take_aim_y(&look) == -MOH_LOOK_RATE_MAX);
    CHECK(moh_look_take_aim_y(&look) == 0);   /* the excess is dropped, not carried */
}

static void yaw_clamp(void) {
    init(200, 0);
    moh_look_motion(&look, 1e9, 0);
    CHECK(moh_look_take_yaw(&look) == MOH_LOOK_YAW_MAX);
    CHECK(moh_look_take_yaw(&look) == 0);
    moh_look_motion(&look, -1e9, 0);
    CHECK(moh_look_take_yaw(&look) == -MOH_LOOK_YAW_MAX);
}

static void sens_bounds(void) {
    init(0, 0);
    moh_look_motion(&look, 1, 0);
    CHECK(moh_look_take_yaw(&look) == 1024);
    init(500, 0);
    moh_look_motion(&look, 1, 0);
    CHECK(moh_look_take_yaw(&look) == 200 * 1024);
}

static void live_set(void) {
    init(1, 0);
    moh_look_motion(&look, 1, 0);
    moh_look_set(&look, 2, 0);
    CHECK(moh_look_take_yaw(&look) == 2048);
    moh_look_set(&look, 40, 1);
    moh_look_motion(&look, 0, 10);
    CHECK(moh_look_take_aim_y(&look) == -819200);
}

static void eligible(void) {
    CHECK(moh_look_eligible(5, 0, 100, 98, 1) == 1);
    /* A slow game frame (5+ VBlanks) or an R2 transition must not count as
     * leaving gameplay: that releases the captured mouse mid-fight and the
     * next click only recaptures instead of firing. */
    CHECK(moh_look_eligible(5, 0, 100, 90, 1) == 1);
    CHECK(moh_look_eligible(5, 0, 100, 88, 1) == 1);
    CHECK(moh_look_eligible(5, 0, 100, 87, 1) == 0);
    CHECK(moh_look_eligible(6, 0, 100, 99, 1) == 0);
    CHECK(moh_look_eligible(5, 0, 100, 99, 0) == 0);
    CHECK(moh_look_eligible(5, 1, 100, 99, 1) == 0);
    CHECK(moh_look_eligible(5, 0, 2, 0xFFFFFFFEu, 1) == 1);
}

int main(void) {
    yaw_exact();
    fraction_carries();
    negative_carries();
    reset_drops();
    yaw_drops_vertical();
    free_look_keeps_vertical();
    free_look_carries_the_fraction();
    drop_y();
    skipped_tilt_load_drops_vertical();
    aim_x_rate();
    aim_y_rate();
    aim_axes_independent();
    mouse_up_looks_up();
    aim_fraction_carries();
    invert();
    rate_clamp();
    yaw_clamp();
    sens_bounds();
    live_set();
    eligible();
    printf(failures ? "mouselook: %d check(s) failed\n" : "mouselook: all checks passed\n", failures);
    return failures ? 1 : 0;
}
