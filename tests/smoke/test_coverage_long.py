"""Unit tests for coverage_long's per-phase accumulation (no game needed)."""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import coverage_long  # noqa: E402


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
