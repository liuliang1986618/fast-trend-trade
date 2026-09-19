#!/usr/bin/env python3
"""主线趋势强度分（0~100）· history.json rotation.score_formula v2 公式实现。

v2：动量 40%（中期 20 日涨幅 60% + 短期 5 日涨幅 40%）+ 均线 30%（MA20 乖离）+ 量能 30%（中位量比），
全程 3 日加权平滑（0.5/0.3/0.2）；各分量按 settings.tracking_score 的 cap 归一化。

同时按 settings.score_alert 判定 L1/L2 预警（量比 = 当日量 / 前 20 日中位量）。

用法：python3 output/tmp/trend_score.py
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TMP = ROOT / "output" / "tmp"

LINES = [
    ("航运", "sh560710"),
    ("算力(PCB/光通信)", "sh515880"),
    ("粮食", "sz159063"),
    ("半导体", "sh512480"),
]

MOM_CAP, MA_CAP, VOL_CAP = 25.0, 15.0, 2.0      # settings.tracking_score caps
W = {"momentum": 0.4, "ma_bias": 0.3, "volume": 0.3}


def load(code: str) -> pd.DataFrame:
    txt = (TMP / f"etf_{code}.md").read_text(encoding="utf-8")
    header, rows = None, []
    for line in txt.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        rows.append(cells)
    df = pd.DataFrame(rows, columns=header)
    df = df.rename(columns={"last": "close"})
    for c in ("open", "close", "high", "low", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def series(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["ma20"] = d["close"].rolling(20).mean()
    d["chg20"] = (d["close"] / d["close"].shift(20) - 1) * 100
    d["chg5"] = (d["close"] / d["close"].shift(5) - 1) * 100
    d["bias20"] = (d["close"] / d["ma20"] - 1) * 100
    d["med5"] = d["volume"].rolling(5).median()
    d["med20"] = d["volume"].rolling(20).median()
    d["vol_ratio"] = d["med5"] / d["med20"]
    mom = (0.6 * d["chg20"].clip(upper=MOM_CAP).clip(lower=0) / MOM_CAP
           + 0.4 * d["chg5"].clip(upper=MOM_CAP).clip(lower=0) / MOM_CAP)
    ma = d["bias20"].clip(lower=0, upper=MA_CAP) / MA_CAP
    vol = d["vol_ratio"].clip(upper=VOL_CAP) / VOL_CAP
    d["raw"] = (W["momentum"] * mom + W["ma_bias"] * ma + W["volume"] * vol) * 100
    d["score"] = (d["raw"] * 0.5 + d["raw"].shift(1) * 0.3 + d["raw"].shift(2) * 0.2).round(1)
    return d


def main() -> int:
    print(f"{'主线':<20}{'日期':>12}{'分数':>8}{'日环比':>8}{'量比':>7}  预警")
    print("-" * 66)
    for name, code in LINES:
        df = load(code)
        d = series(df).dropna(subset=["score"])
        if d.empty:
            print(f"{name:<20}  （数据不足）")
            continue
        cur, prev = d.iloc[-1], d.iloc[-2] if len(d) > 1 else d.iloc[-1]
        delta = round(cur["score"] - prev["score"], 1)
        vr = round(float(cur["vol_ratio"]), 2)
        alert = "—"
        if vr >= 1.8 and cur["score"] < 40:
            alert = "L1 放量关注"
        elif delta >= 12 and cur["score"] < 60 and vr >= 1.2:
            alert = f"L2 启动预警(Δ{delta:+})"
        elif delta >= 12 and cur["score"] < 60 and vr < 1.2:
            alert = "缩量跳升→降级L1观察"
        note = ""
        if cur["chg20"] is not None:
            note = f"  [20日{cur['chg20']:+.2f}% 5日{cur['chg5']:+.2f}% 乖离{cur['bias20']:+.2f}% 收{cur['close']:.3f}]"
        print(f"{name:<20}{cur['date']:%Y-%m-%d:>12}{cur['score']:>8}{delta:>+8}{vr:>7}  {alert}{note}")
        # 最近 5 日序列（供 rotation 追加参考）
        tail = d.tail(5)
        print("      近5日: " + "  ".join(f"{r['date']:%m-%d}={r['score']}" for _, r in tail.iterrows()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
