#!/usr/bin/env python3
"""每日主循环 · v0.2 最小闭环（路线图 §7 第③步）

范围（最小闭环）：
    正向漏斗（探测层 + 确认层）→ 反向漏斗（ETF 20 日涨幅榜）→ 日报 HTML

明确不含（由 WorkBuddy 每日自动化负责，见 docs/automation-daily.md）：
    主线判定（T1-T4）/ 互证矩阵 / 蓄势形态精判 / 观察池状态机 / 驾驶舱 / 台账维护

设计约定（src/README.md）：
    - 全部阈值从 config/settings.json 读取，代码内不出现魔法数字
    - 数据访问只经 DataProvider 接口，禁止直接 import 某个 provider
    - 中间层只输出数量（漏斗计量），名单只出终产物 + 探测层头部

用法：
    python3 src/run_daily.py                    # 落盘 output/daily-run/YYYY-MM-DD.html
    python3 src/run_daily.py --dry-run          # 只打印统计，不写文件
    python3 src/run_daily.py --out /tmp/x.html  # 指定输出路径
"""
import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config                        # noqa: E402
from providers.resolver import resolve_provider, ProviderUnavailable  # noqa: E402

# 免责声明固定文案（与每日自动化保持一致，不得改写）
DISCLAIMER = (
    "免责声明：以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。"
    "市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，"
    "必要时咨询持牌专业机构。过往表现不预示未来收益。"
)

# 字段归一化：CLI 输出表头中英混用（filter 英文 / ranking 中文），统一成内部键名
KEYMAP = {
    "code": "code", "代码": "code",
    "name": "name", "名称": "name",
    "Chg20D": "chg20d", "ChgPct20D": "chg20d", "近20日涨幅": "chg20d", "涨幅": "chg20d",
    "ClosePrice": "close", "最新价": "close", "收盘": "close",
    "ChangePCT": "chg_pct", "涨跌幅": "chg_pct",
    "PE_TTM": "pe_ttm", "市盈率": "pe_ttm",
    "PB": "pb", "市净率": "pb",
    "MainNetFlow5D": "main_net_flow_5d", "MainSum5d": "main_net_flow_5d",
    "TurnoverRate": "turnover_rate", "换手率": "turnover_rate",
    "scale_yi": "scale_yi", "规模": "scale_yi", "资产净值": "scale_yi",
}


def norm(row: dict) -> dict:
    """把一行原始 dict 的键名归一化；未知键保留原名。"""
    return {KEYMAP.get(k, k): v for k, v in row.items()}


def _num(v, default=None):
    """容错取数值：兼容 '1,234.5' / '+3.2%' / '12.4亿' 等写法。"""
    if v is None:
        return default
    s = str(v).replace(",", "").replace("%", "").replace("+", "").strip()
    try:
        return float(s)
    except ValueError:
        return default


def run_forward_funnel(provider, cfg: dict) -> dict:
    """正向漏斗：探测层（早期埋伏）+ 确认层（主升候选）。"""
    f = cfg["funnel"]
    p, c = f["probe"], f["confirm"]
    probe_expr = {
        "chg20d_min": p.get("chg20d_min", 0), "chg20d_max": p.get("chg20d_max", 12),
        "main_net_flow_5d_min": p.get("main_net_flow_5d_min", 0),
        "turnover_rate_min": p.get("turnover_rate_min", 2),
        "pe_ttm_min": p.get("pe_ttm_min", 0),
        "limit": p.get("limit", 15),
    }
    confirm_expr = {
        "chg20d_min": c.get("chg20d_min", 25), "chg20d_max": c.get("chg20d_max", 60),
        "pe_ttm_min": c.get("pe_ttm_min", 0), "pe_ttm_max": c.get("pe_ttm_max", 50),
        "turnover_rate_min": c.get("turnover_rate_min", 3),
        "limit": c.get("limit", 20),
    }
    probe = [norm(r) for r in provider.screen(probe_expr)]
    confirm = [norm(r) for r in provider.screen(confirm_expr)]
    # 市值闸在接口侧可能不生效 → 此处仅标注，不做本地剔除（避免与自动化口径不一致）
    return {"probe": probe, "confirm": confirm}


def run_reverse_funnel(provider, cfg: dict) -> list:
    """反向漏斗：ETF 20 日涨幅榜（按配置阈值过滤 + 排序）。"""
    e = cfg.get("etf_funnel", {})
    rows = [norm(r) for r in provider.etf_rank(metric="chg20d", limit=e.get("top_n", 40) * 2)]
    lo = e.get("chg20d_min", 8)
    kept = []
    for r in rows:
        chg = _num(r.get("chg20d"))
        if chg is not None and chg >= lo:
            r["_chg20d"] = chg
            kept.append(r)
    kept.sort(key=lambda x: -x["_chg20d"])
    return kept[: e.get("top_n", 10)]


def render_html(day: str, provider_name: str, fwd: dict, rev: list) -> str:
    """浅底深字研报风 HTML（纯 CSS，无 JS、无图表库）。"""
    def row_html(r, cols):
        tds = []
        for key, fmt in cols:
            v = r.get(key, "")
            if callable(fmt):
                v = fmt(v)
            tds.append(f"<td>{v}</td>")
        return "<tr>" + "".join(tds) + "</tr>"

    def table(rows, headers, cols):
        th = "".join(f"<th>{h}</th>" for h in headers)
        body = "".join(row_html(r, cols) for r in rows) or \
            f'<tr><td colspan="{len(headers)}" class="empty">（无符合条件的标的）</td></tr>'
        return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"

    pct = lambda v: f"{_num(v, 0):+.2f}%"          # noqa: E731
    num1 = lambda v: (f"{_num(v):.1f}" if _num(v) is not None else "—")  # noqa: E731

    t_probe = table(
        fwd["probe"], ["代码", "名称", "近20日涨幅", "最新价", "换手率"],
        [("code", str), ("name", str), ("chg20d", pct), ("close", str), ("turnover_rate", str)],
    )
    t_confirm = table(
        fwd["confirm"], ["代码", "名称", "近20日涨幅", "最新价", "市盈率"],
        [("code", str), ("name", str), ("chg20d", pct), ("close", str), ("pe_ttm", num1)],
    )
    t_etf = table(
        rev, ["#", "代码", "名称", "近20日涨幅"],
        [("code", str), ("name", str), ("_chg20d", lambda v: f"<b>{v:+.2f}%</b>")],
    )
    # ETF 表补序号列（简单后处理）
    idx = 0
    out_rows = []
    for line in t_etf.split("<tr>"):
        if line.startswith("<td>"):
            idx += 1
            line = f"<td>{idx}</td>" + line
        out_rows.append(line)
    t_etf = "<tr>".join(out_rows)

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>趋势候选日报（run_daily）{day}</title>
<style>
  body{{font-family:-apple-system,"PingFang SC","Helvetica Neue",sans-serif;background:#f7f9fc;color:#1c2333;
       margin:0;padding:28px;line-height:1.65}}
  .wrap{{max-width:960px;margin:0 auto}}
  h1{{font-size:21px;margin:0 0 4px;color:#1a3a6b}}
  .meta{{font-size:12px;color:#8a94a8;margin-bottom:18px}}
  .card{{background:#fff;border:1px solid #e4eaf2;border-radius:12px;padding:18px 20px;margin-bottom:16px;
        box-shadow:0 1px 3px rgba(26,58,107,.05)}}
  .card.pos{{border-left:5px solid #33559a}}
  .card.neg{{border-left:5px solid #1e8449}}
  h2{{font-size:15px;margin:0 0 12px;color:#1a3a6b}}
  .sub{{font-size:12px;color:#8a94a8;font-weight:400}}
  table{{width:100%;border-collapse:collapse;font-size:12.5px}}
  th{{text-align:left;color:#8a94a8;font-weight:500;font-size:11px;padding:6px 8px;
     border-bottom:1px solid #eef2f8;background:#fafcfe}}
  td{{padding:7px 8px;border-bottom:1px solid #f4f7fb}}
  td.empty{{color:#b6c0cf;text-align:center;padding:14px}}
  .note{{font-size:11.5px;color:#8a94a8;margin-top:10px}}
  .dsc{{font-size:11.5px;color:#8a94a8;background:#fff;border:1px solid #e4eaf2;border-radius:10px;
       padding:14px 16px;margin-top:16px}}
</style></head>
<body><div class="wrap">
  <h1>趋势候选日报 · run_daily 最小闭环</h1>
  <div class="meta">数据日期 {day}　｜　数据来源 {provider_name}　｜　生成时间 {datetime.now():%Y-%m-%d %H:%M}</div>

  <div class="card pos">
    <h2>▶ 正向漏斗 · 个股方向 <span class="sub">探测层 {len(fwd['probe'])} 只 ｜ 确认层 {len(fwd['confirm'])} 只</span></h2>
    <p class="note">早期埋伏名单（大钱进了还没涨，探测层口径 chg20d {load_note(cfg_cache, 'probe')}）</p>
    {t_probe}
    <p class="note" style="margin-top:14px">主升名单候选（确认层口径 chg20d {load_note(cfg_cache, 'confirm')}；市值闸需接口侧生效，本脚本不做本地剔除）</p>
    {t_confirm}
  </div>

  <div class="card neg">
    <h2>◀ 反向漏斗 · ETF 方向 <span class="sub">近 20 日涨幅 ≥{load_note(cfg_cache, 'etf')}%，共 {len(rev)} 只</span></h2>
    {t_etf}
    <p class="note">反向漏斗的作用：从「涨得动的 ETF」反查它的成分股主题，比只看个股涨幅更早发现主线。</p>
  </div>

  <div class="dsc">{DISCLAIMER}</div>
</div></body></html>
"""


# 渲染时读取的配置（供区间文案使用；在 main 中填充）
cfg_cache: dict = {}


def load_note(cfg: dict, kind: str) -> str:
    f = cfg.get("funnel", {})
    if kind == "probe":
        return f"[{f.get('probe', {}).get('chg20d_min', 0)}, {f.get('probe', {}).get('chg20d_max', 12)}]"
    if kind == "confirm":
        return f"[{f.get('confirm', {}).get('chg20d_min', 25)}, {f.get('confirm', {}).get('chg20d_max', 60)}]"
    return str(cfg.get("etf_funnel", {}).get("chg20d_min", 8))


def main() -> int:
    ap = argparse.ArgumentParser(description="每日主循环 · v0.2 最小闭环")
    ap.add_argument("--config", default=str(ROOT / "config" / "settings.json"))
    ap.add_argument("--dry-run", action="store_true", help="只打印统计，不写文件")
    ap.add_argument("--out", default=None, help="输出 HTML 路径（默认 output/daily-run/YYYY-MM-DD.html）")
    args = ap.parse_args()

    global cfg_cache
    cfg = load_config()
    cfg_cache = cfg

    try:
        provider, notes = resolve_provider(cfg)
    except ProviderUnavailable as e:
        print("❌ 数据源不可用：", e)
        return 1
    print(f"[run_daily] 数据源 = {provider.name}（{' → '.join(notes)}）")

    print("[run_daily] 正向漏斗（探测层 + 确认层）...")
    fwd = run_forward_funnel(provider, cfg)
    print(f"  探测层 {len(fwd['probe'])} 只 ｜ 确认层 {len(fwd['confirm'])} 只")

    print("[run_daily] 反向漏斗（ETF 20 日涨幅榜）...")
    rev = run_reverse_funnel(provider, cfg)
    print(f"  ETF 上榜 {len(rev)} 只")

    day = date.today().isoformat()
    if args.dry_run:
        print("[run_daily] --dry-run：不写文件。样例：")
        for r in fwd["probe"][:3]:
            print("   probe  ", r.get("code"), r.get("name"), r.get("chg20d"))
        for r in rev[:3]:
            print("   etf    ", r.get("code"), r.get("name"), r.get("_chg20d"))
        return 0

    html = render_html(day, provider.name, fwd, rev)
    out = Path(args.out) if args.out else (ROOT / "output" / "daily-run" / f"{day}.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"[run_daily] ✅ 已落盘 {out}（{len(html)} 字符）")
    print("[run_daily] 提示：本脚本产物与 WorkBuddy 每日自动化分离，互不覆盖。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
