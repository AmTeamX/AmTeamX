#!/usr/bin/env python3
"""Render data/contributions.json as an animated 53-week × 7-day heatmap SVG.

Draws the classic GitHub contribution calendar of rounded, colored boxes with
a green ramp, reveals it once with a diagonal slide-down (CSS keyframes that
play on load then freeze — no looping glow), and adds a Less→More legend plus
a stats footer.

Usage:
    python scripts/render_heatmap_svg.py   # writes contrib-heatmap.svg
"""

import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT = REPO_ROOT / "data" / "contributions.json"
OUTPUT = REPO_ROOT / "contrib-heatmap.svg"

# GitHub-ish green ramp (none -> brightest; the top end is a neon highlight).
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

# Grid geometry.
CELL = 11
GAP = 3
PITCH = CELL + GAP
NROWS = 7

DAY_LABEL_W = 30
MONTH_LABEL_H = 18
MARGIN_LEFT = DAY_LABEL_W
MARGIN_TOP = MONTH_LABEL_H + 6

# Text colors.
TEXT = "#c9d1d9"
DIM = "#8b949e"

# Animation timing.
STEP = 0.04      # seconds per anti-diagonal (col + row)
CELL_DUR = 0.35

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_LABELS = {1: "Mon", 3: "Wed", 5: "Fri"}


def _load() -> dict:
    if not INPUT.exists():
        sys.exit(f"missing {INPUT.name} — run scripts/fetch_contributions.py first")
    return json.loads(INPUT.read_text())


def _color(level: int) -> str:
    return PALETTE[max(0, min(level, len(PALETTE) - 1))]


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> None:
    data = _load()
    days = data["days"]

    by_date = {d["date"]: d for d in days}
    first_date = _parse_date(days[0]["date"])

    # Sunday = 0 ... Saturday = 6.
    offset = (first_date.weekday() + 1) % 7

    # Build the grid of (date, level) keyed by [column][row].
    cells: list[list[tuple[str, int]]] = []
    column = 0
    row = offset
    for d in days:
        if row >= NROWS:
            row = 0
            column += 1
        while len(cells) <= column:
            cells.append([("", 0) for _ in range(NROWS)])
        cells[column][row] = (d["date"], d["level"])
        row += 1

    ncols = len(cells)
    grid_w = ncols * PITCH - GAP
    grid_h = NROWS * PITCH - GAP

    total_w = MARGIN_LEFT + grid_w + 20
    legend_y = MARGIN_TOP + grid_h + 20
    footer_y = legend_y + 24
    total_h = footer_y + 20 + 12

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {total_w} {total_h}" role="img" '
        f'aria-label="Contribution graph">\n',
        "<style>"
        ".c{animation:pop 0.35s ease-out both}"
        "@keyframes pop{from{opacity:0;transform:translateY(-6px)}"
        "to{opacity:1;transform:translateY(0)}}"
        "text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}"
        "</style>\n",
    ]

    # Day-of-week labels (Mon / Wed / Fri).
    for r, label in DAY_LABELS.items():
        y = MARGIN_TOP + r * PITCH + CELL // 2 + 4
        parts.append(
            f'<text x="0" y="{y}" font-size="11" fill="{DIM}">{label}</text>\n'
        )

    # Month labels (drawn where a new month begins, GitHub-style).
    prev_month = None
    for col in range(ncols):
        top = cells[col][0][0]
        if not top:
            continue
        month = _parse_date(top).month
        if month != prev_month:
            x = MARGIN_LEFT + col * PITCH
            parts.append(
                f'<text x="{x}" y="{MONTH_LABEL_H}" font-size="11" '
                f'fill="{DIM}">{MONTHS[month - 1]}</text>\n'
            )
            prev_month = month

    # Contribution cells, revealed with a diagonal stagger.
    for col in range(ncols):
        for r in range(NROWS):
            date_str, level = cells[col][r]
            if not date_str:
                continue
            x = MARGIN_LEFT + col * PITCH
            y = MARGIN_TOP + r * PITCH
            delay = (col + r) * STEP
            parts.append(
                f'<rect class="c" x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
                f'rx="3" fill="{_color(level)}" '
                f'style="animation-delay:{delay:.2f}s"/>'
                f'<title>{date_str}: {by_date[date_str]["count"]} contributions</title>\n'
            )

    # Legend: Less -> More.
    legend_x = MARGIN_LEFT
    parts.append(
        f'<text x="{legend_x}" y="{legend_y}" font-size="11" fill="{DIM}">'
        f"Less</text>\n"
    )
    box_x = legend_x + 32
    for level in range(5):
        parts.append(
            f'<rect x="{box_x}" y="{legend_y - 9}" width="{CELL}" height="{CELL}" '
            f'rx="3" fill="{_color(level)}"/>\n'
        )
        box_x += PITCH
    parts.append(
        f'<text x="{box_x + 4}" y="{legend_y}" font-size="11" fill="{DIM}">'
        f"More</text>\n"
    )

    # Stats footer.
    total = data.get("total", 0)
    current = data.get("current_streak", 0)
    longest = data.get("longest_streak", 0)
    parts.append(
        f'<text x="{MARGIN_LEFT}" y="{footer_y}" font-size="13" fill="{TEXT}">'
        f"{total:,} contributions in the last year</text>\n"
    )
    parts.append(
        f'<text x="{MARGIN_LEFT}" y="{footer_y + 16}" font-size="11" fill="{DIM}">'
        f"current streak {current} days · longest streak {longest} days</text>\n"
    )

    parts.append("</svg>\n")
    OUTPUT.write_text("".join(parts))
    print(f"wrote {OUTPUT.name} ({ncols} weeks × {NROWS} days)")


if __name__ == "__main__":
    main()
