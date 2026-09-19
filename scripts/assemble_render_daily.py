#!/usr/bin/env python3
"""组装 render_daily.py（每日唯一页面渲染器）—— 干净版组装脚本。

输入：render_v3_layered.py（四层骨架+全部日报区块）
      build_dashboard_full.py（驾驶舱独有区块的源实现）
输出：render_daily.py（读 ledger 台账 + 当日 data/，输出 daily/<DAY>/index.html）
"""
import re
from pathlib import Path

SP = Path(__file__).resolve().parent
base = (SP / "render_v3_layered.py").read_text(encoding="utf-8")
dash = (SP / "build_dashboard_full.py").read_text(encoding="utf-8")


def between(src, start, end):
    """提取 [start, end) 之间的源码段（end 为下一锚点起点）。"""
    i = src.find(start)
    assert i >= 0, f"起点未找到：{start[:50]}"
    j = src.find(end, i + len(start))
    assert j > i, f"终点未找到：{end[:50]}"
    return src[i:j].rstrip() + "\n"


def indent4(t):
    return "\n".join(("    " + ln) if ln.strip() else ln for ln in t.splitlines())


# ================= 从驾驶舱提取独有区块 =================
line_colors = between(dash, "LINE_COLORS = ", "\n") + "\n"
legend = between(dash, "legend = ('", "trend_html = (")
heat_block = between(dash, "STAGE_CLS = ", "# 观察池追踪台")      # 含 story + heat_html
watch_block = between(dash, "STATUS_CLS = ", "# 三段式双向锚定")  # 含 watch_html
chain_block = between(dash, "chain = (f'", "stable_rows = ")
chain_block = chain_block[: chain_block.rfind("')") + 3] + "\n"
pattern_block = between(dash, "pc = rot.get(", "# ---- 三池分诊总览")

# 适配：qlink → link（render 的链接函数）
legend = legend.replace("qlink(", "link(")
heat_block = heat_block.replace("qlink(", "link(")
watch_block = watch_block.replace("qlink(", "link(")
pattern_block = pattern_block.replace("qlink(", "link(")

# story 标注为人工叙事
heat_block = heat_block.replace(
    'story = f\'\'\'<div class="story">',
    'story = f\'\'\'<div class="story"><b>〔人工轮动叙事 · 上次更新 09-15，随每日复盘续写〕</b>', 1)

# ================= 组装 render_daily.py =================
out = base

# 1) 输出路径：daily/<DAY>/index.html
out = out.replace('OUT = ROOT / "output" / "daily" / DAY / "layered.html"',
                  'OUT = ROOT / "output" / "daily" / DAY / "index.html"')

# 2) 模块级：LINE_COLORS + legend（render 之前插入）
out = out.replace("def render() -> str:",
                  line_colors + "\n" + legend + "\n\ndef render() -> str:", 1)

# 3) render() 开头：加载台账
out = out.replace(
    "def render() -> str:\n    emo =",
    """def render() -> str:
    # ---- 台账（跨日数据源：轮动/形态/状态机/趋势线序列）----
    _hd = json.loads((ROOT / "output" / "ledger" / "history.json").read_text(encoding="utf-8"))
    days_h = _hd.get("days", [])
    rot = _hd.get("rotation", {})
    today = days_h[-1] if days_h else {}
    prev = days_h[-2] if len(days_h) >= 2 else {}
    emo =""", 1)

# 4) render() 内：驾驶舱区块构造（置于三池统计之前，缩进 4）
anchor = "    # ---------- 三池跟踪统计（台账 pool_tracking）----------"
assert anchor in out, "三池统计锚点缺失"

trend_img_code = (
    "    trend_img = ('<div class=\"rot\"><h3>主线趋势强度曲线——两条线的交叉就是接力棒交接的时刻</h3>'\n"
    "             '<img src=\"../charts/trend-lines.svg\" style=\"width:100%;background:#fff;border-radius:8px\">'\n"
    "             '<img src=\"../charts/trend-lines-annual.svg\" style=\"width:100%;margin-top:10px;background:#fff;border-radius:8px\">'\n"
    "             + legend +\n"
    "             '<div class=\"note\">趋势线由 build_dashboard_full.py 生成（自动化每日更新）。</div></div>')\n")

inject = (
    "    # ---------- 驾驶舱区块（趋势曲线/轮动热力/叙事/形态分布/追踪台）----------\n"
    + trend_img_code
    + indent4(heat_block) + "\n"
    + indent4(watch_block) + "\n"
    + indent4(chain_block) + "\n"
    + indent4(pattern_block) + "\n"
    + anchor)
out = out.replace(anchor, inject, 1)

# 5) 模板：全景带（趋势线+热力+叙事）插到词典后；形态卡插到统计卡后；漏斗链插正向列首
out = out.replace("{dict_html}\n</div>", "{dict_html}\n{trend_img}\n{heat_html}\n</div>", 1)
out = out.replace("{stats_card}", "{stats_card}\n{pattern_card}", 1)
out = out.replace("{fwd_layer}", "{chain}\n{fwd_layer}", 1)

# 6) 观察池卡片标题更新（状态机口径）
out = out.replace('card("观察池 · 跨日追踪（19 只）"',
                  'card("观察池 · 跨日追踪（19 只 · 状态机）"', 1)

# ================= 写出 =================
dst = SP / "render_daily.py"
dst.write_text(out, encoding="utf-8")
print(f"✅ render_daily.py 已组装（{len(out)/1024:.0f} KB）→ {dst}")
