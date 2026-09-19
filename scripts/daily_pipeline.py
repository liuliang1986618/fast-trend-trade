#!/usr/bin/env python3
"""每日流水线一键串联（run_daily 数据快照之后的全部步骤）。

用途：
    · 手动：python3 output/scripts/daily_pipeline.py
    · 自动化：prompt 只需执行本脚本，避免 AI 漏跑步骤

步骤（失败即停，后续步骤依赖前面产物）：
    1. build_growth_pool.py      B 预期驱动池（全市场财务筛 + 技术面买点）
    2. build_etf_holdings.py     ETF 持仓反查（双来源）
    3. build_emotion_pool.py     情绪票池（温度计 + 梯队 + 红旗）
    4. track_pools.py            三池跟踪台账（record + price + backfill + stats）
    5. score_stable.py --json    A 池五维规则分
    6. render_v3_layered.py      四层架构日报（末尾自动跑术语自检）

幂等性：重复运行安全（record 去重、price 覆盖写、backfill 只填空值）。
注：不含 run_daily.py（数据拉取 + 单列日报）—— 那是自动化 prompt 的主任务流程。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ("B 预期驱动池", ["scripts/build_growth_pool.py"]),
    ("ETF 持仓反查", ["scripts/build_etf_holdings.py"]),
    ("情绪票池", ["scripts/build_emotion_pool.py"]),
    ("封板时间分析", ["scripts/build_fengban.py"]),
    ("三池跟踪台账", ["scripts/track_pools.py"]),
    ("A 池规则分", ["scripts/score_stable.py", "--json"]),
    ("四层架构日报", ["scripts/render_v3_layered.py"]),
]


def main() -> int:
    fails = []
    for name, args in STEPS:
        print(f"\n{'=' * 20} {name} {'=' * 20}")
        r = subprocess.run([sys.executable] + args, cwd=str(ROOT))
        if r.returncode != 0:
            print(f"❌ {name} 失败（exit {r.returncode}），流水线中止")
            fails.append(name)
            break
    print("\n" + "=" * 50)
    if fails:
        print(f"❌ 流水线失败于：{'、'.join(fails)}")
        return 1
    print("✅ 流水线全部完成（三池 + 台账 + 日报）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
