#!/usr/bin/env python3
"""Session Doctor app icon: near-black rounded square + emerald pulse line."""
import sys

from PIL import Image, ImageDraw

SIZE = 1024
BG = (8, 9, 10, 255)
LINE = (16, 185, 129, 255)
GLOW = (16, 185, 129, 60)


def main(path: str) -> None:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=228, fill=BG)
    # soft glow under the line
    pts = [(150, 560), (330, 560), (430, 340), (580, 740), (680, 560), (874, 560)]
    for w, color in ((46, GLOW), (30, LINE)):
        d.line(pts, fill=color, width=w, joint="curve")
    # round caps
    for x, y in (pts[0], pts[-1]):
        d.ellipse([x - 15, y - 15, x + 15, y + 15], fill=LINE)
    img.save(path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/sd-icon.png")
