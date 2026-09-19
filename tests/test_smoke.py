#!/usr/bin/env python3
"""最小冒烟测试 —— 4 类真实事故的止损器（跑一次约 10 秒，提交前必跑）。

对应的真实事故（2026-09-18/19）：
    test_syntax_all  ← 语法错误（f-string 断裂）被推上远端
    test_ledger      ← 台账数据键名误改 → render KeyError
    test_sentinel    ← 市值单位（元/亿）静默失效数日
    test_jargon      ← 日报出现 T1~T5 黑话（用户投诉）

用法：
    python3 tests/test_smoke.py            # 全部检查（无第三方依赖，纯标准库）
退出码：0 通过 / 1 有失败（可直接接 CI 或提交前钩子）
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "output" / "scripts"
sys.path.insert(0, str(SCRIPTS))

PASS, FAIL = "✅", "❌"
RESULTS = []


def check(name, fn):
    try:
        fn()
        RESULTS.append((name, True, ""))
        print(f"{PASS} {name}")
    except AssertionError as e:
        RESULTS.append((name, False, str(e)))
        print(f"{FAIL} {name} —— {e}")
    except Exception as e:
        RESULTS.append((name, False, f"异常：{type(e).__name__}: {e}"))
        print(f"{FAIL} {name} —— 异常：{type(e).__name__}: {e}")


# ---------- 1. 语法冒烟：全部 .py 可编译 ----------
def test_syntax_all():
    broken = []
    for py in sorted(SCRIPTS.glob("*.py")):
        try:
            compile(py.read_text(encoding="utf-8"), str(py), "exec")
        except SyntaxError as e:
            broken.append(f"{py.name} L{e.lineno}")
    assert not broken, "语法错误：" + "；".join(broken)


# ---------- 2. import 冒烟：函数式模块可导入（脚本型仅编译不执行）----------
def test_imports():
    import importlib
    mods = ["westock_cli", "emotion_parts", "emotion_section", "lint_report",
            "track_pools", "score_stable", "daily_run_20260918",
            "build_growth_pool", "build_etf_holdings"]
    broken = []
    for m in mods:
        try:
            importlib.import_module(m)
        except Exception as e:
            broken.append(f"{m}: {str(e)[:60]}")
    assert not broken, "import 失败：" + "；".join(broken)


# ---------- 3. 术语自检：日报（全部）+ 驾驶舱 ----------
def test_jargon():
    import lint_report
    targets = sorted((ROOT / "output" / "daily").glob("*.html"))
    dash = ROOT / "output" / "dashboard.html"
    if dash.exists():
        targets = list(targets) + [dash]
    broken = []
    for f in targets:
        issues = lint_report.lint(f)
        if issues:
            broken.append(f"{f.name}: {len(issues)} 处（{issues[0][1]} 等）")
    assert not broken, "术语违规：" + "；".join(broken)


# ---------- 4. 台账 schema：关键字段 + 三池样本 ----------
def test_ledger():
    h = json.loads((ROOT / "output" / "history.json").read_text(encoding="utf-8"))
    assert h.get("days"), "days 快照缺失"
    assert (h["days"][-1] or {}).get("date"), "最后快照无日期"
    entries = h.get("pool_tracking", {}).get("entries", [])
    assert entries, "三池跟踪 entries 为空（track_pools 未跑？）"
    counts = {}
    for e in entries:
        counts[e["pool"]] = counts.get(e["pool"], 0) + 1
    for p in "ABC":
        assert counts.get(p, 0) >= 1, f"{p} 池无样本：{counts}"


# ---------- 5. 市值单位哨兵：to_yi 双口径 ----------
def test_sentinel():
    from westock_cli import to_yi
    assert abs(to_yi(130627000000) - 1306.3) < 0.01, "元→亿换算错误（长电科技实测值 130,627,000,000）"
    assert abs(to_yi(1306.27) - 1306.3) < 0.01, "已是亿值时应直通"


ALL = [test_syntax_all, test_imports, test_jargon, test_ledger, test_sentinel]


def main():
    print("=== 最小冒烟测试（tests/test_smoke.py）===")
    for fn in ALL:
        check(fn.__name__, fn)
    fails = [r for r in RESULTS if not r[1]]
    print()
    if fails:
        print(f"❌ {len(fails)}/{len(RESULTS)} 项失败 —— 修正后再提交")
        return 1
    print(f"✅ {len(RESULTS)}/{len(RESULTS)} 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
