#!/usr/bin/env python3
"""A 池（稳做名单）五维评分规则化 —— 消除"手工打分"的不可复现性。

五维权重（手册口径）：
  1. 主线强度    25 分 —— 主线阶段权重（主升 1.0 / 刚起步 0.8 / 尾声 0.5 / 退潮 0）× 25
  2. 板块内地位  20 分 —— 个股主力5日净流入 ÷ 板块5日主力净流入 × 100（cap 20，板块资金强于个股才给分）
  3. 蓄势形态    25 分 —— 蓄势分 / 100 × 25（与 VCP 引擎同源）
  4. 资金验证    20 分 —— 全市场主力5日榜名次：前 50 → 20；前 300 → 12；前 1500 → 6；榜外 → 0
  5. 距买点      10 分 —— ≤2% → 10；≤5% → 7；≤10% → 4；>10% → 1；已触发 → 10

⚠️ 数据口径声明：资金维使用 `ranking cap_main_5d` 榜（与板块内地位同源）。
   已发现 `filter` 的 MainNetFlow5D 与该榜口径不同（如中天科技 filter 显示 16.86 亿、
   榜内前 1500 名查无）——两源差异原因待查，评分前必须明确单一来源。

用法：
  python3 output/scripts/score_stable.py          # 对当日 A 池打分并输出对比表
  python3 output/scripts/score_stable.py --json   # 输出 JSON（供台账/日报引用）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
TMP = ROOT / "output" / "tmp"
HIST = ROOT / "output" / "history.json"

STAGE_W = {"主升": 1.0, "刚起步": 0.8, "尾声": 0.5, "退潮": 0.0}
W = {"mainline": 25, "position": 20, "vcp": 25, "fund": 20, "dist": 10}

# 主线 → 板块映射（与 build_growth_pool 同口径）
LINE_OF_SECTOR = {
    "半导体": "半导体", "电子化学品Ⅱ": "半导体", "其他电子Ⅱ": "半导体",
    "元件(PCB)": "算力硬件", "通信设备": "算力硬件", "光学光电子": "算力硬件",
    "专用设备": "算力硬件", "计算机设备": "算力硬件",
    "航海装备": "航运船舶", "航运港口": "航运船舶", "物流": "航运船舶",
    "种植业": "农业/粮食", "农产品加工": "农业/粮食", "饲料": "农业/粮食",
    "养殖业": "农业/粮食", "农化制品": "农业/粮食",
}


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def load_cap_rank() -> dict:
    """读取全市场资金榜缓存（cap5d.md，由 westock_cli 生成）。"""
    p = TMP / "cap5d.md"
    if not p.exists():
        return {}
    import re
    rank = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (\d+) \| (\S+) \| (\S+) \|", line)
        if m:
            vals = [x.strip() for x in line.strip("|").split("|")]
            if len(vals) >= 9:
                rank[vals[1]] = {"rank": int(vals[0]), "sum5d_wan": num(vals[8])}
    return rank


def load_sector_flow() -> dict:
    """板块 5 日主力净流入（万元），来自 rotation.sector_check（当日人工体检）。"""
    h = json.loads(HIST.read_text(encoding="utf-8"))
    rot = h.get("rotation", {})
    sc = rot.get("sector_check")
    if isinstance(sc, dict):
        last = sc.get(sorted(sc.keys())[-1], []) if sc else []
    elif isinstance(sc, list):
        last = sc[-1].get("data", []) if sc else []
    else:
        last = []
    flow = {}
    for s in last:
        nm = s.get("sector", "")
        val = num(str(s.get("mainNetInflow5d", "")).replace("亿", "").replace("+", "").split("（")[0])
        if nm and val is not None:
            flow[nm] = val
    return flow


def main() -> int:
    out_json = "--json" in sys.argv
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import daily_run_20260918 as D

    day = D.DAY
    cap_rank = load_cap_rank()
    sector_flow = load_sector_flow()

    # 主线阶段（从当日主线体检取）
    stage_of_line = {}
    for m in D.MAINLINES:
        st = m["stage"].split("（")[0].split("（")[0].strip()
        for key in STAGE_W:
            if key in m["stage"]:
                stage_of_line[m["name"]] = key
                break

    print("=== A 池五维规则化评分（与手工分对照）===")
    print(f"{'标的':<10}{'手工分':>7}{'规则分':>7}{'主线':>6}{'地位':>6}{'蓄势':>6}{'资金':>6}{'距买点':>6}")
    print("-" * 58)

    results = []
    for code, name, manual, line, vcp_txt, reason, qual in D.STABLE_LIST:
        # 解析蓄势分
        try:
            vcp = float(vcp_txt.split()[0])
        except (ValueError, IndexError):
            vcp = None

        # 1. 主线强度
        stage = stage_of_line.get(line.split("（")[0].split("（")[0].strip(), "")
        # 从所属主线找 MAINLINES 的阶段
        for m in D.MAINLINES:
            if line[:2] in m["name"][:2] or m["name"][:2] in line[:2]:
                stage = m["stage"].split("（")[0].split("（")[0].strip()
                break
        s1 = round(STAGE_W.get(stage, 0) * W["mainline"], 1)

        # 2. 板块内地位（个股资金/板块资金，cap 20）
        rank_info = cap_rank.get(code, {})
        fund5d = (rank_info.get("sum5d_wan") or 0) / 10000          # 亿元
        sec = _sector_of(code, D)
        sec_flow = _sector_flow_val(sector_flow, sec)
        if sec_flow and sec_flow > 0:
            s2 = round(min(20, (fund5d / sec_flow) * 200), 1)
        else:
            s2 = round(min(20, fund5d * 2), 1)                      # 板块数据缺 → 按绝对值
        s2 = max(0, s2)

        # 3. 蓄势形态
        s3 = round(vcp / 100 * 25, 1) if vcp else 0

        # 4. 资金验证（榜名次分档）
        rk = rank_info.get("rank")
        if rk and rk <= 50:
            s4 = 20
        elif rk and rk <= 300:
            s4 = 12
        elif rk and rk <= 1500:
            s4 = 6
        else:
            s4 = 0

        # 5. 距买点
        # 从 VCP 表匹配距突破
        vcp_row = next((v for v in D.VCP if v[0] == code), None)
        dist = vcp_row[7] if vcp_row else None
        if vcp_row and vcp_row[3] == "已触发":
            s5 = 10
        elif dist is not None and dist <= 2:
            s5 = 10
        elif dist is not None and dist <= 5:
            s5 = 7
        elif dist is not None and dist <= 10:
            s5 = 4
        else:
            s5 = 1

        total = round(s1 + s2 + s3 + s4 + s5, 1)
        results.append({"code": code, "name": name, "manual": manual, "rule": total,
                        "detail": {"主线": s1, "地位": s2, "蓄势": s3, "资金": s4, "距买点": s5}})
        print(f"{name:<10}{manual:>7}{total:>7}{s1:>6}{s2:>6}{s3:>6}{s4:>6}{s5:>6}")

    print()
    print("⚠️ 数据口径：资金维使用 `ranking cap_main_5d` 榜（与板块内地位同源）。")
    print("   已发现 `filter` 的 MainNetFlow5D 与该榜口径不同，两源差异原因待查。")
    print("   阈值均为首版设定，跑 20 个交易日后按实际表现校准。")

    if out_json:
        out = TMP / "a_pool_scored.json"
        out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n✅ 已输出 {out}")
    return 0


def _sector_of(code, D):
    """从板块映射表查个股所属板块。"""
    import json
    p = TMP / "sector_map.json"
    if not p.exists():
        return ""
    m = json.loads(p.read_text(encoding="utf-8"))
    return m.get(code, {}).get("sector", "")


def _sector_flow_val(flow, sector):
    """从板块资金字典中查找（模糊匹配：板块名含关键字）。"""
    for k, v in flow.items():
        if k[:2] == sector[:2]:
            return v
    return None


if __name__ == "__main__":
    sys.exit(main())
