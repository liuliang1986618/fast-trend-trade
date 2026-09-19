#!/usr/bin/env python3
"""情绪票池构建（只看版）· 市场情绪温度计 + 个股五角色 + 高危剔除。

方法论依据（config/settings.json → emotion_pool）：
  市场级五指标 —— 游资圈共识：连板高度 / 涨停家数 / 炸板率 / 连板溢价率 / 晋级率
  个股五角色   —— 游资圈共识：总龙 / 中军 / 卡位 / 补涨 / 跟风
  高危五类     —— 业内共识，其中 3 类现有数据可判

定位：**只看版**——结构化呈现 + 高风险标注，不产出买入信号。
产出：output/tmp/pools/emotion_pool_<date>.json（供日报渲染与台账追加）

数据源：westock-tool CLI（1.5.0）+ output/tmp/sector_map.json（板块成分映射）
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "output" / "tmp"
WT = "/Users/liuliang19/.workbuddy/plugins/cache/cb_teams_marketplace/finance-data/1.5.0/skills/westock-tool/scripts/index.js"
CFG = json.loads((ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
EP = CFG["emotion_pool"]



def data_day() -> str:
    """数据日期 = 台账最后一个快照日期。

    ⚠️ 不能用 datetime.date.today()：若在收盘后跨零点运行（如 9/19 凌晨跑 9/18 的数据），
    系统日期会与数据日期错位，导致产物文件名与台账不一致。
    """
    import json as _json
    try:
        h = _json.loads((ROOT / "output" / "ledger" / "history.json").read_text(encoding="utf-8"))
        d = (h.get("days") or [{}])[-1].get("date")
        if d:
            return d
    except Exception:
        pass
    import datetime as _dt
    return _dt.date.today().isoformat()

def parse_md(text: str):
    """解析 CLI 的 markdown 表 → (header, rows)。"""
    header, rows = None, []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if len(cells) == len(header):
            rows.append(cells)
    return header, rows


def cli(*args, timeout=120):
    r = subprocess.run(["node", WT, *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout)[:200])
    return r.stdout


def num(v, default=None):
    try:
        return float(str(v).replace(",", "").replace("%", "").replace("+", ""))
    except (ValueError, TypeError):
        return default


def to_yi(v):
    """市值统一转亿元。⚠️ westock quote 的 total_market_cap 单位为「元」，自动判断兼容。"""
    x = num(v)
    if x is None:
        return None
    return round(x / 1e8, 1) if x > 1e6 else round(x, 1)


def limit_up_pct(code: str) -> float:
    """涨停幅度：创业板/科创板 20%，主板 10%（ST 未单列）。"""
    if code.startswith(("sz30", "sh688")):
        return 20.0
    return 10.0


def load_sector_map() -> dict:
    p = TMP / "sector_map.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def fetch_quotes(codes: list) -> dict:
    """批量 quote（分批，避免单次过长）。只取计算所需字段。"""
    out = {}
    for i in range(0, len(codes), 25):
        batch = codes[i:i + 25]
        r = subprocess.run(["westock", "quote", ",".join(batch)],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print(f"  [warn] quote 批次失败 {batch[0]}: {(r.stderr or r.stdout)[:90]}")
            continue
        hdr, rows = parse_md(r.stdout)
        if not hdr:
            continue
        idx = {k: hdr.index(k) for k in
               ("code", "name", "price", "high", "prev_close", "change_percent",
                "turnover_rate", "range_pct", "pe_ratio", "pb_ratio",
                "total_market_cap", "chg_20d") if k in hdr}
        for r in rows:
            c = r[idx["code"]]
            out[c] = {k: r[v] for k, v in idx.items()}
    return out


def main() -> int:
    import datetime
    day = data_day()

    print("[1/5] 拉连板梯队 ...")
    hdr_lu, rows_lu = parse_md(cli("ranking", "limitup_days", "--limit", "80"))
    i_code, i_name, i_days = hdr_lu.index("代码"), hdr_lu.index("名称"), hdr_lu.index("LimitUpDays")
    boards = {}
    for r in rows_lu:
        boards[r[i_code]] = {"name": r[i_name], "boards": int(num(r[i_days], 0))}

    print("[2/5] 拉涨停池 ...")
    _, rows_zt = parse_md(cli("filter", "intersect([ChangePCT > 9.8])", "--limit", "300"))
    zt_codes, zt_name = [], {}
    for r in rows_zt:
        # filter 输出列：code,name,ClosePrice,ChangePCT（顺序随表达式略有不同，按名字定位）
        code = r[0]
        zt_codes.append(code)
        zt_name[code] = r[1] if len(r) > 1 else code
    all_codes = sorted(set(zt_codes) | set(boards.keys()))

    print(f"[3/5] 拉行情（{len(all_codes)} 只）...")
    quotes = fetch_quotes(all_codes)
    smap = load_sector_map()

    # 今日活跃主线（未退潮）+ 主线锚定板块
    hist = json.loads((ROOT / "output" / "ledger" / "history.json").read_text(encoding="utf-8"))
    today = hist["days"][-1]
    active_lines, retired_lines = [], []
    for m in today.get("mainlines", []):
        (retired_lines if "退潮" in str(m.get("stage", "")) else active_lines).append(m["name"])
    line_of_sector = {"半导体": "半导体", "元件(PCB)": "算力硬件", "通信设备": "算力硬件",
                      "光学光电子": "算力硬件", "航海装备": "航运船舶",
                      "种植业": "农业/粮食", "农产品加工": "农业/粮食"}

    print("[4/5] 计算温度计 / 角色 / 高危 ...")
    max_board = max((v["boards"] for v in boards.values()), default=0)
    max_board_name = next((v["name"] for v in boards.values() if v["boards"] == max_board), "—")
    near_pool = [c for c in zt_codes if c in quotes]
    sealed_n = sum(1 for c in near_pool if quotes[c].get("price") and
                   float(quotes[c]["price"]) >= float(quotes[c].get("prev_close") or 0) *
                   (1 + limit_up_pct(c) / 100) - 0.011)
    broken_rate = round((len(near_pool) - sealed_n) / len(near_pool), 3) if near_pool else None
    limitup_count = sealed_n          # 真封板家数（业内口径）

    th = EP["market_thermometer"]["stages"]
    stage, basis = "未知", ""
    if max_board <= th["冰点"]["max_board_max"] and limitup_count <= th["冰点"]["limitup_count_max"]:
        stage, basis = "冰点", f"连板高度 {max_board} ≤3 且 涨停家数 {limitup_count} <30"
    elif max_board >= th["主升"]["max_board_min"]:
        stage, basis = "主升", f"连板高度 {max_board} ≥6"
    elif th["发酵"]["max_board_range"][0] <= max_board <= th["发酵"]["max_board_range"][1]:
        stage, basis = "发酵", f"连板高度 {max_board} 落在 4~5 板 + 涨停家数 {limitup_count}"
    else:
        stage, basis = "发酵/退潮之间", f"连板高度 {max_board}、涨停家数 {limitup_count}（边界值，待本地校准）"

    hr = EP["high_risk_rules"]
    roles = EP["roles"]
    pool = []
    for code in sorted(all_codes, key=lambda c: (-boards.get(c, {}).get("boards", 0), c)):
        q = quotes.get(code, {})
        b = boards.get(code, {}).get("boards", 0)
        name = boards.get(code, {}).get("name") or q.get("name") or zt_name.get(code, code)
        cap = to_yi(q.get("total_market_cap")) or 0.0          # 亿元（自动单位判断）
        turn = num(q.get("turnover_rate")) or 0.0
        chg20 = num(q.get("chg_20d")) or 0.0
        chg = num(q.get("change_percent")) or 0.0
        prev, price = num(q.get("prev_close")) or 0.0, num(q.get("price")) or 0.0
        lim = limit_up_pct(code)
        zt_price = round(prev * (1 + lim / 100), 2) if prev else 0.0
        sealed = bool(zt_price) and price >= zt_price - 0.011      # 是否真封住涨停
        sec = smap.get(code, {}).get("sector", "")
        line = line_of_sector.get(sec, "")
        in_active_line = line in active_lines if line else False

        # ---- 五角色判定（只用可算项）----
        t_range = roles["总龙"]["turnover_range"]
        if (b == max_board and max_board >= roles["总龙"]["max_board_min"]
                and cap <= roles["总龙"]["market_cap_max_yi"]
                and t_range[0] <= turn <= t_range[1]):
            role = "总龙"
        elif b <= roles["补涨"]["max_board_max"] and line and line in retired_lines:
            role = "补涨"
        elif b <= 1 and line and line in active_lines:
            role = "跟风"
        elif b >= 2:
            role = "连板梯队"
        else:
            role = "首板"

        # ---- 高危剔除（3 类可判）----
        flags = []
        if 0 < cap < hr["庄股_小市值"]["market_cap_max_yi"]:
            small_cap_note = f"小市值 {cap:.0f}亿＜{hr['庄股_小市值']['market_cap_max_yi']}亿"
        r2 = hr["高位加速缩量"]
        if b >= r2["max_board_min"] and 0 < turn < r2["turnover_max"] and chg20 > r2["chg20d_min"]:
            flags.append(f"高位加速缩量（{b}板·换手{turn:.1f}%·20日{chg20:+.0f}%）")
        if b >= 2 and line and line in retired_lines:
            flags.append(f"主线退潮期连板（{line} 已退潮，属补涨扩散段）")
        notes = []
        if b <= 1 and not sec:
            notes.append("无板块归属（孤立涨停）")
        if 0 < cap < hr["庄股_小市值"]["market_cap_max_yi"]:
            notes.append(small_cap_note)

        # ---- 板块联动（业内等价于「共振」）----
        if not sec:
            link = "未归类"
        elif in_active_line:
            link = "板块联动·强"
        elif line:
            link = "板块联动·弱（主线已退潮）"
        else:
            link = "板块联动·无"

        pool.append({
            "code": code, "name": name, "boards": b,
            "role": role, "sector": sec or "未归类", "mainline": line or "—",
            "linkage": link,
            "close": num(q.get("price")), "chg_pct": chg,
            "turnover": turn, "market_cap_yi": round(cap, 1),
            "pe": num(q.get("pe_ratio")), "chg20": chg20,
            "sealed": sealed, "red_flags": flags, "notes": notes,
            "status": "禁碰" if flags else "观察",
        })

    result = {
        "date": day,
        "thermometer": {
            "max_board": max_board, "max_board_name": max_board_name,
            "limitup_count": limitup_count,
            "broken_rate": broken_rate, "premium": None, "promotion_rate": None,
            "stage": stage, "stage_basis": basis,
            "unavailable_note": "炸板率（无接口字段）/溢价率/晋级率（需跨日台账积累）暂缺，不臆造",
        },
        "active_lines": active_lines, "retired_lines": retired_lines,
        "pool": pool,
        "core": [p for p in pool if p["boards"] >= 2],
        "first_board": {"count": sum(1 for p in pool if p["boards"] <= 1),
                        "with_flags": sum(1 for p in pool if p["boards"] <= 1 and p["red_flags"])},
        "stats": {
            "总数": len(pool),
            "按角色": {r: sum(1 for p in pool if p["role"] == r)
                       for r in ("总龙", "连板梯队", "补涨", "跟风", "首板")},
            "有红旗": sum(1 for p in pool if p["red_flags"]),
        },
    }
    out = TMP / "pools" / f"emotion_pool_{day}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[5/5] ✅ {out}")
    print(f"  温度计：连板高度 {max_board}（{max_board_name}）｜涨停 {limitup_count} 家｜阶段 {stage}")
    print(f"  角色分布：{result['stats']['按角色']}｜红旗 {result['stats']['有红旗']} 只")
    print(f"  梯队（连板≥2）：{len(result['core'])} 只；首板 {result['first_board']['count']} 只（含红旗 {result['first_board']['with_flags']}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
