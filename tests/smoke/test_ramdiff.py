"""Unit tests for tools/ramdiff.py."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))

import ramdiff  # noqa: E402


class CandidatesTests(unittest.TestCase):
    def test_finds_counter_byte(self):
        snaps = [bytes([7, 7, 1, 0, 0, v, 0, 0]) for v in (0, 1, 2)]
        self.assertEqual(ramdiff.candidates(snaps, [0, 1, 2]), [5])

    def test_ignores_constant_bytes(self):
        snaps = [bytes([0, 0, 1, 0, 0, v, 0, 0]) for v in (0, 1, 2)]
        self.assertNotIn(2, ramdiff.candidates(snaps, [0, 1, 2]))

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            ramdiff.candidates([bytes(8), bytes(9)], [0, 0])

    def test_no_match_empty(self):
        self.assertEqual(ramdiff.candidates([bytes(8)] * 3, [9, 9, 9]), [])


if __name__ == "__main__":
    unittest.main()
