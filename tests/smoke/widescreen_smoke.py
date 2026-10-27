"""Widescreen smoke test: 16:9 native-wide only in gameplay, 4:3 elsewhere.

Prints one line: widescreen_smoke: OK ... or widescreen_smoke: FAIL: <reason>.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pngcheck  # noqa: E402

DARK_BELOW = 8   # a pixel is dark when every channel is below this


def band_dark_fraction(png_path, nw_extra, rows=None):
    """Share of dark pixels in the left and right outer bands (nw_extra // 2 wide each),
    over the row range rows = (first, end) or the whole height."""
    w, h, bpp, pixel_rows = pngcheck.read_pixels(png_path)
    y0, y1 = rows or (0, h)
    band = nw_extra // 2
    result = []
    for x0 in (0, w - band):
        dark = 0
        for row in pixel_rows[y0:y1]:
            for x in range(x0, x0 + band):
                if max(row[x * bpp:x * bpp + 3]) < DARK_BELOW:
                    dark += 1
        result.append(dark / (band * (y1 - y0)))
    return tuple(result)


def band_diff(png_a, png_b, nw_extra):
    """Mean absolute difference per channel byte over both outer bands (nw_extra // 2 wide each)."""
    w, h, bpp, rows_a = pngcheck.read_pixels(png_a)
    _w, _h, _bpp, rows_b = pngcheck.read_pixels(png_b)
    band = nw_extra // 2
    total = count = 0
    for x0 in (0, w - band):
        for ra, rb in zip(rows_a, rows_b):
            seg_a, seg_b = ra[x0 * bpp:(x0 + band) * bpp], rb[x0 * bpp:(x0 + band) * bpp]
            total += sum(abs(p - q) for p, q in zip(seg_a, seg_b))
            count += len(seg_a)
    return total / count


def find_patch_x(wide_png, narrow_png, box, search):
    """(dx, cost): the x shift of the narrow picture's box (x0, y0, x1, y1) inside the wide
    picture, the offset in range(search[0], search[1] + 1) with the smallest difference, and
    that difference as the mean absolute difference per colour channel (0..255)."""
    _wn, _hn, bpp_n, rows_n = pngcheck.read_pixels(narrow_png)
    ww, _hw, bpp_w, rows_w = pngcheck.read_pixels(wide_png)
    x0, y0, x1, y1 = box
    patch = [rows_n[y][x0 * bpp_n:x1 * bpp_n] for y in range(y0, y1)]
    best, best_dx = None, None
    for dx in range(search[0], search[1] + 1):
        if x0 + dx < 0:
            continue
        if (x1 + dx) > ww:
            break
        cost = 0
        for row, y in zip(patch, range(y0, y1)):
            wide = rows_w[y][(x0 + dx) * bpp_w:(x1 + dx) * bpp_w]
            if bpp_n == bpp_w:
                cost += sum(abs(a - b) for a, b in zip(row, wide))
            else:  # compare RGB only
                cost += sum(abs(row[i * bpp_n + c] - wide[i * bpp_w + c])
                            for i in range(x1 - x0) for c in range(3))
        if best is None or cost < best:
            best, best_dx = cost, dx
    return best_dx, best / ((x1 - x0) * (y1 - y0) * 3)


def drawn_share(stats):
    """Draws that found their tag fresh, per tag call (ws_tag_stats hud/background).
    "stale" is no measure: it also counts later packets reusing an expired address."""
    return stats["hit"] / stats["tag_calls"] if stats["tag_calls"] else 0.0


def present_entry(event):
    """One present_ring event: [seq, frame, path, present_w, disp_w, disp_h, game_mode,
    native_43, fellback, tag_delta, nw_extra, gte_verts, ovh_prims, bd_veto]."""
    return {"path": event[2], "present_w": event[3], "nw_extra": event[10]}


def latest_present(reply):
    return present_entry(reply["events"][-1])


# --------------------------------------------------------------------------
# Runtime checks
# --------------------------------------------------------------------------

import argparse  # noqa: E402
import time  # noqa: E402

import flows  # noqa: E402
import modstate  # noqa: E402
import moh  # noqa: E402
import psxdbg  # noqa: E402
import psxrun  # noqa: E402

SmokeFailure = psxrun.SmokeFailure
REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PACKAGE = ("moh.enhancement.widescreen", "widescreen", {})
INTRO_FRAME = 900         # the intro film is running by then (intro_smoke)
SETTLE_SECS = 1.0
LEVEL_SECS = 300.0
HUD_TOLERANCE = 2
SKY_ROWS = (0, 128)       # upper half: the sky strips; the lower bands are legitimately dark ground


def _fail(msg):
    print(f"widescreen_smoke: FAIL: {msg}")
    return 1


def wide_state(port):
    """gpu_state.ws plus the latest present: {"path", "present_w", "nw_extra", "ws": {...}}."""
    entry = latest_present(psxdbg.send("present_ring", port=port, n=1, timeout=10.0))
    entry["ws"] = psxdbg.send("gpu_state", port=port, timeout=10.0).get("ws", {})
    return entry


def expect_path(port, out_dir, label, wide):
    time.sleep(SETTLE_SECS)
    state = wide_state(port)
    shot = flows.shot(port, out_dir, label + ".png")
    if (state["path"] == "wide") != wide:
        raise SmokeFailure(f"{label}: present path {state['path']!r}, expected "
                           f"{'wide' if wide else 'not wide'} (nw_extra {state['nw_extra']})")
    return state, shot


def check_on(proc, port, out_dir, deadline):
    psxrun.wait_for_ping(proc, port, deadline)
    psxrun.wait_frame(port, INTRO_FRAME, deadline)
    expect_path(port, out_dir, "intro_film", False)
    base = flows.boot_to_menu(proc, port, deadline)
    expect_path(port, out_dir, "menu", False)
    flows.goto(port, moh.MENU_RING.index("NEW GAME"), base, deadline)
    psxrun.press(port, "cross")
    flows.advance_until_level(port, deadline)
    expect_path(port, out_dir, "poster", False)
    flows.wait_until_in_level(port, out_dir, deadline)
    time.sleep(2.0)
    state, shot = expect_path(port, out_dir, "level", True)
    if state["nw_extra"] != moh.WS_NW_EXTRA:
        raise SmokeFailure(f"level: nw_extra {state['nw_extra']}, expected {moh.WS_NW_EXTRA}")
    width = pngcheck.read_pixels(shot)[0]
    if width != moh.WS_WIDE_WIDTH:
        raise SmokeFailure(f"level screenshot is {width} wide, expected {moh.WS_WIDE_WIDTH}")
    hud = check_hud(port, out_dir)
    psxrun.hold_buttons(port, "r2")
    expect_path(port, out_dir, "aim", True)
    crosshair = hud_shift(port, out_dir, "crosshair", moh.WS_CROSSHAIR_BOX)
    psxrun.release(port)
    if abs(crosshair - moh.WS_NW_EXTRA // 2) > HUD_TOLERANCE:
        raise SmokeFailure(f"crosshair shifted by {crosshair}, expected {moh.WS_NW_EXTRA // 2} (centred)")
    sky = check_sky(port, out_dir)
    tags = check_tags(port, "M1L1")
    psxrun.press(port, "start")
    expect_path(port, out_dir, "pause", moh.WS_PAUSE_PATH == "wide")
    psxrun.press(port, "start")
    expect_path(port, out_dir, "resumed", True)
    return (f"level wide={width}x{state['nw_extra']} pause={moh.WS_PAUSE_PATH} hud={hud} "
            f"crosshair={crosshair} sky={sky} drawn={tags}")


def check_sky(port, out_dir):
    """The sky reaches into both side bands: in four view directions the upper half
    of each band is no darker than the 4:3 picture's own edges (plus a margin)."""
    worst = 0.0
    for i in range(4):
        set_yaw(port, moh.WS_SKY_BASE_YAW + i * moh.YAW_UNITS_PER_TURN // 4)
        state, shot = expect_path(port, out_dir, f"sky{i}", True)
        left, right = band_dark_fraction(shot, state["nw_extra"], rows=SKY_ROWS)
        if max(left, right) > moh.WS_SKY_MAX_DARK:
            raise SmokeFailure(f"sky view {i}: upper side bands {left:.3f}/{right:.3f} dark "
                               f"(> {moh.WS_SKY_MAX_DARK}): the sky does not reach the edges")
        worst = max(worst, left, right)
    return f"{worst:.3f}"


def hud_shift(port, out_dir, name, box):
    """Shift of a HUD box between a 4:3 and a 16:9 shot of the same moment; the box
    must be found (a missing element would still report some shift)."""
    wide = flows.shot(port, out_dir, f"{name}_169.png")
    psxdbg.send("display_aspect", port=port, num=4, den=3)
    time.sleep(SETTLE_SECS)
    narrow = flows.shot(port, out_dir, f"{name}_43.png")
    psxdbg.send("display_aspect", port=port, num=16, den=9)
    time.sleep(SETTLE_SECS)
    shift, cost = find_patch_x(wide, narrow, box, moh.WS_HUD_SEARCH)
    if cost > moh.WS_HUD_MAX_COST:
        raise SmokeFailure(f"{name}: no match in the 16:9 shot (best shift {shift}, "
                           f"cost {cost:.1f} > {moh.WS_HUD_MAX_COST})")
    return shift


def check_tags(port, label):
    """The HUD and sky tags are drawn while still fresh (they expire 2 vblanks after
    the hook; MOH builds a frame every 2)."""
    stats = psxdbg.send("ws_tag_stats", port=port, timeout=10.0)
    shares = []
    for kind in ("hud", "background"):
        share = drawn_share(stats[kind])
        if share < moh.WS_TAG_MIN_DRAWN:
            raise SmokeFailure(f"{label}: only {share:.3f} of the {kind} tags were drawn while "
                               f"fresh (< {moh.WS_TAG_MIN_DRAWN}): {stats[kind]}")
        shares.append(f"{share:.3f}")
    return "/".join(shares)


def check_hud(port, out_dir):
    """Compass at the left edge (shift 0), ammo counter at the right edge (shift 170)."""
    got = {}
    for name, box, want in (("compass", moh.WS_HUD_COMPASS_BOX, 0),
                            ("ammo", moh.WS_HUD_AMMO_BOX, moh.WS_NW_EXTRA)):
        got[name] = hud_shift(port, out_dir, name, box)
        if abs(got[name] - want) > HUD_TOLERANCE:
            raise SmokeFailure(f"{name} shifted by {got[name]}, expected {want}")
    return f"{got['compass']}/{got['ammo']}"


def set_yaw(port, units):
    """Face a fixed direction: the player's 16.16 yaw (write_ram writes one byte per call)."""
    owner = psxrun.read_u32(port, moh.PLAYER_OWNER_PTR_ADDR)
    addr = psxrun.read_u32(port, owner + moh.PLAYER_PTR_OFFSET) + moh.PLAYER_YAW_OFFSET
    value = (units << 16) & 0xFFFFFFFF
    for i in range(4):
        psxdbg.send("write_ram", port=port, addr="0x%08X" % (addr + i), val=(value >> (8 * i)) & 0xFF)


def edge_check(mission, level, yaw, side):
    """A view where 4:3 culling dropped big polygons in the wide band: the band is
    lit now, and a 200-px cull margin changes nothing more (nothing is culled)."""
    def check(proc, port, out_dir, deadline):
        base = flows.boot_to_menu(proc, port, deadline)
        if (mission, level) == (1, 1):
            flows.start_new_game(port, base, deadline)
        else:
            flows.start_level(port, base, mission, level, deadline)
        flows.wait_until_in_level(port, out_dir, deadline)
        time.sleep(2.0)
        set_yaw(port, yaw)
        state, shot = expect_path(port, out_dir, f"edge_m{mission}l{level}", True)
        left, right = band_dark_fraction(shot, state["nw_extra"])
        dark = left if side == "left" else right
        if dark > moh.WS_EDGE_MAX_DARK:
            raise SmokeFailure(f"M{mission}L{level} yaw {yaw}: {side} band {dark:.3f} dark "
                               f"(> {moh.WS_EDGE_MAX_DARK}): polygons still culled at the edge")
        psxdbg.send("ws_margin", port=port, value=200)
        time.sleep(SETTLE_SECS)
        wider = flows.shot(port, out_dir, f"edge_m{mission}l{level}_margin200.png")
        psxdbg.send("ws_margin", port=port, value=-1)
        diff = band_diff(shot, wider, state["nw_extra"])
        if diff > moh.WS_MARGIN_MAX_DIFF:
            raise SmokeFailure(f"M{mission}L{level} yaw {yaw}: a wider cull margin changes the bands "
                               f"by {diff:.2f}: something is still culled")
        tags = check_tags(port, f"M{mission}L{level}")
        return f"M{mission}L{level}={dark:.3f}/{diff:.2f}/{tags}"
    return check


def check_off(proc, port, out_dir, deadline):
    base = flows.boot_to_menu(proc, port, deadline)
    flows.start_new_game(port, base, deadline)
    flows.wait_until_in_level(port, out_dir, deadline)
    time.sleep(2.0)
    expect_path(port, out_dir, "level_off", False)
    return "off=4:3"


def run(args, label, check, package):
    out_dir = os.path.join(args.out_root, label)
    os.makedirs(out_dir, exist_ok=True)
    build_dir = os.path.dirname(os.path.abspath(args.exe))
    # Off means an explicit selection without it, whatever the player chose.
    with modstate.enabled(build_dir, None, features=[PACKAGE] if package else []):
        proc = psxrun.launch(args.exe, args.cue, args.game, args.port, out_dir)
        try:
            return check(proc, args.port, out_dir, time.monotonic() + LEVEL_SECS)
        finally:
            try:
                psxdbg.send("clear_input", port=args.port, timeout=2.0)
            except ConnectionError:
                pass
            psxrun.shutdown(proc, args.port)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", required=True)
    ap.add_argument("--cue", required=True)
    ap.add_argument("--port", type=int, default=psxdbg.DEFAULT_PORT)
    ap.add_argument("--out", default="")
    ap.add_argument("--game", default=os.path.join(REPO_ROOT, "game.toml"))
    args = ap.parse_args(argv)
    if psxdbg.port_in_use(args.port):
        return _fail(f"port {args.port} busy - another runtime running?")
    if not os.path.isfile(args.exe):
        return _fail(f"exe not found: {args.exe}")
    args.out_root = os.path.abspath(args.out or os.path.join(
        os.environ.get("TEMP", REPO_ROOT), "widescreen-" + time.strftime("%Y%m%d-%H%M%S")))
    print(f"widescreen_smoke: out={args.out_root}", flush=True)
    try:
        parts = [run(args, "on", check_on, True)]
        for mission, level, yaw, side in moh.WS_EDGE_VIEWS:
            parts.append(run(args, f"edge_m{mission}l{level}", edge_check(mission, level, yaw, side), True))
        parts.append(run(args, "off", check_off, False))
        print("widescreen_smoke: OK " + " ".join(parts))
        return 0
    except SmokeFailure as exc:
        return _fail(str(exc))
    except Exception as exc:  # noqa: BLE001 - keep the one-line contract
        return _fail(f"unexpected error: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    sys.exit(main())
