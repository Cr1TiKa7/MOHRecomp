"""Unit tests for coverage_long's per-phase accumulation (no game needed)."""

import os
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
