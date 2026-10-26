"""Unit tests for the pure helpers of mouse_smoke (stdlib only)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mouse_smoke  # noqa: E402


class ExpectationTests(unittest.TestCase):
    def test_expected_yaw(self):
        self.assertEqual(mouse_smoke.expected_yaw(100, 40), 4096000)

    def test_vertical_rate_is_twice_the_angle_and_clamped(self):
        self.assertEqual(mouse_smoke.expected_y_rate(-20, 40), -1638400)
        self.assertEqual(mouse_smoke.expected_y_rate(-100000, 40), -15728640)
        self.assertEqual(mouse_smoke.expected_y_rate(100000, 40), 15728640)

    def test_horizontal_rate_is_the_angle_and_clamped(self):
        self.assertEqual(mouse_smoke.expected_x_rate(20, 40), 819200)
        self.assertEqual(mouse_smoke.expected_x_rate(100000, 40), 15728640)
        self.assertEqual(mouse_smoke.expected_x_rate(-100000, 40), -15728640)

    def test_crosshair_moves_by_an_eighth_of_the_rate(self):
        self.assertEqual(mouse_smoke.crosshair_after(0, -1638400), -204800)
        self.assertEqual(mouse_smoke.crosshair_after(-983040, 1638400), -778240)

    def test_crosshair_shift_rounds_like_sra(self):
        self.assertEqual(mouse_smoke.crosshair_after(0, -9), -2)

    def test_s32(self):
        self.assertEqual(mouse_smoke.s32(0xFFFF0000), -65536)
        self.assertEqual(mouse_smoke.s32(0x7FFFFFFF), 0x7FFFFFFF)


if __name__ == "__main__":
    unittest.main()
