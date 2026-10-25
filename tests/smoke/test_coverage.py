"""Unit tests for coverage_smoke.interp_share."""

import os
import sys
import time
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


class LoaderStateTests(unittest.TestCase):
    """The interp share only means something when the loader counts and no DLLs ran."""

    def test_inactive_loader_rejected(self):
        with self.assertRaisesRegex(coverage_smoke.SmokeFailure, "inactive"):
            coverage_smoke.validate_loader({"active": 0, "loads": 0, "dispatch_native": 0})

    def test_loaded_dlls_rejected(self):
        with self.assertRaisesRegex(coverage_smoke.SmokeFailure, "DLL"):
            coverage_smoke.validate_loader({"active": 1, "loads": 2, "dispatch_native": 0})

    def test_native_dll_dispatch_rejected(self):
        with self.assertRaisesRegex(coverage_smoke.SmokeFailure, "DLL"):
            coverage_smoke.validate_loader({"active": 1, "loads": 0, "dispatch_native": 5})

    def test_clean_loader_accepted(self):
        coverage_smoke.validate_loader({"active": 1, "loads": 0, "dispatch_native": 0})


class AdvanceToLevelTests(unittest.TestCase):
    """After NEW GAME the game shows FMVs and a 3-page briefing that waits for X."""

    def test_presses_cross_until_level_word_appears(self):
        from fakes import FakeServer

        words = iter(["07000000", "07000000", "05000000"])

        def reply(request):
            if request.get("cmd") == "read_ram":
                return {"id": 1, "ok": True, "hex": next(words)}
            return {"id": 1, "ok": True}

        srv = FakeServer(reply)
        try:
            coverage_smoke.advance_until_level(srv.port, time.monotonic() + 5, nudge_secs=0.01)
        finally:
            srv.close()
        presses = [r for r in srv.seen if r["cmd"] == "press"]
        self.assertEqual(len(presses), 2)
        self.assertEqual(presses[0]["buttons"], 0xFFFF & ~0x4000)

    def test_gives_up_with_last_word(self):
        from fakes import FakeServer

        srv = FakeServer(lambda request: {"id": 1, "ok": True, "hex": "07000000"})
        try:
            with self.assertRaisesRegex(coverage_smoke.SmokeFailure, "0x00000007"):
                coverage_smoke.advance_until_level(srv.port, time.monotonic() + 0.5, nudge_secs=0.01)
        finally:
            srv.close()


if __name__ == "__main__":
    unittest.main()
