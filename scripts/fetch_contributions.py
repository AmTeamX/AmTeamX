#!/usr/bin/env python3
"""Fetch a user's public GitHub contribution calendar — no token required.

GitHub serves the contribution calendar as public HTML at
https://github.com/users/<username>/contributions (the same fragment the
profile page itself uses). We fetch it, parse the day cells, and write
data/contributions.json with the raw days plus derived stats (current streak,
longest streak, best day, monthly totals).

Usage:
    python scripts/fetch_contributions.py [username]

Defaults to the GITHUB_USERNAME env var, falling back to the owner of this
repository.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "data" / "contributions.json"
URL_TEMPLATE = "https://github.com/users/{username}/contributions"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}


def _default_username() -> str:
    env = os.environ.get("GITHUB_USERNAME")
    if env:
        return env
    try:
        remote = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "AmTeamX"
    match = re.search(r"github\.com[:/]([^/]+)", remote)
    return match.group(1) if match else "AmTeamX"


def _parse_count(text: str) -> int:
    if re.search(r"\bno contributions?\b", text, re.IGNORECASE):
        return 0
    match = re.search(r"(\d+)\s+contributions?", text)
    if match:
        return int(match.group(1))
    return 0


def _fetch_days(username: str) -> list[dict]:
    url = URL_TEMPLATE.format(username=username)
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Counts live in <tool-tip for="cell-id">"N contributions on ..."</tool-tip>.
    count_by_id: dict[str, int] = {}
    for tip in soup.find_all("tool-tip"):
        tip_id = tip.get("for")
        if tip_id:
            count_by_id[tip_id] = _parse_count(tip.get_text(" ", strip=True))

    days: list[dict] = []
    for cell in soup.find_all("td"):
        date_str = cell.get("data-date")
        if not date_str:
            continue
        try:
            level = int(cell.get("data-level", "0") or 0)
        except ValueError:
            level = 0
        days.append(
            {
                "date": date_str,
                "count": count_by_id.get(cell.get("id"), 0),
                "level": level,
            }
        )

    if not days:
        raise RuntimeError(
            f"no contribution cells parsed from {url}; GitHub may have changed "
            "the markup"
        )

    days.sort(key=lambda d: d["date"])
    return days


def _compute_stats(days: list[dict]) -> dict:
    counts = {d["date"]: d["count"] for d in days}
    dates = sorted(counts)

    total = sum(counts.values())

    # Current streak: consecutive positive days ending at the latest date,
    # tolerating a trailing zero (today may simply not be over yet).
    current = 0
    idx = len(dates) - 1
    if idx >= 0 and counts[dates[idx]] == 0:
        idx -= 1
    while idx >= 0 and counts[dates[idx]] > 0:
        current += 1
        idx -= 1

    longest = 0
    run = 0
    for date_str in dates:
        if counts[date_str] > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    best = max(days, key=lambda d: d["count"])

    monthly: dict[str, int] = {}
    for d in days:
        month = d["date"][:7]
        monthly[month] = monthly.get(month, 0) + d["count"]

    return {
        "total": total,
        "current_streak": current,
        "longest_streak": longest,
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": monthly,
    }


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else _default_username()

    print(f"fetching contributions for {username} ...")
    days = _fetch_days(username)
    stats = _compute_stats(days)

    payload = {
        "username": username,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": days,
        **stats,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(
        f"wrote {OUTPUT.relative_to(REPO_ROOT)} — "
        f"{len(days)} days, {stats['total']} contributions"
    )


if __name__ == "__main__":
    main()
