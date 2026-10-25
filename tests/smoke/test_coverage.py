"""Unit tests for coverage_smoke.interp_share."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import coverage_smoke  # noqa: E402


class InterpShareTests(unittest.TestCase):
    def test_static_hits_count_as_native(self):
        # dispatch_native only counts the DLL loader path; the static
        # dispatcher reports its own hits.
        status = {"dispatch_native": 0, "dispatch_interp_fallback": 10}
        self.assertEqual(coverage_smoke.interp_share(status, 990), (0.01, 990, 10))

    def test_dll_and_static_add_up(self):
        status = {"dispatch_native": 500, "dispatch_interp_fallback": 0}
        self.assertEqual(coverage_smoke.interp_share(status, 500), (0.0, 1000, 0))

    def test_no_dispatches_is_full_interp(self):
        status = {"dispatch_native": 0, "dispatch_interp_fallback": 0}
        self.assertEqual(coverage_smoke.interp_share(status, 0)[0], 1.0)


if __name__ == "__main__":
    unittest.main()
