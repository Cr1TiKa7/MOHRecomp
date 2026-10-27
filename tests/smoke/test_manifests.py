"""Unit tests over the project's mod manifests (stdlib only)."""

import glob
import os
import tomllib
import unittest

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


class BooleanDefaultTests(unittest.TestCase):
    def test_boolean_defaults_are_strings(self):
        # The framework reads a boolean default as a string (mod_packages.cpp,
        # find_or<std::string>): a bare `default = true` silently becomes "false".
        paths = glob.glob(os.path.join(REPO_ROOT, "mods", "**", "manifest.toml"), recursive=True)
        self.assertTrue(paths)
        for path in paths:
            with open(path, "rb") as f:
                manifest = tomllib.load(f)
            for option in manifest.get("option", []):
                if option.get("type") == "boolean":
                    with self.subTest(manifest=os.path.relpath(path, REPO_ROOT), option=option["id"]):
                        self.assertIn(option.get("default", "false"), ("true", "false"))


if __name__ == "__main__":
    unittest.main()
