#!/usr/bin/env python3
"""三池胜率跟踪台账（P0）—— 让「20 个交易日验证」能够真正跑起来。

【为什么需要】
    三池（A 趋势池 / B 预期驱动池 / C 情绪池）已于 2026-09-18 上线，
    但缺一个"记录结果"的机制 → 20 日后的数据裁决（B 池跑赢 A 池说明原硬闸误伤、
    跑输说明硬闸正确）就无从谈起。本脚本补上这个闭环。

【机制】
    1. record   —— 每个交易日把三池新入池标的写入台账（含入池价）
    2. price    —— 同步记录当日全部在跟踪标的的收盘价（形成价格序列）
    3. backfill —— 按交易日历推算 T+3/5/10/20，从价格序列取值算涨跌幅
    4. stats    —— 汇总三池的样本数 / 平均收益 / 胜率 / 最大不利偏移

【数据落点】
    output/history.json → pool_tracking（append-only：entries 与 price_log 不覆盖历史）

用法：
    python3 output/scripts/track_pools.py            # record + price + backfill + stats
    python3 output/scripts/track_pools.py stats      # 只看统计
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import westock_cli as W  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HIST = ROOT / "output" / "history.json"
TMP = ROOT / "output" / "tmp"
HORIZONS = [3, 5, 10, 20]


# ---------------- 基础设施 ----------------
def load_hist() -> dict:
    return json.loads(HIST.read_text(encoding="utf-8"))


def save_hist(h: dict) -> None:
    HIST.write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")
    json.loads(HIST.read_text(encoding="utf-8"))          # 校验


def trading_days() -> list:
    """交易日历（近 120 天），用于 T+N 推算。"""
    out = W._run(["westock", "trade-calendar", "--limit", "120"])
    days = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0][:4].isdigit():
                days.append(cells[0])
    return sorted(set(days))


def collect_pools(day: str) -> list:
    """收集当日三池标的：[{pool, code, name, note}]。"""
    items = []
    h = load_hist()
    # A 池：当日快照的稳做名单
    todays = [d for d in h.get("days", []) if d.get("date") == day]
    if todays:
        for s in todays[-1].get("stable_list", []):
            items.append({"pool": "A", "code": s["code"], "name": s["name"],
                          "note": f"稳做名单 {s.get('score', '—')} 分 · {s.get('tier', '')}"})
    # B 池：预期驱动池
    bp = TMP / f"growth_pool_{day}.json"
    if bp.exists():
        for x in json.loads(bp.read_text(encoding="utf-8")).get("b_pool", []):
            items.append({"pool": "B", "code": x["code"], "name": x["name"],
                          "note": f"营收{x['torg']:.0f}% · 研发{x['rd_ratio']:.0f}% · PE {x.get('pe', '—')}"})
    # C 池：情绪池梯队
    ep = TMP / f"emotion_pool_{day}.json"
    if ep.exists():
        for x in json.loads(ep.read_text(encoding="utf-8")).get("core", []):
            items.append({"pool": "C", "code": x["code"], "name": x["name"],
                          "note": f"{x['boards']}板 · {x.get('role', '')}"})
    # 去重（同池同码只留一条）
    seen, uniq = set(), []
    for it in items:
        k = (it["pool"], it["code"])
        if k not in seen:
            seen.add(k)
            uniq.append(it)
    return uniq


def main() -> int:
    args = sys.argv[1:]
    mode = args[0] if args else "all"
    h = load_hist()
    pt = h.setdefault("pool_tracking", {"entries": [], "price_log": {}, "created": "2026-09-19"})
    entries, plog = pt.setdefault("entries", []), pt.setdefault("price_log", {})

    day = (h.get("days") or [{}])[-1].get("date")
    if not day:
        print("台账中没有当日快照，退出")
        return 1
    print(f"基准日：{day}")

    # ---------- 1. record：登记当日新入池标的 ----------
    if mode in ("all", "record"):
        existed = {(e["date"], e["pool"], e["code"]) for e in entries}
        new_items = [it for it in collect_pools(day) if (day, it["pool"], it["code"]) not in existed]
        codes = [it["code"] for it in new_items]
        q = W.quote(codes) if codes else {}
        added = 0
        for it in new_items:
            px = W.num(q.get(it["code"], {}).get("price"))
            if px is None:
                continue
            entries.append({"date": day, "pool": it["pool"], "code": it["code"],
                            "name": it["name"], "entry_price": px, "note": it["note"],
                            "follow": {f"t{n}": None for n in HORIZONS}})
            added += 1
        print(f"[record] 新增 {added} 条（A/B/C 合计；已跳过重复）")

    # ---------- 2. price：记录当日收盘价序列 ----------
    if mode in ("all", "price", "backfill"):
        tracked = sorted({e["code"] for e in entries} | {c for v in plog.values() for c in v})
        if tracked:
            q = W.quote(tracked)
            snap = {c: W.num(q.get(c, {}).get("price")) for c in tracked}
            snap = {k: v for k, v in snap.items() if v is not None}
            plog[day] = snap
            print(f"[price] 记录 {len(snap)} 只标的的 {day} 收盘价")

    # ---------- 3. backfill：回填 T+N ----------
    if mode in ("all", "backfill"):
        days = trading_days()
        idx = {d: i for i, d in enumerate(days)}
        filled = 0
        for e in entries:
            base = idx.get(e["date"])
            if base is None:
                continue
            for n in HORIZONS:
                key = f"t{n}"
                if e["follow"].get(key) is not None:
                    continue
                target = base + n
                if target >= len(days):
                    continue                      # 还没到 T+N
                td = days[target]
                px = (plog.get(td) or {}).get(e["code"])
                if px is None:
                    continue                      # 那天的价格未记录
                e["follow"][key] = {
                    "date": td, "price": px,
                    "ret_pct": round((px / e["entry_price"] - 1) * 100, 2),
                }
                filled += 1
        print(f"[backfill] 新回填 {filled} 个 T+N 观测")

    # ---------- 4. stats ----------
    if mode in ("all", "stats"):
        print("\n=== 三池跟踪统计 ===")
        print(f"{'池':<4}{'样本':>6}{'已回填':>8}  " + "  ".join(f"T+{n}均收益 / 胜率" for n in HORIZONS))
        for pool in ("A", "B", "C"):
            rows = [e for e in entries if e["pool"] == pool]
            if not rows:
                print(f"{pool:<4}{0:>6}")
                continue
            cells = []
            for n in HORIZONS:
                vals = [e["follow"][f"t{n}"]["ret_pct"] for e in rows if e["follow"].get(f"t{n}")]
                if vals:
                    win = sum(1 for v in vals if v > 0) / len(vals) * 100
                    cells.append(f"{sum(vals)/len(vals):+6.2f}% / {win:4.0f}%")
                else:
                    cells.append("    待回填   ")
            done = sum(1 for e in rows if any(e["follow"].values()))
            print(f"{pool:<4}{len(rows):>6}{done:>8}  " + "  ".join(cells))
        print(f"\n合计样本 {len(entries)} 条（A/B/C）")
        if not any(any(e["follow"].values()) for e in entries):
            print("提示：T+N 观测需等后续交易日积累（当前均为「待回填」属正常）")

    save_hist(h)
    print(f"\n✅ 台账已更新 → {HIST.name}（pool_tracking.entries={len(entries)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
