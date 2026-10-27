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

    def test_dark_means_every_channel_below_8(self):
        path = self.png("dim.png", 20, 4, lambda x: DIM if x < 3 else (8, 0, 0) if x >= 17 else WHITE)
        self.assertEqual(widescreen_smoke.band_dark_fraction(path, 6), (1.0, 0.0))


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
