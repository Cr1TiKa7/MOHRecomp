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


class WaitInLevelTests(unittest.TestCase):
    """The loading poster shows right after LEVEL.BIN lands; the level view differs strongly."""

    def _server(self, colors):
        from test_helpers import _write_png

        shots = iter(colors)

        def reply(request):
            if request["cmd"] == "screenshot":
                _write_png(request["path"], 4, 4, [next(shots)] * 16)
                return {"id": 1, "ok": True, "width": 4, "height": 4}
            return {"id": 1, "ok": True}

        return FakeServer(reply)

    def test_returns_after_two_shots_differ_from_loading_screen(self):
        import tempfile

        bright, dark = (200, 180, 120), (20, 25, 30)
        srv = self._server([bright, bright, dark, dark, dark])
        try:
            with tempfile.TemporaryDirectory() as out:
                flows.wait_until_in_level(srv.port, out, time.monotonic() + 5, poll_secs=0.01)
        finally:
            srv.close()
        self.assertEqual(sum(1 for r in srv.seen if r["cmd"] == "screenshot"), 4)

    def test_dark_poster_and_dark_level_are_told_apart(self):
        # Level 2: "The Fight Continues!" poster vs. night village differ by ~34,
        # while the poster itself only changes by <1 (progress bar).
        import tempfile

        poster, poster_bar, level = (50, 50, 50), (51, 50, 50), (80, 80, 80)
        srv = self._server([poster, poster_bar, level, level, level])
        try:
            with tempfile.TemporaryDirectory() as out:
                flows.wait_until_in_level(srv.port, out, time.monotonic() + 5, poll_secs=0.01)
        finally:
            srv.close()
        self.assertEqual(sum(1 for r in srv.seen if r["cmd"] == "screenshot"), 4)

    def test_gives_up_while_loading_screen_stays(self):
        import tempfile

        bright = (200, 180, 120)
        srv = self._server([bright] * 500)
        try:
            with tempfile.TemporaryDirectory() as out, \
                    self.assertRaisesRegex(psxrun.SmokeFailure, "loading screen"):
                flows.wait_until_in_level(srv.port, out, time.monotonic() + 0.5, poll_secs=0.01)
        finally:
            srv.close()


class WalkRingSizeTests(unittest.TestCase):
    """The ring size is learned: 6 entries on a fresh game, 7 after loading a save."""

    def _ring_server(self, base, size, start):
        from unittest import mock  # noqa: F401
        state = {"i": start}

        def reply(request):
            if request["cmd"] == "press":
                state["i"] = (state["i"] + 1) % size
                return {"id": 1, "ok": True}
            ptr = base + state["i"] * 0x274
            return {"id": 1, "ok": True, "hex": ptr.to_bytes(4, "little").hex()}

        return FakeServer(reply)

    def _walk(self, size, start):
        from unittest import mock

        srv = self._ring_server(0x801A93D8, size, start)
        try:
            with mock.patch.object(flows, "STEP_SECS", 0):
                return flows.walk_ring(srv.port, time.monotonic() + 10)
        finally:
            srv.close()

    def test_six_entry_ring(self):
        self.assertEqual(self._walk(6, 2), (0x801A93D8, 3, 6))

    def test_seven_entry_ring(self):
        self.assertEqual(self._walk(7, 5), (0x801A93D8, 6, 7))

    def test_goto_ptr_reaches_remembered_entry(self):
        # After loading, NEXT MISSION is the entry selected on return - not the
        # lowest pointer - so it is found again by its remembered pointer.
        from unittest import mock

        target = 0x801A93D8 + 5 * 0x274
        srv = self._ring_server(0x801A93D8, 7, 2)
        try:
            with mock.patch.object(flows, "STEP_SECS", 0):
                flows.goto_ptr(srv.port, target, 7, time.monotonic() + 10)
                self.assertEqual(flows.entry_ptr(srv.port), target)
        finally:
            srv.close()
        self.assertEqual(sum(1 for r in srv.seen if r["cmd"] == "press"), 3)


class CdReadsTests(unittest.TestCase):
    """cd_read_log logs the start LBA of each read; count only reads since a mark."""

    def test_reads_since_mark_in_range(self):
        def reply(request):
            if request.get("lba_lo") is None:
                return {"id": 1, "ok": True, "total": 130, "count": 1, "entries": []}
            return {"id": 1, "ok": True, "total": 130, "count": request["tail"],
                    "entries": [{"lba": 6292, "dest": "0x0", "size": 2048}]}

        srv = FakeServer(reply)
        try:
            self.assertEqual(flows.cd_reads_in(srv.port, 100, (6292, 10935)), [6292])
        finally:
            srv.close()
        ranged = [r for r in srv.seen if "lba_lo" in r]
        self.assertEqual((ranged[0]["tail"], ranged[0]["lba_lo"], ranged[0]["lba_hi"]), (30, 6292, 10935))


class RamHitsTests(unittest.TestCase):
    """Game RAM starts at 0x80010000; below it the BIOS caches the card directory."""

    def test_hits_below_game_ram_ignored(self):
        ram = bytearray(0x20000)
        ram[0x4E3E:0x4E44] = b"PASCAL"
        ram[0x1AA00:0x1AA06] = b"PASCAL"
        self.assertEqual(flows.ram_hits(bytes(ram), b"PASCAL"), [0x8001AA00])

    def test_no_hits(self):
        self.assertEqual(flows.ram_hits(bytes(0x20000), b"PASCAL"), [])


if __name__ == "__main__":
    unittest.main()
