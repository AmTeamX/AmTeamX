#!/usr/bin/env python3
"""Render the showcase cards: hero.svg, system-scan.svg, projects.svg, stack.svg.

Same terminal-window aesthetic as info-card.svg / sections.svg (dark cards,
traffic lights, monospace, fade-slide reveal). Data comes from local JSON:

    data/profile.json        (scripts/fetch_profile.py)
    data/contributions.json  (scripts/fetch_contributions.py)
    data/ascii-portrait.json (glyph grid, computed once from source-prepped.png
                              and cached so CI never needs the private photo)

Everything is generated from the free public GitHub API + GitHub Actions —
no third-party image services.

Usage:
    python scripts/make_showcase.py
"""

import base64
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
PROFILE_JSON = DATA / "profile.json"
CONTRIB_JSON = DATA / "contributions.json"
GRID_JSON = DATA / "ascii-portrait.json"
PHOTO = REPO_ROOT / "source-prepped.png"

# --- Geometry / palette (match info-card.svg & sections.svg) ---------------
WIDTH = 860
PAD_X = 30
TITLE_H = 40
PAD = 24
FONT = 15
LINE_H = 22
MAX_CHARS = 66

FONT_FAMILY = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
# GitHub dark theme's page background is #0d1117 — cards use a lighter fill and
# a strong border so the window edges stay visible on a profile page.
BG = "#121822"
TITLE_BG = "#1c2431"
BORDER = "#3d444d"
TRACK = "#2a3140"
PANEL = "#0d1117"
TITLE_TEXT = "#e6edf3"
TEXT = "#c9d1d9"
DIM = "#8b949e"
ACCENT = "#79c0ff"
GREEN = "#39d353"
DOTS = ["#ff5f56", "#ffbd2e", "#27c93f"]

LANG_COLORS = {
    "TypeScript": "#3178c6", "Dart": "#00B4AB", "C++": "#f34b7d",
    "C": "#555555", "CMake": "#DA3434", "Python": "#3572A5",
    "JavaScript": "#f1e05a", "Go": "#00ADD8", "PHP": "#4F5D95",
    "Java": "#b07219", "Kotlin": "#A97BFF", "Ruby": "#701516",
    "Swift": "#F05138", "Rust": "#dea584", "HTML": "#e34c26",
    "CSS": "#563d7c", "Shell": "#89e051", "Lua": "#000080",
}

# Static identity lines (edit here; the API only supplies name/bio/stats).
HANDLE = "AmTeamX"
ALIAS = "PWTeam"
ROLE = "Software Engineer AI Intern @ Omise · Full-Stack Developer"
EDU = "ICT @ Mahidol University"
STATUS = "Building · Learning · Shipping"
NAME_FALLBACK = "Pannawit Krutnak"

# Curate the projects card (up to 4 repo names, in order). Empty = the 4 most
# recently pushed non-fork repos.
PINNED: list[str] = []

STAGGER = 0.05
CHAR = 0.6  # monospace advance as a fraction of font size


def esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def wrap(text: str, width: int = MAX_CHARS) -> list[str]:
    words = text.split()
    lines, cur = [], ""
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
    return lines or [""]


def timeago(days: int) -> str:
    if days < 1:
        return "today"
    if days < 14:
        return f"{days}d ago"
    if days < 60:
        return f"{days // 7}w ago"
    if days < 365:
        return f"{days // 30}mo ago"
    return f"{days // 365}y ago"


def lang_color(lang: str | None) -> str:
    return LANG_COLORS.get(lang or "", DIM)


def avatar_data_uri(url: str | None) -> str | None:
    """Fetch the public avatar and inline it as base64.

    SVGs render in an <img> context, where external resources are blocked —
    a data: URI is the only way to ship a raster image inside the file (and it
    removes any dependence on the client's monospace font metrics).
    """
    if not url:
        return None
    import requests

    try:
        response = requests.get(
            url, params={"s": 220}, headers={"User-Agent": "amteamx-profile-art"},
            timeout=20,
        )
        response.raise_for_status()
        mime = response.headers.get("Content-Type", "image/png").split(";")[0]
        if not mime.startswith("image/"):
            return None
        return f"data:{mime};base64,{base64.b64encode(response.content).decode()}"
    except Exception as exc:
        print(f"note: avatar fetch failed ({exc}); falling back to ascii")
        return None


# ---------------------------------------------------------------------------
# ASCII portrait grid (cached so CI never needs the private photo)
# ---------------------------------------------------------------------------
RAMP = " .`:-=+*cs#%@"
CELL_W, CELL_H = 6, 10
SCAN_COLS = 32


def _compute_grid() -> dict:
    """Downsample source-prepped.png into a glyph grid (needs numpy + Pillow)."""
    import numpy as np
    from PIL import Image

    if not PHOTO.exists():
        sys.exit(
            f"missing {GRID_JSON.relative_to(REPO_ROOT)} and {PHOTO.name} — "
            "run this locally once where the photo exists"
        )
    img = Image.open(PHOTO).convert("L")
    rows = max(1, round(img.height / img.width * SCAN_COLS * (CELL_W / CELL_H)))
    small = img.resize((SCAN_COLS, rows), Image.LANCZOS)
    arr = np.asarray(small)
    grid = [
        "".join(RAMP[int(round((255 - int(b)) / 255 * (len(RAMP) - 1)))] for b in row)
        for row in arr
    ]
    return {
        "cols": SCAN_COLS,
        "rows": rows,
        "cell_w": CELL_W,
        "cell_h": CELL_H,
        "grid": grid,
    }


def ascii_grid() -> dict:
    if GRID_JSON.exists():
        return json.loads(GRID_JSON.read_text())
    payload = _compute_grid()
    DATA.mkdir(parents=True, exist_ok=True)
    GRID_JSON.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"cached ascii grid -> {GRID_JSON.relative_to(REPO_ROOT)}")
    return payload


# ---------------------------------------------------------------------------
# Card builder: renders content into a buffer, then wraps it in window chrome
# ---------------------------------------------------------------------------
class Card:
    def __init__(self, cmd: str):
        self.cmd = cmd
        self.buf: list[str] = []
        self.y = 0      # content cursor (relative to content top)
        self.t = 0.16   # animation clock

    def _abs_y(self) -> int:
        return TITLE_H + PAD + self.y

    def text(
        self,
        x: int,
        s: str,
        color: str,
        size: int = FONT,
        anchor: str | None = None,
        advance: int = LINE_H,
    ) -> None:
        mid = f' text-anchor="{anchor}"' if anchor else ""
        baseline = self._abs_y() + int(size * 0.74)
        self.buf.append(
            f'<text x="{x}" y="{baseline}"{mid} font-size="{size}" '
            f'fill="{color}" class="l" style="animation-delay:{self.t:.2f}s">'
            f"{esc(s)}</text>\n"
        )
        self.y += advance
        self.t += STAGGER

    def raw(self, svg: str, advance: int = 0, pause: float = 0.0) -> None:
        self.buf.append(svg)
        self.y += advance
        self.t += pause

    def bar(self, x: int, w_max: int, pct: int, color: str, h: int = 6) -> str:
        w = max(2, round(w_max * pct / 100))
        y = self._abs_y()
        return (
            f'<rect x="{x}" y="{y}" width="{w_max}" height="{h}" rx="{h / 2}" '
            f'fill="{TRACK}"/>'
            f'<rect x="{x}" y="{y}" width="0" height="{h}" rx="{h / 2}" '
            f'fill="{color}">'
            f'<animate attributeName="width" from="0" to="{w}" '
            f'begin="{self.t:.2f}s" dur="0.7s" fill="freeze"/></rect>'
        )

    def render(self) -> str:
        content_h = self.y
        total_h = TITLE_H + PAD + content_h + PAD
        out = [
            '<?xml version="1.0" encoding="UTF-8"?>\n',
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {WIDTH} '
            f'{total_h}" role="img" aria-label="{esc(self.cmd)} profile card">\n',
            "<style>"
            ".l{animation:fade-slide 0.4s ease both}"
            "@keyframes fade-slide{from{opacity:0;transform:translateY(8px)}"
            "to{opacity:1;transform:translateY(0)}}"
            # No font-size here: a CSS size would override the per-text
            # font-size attributes (CSS beats presentation attributes).
            f"text{{font-family:{FONT_FAMILY}}}" 
            "</style>\n",
        ]
        # Window chrome.
        out.append(
            f'<defs><clipPath id="win">'
            f'<rect width="{WIDTH}" height="{total_h}" rx="12"/>'
            f"</clipPath>"
            # Green scanline sweep shared by the scan-card columns.
            f'<linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{GREEN}" stop-opacity="0"/>'
            f'<stop offset="0.5" stop-color="{GREEN}" stop-opacity="0.45"/>'
            f'<stop offset="1" stop-color="{GREEN}" stop-opacity="0"/>'
            f"</linearGradient></defs>\n"
        )
        out.append(f'<g clip-path="url(#win)">\n')
        out.append(f'<rect width="{WIDTH}" height="{total_h}" fill="{BG}"/>\n')
        out.append(
            f'<rect width="{WIDTH}" height="{TITLE_H}" fill="{TITLE_BG}"/>\n'
        )
        for i, color in enumerate(DOTS):
            out.append(
                f'<circle cx="{24 + i * 20}" cy="{TITLE_H // 2}" r="6" '
                f'fill="{color}"/>\n'
            )
        out.append(
            f'<text x="{WIDTH // 2}" y="{TITLE_H // 2 + 5}" '
            f'text-anchor="middle" fill="{TITLE_TEXT}" '
            f'font-size="16">team@github ~ $ {esc(self.cmd)}</text>\n'
        )
        out.append("</g>\n")
        out.append(
            f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{total_h - 1}" '
            f'rx="12" fill="none" stroke="{BORDER}"/>\n'
        )
        out.extend(self.buf)
        out.append("</svg>\n")
        return "".join(out)


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------
def make_hero(profile: dict, contrib_total: int, active_days: int) -> str:
    card = Card("whoami")
    name = profile.get("name") or NAME_FALLBACK

    # Big name + blinking terminal cursor.
    size = 38
    name_w = int(len(name) * size * CHAR)
    baseline = card._abs_y() + int(size * 0.74)
    card.text(PAD_X, name, TITLE_TEXT, size=size, advance=0)
    card.raw(
        f'<rect x="{PAD_X + name_w + 10}" y="{baseline - 30}" width="16" '
        f'height="38" fill="{GREEN}">'
        f'<animate attributeName="opacity" values="1;0;1" dur="1.2s" '
        f'repeatCount="indefinite"/></rect>'
    )
    card.t += STAGGER
    card.y += 52

    # Inset panel so the identity lines read as boxed output, like the chips.
    panel_y = card.y
    panel_h = 4 * 24 + 24
    card.raw(
        f'<rect x="{PAD_X}" y="{TITLE_H + PAD + panel_y}" width="{WIDTH - 2 * PAD_X}" '
        f'height="{panel_h}" rx="10" fill="{PANEL}" stroke="{BORDER}"/>'
    )
    card.y = panel_y + 12
    card.text(PAD_X + 18, f'@{HANDLE} · "{ALIAS}"', ACCENT, advance=24)
    card.text(PAD_X + 18, ROLE, TEXT, advance=24)
    card.text(PAD_X + 18, EDU, DIM, advance=24)
    card.text(
        PAD_X + 18,
        f"{profile['public_repos']} public repos · "
        f"{contrib_total} contributions last year · "
        f"{active_days} active days · ★ {profile['total_stars']}",
        DIM,
        size=14,
        advance=24,
    )
    card.y = panel_y + panel_h + 14

    # Language chips from live repository weighting.
    x = PAD_X
    for entry in profile.get("top_languages", [])[:5]:
        lang = entry["language"]
        dot_x, cy = x + 14, card._abs_y() + 13
        chip_w = 26 + int(len(lang) * 13 * CHAR) + 12
        card.raw(
            f'<rect x="{x}" y="{cy - 13}" width="{chip_w}" height="26" '
            f'rx="13" fill="{TITLE_BG}" stroke="{BORDER}"/>'
            f'<circle cx="{dot_x}" cy="{cy}" r="4.5" fill="{lang_color(lang)}"/>'
        )
        card.text(x + 26, lang, TEXT, size=13, advance=0)
        x += chip_w + 10
    card.y += 34

    return card.render()


def make_system_scan(profile: dict, contrib: dict) -> str:
    card = Card("./profile-scan --live")
    uri = avatar_data_uri(profile.get("avatar_url"))
    if uri:
        col_w, content_h = _scan_avatar(card, uri)
    else:
        col_w, content_h = _scan_ascii(card)

    langs = " · ".join(e["language"] for e in profile["top_languages"][:4])
    name = profile.get("name") or NAME_FALLBACK
    subject = name if name == ALIAS else f'{name} · "{ALIAS}"'
    stats = [
        ("Subject", subject),
        ("Handle", f"@{HANDLE}"),
        ("Role", "Software Engineer AI Intern @ Omise"),
        ("Status", STATUS),
        ("Languages", langs),
        ("Repositories", f"{profile['public_repos']} public"),
        ("Contributions", f"{contrib['total']} in the last year"),
        ("Active Days", f"{contrib['active_days']} of 365"),
        ("Stars", f"{profile['total_stars']} · {profile['followers']} followers"),
        ("Education", EDU),
        ("Contact", f"github.com/{HANDLE}"),
    ]
    content_h = max(content_h, len(stats) * 26)

    # Stats column.
    card.y = 8
    label_x = PAD_X + col_w + 36
    value_x = label_x + 142
    row_delay = card.t
    for label, value in stats:
        baseline = card._abs_y() + int(FONT * 0.74)
        if label == "Status":
            card.buf.append(
                f'<circle cx="{value_x - 16}" cy="{baseline - 5}" r="3.5" '
                f'fill="{GREEN}">'
                f'<animate attributeName="r" values="3;5;3" dur="1.6s" '
                f'repeatCount="indefinite"/>'
                f'<animate attributeName="opacity" values="0.6;1;0.6" '
                f'dur="1.6s" repeatCount="indefinite"/></circle>'
            )
        card.buf.append(
            f'<text x="{label_x}" y="{baseline}" fill="{ACCENT}" class="l" '
            f'style="animation-delay:{row_delay:.2f}s">{esc(label)}</text>\n'
            f'<text x="{value_x}" y="{baseline}" fill="{TEXT}" class="l" '
            f'style="animation-delay:{row_delay + 0.02:.2f}s">{esc(value)}</text>\n'
        )
        card.y += 26
        card.t += STAGGER
        row_delay = card.t

    # Pad the content so the taller column defines the card height.
    card.y = content_h
    return card.render()


def _scan_avatar(card: Card, uri: str) -> tuple[int, int]:
    """Draw the avatar with a scanning sweep; returns (column width, height)."""
    size = 220
    card.y = 8
    av_y = card._abs_y()
    card.raw(
        f'<defs><clipPath id="av"><rect x="{PAD_X}" y="{av_y}" '
        f'width="{size}" height="{size}" rx="14"/></clipPath></defs>'
        f'<g clip-path="url(#av)">'
        f'<image href="{uri}" xlink:href="{uri}" x="{PAD_X}" y="{av_y}" '
        f'width="{size}" height="{size}" preserveAspectRatio="xMidYMid slice"/>'
        f'<rect x="{PAD_X}" y="{av_y - 24}" width="{size}" height="24" '
        f'rx="12" fill="url(#scan)" opacity="0.7">'
        f'<animate attributeName="y" values="{av_y - 24};{av_y + size};'
        f'{av_y - 24}" dur="3.4s" repeatCount="indefinite"/></rect>'
        f"</g>"
        f'<rect x="{PAD_X + 0.5}" y="{av_y + 0.5}" width="{size - 1}" '
        f'height="{size - 1}" rx="14" fill="none" stroke="{BORDER}"/>'
        f'<rect x="{PAD_X + 10}" y="{av_y + size - 32}" width="64" height="22" '
        f'rx="11" fill="{PANEL}" stroke="{GREEN}"/>'
        f'<text x="{PAD_X + 20}" y="{av_y + size - 17}" font-size="12" '
        f'fill="{GREEN}">● LIVE</text>'
    )
    card.t += 0.3
    return size, size + 16


def _scan_ascii(card: Card) -> tuple[int, int]:
    """Fallback: glyph portrait from the cached grid; returns (width, height)."""
    grid = ascii_grid()
    cols, rows = grid["cols"], grid["rows"]
    cw, ch = grid["cell_w"], grid["cell_h"]
    ascii_w, ascii_h = cols * cw, rows * ch

    y0 = card._abs_y()
    row_delay = card.t
    for i, row in enumerate(grid["grid"]):
        baseline = y0 + i * ch + int(ch * 0.78)
        card.buf.append(
            f'<text x="{PAD_X}" y="{baseline}" font-size="{ch}" fill="{TEXT}" '
            f'class="l" style="animation-delay:{row_delay + i * 0.03:.2f}s">'
            f"{esc(row)}</text>\n"
        )
    gy0, gy1 = y0 - 18, y0 + ascii_h
    card.raw(
        f'<rect x="{PAD_X - 8}" y="{gy0}" width="{ascii_w + 16}" height="24" '
        f'rx="12" fill="url(#scan)" opacity="0.6">'
        f'<animate attributeName="y" values="{gy0};{gy1};{gy0}" '
        f'dur="3.4s" repeatCount="indefinite"/></rect>'
    )
    card.t += 0.3
    return ascii_w, ascii_h


def pick_projects(profile: dict) -> list[dict]:
    repos = profile.get("projects", [])
    if PINNED:
        by_name = {r["name"]: r for r in repos}
        picked = [by_name[n] for n in PINNED if n in by_name]
        if picked:
            return picked[:4]
    return repos[:4]


def make_projects(profile: dict) -> str:
    card = Card("ls ~/repos --sort=recent")
    for i, repo in enumerate(pick_projects(profile)):
        meta = (
            f"{repo['language'] or '—'} · ★ {repo['stars']} · "
            f"pushed {timeago(repo['days_since_push'])}"
        )
        name = "▸ " + repo["name"]
        # Right-aligned meta shares the name line when there is room.
        if len(name) + len(meta) + 4 <= 86:
            baseline = card._abs_y() + int(FONT * 0.74)
            card.buf.append(
                f'<text x="{PAD_X}" y="{baseline}" fill="{ACCENT}" class="l" '
                f'style="animation-delay:{card.t:.2f}s">{esc(name)}</text>\n'
                f'<text x="{WIDTH - PAD_X}" y="{baseline}" '
                f'text-anchor="end" font-size="13" fill="{DIM}" class="l" '
                f'style="animation-delay:{card.t + 0.02:.2f}s">{esc(meta)}</text>\n'
            )
            card.y += LINE_H
            card.t += STAGGER
        else:
            card.text(PAD_X, name, ACCENT)
            card.text(WIDTH - PAD_X, meta, DIM, size=13, anchor="end", advance=0)

        desc = repo.get("description") or "no description provided"
        for chunk in wrap(desc):
            card.text(PAD_X + 12, chunk, DIM, advance=20)

        card.raw(card.bar(PAD_X, WIDTH - 2 * PAD_X - 46, repo["freshness"],
                          lang_color(repo["language"])))
        card.text(WIDTH - PAD_X, f"{repo['freshness']}%", DIM, size=12,
                  anchor="end", advance=18)
        if i < 3:
            card.t += 0.1
            card.y += 12
    return card.render()


def make_stack(profile: dict) -> str:
    card = Card("cat stack.txt --sort=bytes")
    langs = profile.get("top_languages", [])[:6]
    card.text(
        PAD_X,
        f"repository-weighted across {profile['public_repos']} public "
        f"repositories · live from the GitHub API",
        DIM,
        size=13,
        advance=28,
    )
    for entry in langs:
        lang, pct = entry["language"], entry["pct"]
        baseline = card._abs_y() + int(FONT * 0.74)
        card.buf.append(
            f'<circle cx="{PAD_X + 6}" cy="{baseline - 5}" r="5" '
            f'fill="{lang_color(lang)}" class="l" '
            f'style="animation-delay:{card.t:.2f}s"/>\n'
            f'<text x="{PAD_X + 20}" y="{baseline}" fill="{TEXT}" class="l" '
            f'style="animation-delay:{card.t:.2f}s">{esc(lang)}</text>\n'
            + card.bar(PAD_X + 180, WIDTH - PAD_X - 180 - 66, pct,
                       lang_color(lang), h=8)
            + f'<text x="{WIDTH - PAD_X}" y="{baseline}" text-anchor="end" '
            f'font-size="13" fill="{DIM}" class="l" '
            f'style="animation-delay:{card.t + 0.02:.2f}s">{pct}%</text>\n'
        )
        card.y += 36
        card.t += STAGGER
    return card.render()


# ---------------------------------------------------------------------------
def main() -> None:
    if not PROFILE_JSON.exists():
        sys.exit(f"missing {PROFILE_JSON.relative_to(REPO_ROOT)} — "
                 "run scripts/fetch_profile.py first")
    profile = json.loads(PROFILE_JSON.read_text())

    contrib = {"total": 0, "active_days": 0}
    if CONTRIB_JSON.exists():
        raw = json.loads(CONTRIB_JSON.read_text())
        contrib = {
            "total": raw.get("total", 0),
            "active_days": sum(1 for d in raw.get("days", []) if d["count"] > 0),
        }
    else:
        print("note: no contributions.json — run fetch_contributions.py for "
              "live contribution stats")

    outputs = {
        "hero.svg": make_hero(profile, contrib["total"], contrib["active_days"]),
        "system-scan.svg": make_system_scan(profile, contrib),
        "projects.svg": make_projects(profile),
        "stack.svg": make_stack(profile),
    }
    for name, svg in outputs.items():
        (REPO_ROOT / name).write_text(svg)
        print(f"wrote {name}")


if __name__ == "__main__":
    main()
