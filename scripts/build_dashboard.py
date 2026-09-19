#!/usr/bin/env python3
"""驾驶舱重建脚本：读取 output/history.json，渲染跨日追踪台。每天收盘后由自动化运行。"""
import json, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(BASE, "ledger", "history.json")
OUT  = os.path.join(BASE, "dashboard.html")

with open(HIST) as f:
    hist = json.load(f)
days = hist["days"]
today = days[-1]
prev = days[-2] if len(days) >= 2 else None
prev_watch = {w["code"]: w for w in prev["watchlist"]} if prev else {}
prev_main = {m["name"]: m for m in prev["mainlines"]} if prev else {}

STATUS_CLS = {"观察中":"p-blue","临近突破":"p-red","已触发":"p-green","已触及·等回踩":"p-orange","已失效":"p-gray"}

def xushi_tag(score):
    if score is None: return '<span class="pill p-gray">没形态</span>'
    if score >= 75: return f'<b class="up">{score}</b> <span class="pill p-red">快憋满</span>'
    if score >= 60: return f'<b>{score}</b> <span class="pill p-blue">还在压</span>'
    return f'<b>{score}</b> <span class="pill p-gray">没形态</span>'

def delta(code, score):
    p = prev_watch.get(code)
    if not p: return '<span class="up">新面孔</span>' if score is not None else '<span class="up">新面孔</span>'
    ps = p.get("xushi")
    if ps is None or score is None:
        return "—" if ps == score else ("<span class='up'>▲</span>" if score else "—")
    d = round(score - ps, 1)
    if d > 0: return f'<span class="up">▲ +{d}</span>'
    if d < 0: return f'<span class="down">▼ {d}</span>'
    return "—（持平）"

def spark(code, cur_score):
    seq = []
    for d in days:
        for w in d["watchlist"]:
            if w["code"] == code and w.get("xushi") is not None:
                seq.append(w["xushi"])
    seq = seq[-4:] + ([cur_score] if cur_score is not None else [])
    if not seq: return '<span class="muted">无</span>'
    bars = "".join(f'<div class="sp" style="height:{max(3,int(s/3))}px" title="{s}"></div>' for s in seq)
    return f'<div class="spark">{bars}</div>'

def dist_bar(v):
    if v is None: return '<span class="muted">—</span>'
    pct = max(0, min(100, 100 - v * 20))  # 距突破价0%≈满条,5%≈0条
    return f'<div class="bar-wrap"><div class="bar dg" style="width:{pct}%"></div></div><span class="muted">{v}%</span>'

rows = []
for w in today["watchlist"]:
    code = w["code"]
    p = prev_watch.get(code)
    if p:
        st_chg = "" if p["status"] == w["status"] else f'<br><span class="muted">昨:{p["status"]}</span>'
        name_html = f'{w["name"]}'
    else:
        st_chg = '<br><span class="up">新入池</span>'
        name_html = f'{w["name"]}'
    rows.append(f'''<tr>
<td><b>{name_html}</b><br><span class="muted">{code}</span></td>
<td>{w["first_seen"]}</td><td class="num">{w["days_in"]}</td>
<td><span class="pill {STATUS_CLS.get(w["status"],"p-gray")}">{w["status"]}</span>{st_chg}</td>
<td>{xushi_tag(w.get("xushi"))}</td>
<td>{dist_bar(w.get("dist_to_break_pct"))}</td>
<td>{delta(code, w.get("xushi"))}</td>
<td>{spark(code, w.get("xushi"))}</td></tr>''')

# 主线轨迹
main_rows = []
for m in today["mainlines"]:
    p = prev_main.get(m["name"].replace("(候补未确认)",""))
    if p and p["stage"] != m["stage"]:
        arrow = f'<span class="up">▲ {p["stage"]}→{m["stage"]}</span>' if m["stage"] in ("主升","刚起步") and p["stage"]=="刚起步" else f'<span class="down">▼ {p["stage"]}→{m["stage"]}</span>'
    elif p:
        arrow = '<span class="muted">持平</span>'
    else:
        arrow = '<span class="up">新入册</span>'
    stage_cls = {"主升":"p-red","刚起步":"p-blue","尾声":"p-gold","退潮":"p-gray"}.get(m["stage"],"p-gray")
    main_rows.append(f'<tr><td><b>{m["name"]}</b></td><td>{m["type"]}</td><td class="num">{m["持续天数"]}</td><td><span class="pill {stage_cls}">{m["stage"]}</span></td><td>{arrow}</td></tr>')

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>趋势观察驾驶舱 · 每日收盘后自动重建</title>
<style>
:root{{--ink:#1c2330;--sub:#5b6472;--line:#e3e7ee;--bg:#f7f8fa;--up:#d43a3a;--down:#1a9e6b;--blue:#2b5fad;--orange:#d97b1c;--gold:#b8860b}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);line-height:1.7;font-size:14.5px}}
.wrap{{max-width:1120px;margin:0 auto;padding:28px 20px 60px}}
h1{{font-size:22px}} h2{{font-size:18px;margin:28px 0 10px;padding-left:10px;border-left:4px solid var(--blue)}}
.meta{{color:var(--sub);font-size:13px;margin-top:4px}}
.card{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-top:12px}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}}
th{{background:#eef2f7;padding:8px 10px;border-bottom:2px solid var(--line);text-align:left;white-space:nowrap}}
td{{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:middle}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.up{{color:var(--up);font-weight:600}} .down{{color:var(--down);font-weight:600}}
.pill{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}}
.p-blue{{background:#e8f0fe;color:var(--blue)}} .p-red{{background:#fdeaea;color:var(--up)}}
.p-green{{background:#e6f5ee;color:var(--down)}} .p-orange{{background:#fdf1e2;color:var(--orange)}}
.p-gray{{background:#eceff3;color:#6b7280}} .p-gold{{background:#fbf3dd;color:var(--gold)}}
.muted{{color:var(--sub);font-size:12px}}
.bar-wrap{{background:#eef2f7;border-radius:4px;height:12px;min-width:90px;position:relative}}
.bar{{height:12px;border-radius:4px}} .bar.dg{{background:linear-gradient(90deg,#e4a95a,#c07b30)}}
.spark{{display:flex;align-items:flex-end;gap:3px;height:36px}}
.spark .sp{{width:14px;border-radius:2px 2px 0 0;background:linear-gradient(180deg,#5a8de4,#2b5fad)}}
.note{{font-size:12.5px;color:var(--sub);margin-top:10px}}
.tip{{background:#fbfcfe;border:1px dashed #c8d2e0;border-radius:8px;padding:12px 16px;margin-top:12px;font-size:13px}}
</style></head><body><div class="wrap">
<h1>趋势观察驾驶舱</h1>
<div class="meta">最新快照：{today["date"]} 收盘 · 本页每天收盘后自动重建（由自动化流程从 output/history.json 渲染）</div>

<div class="tip"><b>怎么看这张追踪台</b>：连续多日在榜且蓄势分往上爬＝真在憋大招；闪进闪出＝噪音，不用理。<b>已触发</b>的票转入跟踪（跌破认错价才离场），<b>已失效</b>的票保留 5 天记录用于复盘胜率，然后移出。状态含义：<span class="pill p-blue">观察中</span> 默认 · <span class="pill p-red">临近突破</span> 分数够高或贴着突破价 · <span class="pill p-green">已触发</span> 收盘站上突破价 · <span class="pill p-orange">已触及·等回踩</span> 盘中摸过价但收盘没站稳 · <span class="pill p-gray">已失效</span> 跌破认错价看错了。</div>

<h2>观察池 · 跨日追踪台（共 {len(today["watchlist"])} 只）</h2>
<div class="card">
<table>
<tr><th>观察票</th><th>入池日</th><th class="num">连续在榜天数</th><th>状态</th><th>今日蓄势分＋档位</th><th>距突破价进度</th><th>较昨日</th><th>近5日蓄势分</th></tr>
{''.join(rows)}
</table>
<p class="note">蓄势分档位：≥75 快憋满（盯突破价）｜60~75 还在压（只观察）｜&lt;60 没形态（不配价格参数）。无分数的票保留状态行用于跨日跟踪。</p>
</div>

<h2>主线轨迹</h2>
<div class="card">
<table>
<tr><th>主线</th><th>类型</th><th class="num">已持续天数</th><th>今日阶段</th><th>较昨日</th></tr>
{''.join(main_rows)}
</table>
<p class="note">阶段升级（如 刚起步→主升）标红 ▲；转入退潮标绿 ▼。候补主线未确认成立，仅记录资金动向。</p>
</div>

<h2>当日漏斗与 ETF 热区</h2>
<div class="card">
<p><b>漏斗</b>：全市场约 {today["funnel"]["全市场约"]} → 站上所有均线 {today["funnel"]["站上所有均线"]} → 早期埋伏 {today["funnel"].get("早期埋伏","—")} → 主升候选(剔小市值) {today["funnel"].get("主升候选(剔小市值后)","—")} → <b>稳做 {today["funnel"]["稳做名单"]} / 快打 {today["funnel"]["快打名单"]}</b></p>
<p style="margin-top:8px"><b>ETF 20 日涨幅热区</b>（同一指数只留一只）：{' · '.join(today["etf_top"])}</p>
<p class="note">明细见当日日报 <code>output/daily/{today["date"]}.html</code>。</p>
</div>
</div></body></html>'''

with open(OUT, "w") as f:
    f.write(html)
print("dashboard.html 已重建:", OUT)
