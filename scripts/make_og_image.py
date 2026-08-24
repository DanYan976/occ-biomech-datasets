#!/usr/bin/env python3
"""
Regenerate site/og-image.png — the 1200x630 card shown when a link to the site
is shared (Open Graph / Twitter cards).

This is NOT part of the normal build: run it only when the brand, headline, or
subtitle changes, then commit the resulting PNG.

    pip install pillow
    python scripts/make_og_image.py

It draws in the site's own palette, uses site/assets/logo-source.png for the
mark (the header logo's own artwork, minus its baked-in white square, so it
blends into the card background), and pulls IBM Plex from Google
Fonts (needs network) so the type matches the pages.
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Missing dependency. Run: pip install pillow")

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
OUT = SITE / "og-image.png"
FONT_CACHE = Path(__file__).resolve().parent / ".fontcache"

# Same values as site/style.css.
PAPER = (245, 246, 248)
INK = (21, 32, 43)
MUTED = (88, 102, 111)
ACCENT = (15, 118, 110)

W, H = 1200, 630
PAD = 92

HEADLINE_INK = "Human-motion datasets, models & analysis tools for occupational tasks,"
HEADLINE_ACCENT = "indexed in one place."
SUBTITLE = ("Motion capture, video, and wearable sensors — plus a dedicated collection "
            "of occupational exoskeleton studies.")

CSS = ("https://fonts.googleapis.com/css2?"
       "family=IBM+Plex+Sans:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap")


def fonts() -> dict[str, Path]:
    """Download the TTFs Google Fonts serves to old browsers, cached on disk."""
    FONT_CACHE.mkdir(exist_ok=True)
    req = urllib.request.Request(CSS, headers={"User-Agent": "Mozilla/4.0"})
    css = urllib.request.urlopen(req, timeout=30).read().decode()

    found: dict[str, Path] = {}
    for block in css.split("@font-face"):
        family = re.search(r"font-family:\s*'([^']+)'", block)
        weight = re.search(r"font-weight:\s*(\d+)", block)
        url = re.search(r"src:\s*url\((https://[^)]+)\)", block)
        if not (family and weight and url):
            continue
        key = f"{family.group(1).replace(' ', '')}-{weight.group(1)}"
        path = FONT_CACHE / f"{key}.ttf"
        if not path.exists():
            path.write_bytes(urllib.request.urlopen(url.group(1), timeout=30).read())
        found[key] = path
    missing = {"IBMPlexSans-400", "IBMPlexSans-700", "IBMPlexMono-400"} - set(found)
    if missing:
        sys.exit(f"Google Fonts did not serve: {', '.join(sorted(missing))}")
    return found


def paste_mark(img: Image.Image, x: int, y: int, size: int) -> None:
    # logo.png bakes in a white square; the transparent source blends into PAPER.
    mark = Image.open(SITE / "assets" / "logo-source.png").convert("RGBA")
    mark = mark.crop(mark.getchannel("A").getbbox())
    scale = size / max(mark.size)
    mark = mark.resize((round(mark.width * scale), round(mark.height * scale)), Image.LANCZOS)
    img.paste(mark, (x + (size - mark.width) // 2, y + (size - mark.height) // 2), mark)


def wrap(draw: ImageDraw.ImageDraw, words: list, font, max_width: int) -> list[list]:
    """Greedy wrap over (word, colour) pairs."""
    lines, line = [], []
    for word in words:
        trial = line + [word]
        if line and draw.textlength(" ".join(w for w, _ in trial), font=font) > max_width:
            lines.append(line)
            line = [word]
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def main() -> None:
    face = fonts()
    head_font = ImageFont.truetype(str(face["IBMPlexSans-700"]), 52)
    brand_font = ImageFont.truetype(str(face["IBMPlexSans-700"]), 44)
    body_font = ImageFont.truetype(str(face["IBMPlexSans-400"]), 24)
    mono_font = ImageFont.truetype(str(face["IBMPlexMono-400"]), 19)

    img = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 9], fill=ACCENT)

    paste_mark(img, PAD, 84, 96)
    draw.text((PAD + 122, 92), "OccBiomechanics", font=brand_font, fill=INK)
    draw.text((PAD + 122, 148), "occbiomechanics.org", font=mono_font, fill=MUTED)

    headline = ([(w, INK) for w in HEADLINE_INK.split()]
                + [(w, ACCENT) for w in HEADLINE_ACCENT.split()])
    y = 292
    for line in wrap(draw, headline, head_font, W - 2 * PAD):
        x = PAD
        for word, colour in line:
            draw.text((x, y), word, font=head_font, fill=colour)
            x += draw.textlength(word + " ", font=head_font)
        y += 64

    y += 18
    for line in wrap(draw, [(w, MUTED) for w in SUBTITLE.split()], body_font, W - 2 * PAD):
        draw.text((PAD, y), " ".join(w for w, _ in line), font=body_font, fill=MUTED)
        y += 36

    img.save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)} ({img.width}x{img.height})")


if __name__ == "__main__":
    main()
