"""Count distinct pixel values in a PNG (stdlib only).

Supports 8-bit RGB (color type 2) and RGBA (color type 6), non-interlaced,
all five PNG filter types. Anything else raises ValueError.
"""

import struct
import zlib

_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _read_chunks(data):
    pos = len(_SIGNATURE)
    while pos + 8 <= len(data):
        length, tag = struct.unpack(">I4s", data[pos:pos + 8])
        yield tag, data[pos + 8:pos + 8 + length]
        pos += 12 + length


def distinct_colors(path, limit=256):
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(_SIGNATURE):
        raise ValueError(f"{path}: not a PNG")

    width = height = None
    idat = bytearray()
    for tag, body in _read_chunks(data):
        if tag == b"IHDR":
            width, height, depth, ctype, _comp, _filt, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or ctype not in (2, 6) or interlace != 0:
                raise ValueError(
                    f"{path}: unsupported PNG (depth={depth}, color type={ctype}, interlace={interlace})"
                )
            bpp = 3 if ctype == 2 else 4
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
    if width is None:
        raise ValueError(f"{path}: missing IHDR")

    raw = zlib.decompress(bytes(idat))
    stride = width * bpp
    prev = bytearray(stride)
    seen = set()
    pos = 0
    for _ in range(height):
        ftype = raw[pos]
        row = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for i in range(stride):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            if ftype == 1:
                row[i] = (row[i] + a) & 0xFF
            elif ftype == 2:
                row[i] = (row[i] + b) & 0xFF
            elif ftype == 3:
                row[i] = (row[i] + ((a + b) >> 1)) & 0xFF
            elif ftype == 4:
                c = prev[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + _paeth(a, b, c)) & 0xFF
            elif ftype != 0:
                raise ValueError(f"{path}: bad filter type {ftype}")
        for i in range(0, stride, bpp):
            seen.add(bytes(row[i:i + bpp]))
            if len(seen) >= limit:
                return limit
        prev = row
    return len(seen)
