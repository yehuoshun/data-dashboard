"""语雀数据源采集 — 通过 mcporter CLI 调 yuque-mcp（编辑中心全景，Cookie 认证）。

一个调用拿全套核心指标，不用遍历知识库。
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
from datetime import datetime, timezone


class YuqueError(RuntimeError):
    pass


def _mcporter_root() -> str | None:
    """mcporter 按 cwd 读取 config/mcporter.json，向上找该配置所在目录。"""
    for parent in pathlib.Path(__file__).resolve().parents:
        if (parent / "config" / "mcporter.json").exists():
            return str(parent)
    return None


def _call(tool: str, args: dict | None = None, timeout: int = 90) -> dict:
    exe = shutil.which("mcporter")
    if not exe:
        raise YuqueError("未找到 mcporter CLI")
    cmd = [exe, "call", f"yuque-mcp.{tool}", "--args", json.dumps(args or {}, ensure_ascii=False)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=_mcporter_root())
    if proc.returncode != 0:
        raise YuqueError(f"语雀 MCP [{tool}] 失败: {proc.stderr.strip()[:300]}")
    txt = proc.stdout.strip()
    i = txt.find("{")
    if i < 0:
        raise YuqueError(f"语雀 MCP [{tool}] 非 JSON 返回: {txt[:200]}")
    return json.loads(txt[i:])


def _metric(node, key: str) -> dict:
    return node.get(key) or {}


def collect() -> dict:
    ec = _call("yuque_get_editor_center")
    ov = ec.get("overview") or {}
    ed = ec.get("editing") or {}
    en = ec.get("engagement") or {}

    books, docs, notes, words = _metric(ov, "books"), _metric(ov, "docs"), _metric(ov, "notes"), _metric(ov, "words")
    et, edays = _metric(ed, "edit_times"), _metric(ed, "edit_days")

    return {
        "source": "yuque",
        "user": {"login": ec.get("login") or "yehuoshun"},
        "overview": {
            "books_all": books.get("all", 0),
            "books_30d": books.get("last_30d", 0),
            "docs_all": docs.get("all", 0),
            "docs_30d": docs.get("last_30d", 0),
            "notes_all": notes.get("all", 0),
            "words_all": words.get("all", 0),
            "words_30d": words.get("last_30d", 0),
            "days_since_join": ov.get("days_since_join", 0),
        },
        "editing": {
            "edit_times_all": et.get("all", 0),
            "edit_times_30d": et.get("last_30d", 0),
            "edit_days_all": edays.get("all", 0),
            "edit_days_30d": edays.get("last_30d", 0),
        },
        "engagement": {
            "liked_all": _metric(en, "liked").get("all", 0),
        },
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }