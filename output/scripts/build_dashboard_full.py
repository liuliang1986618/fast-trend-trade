#!/usr/bin/env python3
"""驾驶舱全量重建：读 output/history.json 渲染五区（词典/曲线两件套/轮动热力表/观察池/双向锚定）。
每天收盘后由自动化运行。曲线 SVG 纯静态，无 JS 图表库。"""
import json, os, datetime

# 本脚本固定位于 <仓库根>/output/scripts/ 下，故 BASE = 其父目录（output/）
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(BASE, "history.json")
OUT = os.path.join(BASE, "dashboard.html")

with open(HIST) as f:
    hist = json.load(f)
rot = hist["rotation"]
days = hist["days"]
today = days[-1]
prev = days[-2] if len(days) >= 2 else None
prev_watch = {w["code"]: w for w in prev["watchlist"]} if prev else {}
score_dates = rot["score_dates"]           # YYYY-MM-DD 全轴
idx_of = {d: i for i, d in enumerate(score_dates)}
N = len(score_dates)

LINE_COLORS = {"航运": "#2b5fad", "算力(PCB/光通信)": "#c0392b", "粮食": "#b8860b", "半导体": "#7b3fa0"}
_LINE_FALLBACK = "#7b3fa0"          # 新主线未登记颜色时的兜底，避免 KeyError 中断重建

# 兼容 Python 3.9+：f-string 表达式内禁止出现反斜杠（PEP 701 是 3.12+ 才放宽），
# 因此需要内嵌引号的片段一律预先定义成常量，勿在 {} 里写 \" 转义。
_TAG_WARN_OPEN = '<span class="tag warn">'
_TAG_CLOSE = '</span>'

# —— 跳转链接：每个标的可点击打开行情详情页（腾讯自选股，与 westock 生态一致）——
def to_full(code: str) -> str:
    """裸码/带前缀码 → 带市场前缀。"""
    c = (code or "").strip()
    if c.startswith(("sh", "sz", "bj")):
        return c
    c = c.zfill(6)
    return ("sh" if c.startswith(("6", "9")) else "sz") + c

def qlink(code: str, text: str, cls: str = "q") -> str:
    """生成可点击的行情详情链接；无 code 时返回纯文本。"""
    full = to_full(code)
    if not full:
        return text
    return '<a class="%s" href="https://gu.qq.com/%s" target="_blank" rel="noopener" title="打开 %s 行情详情">%s</a>' % (cls, full, full, text)
#粮食线从 partial 序列展开为 {date: score}
grain = dict(zip(rot["score_series_partial"]["粮食"]["dates"], rot["score_series_partial"]["粮食"]["scores"]))

# ---------------- SVG 工具 ----------------
def y_of(s): return round(380 - s * 3.4, 1)

def month_marks(dates):
    """返回 [(index, 'MM-DD')] 月首日"""
    marks = []
    for i, d in enumerate(dates):
        mm = d[5:7]
        if i == 0 or d[5:7] != dates[i-1][5:7]:
            marks.append((i, d[5:10]))
    return marks

def mondays(dates):
    return [i for i, d in enumerate(dates)
            if datetime.datetime.strptime(d, "%Y-%m-%d").weekday() == 0]

def build_series_points(dates_axis, d2s, x_of):
    pts = []
    for d, s in d2s.items():
        i = idx_of.get(d)
        if i is not None and s is not None:
            pts.append((i, s))
    pts.sort()
    return pts

def polyline(pts, x_of, color):
    p = " ".join(f"{x_of(i)},{y_of(s)}" for i, s in pts)
    return f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>'

def dots(pts, x_of, name):
    return "".join(f'<circle cx="{x_of(i)}" cy="{y_of(s)}" r="2.4" fill="{LINE_COLORS.get(name, _LINE_FALLBACK)}"><title>{score_dates[i]} {name} {s}</title></circle>'
                   for i, s in pts)

def alert_marks(x_of, ytop_scale=1):
    out = []
    for e in rot.get("alert_events", []):
        d = e["date"]
        full = f"2026-{d}" if len(d) == 5 else d
        i = idx_of.get(full)
        if i is None: continue
        x = x_of(i)
        if "✕" in e.get("level", "") or "降级" in e.get("level", ""):
            out.append(f'<circle cx="{x}" cy="{y_of(e.get("score",20))}" r="5" fill="none" stroke="#9aa3ad" stroke-width="2"/><text x="{x}" y="{y_of(e.get("score",20))-8}" font-size="10" fill="#9aa3ad" text-anchor="middle">✕</text><title>{d} 缩量骗炮(量比{e.get("vol_ratio")})</title>')
        elif e["level"].startswith("L2"):
            out.append(f'<circle cx="{x}" cy="{y_of(e.get("score",30))}" r="5" fill="{LINE_COLORS.get(e["line"],"#c0392b")}"/><text x="{x}" y="{y_of(e.get("score",30))-9}" font-size="11" fill="#c0392b" text-anchor="middle" font-weight="700">▲</text><title>{d} L2启动预警 Δ{e.get("delta")} 量比{e.get("vol_ratio")}</title>')
        else:
            out.append(f'<circle cx="{x}" cy="{y_of(e.get("score",30))}" r="5" fill="none" stroke="{LINE_COLORS.get(e["line"],"#2b5fad")}" stroke-width="2"/><text x="{x}" y="{y_of(e.get("score",30))-8}" font-size="10" fill="{LINE_COLORS.get(e["line"],"#2b5fad")}" text-anchor="middle">○</text><title>{d} L1放量关注</title>')
    return "".join(out)

def event_marks(x_of):
    out = []
    for line, evs in rot.get("score_events", {}).items():
        for e in evs:
            d = e["date"]
            full = f"2026-{d}" if len(d) == 5 else d
            i = idx_of.get(full)
            if i is None: continue
            x = x_of(i)
            color = LINE_COLORS.get(line, "#5b6472")
            out.append(f'<line x1="{x}" y1="46" x2="{x}" y2="380" stroke="{color}" stroke-dasharray="3,3" stroke-width="1" opacity="0.55"/><text x="{x+3}" y="42" font-size="10.5" fill="{color}" font-weight="600">{e["label"]}({line})</text>')
    return "".join(out)

def detail_svg():
    W = N * 13 + 92
    def x_of(i): return round(64 + i * 13 + 6, 1)
    parts = [f'<svg viewBox="0 0 {W} 420" style="width:{W}px;height:auto;background:#fff;" xmlns="http://www.w3.org/2000/svg">']
    parts.append(f'<text x="64" y="20" font-size="13" fill="#1a3a6b" font-weight="700">全历史细节 · 每日粒度（共{N}个交易日，横向滑动查看；鼠标悬停数据点看当日分数）</text>')
    # 参考线
    parts.append('<line x1="64" y1="76" x2="' + str(W-20) + '" y2="76" stroke="#c0392b" stroke-dasharray="5,4" stroke-width="1" opacity="0.5"/><text x="24" y="80" font-size="10" fill="#c0392b">60 主升</text>')
    parts.append('<line x1="64" y1="380" x2="' + str(W-20) + '" y2="380" stroke="#e3e7ee" stroke-width="1"/><text x="24" y="384" font-size="10" fill="#8a94a8">0</text>')
    # 周一竖线
    for i in mondays(score_dates):
        parts.append(f'<line x1="{x_of(i)}" y1="52" x2="{x_of(i)}" y2="380" stroke="#eef1f6" stroke-width="1"/>')
    # 月份分隔 + 标签
    for i, lab in month_marks(score_dates):
        x = x_of(i)
        parts.append(f'<line x1="{x-6}" y1="52" x2="{x-6}" y2="380" stroke="#c8d2e0" stroke-dasharray="4,4" stroke-width="1"/><text x="{x-4}" y="66" font-size="11" font-weight="700" fill="#1a3a6b">{lab}</text>')
    # 每日日号
    for i, d in enumerate(score_dates):
        parts.append(f'<text x="{x_of(i)}" y="398" font-size="8.5" fill="#a5adba" text-anchor="middle">{d[8:10]}</text>')
    # 各线
    for name, series in rot["score_series"].items():
        d2s = dict(zip(score_dates, series))
        pts = build_series_points(score_dates, d2s, x_of)
        parts.append(polyline(pts, x_of, LINE_COLORS.get(name, _LINE_FALLBACK)))
        parts.append(dots(pts, x_of, name))
    pts = build_series_points(score_dates, grain, x_of)
    parts.append(polyline(pts, x_of, LINE_COLORS.get("粮食", "#b8860b")))
    parts.append(dots(pts, x_of, "粮食"))
    parts.append(event_marks(x_of))
    parts.append(alert_marks(x_of))
    parts.append('</svg>')
    return "".join(parts)

def annual_svg():
    W = 1300
    x0, x1 = 46, 1270
    span = x1 - x0
    def x_of(i): return round(x0 + i * span / (N - 1), 1)
    parts = [f'<svg viewBox="0 0 {W} 420" style="width:100%;height:auto;background:#fff;" xmlns="http://www.w3.org/2000/svg">']
    parts.append(f'<text x="46" y="20" font-size="13" fill="#1a3a6b" font-weight="700">一年全貌 · 全部{N}个交易日缩放（每月首日刻度；看长周期叙事用）</text>')
    parts.append('<line x1="46" y1="76" x2="1270" y2="76" stroke="#c0392b" stroke-dasharray="5,4" stroke-width="1" opacity="0.5"/><text x="8" y="80" font-size="10" fill="#c0392b">60 主升</text>')
    parts.append('<line x1="46" y1="380" x2="1270" y2="380" stroke="#e3e7ee" stroke-width="1"/><text x="8" y="384" font-size="10" fill="#8a94a8">0</text>')
    for i, lab in month_marks(score_dates):
        x = x_of(i)
        parts.append(f'<line x1="{x}" y1="52" x2="{x}" y2="380" stroke="#c8d2e0" stroke-dasharray="4,4" stroke-width="1"/><text x="{x+2}" y="66" font-size="11" font-weight="700" fill="#1a3a6b">{lab}</text>')
    for name, series in rot["score_series"].items():
        d2s = dict(zip(score_dates, series))
        pts = build_series_points(score_dates, d2s, x_of)
        sw = 1.6 if len(pts) > 150 else 2
        parts.append(f'<polyline points="{" ".join(f"{x_of(i)},{y_of(s)}" for i, s in pts)}" fill="none" stroke="{LINE_COLORS.get(name, _LINE_FALLBACK)}" stroke-width="{sw}" stroke-linejoin="round"/>')
        parts.append(dots(pts, x_of, name))
    pts = build_series_points(score_dates, grain, x_of)
    parts.append(f'<polyline points="{" ".join(f"{x_of(i)},{y_of(s)}" for i, s in pts)}" fill="none" stroke="{LINE_COLORS.get("粮食", "#b8860b")}" stroke-width="1.6" stroke-linejoin="round"/>')
    parts.append(dots(pts, x_of, "粮食"))
    parts.append(event_marks(x_of))
    parts.append(alert_marks(x_of))
    # 长周期事件标注
    i_sh_gao = idx_of.get("2026-02-12")
    if i_sh_gao:
        parts.append(f'<text x="{x_of(i_sh_gao)+4}" y="{y_of(49.3)-10}" font-size="10.5" fill="#2b5fad">年初高位(49.3)</text>')
    i_g_start = idx_of.get("2026-06-15")
    if i_g_start:
        parts.append(f'<text x="{x_of(i_g_start)+4}" y="{y_of(7.5)-10}" font-size="10.5" fill="#b8860b">粮食ETF数据起点</text>')
    i_sh_hi = idx_of.get("2026-09-10")
    if i_sh_hi:
        parts.append(f'<text x="{x_of(i_sh_hi)-10}" y="{y_of(64.4)-10}" font-size="10.5" fill="#2b5fad" text-anchor="end">航运主升峰(64.4)</text>')
    parts.append('</svg>')
    return "".join(parts)

# ---------------- 区块渲染 ----------------
DICT = '<div class="tip"><b>名词小词典</b>：资金主线＝整个行业被大钱持续买入；涨停主线＝游资连板炒的；刚起步＝钱进了价没涨；主升＝钱价一起涨；尾声＝开始炒补涨股；退潮＝大钱在撤；互证＝股票和它的ETF同时涨（最强信号）；蓄势分＝"回调变浅+成交变少"的压弹簧评分（0~100，75以上快憋满）；突破价＝涨过它=真启动；认错价＝跌破它=看错了；稳做名单＝跟主线慢慢拿；快打名单＝情绪票快进快出。</div>'

legend = ('<div class="note">曲线怎么读：每条线是一条主线的"趋势强度分"（动量40%+均线30%+量能30%，锚定ETF日K计算，60分以上=主升区）。'
          '<b>预警标记怎么看</b>：○ 空心圆=放量关注(L1)；实心圆+▲=启动预警(L2)；灰空心圆+✕=缩量骗炮——'
          '<b>量价同涨才可信</b>，缩量涨价多为反弹噪音（历史验证：08-10量比0.77骗炮、09-07量比1.48真启动）。</div>')

trend_html = (f'<div class="rot"><h3>主线趋势强度曲线——两条线的交叉就是接力棒交接的时刻</h3>'
              f'<div id="trendScroll" style="overflow-x:auto;border:1px solid #e4eaf2;border-radius:8px;background:#fff;">{detail_svg()}</div>'
              f'<script>document.getElementById("trendScroll").scrollLeft=document.getElementById("trendScroll").scrollWidth;</script>'
              f'<div class="note">← 可左右滑动，最新在右侧</div>'
              f'<div style="margin-top:10px;border:1px solid #e4eaf2;border-radius:8px;background:#fff;">{annual_svg()}</div>'
              + legend +
              f'<div class="note">图例：' + "".join(f'<span style="color:{c};font-weight:600;margin-right:14px">— {n}</span>' for n, c in LINE_COLORS.items()) + '</div></div>')

# 轮动热力表
STAGE_CLS = {"启动":"c-启动","刚起步":"c-刚起步","主升":"c-主升","尾声":"c-尾声","退潮":"c-退潮","蓄势":"c-蓄势","埋伏":"c-埋伏","退出":"c-退出"}
heat_rows = []
for line in rot["lines"]:
    cells = []
    for d in rot["dates"]:
        st = line["stages"].get(d, "")
        cls = STAGE_CLS.get(st.replace("*", ""), "c-blank")
        cells.append(f'<td class="{cls}">{st.replace("*","") if st else "·"}</td>')
    heat_rows.append(f'<tr><td class="nm">{line["name"]}</td>{"".join(cells)}</tr>')
dates_head = "".join(f'<th>{d}</th>' for d in rot["dates"])

story = f'''<div class="story"><b>老主线怎么走完（农业/粮食）</b>：08-18 粮食ETF点火（+52分跳升）→ 08-19~09-07 主升（20日涨幅一度+20.4%）→ 09-08 尾声 → 09-10 退潮确认（中粮糖业天地板、梯队晋级失败）→ 09-14 退潮第3日（敦煌种业跌停-10%）→ <b>09-15 退潮第4日：种植业-4.65%（0/20上涨）、敦煌种业再跌停、粮食ETF 4连阴（今日-3.93%），20日涨幅滑落至-6.7%（今日口径），趋势强度分 38.4→30.4。彻底退场，只可龙头快打或不碰。</b><br>
<b>新主线怎么接棒（算力硬件·PCB/覆铜板）</b>：09-10 候补入册（探测层15席占12席，资金先行）→ 09-14 转正"刚起步"（元件5日145.4亿第1）→ <b>09-15 刚起步第2日：元件5日136.4亿维持第1、玻璃玻纤64.9亿第2；元件当日主力-17.6亿高位换手、玻璃玻纤当日+15.4亿接棒；板块内连板梯队仍在晋级（澳弘电子3板、双星新材3板、华正新材2连板涨停踩到突破价251.57）。但通信ETF方向闸仍未过（20日-8.0%、60日-27.4%深跌通道），且前十大权重无PCB股（锚定错配）——仍是"钱进了价没涨"，等ETF点火才有"主升·互证"。</b><br>
<b>航运船舶（刚起步第7日）预警亮牌</b>：09-11 主升降级回刚起步后，09-15 ETF资金通道确认「价涨钱走=衰竭预警」——船舶ETF当日净流出480万、份额月-6.0%/周-3.7%，与20日+4.3%的涨幅背离；板块资金第7（未转流出）暂保刚起步，份额续缩则降级退潮。<br>
<b>候补更替</b>：医疗服务候补一夜证伪（5日资金第11→第100）；新候补=<b>风电设备</b>（09-15 涨幅第2+5日资金第3+上涨家数80%，海力风电+12.84%）。<br>
<b>轮动规律一句话</b>：资金是搬家不是离场——农业退潮撤出的钱正趴在元件板块（5日136亿），并已开始试水风电设备。盯住老主线尾声时谁在蓄势，接力棒交接处（曲线交叉）就是布局窗口。</div>'''

heat_html = (f'<div class="rot"><h3>主线轮动时间线 · 阶段热力表（新日期在右；带*为ETF日K回溯推算）</h3>'
             f'<table><tr><th class="nm">主线</th>{dates_head}</tr>{"".join(heat_rows)}</table>{story}</div>')

# 观察池追踪台
STATUS_CLS = {"观察中":"p-blue","临近突破":"p-red","已触发":"p-green","已触及·等回踩":"p-orange","已失效":"p-gray"}
def pill(st): return f'<span class="pill {STATUS_CLS.get(st,"p-gray")}">{st}</span>'
def xushi_cell(sc):
    if sc is None: return '<span class="muted">—</span>'
    tag = "快憋满" if sc >= 75 else ("还在压" if sc >= 60 else "没形态")
    cls = "p-red" if sc >= 75 else ("p-blue" if sc >= 60 else "p-gray")
    return f'<b>{sc}</b> <span class="pill {cls}">{tag}</span>'
def dist_cell(v):
    if v is None: return '<span class="muted">—</span>'
    pct = max(0, min(100, 100 - v * 20))
    return f'<div class="bar-wrap"><div class="bar dg" style="width:{pct}%"></div></div><span class="muted">{v}%</span>'
rows = []
for w0 in today["watchlist"]:
    p = prev_watch.get(w0["code"])
    if p:
        ps = p.get("xushi")
        if ps is None and w0["xushi"] is None: d = "—"
        elif w0["xushi"] is None: d = "—"
        elif ps is None: d = '<span class="up">▲新</span>'
        else:
            dd = round(w0["xushi"] - ps, 1)
            d = f'<span class="up">▲ +{dd}</span>' if dd > 0 else (f'<span class="down">▼ {dd}</span>' if dd < 0 else "—")
    else:
        d = '<span class="up">新面孔</span>'
    seq = []
    for dd in days[-5:]:
        for ww in dd["watchlist"]:
            if ww["code"] == w0["code"] and ww.get("xushi") is not None:
                seq.append(ww["xushi"])
    bars = "".join(f'<div class="sp" style="height:{max(3,int(s/3))}px" title="{s}"></div>' for s in seq[-5:]) or '<span class="muted">—</span>'
    gate = ' <span class="pill p-gold">红线</span>' if "红线" in (w0.get("note") or "") else ""
    rows.append(f'<tr><td class="nm">{qlink(w0.get("code",""), w0["name"])}{gate}</td><td>{w0["first_seen"][5:]}</td><td class="num">{w0["days_in"]}</td>'
                f'<td>{pill(w0["status"])}</td><td>{xushi_cell(w0["xushi"])}</td><td>{dist_cell(w0["dist_to_break_pct"])}</td>'
                f'<td>{d}</td><td><div class="spark">{bars}</div></td><td class="muted">{w0["note"][:38]}…</td></tr>')
watch_html = (f'<div class="rot"><h3>观察池 · 跨日追踪台（收盘价口径推进 · 数据日期 {today["date"]}）</h3>'
              f'<table><tr><th>观察票</th><th>入池日</th><th>连续在榜</th><th>状态</th><th>今日蓄势分</th><th>距突破价</th><th>较上次</th><th>近5日</th><th>备注</th></tr>{"".join(rows)}</table></div>')

# 三段式双向锚定：第一段 ▶ 个股趋势→ETF 趋势；第二段 ◀ ETF 趋势→龙头个股；第三段 ⇄ 互证
f = today["funnel"]
chain = (f'<div class="chain">约 <b>{f.get("全市场约","—")}</b> 全市场 → <b>{f.get("站上所有均线","—")}</b> 站上所有主要均线 → '
         f'<b>{f.get("早期埋伏","—")}</b> 早期埋伏（大钱进了还没涨） → <b>{f.get("主升候选(剔小市值后)","—")}</b> 主升候选（合格{f.get("主升候选(市值≥100亿合格)","—")}） → '
         f'<b>{f.get("多头池资金强","—")}</b> 多头池×资金交叉 → <b>稳做 {f.get("稳做名单","—")}</b> ＋ <b>快打 {f.get("快打名单","—")}</b>'
         f'<span class="anchor-sub">（数据日期 {today["date"]}）</span></div>')
stable_rows = "".join(f'<tr><td class="nm">{qlink(s["code"], s["name"])}</td><td class="muted">{s["code"]}</td><td>{s["mainline"]}</td><td class="num"><b>{s["score"]}</b></td><td>{s["tier"]}</td><td class="muted">{s["reason"]}</td></tr>' for s in today["stable_list"])

# —— 第一段 ▶ 个股趋势 → ETF 趋势（正向通道）——
pos_card = (f'<div class="anchor-card pos"><div class="anchor-head"><span class="anchor-tag">第一段 ▶ 个股趋势 → ETF 趋势</span>'
            f'<span class="anchor-sub">自下而上：个股筛选汇聚成主线，再映射到 ETF 层（{today["date"]}）</span></div>'
            f'{chain}<table class="mini"><tr><th>稳做名单（按主线分组）</th><th>代码</th><th>所属主线</th><th>综合分</th><th>档位</th><th>要点</th></tr>{stable_rows}</table>')

# 主线 → 锚定 ETF 流向表（数据：cross_matrix + rotation.etf_flow_check）
flow_check = rot.get("etf_flow_check") or []
latest_fc = flow_check[-1] if flow_check else None
flow_rows = ""
for c in today["cross_matrix"]:
    fc = ""
    if latest_fc and latest_fc.get("mainline") == c["line"]:
        fc = latest_fc.get("quadrant", "")
    gate = '<span class="p-green">✅通过</span>' if c["overlap"] else '<span class="p-red">❌深跌</span>'
    flow_rows += (f'<tr><td class="nm">{c["line"]}（{c["stage"]}）</td><td class="arrow">→</td>'
                  f'<td class="etf">{c["etf_theme"]}</td><td>{c["etf_chg20d"]}</td><td>{gate}</td>'
                  f'<td><b>{fc or "—"}</b></td></tr>')
flow_tbl = (f'<h3 class="flow-h">主线 → 锚定 ETF 流向（个股趋势汇聚后，在 ETF 层的样子）</h3>'
            f'<table class="mini flowtbl"><tr><th>主线（阶段）</th><th></th><th>锚定 ETF</th><th>20日</th><th>方向闸</th><th>资金四象限</th></tr>{flow_rows}</table>'
            f'<div class="note">读法：回答「个股选出来的主线，ETF 层跟上了吗」——方向闸拦深跌反弹；资金四象限看钱进钱走（衰竭预警在此亮牌）。</div>')
pos_card += flow_tbl + '</div>'

# —— 第二段 ◀ ETF 趋势 → 龙头个股（反向通道）——
etf_rows = "".join(f'<tr><td>{i+1}</td><td class="nm">{qlink(e["code"], e["name"], "q etf")}</td><td class="muted">{e["code"]}</td><td>{e["theme"]}</td>'
                   f'<td><span class="bar" style="width:{min(e["chg20d"],20)/20*120:.0f}px"></span>{e["chg20d"]}%</td>'
                   f'<td>{e["overlap"] or "—"}</td><td>{(_TAG_WARN_OPEN + e["mark"] + _TAG_CLOSE) if e["mark"] else "—"}</td></tr>'
                   for i, e in enumerate(today["etf_reverse"]))
holdings = rot.get("etf_holdings") or []
h_rows = ""
for h in holdings[-3:]:
    tops = h.get("top3") or []
    tops_str = "｜".join(f'<b>{qlink(t.get("code",""), t.get("name",""))}</b> {t.get("ratio")}%（{t.get("chg_pct") or "—"}）' for t in tops)
    h_rows += f'<tr><td class="nm">{h.get("mainline")}</td><td class="arrow">→</td><td class="etf">{h.get("etf_code")}</td><td>{tops_str or "—"}</td></tr>'
reverse_tbl = (f'<h3 class="flow-h">重点 ETF → 龙头个股反查（前三大权重 + 当日涨跌）</h3>'
               f'<table class="mini flowtbl"><tr><th>主线</th><th></th><th>ETF</th><th>前三大权重（当日涨跌）</th></tr>{h_rows}</table>'
               if h_rows else '<div class="note">ETF 持仓快照待生成（rotation.etf_holdings，由每日自动化写入后显示）。</div>')
neg_card = (f'<div class="anchor-card neg"><div class="anchor-head"><span class="anchor-tag">第二段 ◀ ETF 趋势 → 龙头个股</span>'
            f'<span class="anchor-sub">自上而下：ETF 涨幅榜反查成分龙头</span></div>'
            f'<table class="mini"><tr><th>#</th><th>ETF</th><th>代码</th><th>主题</th><th>近20日涨幅</th><th>与主线重合</th><th>标记</th></tr>{etf_rows}</table>'
            f'{reverse_tbl}'
            f'<div class="note">重要信号：主题 ETF 热度收缩期，用「ETF → 龙头个股反查」看钱的去向——权重越高，ETF 资金流入对该股的被动买盘越大。</div></div>')

# —— 第三段 ⇄ 双向交叉验证 ——
cross_rows = "".join(f'<tr><td class="nm">{c["line"]}</td><td>{c["type"]}</td><td>{c["stage"]}</td><td>{c["etf_theme"]}({c["etf_chg20d"]})</td>'
                     f'<td>{"✓" if c["overlap"] else "✗"}×{"✓" if c["overlap"] else "✗"}</td><td class="muted">{c["conclusion"]}</td></tr>'
                     for c in today["cross_matrix"])
cross_card = (f'<div class="anchor-card cross"><div class="anchor-head"><span class="anchor-tag">第三段 ⇄ 双向交叉验证</span>'
              f'<span class="anchor-sub">两路结论互相印证（主线✓ × ETF✓，且通过方向闸）</span></div>'
              f'<table class="mini"><tr><th>主线</th><th>类型</th><th>今日阶段</th><th>对应ETF主题(20日涨幅)</th><th>重合</th><th>结论</th></tr>{cross_rows}</table>'
              f'<div class="quad"><div><b>主线✓ ETF✓</b>互证成功 · 最强信号</div><div><b>✗ ✓</b>值得期待 · 进观察名单</div><div><b>✓ ✗</b>成立但缺印证</div><div><b>✗ ✗</b>没信号</div></div>'
              f'<div class="note">交叉时叠加 ETF 资金通道（价×钱）：主线✓但资金通道为「价涨钱走」→ 互证结论打折扣；刚起步且「价跌钱进」→ 资金面支持，但须等方向闸解除才升级。今日无互证成功组合——指数环境档位：<b>谨慎</b>（主线锚定ETF普跌）。</div></div>')

# —— 第六区：形态分布 · 个股资格（v0.2 pattern_check；形态标签 ≠ 交易资格，两层合并输出）——
pc = rot.get("pattern_check") or []
pe = pc[-1] if pc else None
if pe:
    d_ = pe.get("dist", {})
    chips = " · ".join(f'{k} <b>{v}</b> 只' for k, v in d_.items() if v)
    rows_p = ""
    for s in pe.get("stocks", []):
        e = s.get("eligibility", "—")
        cls = "p-green" if e.startswith("✅") else ("p-gray" if e.startswith("观察") else "p-red")
        rows_p += (f'<tr><td class="nm">{qlink(s.get("code",""), s.get("name",""))}</td><td>{s.get("pattern","")}</td>'
                   f'<td class="num">{s.get("chg60d","—")}</td><td class="num">{s.get("chg20d","—")}</td>'
                   f'<td class="num">{s.get("chg5d","—")}</td><td class="num">{s.get("today","—")}</td>'
                   f'<td><span class="pill {cls}">{e}</span></td><td class="muted">{s.get("elig_note","")}</td></tr>')
    t1 = pe.get("t1_count_issue")
    pattern_card = (f'<div class="anchor-card" style="border-left:5px solid #8e44ad">'
        f'<div class="anchor-head"><span class="anchor-tag">形态分布 · 个股资格</span>'
        f'<span class="anchor-sub">形态标签（走势长什么样）≠ 交易资格（能不能做）· 两层合并输出 · {pe.get("date","")}</span></div>'
        f'<div class="chain">形态分布：{chips}　<span class="anchor-sub">（{pe.get("mainline","")}主线内逐票）</span></div>'
        f'<table class="mini"><tr><th>个股</th><th>形态</th><th>60日</th><th>20日</th><th>5日</th><th>今日</th><th>系统资格</th><th>依据</th></tr>{rows_p}</table>'
        + (f'<div class="tip">⚠️ <b>T1 计数复核</b>：{t1}</div>' if t1 else '')
        + f'<div class="note">{pe.get("note","")}</div></div>')
else:
    pattern_card = '<div class="note">形态分布数据待生成（rotation.pattern_check，由每日自动化写入）。</div>'

# ---- 三池分诊总览（v0.3）----
import json as _json
import os as _os
_day = today.get("date", "")
def _load_json(path):
    try:
        return _json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}
_gp = _load_json(_os.path.join(BASE, "tmp", f"growth_pool_{_day}.json")).get("b_pool", [])
_core = _load_json(_os.path.join(BASE, "tmp", f"emotion_pool_{_day}.json")).get("core", [])
_a_cnt = len(today.get("stable_list", []))
def _top(lst, n=4):
    names = []
    for x in lst[:n]:
        if isinstance(x, dict):
            names.append(x.get("name", ""))
        elif isinstance(x, (list, tuple)) and len(x) > 1:
            names.append(str(x[1]))
    return "、".join(n2 for n2 in names if n2) or "—"
def _gp_name(x):
    return x.get("name", "")
_clinic_rows = (
    f'<tr><td><span class="pill p-green">A 趋势池</span></td><td class="num">{_a_cnt}</td>'
    f'<td>PE∈[0,80] · PB≤8 · 扣非盈利</td><td>仓位≤20% · 让利润奔跑</td><td>{_top(today.get("stable_list", []))}</td></tr>'
    f'<tr><td><span class="pill p-orange">B 预期驱动池</span></td><td class="num">{len(_gp)}</td>'
    f'<td>营收≥30% · 毛利&gt;40% · 研发≥15%</td><td>仓位≤10% · 独立账本 · 止损-5%</td><td>{_top(_gp)}</td></tr>'
    f'<tr><td><span class="pill p-red">C 情绪池</span></td><td class="num">{len(_core)}</td>'
    f'<td>涨停/连板 · 换手&gt;15%</td><td>机动仓≤5% · 快进快出</td><td>{_top(_core)}</td></tr>')
clinic_card = (f'<div class="anchor-card" style="border-left:5px solid #EF9F27">'
    f'<div class="anchor-head"><span class="anchor-tag">物种分诊 · 三池总览</span>'
    f'<span class="anchor-sub">筛选与分类分离——同一批候选按物种分诊，各池独立纪律（{_day}）</span></div>'
    f'<table class="mini"><tr><th>池</th><th>数量</th><th>判据</th><th>纪律</th><th>代表标的</th></tr>{_clinic_rows}</table>'
    f'<div class="note">B 池买点状态四档：已触发（收盘站上突破价）｜临近突破（距突破价≤2%）｜'
    f'蓄势充分（形态憋满但离买点远）｜观察中。台账 pool_tracking 记录三池后续表现，20 交易日后数据裁决。</div></div>')

html = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>趋势观察驾驶舱 · 每日收盘后自动重建</title><style>
:root{{--ink:#1c2330;--sub:#5b6472;--line:#e3e7ee;--bg:#f7f8fa;--up:#d43a3a;--down:#1a9e6b;--blue:#2b5fad;--orange:#d97b1c;--gold:#b8860b}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);line-height:1.7;font-size:14.5px}}
.wrap{{max-width:1120px;margin:0 auto;padding:28px 20px 60px}}
h1{{font-size:22px}} h2{{font-size:18px;margin:28px 0 10px;padding-left:10px;border-left:4px solid var(--blue)}}
.meta{{color:var(--sub);font-size:13px;margin-top:4px}}
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
.rot{{background:#fff;border:1px solid #e4eaf2;border-radius:10px;padding:14px 16px;margin-top:14px;overflow-x:auto}}
.rot h3{{font-size:14px;margin-bottom:8px;color:#1a3a6b}}
.rot table{{border-collapse:collapse;font-size:10px}}
.rot th,.rot td{{border:1px solid #eef1f6;padding:3px 2px;text-align:center;min-width:34px}}
.rot th{{font-weight:500;color:#8a94a8;font-size:9.5px}}
.rot .nm{{min-width:86px;text-align:left;font-size:12px;font-weight:600;color:#1c2333;white-space:nowrap;padding-left:8px}}
.rot .c-启动{{background:#dbe6f5;color:#33559a;font-weight:600}} .rot .c-主升{{background:#fdecea;color:#c0392b;font-weight:700}}
.rot .c-尾声{{background:#fff3e0;color:#b26a00;font-weight:600}} .rot .c-退潮{{background:#e8f6ee;color:#1e8449;font-weight:700}}
.rot .c-蓄势{{background:#eef4fb;color:#5b7bb2}} .rot .c-刚起步{{background:#eef4fb;color:#33559a;font-weight:600}}
.rot .c-埋伏{{background:#f4f6fa;color:#7f8fb3}} .rot .c-退出{{background:#f0f1f3;color:#95a5a6}}
.rot .c-blank{{color:#d8dee8}}
a.q{{color:#2b5fad;text-decoration:none;border-bottom:1px dashed #b9c9e2;cursor:pointer}}
a.q:hover{{color:#c0392b;border-bottom-color:#c0392b}}
a.q::after{{content:"↗";font-size:9px;margin-left:2px;color:#8a94a8;vertical-align:top}}
a.q.etf{{color:#8e44ad;border-bottom-color:#d9c7ea}}
.rot .story{{font-size:12.5px;color:#4a5568;margin:8px 0 0;line-height:1.7}}
.anchor-card{{background:#fff;border:1px solid #e4eaf2;border-radius:12px;padding:18px 20px;margin-top:18px;box-shadow:0 1px 3px rgba(26,58,107,.05)}}
.anchor-card.pos{{border-left:5px solid #33559a}} .anchor-card.neg{{border-left:5px solid #1e8449}} .anchor-card.cross{{border-left:5px solid #c0392b}}
.anchor-head{{display:flex;align-items:baseline;gap:12px;margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid #eef2f8}}
.anchor-tag{{font-size:16px;font-weight:700;color:#1a3a6b}} .anchor-sub{{font-size:12px;color:#8a94a8}}
.chain{{font-size:12.5px;color:#4a5568;background:#f6f9fd;border:1px solid #e8eff8;border-radius:8px;padding:10px 12px;margin-bottom:14px;line-height:2.1}}
.chain b{{color:#1a3a6b;font-size:13.5px}}
.mini{{width:100%;border-collapse:collapse;font-size:12px}}
.mini th{{text-align:left;color:#8a94a8;font-weight:500;padding:6px 8px;border-bottom:1px solid #eef2f8;font-size:11px;background:#fafcfe}}
.mini td{{padding:7px 8px;border-bottom:1px solid #f4f7fb;color:#2c3446}}
.mini .nm{{font-weight:600;color:#1c2333}}
.tag{{font-size:10px;padding:1px 6px;border-radius:4px;display:inline-block}}
.tag.ok{{background:#e8f6ee;color:#1e8449;font-weight:600}} .tag.warn{{background:#fdecea;color:#c0392b;font-weight:600}}
.tag.gray{{background:#f0f1f3;color:#95a5a6}} .tag.blue{{background:#eef4fb;color:#33559a;font-weight:600}}
.quad{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:16px}}
.quad>div{{background:#fafcfe;border:1px solid #eef2f8;border-radius:8px;padding:11px 10px;font-size:11.5px;color:#4a5568;text-align:center;line-height:1.6}}
.quad b{{display:block;font-size:13px;color:#1a3a6b;margin-bottom:5px}}
</style></head><body><div class="wrap">
<h1>趋势观察驾驶舱</h1>
<div class="meta">最新快照：{today["date"]} 收盘 · 本页每天收盘后自动重建（由自动化流程从 output/history.json 渲染）</div>
{DICT}
<h2>主线趋势强度曲线</h2>
{trend_html}
<h2>主线轮动时间线</h2>
{heat_html}
<h2>观察池 · 跨日追踪台</h2>
{watch_html}
<h2>双向锚定 · 正反两路交叉验证</h2>
{pos_card}{neg_card}{cross_card}
{pattern_card}
{clinic_card}
</div></body></html>'''

with open(OUT, "w") as f2:
    f2.write(html)

# 快照交付机制：dashboard.html 是会被反复覆盖的"活文件"（预览面板对其存在缓存/覆盖窗口问题），
# 因此每次重建同时产出带日期戳的快照（output/snapshots/），**交付给人看的永远用快照文件**。
SNAP_DIR = os.path.join(BASE, "snapshots")
os.makedirs(SNAP_DIR, exist_ok=True)
SNAP = os.path.join(SNAP_DIR, "dashboard-%s.html" % today["date"])
with open(SNAP, "w", encoding="utf-8") as f3:
    f3.write(html)

# 同步落盘独立 SVG（细节长卷）
with open(os.path.join(BASE, "trend-lines.svg"), "w") as f3:
    f3.write(detail_svg().replace('<svg ', '<svg ', 1))
with open(os.path.join(BASE, "trend-lines-annual.svg"), "w") as f3:
    f3.write(annual_svg().replace('<svg ', '<svg ', 1))
print("dashboard.html 重建完成:", os.path.getsize(OUT), "bytes")
