"""Unit tests for the pure helpers of pgxp_smoke (stdlib only)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pgxp_smoke  # noqa: E402


def geom(precise, mixed, native):
    return {"pgxp": {"tri_precise": precise, "tri_mixed": mixed, "tri_native": native}}


class CorrectedShareTests(unittest.TestCase):
    def test_share_of_precise_and_mixed_triangles(self):
        self.assertAlmostEqual(pgxp_smoke.corrected_share(geom(2282, 84677, 114391)), 86959 / 201350)

    def test_window_difference(self):
        before, after = geom(100, 1000, 900), geom(150, 1400, 1450)
        self.assertAlmostEqual(pgxp_smoke.corrected_share(after, before), 450 / 1000)

    def test_no_triangles_is_not_a_share(self):
        with self.assertRaises(ValueError):
            pgxp_smoke.corrected_share(geom(0, 0, 0))


class ResolutionTests(unittest.TestCase):
    def test_4k_check(self):
        self.assertTrue(pgxp_smoke.is_4k({"effective_scale": 9, "gl_clamp_reason": 0}))
        self.assertFalse(pgxp_smoke.is_4k({"effective_scale": 6, "gl_clamp_reason": 2}))


if __name__ == "__main__":
    unittest.main()
