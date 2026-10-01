#!/usr/bin/env python3
"""Render the original MIT-licensed roof-window symbol with Python standard library."""

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def image(size):
    """Use crisp geometric shapes with transparency, independent of system fonts."""
    data = bytearray()
    for y in range(size):
        data.append(0)
        for x in range(size):
            px, py = x / size, y / size
            roof = abs(py - (0.22 + abs(px - 0.5) * 0.75)) < 0.025 and 0.12 < px < 0.88
            window = 0.32 < px < 0.68 and 0.36 < py < 0.77
            frame = window and (
                px < 0.355
                or px > 0.645
                or py < 0.395
                or py > 0.735
                or abs(px - 0.5) < 0.016
                or abs(py - 0.565) < 0.016
            )
            rgba = (
                (36, 86, 119, 255)
                if roof or frame
                else (107, 187, 205, 255)
                if window
                else (0, 0, 0, 0)
            )
            data.extend(rgba)

    def chunk(kind, body):
        return (
            struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">2I5B", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(data), 9))
        + chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    for size, filename in [(256, "icon.png"), (512, "icon@2x.png")]:
        (ROOT / "custom_components/velux_active/brand" / filename).write_bytes(image(size))
