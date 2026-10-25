"""Unit tests for the shared game flows in flows.py."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flows  # noqa: E402
import psxrun  # noqa: E402
from fakes import FakeServer  # noqa: E402


class AdvanceToLevelTests(unittest.TestCase):
    """After NEW GAME the game shows FMVs and a 3-page briefing that waits for X."""

    def test_presses_cross_until_level_word_appears(self):
        words = iter(["07000000", "07000000", "05000000"])

        def reply(request):
            if request.get("cmd") == "read_ram":
                return {"id": 1, "ok": True, "hex": next(words)}
            return {"id": 1, "ok": True}

        srv = FakeServer(reply)
        try:
            flows.advance_until_level(srv.port, time.monotonic() + 5, nudge_secs=0.01)
        finally:
            srv.close()
        presses = [r for r in srv.seen if r["cmd"] == "press"]
        self.assertEqual(len(presses), 2)
        self.assertEqual(presses[0]["buttons"], 0xFFFF & ~0x4000)

    def test_gives_up_with_last_word(self):
        srv = FakeServer(lambda request: {"id": 1, "ok": True, "hex": "07000000"})
        try:
            with self.assertRaisesRegex(psxrun.SmokeFailure, "0x00000007"):
                flows.advance_until_level(srv.port, time.monotonic() + 0.5, nudge_secs=0.01)
        finally:
            srv.close()


class WindowShareTests(unittest.TestCase):
    def test_window_share_uses_deltas(self):
        before = {"native": 0, "static": 1000, "interp": 100, "insns": 0}
        after = {"native": 0, "static": 1990, "interp": 110, "insns": 5}
        self.assertAlmostEqual(flows.window_share(before, after), 0.01)

    def test_window_share_no_dispatches(self):
        c = {"native": 1, "static": 2, "interp": 3, "insns": 4}
        self.assertEqual(flows.window_share(c, dict(c)), 1.0)


class OverlayCountersTests(unittest.TestCase):
    def test_overlay_counters_reads_three_commands(self):
        replies = {
            "overlay_loader_status": {"ok": True, "dispatch_native": 2, "dispatch_interp_fallback": 3},
            "overlay_static_entries": {"ok": True, "total_hits": 5},
            "dirty_ram_stats": {"ok": True, "insns_run": 7},
        }
        srv = FakeServer(lambda request: replies[request["cmd"]])
        try:
            self.assertEqual(flows.overlay_counters(srv.port),
                             {"native": 2, "static": 5, "interp": 3, "insns": 7})
        finally:
            srv.close()

    def test_overlay_counters_without_static_dispatcher(self):
        replies = {
            "overlay_loader_status": {"ok": True, "dispatch_native": 0, "dispatch_interp_fallback": 9},
            "overlay_static_entries": {"ok": False, "error": "no static overlay dispatcher linked"},
            "dirty_ram_stats": {"ok": True, "insns_run": 1},
        }
        srv = FakeServer(lambda request: replies[request["cmd"]])
        try:
            self.assertEqual(flows.overlay_counters(srv.port)["static"], 0)
        finally:
            srv.close()


if __name__ == "__main__":
    unittest.main()
