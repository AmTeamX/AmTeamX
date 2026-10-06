#!/usr/bin/env python3
"""Convert a prepped grayscale photo into a self-typing monochrome ASCII SVG.

Reads source-prepped.png (from prep_photo.py), downsamples it to a character
grid, and maps each pixel's brightness to a glyph on a density ramp. Each row
is wrapped in a horizontal clip that wipes left-to-right (a small block cursor
rides the wipe edge), staggered top-to-bottom. The portrait prints once and
freezes — no looping.

Usage:
    python scripts/make_ascii_svg.py   # writes avi-ascii.svg
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT = REPO_ROOT / "source-prepped.png"
OUTPUT = REPO_ROOT / "avi-ascii.svg"

# Bright (sparse) -> dark (dense). The leading space clears the background.
RAMP = " .`:-=+*cs#%@"

# Grid + glyph geometry.
COLS = 100
CELL_W = 10
CELL_H = 16
FONT_SIZE = CELL_H
BASELINE_FRAC = 0.78

# Animation timing (seconds).
STAGGER = 0.10
WIPE_DUR = 0.40

# Monochrome: a single light-gray fill (dark-mode optimized).
FILL = "#c9d1d9"
CURSOR_FILL = "#e6edf3"


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def load_prepped() -> Image.Image:
    if not INPUT.exists():
        sys.exit(f"missing {INPUT.name} — run scripts/prep_photo.py first")
    return Image.open(INPUT).convert("L")


def compute_rows(img: Image.Image) -> int:
    width, height = img.size
    # Preserve the photo's aspect ratio in the character grid (glyphs are
    # wider than they are tall: CELL_W / CELL_H).
    rows = int(round(height / width * COLS * (CELL_W / CELL_H)))
    return max(1, rows)


def main() -> None:
    img = load_prepped()
    rows = compute_rows(img)
    small = img.resize((COLS, rows), Image.LANCZOS)
    arr = np.asarray(small)

    n_ramp = len(RAMP)
    glyph_grid = []
    for y in range(rows):
        row = []
        for x in range(COLS):
            brightness = int(arr[y, x])
            idx = int(round((255 - brightness) / 255 * (n_ramp - 1)))
            row.append(RAMP[idx])
        glyph_grid.append("".join(row))

    total_w = COLS * CELL_W
    total_h = rows * CELL_H
    baseline = int(CELL_H * BASELINE_FRAC)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {total_w} {total_h}" role="img" '
        f'aria-label="ASCII portrait">\n',
        "<style>text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"
        f"monospace;font-size:{FONT_SIZE}px;fill:{FILL}" "}</style>\n",
        "<defs>\n",
    ]

    # One horizontal wipe clip per row.
    for i in range(rows):
        begin = i * STAGGER
        parts.append(
            f'<clipPath id="c{i}">'
            f'<rect x="0" y="{i * CELL_H}" width="0" height="{CELL_H}">'
            f'<animate attributeName="width" from="0" to="{total_w}" '
            f'begin="{begin:.2f}s" dur="{WIPE_DUR:.2f}s" fill="freeze"/>'
            f"</rect></clipPath>\n"
        )
    parts.append("</defs>\n")

    # Background is transparent; space glyphs are omitted entirely.
    for i in range(rows):
        y0 = i * CELL_H
        py = y0 + baseline
        row_texts = [
            f'<text x="{x * CELL_W}" y="{py}">{_xml_escape(ch)}</text>'
            for x, ch in enumerate(glyph_grid[i])
            if ch != " "
        ]
        if not row_texts:
            continue
        parts.append(f'<g clip-path="url(#c{i})">')
        parts.extend(row_texts)
        parts.append("</g>\n")

    # A small block cursor that rides each row's wipe edge.
    for i in range(rows):
        begin = i * STAGGER
        parts.append(
            f'<rect x="0" y="{i * CELL_H}" width="2" height="{CELL_H}" '
            f'fill="{CURSOR_FILL}" opacity="0">'
            f'<animate attributeName="opacity" values="0;0.9;0" '
            f'keyTimes="0;0.05;1" begin="{begin:.2f}s" dur="{WIPE_DUR:.2f}s" '
            f'fill="freeze"/>'
            f'<animate attributeName="x" from="0" to="{total_w}" '
            f'begin="{begin:.2f}s" dur="{WIPE_DUR:.2f}s" fill="freeze"/>'
            f"</rect>\n"
        )

    parts.append("</svg>\n")
    OUTPUT.write_text("".join(parts))
    print(f"wrote {OUTPUT.name} ({COLS}x{rows} grid)")


if __name__ == "__main__":
    main()
