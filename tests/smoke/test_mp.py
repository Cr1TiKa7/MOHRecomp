"""Unit tests for the split-screen smoke test (mp_smoke.py)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mp_smoke  # noqa: E402


class SplitTests(unittest.TestCase):
    """Turning one player must change that player's half, not the other one."""

    def test_own_half_moves(self):
        # Measured 2026-10-26: P1 (12.5, 0.0), P2 (0.0, 13.1), idle (0.0, 0.0).
        self.assertTrue(mp_smoke.split_ok(own=12.5, other=0.0))

    def test_too_little_change_fails(self):
        self.assertFalse(mp_smoke.split_ok(own=2.0, other=0.0))

    def test_wrong_half_fails(self):
        self.assertFalse(mp_smoke.split_ok(own=0.0, other=13.1))

    def test_both_halves_moving_fails(self):
        # One pad driving both views would mean the ports are not separate.
        self.assertFalse(mp_smoke.split_ok(own=12.0, other=11.0))

    def test_own_and_other_by_player(self):
        self.assertEqual(mp_smoke.own_and_other(1, (12.5, 0.3)), (12.5, 0.3))
        self.assertEqual(mp_smoke.own_and_other(2, (0.3, 13.1)), (13.1, 0.3))


if __name__ == "__main__":
    unittest.main()
