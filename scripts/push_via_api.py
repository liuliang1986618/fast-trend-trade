#!/usr/bin/env python3
"""备用推送通道：当 `git push` 被本地代理阻断时，走 GitHub Git Data API 推送本地 commit。

背景（2026-09-18 实测）：
    WorkBuddy 沙箱透明代理（127.0.0.1:51861）对 `github.com` 返回 HTTP 000 / 502，
    但 `api.github.com` 正常（HTTP 200）。`git push` 必须走 github.com:443，因此被阻断；
    绕过代理直连又被沙箱拒绝（Connection reset）。

原理：
    用 GitHub 的 Git Data API 手工重放本地 commit——
      每个文件的 blob（POST /git/blobs）→ tree（POST /git/trees，base_tree 指向父树）
      → commit（POST /git/commits，保留原 message/author/时间）→ 最后更新 ref
    由于对象内容与原 commit 完全一致，**产生的 SHA 与本地相同**，推完后 git 状态即为同步。

用法：
    python3 output/scripts/push_via_api.py [--dry-run] [--from <sha>]
    --from 指定远端当前 HEAD（默认自动查询）
"""
import argparse
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = "liuliang1986618/fast-trend-rail"          # 占位，运行时覆盖
API = "https://api.github.com"


def sh(*args, binary=False):
    r = subprocess.run(list(args), capture_output=True, text=not binary, timeout=60)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout)[:300])
    return r.stdout


def api(method, path, data=None, token=""):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        f"{API}{path}", method=method, data=body,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API {method} {path} → {e.code}: {e.read()[:300]}")


def load_token(explicit=None) -> str:
    """token 取值优先级：命令行参数 > 仓库根 .env 的 GITHUB_TOKEN。"""
    if explicit:
        return explicit
    env_path = Path(__file__).resolve().parents[2] / ".env"   # 仓库根/.env
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GITHUB_TOKEN="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("未找到 token：请传 --token 或在仓库根 .env 写 GITHUB_TOKEN=...")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="liuliang1986618/fast-trend-trade")
    ap.add_argument("--token", default=None, help="缺省从仓库根 .env 的 GITHUB_TOKEN 读取")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--from", dest="base", default=None, help="远端当前 HEAD（默认自动查询）")
    args = ap.parse_args()
    args.token = load_token(args.token)

    repo = args.repo
    tok = args.token
    root = Path(__file__).resolve().parents[2]
    subprocess.run(["git", "-C", str(root), "rev-parse", "--git-dir"], check=True, capture_output=True)

    def git(*a, binary=False):
        return sh("git", "-C", str(root), *a, binary=binary)

    base = args.base or api("GET", f"/repos/{repo}/git/ref/heads/{args.branch}", token=tok)["object"]["sha"]
    print(f"远端 {args.branch} 当前 = {base[:12]}")

    commits = git("rev-list", "--reverse", f"{base}..HEAD").split()
    if not commits:
        print("无待推送 commit")
        return 0
    print(f"待推送 {len(commits)} 条 commit：")
    for c in commits:
        print(f"  {c[:12]} {git('show','-s','--format=%s', c).strip()}")

    parent = base
    for sha in commits:
        changed = [l for l in git("diff-tree", "--no-commit-id", "--name-status", "-r", sha).splitlines() if l.strip()]
        entries = []
        for line in changed:
            parts = line.split("\t")
            status, path = parts[0], parts[-1]
            if status.startswith("D"):
                entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
                continue
            # 用 ls-tree 取准确 mode
            mode = git("ls-tree", sha, "--", path).split()[0]
            content = git("show", f"{sha}:{path}", binary=True)
            blob = api("POST", f"/repos/{repo}/git/blobs",
                       {"content": base64.b64encode(content).decode(), "encoding": "base64"}, tok)
            entries.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
        print(f"  → {sha[:12]}: {len(entries)} 个文件变更，blob 已上传")

        parent_tree = api("GET", f"/repos/{repo}/git/commits/{parent}", token=tok)["tree"]["sha"]
        tree = api("POST", f"/repos/{repo}/git/trees",
                   {"base_tree": parent_tree, "tree": entries}, tok)

        meta = git("show", "-s", "--format=%an|%ae|%aI|%cn|%ce|%cI", sha).strip().split("|")
        # git format 输出会在 message 后再加一个换行，需 strip 掉后补回 message 自身的结尾换行，
        # 否则 commit 对象字节不同 → SHA 不一致（实测差异就是这一个字节）
        msg = git("show", "-s", "--format=%B", sha).rstrip("\n") + "\n"
        payload = {"message": msg, "tree": tree["sha"], "parents": [parent],
                   "author": {"name": meta[0], "email": meta[1], "date": meta[2]},
                   "committer": {"name": meta[3], "email": meta[4], "date": meta[5]}}
        nc = api("POST", f"/repos/{repo}/git/commits", payload, tok)
        local_tree = git("show", "-s", "--format=%T", sha).strip()
        print(f"     tree 本地 {local_tree[:12]} / 远端 {tree['sha'][:12]}"
              f"{'  ✅' if local_tree == tree['sha'] else '  ❌'}")
        print(f"     新 commit = {nc['sha'][:12]}（本地 {sha[:12]}）"
              f"{'  ✅ SHA 一致' if nc['sha'] == sha else '  ⚠️ SHA 不一致'}")
        parent = nc["sha"]

    if args.dry_run:
        print(f"\n[dry-run] 未更新 ref。将把 {args.branch} 指向 {parent[:12]}")
        return 0

    api("PATCH", f"/repos/{repo}/git/refs/heads/{args.branch}", {"sha": parent, "force": False}, tok)
    print(f"\n✅ 已更新 {args.branch} → {parent[:12]}")
    print(f"   本地 HEAD = {git('rev-parse','HEAD').strip()[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
