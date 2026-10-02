#!/usr/bin/env python3
"""Draw the extension icons (a white ring and dot on an orange rounded square) as PNG files.

Standard library only, so the icons can be regenerated anywhere without an image editor.
Run from the repository root: ``python3 scripts/make_icons.py``.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ORANGE = (232, 113, 10)
WHITE = (255, 255, 255)
SIZES = (16, 32, 48, 128)
SUPERSAMPLE = 4  # draw larger, then average down, for smooth edges


def _inside_rounded_square(x: float, y: float, size: float, radius: float) -> bool:
    nearest_x = min(max(x, radius), size - radius)
    nearest_y = min(max(y, radius), size - radius)
    return (x - nearest_x) ** 2 + (y - nearest_y) ** 2 <= radius ** 2


def _inside_mark(x: float, y: float, size: float) -> bool:
    """A ring with a dot at its centre."""
    distance = ((x - size / 2) ** 2 + (y - size / 2) ** 2) ** 0.5
    return distance <= size * 0.09 or size * 0.22 <= distance <= size * 0.32


def render(size: int) -> bytes:
    big = size * SUPERSAMPLE
    rows = []
    for row in range(size):
        line = bytearray([0])  # PNG filter type: none
        for column in range(size):
            red = green = blue = alpha = 0
            for sub_y in range(SUPERSAMPLE):
                for sub_x in range(SUPERSAMPLE):
                    x = column * SUPERSAMPLE + sub_x + 0.5
                    y = row * SUPERSAMPLE + sub_y + 0.5
                    if not _inside_rounded_square(x, y, big, big * 0.22):
                        continue
                    colour = WHITE if _inside_mark(x, y, big) else ORANGE
                    red += colour[0]
                    green += colour[1]
                    blue += colour[2]
                    alpha += 255
            samples = SUPERSAMPLE * SUPERSAMPLE
            covered = alpha // 255 or 1
            line += bytes((red // covered, green // covered, blue // covered, alpha // samples))
        rows.append(bytes(line))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")


def main() -> None:
    target = Path(__file__).resolve().parent.parent / "extension" / "icons"
    target.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        (target / f"icon-{size}.png").write_bytes(render(size))
        print(f"wrote icons/icon-{size}.png")


if __name__ == "__main__":
    main()
