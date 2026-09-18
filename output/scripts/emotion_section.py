#!/usr/bin/env python3
"""情绪票池渲染模块（只看版）。

设计规范（三重冗余编码，config/settings.json → emotion_pool.display）：
  ① 色系：趋势=冷蓝 #185FA5 ｜ 情绪=暖橙红 #D85A30
  ② 徽章：趋势=描边胶囊 ｜ 情绪=实心胶囊（更强的警示）
  ③ 版式：趋势=表格（可比较） ｜ 情绪=卡片流（各自处境，不可比）
  另：情绪区块带 1.5px 全边框 + 顶部实色警示带（视觉重量更重）

用法：from emotion_section import render_section; html = render_section(data)
"""
import html as H


def _link(code: str, name: str) -> str:
    return f'<a href="https://gu.qq.com/{code}" target="_blank">{H.escape(str(name))}</a>'


BADGE_TREND = '<span class="badge-trend">趋势</span>'
BADGE_EMOTION = '<span class="badge-emotion">情绪</span>'

LINKAGE_CLS = {"板块联动·强": "lk-strong", "板块联动·弱（主线已退潮）": "lk-weak",
               "板块联动·无": "lk-none", "未归类": "lk-none"}
ROLE_CLS = {"总龙": "r-lead", "连板梯队": "r-tier", "补涨": "r-fill",
            "跟风": "r-follow", "首板": "r-first"}


def render_guide(thermo: dict, active: list, retired: list) -> str:
    """顶部导向条：今天该看哪本账。"""
    stage = thermo.get("stage", "—")
    if not active:
        trend_txt, emotion_txt = "无活跃主线 → 只跟踪不新开仓", "仅强联动档可看，其余看戏"
    else:
        trend_txt = f"活跃主线 {'/'.join(active)} → 按既定规则执行"
        emotion_txt = f"{len(active)} 条活跃主线 → 联动档可看"
    if stage in ("冰点", "退潮"):
        emotion_txt = f"情绪{stage} → 原则上不参与"
    br = thermo.get("broken_rate")
    br_txt = f"{br:.0%}" if isinstance(br, (int, float)) else "—"
    return (f'<div class="guide"><span class="guide-title">今日该看哪本账</span>'
            f'<span class="guide-trend">{BADGE_TREND} {trend_txt}</span>'
            f'<span class="guide-emotion">{BADGE_EMOTION} {emotion_txt}</span>'
            f'<span class="guide-meta">活跃主线 {len(active)} 条 / 退潮 {len(retired)} 条</span>'
            f'<div class="guide-quick">情绪温度计：最高板 <b>{thermo.get("max_board")}</b>'
            f'（{thermo.get("max_board_name")}）　涨停 <b>{thermo.get("limitup_count")}</b> 家'
            f'　炸板率 <b>{br_txt}</b>　阶段 <b>{stage}</b>'
            f'　<a href="#emoPool">↓ 展开连板梯队与红旗</a></div></div>')


def render_section(data: dict, title: str = "情绪票池 · 非趋势 · 高波动") -> str:
    t = data["thermometer"]
    core = data.get("core", [])
    fb = data.get("first_board", {})

    def fmt(v, suffix="", nd=1):
        return "—" if v is None else f"{v:.{nd}f}{suffix}"

    # 温度计
    th_rows = [
        ("连板高度（市场最高板）", f'{t["max_board"]}（{t["max_board_name"]}）'),
        ("涨停家数（真封板）", f'{t["limitup_count"]} 家'),
        ("炸板率（近似）", fmt(t.get("broken_rate"), "", 3) if t.get("broken_rate") is not None else "—"),
        ("连板溢价率", "待台账积累"),
        ("晋级率", "待台账积累"),
    ]
    th_html = "".join(f'<div class="th-item"><span class="th-k">{k}</span><span class="th-v">{v}</span></div>'
                      for k, v in th_rows)

    # 梯队卡片流
    cards = []
    for p in core:
        flags = p.get("red_flags") or []
        notes = p.get("notes") or []
        flag_html = "".join(f'<span class="flag"><span class="flag-dot"></span>{H.escape(f)}</span>' for f in flags)
        note_html = "".join(f'<span class="note-item">{H.escape(n)}</span>' for n in notes)
        link_cls = LINKAGE_CLS.get(p.get("linkage", ""), "lk-none")
        role_cls = ROLE_CLS.get(p.get("role", ""), "r-tier")
        cards.append(f'''<div class="emo-card{' has-flag' if flags else ''}">
<div class="emo-line1">
  <span class="emo-name">{_link(p["code"], p["name"])}</span>
  <span class="boards">{p["boards"]} 板</span>
  <span class="role {role_cls}">{p["role"]}</span>
  <span class="lk {link_cls}">{H.escape(p.get("linkage", "—"))}</span>
</div>
<div class="emo-line2">
  <span>{H.escape(p.get("sector", "—"))}</span>
  <span class="muted">现价 {fmt(p.get("close"), "", 2)}</span>
  <span class="{"up" if (p.get("chg_pct") or 0) >= 0 else "down"}">{fmt(p.get("chg_pct"), "%", 2)}</span>
  <span class="muted">换手 {fmt(p.get("turnover"), "%")}</span>
  <span class="muted">市值 {fmt(p.get("market_cap_yi"), "亿", 0)}</span>
</div>
{(f'<div class="emo-flags">{flag_html}</div>' if flag_html else '')}
{(f'<div class="emo-notes">{note_html}</div>' if note_html else '')}
</div>''')

    return f'''<div class="emo-wrap" id="emoPool">
<div class="emo-band">
  {BADGE_EMOTION}<span class="emo-band-title">{H.escape(title)}</span>
  <span class="emo-band-rule">机动仓 ≤1/3 · 只赌分歧转一致 · 破启动板无条件清仓</span>
</div>
<div class="emo-body">
  <div class="th-block"><div class="th-title">市场情绪温度计<span class="muted">（游资圈五指标 · 阈值待本地校准）</span></div>
    <div class="th-grid">{th_html}</div>
    <div class="th-basis">阶段判定：<b>{H.escape(t.get("stage", "—"))}</b>　依据：{H.escape(t.get("stage_basis", ""))}
    <span class="muted">　｜　{H.escape(t.get("unavailable_note", ""))}</span></div>
  </div>
  <div class="tier-title">连板梯队（{len(core)} 只）<span class="muted">— 情绪的核心结构：谁在最前面、谁在退潮期硬撑</span></div>
  <div class="emo-cards">{"".join(cards)}</div>
  <div class="fb-note">首板 {fb.get("count", 0)} 只（含红旗 {fb.get("with_flags", 0)} 只）——首板是情绪燃料，不是可操作对象，此处只计数不列名。</div>
  <div class="emo-disclaimer">本区块标的与稳做名单无任何关系，不适用趋势仓位与止盈规则。标注为机器判据，终审由人。</div>
</div></div>'''


CSS = """
.guide{background:#0C447C;border-radius:10px;padding:11px 16px;margin-bottom:16px;display:flex;flex-wrap:wrap;gap:6px 18px;align-items:baseline}
.guide-title{font-size:12px;color:#85B7EB}
.guide-trend{font-size:12.5px;color:#E6F1FB}
.guide-emotion{font-size:12.5px;color:#F5C4B3}
.guide-meta{font-size:11.5px;color:#85B7EB;margin-left:auto}
.guide-quick{flex-basis:100%;font-size:12.5px;color:#F5C4B3;padding-top:8px;margin-top:6px;border-top:1px solid rgba(255,255,255,.18)}
.guide-quick b{color:#fff;font-weight:500}
.guide-quick a{color:#85B7EB;text-decoration:underline}
.badge-trend{display:inline-block;border:.5px solid #85B7EB;color:#85B7EB;border-radius:999px;padding:0 7px;font-size:11px}
.badge-emotion{display:inline-block;background:#D85A30;color:#fff;border-radius:999px;padding:0 7px;font-size:11px}
.emo-wrap{border:2.5px solid #C0392B;border-radius:12px;overflow:hidden;margin-bottom:16px;background:#fdf3ee}
.emo-band{background:#C0392B;padding:12px 16px;display:flex;flex-wrap:wrap;gap:6px 16px;align-items:baseline}
.emo-band-title{font-size:15px;color:#fff;font-weight:500}
.emo-band-rule{font-size:12px;color:#FBDDD3}
.emo-body{padding:14px 16px}
.th-block{background:#fff;border:1px solid #F0D3C8;border-radius:8px;padding:12px 14px;margin-bottom:14px}
.th-title{font-size:12.5px;color:#993C1D;font-weight:500;margin-bottom:8px}
.th-grid{display:flex;flex-wrap:wrap;gap:8px 22px}
.th-item{display:flex;gap:6px;align-items:baseline}
.th-k{font-size:11.5px;color:#a08177}
.th-v{font-size:13px;color:#5b3a30;font-weight:500}
.th-basis{font-size:11.5px;color:#8a6a60;margin-top:9px;line-height:1.6}
.tier-title{font-size:12.5px;color:#993C1D;font-weight:500;margin:4px 0 9px}
.tier-title .muted{font-weight:400}
.emo-cards{display:flex;flex-direction:column;gap:8px}
.emo-card{background:#fff;border-left:4px solid #E8B9A6;border-radius:7px;padding:10px 13px}
.emo-card.has-flag{border-left-color:#d43a3a;background:#fff7f7}
.emo-line1{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:baseline}
.emo-name{font-size:13.5px;font-weight:500;color:#1c2333}
.boards{font-size:11.5px;color:#993C1D;font-weight:500}
.role{font-size:11px;border-radius:999px;padding:0 7px}
.r-lead{background:#fdeaea;color:#c0392b}.r-tier{background:#f0f0f0;color:#5b6472}
.r-fill{background:#fdf1e2;color:#d97b1c}.r-follow{background:#eceff3;color:#6b7280}.r-first{background:#eceff3;color:#6b7280}
.lk{font-size:11px;border-radius:999px;padding:0 7px}
.lk-strong{background:#e6f5ee;color:#1a9e6b}.lk-weak{background:#fdeaea;color:#c0392b}.lk-none{background:#eceff3;color:#6b7280}
.emo-line2{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:11.5px;color:#5b6472;margin-top:4px}
.emo-flags{margin-top:5px;display:flex;flex-wrap:wrap;gap:6px 14px}
.flag{font-size:11.5px;color:#c0392b;display:inline-flex;align-items:center;gap:4px}
.flag-dot{display:inline-block;width:6px;height:6px;background:#d43a3a;transform:rotate(45deg)}
.emo-notes{margin-top:4px;display:flex;flex-wrap:wrap;gap:6px 14px}
.note-item{font-size:11px;color:#8a94a8}
.fb-note{font-size:11.5px;color:#8a94a8;margin-top:10px}
.emo-disclaimer{font-size:11px;color:#c0392b;margin-top:10px;padding-top:9px;border-top:1px dashed #f0d3c8}
.emo-body .up{color:#d43a3a}.emo-body .down{color:#1a9e6b}.emo-body .muted{color:#8a94a8}
"""
