"""Switch the mouse-keyboard mod package on for one smoke run (stdlib only).

The runtime reads the launcher's mod selection from <build_dir>/mods/state.toml
even with --no-launcher. enabled() writes a selection with the mouse-look
feature on and puts the previous file back afterwards, byte for byte (or
removes it when there was none), so a test never changes the player's choice.
"""

import contextlib
import os

PACKAGE_ID = "moh.input.mouse-keyboard"
FEATURE_ID = "mouse-look"


def _toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def state_text(values, features=None):
    """features: [(package_id, feature_id, values), ...]; None = the mouse feature with
    values; [] = no feature, so every package keeps its default."""
    lines = ["format_version = 2"]
    if features is None:
        features = [(PACKAGE_ID, FEATURE_ID, values)]
    for package_id, feature_id, vals in features:
        lines += ["", "[[feature]]", f'package_id = "{package_id}"', f'id = "{feature_id}"', "enabled = true"]
        if vals:
            lines += ["", "[feature.values]"] + [f"{k} = {_toml_value(v)}" for k, v in vals.items()]
    return "\n".join(lines) + "\n"


@contextlib.contextmanager
def enabled(build_dir, values, features=None):
    path = os.path.join(build_dir, "mods", "state.toml")
    original = None
    if os.path.isfile(path):
        with open(path, "rb") as f:
            original = f.read()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(state_text(values, features))
        yield path
    finally:
        if original is None:
            if os.path.exists(path):
                os.remove(path)
        else:
            with open(path, "wb") as f:
                f.write(original)
