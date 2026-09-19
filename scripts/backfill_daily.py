#!/usr/bin/env python3
"""日报补跑工具：为缺失的交易日生成报告并补记台账。

背景（docs/automation-daily.md「二·补：补跑检查」）：
    收盘后客户端未运行时 15:30 调度不会触发；调度器自带的 12 小时补跑窗口若落在周末，
    会被"当天休市则结束"的规则跳过，导致该交易日日报永久缺失。本脚本用于事后补齐。

用法：
    python3 output/scripts/backfill_daily.py 2026-09-11
    python3 output/scripts/backfill_daily.py 2026-09-11 --dry-run

范围（诚实声明）：
    补跑覆盖**数据可确定性复现**的部分——漏斗计量、探测层/确认层名单、ETF 榜、连板梯队；
    主线判定（T1-T5）、蓄势形态精判、互证结论依赖模型判断，补跑版**明确标注"需人工复核"**，
    不臆造结论。台账只补记快照，**不重算后续日期的状态机**（避免与既有数据冲突）。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # <仓库根>/output
ROOT = os.path.dirname(BASE)
HIST = os.path.join(BASE, "ledger", "history.json")
DAILY = os.path.join(BASE, "daily")
WE = os.popen("ls -d ~/.workbuddy/plugins/cache/*/finance-data/*/skills/westock-tool/scripts/index.js 2>/dev/null").read().split()
WT = WE[-1] if WE else ""                                                    # westock-tool 入口

DISCLAIMER = ("免责声明：以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。"
              "市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，"
              "必要时咨询持牌专业机构。过往表现不预示未来收益。")

PROBE_EXPR = "intersect([Chg20D >= 0, Chg20D < 12, MainNetFlow5D > 0, TurnoverRate > 2, PE_TTM > 0])"
CONFIRM_EXPR = "intersect([Chg20D > 25, Chg20D < 60, PE_TTM > 0, PE_TTM < 50, TurnoverRate > 3])"


def run_wt(*args):
    """调用 westock-tool，返回 stdout（失败抛异常）。"""
    if not WT:
        raise RuntimeError("未找到 westock-tool 入口，请检查插件目录")
    r = subprocess.run(["node", WT] + list(args), capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout)[:300])
    return r.stdout


def parse_md(md):
    """解析 markdown 表格 → list[dict]（表头作键）。"""
    rows, header = [], None
    for line in md.splitlines():
        if not line.strip().startswith("|") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            header = cells
        elif len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    return rows


def fetch(day):
    """拉取目标交易日的四组数据。"""
    data = {}
    data["probe"] = parse_md(run_wt("filter", PROBE_EXPR, "--date", day,
                                    "--orderby", "MainNetFlow5D", "--desc", "--limit", "15"))
    data["confirm"] = parse_md(run_wt("filter", CONFIRM_EXPR, "--date", day,
                                      "--orderby", "Chg20D", "--desc", "--limit", "20"))
    data["etf"] = parse_md(run_wt("ranking", "qt_chg_interval", "--asset", "etf", "--date", day,
                                  "--orderby", "ChgPct20D", "--min-ChgPct20D", "8", "--limit", "20"))
    data["limitup"] = parse_md(run_wt("ranking", "limitup_days", "--date", day, "--limit", "10"))
    return data


def table(rows, cols, headers):
    """cols: [(显示名, dict键)]"""
    th = "".join("<th>%s</th>" % h for h in headers)
    body = []
    for r in rows:
        tds = "".join("<td>%s</td>" % (r.get(k, "—") or "—") for _, k in cols)
        body.append("<tr>%s</tr>" % tds)
    if not body:
        body.append('<tr><td colspan="%d" class="empty">（无数据）</td></tr>' % len(headers))
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (th, "".join(body))


def render(day, data):
    """生成补跑版日报 HTML。"""
    note = ('<p class="note">⚠️ <b>本报告为补跑版</b>：覆盖数据可确定性复现的部分。'
            '主线判定（T1-T5）、蓄势形态精判、互证结论需人工/模型复核，补跑不臆造结论。'
            '台账仅补记快照，未重算后续日期的状态机。</p>')
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>趋势候选日报（补跑）%s</title>
<style>
 body{font-family:-apple-system,"PingFang SC",sans-serif;background:#f7f9fc;color:#1c2333;margin:0;padding:28px;line-height:1.65}
 .wrap{max-width:980px;margin:0 auto}
 h1{font-size:21px;margin:0 0 4px;color:#1a3a6b}
 .meta{font-size:12px;color:#8a94a8;margin-bottom:18px}
 .card{background:#fff;border:1px solid #e4eaf2;border-radius:12px;padding:18px 20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(26,58,107,.05)}
 .card.b{border-left:5px solid #33559a}.card.g{border-left:5px solid #1e8449}
 h2{font-size:15px;margin:0 0 12px;color:#1a3a6b}
 table{width:100%%;border-collapse:collapse;font-size:12.5px}
 th{text-align:left;color:#8a94a8;font-weight:500;font-size:11px;padding:6px 8px;border-bottom:1px solid #eef2f8;background:#fafcfe}
 td{padding:6px 8px;border-bottom:1px solid #f4f7fb}
 td.empty{color:#b6c0cf;text-align:center}
 .note{font-size:11.5px;color:#8a94a8;margin-top:10px}
 .dsc{font-size:11.5px;color:#8a94a8;background:#fff;border:1px solid #e4eaf2;border-radius:10px;padding:14px 16px;margin-top:16px}
</style></head><body><div class="wrap">
<h1>趋势候选日报（补跑）· %s</h1>
<div class="meta">数据日期 %s（收盘口径）　｜　生成时间 %s　｜　补跑工具 output/scripts/backfill_daily.py</div>
%s
<div class="card b"><h2>① 选股漏斗计量 ＋ ③④ 主线与互证（补跑版）</h2>
<p class="note">探测层 %d 只 ｜ 确认层 %d 只 ｜ ETF 20日涨幅≥8%% 的 %d 只 ｜ 连板梯队 %d 只</p>
%s</div>
<div class="card b"><h2>⑤ 早期埋伏名单（探测层，前 15）</h2>%s</div>
<div class="card b"><h2>⑤ 主升名单候选（确认层，前 20）</h2>%s</div>
<div class="card g"><h2>⑥ ETF 反查榜（20 日涨幅 ≥8%%）</h2>%s</div>
<div class="card b"><h2>⑦ 连板梯队</h2>%s</div>
<div class="dsc">%s</div>
</div></body></html>
""" % (
        day, day, day, datetime.now().strftime("%Y-%m-%d %H:%M"), note,
        len(data["probe"]), len(data["confirm"]), len(data["etf"]), len(data["limitup"]),
        note,
        table(data["probe"], [("代码", "code"), ("名称", "name"), ("Chg20D", "Chg20D"),
                              ("最新价", "ClosePrice"), ("换手率", "TurnoverRate")],
              ["代码", "名称", "近20日涨幅", "最新价", "换手率"]),
        table(data["confirm"], [("代码", "code"), ("名称", "name"), ("Chg20D", "Chg20D"),
                                ("最新价", "ClosePrice"), ("PE_TTM", "PE_TTM")],
              ["代码", "名称", "近20日涨幅", "最新价", "市盈率"]),
        table(data["etf"], [("代码", "code"), ("名称", "name"), ("主题", "ChgPct20D")],
              ["代码", "名称", "近20日涨幅"]),
        table(data["limitup"], [("代码", "code"), ("名称", "name"), ("连板", "LimitUpDays")],
              ["代码", "名称", "连板数"]),
        DISCLAIMER,
    )


def update_history(day, data):
    """补记台账快照（按日期排序插入；不重算状态机）。"""
    d = json.load(open(HIST, encoding="utf-8"))
    dates = [x["date"] for x in d["days"]]
    if day in dates:
        return "台账已存在该日快照，跳过补记"
    snap = {
        "date": day,
        "funnel": {"probe": len(data["probe"]), "confirm": len(data["confirm"]),
                   "etf": len(data["etf"]), "backfilled": True},
        "mainlines": [],
        "watchlist": [{"name": r.get("name"), "code": r.get("code"),
                       "group": "补跑", "status": "未评分",
                       "close": r.get("ClosePrice"),
                       "note": "补跑快照：未重算状态机与评分"} for r in data["confirm"][:10]],
    }
    d["days"].append(snap)
    d["days"].sort(key=lambda x: x["date"])
    json.dump(d, open(HIST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return "台账已补记 %s 快照（days 现 %d 天）" % (day, len(d["days"]))


def main():
    ap = argparse.ArgumentParser(description="日报补跑工具")
    ap.add_argument("date", help="目标交易日 YYYY-MM-DD")
    ap.add_argument("--dry-run", action="store_true", help="只取数并打印统计，不写文件")
    args = ap.parse_args()
    day = args.date
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", day):
        print("❌ 日期格式应为 YYYY-MM-DD"); return 1

    print("[backfill] 拉取 %s 数据（收盘口径）..." % day)
    data = fetch(day)
    print("  探测层 %d ｜ 确认层 %d ｜ ETF %d ｜ 连板 %d"
          % (len(data["probe"]), len(data["confirm"]), len(data["etf"]), len(data["limitup"])))
    if args.dry_run:
        print("[backfill] --dry-run：不写文件"); return 0

    os.makedirs(DAILY, exist_ok=True)
    out = os.path.join(DAILY, "%s.html" % day)
    open(out, "w", encoding="utf-8").write(render(day, data))
    print("[backfill] ✅ 报告已落盘 %s" % out)
    print("[backfill] " + update_history(day, data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
