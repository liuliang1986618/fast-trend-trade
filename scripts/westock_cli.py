#!/usr/bin/env python3
"""CLI 数据通道封装 —— 统一走 westock CLI，规避 MCP 限频。

背景（2026-09-18 实测）：
    MCP 通道（mcp__westock-mcp__*）反复返回「服务限频」，
    而 CLI 通道（westock / westock-tool）当天全程顺畅。
    二者是独立接入路径，同一份数据在 CLI 侧完全可得且数值一致
    （实测：半导体 5 日主力净流入 2437776.21 万元 = 243.78 亿，与 MCP 分毫不差）。

本模块封装常用 CLI 调用，供各脚本复用：
    quote(codes)       行情快照（含 PE/PB/市值/涨跌/换手）
    kline(code)        日K（120 根）
    finance(codes)     利润表（营收/研发/毛利/增速，多期）
    sector_list()      全部板块清单（含资金/涨跌/上涨家数/龙头）
    sector_members(c)  单个板块成分股
    filter(expr)       条件选股（支持财务字段，如 TORGrowRate）
    ranking(metric)    排行榜

⚠️ 已知不可用：ETF/指数持仓明细 ——
    MCP data_etf(holdings) 限频、CLI index constituent 报 service error，
    两条通道同时故障，属上游服务问题，非通道选择问题。
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WT_TOOL = "/Users/liuliang19/.workbuddy/plugins/cache/cb_teams_marketplace/finance-data/1.5.0/skills/westock-tool/scripts/index.js"


def _run(args, timeout=180):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                       env={**__import__("os").environ, "PATH": __import__("os").environ.get("PATH", "") + ":" + str(Path.home() / ".local/bin")})
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:3])} → {(r.stderr or r.stdout)[:180]}")
    return r.stdout


def parse_table(text):
    """解析 markdown 表 → list[dict]（跳过标题/分隔行）。"""
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


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def to_yi(v):
    """市值统一转亿元（quote 的 total_market_cap 单位为「元」）。"""
    x = num(v)
    if x is None:
        return None
    return round(x / 1e8, 1) if x > 1e6 else round(x, 1)


# ---------------- 数据接口 ----------------
def quote(codes, batch=30):
    """行情快照。codes 可为 str 或 list。"""
    codes = [codes] if isinstance(codes, str) else list(codes)
    out = {}
    for i in range(0, len(codes), batch):
        for row in parse_table(_run(["westock", "quote", ",".join(codes[i:i + batch])])):
            out[row["code"]] = row
    return out


def kline(code, limit=120):
    return parse_table(_run(["westock", "kline", code, "--period", "day", "--limit", str(limit)]))


def finance(codes, limit=8, batch=25):
    codes = [codes] if isinstance(codes, str) else list(codes)
    out = {}
    for i in range(0, len(codes), batch):
        for row in parse_table(_run(["westock", "finance", ",".join(codes[i:i + batch]),
                                     "--type", "income", "--limit", str(limit), "--fields", "core"])):
            out.setdefault(row["code"], []).append(row)
    return out


def sector_list(kind="industry", sort_by="mainNetInflow5d", order="desc"):
    """全部板块清单（含资金/涨跌/上涨家数/龙头）。"""
    return parse_table(_run(["westock", "sector", "ranking", "--kind", kind,
                             "--type", sort_by, "--order", order]))


def sector_members(sector_code, limit=500):
    """单个板块成分股（替代 filter --universe）。"""
    return parse_table(_run(["westock", "sector", "constituent", sector_code, "--limit", str(limit)]))


def filter_stocks(expr, limit=200):
    return parse_table(_run(["node", WT_TOOL, "filter", expr, "--limit", str(limit)]))


def ranking(metric, limit=100, extra=None):
    args = ["node", WT_TOOL, "ranking", metric, "--limit", str(limit)]
    if extra:
        args += extra
    return parse_table(_run(args))


def build_sector_map(cache_path=None, verbose=True):
    """用 sector constituent 重建「个股 → 板块」全量映射。"""
    cache_path = Path(cache_path) if cache_path else ROOT / "output" / "tmp" / "sector_map.json"
    sectors = sector_list()
    mapping, stat = {}, []
    for i, s in enumerate(sectors, 1):
        code, name = s.get("code"), s.get("name")
        if not code:
            continue
        try:
            members = sector_members(code)
        except Exception as e:
            stat.append((name, f"失败：{str(e)[:40]}"))
            continue
        for m in members:
            mapping.setdefault(m["code"], {"sector": name, "name": m["name"]})
        stat.append((name, len(members)))
        if verbose and i % 20 == 0:
            print(f"    进度 {i}/{len(sectors)}：累计 {len(mapping)} 只")
    cache_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
    return mapping, stat


if __name__ == "__main__":
    print("=== 1. 板块清单 ===")
    secs = sector_list()
    print(f"  {len(secs)} 个板块")
    print("=== 2. 重建板块映射 ===")
    mp, stat = build_sector_map()
    ok = sum(1 for _, v in stat if isinstance(v, int))
    print(f"  ✅ 映射 {len(mp)} 只个股，覆盖 {ok}/{len(stat)} 个板块 → output/tmp/sector_map.json")
    if ok < len(stat):
        print("  失败板块：", [n for n, v in stat if not isinstance(v, int)][:6])
