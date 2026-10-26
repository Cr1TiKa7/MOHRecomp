"""Unit tests for the shared runtime helpers in psxrun (stdlib only)."""

import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psxrun  # noqa: E402
from fakes import FakeServer  # noqa: E402


class MaskTests(unittest.TestCase):
    def test_mask_start(self):
        self.assertEqual(psxrun.mask("start"), 0xFFF7)

    def test_mask_combines(self):
        self.assertEqual(psxrun.mask("up", "cross"), 0xFFFF & ~0x4010)

    def test_mask_unknown_raises(self):
        with self.assertRaises(KeyError):
            psxrun.mask("jump")


class RemoteTests(unittest.TestCase):
    def test_press_sends_inverted_mask(self):
        srv = FakeServer({"id": 1, "ok": True})
        try:
            psxrun.press(srv.port, "right")
        finally:
            srv.close()
        self.assertEqual(srv.seen, [{"id": 1, "cmd": "press", "buttons": 0xFFDF, "frames": 4,
                                     "lx": 128, "ly": 128, "rx": 128, "ry": 128}])

    def test_hold_buttons_sends_centred_sticks(self):
        # An analog P1 (mouse package on) otherwise gets the d-pad copied onto the
        # left stick by the debug override: one RIGHT would count twice.
        srv = FakeServer({"id": 1, "ok": True})
        try:
            psxrun.hold_buttons(srv.port, "r2", "up")
        finally:
            srv.close()
        self.assertEqual(srv.seen, [{"id": 1, "cmd": "set_input", "buttons": 0xFDEF,
                                     "lx": 128, "ly": 128, "rx": 128, "ry": 128}])

    def test_host_layer_press_holds_then_releases_the_virtual_gamepad(self):
        srv = FakeServer({"id": 1, "ok": True})
        try:
            with mock.patch.object(psxrun, "INPUT_LAYER", "host"), \
                    mock.patch.object(psxrun, "_host_armed", {srv.port}), \
                    mock.patch.object(psxrun.time, "sleep") as sleep:
                psxrun.press(srv.port, "right", frames=4)
        finally:
            srv.close()
        centred = {"lx": 128, "ly": 128, "rx": 128, "ry": 128}
        self.assertEqual(srv.seen, [
            {"id": 1, "cmd": "set_input", "layer": "host", "buttons": 0xFFDF, **centred},
            {"id": 1, "cmd": "set_input", "layer": "host", "buttons": 0xFFFF, **centred}])
        sleep.assert_called_once_with(4 / 50 + psxrun.HOST_PRESS_MARGIN_SECS)

    def test_host_layer_plugs_the_gamepad_in_before_its_first_input(self):
        # The first input after arming the virtual gamepad was lost once (it
        # connects with that request), so it is armed neutral and given time.
        srv = FakeServer({"id": 1, "ok": True})
        try:
            with mock.patch.object(psxrun, "INPUT_LAYER", "host"), \
                    mock.patch.object(psxrun, "_host_armed", set()), \
                    mock.patch.object(psxrun.time, "sleep") as sleep:
                psxrun.hold_buttons(srv.port, "r2")
                psxrun.hold_buttons(srv.port, "r2")
        finally:
            srv.close()
        centred = {"lx": 128, "ly": 128, "rx": 128, "ry": 128}
        self.assertEqual(srv.seen, [
            {"id": 1, "cmd": "set_input", "layer": "host", "buttons": 0xFFFF, **centred},
            {"id": 1, "cmd": "set_input", "layer": "host", "buttons": 0xFDFF, **centred},
            {"id": 1, "cmd": "set_input", "layer": "host", "buttons": 0xFDFF, **centred}])
        sleep.assert_called_once_with(psxrun.HOST_ARM_SECS)

    def test_release_clears_port_1_or_lets_go_of_the_virtual_gamepad(self):
        srv = FakeServer({"id": 1, "ok": True})
        try:
            psxrun.release(srv.port)
            with mock.patch.object(psxrun, "INPUT_LAYER", "host"), \
                    mock.patch.object(psxrun, "_host_armed", {srv.port}):
                psxrun.release(srv.port)   # stays plugged in: clear_input would unplug it
        finally:
            srv.close()
        self.assertEqual(srv.seen, [
            {"id": 1, "cmd": "clear_input", "port": 1},
            {"id": 1, "cmd": "set_input", "layer": "host", "buttons": 0xFFFF,
             "lx": 128, "ly": 128, "rx": 128, "ry": 128}])

    def test_launch_forgets_the_armed_gamepad_of_its_port(self):
        import tempfile

        with tempfile.TemporaryDirectory() as out, \
                mock.patch.object(psxrun, "_host_armed", {4370, 4371}), \
                mock.patch.object(psxrun.subprocess, "Popen"):
            psxrun.launch(sys.executable, "x.cue", "game.toml", 4370, out)
            self.assertEqual(psxrun._host_armed, {4371})

    def test_input_layer_comes_from_the_environment(self):
        self.assertEqual(psxrun.input_layer({"MOH_SMOKE_PAD_LAYER": "host"}), "host")
        self.assertIsNone(psxrun.input_layer({}))
        with self.assertRaises(ValueError):
            psxrun.input_layer({"MOH_SMOKE_PAD_LAYER": "gamepad"})

    def test_wait_frame_returns_first_reaching(self):
        frames = iter([10, 20, 30, 40])
        srv = FakeServer(lambda request: {"id": 1, "ok": True, "frame": next(frames)})
        try:
            self.assertEqual(psxrun.wait_frame(srv.port, 25, time.monotonic() + 5), 30)
        finally:
            srv.close()

    def test_wait_frame_times_out(self):
        srv = FakeServer({"id": 1, "ok": True, "frame": 1})
        try:
            with self.assertRaises(TimeoutError):
                psxrun.wait_frame(srv.port, 5, time.monotonic() + 1)
        finally:
            srv.close()

    def test_wait_u32_returns_when_value_matches(self):
        words = iter(["07000000", "07000000", "05000000"])
        srv = FakeServer(lambda request: {"id": 1, "ok": True, "hex": next(words)})
        try:
            psxrun.wait_u32(srv.port, 0x80039F28, 5, time.monotonic() + 5)
        finally:
            srv.close()
        self.assertEqual(len(srv.seen), 3)

    def test_wait_u32_times_out_with_last_value(self):
        srv = FakeServer({"id": 1, "ok": True, "hex": "07000000"})
        try:
            with self.assertRaisesRegex(TimeoutError, "0x00000007"):
                psxrun.wait_u32(srv.port, 0x80039F28, 5, time.monotonic() + 1)
        finally:
            srv.close()

    def test_read_bytes_decodes_hex(self):
        srv = FakeServer({"id": 1, "ok": True, "hex": "0a0b"})
        try:
            self.assertEqual(psxrun.read_bytes(srv.port, 0x80000000, 2), b"\x0a\x0b")
        finally:
            srv.close()
        self.assertEqual(srv.seen[0]["addr"], "0x80000000")
        self.assertEqual(srv.seen[0]["len"], 2)


class LaunchTests(unittest.TestCase):
    def test_launch_uses_dummy_audio_driver(self):
        # PSX_HOST_MUTE is not read by the runtime; without this the smoke
        # tests play game audio on the default output device.
        import tempfile
        from unittest import mock

        with tempfile.TemporaryDirectory() as out, \
                mock.patch.object(psxrun.subprocess, "Popen") as popen:
            psxrun.launch(sys.executable, "x.cue", "game.toml", 4370, out)
        self.assertEqual(popen.call_args.kwargs["env"]["SDL_AUDIODRIVER"], "dummy")


if __name__ == "__main__":
    unittest.main()
