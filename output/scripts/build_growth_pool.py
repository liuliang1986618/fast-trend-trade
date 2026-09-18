#!/usr/bin/env python3
"""B 预期驱动池构建（v0.3 物种分诊台 · 第二层）。

设计依据（config/settings.json → species_classifier）：
  入口判据：营收增速 ≥30%（A股高成长赛道标准）+ 毛利率 >40%（券商框架下调本地化）
  本地校验：研发/营收 ≥15%（创业板第四套标准）+ 市值 ≥100亿
  反闸：营收增速转负 / 毛利率连续两季下滑 / PE>200（业内共识的伪成长信号）
  分诊：PE∈[0,80] 且 PB≤8 → 归 A 池；其余 → B 池

定位：**独立入口**（全市场按财务筛），不挂在日报候选池下
      —— 实测证实日报候选池偏成熟/周期股（1/3 营收负增长），不是高成长聚集地。

产出：output/tmp/growth_pool_<date>.json
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TMP = ROOT / "output" / "tmp"
WT = "/Users/liuliang19/.workbuddy/plugins/cache/cb_teams_marketplace/finance-data/1.5.0/skills/westock-tool/scripts/index.js"
CFG = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
BP = CFG["species_classifier"]["B_growth_pool"]
ENTRY = BP["entry_filter"]
LOCAL = BP["local_check"]
GATES = BP["reject_gates"]


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def to_yi(v):
    """市值统一转亿元。⚠️ 实测 westock quote 的 total_market_cap 单位是「元」
    （长电科技 130,627,000,000 = 1306.27 亿），此处做自动判断以兼容两种口径。"""
    x = num(v)
    if x is None:
        return None
    return round(x / 1e8, 1) if x > 1e6 else round(x, 1)


def parse_md(text):
    hdr, rows = None, []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if hdr is None:
            hdr = cells
            continue
        if len(cells) == len(hdr):
            rows.append(dict(zip(hdr, cells)))
    return rows


def sh(*args, timeout=180):
    r = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)
    return r.stdout if r.returncode == 0 else ""


def main() -> int:
    import datetime
    day = datetime.date.today().isoformat()

    # ---------- 1. 入口：全市场财务筛选 ----------
    expr = (f"intersect([TORGrowRate > {ENTRY['revenue_growth_min']}, "
            f"GrossIncomeRatio > {ENTRY['gross_margin_min']}])")
    print(f"[1/5] 入口筛选：{expr}")
    rows = parse_md(sh("node", WT, "filter", expr, "--limit", "400"))
    print(f"  → {len(rows)} 只（营收增速>{ENTRY['revenue_growth_min']}% 且 毛利>{ENTRY['gross_margin_min']}%）")
    if not rows:
        print("  无候选，退出")
        return 1

    codes = [r["code"] for r in rows]
    name_of = {r["code"]: r.get("name", r["code"]) for r in rows}
    entry_val = {r["code"]: (num(r.get("TORGrowRate")), num(r.get("GrossIncomeRatio"))) for r in rows}

    # ---------- 2. 行情（市值/PE/PB）----------
    print(f"[2/5] 拉行情（{len(codes)} 只）...")
    quotes = {}
    for i in range(0, len(codes), 30):
        for row in parse_md(sh("westock", "quote", ",".join(codes[i:i + 30]))):
            quotes[row["code"]] = row

    # ---------- 3. 财务（研发/营收 + 多期增速与毛利）----------
    print(f"[3/5] 拉财务（{len(codes)} 只）...")
    fin = {}
    for i in range(0, len(codes), 25):
        for row in parse_md(sh("westock", "finance", ",".join(codes[i:i + 25]),
                               "--type", "income", "--limit", "8", "--fields", "core")):
            fin.setdefault(row["code"], []).append(row)

    # 行业排除（业内「赛道空间」标准的机械化落地）
    smap = {}
    _sm = TMP / "sector_map.json"
    if _sm.exists():
        smap = json.loads(_sm.read_text(encoding="utf-8"))
    excl = set(BP.get("excluded_sectors", {}).get("list", []))

    # ---------- 4. 分诊 + 校验 + 反闸 ----------
    print("[4/5] 分诊 / 校验 / 反闸 ...")
    b_pool, to_a, rejected = [], [], []
    for code in codes:
        q = quotes.get(code, {})
        pe, pb = num(q.get("pe_ratio")), num(q.get("pb_ratio"))
        cap = to_yi(q.get("total_market_cap"))
        recs = sorted(fin.get(code, []), key=lambda r: r.get("EndDate", ""), reverse=True)
        if not recs:
            rejected.append({"code": code, "name": name_of[code], "reason": "无财务数据"})
            continue
        latest = recs[0]
        torg, gross = entry_val[code]
        rev, rd = num(latest.get("OperatingRevenue")), num(latest.get("RAndD"))
        rd_ratio = (rd / rev * 100) if (rd is not None and rev) else None
        torg_now = num(latest.get("TORGrowRate"))
        gross_seq = [num(r.get("GrossIncomeRatio")) for r in recs[:3] if num(r.get("GrossIncomeRatio")) is not None]

        base = {"code": code, "name": name_of[code], "torg": torg, "gross": gross,
                "sector": smap.get(code, {}).get("sector", ""),
                "rd_ratio": round(rd_ratio, 1) if rd_ratio is not None else None,
                "cap_yi": cap, "pe": pe, "pb": pb,
                "period": latest.get("EndDate")}

        # 反闸
        if GATES.get("revenue_growth_negative") and torg_now is not None and torg_now < 0:
            rejected.append({**base, "reason": f"反闸·营收增速转负（{torg_now:.1f}%）"}); continue
        if GATES.get("gross_margin_decline_2q") and len(gross_seq) >= 3 and gross_seq[0] < gross_seq[1] < gross_seq[2]:
            rejected.append({**base, "reason": f"反闸·毛利率连续两季下滑（{gross_seq[2]:.1f}→{gross_seq[1]:.1f}→{gross_seq[0]:.1f}）"}); continue
        if GATES.get("pe_ttm_gt") and pe is not None and pe > GATES["pe_ttm_gt"]:
            rejected.append({**base, "reason": f"反闸·PE {pe:.0f} > {GATES['pe_ttm_gt']}"}); continue

        # 行业排除
        sec = smap.get(code, {}).get("sector", "")
        if sec in excl:
            rejected.append({**base, "sector": sec, "reason": f"行业排除（{sec} 属周期/金融）"}); continue

        # 本地校验
        if rd_ratio is None:
            rejected.append({**base, "sector": sec, "reason": "研发数据缺失，无法验证技术投入"}); continue
        if rd_ratio < LOCAL["rd_ratio_min"]:
            rejected.append({**base, "sector": sec, "reason": f"研发/营收 {rd_ratio:.1f}% < {LOCAL['rd_ratio_min']}%"}); continue
        if cap is None or cap < LOCAL["market_cap_min_yi"]:
            rejected.append({**base, "reason": f"市值 {cap if cap else '—'} 亿 < {LOCAL['market_cap_min_yi']} 亿"}); continue

        # 分诊：PE/PB 合格 → A 池
        a_ok = (pe is not None and 0 <= pe <= 80) and (pb is not None and pb <= 8)
        if a_ok and not CFG["species_classifier"]["A_trend_pool"].get("deduct_nonrecurring_loss_reject"):
            pass
        if a_ok:
            to_a.append({**base, "verdict": "PE/PB 合格 → 归 A 池（但仍需技术面四维≥3票）"})
        else:
            why = []
            if pe is None or pe < 0:
                why.append(f"PE {pe if pe is not None else '—'}（亏损）")
            elif pe > 80:
                why.append(f"PE {pe:.1f} > 80")
            if pb is not None and pb > 8:
                why.append(f"PB {pb:.2f} > 8")
            b_pool.append({**base, "moved_from": "PE/PB 不合格：" + "；".join(why)})

    result = {
        "date": day,
        "entry_expr": expr,
        "criteria": {"revenue_growth_min": ENTRY["revenue_growth_min"],
                     "gross_margin_min": ENTRY["gross_margin_min"],
                     "rd_ratio_min": LOCAL["rd_ratio_min"],
                     "market_cap_min_yi": LOCAL["market_cap_min_yi"]},
        "b_pool": sorted(b_pool, key=lambda x: -(x["torg"] or 0)),
        "assigned_to_a": to_a,
        "rejected": rejected,
        "stats": {"entry": len(codes), "b_pool": len(b_pool),
                  "assigned_to_a": len(to_a), "rejected": len(rejected)},
    }
    out = TMP / f"growth_pool_{day}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"[5/5] ✅ {out}")
    print(f"  入口 {len(codes)} 只 → B 池 {len(b_pool)} 只 ｜ 归 A {len(to_a)} 只 ｜ 反闸剔除 {len(rejected)} 只")
    print()
    print(f"  {'代码':<10}{'名称':<10}{'营收增速':>9}{'毛利':>7}{'研发占比':>9}{'市值亿':>8}{'PE':>9}")
    print("  " + "-" * 62)
    for p in result["b_pool"][:20]:
        pe_s = f"{p['pe']:.1f}" if p['pe'] is not None else "—"
        print(f"  {p['code']:<10}{p['name']:<10}{p['torg']:>8.1f}%{p['gross']:>6.1f}%"
              f"{(p['rd_ratio'] if p['rd_ratio'] is not None else 0):>8.1f}%{p['cap_yi'] or 0:>8.0f}{pe_s:>9}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
