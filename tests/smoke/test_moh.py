"""Unit tests for the MOH-specific constants and helpers in moh.py."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import moh  # noqa: E402

BASE = 0x801A93D8  # entry array base seen in one run; it moves between runs
S = moh.MENU_ITEM_STRIDE


class MenuIndexTests(unittest.TestCase):
    def test_first_item(self):
        self.assertEqual(moh.menu_index_from_ptr(BASE, BASE), 0)

    def test_last_item(self):
        self.assertEqual(moh.menu_index_from_ptr(BASE + 5 * S, BASE), 5)

    def test_unaligned_pointer_is_none(self):
        self.assertIsNone(moh.menu_index_from_ptr(BASE + 0x10, BASE))

    def test_past_ring_is_none(self):
        self.assertIsNone(moh.menu_index_from_ptr(BASE + 6 * S, BASE))

    def test_below_base_is_none(self):
        self.assertIsNone(moh.menu_index_from_ptr(BASE - S, BASE))

    def test_ring_has_six_items(self):
        self.assertEqual(len(moh.MENU_RING), 6)


class RingStepTests(unittest.TestCase):
    def test_forward_step(self):
        self.assertTrue(moh.is_ring_step(BASE + S, BASE + 2 * S))

    def test_wrap_from_last_to_first(self):
        self.assertTrue(moh.is_ring_step(BASE + 5 * S, BASE))

    def test_no_movement_is_not_a_step(self):
        self.assertFalse(moh.is_ring_step(BASE + S, BASE + S))

    def test_backward_step_is_not_a_step(self):
        self.assertFalse(moh.is_ring_step(BASE + 2 * S, BASE + S))

    def test_wrap_of_seven_entry_ring(self):
        # After loading a save the ring has 7 entries (pointer wraps by 6 slots).
        self.assertTrue(moh.is_ring_step(BASE + 6 * S, BASE, ring_size=7))
        self.assertFalse(moh.is_ring_step(BASE + 6 * S, BASE))


class LevelTableTests(unittest.TestCase):
    def test_levels_table_has_24_entries_without_overlap(self):
        self.assertEqual(len(moh.LEVELS), 24)
        ranges = sorted(r for _m, _l, r in moh.LEVELS)
        for (lo, hi), (next_lo, _) in zip(ranges, ranges[1:]):
            self.assertLessEqual(lo, hi)
            self.assertLess(hi, next_lo)
        self.assertEqual(moh.LEVELS[0], (1, 1, moh.M1_LVL1_LBAS))
        self.assertEqual(moh.LEVELS[1], (1, 2, moh.M1_LVL2_LBAS))

    def test_bonus_levels_are_msn12(self):
        self.assertEqual([(m, l) for m, l, _ in moh.BONUS_LEVELS], [(12, n) for n in range(1, 8)])

    def test_level_lookup(self):
        self.assertEqual(moh.level_lbas(2, 1), (24692, 28821))
        with self.assertRaises(KeyError):
            moh.level_lbas(6, 1)


class ShotCountTests(unittest.TestCase):
    def test_counts_decrements_only(self):
        # 8 -> 7 -> 7 -> 6, reload to 8, -> 7: three shots
        self.assertEqual(moh.count_shots([8, 7, 7, 6, 8, 7]), 3)

    def test_no_shots(self):
        self.assertEqual(moh.count_shots([8, 8, 8]), 0)


if __name__ == "__main__":
    unittest.main()
