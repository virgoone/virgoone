#!/usr/bin/env python3
"""Generate profile SVG cards using GitHub REST API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List


API_BASE = "https://api.github.com"


def api_get(url: str, token: str | None) -> object:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "profile-stats-generator")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {url}: {body}") from exc


def iter_owned_repos(username: str, token: str | None) -> Iterable[dict]:
    page = 1
    while True:
        query = urllib.parse.urlencode(
            {"per_page": 100, "page": page, "type": "owner", "sort": "updated"}
        )
        url = f"{API_BASE}/users/{username}/repos?{query}"
        payload = api_get(url, token)
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected repos response: {type(payload)}")
        if not payload:
            break
        for repo in payload:
            if isinstance(repo, dict):
                yield repo
        page += 1


def format_number(value: int) -> str:
    return f"{value:,}"


def parse_github_iso8601(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def render_stats_svg(username: str, user: dict, repo_count: int, total_stars: int) -> str:
    followers = int(user.get("followers", 0))
    created_at = parse_github_iso8601(user.get("created_at"))
    updated_at = parse_github_iso8601(user.get("updated_at"))
    now = datetime.now(timezone.utc)
    account_age = f"{max(0, int((now - created_at).days // 365))}y" if created_at else "n/a"

    rows = [
        ("followers", format_number(followers)),
        ("public_repos", format_number(repo_count)),
        ("total_stars", format_number(total_stars)),
        ("account_age", account_age),
    ]

    y = 76
    lines: List[str] = []
    for label, value in rows:
        lines.append(
            f'<text x="30" y="{y}" fill="#8af29f" font-size="12" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace">$ {label}</text>'
        )
        lines.append(
            f'<text x="462" y="{y}" text-anchor="end" fill="#d7ffe0" font-size="18" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace">{value}</text>'
        )
        y += 28

    updated_label = updated_at.strftime("%Y-%m-%d") if updated_at else "n/a"

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195" '
        f'role="img" aria-label="{username} GitHub stats">'
        "<defs>"
        '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#08110b"/>'
        '<stop offset="100%" stop-color="#030604"/>'
        "</linearGradient>"
        '<pattern id="grid" width="18" height="18" patternUnits="userSpaceOnUse">'
        '<path d="M18 0H0V18" fill="none" stroke="#0d1c12" stroke-width="1"/>'
        "</pattern>"
        "</defs>"
        '<rect width="495" height="195" fill="url(#g)"/>'
        '<rect width="495" height="195" fill="url(#grid)" opacity="0.5"/>'
        '<rect x="0.5" y="0.5" width="494" height="194" fill="none" stroke="#1f4028"/>'
        '<text x="30" y="30" fill="#4ff57a" font-size="14" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">[ SYSTEM :: GITHUB PROFILE ]</text>'
        f'<text x="30" y="50" fill="#d7ffe0" font-size="15" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">@{username}</text>'
        f'<text x="462" y="50" text-anchor="end" fill="#7fc38f" font-size="11" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">updated {updated_label}</text>'
        + "".join(lines)
        + '<rect x="28" y="161" width="439" height="12" fill="#0a120d" stroke="#1a3422"/>'
        + '<text x="36" y="170" fill="#7fc38f" font-size="10" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">status=online</text>'
        + '<text x="462" y="170" text-anchor="end" fill="#7fc38f" font-size="10" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">source=api.github.com</text>'
        + "</svg>"
    )


def render_top_langs_svg(username: str, lang_bytes: Dict[str, int]) -> str:
    total = sum(lang_bytes.values())
    top = sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)[:6]

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195" '
        f'role="img" aria-label="{username} top languages">',
        "<defs>",
        '<linearGradient id="g2" x1="0" y1="0" x2="1" y2="1">',
        '<stop offset="0%" stop-color="#070d10"/>',
        '<stop offset="100%" stop-color="#040709"/>',
        "</linearGradient>",
        '<pattern id="grid2" width="18" height="18" patternUnits="userSpaceOnUse">',
        '<path d="M18 0H0V18" fill="none" stroke="#122028" stroke-width="1"/>',
        "</pattern>",
        "</defs>",
        '<rect width="495" height="195" fill="url(#g2)"/>',
        '<rect width="495" height="195" fill="url(#grid2)" opacity="0.5"/>',
        '<rect x="0.5" y="0.5" width="494" height="194" fill="none" stroke="#24414f"/>',
        '<text x="30" y="30" fill="#54d6ff" font-size="14" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">[ STACK :: TOP LANGUAGES ]</text>',
    ]

    if total <= 0 or not top:
        lines.append(
            '<text x="30" y="92" fill="#8fa7b2" font-size="14" '
            'font-family="ui-monospace, SFMono-Regular, Menlo, monospace">No public language data</text>'
        )
    else:
        y = 60
        for language, size in top:
            pct = (size / total) * 100
            width = max(2, int((size / total) * 280))
            lines.append(
                f'<text x="30" y="{y}" fill="#d9f5ff" font-size="12" '
                f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace">{language.lower()}</text>'
            )
            lines.append(
                f'<rect x="150" y="{y - 10}" width="280" height="8" fill="#0e151b"/>'
            )
            lines.append(
                f'<rect x="150" y="{y - 10}" width="{width}" height="8" fill="#54d6ff"/>'
            )
            lines.append(
                f'<text x="462" y="{y}" text-anchor="end" fill="#9fc8d8" font-size="12" '
                f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace">{pct:.1f}%</text>'
            )
            y += 20

    lines.append(
        '<text x="30" y="174" fill="#6f95a8" font-size="10" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">scope=owned_non_fork_repos</text>'
    )
    lines.append("</svg>")
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True, help="GitHub username")
    parser.add_argument(
        "--stats-output", default="assets/github-stats.svg", help="Stats SVG output path"
    )
    parser.add_argument(
        "--langs-output", default="assets/top-langs.svg", help="Top languages SVG output path"
    )
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")

    user = api_get(f"{API_BASE}/users/{args.username}", token)
    if not isinstance(user, dict):
        raise RuntimeError(f"Unexpected user response: {type(user)}")

    total_stars = 0
    repo_count = 0
    language_totals: Dict[str, int] = defaultdict(int)

    for repo in iter_owned_repos(args.username, token):
        if repo.get("fork"):
            continue
        repo_count += 1
        total_stars += int(repo.get("stargazers_count", 0) or 0)
        languages_url = repo.get("languages_url")
        if isinstance(languages_url, str) and languages_url:
            payload = api_get(languages_url, token)
            if isinstance(payload, dict):
                for name, size in payload.items():
                    if isinstance(name, str) and isinstance(size, int):
                        language_totals[name] += size

    stats_svg = render_stats_svg(args.username, user, repo_count, total_stars)
    langs_svg = render_top_langs_svg(args.username, language_totals)

    stats_out = Path(args.stats_output)
    langs_out = Path(args.langs_output)
    stats_out.parent.mkdir(parents=True, exist_ok=True)
    langs_out.parent.mkdir(parents=True, exist_ok=True)
    stats_out.write_text(stats_svg, encoding="utf-8")
    langs_out.write_text(langs_svg, encoding="utf-8")
    print(f"Wrote {stats_out} and {langs_out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
