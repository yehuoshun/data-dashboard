#!/usr/bin/env python3
"""Push working tree to GitHub via REST git-data API.

Fallback for when `git push` over HTTPS is blocked by the sandbox network
(git POST to /git-*-pack returns 502). Compares the working tree against the
remote tree directly, so it does not depend on local commit history.
"""
import base64, json, os, subprocess, sys, urllib.request, urllib.error

PROJ = os.path.dirname(os.path.abspath(__file__))
REPO = "yehuoshun/data-dashboard"
BRANCH = "main"
TOKEN = os.environ.get("GITHUB_PAT_CLASSIC") or os.environ.get("GITHUB_PAT_FINEGRAINED")


def api(method, path, payload=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode()
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as e:
        print(f"API {method} {path} failed: {e.code} {e.read().decode()[:300]}", file=sys.stderr)
        raise


def git(*args, **kw):
    return subprocess.run(["git", "-C", PROJ, *args], capture_output=True, text=True,
                          check=kw.get("check", True)).stdout.strip()


def main():
    if not TOKEN:
        print("[api_push] 缺少 GitHub token", file=sys.stderr)
        return 1

    head = api("GET", f"/git/ref/heads/{BRANCH}")["object"]
    base_commit = api("GET", f"/git/commits/{head['sha']}")
    base_tree = base_commit["tree"]["sha"]
    remote = {e["path"]: e for e in api("GET", f"/git/trees/{base_tree}?recursive=1")["tree"]}

    tracked = git("ls-files").splitlines()
    entries, changed, deleted = [], [], []
    for path in tracked:
        full = os.path.join(PROJ, path)
        if not os.path.exists(full):
            if path in remote:
                deleted.append(path)
            continue
        local_sha = git("hash-object", "--", path)
        if remote.get(path, {}).get("sha") == local_sha:
            continue
        content = base64.b64encode(open(full, "rb").read()).decode()
        blob = api("POST", "/git/blobs", {"content": content, "encoding": "base64"})
        mode = "100755" if os.access(full, os.X_OK) else "100644"
        entries.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
        changed.append(path)

    for path in deleted:
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})

    if not entries:
        print("[api_push] 远端内容已是最新，无需推送")
        return 0

    tree = api("POST", "/git/trees", {"base_tree": base_tree, "tree": entries})
    msg = git("log", "-1", "--pretty=%B", check=False) or "chore: 数据自动更新"
    commit = api("POST", "/git/commits", {"message": msg, "tree": tree["sha"],
                                         "parents": [head["sha"]]})
    api("PATCH", f"/git/refs/heads/{BRANCH}", {"sha": commit["sha"], "force": False})
    print(f"[api_push] 已推送 {commit['sha'][:7]}（{len(changed)} 改 / {len(deleted)} 删）")
    return 0


if __name__ == "__main__":
    sys.exit(main())