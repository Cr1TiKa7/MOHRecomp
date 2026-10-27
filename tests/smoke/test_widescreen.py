"""Unit tests for the pure helpers of widescreen_smoke (stdlib only)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import widescreen_smoke  # noqa: E402
from test_helpers import _write_png  # noqa: E402

BLACK, WHITE, DIM = (0, 0, 0), (255, 255, 255), (7, 7, 7)


class BandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def png(self, name, w, h, colour_at):
        path = os.path.join(self.tmp.name, name)
        _write_png(path, w, h, [colour_at(x) for _y in range(h) for x in range(w)])
        return path

    def test_black_bands(self):
        path = self.png("bands.png", 20, 4, lambda x: BLACK if x < 3 or x >= 17 else WHITE)
        self.assertEqual(widescreen_smoke.band_dark_fraction(path, 6), (1.0, 1.0))

    def test_lit_bands(self):
        path = self.png("lit.png", 20, 4, lambda x: WHITE)
        self.assertEqual(widescreen_smoke.band_dark_fraction(path, 6), (0.0, 0.0))

    def test_dark_fraction_over_a_row_range(self):
        # Top two rows black in the left band, bottom two lit: the upper half is all dark.
        path = os.path.join(self.tmp.name, "half.png")
        _write_png(path, 20, 4, [BLACK if (x < 3 and y < 2) or 3 <= x < 17 else WHITE
                                 for y in range(4) for x in range(20)])
        self.assertEqual(widescreen_smoke.band_dark_fraction(path, 6, rows=(0, 2)), (1.0, 0.0))
        self.assertEqual(widescreen_smoke.band_dark_fraction(path, 6), (0.5, 0.0))

    def test_band_diff_compares_only_the_outer_bands(self):
        a = self.png("a.png", 20, 4, lambda x: BLACK)
        b = self.png("b.png", 20, 4, lambda x: WHITE if 3 <= x < 17 else BLACK)   # centre differs
        c = self.png("c.png", 20, 4, lambda x: WHITE if x < 3 else BLACK)          # left band differs
        self.assertEqual(widescreen_smoke.band_diff(a, b, 6), 0.0)
        self.assertEqual(widescreen_smoke.band_diff(a, c, 6), 127.5)

    def test_dark_means_every_channel_below_8(self):
        path = self.png("dim.png", 20, 4, lambda x: DIM if x < 3 else (8, 0, 0) if x >= 17 else WHITE)
        self.assertEqual(widescreen_smoke.band_dark_fraction(path, 6), (1.0, 0.0))


class FindPatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def png(self, name, w, mark_x):
        """Grey picture with a 6x4 mark (white/black checks) at mark_x."""
        def colour(x, y):
            if mark_x <= x < mark_x + 6 and 1 <= y < 5:
                return WHITE if (x + y) % 2 else BLACK
            return (90, 90, 90)
        path = os.path.join(self.tmp.name, name)
        _write_png(path, w, 6, [colour(x, y) for y in range(6) for x in range(w)])
        return path

    def test_finds_the_shift_of_a_mark(self):
        narrow, wide = self.png("n.png", 40, 10), self.png("w.png", 60, 30)
        self.assertEqual(widescreen_smoke.find_patch_x(wide, narrow, (10, 1, 16, 5), (0, 20)), (20, 0.0))

    def test_unmoved_mark(self):
        narrow, wide = self.png("n.png", 40, 10), self.png("w.png", 60, 10)
        self.assertEqual(widescreen_smoke.find_patch_x(wide, narrow, (10, 1, 16, 5), (0, 20)), (0, 0.0))

    def test_negative_shift(self):
        narrow, wide = self.png("n.png", 40, 10), self.png("w.png", 60, 4)
        self.assertEqual(widescreen_smoke.find_patch_x(wide, narrow, (10, 1, 16, 5), (-20, 20)), (-6, 0.0))

    def test_missing_mark_costs_a_lot(self):
        narrow, wide = self.png("n.png", 40, 10), self.png("w.png", 60, 100)
        _dx, cost = widescreen_smoke.find_patch_x(wide, narrow, (10, 1, 16, 5), (0, 20))
        self.assertGreater(cost, 50)


class TagStatsTests(unittest.TestCase):
    def test_drawn_share(self):
        self.assertAlmostEqual(widescreen_smoke.drawn_share({"tag_calls": 200, "hit": 190}), 0.95)

    def test_no_tags(self):
        self.assertEqual(widescreen_smoke.drawn_share({"tag_calls": 0, "hit": 0}), 0.0)


class PresentRingTests(unittest.TestCase):
    EVENT = [2576, 8281, "wide", 682, 512, 256, 1, 0, 0, 2147483647, 170, 0, 0, 0]

    def test_present_entry(self):
        self.assertEqual(widescreen_smoke.present_entry(self.EVENT),
                         {"path": "wide", "present_w": 682, "nw_extra": 170})

    def test_latest_present_takes_the_last_event(self):
        reply = {"events": [[1, 2, "native43", 512, 512, 256, 0, 1, 0, 0, 0, 0, 0, 0], self.EVENT]}
        self.assertEqual(widescreen_smoke.latest_present(reply)["path"], "wide")


if __name__ == "__main__":
    unittest.main()
