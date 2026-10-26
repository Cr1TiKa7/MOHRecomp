"""Unit tests for sweep_smoke's level loop (no game needed)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psxrun  # noqa: E402
import sweep_smoke  # noqa: E402


class RunAllTests(unittest.TestCase):
    """One failing (or crashing) level must not stop the sweep."""

    def test_sweep_reports_each_level(self):
        levels = [(1, 1, (1, 2)), (1, 2, (3, 4)), (1, 3, (5, 6))]

        def check(mission, level):
            if level == 2:
                raise psxrun.SmokeFailure("level stalled")
            if level == 3:
                raise RuntimeError("socket died")
            return "interp=0.0010"

        lines, failures = sweep_smoke.run_all(levels, check)
        self.assertEqual(failures, 2)
        self.assertEqual(lines[0], "M1L1: OK interp=0.0010")
        self.assertEqual(lines[1], "M1L2: FAIL level stalled")
        self.assertTrue(lines[2].startswith("M1L3: FAIL unexpected error: RuntimeError"))
        self.assertEqual(lines[3], "sweep: 1/3 levels OK")

    def test_select_levels_by_mission_and_bonus(self):
        self.assertEqual([(m, l) for m, l, _ in sweep_smoke.select_levels(mission=4, bonus=False)],
                         [(4, 1), (4, 2), (4, 3)])
        self.assertEqual(len(sweep_smoke.select_levels(mission=None, bonus=False)), 24)
        self.assertEqual(len(sweep_smoke.select_levels(mission=None, bonus=True)), 7)


if __name__ == "__main__":
    unittest.main()
