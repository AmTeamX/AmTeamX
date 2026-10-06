#!/usr/bin/env python3
"""Render the profile sections as a single animated terminal-card SVG.

Emits Experience, Projects, Skills, and Contact as stacked "terminal window"
cards — same frame, monospace font, and fade/slide-in animation as the info
card — and writes sections.svg.

Usage:
    python scripts/make_sections.py   # writes sections.svg
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "sections.svg"

# --- Geometry / palette (match info-card.svg) -----------------------------
WIDTH = 860
PAD_X = 30
TITLE_H = 40
LINE_H = 22
FONT = 15
MAX_CHARS = 82

FONT_FAMILY = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
BG = "#0d1117"
TITLE_BG = "#161b22"
BORDER = "#30363d"
TITLE_TEXT = "#e6edf3"
TEXT = "#c9d1d9"
DIM = "#8b949e"
ACCENT = "#79c0ff"
DOTS = ["#ff5f56", "#ffbd2e", "#27c93f"]

CARD_GAP = 20
TOP_PAD = 18
BOT_PAD = 20
KV_LABEL_W = 118  # px for label column (skills / contact)

# --- Animation ------------------------------------------------------------
LINE_STAGGER = 0.045
CARD_GAP_TIME = 0.28


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def wrap(text: str, width: int = MAX_CHARS) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= width:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# --------------------------------------------------------------------------
# Content -> visual lines. A visual line is one of:
#   ("text", str, color)
#   ("kv", label, value)
#   ("spacer",)
# --------------------------------------------------------------------------
def build_sections() -> list[dict]:
    sections = []

    # --- Experience ---
    exp_lines = []
    exp_entries = [
        (
            "Software Engineer AI Intern",
            "Omise (Opn Payments) · Apr 2026 – Present",
            "Python Risk Score Engine for automated underwriting; KYC AI "
            "solutions; PoCs in Next.js, Golang, JS",
        ),
        (
            "Backend Developer Intern / Part-time",
            "Tech Horizon (Japan Fintech) · Jan 2026 – Mar 2026",
            "Japanese e-wallet with BNPL in PHP; major payment gateway "
            "integrations",
        ),
        (
            "Lab Assistant",
            "Biomedical Informatics Research Lab · Aug 2024 – Present",
            "End-to-end AI pipelines (TensorFlow, PyTorch) for Full HD "
            "240fps video research",
        ),
        (
            "Software Engineering Intern",
            "CourseSquare · 2024",
            "Maintained and enhanced educational platform web apps",
        ),
    ]
    for i, (role, org, bullet) in enumerate(exp_entries):
        exp_lines.append(("text", "▸ " + role, TITLE_TEXT))
        exp_lines.append(("text", "  " + org, DIM))
        for chunk in wrap(bullet, MAX_CHARS - 6):
            exp_lines.append(("text", "  • " + chunk, TEXT))
        if i < len(exp_entries) - 1:
            exp_lines.append(("spacer",))
    sections.append({"command": "cat experience.md", "lines": exp_lines})

    # --- Projects ---
    proj_lines = []
    projects = [
        (
            "BONDUP",
            "Real-time community & activity app (Lead Mobile Developer)",
            "Flutter · Clean Architecture",
        ),
        (
            "BlinkDx",
            "AI blink anomaly detection (95% accuracy)",
            "Python · PyTorch · Computer Vision · NSC 2025 Honorable Mention",
        ),
        (
            "AI Restricted Area Protection",
            "Bird-detection surveillance system",
            "Python · Computer Vision · 1st Prize AI Hackathon 2024",
        ),
        (
            "MUICT Open House",
            "Mobile-first registration for 200+ concurrent users",
            "Next.js · Express.js · MongoDB",
        ),
    ]
    for i, (name, desc, stack) in enumerate(projects):
        proj_lines.append(("text", name, ACCENT))
        for chunk in wrap(desc, MAX_CHARS - 2):
            proj_lines.append(("text", "  " + chunk, TEXT))
        proj_lines.append(("text", "  " + stack, DIM))
        if i < len(projects) - 1:
            proj_lines.append(("spacer",))
    sections.append({"command": "cat projects.md", "lines": proj_lines})

    # --- Skills ---
    skills_lines = [
        ("kv", "Languages:", "Python, C/C++, Golang, JavaScript, TypeScript, Dart, PHP, SQL"),
        ("kv", "Frontend:", "Flutter, Next.js, React, HTML/CSS, Tailwind CSS"),
        ("kv", "Backend:", "Node.js, Express.js, PostgreSQL, MongoDB, Redis, Firebase, RESTful APIs"),
        ("kv", "AI/ML:", "TensorFlow, PyTorch, Scikit-Learn, Pandas, NumPy, Computer Vision"),
        ("kv", "DevOps:", "Git, Docker, Linux, CI/CD, Agile/Scrum, UML"),
    ]
    sections.append({"command": "cat skills.txt", "lines": skills_lines})

    # --- Contact ---
    contact_lines = [
        ("kv", "Portfolio", "→ profile.teampk.site"),
        ("kv", "LinkedIn", "→ linkedin.com/in/pannawit-krutnak-9728562a8"),
        ("kv", "Email", "→ amteamxmail@gmail.com"),
        ("kv", "GitHub", "→ github.com/AmTeamX"),
    ]
    sections.append({"command": "./contact.sh", "lines": contact_lines})

    return sections


def line_height(kind: str) -> int:
    return 8 if kind == "spacer" else LINE_H


def main() -> None:
    sections = build_sections()

    # Layout: compute each card's height and y offset.
    cards = []
    y = 0
    time = 0.12
    for sec in sections:
        body_h = TOP_PAD + sum(line_height(ln[0]) for ln in sec["lines"]) + BOT_PAD
        card_h = TITLE_H + body_h
        cards.append(
            {
                "command": sec["command"],
                "lines": sec["lines"],
                "y": y,
                "h": card_h,
                "body_h": body_h,
                "start": time,
            }
        )
        time += 0.08 + len(sec["lines"]) * LINE_STAGGER + CARD_GAP_TIME
        y += card_h + CARD_GAP

    total_h = y - CARD_GAP

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {WIDTH} {total_h}" role="img" '
        f'aria-label="Profile sections">\n',
        "<style>"
        ".l{animation:fade-slide 0.4s ease both}"
        "@keyframes fade-slide{from{opacity:0;transform:translateY(8px)}"
        "to{opacity:1;transform:translateY(0)}}"
        f"text{{font-family:{FONT_FAMILY};font-size:{FONT}px}}"
        "</style>\n",
    ]

    baseline = int(FONT * 0.74)

    for card_idx, card in enumerate(cards):
        y0 = card["y"]
        x0 = 0
        w = WIDTH
        h = card["h"]
        start = card["start"]

        # Card chrome (clipped rounded corners + border).
        parts.append(
            f'<defs><clipPath id="clip-{card_idx}">'
            f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" rx="12"/>'
            f'</clipPath></defs>\n'
        )
        parts.append(f'<g clip-path="url(#clip-{card_idx})">\n')
        parts.append(
            f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="{BG}" '
            f'class="l" style="animation-delay:{start:.2f}s"/>\n'
        )
        parts.append(
            f'<rect x="{x0}" y="{y0}" width="{w}" height="{TITLE_H}" '
            f'fill="{TITLE_BG}" class="l" style="animation-delay:{start:.2f}s"/>\n'
        )
        # Traffic-light dots.
        for i, color in enumerate(DOTS):
            cx = x0 + 24 + i * 20
            cy = y0 + TITLE_H // 2
            parts.append(
                f'<circle cx="{cx}" cy="{cy}" r="6" fill="{color}" '
                f'class="l" style="animation-delay:{start:.2f}s"/>\n'
            )
        # Command.
        parts.append(
            f'<text x="{x0 + w // 2}" y="{y0 + TITLE_H // 2 + 5}" '
            f'text-anchor="middle" fill="{TITLE_TEXT}" class="l" '
            f'style="animation-delay:{start + 0.03:.2f}s">'
            f"team@github ~ $ {esc(card['command'])}</text>\n"
        )
        parts.append("</g>\n")
        # Border.
        parts.append(
            f'<rect x="{x0 + 0.5}" y="{y0 + 0.5}" width="{w - 1}" '
            f'height="{h - 1}" rx="12" fill="none" stroke="{BORDER}" '
            f'class="l" style="animation-delay:{start:.2f}s"/>\n'
        )

        # Content lines.
        cy = y0 + TITLE_H + TOP_PAD + baseline
        for li, ln in enumerate(card["lines"]):
            kind = ln[0]
            delay = start + 0.08 + li * LINE_STAGGER
            if kind == "spacer":
                cy += line_height("spacer")
                continue
            if kind == "text":
                _, text, color = ln
                parts.append(
                    f'<text x="{x0 + PAD_X}" y="{cy}" fill="{color}" '
                    f'class="l" style="animation-delay:{delay:.2f}s">'
                    f"{esc(text)}</text>\n"
                )
                cy += LINE_H
            elif kind == "kv":
                _, label, value = ln
                parts.append(
                    f'<text x="{x0 + PAD_X}" y="{cy}" fill="{ACCENT}" '
                    f'class="l" style="animation-delay:{delay:.2f}s">'
                    f"{esc(label)}</text>\n"
                )
                parts.append(
                    f'<text x="{x0 + PAD_X + KV_LABEL_W}" y="{cy}" fill="{TEXT}" '
                    f'class="l" style="animation-delay:{delay:.2f}s">'
                    f"{esc(value)}</text>\n"
                )
                cy += LINE_H

    parts.append("</svg>\n")
    OUTPUT.write_text("".join(parts))
    print(f"wrote {OUTPUT.name} ({WIDTH}x{total_h})")


if __name__ == "__main__":
    main()
