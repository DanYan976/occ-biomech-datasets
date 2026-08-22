#!/usr/bin/env python3
"""
Swap the site's brand mark for a raster logo.

    python scripts/apply_logo.py site/assets/logo-source.png

What it does
  1. trims the source to its content, turns the outer white background
     transparent (flood-fill from the corners, so light fills inside the
     artwork survive), and pads it to a square;
  2. writes site/assets/logo.png (header mark), site/favicon.png and
     site/favicon.ico;
  3. points every page (site/*.html, site/datasets/*.html) and the page
     template in scripts/build_catalog.py at the new files, bumping the
     favicon cache-buster to today's date.

Re-run scripts/make_og_image.py afterwards if you want the share card to carry
the new mark too.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
LOGO_PNG = SITE / "assets" / "logo.png"
FAVICON_PNG = SITE / "favicon.png"
FAVICON_ICO = SITE / "favicon.ico"

WHITE_TOL = 18        # how far from pure white still counts as background
LOGO_SIZE = 256       # header mark is shown at 30px; 256 keeps it crisp on HiDPI
FAVICON_SIZES = (16, 32, 48, 64)


def knock_out_background(img: Image.Image) -> Image.Image:
    """Make the white surround transparent without touching whites inside the art."""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    seen = bytearray(w * h)
    stack = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]

    def is_bg(x: int, y: int) -> bool:
        r, g, b, a = px[x, y]
        return a == 0 or (r >= 255 - WHITE_TOL and g >= 255 - WHITE_TOL and b >= 255 - WHITE_TOL)

    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= w or y >= h or seen[y * w + x] or not is_bg(x, y):
            continue
        seen[y * w + x] = 1
        px[x, y] = (255, 255, 255, 0)
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return img


def square(img: Image.Image, size: int, pad_frac: float = 0.0) -> Image.Image:
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    side = int(max(img.size) * (1 + 2 * pad_frac))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return canvas.resize((size, size), Image.LANCZOS)


def rewrite_refs(stamp: str) -> int:
    pages = list(SITE.glob("*.html")) + list(SITE.glob("datasets/*.html")) + [ROOT / "scripts" / "build_catalog.py"]
    changed = 0
    for p in pages:
        s = p.read_text(encoding="utf-8")
        t = s.replace("assets/logo.svg", "assets/logo.png")
        t = re.sub(r'<link rel="icon" type="image/svg\+xml" href="(/?)favicon\.svg\?v=\d+" />',
                   rf'<link rel="icon" type="image/png" href="\1favicon.png?v={stamp}" />', t)
        t = re.sub(r'(href="/?favicon\.png\?v=)\d+', rf'\g<1>{stamp}', t)
        if t != s:
            p.write_text(t, encoding="utf-8")
            changed += 1
    return changed


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    if not src.exists():
        sys.exit(f"not found: {src}")

    art = knock_out_background(Image.open(src))
    square(art, LOGO_SIZE).save(LOGO_PNG, optimize=True)
    fav = square(art, 64)
    fav.save(FAVICON_PNG, optimize=True)
    fav.save(FAVICON_ICO, sizes=[(s, s) for s in FAVICON_SIZES])

    stamp = dt.date.today().strftime("%Y%m%d")
    n = rewrite_refs(stamp)
    for out in (LOGO_PNG, FAVICON_PNG, FAVICON_ICO):
        print(f"wrote {out.relative_to(ROOT)}")
    print(f"updated references in {n} files (favicon v={stamp})")


if __name__ == "__main__":
    main()
