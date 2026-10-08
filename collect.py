#!/usr/bin/env python3
"""数据聚合看板 — 采集 + 渲染。

用法：
    python3 collect.py                 # 采集 + 渲染
    python3 collect.py --collect-only  # 只采集 → data/dashboard.json
    python3 collect.py --render-only   # 只用现有 JSON 渲染 → docs/index.html
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from sources import github, yuque  # noqa: E402

DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "docs"  # GitHub Pages 源目录
TEMPLATE = ROOT / "template" / "index.html"
DATA_PLACEHOLDER = "/*__DASHBOARD_DATA__*/"

SOURCES = (("github", github), ("yuque", yuque))


def collect_all() -> dict:
    result: dict = {"collected_at": datetime.now(timezone.utc).isoformat(), "sources": {}}
    for name, mod in SOURCES:
        try:
            result["sources"][name] = mod.collect()
            print(f"  ✅ {name}")
        except Exception as e:  # noqa: BLE001 — 单源失败不拖垮整体
            result["sources"][name] = {"source": name, "error": str(e)}
            print(f"  ❌ {name}: {e}")
    return result


def render(data: dict) -> pathlib.Path:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if DATA_PLACEHOLDER not in tpl:
        raise RuntimeError(f"模板缺少占位符 {DATA_PLACEHOLDER}")
    html = tpl.replace(DATA_PLACEHOLDER, json.dumps(data, ensure_ascii=False))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="数据聚合看板")
    ap.add_argument("--collect-only", action="store_true", help="只采集，不渲染")
    ap.add_argument("--render-only", action="store_true", help="只渲染，不采集")
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data_file = DATA_DIR / "dashboard.json"

    if args.render_only:
        data = json.loads(data_file.read_text(encoding="utf-8"))
    else:
        print("采集数据源...")
        data = collect_all()
        data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  → {data_file.relative_to(ROOT)}")

    if not args.collect_only:
        out = render(data)
        print(f"  → {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())