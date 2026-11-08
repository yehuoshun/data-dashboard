#!/usr/bin/env bash
# data-dashboard 自动更新：采集 → 渲染 → 提交 → 推送（Pages 自动重建）
set -euo pipefail

PROJ="/home/admin/.openclaw/workspace/code/data-dashboard"
cd "$PROJ"
source /home/admin/.openclaw/secrets/credentials.env

python3 collect.py

git add -A
if git diff --cached --quiet; then
  echo "[update] 数据无变化，跳过提交"
  exit 0
fi
git -c user.name=yehuoshun -c user.email=yehuoshun@users.noreply.github.com \
  commit -q -m "chore: 数据自动更新 $(date '+%Y-%m-%d %H:%M')"

# 优先直连推送；沙箱网络对 git HTTPS POST 返回 502 时回退到 REST API 推送
if git push -q origin main 2>/dev/null; then
  echo "[update] 已推送 → Pages 将自动重建"
else
  echo "[update] git push 失败，改用 GitHub API 推送"
  python3 api_push.py
fi
