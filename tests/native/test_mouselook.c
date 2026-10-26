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
    CHECK(moh_look_take_pitch_rate(&look) == 0);
}

static void reset_drops_ready_rate(void) {
    init(40, 0);
    moh_look_motion(&look, 0, 10);
    moh_look_take_yaw(&look);
    moh_look_reset(&look);
    CHECK(moh_look_take_pitch_rate(&look) == 0);
}

static void pitch_after_take(void) {
    init(40, 0);
    moh_look_motion(&look, 0, 10);
    CHECK(moh_look_take_pitch_rate(&look) == 0);   /* not converted before the frame's yaw take */
    CHECK(moh_look_take_yaw(&look) == 0);
    CHECK(moh_look_take_pitch_rate(&look) == 819200);
    CHECK(moh_look_take_pitch_rate(&look) == 0);
}

static void mouse_up_looks_up(void) {
    init(40, 0);
    moh_look_motion(&look, 0, -10);
    moh_look_take_yaw(&look);
    CHECK(moh_look_take_pitch_rate(&look) == -819200);
}

static void pitch_stale_dropped(void) {
    init(40, 0);
    moh_look_motion(&look, 0, 10);
    moh_look_take_yaw(&look);
    moh_look_take_yaw(&look);
    CHECK(moh_look_take_pitch_rate(&look) == 0);
}

static void pitch_fraction_carries(void) {
    int32_t sum = 0;
    init(1, 0);
    for (int i = 0; i < 10; i++) {
        moh_look_motion(&look, 0, 0.0001);
        moh_look_take_yaw(&look);
        sum += moh_look_take_pitch_rate(&look);
    }
    CHECK(sum == 2);
}

static void invert(void) {
    init(40, 1);
    moh_look_motion(&look, 0, 10);
    moh_look_take_yaw(&look);
    CHECK(moh_look_take_pitch_rate(&look) == -819200);
}

static void rate_clamp(void) {
    init(40, 0);
    moh_look_motion(&look, 0, 1e6);
    moh_look_take_yaw(&look);
    CHECK(moh_look_take_pitch_rate(&look) == MOH_LOOK_RATE_MAX);
    moh_look_motion(&look, 0, -1e6);
    moh_look_take_yaw(&look);
    CHECK(moh_look_take_pitch_rate(&look) == -MOH_LOOK_RATE_MAX);
    moh_look_take_yaw(&look);
    CHECK(moh_look_take_pitch_rate(&look) == 0);   /* the excess is dropped, not carried */
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
    moh_look_take_yaw(&look);
    CHECK(moh_look_take_pitch_rate(&look) == -819200);
}

static void eligible(void) {
    CHECK(moh_look_eligible(5, 0, 100, 98, 1) == 1);
    CHECK(moh_look_eligible(5, 0, 100, 96, 1) == 1);
    CHECK(moh_look_eligible(5, 0, 100, 95, 1) == 0);
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
    reset_drops_ready_rate();
    pitch_after_take();
    mouse_up_looks_up();
    pitch_stale_dropped();
    pitch_fraction_carries();
    invert();
    rate_clamp();
    yaw_clamp();
    sens_bounds();
    live_set();
    eligible();
    printf(failures ? "mouselook: %d check(s) failed\n" : "mouselook: all checks passed\n", failures);
    return failures ? 1 : 0;
}
