#!/usr/bin/env python3
"""Fetch public GitHub profile stats into data/profile.json — free, no setup.

Uses the public REST API (api.github.com). Works unauthenticated (60 req/hr);
set GITHUB_TOKEN (or GH_TOKEN) for a higher rate limit — the token that GitHub
Actions provides automatically (secrets.GITHUB_TOKEN) works and costs nothing.

The payload holds what the showcase cards render:
- identity: name, bio, followers, public_repos, total stars
- top_languages: repository-weighted share of the user's non-fork repos
  (same weighting GitSkins uses)
- projects: every non-fork repo, most recently pushed first, each with a
  simple recency-based "freshness" score (100 = pushed today, 0 = a year+)

Usage:
    python scripts/fetch_profile.py [username]

Defaults to the GITHUB_USERNAME env var, falling back to the origin remote's
owner (same as fetch_contributions.py).
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "data" / "profile.json"
API = "https://api.github.com"


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


def _headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "amteamx-profile-art",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(url: str) -> dict | list:
    response = requests.get(url, headers=_headers(), timeout=30)
    response.raise_for_status()
    return response.json()


def _all_repos(username: str) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while page <= 5:  # 500 repos is plenty for a profile
        batch = _get(
            f"{API}/users/{username}/repos"
            f"?per_page=100&page={page}&sort=pushed&direction=desc"
        )
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def _days_since(iso: str) -> int:
    then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return max(0, (datetime.now(timezone.utc) - then).days)


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else _default_username()

    print(f"fetching profile for {username} ...")
    user = _get(f"{API}/users/{username}")
    repos = _all_repos(username)

    # Skip forks and the <username>/<username> profile-README repo itself.
    own = [
        r for r in repos
        if not r["fork"] and r["name"].lower() != username.lower()
    ]
    own.sort(key=lambda r: r["pushed_at"], reverse=True)

    # Repository-weighted language share (primary language per non-fork repo).
    counts: dict[str, int] = {}
    for repo in own:
        lang = repo.get("language")
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    total = sum(counts.values()) or 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    top_languages = [
        {"language": lang, "repos": n, "pct": round(n * 100 / total)}
        for lang, n in ranked
    ]

    projects = [
        {
            "name": repo["name"],
            "description": repo.get("description"),
            "language": repo.get("language"),
            "stars": repo["stargazers_count"],
            "pushed_at": repo["pushed_at"],
            "days_since_push": _days_since(repo["pushed_at"]),
            "freshness": max(0, 100 - _days_since(repo["pushed_at"]) * 100 // 365),
        }
        for repo in own  # most recently pushed first; the card picks what to show
    ]

    payload = {
        "username": username,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "name": user.get("name"),
        "bio": user.get("bio"),
        "avatar_url": user.get("avatar_url"),
        "followers": user.get("followers", 0),
        "public_repos": user.get("public_repos", len(repos)),
        "total_stars": sum(r["stargazers_count"] for r in repos),
        "top_languages": top_languages,
        "projects": projects,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(
        f"wrote {OUTPUT.relative_to(REPO_ROOT)} — "
        f"{payload['public_repos']} public repos, "
        f"{len(top_languages)} languages, {len(projects)} recent projects"
    )


if __name__ == "__main__":
    main()
