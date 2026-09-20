#!/usr/bin/env python3
"""日报四层架构版（v3）：全局天气层 / 汇合层 / 双通道 / 时间层。

架构依据（用户 2026-09-18 提出的方向）：
  项目骨架本是「双向锚定」——正向漏斗（个股→主线）× 反向漏斗（ETF→成分股），
  互证矩阵是两者的交点；情绪不属于任何一侧，它是「天气」。
  因此按「方向」组织，而不是按「内容类型」组织。

四层归属：
  ① 全局天气层（固定）  —— 情绪温度计 + 今日该看哪本账
  ② 汇合层（固定）      —— 互证矩阵（正向 × 反向 的交点＝今天有没有机会）
  ③ 双通道（滚动区）    —— 正向 ▶ ｜ 反向 ◀ ｜ 情绪 ⊙（三列各自独立滚动）
  ④ 时间层              —— 观察池跨日（左列底）+ 情绪梯队跨日（右列底）

数据来源：复用 daily_run_20260918.py 的当日数据常量 + emotion_pool JSON。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))

import daily_run_20260918 as D                      # noqa: E402  当日数据常量
from emotion_section import CSS as EMO_CSS, render_guide  # noqa: E402
from emotion_parts import CSS_EXTRA, render_thermometer, render_tier_list  # noqa: E402

# ——— 兼容 Python 3.9+：f-string 表达式内禁止反斜杠转义（PEP 701 属 3.12+），
#     需内嵌引号的 HTML 片段一律预先定义为模块常量。修复：2026-09-20 冒烟测试抓获。
_GATE_OK = '<span class="gate-ok">✅ 过闸</span>'
_GATE_NO = '<span class="gate-no">❌ 深跌</span>'
_B_EMPTY = '<tr><td colspan=9 class="muted">（今日无）</td></tr>'


DAY = D.DAY
OUT = ROOT / "output" / "daily" / DAY / "index.html"
EP = ROOT / "output" / "daily" / DAY / "data" / "emotion_pool.json"

# 反向通道：主线锚定 ETF 实测数据（09-18；资金字段当日未出）
ETF_ANCHORS = [
    ("sh560710", "船舶ETF富国", "航运船舶", "+8.26%", "+6.45%", True, 15.65),
    ("sh515880", "通信ETF", "算力硬件", "+3.31%", "-27.18%", False, 433.98),
    ("sz159063", "粮食ETF南方", "农业/粮食", "+1.14%", "+10.64%", True, 0.59),
    ("sh512480", "半导体ETF国联安", "半导体", "-3.66%", "-27.83%", False, 198.90),
]
SECTOR_LINK = [   # 板块联动（正向主线 × 板块资金方向）
    ("半导体", "+243.78 亿（第 1）", "177/181（98%）", "强", "新晋资金主线·刚起步"),
    ("通信设备（光通信侧）", "+49.76 亿（第 2）", "73/85（86%）", "中", "算力主线内部仍强的一侧"),
    ("元件（PCB 侧）", "-67.84 亿（转净流出）", "43/61（70%）", "弱", "算力主线的走弱侧"),
    ("航海装备", "-19.64 亿（净流出）", "9/10（90%）", "弱", "航运主线·退潮"),
    ("种植业", "-13.90 亿（净流出）", "9/20（45%）", "弱", "粮食主线·退潮第 7 日"),
]


def _render_etf_holdings() -> str:
    """ETF → 龙头个股反查表（读 build_etf_holdings.py 产出）。"""
    p = ROOT / "output" / "daily" / DAY / "data" / "etf_holdings.json"
    if not p.exists():
        return '<p class="muted">ETF 持仓数据未生成。</p>'
    d = json.loads(p.read_text(encoding="utf-8"))
    rows = ""
    for h in d.get("holdings", []):
        if h.get("error"):
            rows += (f'<tr><td>{H_(h["etf_name"])}</td><td colspan="2" class="muted">取数失败：{H_(h["error"])}</td></tr>')
            continue
        tag = ('<span class="prec-yes">精确</span>' if h.get("precise")
               else '<span class="prec-approx">近似</span>')
        tops = "　".join(
            f'{link(t["code"], t["name"])}<span class="muted">({t["cap_yi"]:.0f}亿)</span>'
            for t in h.get("top10", [])[:3] if t.get("cap_yi"))
        rows += (f'<tr><td>{link(h["etf_code"], h["etf_name"])}</td><td>{tag}</td>'
                 f'<td>{tops or "—"}</td></tr>')
    return ('<table class="etfh"><thead><tr><th>ETF</th><th>来源</th>'
            '<th>前三大权重（市值）</th></tr></thead><tbody>' + rows + '</tbody></table>')


def card(title, body, cls="", sub=""):
    sub_html = f'<span class="card-sub">{sub}</span>' if sub else ""
    return (f'<div class="card {cls}"><h2>{title}{sub_html}</h2>{body}</div>')


def table(headers, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in headers)
    return (f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table>')


def link(code, name):
    return D.lk(code, name)


def pct(v):
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return "—"


def load_hist_tracking():
    import json as _j
    p = ROOT / "output" / "ledger" / "history.json"
    return _j.loads(p.read_text(encoding="utf-8")).get("pool_tracking", {})


def H_(v):
    return str(v).replace('<', '&lt;').replace('>', '&gt;')


LINE_COLORS = {"航运": "#2b5fad", "算力(PCB/光通信)": "#c0392b", "粮食": "#b8860b", "半导体": "#7b3fa0"}


legend = ('<div class="note">曲线怎么读：每条线是一条主线的"趋势强度分"（动量40%+均线30%+量能30%，锚定ETF日K计算，60分以上=主升区）。'
          '<b>预警标记怎么看</b>：○ 空心圆=放量关注(L1)；实心圆+▲=启动预警(L2)；灰空心圆+✕=缩量骗炮——'
          '<b>量价同涨才可信</b>，缩量涨价多为反弹噪音（历史验证：08-10量比0.77骗炮、09-07量比1.48真启动）。</div>')


def render() -> str:
    # ---- 台账（跨日数据源：轮动/形态/状态机/趋势线序列）----
    _hd = json.loads((ROOT / "output" / "ledger" / "history.json").read_text(encoding="utf-8"))
    days_h = _hd.get("days", [])
    rot = _hd.get("rotation", {})
    today = days_h[-1] if days_h else {}
    prev = days_h[-2] if len(days_h) >= 2 else {}
    emo = json.loads(EP.read_text(encoding="utf-8")) if EP.exists() else None
    guide = render_guide(emo["thermometer"], emo["active_lines"], emo["retired_lines"]) if emo else ""
    wx = render_thermometer(emo) if emo else ""
    tier = render_tier_list(emo, "情绪梯队名册 · 非趋势（原「快打名单」）") if emo else ""
    f = D.FUNNEL

    # ---------- 个股 → 板块 → 主线 的显性关联 ----------
    SMAP = {}
    _sm = ROOT / "output" / "cache" / "sector_map.json"
    if _sm.exists():
        SMAP = json.loads(_sm.read_text(encoding="utf-8"))
    # 板块 → 主线（一条主线通常横跨多个板块；多对多时取主关联，首版口径）
    LINE_OF_SECTOR = {
        "半导体": "半导体", "电子化学品Ⅱ": "半导体", "其他电子Ⅱ": "半导体",
        "元件(PCB)": "算力硬件", "通信设备": "算力硬件", "光学光电子": "算力硬件",
        "专用设备": "算力硬件", "计算机设备": "算力硬件",
        "航海装备": "航运船舶", "航运港口": "航运船舶", "物流": "航运船舶",
        "种植业": "农业/粮食", "农产品加工": "农业/粮食", "饲料": "农业/粮食",
        "养殖业": "农业/粮食", "农化制品": "农业/粮食",
    }
    _active = set(emo["active_lines"]) if emo else set()
    _retired = set(emo["retired_lines"]) if emo else set()

    def sector_cell(code: str) -> str:
        """个股的 板块·主线 标签（绿=活跃主线内 / 红=退潮主线内 / 灰=非主线 / 虚=未归类）。"""
        sec = SMAP.get(code, {}).get("sector", "")
        if not sec:
            return '<span class="sec-none">未归类</span>'
        line = LINE_OF_SECTOR.get(sec, "")
        if not line:
            return f'<span class="sec">{sec}</span>'
        if line in _active:
            return f'<span class="sec sec-strong">{sec} · {line}</span>'
        if line in _retired:
            return f'<span class="sec sec-weak">{sec} · {line}</span>'
        return f'<span class="sec">{sec} · {line}</span>'

    # ---------- ② 汇合层：交叉验证表（正向侧 × 反向侧 → 判定） ----------
    def _cls(concl):
        if "互证" in concl or "互证" in concl:
            return "q-strong", "✓✓ 互证"
        if "缺印证" in concl:
            return "q-miss", "✓✗ 缺印证"
        if "双弱" in concl or "背离" in concl:
            return "q-weak", "✗✗ 双弱"
        return "q-none", "✗✗ 无信号"

    anchor_by_line = {a[2]: a for a in ETF_ANCHORS}
    cv_rows = ""
    for line, fwd, rev, concl, note in D.CROSS:
        cls, tag = _cls(concl)
        a = anchor_by_line.get(line)
        if a:
            gate = "过闸" if a[5] else "未过闸"
            rev = (f'{rev}<div class="cv-data">{link(a[0], a[1])}　20日 {a[3]}　60日 {a[4]}　'
                   f'规模 {a[6]} 亿　<span class="{"cv-gate-ok" if a[5] else "cv-gate-no"}">{gate}</span></div>')
        cv_rows += (
            f'<tr><td class="cv-line">{line}</td>'
            f'<td class="cv-fwd"><span class="cv-side">正向</span>{fwd}</td>'
            f'<td class="cv-arrow">⇄</td>'
            f'<td class="cv-rev"><span class="cv-side">反向</span>{rev}</td>'
            f'<td class="cv-res {cls}">{tag}<div class="cv-note">{note}</div></td></tr>')
    merge_layer = (
        '<div class="layer merge-layer">'
        '<div class="layer-title">② 汇合层 · <b>交叉验证</b>（正向通道 × 反向通道 的交点）'
        '<span class="layer-sub">左栏＝个股侧选出的主线；右栏＝它对应的 ETF 侧印证；判定＝两边是否相互确认</span></div>'
        f'<table class="cv-table"><thead><tr>'
        f'<th style="width:15%">主线</th><th style="width:31%">正向侧 · 个股 → 主线</th><th style="width:3%"></th>'
        f'<th style="width:31%">反向侧 · ETF → 成分</th><th style="width:20%">交叉判定</th>'
        f'</tr></thead><tbody>{cv_rows}</tbody></table>'
        '<div class="cv-legend">✓✓ 互证＝最强 ｜ ✓✗ 成立但缺印证 ｜ ✗✗ 双弱/无信号 —— '
        '判定说明：ETF 侧须过「方向闸」（20日≥8% 或创60日新高，且站上 MA20、60日跌幅≥-10%），'
        '深跌通道中的涨幅视为反弹噪音，不计印证。</div></div>')

    # ---------- ③ 正向通道 ----------
    funnel_rows = "".join(
        f'<tr><td>{k}</td><td class="num"><b>{v}</b></td></tr>' for k, v in [
            ("全市场约", f['全市场约']), ("站上所有均线", f['站上所有均线']),
            ("早期埋伏（大钱进了还没涨）", f['早期埋伏']),
            ("主升候选 · 剔除市值＜50亿后", f['主升候选(剔小市值后)']),
            ("主升候选 · 其中市值≥100亿", f['主升候选(市值≥100亿合格)']),
            ("站上主要均线 · 资金强", f['多头池资金强']),
            ("A 趋势池", f['A趋势池']),
            ("B 预期驱动池", f['B预期驱动池']),
            ("C 情绪池（原快打名单）", f['C情绪池'])])
    probe_rows = "".join(
        f'<tr><td>{link(p[0], p[1])}</td><td>{sector_cell(p[0])}</td><td class="num">{pct(p[2])}</td>'
        f'<td class="num">{p[3]}</td><td class="num">{p[4]:.1f}%</td></tr>' for p in D.PROBE)
    confirm_rows = "".join(
        f'<tr><td>{link(c[0], c[1])}</td><td>{sector_cell(c[0])}</td><td class="num">{pct(c[2])}</td>'
        f'<td class="num">{c[3]}</td><td class="num">{c[4]:.1f}</td></tr>' for c in D.CONFIRM)
    # A 池评分：优先规则分（可复现），无则回退手工分
    import subprocess as _sp2
    _sc_script = Path(__file__).parent / "score_stable.py"
    _sc_path = ROOT / "output" / "daily" / DAY / "data" / "a_pool_scored.json"
    if _sc_script.exists():
        _sp2.run([sys.executable, str(_sc_script), "--json"],
                 capture_output=True, text=True, timeout=180,
                 cwd=str(ROOT))   # 实时重算评分（不读过期缓存）
    _scores = {}
    if _sc_path.exists():
        for _sr in json.loads(_sc_path.read_text(encoding="utf-8")):
            _scores[_sr["code"]] = _sr
    a_rows_sorted = sorted(D.STABLE_LIST, key=lambda s: -(_scores.get(s[0], {}).get("rule") or s[2]))
    stable_rows = ""
    for s in a_rows_sorted:
        sr = _scores.get(s[0])
        if sr:
            d5 = sr["detail"]
            score_html = (f'<b>{sr["rule"]}</b><span class="muted">'
                          f'（主线{d5["主线"]}·地位{d5["地位"]}·蓄势{d5["蓄势"]}·资金{d5["资金"]}·距买点{d5["距买点"]}）</span>')
        else:
            score_html = f'<b>{s[2]}</b><span class="muted">（手工）</span>'
        stable_rows += (f'<tr><td>{link(s[0], s[1])}</td><td>{sector_cell(s[0])}</td>'
                        f'<td class="num">{score_html}</td>'
                        f'<td>{s[4]}</td><td class="muted">{s[6]}</td></tr>')
    vcp_rows = "".join(
        f'<tr><td>{link(v[0], v[1])}</td><td>{sector_cell(v[0])}</td><td class="num"><b>{v[2]}</b></td>'
        f'<td>{v[3]}</td><td class="num">{v[5]}</td><td class="num">{v[6]}</td>'
        f'<td class="num">{v[7]}%</td></tr>' for v in D.VCP)
    ml_blocks = []
    for m in D.MAINLINES:
        sc = m["sector"]
        etf = m["etf"]
        cls = {"刚起步": "ml-blue", "主升": "ml-red", "退潮": "ml-green"}.get(m["stage"].split("（")[0], "ml-gray")
        ml_blocks.append(
            f'<div class="ml-item {cls}"><div class="ml-h"><b>{m["name"]}</b> '
            f'<span class="ml-stage">{m["stage"]}</span>'
            f'<span class="ml-type">{m["type"]}</span></div>'
            f'<div class="ml-row"><span class="ml-k">板块体检</span>{sc[0]}｜当日 {sc[2]}｜上涨 {sc[3]}｜主力5日 <b>{sc[4]}</b>｜龙头 {sc[5]}</div>'
            f'<div class="ml-row"><span class="ml-k">ETF 通道</span>{link(etf[0], etf[1])}｜20日 {etf[2]}｜60日 {etf[3]}｜{etf[4]}｜规模 {etf[5]}</div>'
            f'<div class="ml-row"><span class="ml-k">判据</span>{m["judge"]}</div>'
            f'<div class="ml-note">{m["note"]}</div></div>')
    fwd_layer = (
        '<div class="layer-title fwd">③ 正向通道 ▶'
        '<span class="layer-sub">自下而上：个股 → 汇聚成主线 → 选票</span></div>'
        + card("漏斗计量", table(["环节", "数量"], funnel_rows), sub="漏斗宽窄＝市场温度计")
        + card("主线体检", "".join(ml_blocks), sub="判据：板块资金 × 上涨广度 × ETF 印证")
        + card("早期埋伏前 5", table(["标的", "板块 · 主线", "20日", "现价", "换手"], probe_rows),
               sub="大钱进了还没涨（早期埋伏名单）")
        + card("主升候选", table(["标的", "板块 · 主线", "20日", "现价", "PE"], confirm_rows),
               sub="主升名单 25~60%")
        + card("稳做名单", table(["标的", "板块 · 主线", "评分", "形态", "资格"], stable_rows),
               sub="五维规则评分（主线强度/板块地位/蓄势形态/资金验证/距买点）· 降序 · 形态≠交易资格")
        + card("蓄势观察", table(["标的", "板块 · 主线", "蓄势分", "档位", "突破价", "认错价", "距突破"], vcp_rows),
               sub="≥75 快憋满 / 60~75 还在压")
    )

    # ---------- ③ 反向通道 ----------
    etf_rows = "".join(
        f'<tr><td class="num">{i}</td><td>{link(e[0], e[1])}</td>'
        f'<td class="num"><b>{pct(e[2])}</b></td><td class="muted">{e[3]}</td></tr>'
        for i, e in enumerate(D.ETF_TOP, 1))
    anchor_rows = "".join(
        f'<tr><td>{link(a[0], a[1])}</td><td>{a[2]}</td><td class="num">{a[3]}</td>'
        f'<td class="num">{a[4]}</td>'
        f'<td>{_GATE_OK if a[5] else _GATE_NO}</td>'
        f'<td class="num">{a[6]} 亿</td></tr>' for a in ETF_ANCHORS)
    link_rows = "".join(
        f'<tr><td>{s[0]}</td><td class="num">{s[1]}</td><td class="num">{s[2]}</td>'
        f'<td><span class="lk-{"strong" if s[3]=="强" else ("weak" if s[3]=="弱" else "mid")}">{s[3]}</span></td>'
        f'<td class="muted">{s[4]}</td></tr>' for s in SECTOR_LINK)
    rev_layer = (
        '<div class="layer-title rev">◀ 反向通道'
        '<span class="layer-sub">自上而下：ETF → 反查成分龙头</span></div>'
        + card("ETF 20 日涨幅榜", table(["#", "ETF", "20日", "备注"], etf_rows),
               sub="剔宽基/海外 · 同指数留最大 · 规模≥5亿", cls="rev")
        + card("主线锚定 ETF 通道", table(["ETF", "主线", "20日", "60日", "方向闸", "规模"], anchor_rows),
               sub="方向闸拦深跌反弹 · 资金四象限当日申赎数据未出", cls="rev")
        + card("板块联动强度", table(["板块", "主力5日", "上涨家数", "联动", "说明"], link_rows),
               sub="业内等价于「互证」：板块资金方向 × 上涨广度", cls="rev")
        + card("ETF 持仓龙头反查",
               _render_etf_holdings(),
               sub="精确=跟踪指数成分 ｜ 近似=板块市值前列（ETF 实际持仓接口上游故障）", cls="rev")
    )

    # ---------- ④ 时间层（并入左右列底部） ----------
    watch_rows = "".join(
        f'<tr><td>{link(w[0], w[1])}</td><td>{sector_cell(w[0])}</td><td class="num">{w[3]}</td>'
        f'<td><span class="st">{w[4]}</span></td><td class="num">{w[5] if w[5] is not None else "—"}</td>'
        f'<td class="num">{w[6]}</td></tr>' for w in D.WATCH)
    ts_rows = "".join(
        f'<tr><td>{t[0]}</td><td class="num"><b>{t[1]}</b></td>'
        f'<td class="num">{t[2]:+.1f}</td><td class="num">{t[3]}</td></tr>' for t in D.SCORE_TREND)
    time_fwd = (card("观察池 · 跨日追踪（19 只 · 状态机）",
                     table(["标的", "板块 · 主线", "连续", "状态", "蓄势分", "今收"], watch_rows),
                     sub="收盘价推进状态机 · 与趋势强度分同轴", cls="time")
                + card("主线趋势强度分", table(["主线", "分数", "日环比", "量比"], ts_rows),
                       sub="v2 公式：动量40%+均线30%+量能30% · 3日平滑", cls="time"))
    time_emo = tier

    # ---------- ②.5 物种分诊：三池总览 + B 池详情 ----------
    gp = {}
    _gp = ROOT / "output" / "daily" / DAY / "data" / "growth_pool.json"
    if _gp.exists():
        gp = json.loads(_gp.read_text(encoding="utf-8"))
    bp = gp.get("b_pool", [])
    a_cnt = len(D.STABLE_LIST)
    c_cnt = len(emo["core"]) if emo else 0
    overview = (
        '<div class="layer clinic"><div class="layer-title">③ 物种分诊 · 三池总览'
        '<span class="layer-sub">筛选与分类分离——同一批候选按物种分诊，各池独立纪律</span></div>'
        '<div class="clinic-grid">'
        f'<div class="clinic-item c-a"><div class="ci-h">A · 稳做名单</div>'
        f'<div class="ci-n">{a_cnt} 只</div>'
        f'<div class="ci-d">PE∈[0,80] · PB≤8 · 扣非盈利</div>'
        f'<div class="ci-r">纪律：仓位≤20% · 让利润奔跑</div></div>'
        f'<div class="clinic-item c-b"><div class="ci-h">B · 预期驱动池</div>'
        f'<div class="ci-n">{len(bp)} 只</div>'
        f'<div class="ci-d">营收≥30% · 毛利&gt;40% · 研发≥15%</div>'
        f'<div class="ci-r">纪律：仓位≤10% · 独立账本 · 止损-5%</div></div>'
        f'<div class="clinic-item c-c"><div class="ci-h">C · 情绪池</div>'
        f'<div class="ci-n">{c_cnt} 只</div>'
        f'<div class="ci-d">涨停/连板 · 换手&gt;15%</div>'
        f'<div class="ci-r">纪律：机动仓≤5% · 快进快出</div></div>'
        '</div></div>')

    # ---------- 驾驶舱区块（趋势曲线/轮动热力/叙事/形态分布/追踪台）----------
    # 趋势线 SVG 为文本文件——直接内嵌（<img> 的相对路径在预览环境会 404）
    _sv_detail = (ROOT / "output" / "charts" / "trend-lines.svg").read_text(encoding="utf-8")
    _sv_annual = (ROOT / "output" / "charts" / "trend-lines-annual.svg").read_text(encoding="utf-8")
    # ---------- 左侧日期导航 + 总览入口页 ----------
    _all_days = sorted([d.name for d in (ROOT / "output" / "daily").iterdir()
                        if d.is_dir() and d.name[:4].isdigit()], reverse=True)

    def _day_href(d):
        """该日可打开的页面：index > report > layered。"""
        dd = ROOT / "output" / "daily" / d
        for cand in ("index.html", "report.html", "layered.html"):
            if (dd / cand).exists():
                return f"../{d}/{cand}"
        return f"../{d}/"

    _nav_items, _cur_m = "", None
    for d in _all_days:
        _m = d[:7]
        if _m != _cur_m:
            _nav_items += f'<div class="nav-m">{_m}</div>'
            _cur_m = _m
        _cur = ' cur' if d == DAY else ''
        _nav_items += f'<a class="nav-d{_cur}" href="{_day_href(d)}" title="{d}">{d[8:]}</a>'  # 只显示「日」
    nav_bar = f'<div class="date-nav"><div class="nav-t">复盘档案</div>{_nav_items}</div>'

    try:
        _ov_rows = []
        for _d in reversed(_all_days):
            _st = "；".join(f'{ln["name"]}·{ln["stages"].get(_d, "·")}'
                            for ln in rot.get("lines", []) if ln["stages"].get(_d))
            _ov_rows.append(f'<a class="ov-row" href="{_day_href(_d)}">'
                            f'<span class="ov-d">{_d}</span><span class="ov-s">{_st or "…"}</span></a>')
        _ov_css = ('<style>body{font-family:"PingFang SC",sans-serif;background:#f7f8fa;color:#1c2330;'
                   'max-width:860px;margin:40px auto;padding:0 20px}'
                   'h1{font-size:20px}a{display:flex;gap:16px;padding:10px 14px;margin:6px 0;'
                   'background:#fff;border-radius:9px;text-decoration:none;color:#1c2330;'
                   'box-shadow:0 1px 3px rgba(26,58,107,.06)}a:hover{background:#eef4ff}'
                   '.ov-d{font-weight:700;min-width:92px}.ov-s{color:#5b6472;font-size:13.5px}</style>')
        (ROOT / "output" / "index.html").write_text(
            f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
            f'<title>复盘档案 · 总览</title>{_ov_css}</head><body>'
            f'<h1>复盘档案 · 总览（点击进入当日页面）</h1>' + "".join(_ov_rows) + "</body></html>",
            encoding="utf-8")
    except Exception as _e:
        print(f"  ⚠️ 总览页生成失败：{_e}")

    trend_img = ('<div class="rot"><h3>主线趋势强度曲线——两条线的交叉就是接力棒交接的时刻</h3>'
                 '<div style="overflow-x:auto;background:#fff;border-radius:8px">' + _sv_detail + '</div>'
                 '<div style="margin-top:10px;background:#fff;border-radius:8px">' + _sv_annual + '</div>'
                 + legend +
                 '<div class="note">趋势线由 build_dashboard_full.py 生成（自动化每日更新）。</div></div>')
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

    story = f'''<div class="story"><b>〔人工轮动叙事 · 上次更新 09-15，随每日复盘续写〕</b><b>老主线怎么走完（农业/粮食）</b>：08-18 粮食ETF点火（+52分跳升）→ 08-19~09-07 主升（20日涨幅一度+20.4%）→ 09-08 尾声 → 09-10 退潮确认（中粮糖业天地板、梯队晋级失败）→ 09-14 退潮第3日（敦煌种业跌停-10%）→ <b>09-15 退潮第4日：种植业-4.65%（0/20上涨）、敦煌种业再跌停、粮食ETF 4连阴（今日-3.93%），20日涨幅滑落至-6.7%（今日口径），趋势强度分 38.4→30.4。彻底退场，只可龙头快打或不碰。</b><br>
    <b>新主线怎么接棒（算力硬件·PCB/覆铜板）</b>：09-10 候补入册（早期埋伏名单15席占12席，资金先行）→ 09-14 转正"刚起步"（元件5日145.4亿第1）→ <b>09-15 刚起步第2日：元件5日136.4亿维持第1、玻璃玻纤64.9亿第2；元件当日主力-17.6亿高位换手、玻璃玻纤当日+15.4亿接棒；板块内连板梯队仍在晋级（澳弘电子3板、双星新材3板、华正新材2连板涨停踩到突破价251.57）。但通信ETF方向闸仍未过（20日-8.0%、60日-27.4%深跌通道），且前十大权重无PCB股（锚定错配）——仍是"钱进了价没涨"，等ETF点火才有"主升·互证"。</b><br>
    <b>航运船舶（刚起步第7日）预警亮牌</b>：09-11 主升降级回刚起步后，09-15 ETF资金通道确认「价涨钱走=衰竭预警」——船舶ETF当日净流出480万、份额月-6.0%/周-3.7%，与20日+4.3%的涨幅背离；板块资金第7（未转流出）暂保刚起步，份额续缩则降级退潮。<br>
    <b>候补更替</b>：医疗服务候补一夜证伪（5日资金第11→第100）；新候补=<b>风电设备</b>（09-15 涨幅第2+5日资金第3+上涨家数80%，海力风电+12.84%）。<br>
    <b>轮动规律一句话</b>：资金是搬家不是离场——农业退潮撤出的钱正趴在元件板块（5日136亿），并已开始试水风电设备。盯住老主线尾声时谁在蓄势，接力棒交接处（曲线交叉）就是布局窗口。</div>'''

    heat_html = (f'<div class="rot"><h3>主线轮动时间线 · 阶段热力表（新日期在右；带*为ETF日K回溯推算）</h3>'
                 f'<table><tr><th class="nm">主线</th>{dates_head}</tr>{"".join(heat_rows)}</table>{story}</div>')
    prev_watch = {w["code"]: w for w in prev.get("watchlist", [])} if prev else {}   # list→dict（按 code 索引）
    days = days_h
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
        rows.append(f'<tr><td class="nm">{link(w0.get("code",""), w0["name"])}{gate}</td><td>{w0["first_seen"][5:]}</td><td class="num">{w0["days_in"]}</td>'
                    f'<td>{pill(w0["status"])}</td><td>{xushi_cell(w0["xushi"])}</td><td>{dist_cell(w0["dist_to_break_pct"])}</td>'
                    f'<td>{d}</td><td><div class="spark">{bars}</div></td><td class="muted">{w0["note"][:38]}…</td></tr>')
    watch_html = (f'<div class="rot"><h3>观察池 · 跨日追踪台（收盘价口径推进 · 数据日期 {today["date"]}）</h3>'
                  f'<table><tr><th>观察票</th><th>入池日</th><th>连续在榜</th><th>状态</th><th>今日蓄势分</th><th>距突破价</th><th>较上次</th><th>近5日</th><th>备注</th></tr>{"".join(rows)}</table></div>')
    chain = (f'<div class="chain">约 <b>{f.get("全市场约","—")}</b> 全市场 → <b>{f.get("站上所有均线","—")}</b> 站上所有主要均线 → '
             f'<b>{f.get("早期埋伏","—")}</b> 早期埋伏（大钱进了还没涨） → <b>{f.get("主升候选(剔小市值后)","—")}</b> 主升候选（合格{f.get("主升候选(市值≥100亿合格)","—")}） → '
             f'<b>{f.get("站上主要均线资金强","—")}</b> 站上主要均线×资金交叉 → <b>稳做 {f.get("稳做名单","—")}</b> ＋ <b>快打 {f.get("快打名单","—")}</b>'
             f'<span class="anchor-sub">（数据日期 {today["date"]}）</span></div>')

    pc = rot.get("pattern_check") or []
    pe = pc[-1] if pc else None
    if pe:
        d_ = pe.get("dist", {})
        chips = " · ".join(f'{k} <b>{v}</b> 只' for k, v in d_.items() if v)
        rows_p = ""
        for s in pe.get("stocks", []):
            e = s.get("eligibility", "—")
            cls = "p-green" if e.startswith("✅") else ("p-gray" if e.startswith("观察") else "p-red")
            rows_p += (f'<tr><td class="nm">{link(s.get("code",""), s.get("name",""))}</td><td>{s.get("pattern","")}</td>'
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
    # ---------- 三池跟踪统计（台账 pool_tracking）----------
    stats_card = ""
    try:
        _pt = load_hist_tracking()
        _en = _pt.get("entries", [])
        if _en:
            _h = [3, 5, 10, 20]
            _rows = ""
            for _pool in ("A", "B", "C"):
                _r = [e for e in _en if e["pool"] == _pool]
                if not _r:
                    continue
                _cells = []
                _done_any = False
                for _n in _h:
                    _vals = [e["follow"][f"t{_n}"]["ret_pct"] for e in _r if e["follow"].get(f"t{_n}")]
                    if _vals:
                        _done_any = True
                        _win = sum(1 for v in _vals if v > 0) / len(_vals) * 100
                        _cells.append(f"{sum(_vals)/len(_vals):+.1f}% / {_win:.0f}%")
                    else:
                        _cells.append("—")
                _cells.append(f"{sum(1 for e in _r if any(e['follow'].values()))}/{len(_r)}")
                _rows += (f'<tr><td>{_pool} 池</td><td class="num">{len(_r)}</td>'
                          + "".join(f'<td class="num">{c}</td>' for c in _cells) + "</tr>")
            if _rows:
                stats_card = ('<div class="layer" style="border-left:5px solid #7F77DD">'
                    '<div class="layer-title">三池跟踪 · 台账统计'
                    '<span class="layer-sub">T+N 均收益 / 胜率 · 已回填/样本 · 20 交易日后数据裁决</span></div>'
                    '<table class="mini2"><tr><th>池</th><th>样本</th>'
                    + "".join(f"<th>T+{n}</th>" for n in _h) + "<th>已回填</th></tr>"
                    + _rows + '</table>'
                    '<div class="bp-note">裁决规则：B 池跑赢 A 池 → 原 PE 硬闸在误伤，应放宽；'
                    'B 池跑输 → 硬闸正确。数据裁决，不凭感觉改纪律。</div></div>')
    except Exception:
        stats_card = ""

    b_rows = ""
    for x in bp[:20]:
        t = x.get("tech") or {}
        st_cls = {"已触发": "st-fire", "临近突破": "st-near",
                  "蓄势充分": "st-ready"}.get(t.get("status"), "st-watch")
        tech_cells = (
            f'<td class="num">{t.get("vcp_score", "—")}</td>'
            f'<td><span class="{st_cls}">{t.get("status", "—")}</span></td>'
            f'<td class="num">{t.get("break_price", "—")}</td>'
            f'<td class="num">{t.get("invalid_price", "—")}</td>'
        ) if t else '<td colspan="4" class="muted">技术面缺失</td>'
        b_rows += (f'<tr><td>{link(x["code"], x["name"])}</td>'
                   f'<td class="muted">{H_(x.get("sector") or "—")}</td>'
                   f'<td class="num"><b>{x["torg"]:.1f}%</b></td>'
                   f'<td class="num">{x["gross"]:.1f}%</td>'
                   f'<td class="num">{x["rd_ratio"]:.1f}%</td>'
                   + tech_cells + '</tr>')
    b_block = (
        '<div class="layer bpool"><div class="layer-title">B 池详情 · 预期驱动'
        '<span class="layer-sub">被 A 池 PE/PB 硬闸拦下、但成长性可验证的标的 —— '
        '⚠️ 买点与 A 池相同（价格确认永不让步）；仓位减半、独立账本。买点状态：已触发＝收盘站上突破价 ｜ 临近突破＝距突破价 ≤2% ｜ 蓄势充分＝形态憋满但离买点还远</span></div>'
        '<table class="bp-table"><thead><tr>'
        '<th>标的</th><th>板块</th><th>营收增速</th><th>毛利率</th><th>研发占比</th>'
        '<th>蓄势分</th><th>买点状态</th><th>突破价</th><th>认错价</th>'
        f'</tr></thead><tbody>{b_rows or _B_EMPTY}</tbody></table>'
        f'<div class="bp-note">入口：{gp.get("entry_expr", "—")}　｜　'
        f'入口 {gp.get("stats", {}).get("entry", 0)} 只 → 反闸剔除 {gp.get("stats", {}).get("rejected", 0)} 只 '
        f'→ B 池 {len(bp)} 只　｜　依据：CANSLIM + Rule of 40 + 创业板第四套标准</div></div>')

    # ---------- 名词小词典（项目铁律：日报开头固定放，禁黑话）----------
    DICT_ITEMS = [
        ("资金主线", "整个行业被大钱持续买入"), ("涨停主线", "游资连板炒起来的热点"),
        ("刚起步", "钱进了、价还没涨"), ("主升", "钱和价一起涨"),
        ("尾声", "开始炒补涨股"), ("退潮", "大钱在撤"),
        ("互证", "股票和它对应的 ETF 同时走强——最强的确认信号"),
        ("蓄势形态", "回调一次比一次浅、成交一次比一次少，涨之前憋的那口气"),
        ("突破价", "涨过它说明真启动"), ("认错价", "跌破它说明看错了"),
        ("A 稳做名单", "基本面合格 + 技术趋势确认（原「稳做名单」）"),
        ("B 预期驱动池", "眼下不盈利或微利，但营收高增长、研发重投入"),
        ("C 情绪池", "涨停/连板票，纯博弈，不进趋势账本"),
        ("早期埋伏名单", "大钱已经进了、股价还没涨的票"),
        ("主升名单", "已涨 25%~60%、趋势确认中的票"),
    ]
    dict_html = ('<div class="dictbar"><b>名词小词典</b>'
                 + "".join(f'<span class="di"><b>{k}</b>{v}</span>' for k, v in DICT_ITEMS)
                 + '</div>')

    guide_strip = (f'<div class="strip">{guide}</div>' if guide else "")
    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>趋势候选日报 · 四层架构 + 三池分诊 {DAY}</title>
<style>
 body{{font-family:-apple-system,"PingFang SC","Helvetica Neue",sans-serif;background:#f2f5f9;color:#1c2333;
      margin:0;padding:0;line-height:1.65}}
 .date-nav{{position:fixed;left:0;top:0;bottom:0;width:88px;overflow-y:auto;background:#16202e;padding:12px 6px;z-index:50}}.date-nav .nav-t{{color:#5b6b80;font-size:11px;font-weight:700;padding:4px 6px;margin-bottom:6px}}.date-nav .nav-m{{color:#e8b14a;font-size:10.5px;font-weight:700;padding:8px 6px 3px;border-top:1px solid #243244;margin-top:4px}}.date-nav a{{display:block;color:#9fb0c8;text-decoration:none;font-size:12.5px;padding:5px 7px;border-radius:6px;margin-bottom:2px;text-align:center}}.date-nav a.cur{{background:#2b5fad;color:#fff;font-weight:700}}.date-nav a:hover{{background:#243244}}.shell{{max-width:1900px;height:100vh;margin:0 auto 0 88px;padding:14px 18px 0;display:flex;flex-direction:column;box-sizing:border-box}}
 .fixed{{flex:0 0 auto}}
 h1{{font-size:20px;margin:0 0 2px;color:#1a3a6b}}
 .meta{{font-size:11.5px;color:#8a94a8;margin-bottom:10px}}
 .strip .guide{{margin-bottom:10px}}
 .layer{{background:#fff;border:1px solid #e4eaf2;border-radius:12px;padding:12px 15px;margin-bottom:10px}}
 .layer-title{{font-size:12.5px;color:#8a94a8;margin-bottom:9px;font-weight:400}}
 .layer-title b,.layer-title{{font-weight:500}}
 .layer-sub{{font-weight:400;font-size:11px;color:#a8b2c0;margin-left:8px}}
 .merge-layer{{border-left:5px solid #b8860b}}
 .cv-table{{width:100%;border-collapse:collapse;font-size:11.5px}}
 .cv-table th{{text-align:left;color:#8a94a8;font-weight:500;font-size:10.5px;padding:5px 8px;
   border-bottom:1px solid #eef2f8;background:#fafcfe}}
 .cv-table td{{padding:7px 8px;border-bottom:1px solid #f4f7fb;vertical-align:top}}
 .cv-line{{font-weight:500;color:#1c2333}}
 .cv-fwd{{background:#f5f9ff;color:#1a3a6b;border-radius:6px}}
 .cv-rev{{background:#f4fbf8;color:#0f6e56;border-radius:6px}}
 .cv-side{{display:block;font-size:10px;color:#a8b2c0;margin-bottom:2px}}
 .cv-arrow{{text-align:center;color:#c8d2e0;font-size:15px;width:26px}}
 .cv-res{{font-weight:500;white-space:nowrap}}
 .cv-res.q-strong{{color:#1a9e6b}} .cv-res.q-miss{{color:#d97b1c}}
 .cv-res.q-weak{{color:#d43a3a}} .cv-res.q-none{{color:#8a94a8}}
 .cv-note{{font-weight:400;font-size:10.5px;color:#8a94a8;white-space:normal;margin-top:2px;line-height:1.5}}
 .dictbar{{background:#fffdf5;border:1px dashed #e0cfa0;border-radius:9px;padding:9px 12px;margin-top:8px;
   font-size:11px;color:#5b5233;line-height:1.8}}
 .dictbar>b{{color:#8a6a3a;margin-right:8px}}
 .di{{margin-right:14px;display:inline-block}}
 .di>b{{color:#1a3a6b;font-weight:500}}
 .etfh{{width:100%;border-collapse:collapse;font-size:11.5px}}
 .etfh th{{text-align:left;color:#8a94a8;font-weight:500;font-size:10.5px;padding:5px 6px;border-bottom:1px solid #eef2f8;background:#fafcfe}}
 .etfh td{{padding:6px;border-bottom:1px solid #f4f7fb;vertical-align:top}}
 .prec-yes{{background:#e6f5ee;color:#0f6e56;border-radius:999px;padding:1px 7px;font-size:11px}}
 .prec-approx{{background:#fdf1e2;color:#d97b1c;border-radius:999px;padding:1px 7px;font-size:11px}}
 .mini2{{width:100%;border-collapse:collapse;font-size:11.5px}}
 .mini2 th{{text-align:left;color:#8a94a8;font-weight:500;font-size:10.5px;padding:5px 6px;border-bottom:1px solid #eef2f8;background:#fafcfe}}
 .mini2 td{{padding:6px;border-bottom:1px solid #f4f7fb}}
 .clinic{{border-left:5px solid #EF9F27}}
 .clinic-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}}
 .clinic-item{{border-radius:9px;padding:9px 12px;border:1px solid #eef2f8}}
 .c-a{{background:#f1f8ff;border-color:#b5d4f4}} .c-b{{background:#f4f7ff;border-color:#a9b6e8}}
 .c-c{{background:#fdf3ee;border-color:#f0c8b4}}
 .ci-h{{font-size:12.5px;font-weight:500;color:#1a3a6b}}
 .c-c .ci-h{{color:#993C1D}}
 .ci-n{{font-size:19px;font-weight:500;color:#1c2333;line-height:1.2;margin:2px 0}}
 .ci-d{{font-size:11px;color:#5b6472}}
 .ci-r{{font-size:11px;color:#8a94a8;margin-top:3px;padding-top:3px;border-top:1px dashed #e8eef6}}
 .bpool{{border-left:5px solid #7F77DD}}
 .bp-table{{width:100%;border-collapse:collapse;font-size:11.5px}}
 .bp-table th{{text-align:left;color:#8a94a8;font-weight:500;font-size:10.5px;padding:5px 6px;border-bottom:1px solid #eef2f8;background:#fafcfe;white-space:nowrap}}
 .bp-table td{{padding:6px;border-bottom:1px solid #f4f7fb;vertical-align:top}}
 .st-fire{{background:#e6f5ee;color:#0f6e56;border-radius:999px;padding:1px 7px;font-size:11px;font-weight:500}}
 .st-near{{background:#fdf1e2;color:#d97b1c;border-radius:999px;padding:1px 7px;font-size:11px;font-weight:500}}
 .st-ready{{background:#eef2f7;color:#5b6472;border-radius:999px;padding:1px 7px;font-size:11px}}
 .st-watch{{background:#f4f7fb;color:#a8b2c0;border-radius:999px;padding:1px 7px;font-size:11px}}
 .bp-note{{font-size:11px;color:#8a94a8;margin-top:8px;padding-top:7px;border-top:1px dashed #e8eef6;line-height:1.6}}
 .sec{{font-size:10.5px;background:#eef2f7;border-radius:4px;padding:1px 6px;color:#5b6472;white-space:nowrap}}
 .sec-strong{{background:#e6f5ee;color:#0f6e56}}
 .sec-weak{{background:#fdeaea;color:#c0392b}}
 .sec-none{{color:#c8d2e0;font-size:10.5px}}
 .cv-data{{font-size:10.5px;color:#5b6472;margin-top:3px;line-height:1.5}}
 .cv-gate-ok{{color:#1a9e6b}} .cv-gate-no{{color:#d43a3a}}
 .cv-legend{{font-size:11px;color:#8a94a8;margin-top:8px;padding-top:7px;border-top:1px dashed #e8eef6;line-height:1.6}}
 .quad-item{{border-radius:8px;padding:8px 11px;border:1px solid #eef2f8;background:#fafcfe}}
 .q-strong{{background:#e6f5ee;border-color:#9fe1cb}}
 .q-miss{{background:#fdf1e2;border-color:#f5c4b3}}
 .q-weak{{background:#fdeaea;border-color:#f7c1c1}}
 .q-none{{background:#f2f1ec;border-color:#e3e1d7}}
 .q-name{{font-size:12.5px;font-weight:500;color:#1c2333}}
 .q-tag{{font-size:11.5px;color:#5b6472;margin:2px 0}}
 .q-note{{font-size:11px;color:#8a94a8}}
 .cols{{flex:1 1 auto;display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:14px;min-height:0}}
 .col{{overflow-y:auto;overscroll-behavior:contain;padding-right:9px;padding-bottom:20px}}
 .col::-webkit-scrollbar{{width:9px}}
 .col::-webkit-scrollbar-track{{background:#e9edf3;border-radius:5px}}
 .col::-webkit-scrollbar-thumb{{background:#c3ccd8;border-radius:5px}}
 .col::-webkit-scrollbar-thumb:hover{{background:#a8b4c4}}
 .col-inner{{position:sticky;top:0;background:#f2f5f9;z-index:5;padding-bottom:8px}}
 .layer-title.fwd{{color:#185FA5;border-bottom:2px solid #85B7EB;padding-bottom:5px}}
 .layer-title.rev{{color:#0F6E56;border-bottom:2px solid #5DCAA5;padding-bottom:5px}}
 .card{{background:#fff;border:1px solid #e4eaf2;border-radius:10px;padding:11px 13px;margin-bottom:11px}}
 .card.rev{{border-left:4px solid #5DCAA5}}
 .card.time{{border-left:4px solid #b8860b}}
 .card h2{{font-size:13px;margin:0 0 8px;color:#1a3a6b;font-weight:500}}
 .card-sub{{font-weight:400;font-size:11px;color:#a8b2c0;margin-left:8px}}
 .card p.muted{{font-size:11.5px;color:#8a94a8;margin:0}}
 table{{width:100%;border-collapse:collapse;font-size:11.5px}}
 th{{text-align:left;color:#8a94a8;font-weight:500;font-size:10.5px;padding:5px 6px;
    border-bottom:1px solid #eef2f8;background:#fafcfe;white-space:nowrap}}
 td{{padding:5px 6px;border-bottom:1px solid #f4f7fb;vertical-align:top}}
 td.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
 a{{color:#2b5fad;text-decoration:none}} a:hover{{text-decoration:underline}}
 .muted{{color:#8a94a8;font-size:11px}}
 .st{{font-size:11px;background:#eef2f7;border-radius:999px;padding:1px 7px;color:#5b6472;white-space:nowrap}}
 .gate-ok{{color:#1a9e6b;font-size:11px;font-weight:500}}
 .gate-no{{color:#d43a3a;font-size:11px;font-weight:500}}
 .lk-strong{{background:#e6f5ee;color:#1a9e6b;border-radius:999px;padding:1px 7px;font-size:11px}}
 .lk-mid{{background:#fdf1e2;color:#d97b1c;border-radius:999px;padding:1px 7px;font-size:11px}}
 .lk-weak{{background:#fdeaea;color:#d43a3a;border-radius:999px;padding:1px 7px;font-size:11px}}
 .foot{{flex:0 0 auto;font-size:11px;color:#8a94a8;border-top:1px solid #e4eaf2;padding:8px 0 10px}}
 {EMO_CSS}
 .ml-item{{border:1px solid #eef2f8;border-left:4px solid #b4b2a9;border-radius:8px;padding:9px 11px;margin-bottom:8px;background:#fafcfe}}
 .ml-blue{{border-left-color:#85B7EB}} .ml-red{{border-left-color:#F09595}}
 .ml-green{{border-left-color:#5DCAA5}} .ml-gray{{border-left-color:#b4b2a9}}
 .ml-h{{font-size:12.5px;margin-bottom:4px}}
 .ml-stage{{font-size:11px;background:#eef2f7;border-radius:999px;padding:1px 7px;color:#5b6472;margin-left:5px}}
 .ml-type{{font-size:11px;color:#8a94a8;margin-left:5px}}
 .ml-row{{font-size:11.5px;color:#3d4757;margin:2px 0}}
 .ml-k{{display:inline-block;min-width:58px;color:#a8b2c0;font-size:10.5px}}
 .ml-note{{font-size:11px;color:#8a6a3a;background:#fffdf5;border-radius:6px;padding:5px 8px;margin-top:5px}}
 {CSS_EXTRA}
 @media(max-width:1250px){{
   .shell{{height:auto}} body{{overflow:auto}}
   .cols{{display:block}} .col{{overflow:visible;height:auto}}
 }}
</style></head><body>{nav_bar}<div class="shell">
<div class="fixed">
<h1>趋势候选日报 · 四层架构 {DAY}</h1>
<div class="meta">数据时点 {DAY} 收盘（ETF 区间榜为 09-17 口径）｜数据来源 腾讯自选股（westock）｜
① 天气 → ② 汇合 → ③ 双通道 → ④ 时间层</div>
<div class="strip"><div class="guide"><span class="guide-title">今日该看哪本账</span>
<span class="guide-trend"><span class="badge-trend">趋势</span> 活跃主线 {'/'.join(emo["active_lines"]) if emo else '—'} → 按既定规则执行</span>
<span class="guide-emotion"><span class="badge-emotion">情绪</span> 阶段 {emo["thermometer"]["stage"] if emo else '—'} → 仅强联动可看</span>
<span class="guide-meta">活跃主线 {len(emo["active_lines"]) if emo else 0} 条 / 退潮 {len(emo["retired_lines"]) if emo else 0} 条</span></div></div>
{wx}
{dict_html}
{trend_img}
{heat_html}
</div>

{merge_layer}

{overview}
{stats_card}
{pattern_card}

<div class="cols">
 <div class="col">
  <div class="col-inner"><div class="layer-title fwd">③ 正向通道 ▶ 自下而上：个股 → 主线 → 选票</div></div>
  {chain}
{fwd_layer}
  {b_block}
  <div class="col-inner"><div class="layer-title" style="color:#b8860b;border-bottom:2px solid #f0c96a;padding-bottom:5px">④ 时间层 · 趋势侧跨日跟踪</div></div>
  {time_fwd}
 </div>
 <div class="col">
  <div class="col-inner"><div class="layer-title rev">◀ 反向通道 自上而下：ETF → 成分龙头</div></div>
  {rev_layer}
 </div>
 <div class="col">
  <div class="col-inner"><div class="layer-title emo" style="color:#993C1D;border-bottom:2px solid #E8B9A6;padding-bottom:5px">④ 时间层 · 情绪侧跨日跟踪</div></div>
  {time_emo}
 </div>
</div>

<div class="foot">{D.DISCLAIMER}</div>
</div></body></html>
'''


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    html = render()
    OUT.write_text(html, encoding="utf-8")
    print(f"[ok] 四层架构版已落盘 {OUT}（{len(html)} 字符）")

    # 术语自检（prompt「语言规范」为铁律，防黑话/内部编号回归）
    import subprocess as _sp
    lint = Path(__file__).parent / "lint_report.py"
    if lint.exists():
        r = _sp.run([sys.executable, str(lint), str(OUT)], capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode != 0:
            print("⚠️  术语自检未通过 —— 请按 prompt「语言规范」修正后再提交")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
