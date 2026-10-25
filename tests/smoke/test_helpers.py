"""Unit tests for the smoke-test helpers (stdlib only).

Run from the repo root:  py -3 -m unittest discover -s tests/smoke -v
"""

import json
import os
import socket
import struct
import sys
import tempfile
import threading
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pngcheck  # noqa: E402
import psxdbg  # noqa: E402


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


# --------------------------------------------------------------------------
# Fake debug server: accepts connections, reads one line, answers one line
# --------------------------------------------------------------------------

class FakeServer:
    def __init__(self, reply):
        self.reply = reply
        self.seen = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self._stop = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        self.sock.settimeout(0.2)
        while not self._stop:
            try:
                conn, _ = self.sock.accept()
            except (socket.timeout, OSError):
                continue
            with conn:
                buf = b""
                conn.settimeout(2.0)
                try:
                    while not buf.endswith(b"\n"):
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                except socket.timeout:
                    pass
                request = json.loads(buf.decode()) if buf.strip() else {}
                if request:
                    self.seen.append(request)
                reply = self.reply(request) if callable(self.reply) else self.reply
                conn.sendall((json.dumps(reply) + "\n").encode())

    def close(self):
        self._stop = True
        self.sock.close()
        self.thread.join(timeout=2)


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


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
            later = boot_smoke._check_frames_advance(srv.port)
        finally:
            srv.close()
        self.assertEqual(later["frame"], 150)
        self.assertEqual([r["cmd"] for r in srv.seen], ["frame", "frame"])


if __name__ == "__main__":
    unittest.main()
