"""Unit tests for modstate (stdlib only)."""

import os
import sys
import tempfile
import tomllib
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import modstate  # noqa: E402


class EnabledTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.build = self.tmp.name
        os.makedirs(os.path.join(self.build, "mods"))
        self.state = os.path.join(self.build, "mods", "state.toml")

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_the_feature_with_its_values(self):
        with modstate.enabled(self.build, {"sensitivity": 40, "invert_y": False}):
            with open(self.state, "rb") as f:
                state = tomllib.load(f)
        self.assertEqual(state["format_version"], 2)
        feature = state["feature"][0]
        self.assertEqual(feature["package_id"], "moh.input.mouse-keyboard")
        self.assertEqual(feature["id"], "mouse-look")
        self.assertIs(feature["enabled"], True)
        self.assertEqual(feature["values"], {"sensitivity": 40, "invert_y": False})

    def test_several_features_each_with_their_values(self):
        features = [("moh.enhancement.widescreen", "widescreen", {}),
                    ("psx.enhancement.internal-resolution", "internal-resolution", {"resolution": "4k"})]
        with modstate.enabled(self.build, None, features=features):
            with open(self.state, "rb") as f:
                state = tomllib.load(f)
        got = [(f["package_id"], f["id"], f["enabled"], f.get("values", {})) for f in state["feature"]]
        self.assertEqual(got, [("moh.enhancement.widescreen", "widescreen", True, {}),
                               ("psx.enhancement.internal-resolution", "internal-resolution", True,
                                {"resolution": "4k"})])

    def test_restores_an_existing_file_byte_for_byte(self):
        original = b"format_version = 2\r\n# player's own choice\n"
        with open(self.state, "wb") as f:
            f.write(original)
        with modstate.enabled(self.build, {}):
            pass
        with open(self.state, "rb") as f:
            self.assertEqual(f.read(), original)

    def test_removes_the_file_when_there_was_none(self):
        with modstate.enabled(self.build, {}):
            self.assertTrue(os.path.isfile(self.state))
        self.assertFalse(os.path.exists(self.state))

    def test_restores_after_an_exception(self):
        with open(self.state, "wb") as f:
            f.write(b"format_version = 2\n")
        with self.assertRaises(RuntimeError):
            with modstate.enabled(self.build, {"sensitivity": 1}):
                raise RuntimeError("boom")
        with open(self.state, "rb") as f:
            self.assertEqual(f.read(), b"format_version = 2\n")


if __name__ == "__main__":
    unittest.main()
