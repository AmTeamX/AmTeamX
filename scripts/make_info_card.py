#!/usr/bin/env python3
"""Hand-author a neofetch-style info card as an animated SVG.

A small panel that looks like the output of the `neofetch` command: a title
bar, then colored key/value rows (Now, Prev, Stack, Highlights). Each line
fades and slides in on a short stagger so the panel looks like it is printing.

Set STATIC=1 to emit a frozen frame (handy for local Quick Look previews):

    python scripts/make_info_card.py            # writes info-card.svg
    STATIC=1 python scripts/make_info_card.py   # frozen frame

The heatmap already covers your GitHub stats, so this card carries the story
the numbers can't tell.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "info-card.svg"

# --- Content -------------------------------------------------------------
HOST = "team@github"

# Each row is (label, value). Empty labels continue the previous entry.
ROWS = [
    ("Now", "Software Engineer AI Intern @ Omise"),
    ("Prev", "Full-Stack Developer"),
    ("Stack", "Python · Golang · Flutter"),
    ("", "Next.js · TypeScript · SQL"),
    ("Highlights", "NSC 2025 Honorable Mention"),
    ("", "AI Hackathon 2024 1st Prize"),
    ("", "BONDUP in production"),
    ("", "Research @ Biomedical Informatics"),
]

LABEL_COLORS = {
    "Now": "#79c0ff",       # cyan
    "Prev": "#d2a8ff",      # magenta
    "Stack": "#7ee787",     # green
    "Highlights": "#ffa657",  # orange
}

# --- Layout --------------------------------------------------------------
WIDTH = 500
TITLE_H = 44
PAD_X = 26
LABEL_W = 118
GAP = 16
ROW_H = 24
FONT = 15
CONTENT_TOP = TITLE_H + 20
BOTTOM_PAD = 18

LABEL_END = PAD_X + LABEL_W
VALUE_X = LABEL_END + GAP
BASELINE = int(FONT * 0.74)

# --- Palette -------------------------------------------------------------
BG = "#0d1117"
TITLE_BG = "#161b22"
BORDER = "#30363d"
TEXT = "#c9d1d9"
HOST_TEXT = "#e6edf3"
DOTS = ["#ff5f56", "#ffbd2e", "#27c93f"]

# --- Animation -----------------------------------------------------------
ROW_STAGGER = 0.09
ROW_DUR = 0.4
TITLE_DELAY = 0.0


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main() -> None:
    static = os.environ.get("STATIC") == "1"

    height = CONTENT_TOP + len(ROWS) * ROW_H + BOTTOM_PAD

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" '
        f'aria-label="Profile info card">\n',
    ]

    if not static:
        parts.append(
            "<style>"
            ".line{animation:fade-slide 0.4s ease both}"
            "@keyframes fade-slide{from{opacity:0;transform:translateY(8px)}"
            "to{opacity:1;transform:translateY(0)}}"
            "</style>\n"
        )
    else:
        parts.append(
            "<style>text{font-family:ui-monospace,SFMono-Regular,Menlo,"
            "Consolas,monospace}</style>\n"
        )

    parts.append(
        '<defs><clipPath id="card">'
        f'<rect width="{WIDTH}" height="{height}" rx="12"/>'
        "</clipPath></defs>\n"
    )

    def anim(delay: float) -> str:
        return "" if static else f' class="line" style="animation-delay:{delay:.2f}s"'

    # Card chrome (clipped to the rounded shape).
    parts.append('<g clip-path="url(#card)">\n')
    parts.append(f'<rect width="{WIDTH}" height="{height}" fill="{BG}"/>\n')
    parts.append(f'<rect width="{WIDTH}" height="{TITLE_H}" fill="{TITLE_BG}"/>\n')

    # Title bar traffic lights.
    for idx, color in enumerate(DOTS):
        cx = 24 + idx * 20
        parts.append(f'<circle cx="{cx}" cy="{TITLE_H // 2}" r="6" fill="{color}"{anim(0)}/>\n')

    # Hostname.
    parts.append(
        f'<text x="{WIDTH // 2}" y="{TITLE_H // 2 + 5}" text-anchor="middle" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
        f'font-size="{FONT + 1}" fill="{HOST_TEXT}"{anim(0)}>{_xml_escape(HOST)}</text>\n'
    )

    # Key/value rows.
    for i, (label, value) in enumerate(ROWS):
        y = CONTENT_TOP + i * ROW_H + BASELINE
        delay = 0.12 + i * ROW_STAGGER
        if label:
            color = LABEL_COLORS.get(label, TEXT)
            parts.append(
                f'<text x="{LABEL_END}" y="{y}" text-anchor="end" '
                f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
                f'font-size="{FONT}" fill="{color}"{anim(delay)}>'
                f"{_xml_escape(label)}:</text>\n"
            )
        parts.append(
            f'<text x="{VALUE_X}" y="{y}" '
            f'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" '
            f'font-size="{FONT}" fill="{TEXT}"{anim(delay)}>'
            f"{_xml_escape(value)}</text>\n"
        )

    parts.append("</g>\n")
    # Border on top of the rounded card.
    parts.append(
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" '
        f'rx="12" fill="none" stroke="{BORDER}"/>\n'
    )
    parts.append("</svg>\n")

    OUTPUT.write_text("".join(parts))
    print(f"wrote {OUTPUT.name} ({WIDTH}x{height})")


if __name__ == "__main__":
    main()
