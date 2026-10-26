"""Read the directory of a PS1 memory card image (stdlib only).

Frame 0 starts with "MC"; frames 1-15 (128 bytes each) are directory entries.
Each entry begins with a 32-bit allocation state (0x51 = first block of a
file, 0x52/0x53 = continuation, 0xA0-0xA3 = free/deleted) and carries the
file name as ASCII from byte 0x0A, zero-terminated, at most 20 characters.
"""

import struct

FRAME = 0x80
FIRST_BLOCK = 0x51
NAME_OFFSET = 0x0A
NAME_LEN = 20
MOH_SERIAL = "SLES-02470"


def saves(path):
    """File names of every save (first blocks) on the card."""
    with open(path, "rb") as fh:
        data = fh.read(16 * FRAME)
    if data[:2] != b"MC":
        raise ValueError(f"{path}: not a formatted memory card (no MC header)")
    names = []
    for block in range(1, 16):
        entry = data[block * FRAME:(block + 1) * FRAME]
        if struct.unpack_from("<I", entry, 0)[0] != FIRST_BLOCK:
            continue
        raw = entry[NAME_OFFSET:NAME_OFFSET + NAME_LEN].split(b"\0", 1)[0]
        names.append(raw.decode("ascii", "replace"))
    return names


def moh_saves(path):
    """Saves of this game (PAL Medal of Honor) on the card."""
    return [name for name in saves(path) if MOH_SERIAL in name]


def save_name(filename):
    """Player name of a MOH save: BESLES-02470<name><slot digit> -> <name>."""
    prefix = "BE" + MOH_SERIAL   # "BE" = European region code of PS1 save names
    if not filename.startswith(prefix):
        raise ValueError(f"not a PAL Medal of Honor save: {filename}")
    rest = filename[len(prefix):]
    return rest[:-1] if rest[-1:].isdigit() else rest
