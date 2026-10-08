"""GitHub 数据源采集 — 纯标准库 urllib，零第三方依赖。

需要环境变量之一：GITHUB_PAT_CLASSIC / GITHUB_PAT_FINEGRAINED / GITHUB_TOKEN
（见 ~/.openclaw/secrets/credentials.env）
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.github.com"
_TOKEN_KEYS = ("GITHUB_PAT_CLASSIC", "GITHUB_PAT_FINEGRAINED", "GITHUB_TOKEN")


class GitHubError(RuntimeError):
    pass


def _token() -> str:
    for key in _TOKEN_KEYS:
        if os.environ.get(key):
            return os.environ[key]
    raise GitHubError("未找到 GitHub token（GITHUB_PAT_CLASSIC / GITHUB_PAT_FINEGRAINED）")


def _get(path: str, token: str, params: dict | None = None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "data-dashboard")
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:  # noqa: PERF203
        body = e.read()[:200]
        raise GitHubError(f"GET {path} -> HTTP {e.code}: {body!r}") from e


def _count(path: str, q: str, token: str) -> int:
    return int(_get(path, token, {"q": q, "per_page": 1}).get("total_count", 0))


def collect() -> dict:
    token = _token()
    now = datetime.now(timezone.utc)

    user = _get("/user", token)
    login = user["login"]

    # 老板 repo < 100，单页足够；超 100 需加分页
    repos = _get(
        "/user/repos",
        token,
        {"per_page": 100, "sort": "updated", "affiliation": "owner"},
    )
    if not isinstance(repos, list):
        repos = []

    def commit_count(days: int) -> int:
        since = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        return _count("/search/commits", f"author:{login} author-date:>{since}", token)

    return {
        "source": "github",
        "user": {
            "login": login,
            "name": user.get("name") or login,
            "public_repos": user.get("public_repos", 0),
            "private_repos": user.get("total_private_repos", 0),
            "followers": user.get("followers", 0),
        },
        "repos": {
            "total": len(repos),
            "stars_total": sum(r.get("stargazers_count", 0) for r in repos),
            "top_starred": [
                {"name": r["name"], "stars": r.get("stargazers_count", 0), "private": r["private"]}
                for r in sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:5]
            ],
            "recent_active": [
                {
                    "name": r["name"],
                    "pushed_at": (r.get("pushed_at") or "")[:10],
                    "private": r["private"],
                }
                for r in sorted(repos, key=lambda r: r.get("pushed_at") or "", reverse=True)[:5]
            ],
        },
        "commits": {
            "total": _count("/search/commits", f"author:{login}", token),
            "d1": commit_count(1),
            "d7": commit_count(7),
            "d30": commit_count(30),
            "d365": commit_count(365),
        },
        "open_pr": _count("/search/issues", f"author:{login} type:pr state:open", token),
        "open_issue": _count("/search/issues", f"author:{login} type:issue state:open", token),
        "collected_at": now.isoformat(),
    }