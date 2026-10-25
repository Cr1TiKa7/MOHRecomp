"""Unit tests for menu_smoke helpers that do not need a running game."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import menu_smoke  # noqa: E402


class MemcardProbeTests(unittest.TestCase):
    """The runtime formats card1.mcd itself; only game-side SIO traffic proves recognition."""

    def test_probe_counts(self):
        menu_smoke.check_memcard_probed({"ok": True, "mc_probes": 3, "mc_reads": 0})

    def test_read_counts(self):
        menu_smoke.check_memcard_probed({"ok": True, "mc_probes": 0, "mc_reads": 1})

    def test_no_traffic_raises(self):
        with self.assertRaisesRegex(menu_smoke.SmokeFailure, "memory card"):
            menu_smoke.check_memcard_probed({"ok": True, "mc_probes": 0, "mc_reads": 0})


if __name__ == "__main__":
    unittest.main()
