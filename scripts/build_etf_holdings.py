#!/usr/bin/env python3
"""ETF 持仓反查（反向通道）—— 双来源策略。

⚠️ 数据来源说明（2026-09-18 实测）：
    ETF 实际持仓明细的两条通道**同时故障**：
      · MCP  data_etf(aspect=holdings) → 服务限频
      · CLI  index constituent <行业主题指数> → service error
    （CLI 仅支持「重要指数」如沪深300/科创50，不支持行业主题指数如 cs950125）
    故本脚本按可用性分层取数，并在输出中标注来源与精度：

    来源A（精确）：跟踪指数属「重要指数」→ westock index constituent
    来源B（近似）：其余 → 对应板块成分按市值排序取前 10
                   （行业主题 ETF 的选样通常按市值/流动性加权，
                     故板块市值前列与实际重仓方向高度重合，但非精确权重）

产出：output/tmp/etf_holdings_<date>.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import westock_cli as W  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "output" / "tmp"

# ETF → 数据来源定义
TARGETS = [
    ("sh588000", "科创50ETF华夏", "index", "sh000688"),
    ("sh560710", "船舶ETF富国", "sector", ["pt01801744", "pt01801992"]),
    ("sh515880", "通信ETF", "sector", ["pt01801102"]),
    ("sz159063", "粮食ETF南方", "sector", ["pt01801016", "pt01801012"]),
    ("sh512480", "半导体ETF国联安", "sector", ["pt01801081"]),
    ("sh588170", "科创半导体ETF华夏", "sector", ["pt01801081"], "688"),
]

TOP_N = 10



def data_day() -> str:
    """数据日期 = 台账最后一个快照日期。

    ⚠️ 不能用 datetime.date.today()：若在收盘后跨零点运行（如 9/19 凌晨跑 9/18 的数据），
    系统日期会与数据日期错位，导致产物文件名与台账不一致。
    """
    import json as _json
    try:
        h = _json.loads((ROOT / "output" / "history.json").read_text(encoding="utf-8"))
        d = (h.get("days") or [{}])[-1].get("date")
        if d:
            return d
    except Exception:
        pass
    import datetime as _dt
    return _dt.date.today().isoformat()

def main() -> int:
    import datetime
    day = data_day()
    out = []

    for tgt in TARGETS:
        etf_code, etf_name, kind, src = tgt[0], tgt[1], tgt[2], tgt[3]
        board_filter = tgt[4] if len(tgt) > 4 else None
        members = []
        try:
            if kind == "index":
                for m in W.parse_table(W._run(["westock", "index", "constituent", src, "--limit", "60"])):
                    members.append({"code": m["code"], "name": m["name"]})
                source_desc = f"精确·跟踪指数 {src}"
                precise = True
            else:
                seen = set()
                for sc in src:
                    for m in W.sector_members(sc):
                        if m["code"] not in seen:
                            seen.add(m["code"])
                            members.append({"code": m["code"], "name": m["name"]})
                # 交易板过滤（如科创半导体 ETF 只看 688）
                if board_filter:
                    members = [m for m in members if m["code"][2:].startswith(board_filter)]
                source_desc = ("近似·板块成分按市值排序（板块 " + "、".join(src) + "）"
                               + (f" + 仅 {board_filter} 板" if board_filter else ""))
                precise = False
        except Exception as e:
            out.append({"etf_code": etf_code, "etf_name": etf_name, "error": str(e)[:80]})
            continue

        # 补市值/涨跌并排序
        q = W.quote([m["code"] for m in members]) if members else {}
        for m in members:
            row = q.get(m["code"], {})
            m["cap_yi"] = W.to_yi(row.get("total_market_cap"))
            m["chg_pct"] = W.num(row.get("change_percent"))
            m["pe"] = W.num(row.get("pe_ratio"))
        members.sort(key=lambda x: -(x["cap_yi"] or 0))

        out.append({
            "etf_code": etf_code, "etf_name": etf_name,
            "source": "index" if precise else "sector_approx",
            "source_desc": source_desc, "precise": precise,
            "member_count": len(members),
            "top10": [{"code": m["code"], "name": m["name"], "cap_yi": m["cap_yi"],
                       "chg_pct": m["chg_pct"], "pe": m["pe"]} for m in members[:TOP_N]],
        })
        flag = "精确" if precise else "近似"
        print(f"  {etf_name:<20} [{flag}] {len(members)} 只 → 前3："
              + "、".join(m["name"] for m in members[:3]))

    result = {"date": day, "note": "ETF 实际持仓接口故障（MCP 限频 + CLI 不支持行业主题指数）；"
                                   "index 类为精确成分，sector_approx 类为板块市值前列近似",
              "holdings": out}
    p = TMP / f"etf_holdings_{day}.json"
    p.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✅ {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
