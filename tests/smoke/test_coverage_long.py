"""Unit tests for coverage_long's per-phase accumulation (no game needed)."""

import contextlib
import io
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import coverage_long  # noqa: E402
from fakes import FakeServer  # noqa: E402


def c(native, static, interp, insns):
    return {"native": native, "static": static, "interp": interp, "insns": insns}


class AccumulateTests(unittest.TestCase):
    def test_windows_accumulate_per_phase(self):
        # A phase may span several runtime instances (e.g. three levels); its
        # share is computed over the summed deltas, never over boot totals.
        segments = [
            ("level", c(0, 5000, 50, 100), c(0, 6000, 60, 300)),     # +1000 static, +10 interp
            ("level", c(0, 100, 0, 0), c(0, 3100, 30, 900)),         # +3000 static, +30 interp
            ("menu", c(0, 0, 0, 0), c(0, 990, 10, 50)),
        ]
        totals = coverage_long.accumulate(segments)
        self.assertEqual(totals["level"], c(0, 4000, 40, 1100))
        self.assertAlmostEqual(coverage_long.share(totals["level"]), 40 / 4040)
        self.assertAlmostEqual(coverage_long.share(totals["menu"]), 0.01)

    def test_empty_phase_counts_as_fully_interpreted(self):
        self.assertEqual(coverage_long.share(c(0, 0, 0, 0)), 1.0)


class FilmTests(unittest.TestCase):
    """BRIEFING is a ~108 s film; mdec_state.dma_in_words restarts at each film."""

    def test_film_words_counts_across_the_restart(self):
        # Measured 2026-10-26: stale intro count, restart at 64, film end at 6968160.
        samples = [11138624, 11138624, 64, 15936, 367136, 6968160, 6968160]
        self.assertEqual(coverage_long.film_words(samples), 6968160)

    def test_no_film_counts_nothing(self):
        self.assertEqual(coverage_long.film_words([11138624] * 5), 0)

    def _briefing_server(self, mdec, polls_until_menu):
        """Entry pointer stays on BRIEFING for polls_until_menu reads after X, then NEW GAME."""
        base = 0x801A93D8
        briefing = base + coverage_long.moh.MENU_RING.index("BRIEFING") * 0x274
        state = {"pressed": False, "reads": 0, "mdec": iter(mdec)}

        def reply(request):
            cmd = request["cmd"]
            if cmd == "press":
                state["pressed"] = True
            elif cmd == "mdec_state":
                return {"id": 1, "ok": True, "dma_in_words": next(state["mdec"])}
            elif cmd == "read_ram":
                if state["pressed"]:
                    state["reads"] += 1
                ptr = base if state["reads"] > polls_until_menu else briefing
                return {"id": 1, "ok": True, "hex": ptr.to_bytes(4, "little").hex()}
            return {"id": 1, "ok": True}

        srv = FakeServer(reply)
        self.addCleanup(srv.close)
        return srv, base

    def test_briefing_waits_for_the_menu_and_counts_the_film(self):
        srv, base = self._briefing_server([500, 500, 64, 3000000, 6968160, 6968160], polls_until_menu=4)
        with mock.patch.object(coverage_long, "BRIEFING_POLL_SECS", 0):
            words = coverage_long.play_briefing(srv.port, base, time.monotonic() + 5)
        self.assertEqual(words, 6968160)

    def test_briefing_without_film_fails(self):
        srv, base = self._briefing_server([500] * 10, polls_until_menu=4)
        with mock.patch.object(coverage_long, "BRIEFING_POLL_SECS", 0), \
                self.assertRaisesRegex(coverage_long.SmokeFailure, "no film"):
            coverage_long.play_briefing(srv.port, base, time.monotonic() + 5)

    def test_briefing_that_never_returns_fails(self):
        srv, base = self._briefing_server([64] * 1000, polls_until_menu=10 ** 9)
        with mock.patch.object(coverage_long, "BRIEFING_POLL_SECS", 0.01), \
                mock.patch.object(coverage_long, "BRIEFING_MAX_SECS", 0.3), \
                self.assertRaisesRegex(coverage_long.SmokeFailure, "did not return"):
            coverage_long.play_briefing(srv.port, base, time.monotonic() + 5)


class FailureReportTests(unittest.TestCase):
    """A failure late in the ~35 min run must not throw away the phases already measured."""

    def test_finished_phases_printed_before_fail(self):
        def videos_and_menus(args, out_root, window, segments):
            segments.append(("videos", c(0, 0, 0, 0), c(0, 990, 1, 5)))
            segments.append(("menus", c(0, 0, 0, 0), c(0, 500, 2, 7)))

        def levels(args, out_root, window, segments):
            raise coverage_long.SmokeFailure("no reads of M3L1 data")

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(coverage_long.psxdbg, "port_in_use", return_value=False), \
                mock.patch.object(coverage_long, "videos_and_menus", videos_and_menus), \
                mock.patch.object(coverage_long, "levels", levels), \
                contextlib.redirect_stdout(io.StringIO()) as out, \
                contextlib.redirect_stderr(io.StringIO()) as err:
            exe = os.path.join(tmp, "game.exe")
            open(exe, "wb").close()
            code = coverage_long.main(["--exe", exe, "--cue", "x.cue", "--out", os.path.join(tmp, "o")])
        self.assertEqual(code, 1)
        self.assertIn("coverage_long: videos: interp=0.0010", out.getvalue())
        self.assertIn("coverage_long: menus: interp=0.0040", out.getvalue())
        self.assertNotIn("levels:", out.getvalue())
        self.assertIn("FAIL: no reads of M3L1 data", err.getvalue())


if __name__ == "__main__":
    unittest.main()
