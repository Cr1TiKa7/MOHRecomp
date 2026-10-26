"""Unit tests for the smoke-test helpers (stdlib only).

Run from the repo root:  py -3 -m unittest discover -s tests/smoke -v
"""

import contextlib
import io
import os
import struct
import sys
import tempfile
import time
import unittest
import zlib
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pngcheck  # noqa: E402
import psxdbg  # noqa: E402
from fakes import FakeServer, _FakeProc, free_port as _free_port  # noqa: E402


# --------------------------------------------------------------------------
# PNG writer used only by the tests (applies a chosen filter to every row)
# --------------------------------------------------------------------------

def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _filter_row(ftype, row, prev, bpp):
    out = bytearray()
    for i, x in enumerate(row):
        a = row[i - bpp] if i >= bpp else 0
        b = prev[i]
        c = prev[i - bpp] if i >= bpp else 0
        if ftype == 0:
            pred = 0
        elif ftype == 1:
            pred = a
        elif ftype == 2:
            pred = b
        elif ftype == 3:
            pred = (a + b) // 2
        else:
            pred = _paeth(a, b, c)
        out.append((x - pred) & 0xFF)
    return bytes(out)


def _chunk(tag, data):
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _write_png(path, w, h, pixels, color_type=2, filter_type=0):
    """pixels: list of tuples, row-major. color_type 2 = RGB, 6 = RGBA."""
    bpp = 3 if color_type == 2 else 4
    raw = bytearray()
    prev = bytes(w * bpp)
    for y in range(h):
        row = bytes(v for px in pixels[y * w:(y + 1) * w] for v in px)
        raw.append(filter_type)
        raw += _filter_row(filter_type, row, prev, bpp)
        prev = row
    ihdr = struct.pack(">IIBBBBB", w, h, 8, color_type, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(_chunk(b"IHDR", ihdr))
        f.write(_chunk(b"IDAT", zlib.compress(bytes(raw))))
        f.write(_chunk(b"IEND", b""))


class PngCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "t.png")

    def tearDown(self):
        self.tmp.cleanup()

    def test_uniform_rgb_has_one_color(self):
        _write_png(self.path, 4, 4, [(0, 0, 0)] * 16, filter_type=0)
        self.assertEqual(pngcheck.distinct_colors(self.path), 1)

    def test_two_colors_with_paeth_filter(self):
        px = [(255, 255, 255) if (x + y) % 2 else (0, 0, 0) for y in range(4) for x in range(4)]
        _write_png(self.path, 4, 4, px, filter_type=4)
        self.assertEqual(pngcheck.distinct_colors(self.path), 2)

    def test_rgba_counts_alpha_as_distinct(self):
        _write_png(self.path, 2, 1, [(1, 2, 3, 255), (1, 2, 3, 0)], color_type=6)
        self.assertEqual(pngcheck.distinct_colors(self.path), 2)

    def test_limit_stops_counting(self):
        px = [(x, y, (x * y) & 0xFF) for y in range(16) for x in range(16)]
        _write_png(self.path, 16, 16, px, filter_type=1)
        self.assertEqual(pngcheck.distinct_colors(self.path, limit=10), 10)

    def test_palette_png_rejected(self):
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 3, 0, 0, 0)
        with open(self.path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IEND", b""))
        with self.assertRaises(ValueError):
            pngcheck.distinct_colors(self.path)

    def test_mean_abs_diff_identical_is_zero(self):
        px = [(x * 10, y * 20, 7) for y in range(4) for x in range(4)]
        _write_png(self.path, 4, 4, px, filter_type=2)
        self.assertEqual(pngcheck.mean_abs_diff(self.path, self.path), 0.0)

    def test_mean_abs_diff_known_value(self):
        other = os.path.join(self.tmp.name, "u.png")
        _write_png(self.path, 2, 2, [(0, 0, 0)] * 4, filter_type=3)
        _write_png(other, 2, 2, [(30, 30, 30)] * 2 + [(0, 0, 0)] * 2, filter_type=4)
        self.assertEqual(pngcheck.mean_abs_diff(self.path, other), 15.0)

    def test_mean_abs_diff_size_mismatch_raises(self):
        other = os.path.join(self.tmp.name, "u.png")
        _write_png(self.path, 2, 2, [(0, 0, 0)] * 4)
        _write_png(other, 4, 1, [(0, 0, 0)] * 4)
        with self.assertRaises(ValueError):
            pngcheck.mean_abs_diff(self.path, other)

    def test_half_diffs_split_top_and_bottom(self):
        other = os.path.join(self.tmp.name, "u.png")
        _write_png(self.path, 2, 4, [(0, 0, 0)] * 8, filter_type=1)
        _write_png(other, 2, 4, [(0, 0, 0)] * 4 + [(30, 30, 30)] * 2 + [(0, 0, 0)] * 2)
        self.assertEqual(pngcheck.half_diffs(self.path, other), (0.0, 15.0))


class PsxDbgTests(unittest.TestCase):
    def test_send_roundtrip(self):
        srv = FakeServer({"id": 1, "frame": 42})
        try:
            self.assertEqual(psxdbg.send("ping", port=srv.port), {"id": 1, "frame": 42})
            self.assertEqual(srv.seen, [{"id": 1, "cmd": "ping"}])
        finally:
            srv.close()

    def test_send_passes_params(self):
        srv = FakeServer({"id": 1, "ok": True})
        try:
            psxdbg.send("screenshot", port=srv.port, path="a.png")
            self.assertEqual(srv.seen[0]["cmd"], "screenshot")
            self.assertEqual(srv.seen[0]["path"], "a.png")
        finally:
            srv.close()

    def test_payload_may_carry_port(self):
        # The debug command's own "port" field (pad port) cannot be a kwarg:
        # send()'s port= is the TCP port.
        srv = FakeServer({"id": 1, "ok": True})
        try:
            psxdbg.send("press", port=srv.port, payload={"port": 2, "buttons": 0xFFFF})
        finally:
            srv.close()
        self.assertEqual(srv.seen, [{"id": 1, "cmd": "press", "port": 2, "buttons": 0xFFFF}])

    def test_send_no_listener_raises(self):
        with self.assertRaises(ConnectionError):
            psxdbg.send("ping", port=_free_port(), timeout=1.0)

    def test_port_in_use(self):
        srv = FakeServer({"id": 1})
        try:
            self.assertTrue(psxdbg.port_in_use(srv.port))
        finally:
            srv.close()
        self.assertFalse(psxdbg.port_in_use(_free_port()))


class BootSmokeTests(unittest.TestCase):
    def test_refuses_busy_port(self):
        import subprocess

        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boot_smoke.py")
        srv = FakeServer({"id": 1})
        try:
            proc = subprocess.run(
                [sys.executable, script, "--exe", "does-not-exist.exe", "--cue", "x.cue",
                 "--port", str(srv.port)],
                capture_output=True, text=True, timeout=30,
            )
        finally:
            srv.close()
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("busy", proc.stderr)

    def test_frame_check_uses_frame_command(self):
        # The real runtime answers "ping" on its I/O thread without a frame
        # counter; only the "frame" command reports emulated frames.
        import boot_smoke

        frames = iter(range(100, 1000, 50))

        def reply(request):
            if request.get("cmd") == "ping":
                return {"id": 0, "ok": True, "pong": True, "io_thread": True}
            return {"id": 1, "ok": True, "frame": next(frames)}

        srv = FakeServer(reply)
        try:
            later = boot_smoke._check_frames_advance(srv.port, time.monotonic() + 10)
        finally:
            srv.close()
        self.assertEqual(later["frame"], 150)
        self.assertEqual([r["cmd"] for r in srv.seen], ["frame", "frame"])

    def test_frame_check_retries_until_frame_reported(self):
        # A cold-starting runtime may answer without a frame counter at first.
        import boot_smoke

        replies = iter([{"id": 1, "ok": False, "error": "not ready"},
                        {"id": 1, "ok": True, "frame": 100},
                        {"id": 1, "ok": True, "frame": 150}])
        srv = FakeServer(lambda request: next(replies))
        try:
            later = boot_smoke._check_frames_advance(srv.port, time.monotonic() + 10)
        finally:
            srv.close()
        self.assertEqual(later["frame"], 150)

    def test_unexpected_error_is_one_line_failure(self):
        import boot_smoke

        stderr = io.StringIO()
        with mock.patch.object(boot_smoke.subprocess, "Popen", return_value=_FakeProc(None)), \
                mock.patch.object(boot_smoke, "_wait_for_ping", side_effect=ValueError("bad json")), \
                contextlib.redirect_stderr(stderr):
            rc = boot_smoke.main(["--exe", sys.executable, "--cue", "x.cue",
                                  "--port", str(_free_port()), "--out", self.tmp.name])
        self.assertEqual(rc, 1)
        lines = stderr.getvalue().strip().splitlines()
        self.assertEqual(len(lines), 1, stderr.getvalue())
        self.assertIn("ValueError: bad json", lines[0])

    def test_non_ascii_out_dir_rejected(self):
        import boot_smoke

        stderr = io.StringIO()
        with mock.patch.object(boot_smoke.subprocess, "Popen") as popen, \
                contextlib.redirect_stderr(stderr):
            rc = boot_smoke.main(["--exe", sys.executable, "--cue", "x.cue",
                                  "--port", str(_free_port()),
                                  "--out", os.path.join(self.tmp.name, "smöke")])
        self.assertEqual(rc, 1)
        self.assertIn("ASCII", stderr.getvalue())
        popen.assert_not_called()

    def _card(self, data):
        path = os.path.join(self.tmp.name, "card1.mcd")
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_memcard_ok(self):
        import boot_smoke

        boot_smoke.check_memcard(self._card(b"MC" + bytes(131070)))

    def test_memcard_missing(self):
        import boot_smoke

        with self.assertRaisesRegex(boot_smoke.SmokeFailure, "missing"):
            boot_smoke.check_memcard(os.path.join(self.tmp.name, "nope.mcd"))

    def test_memcard_wrong_size(self):
        import boot_smoke

        with self.assertRaisesRegex(boot_smoke.SmokeFailure, "size"):
            boot_smoke.check_memcard(self._card(b"MC" + bytes(998)))

    def test_memcard_unformatted(self):
        import boot_smoke

        with self.assertRaisesRegex(boot_smoke.SmokeFailure, "format"):
            boot_smoke.check_memcard(self._card(bytes(131072)))

    def test_relative_paths_made_absolute(self):
        import boot_smoke

        stderr = io.StringIO()
        with mock.patch.object(boot_smoke.subprocess, "Popen", return_value=_FakeProc(0)) as popen, \
                contextlib.redirect_stderr(stderr):
            boot_smoke.main(["--exe", sys.executable, "--cue", "x.cue",
                             "--port", str(_free_port()), "--out", self.tmp.name])
        cmd = popen.call_args.args[0]
        self.assertTrue(os.path.isabs(cmd[cmd.index("--disc") + 1]), cmd)
        self.assertTrue(os.path.isabs(cmd[cmd.index("--memcard-dir") + 1]), cmd)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()


class KeybindsTests(unittest.TestCase):
    """config/keybinds.ini: player 1's mouse + keyboard layout (M4)."""

    def setUp(self):
        import configparser
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config", "keybinds.ini")
        parser = configparser.ConfigParser()
        with open(path, encoding="utf-8") as f:
            parser.read_file(f)
        self.p1 = {k: [b.strip() for b in v.split(",")] for k, v in parser["player1"].items()}

    def test_mouse_buttons_fire_and_aim(self):
        self.assertIn("Mouse1", self.p1["cross"])
        self.assertIn("Mouse3", self.p1["r2"])

    def test_a_and_d_strafe(self):
        self.assertEqual(self.p1["l1"][0], "A")
        self.assertEqual(self.p1["r1"][0], "D")

    def test_triangle_has_a_key_besides_escape(self):
        # Escape first releases the captured mouse, so triangle (look up) needs another key.
        self.assertIn("Escape", self.p1["triangle"])
        self.assertIn("F", self.p1["triangle"])

    def test_sticks_are_unbound(self):
        # An analog P1 would otherwise get every key twice (d-pad and stick).
        for name in ("ls_up", "ls_down", "ls_left", "ls_right", "rs_up", "rs_down", "rs_left", "rs_right"):
            self.assertEqual(self.p1[name], ["None"], name)

    def test_no_key_drives_two_inputs(self):
        seen = {}
        for name, keys in self.p1.items():
            for key in keys:
                if key != "None":
                    self.assertNotIn(key, seen, f"{key} bound to {seen.get(key)} and {name}")
                    seen[key] = name


if __name__ == "__main__":
    unittest.main()
