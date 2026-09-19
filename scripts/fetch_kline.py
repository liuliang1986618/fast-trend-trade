#!/usr/bin/env python3
"""取日K转 CSV（供 run_signal.py --source csv 使用）。

背景：run_signal.py 的 --source westock 依赖 `westock-data` 命令（本机未安装），
而 westock CLI（v0.0.4）名为 `westock`。故改用 CSV 通道：westock kline → CSV → run_signal。
"""
import csv
import subprocess
import sys
from pathlib import Path

CODES = [
    "sz002080", "sh600522", "sh603256", "sz300502", "sz002487",
    "sh600183", "sz002436", "sh603186", "sh603601", "sz300398",
]

ROOT = Path(__file__).resolve().parents[1]          # 仓库根
OUT = ROOT / "output" / "tmp" / "kline"
OUT.mkdir(parents=True, exist_ok=True)


def fetch(code: str, limit: int = 120) -> int:
    r = subprocess.run(
        ["westock", "kline", code, "--period", "day", "--limit", str(limit)],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        print(f"ERR  {code}: {(r.stderr or r.stdout)[:120]}")
        return 0
    header, rows = None, []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        rows.append(cells)
    if not rows:
        print(f"NODATA {code}")
        return 0
    rows.reverse()                                   # CLI 返回降序 → 升序
    idx = {k: i for i, k in enumerate(header)}
    path = OUT / f"{code}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "open", "high", "low", "close", "volume"])
        for rw in rows:
            w.writerow([rw[idx["date"]], rw[idx["open"]], rw[idx["high"]],
                        rw[idx["low"]], rw[idx["last"]], rw[idx["volume"]]])
    print(f"OK   {code}  {len(rows)} 根 → {path.name}")
    return len(rows)


if __name__ == "__main__":
    total = sum(fetch(c) for c in CODES)
    print(f"合计 {total} 根K线，落地 {OUT}")
    sys.exit(0 if total else 1)
