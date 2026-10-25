"""Unit tests for the shared runtime helpers in psxrun (stdlib only)."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psxrun  # noqa: E402
from fakes import FakeServer  # noqa: E402


class MaskTests(unittest.TestCase):
    def test_mask_start(self):
        self.assertEqual(psxrun.mask("start"), 0xFFF7)

    def test_mask_combines(self):
        self.assertEqual(psxrun.mask("up", "cross"), 0xFFFF & ~0x4010)

    def test_mask_unknown_raises(self):
        with self.assertRaises(KeyError):
            psxrun.mask("jump")


class RemoteTests(unittest.TestCase):
    def test_press_sends_inverted_mask(self):
        srv = FakeServer({"id": 1, "ok": True})
        try:
            psxrun.press(srv.port, "right")
        finally:
            srv.close()
        self.assertEqual(srv.seen, [{"id": 1, "cmd": "press", "buttons": 0xFFDF, "frames": 4}])

    def test_wait_frame_returns_first_reaching(self):
        frames = iter([10, 20, 30, 40])
        srv = FakeServer(lambda request: {"id": 1, "ok": True, "frame": next(frames)})
        try:
            self.assertEqual(psxrun.wait_frame(srv.port, 25, time.monotonic() + 5), 30)
        finally:
            srv.close()

    def test_wait_frame_times_out(self):
        srv = FakeServer({"id": 1, "ok": True, "frame": 1})
        try:
            with self.assertRaises(TimeoutError):
                psxrun.wait_frame(srv.port, 5, time.monotonic() + 1)
        finally:
            srv.close()

    def test_read_bytes_decodes_hex(self):
        srv = FakeServer({"id": 1, "ok": True, "hex": "0a0b"})
        try:
            self.assertEqual(psxrun.read_bytes(srv.port, 0x80000000, 2), b"\x0a\x0b")
        finally:
            srv.close()
        self.assertEqual(srv.seen[0]["addr"], "0x80000000")
        self.assertEqual(srv.seen[0]["len"], 2)


if __name__ == "__main__":
    unittest.main()
