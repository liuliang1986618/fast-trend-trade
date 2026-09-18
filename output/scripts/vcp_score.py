#!/usr/bin/env python3
"""蓄势形态（VCP）打分 · run_signal.py vcp 引擎同源公式复刻。

背景：官方 run_signal.py 的 _run_vcp 依赖 np.array_split(DataFrame) 的旧行为，
在 numpy 2.5 / pandas 3.0 下抛 IndexError（ch 退化为 ndarray）。为不改第三方脚本，
此处按其公式逐行复刻（评分权重 40/35/25、tail(80) 四等分、突破价=近20日高、认错价=近20日低）。

用法：python3 output/tmp/vcp_score.py [code ...]
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
KLINE = ROOT / "output" / "tmp" / "kline"

CODES = sys.argv[1:] or [
    "sz002080", "sh600522", "sh603256", "sz300502", "sz002487",
    "sh600183", "sz002436", "sh603186", "sh603601", "sz300398",
]


def vcp(df: pd.DataFrame) -> dict:
    """照抄 _run_vcp：4 段收缩度 40 分 + 量能收缩 35 分 + 贴近高点 25 分。"""
    if len(df) < 60:
        return {"status": "insufficient_data", "bars": len(df)}
    d = df.tail(80).copy()
    close = d["close"]
    n = len(d)
    bounds = [round(i * n / 4) for i in range(5)]          # 等价 np.array_split 的等分
    contractions = []
    for i in range(4):
        ch = d.iloc[bounds[i]:bounds[i + 1]]
        high, low = float(ch["high"].max()), float(ch["low"].min())
        contractions.append({
            "stage": i + 1,
            "drawdown_pct": round((low / high - 1) * 100, 2) if high else 0.0,
            "volume_avg": round(float(ch["volume"].mean()), 0),
        })
    dd = [abs(x["drawdown_pct"]) for x in contractions]
    vv = [x["volume_avg"] for x in contractions]
    dd_score = sum(1 for a, b in zip(dd, dd[1:]) if b <= a) / 3
    vol_score = sum(1 for a, b in zip(vv, vv[1:]) if b <= a) / 3 if all(vv) else 0
    recent_high = float(d["high"].tail(20).max())
    last_close = float(close.iloc[-1])
    near_high = last_close / recent_high if recent_high else 0
    score = round(dd_score * 40 + vol_score * 35 + min(near_high, 1) * 25, 1)
    status = "快憋满" if score >= 75 else ("还在压" if score >= 60 else "没形态")
    return {
        "score": score, "status": status,
        "last_close": round(last_close, 2),
        "trigger_price": round(recent_high, 2),
        "invalid_below": round(float(d["low"].tail(20).min()), 2),
        "dist_to_trigger_pct": round((recent_high / last_close - 1) * 100, 2),
        "contractions": contractions,
    }


def main() -> int:
    print(f"{'代码':<10}{'蓄势分':>7}{'档位':>8}{'现价':>9}{'突破价':>9}{'认错价':>9}{'距突破':>8}")
    print("-" * 62)
    for code in CODES:
        path = KLINE / f"{code}.csv"
        if not path.exists():
            print(f"{code:<10}  （缺 K 线数据）")
            continue
        r = vcp(pd.read_csv(path))
        if "score" not in r:
            print(f"{code:<10}  {r['status']}")
            continue
        print(f"{code:<10}{r['score']:>7}{r['status']:>8}{r['last_close']:>9}"
              f"{r['trigger_price']:>9}{r['invalid_below']:>9}{r['dist_to_trigger_pct']:>7}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
