"""Unit tests for level_smoke helpers that do not need a running game."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import level_smoke  # noqa: E402


class FpsVerdictTests(unittest.TestCase):
    """One disturbed window (host busy for a few seconds) must not decide the verdict."""

    def test_single_slow_window_ignored(self):
        self.assertEqual(level_smoke.fps_verdict([37.3, 50.0, 49.8]), 49.8)

    def test_sustained_slowness_counts(self):
        self.assertEqual(level_smoke.fps_verdict([30.0, 31.0, 50.0]), 31.0)

    def test_needs_three_windows(self):
        with self.assertRaises(ValueError):
            level_smoke.fps_verdict([50.0, 50.0])


class FrozenTests(unittest.TestCase):
    """A hung guest still counts frames but keeps showing the same picture."""

    def test_identical_consecutive_shots_are_frozen(self):
        self.assertTrue(level_smoke.looks_frozen([12.0, 0.2, 9.0]))

    def test_changing_shots_are_live(self):
        self.assertFalse(level_smoke.looks_frozen([12.0, 3.5, 9.0]))


if __name__ == "__main__":
    unittest.main()
