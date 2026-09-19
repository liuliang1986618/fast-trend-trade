#!/usr/bin/env python3
"""四层架构专用渲染部件：情绪天气条 + 梯队名册 + 附加样式。

与 emotion_section.py 的关系：
  emotion_section.py —— 单列/双列版用的整块渲染（render_section）
  本文件 —— 四层架构版用的拆分渲染（天气层 / 时间层各取所需）
"""
import html as H

from emotion_section import BADGE_EMOTION, LINKAGE_CLS, ROLE_CLS, _link


def render_thermometer(data: dict) -> str:
    """① 全局天气层：市场情绪温度计（横排大数字）。"""
    t = data["thermometer"]
    br = t.get("broken_rate")
    items = [
        ("连板高度", str(t.get("max_board", "—")), f'（{t.get("max_board_name", "—")}）'),
        ("涨停家数", str(t.get("limitup_count", "—")), "家"),
        ("炸板率", f"{br:.0%}" if isinstance(br, (int, float)) else "—", "近似"),
        ("情绪阶段", str(t.get("stage", "—")), ""),
    ]
    cells = "".join(
        f'<div class="wx-cell"><div class="wx-k">{k}</div>'
        f'<div class="wx-v">{v}<span class="wx-u">{u}</span></div></div>'
        for k, v, u in items)
    return (f'<div class="wx"><div class="wx-title">情绪天气'
            f'<span class="wx-sub">游资圈五指标·阈值待本地校准·溢价率与晋级率待台账积累</span></div>'
            f'<div class="wx-grid">{cells}</div></div>')


def _num(v, fmt=".2f", suffix=""):
    if v is None:
        return "—"
    try:
        return format(float(v), fmt) + suffix
    except (TypeError, ValueError):
        return "—"


def render_tier_list(data: dict, title: str = "情绪梯队名册 · 非趋势 · 高波动") -> str:
    """④ 时间层：连板梯队 + 红旗（与观察池并列的跨日跟踪对象）。"""
    core = data.get("core", [])
    fb = data.get("first_board", {})
    cards = []
    for p in core:
        flags = p.get("red_flags") or []
        notes = p.get("notes") or []
        flag_html = "".join(
            f'<span class="flag"><span class="flag-dot"></span>{H.escape(f)}</span>' for f in flags)
        note_html = "".join(f'<span class="note-item">{H.escape(n)}</span>' for n in notes)
        link_cls = LINKAGE_CLS.get(p.get("linkage", ""), "lk-none")
        role_cls = ROLE_CLS.get(p.get("role", ""), "r-tier")
        _seal = p.get("seal_time")
        _eod = p.get("seal_eod")
        _eod_tag = ('<span class="seal-ok">尾盘封死</span>' if _eod
                    else ('<span class="seal-broken">炸板</span>' if _seal else ''))
        cards.append(
            f'<div class="tier-card{" has-flag" if flags else ""}">'
            f'<div class="tier-l1">'
            f'<span class="tier-name">{_link(p["code"], p["name"])}</span>'
            f'<span class="boards">{p["boards"]} 板</span>'
            f'<span class="role {role_cls}">{p["role"]}</span>'
            f'<span class="lk {link_cls}">{H.escape(p.get("linkage", "—"))}</span>'
            f'</div>'
            f'<div class="tier-l2"><span>{H.escape(p.get("sector", "—"))}</span>'
            f'<span class="muted">首封 {_seal or "—"}</span>{_eod_tag}'
            f'<span class="muted">现价 {_num(p.get("close"))}</span>'
            f'<span class="muted">换手 {_num(p.get("turnover"), ".1f", "%")}</span>'
            f'<span class="muted">市值 {_num(p.get("market_cap_yi"), ".0f", "亿")}</span></div>'
            + (f'<div class="tier-flags">{flag_html}</div>' if flag_html else "")
            + (f'<div class="tier-notes">{note_html}</div>' if note_html else "")
            + '</div>')
    return (f'<div class="tier-wrap">'
            f'<div class="tier-band">{BADGE_EMOTION}'
            f'<span class="tier-band-t">{H.escape(title)}</span>'
            f'<span class="tier-band-r">机动仓 ≤1/3 · 破启动板无条件清仓</span></div>'
            f'<div class="tier-body">{"".join(cards)}'
            f'<div class="fb-note">首板 {fb.get("count", 0)} 只（含红旗 {fb.get("with_flags", 0)}）'
            f'——首板是情绪燃料，只计数不列名。</div>'
            f'<div class="emo-disclaimer">与稳做名单无任何关系，不适用趋势仓位与止盈规则；'
            f'机器判据，终审由人。</div></div></div>')


CSS_EXTRA = """
.seal-ok{background:#e6f5ee;color:#0f6e56;border-radius:4px;padding:1px 5px;font-size:10.5px}
.seal-broken{background:#fdeaea;color:#c0392b;border-radius:4px;padding:1px 5px;font-size:10.5px}
.wx{border:1px solid #F0D3C8;background:#fff;border-radius:10px;padding:10px 14px}
.wx-title{font-size:12.5px;color:#993C1D;font-weight:500;margin-bottom:8px}
.wx-sub{font-weight:400;font-size:11px;color:#a08177;margin-left:8px}
.wx-grid{display:flex;flex-wrap:wrap;gap:10px 36px}
.wx-cell{display:flex;flex-direction:column;gap:2px}
.wx-k{font-size:11px;color:#8a94a8}
.wx-v{font-size:20px;font-weight:500;color:#1c2333;line-height:1.15}
.wx-u{font-size:11px;color:#a08177;margin-left:4px}
.tier-wrap{border:2px solid #C0392B;border-radius:10px;overflow:hidden;background:#fdf3ee}
.tier-band{background:#C0392B;padding:8px 13px;display:flex;flex-wrap:wrap;gap:5px 12px;align-items:baseline}
.tier-band-t{font-size:13px;color:#fff;font-weight:500}
.tier-band-r{font-size:11px;color:#FBDDD3}
.tier-body{padding:11px 13px}
.tier-card{background:#fff;border-left:4px solid #E8B9A6;border-radius:7px;padding:8px 11px;margin-bottom:8px}
.tier-card.has-flag{border-left-color:#d43a3a;background:#fff8f8}
.tier-l1{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:baseline}
.tier-name{font-size:13px;font-weight:500;color:#1c2333}
.tier-l2{display:flex;flex-wrap:wrap;gap:5px 12px;font-size:11.5px;color:#5b6472;margin-top:3px}
.tier-flags{margin-top:4px;display:flex;flex-wrap:wrap;gap:5px 12px}
.tier-notes{margin-top:3px;display:flex;flex-wrap:wrap;gap:5px 12px}
.tier-wrap .up{color:#d43a3a}.tier-wrap .down{color:#1a9e6b}.tier-wrap .muted{color:#8a94a8}
.layer-head{font-size:12px;color:#8a94a8;border-bottom:1px solid #e4eaf2;padding-bottom:6px;margin:0 0 10px;
  display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline}
.layer-head b{color:#1a3a6b;font-weight:500}
.layer-head.rev b{color:#0f6e56}
.layer-head.emo b{color:#993C1D}
"""
