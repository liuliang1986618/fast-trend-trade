#!/usr/bin/env python3
"""结构迁移：output 改为「按日历组织」+ 路径全量同步。

新结构：
  output/daily/<date>/index.html     当天唯一页面（合并渲染器产出，下一步实现）
  output/daily/<date>/data/          当天过程数据（三池 JSON / 筛选产物）
  output/daily/<date>/dashboard.html 当日驾驶舱快照
  output/ledger/history.json         跨日台账
  output/cache/                      与天无关的基础设施（sector_map / kline）
"""
import json
import shutil
from pathlib import Path

BASE = Path("output")

# ---------- 1. 迁移现有产物到「按日」结构 ----------
# 已知日期与其文件
moves_by_day = {}

# snapshots → daily/<date>/dashboard.html
for f in sorted((BASE / "snapshots").glob("dashboard-*.html")):
    day = f.stem.replace("dashboard-", "")
    moves_by_day.setdefault(day, []).append((f, "dashboard.html"))

# tmp pools JSON → daily/<date>/data/
for f in sorted((BASE / "tmp" / "pools").glob("*.json")):
    # 文件名含日期：growth_pool_2026-09-18.json
    stem = f.stem
    day = None
    for part in stem.split("_"):
        if len(part) == 10 and part[4] == "-":
            day = part
            break
    if day:
        moves_by_day.setdefault(day, []).append((f, f"{stem.split('_' + day)[0]}.json" if "_" + day in stem else f"{stem}.json"))

# screen 中间产物 → daily/<date>/data/screen/（最新一天，历史 md 无日期归属则归 09-18）
screen_day = "2026-09-18"
for f in sorted((BASE / "tmp" / "screen").glob("*")):
    if f.is_file():
        moves_by_day.setdefault(screen_day, []).append((f, f"screen/{f.name}"))

# cache → output/cache/
for f in sorted((BASE / "tmp" / "cache").rglob("*")):
    if f.is_file():
        rel = f.relative_to(BASE / "tmp" / "cache")
        moves_by_day.setdefault("__cache__", []).append((f, str(rel)))

# history → ledger
moves_by_day.setdefault("__ledger__", []).append((BASE / "history.json", "history.json"))

# ---------- 2. 执行移动 ----------
made = set()
for day, items in moves_by_day.items():
    if day == "__cache__":
        for src, rel in items:
            dst = BASE / "cache" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.move(str(src), str(dst))
                made.add("cache")
        continue
    if day == "__ledger__":
        for src, rel in items:
            dst = BASE / "ledger" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.move(str(src), str(dst))
                made.add("ledger")
        continue
    ddir = BASE / "daily" / day
    ddir.mkdir(parents=True, exist_ok=True)
    for src, rel in items:
        dst = ddir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.move(str(src), str(dst))
            made.add(day)

# 旧单列日报 → daily/<date>/report.html（历史归位）
for f in sorted((BASE / "daily").glob("2*.html")):
    if "-layered" in f.name or f.name.endswith("index.html"):
        continue
    day = f.stem
    ddir = BASE / "daily" / day
    ddir.mkdir(parents=True, exist_ok=True)
    dst = ddir / "report.html"
    if not dst.exists():
        shutil.move(str(f), str(dst))
        made.add(day)

# 旧 layered → daily/<date>/layered.html（保留原版；合并页后续产出 index.html）
for f in sorted((BASE / "daily").glob("*-layered.html")):
    day = f.stem.replace("-layered", "")
    ddir = BASE / "daily" / day
    ddir.mkdir(parents=True, exist_ok=True)
    dst = ddir / "layered.html"
    if not dst.exists():
        shutil.move(str(f), str(dst))

# 清空的旧目录移入 archive
arch = BASE.parent / "output_archive_pre_v31"
arch.mkdir(exist_ok=True)
for d in ("snapshots", "tmp"):
    src = BASE / d
    if src.exists() and not any(src.iterdir()):
        src.rmdir()
    elif src.exists():
        shutil.move(str(src), str(arch / f"old-{d}"))
        print(f"  [archive] {d} → output_archive_pre_v31/old-{d}")

print("✅ 迁移完成。已建日期目录：", sorted(made - {"cache", "ledger"}))
