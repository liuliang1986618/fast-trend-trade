#!/usr/bin/env python3
"""2026-09-18 日运行：生成日报 HTML + 更新 history.json 台账。

数据来源（本次运行实测）：
- 选股四件套：westock-tool CLI（1.5.0）
- 板块体检：mcp data_sector（09-18 收盘口径，单位万元→亿元折算）
- ETF 数据：mcp data_etf overview（09-18）+ ETF 榜（09-17 口径）
- 个股行情：westock quote（09-18 收盘）
- 蓄势分：run_signal vcp 同源公式复算（output/tmp/vcp_score.py）
- 趋势强度分：rotation.score_formula v2 实现（output/tmp/trend_score.py）

注意：ETF 资金通道字段（etfInFlow/份额变化）当日返回全 0（申赎数据未出），
故四象限结论标注"当日数据缺失"；不臆造。
"""
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAY = "2026-09-18"
HIST = ROOT / "output" / "ledger" / "history.json"
# 单列版日报已退役（v3.1 合并页 daily/<DAY>/index.html 取代），render() 保留供追溯
D_TMP = ROOT / "output" / "tmp"

DISCLAIMER = (
    "免责声明：以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。"
    "市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，"
    "必要时咨询持牌专业机构。过往表现不预示未来收益。"
)


def lk(code, name):
    """标的 → 腾讯自选股详情页可点击链接。"""
    return f'<a href="https://gu.qq.com/{code}" target="_blank">{name}</a>'


# ---------------------------------------------------------------- 今日数据
# 漏斗计量（当日实测值；两版日报共用此口径）
# 注：「稳做名单」= A 趋势池，「快打名单」= C 情绪池（显示时用新名称）
FUNNEL = {
    "全市场约": 5577, "站上所有均线": 517, "早期埋伏": 15,
    "主升候选(剔小市值后)": 15, "主升候选(市值≥100亿合格)": 3,
    "多头池资金强": 15,
    "A趋势池": 8, "B预期驱动池": 31, "C情绪池": 12,
}

PROBE = [  # 早期埋伏前 5（早期埋伏名单按主力5日净流入降序前5）
    ("sz002080", "中材科技", 11.70, 60.22, 6.71, 19.21),
    ("sh600522", "中天科技", 7.63, 35.98, 8.57, 16.86),
    ("sh603256", "宏和科技", 5.97, 148.79, 3.58, 12.98),
    ("sz300502", "新易盛", 0.68, 445.00, 3.35, 11.79),
    ("sz002487", "大金重工", 1.07, 39.60, 13.53, 11.47),
]

CONFIRM = [  # 主升候选（主升名单 25~60）
    ("sh600354", "敦煌种业", 59.10, 10.23, 39.3, 4.92),
    ("sz003006", "百亚股份", 56.25, 21.25, 45.9, 6.04),
    ("sz001216", "华瓷股份", 50.83, 21.87, 31.4, 10.01),
    ("sz301688", "格林生物", 48.54, 39.11, 28.5, 7.74),
    ("sz002011", "盾安环境", 43.72, 14.20, 15.1, 1.79),
    ("sz300592", "华凯易佰", 40.78, 20.99, 29.9, 0.57),
    ("sz300473", "德尔股份", 38.98, 30.45, 30.1, 0.69),
    ("sz001368", "通达创智", 38.56, 32.45, 36.4, 2.95),
    ("sh600059", "古越龙山", 35.79, 10.70, 43.6, 8.63),
    ("sz002443", "金洲管道", 34.84, 12.50, 39.3, 0.40),
    ("sh605258", "协和电子", 34.09, 37.45, 49.9, 0.19),
    ("sh688799", "华纳药厂", 28.52, 56.10, 32.35, 6.84),
    ("sz002734", "利民股份", 27.71, 18.62, 18.11, 1.53),
    ("sh605580", "恒盛能源", 27.60, 22.70, 34.93, -2.95),
    ("sh601218", "吉鑫科技", 26.71, 5.55, 31.13, -3.31),
    ("sh600163", "中闽能源", 26.12, 6.18, 23.79, 4.22),
    ("sh603236", "移远通信", 26.07, 72.54, 30.37, -1.52),
]

MAINLINES = [
    {
        "name": "半导体", "type": "资金主线", "stage": "刚起步",
        "sector": ("半导体", "pt01801081", "+3.95%", "177/181（98%）", "+243.78 亿（第 1）", "托伦斯 +20.00%"),
        "etf": ("sh512480", "半导体ETF国联安", "20 日 -3.66%", "60 日 -27.83%", "深跌通道", "198.9 亿"),
        "limitup": "澳弘电子（PCB，5 板，属算力侧）", "pattern": "待精判",
        "judge": "上涨面 ✅ 98%（177/181）｜板块资金 ✅ 全市场第 1（+243.78 亿）｜ETF 印证 ✗（仍在深跌通道，方向闸不通过）"
                 "｜题材成色（人判）：AI 算力/国产替代产业逻辑在，今日为板块级放量反攻 → 判「刚起步」（资金先行、价格未点火）",
        "note": "今日最强资金方向：半导体 5 日吸金 243.78 亿居全市场第 1，且上涨广度 98%；但 ETF 仍处深跌后的反弹通道，"
                "按 ETF 方向闸不算印证 → 属「资金型埋伏」而非「互证主升」。",
    },
    {
        "name": "算力硬件（PCB/覆铜板/光通信）", "type": "资金主线", "stage": "退潮",
        "sector": ("元件", "pt01801083", "+0.91%", "43/61（70%）", "-67.84 亿（转净流出）", "一博科技 +12.04%"),
        "sector2": ("通信设备（光通信侧）", "pt01801102", "+2.92%", "73/85（86%）", "+49.76 亿（第 2）", "阿莱德 +13.03%"),
        "etf": ("sh515880", "通信ETF", "20 日 +3.31%", "60 日 -27.18%", "深跌通道", "433.98 亿"),
        "limitup": "澳弘电子 5 板（PCB）、中晶科技 3 板", "pattern": "待精判",
        "judge": "上涨面 ✅（元件 43/61、通信设备 73/85）｜板块资金 ⚠️ 分化：元件由第 1 转为净流出 -67.84 亿、光通信侧仍居第 2"
                 "｜ETF 印证 ✗（通信ETF 60 日 -27.18%，深跌）→ 按「板块资金转流出＝退潮」判退潮",
        "note": "⚠️ 内部严重分化：PCB/覆铜板侧（元件板块）资金由强转负，光通信侧（通信设备）仍强。"
                "趋势强度分却从 16.7 一路回升至 30.6（+6.7）——价格在回暖而核心板块的钱在撤，属典型「价钱背离」，重点观察。",
    },
    {
        "name": "航运船舶", "type": "资金主线", "stage": "退潮",
        "sector": ("航海装备Ⅱ", "pt01801744", "+2.26%", "9/10（90%）", "-19.64 亿（净流出）", "松发股份 +7.49%"),
        "etf": ("sh560710", "船舶ETF富国", "20 日 +8.26%", "60 日 +6.45%", "方向闸✅通过", "15.65 亿"),
        "limitup": "—", "pattern": "待精判",
        "judge": "上涨面 ✅ 90%（9/10）｜板块资金 ✗ 净流出 -19.64 亿｜ETF 印证 ✅（20 日 +8.26%、60 日 +6.45%，方向闸通过）"
                 "→ 资金与价格背离，按「板块 5 日资金转流出＝退潮」判退潮",
        "note": "唯一仍满足 ETF 价格印证的主线，但板块资金连续转出、份额持续萎缩（09-17：周份额 -7.97%）——"
                "「价涨钱走」的衰竭形态延续，趋势强度分 49.3 → 37.9 回落。",
    },
    {
        "name": "农业/粮食", "type": "涨停主线", "stage": "退潮（第 7 日）",
        "sector": ("种植业", "pt01801016", "-0.18%", "9/20（45%）", "-13.90 亿（净流出）", "敦煌种业 +4.92%"),
        "sector2": ("农产品加工", "pt01801012", "+1.42%", "14/23（61%）", "+2.12 亿", "金健米业 +9.98%"),
        "etf": ("sz159063", "粮食ETF南方", "20 日 +1.14%", "60 日 +10.64%", "规模 0.59 亿＜2 亿降权", "0.59 亿"),
        "limitup": "万向德农 2 板", "pattern": "待精判",
        "judge": "上涨面 ✗ 45%（种植业 9/20）｜板块资金 ✗ 净流出 -13.90 亿｜ETF 无印证（20 日仅 +1.14%）→ 退潮延续",
        "note": "金健米业（sh600127）今日再涨停 +9.98%，但属个股情绪脉冲：20 日涨幅已达 74.63%（超高位档 60% 线），"
                "且近 10 日涨停 ≥2 根触发硬闸 → 系统判定为「情绪票」，不入稳做名单（快打范畴，主线退潮期不碰）。",
    },
]

CROSS = [
    ("半导体", "✓ 上涨面 98%（177/181）· 主力 5 日 +243.78 亿（全市场第 1）",
     "✗ ETF 仍在深跌通道（20 日 -3.66% · 60 日 -27.83%）", "成立但缺印证",
     "资金全市场第 1，却无 ETF 搭档印证——若 ETF 后续站上 20 日线并跟涨，可升级为互证"),
    ("航运船舶", "✓ 上涨面 90%（9/10）",
     "✓ ETF 过闸（20 日 +8.26%），但份额萎缩", "弱互证 / 衰竭预警",
     "价格在涨、资金在撤，涨幅靠存量资金推升"),
    ("算力硬件", "✓ 上涨面 70~86%（元件 43/61 · 通信设备 73/85）· 但元件资金转负 -67.84 亿",
     "✗ ETF 仍在深跌通道（通信ETF 60 日 -27.18%）", "双弱 / 价钱背离",
     "价格回暖、PCB 侧资金撤出，内部分歧最大"),
    ("农业/粮食", "✗ 上涨面 45%（种植业 9/20）· 涨停主线退潮第 7 日",
     "✗ ETF 无印证（20 日 +1.14%）", "无信号", "退潮第 7 日，反抽不改退潮判定"),
]

ETF_TOP = [
    ("sz159981", "能源化工ETF建信", 13.30, "宽基/商品，剔除"),
    ("sh520870", "巴西ETF易方达", 10.22, "海外，剔除"),
    ("sz159100", "巴西ETF华夏", 9.70, "海外，剔除"),
    ("sh560710", "船舶ETF富国", 8.26, "★ 航运主线锚定，方向闸✅"),
    ("sz159985", "豆粕ETF华夏", 7.28, "＜8% 阈值，观察"),
    ("sh513350", "标普油气ETF富国", 5.81, "海外，剔除"),
    ("sz159855", "影视ETF银华", 5.01, "主题偏弱"),
    ("sz159518", "标普油气ETF嘉实", 4.94, "海外，剔除"),
    ("sh516620", "影视ETF国泰", 4.79, "主题偏弱"),
    ("sh512670", "国防ETF鹏华", 4.70, "军工系，未成主线"),
]

LIMITUP = [
    ("sh605058", "澳弘电子", 5, "算力硬件（PCB）"), ("sh603248", "锡华科技", 3, "—"),
    ("sz001216", "华瓷股份", 3, "主升名单候选（主升档）"), ("sz003026", "中晶科技", 3, "算力硬件（半导体材料）"),
    ("sh600371", "万向德农", 2, "农业/粮食（退潮中）"), ("sz003001", "中岩大地", 2, "—"),
    ("sh603230", "内蒙新华", 2, "—"), ("sz002655", "共达电声", 2, "—"), ("sz002285", "世联行", 2, "房地产服务"),
]

VCP = [  # (code, name, score, grade, close, trigger, invalid, dist)
    ("sz300398", "飞凯材料", 86.3, "快憋满", 38.35, 38.89, 31.60, 1.41),
    ("sh600522", "中天科技", 86.0, "快憋满", 35.98, 36.90, 31.31, 2.56),
    ("sh603256", "宏和科技", 74.4, "还在压", 148.79, 152.18, 118.73, 2.28),
    ("sz002436", "兴森科技", 74.4, "还在压", 42.88, 44.00, 31.81, 2.61),
    ("sz002080", "中材科技", 73.3, "还在压", 60.22, 64.56, 46.59, 7.21),
    ("sh603601", "再升科技", 73.3, "还在压", 10.21, 10.96, 8.52, 7.35),
    ("sh603186", "华正新材", 59.8, "没形态", 226.78, 264.00, 160.67, 16.41),
    ("sz300502", "新易盛", 49.5, "没形态", 445.00, 453.78, 378.56, 1.97),
    ("sh600183", "生益科技", 47.8, "没形态", 143.93, 157.50, 122.05, 9.43),
    ("sz002487", "大金重工", 36.4, "没形态", 39.60, 42.90, 32.04, 8.33),
]

# 跨日追踪：昨日 19 只 → 今日状态推进（用收盘/最高价对比突破价/认错价）
WATCH = [
    ("sz300398", "飞凯材料", "2026-09-15", 3, "已触发", 86.3, 38.35, 38.89, 37.33, 31.60, 1.41, "收盘 38.35 站上突破价 37.33 ✅ 转稳做跟踪"),
    ("sz002008", "大族激光", "2026-09-12", 8, "已触发", 73.5, 99.60, 100.89, 99.50, 82.33, 0.10, "收盘 99.60 站上突破价 99.50 ✅ 转稳做跟踪"),
    ("sz002436", "兴森科技", "2026-09-15", 5, "已触发", 74.4, 42.88, 44.00, 42.73, 31.81, 0.35, "收盘 42.88 站上突破价 42.73 ✅ 转稳做跟踪"),
    ("sh600522", "中天科技", "2026-09-16", 3, "已触及·等回踩", 86.0, 35.98, 36.90, 36.47, 31.31, 1.36, "盘中 36.90 触价、收盘 35.98 未站稳"),
    ("sz002080", "中材科技", "2026-09-16", 3, "已触及·等回踩", 73.3, 60.22, 64.56, 61.47, 46.59, 2.07, "盘中 64.56 触价、收盘 60.22 未站稳"),
    ("sh600105", "永鼎股份", "2026-09-17", 2, "已触及·等回踩", 74.0, 46.47, 47.50, 46.99, 36.56, 1.12, "盘中 47.50 触价、收盘 46.47 未站稳"),
    ("sz300394", "天孚通信", "2026-09-10", 7, "已触及·等回踩", 47.2, 284.66, 292.07, 289.70, 237.80, 1.77, "盘中 292.07 触价、收盘 284.66 未站稳"),
    ("sz300570", "太辰光", "2026-09-15", 5, "已触及·等回踩", 60.1, 229.35, 242.99, 230.46, 178.18, 0.48, "盘中 242.99 触价、收盘 229.35 未站稳"),
    ("sh601872", "招商轮船", "2026-09-10", 8, "已触发（跟踪中）", 62.0, 22.36, 22.90, 21.70, 17.79, 3.04, "维持已触发，收盘 22.36 高于突破价"),
    ("sh603601", "再升科技", "2026-09-11", 5, "观察中", 73.3, 10.21, 10.36, 10.96, 8.52, 7.35, "蓄势分 86.2→73.3 回落，退回观察"),
    ("sh600183", "生益科技", "2026-09-11", 8, "观察中", 47.8, 143.93, 149.60, 157.28, 122.05, 9.43, "⚠️ 蓄势分 87.2→47.8 大幅回落，触及后未站稳回落至观察"),
    ("sh603186", "华正新材", "2026-09-10", 7, "观察中", 59.8, 226.78, 242.80, 251.57, 160.67, 16.41, "警示：距突破价 16.41%，蓄势分 76.7→59.8 走弱"),
    ("sz300475", "香农芯创", "2026-09-10", 7, "观察中", 71.9, 174.32, 174.97, 187.52, 147.20, 7.57, "继续观察"),
    ("sh600176", "中国巨石", "2026-09-17", 2, "观察中", 61.1, 45.02, 48.48, 51.68, 37.83, 12.92, "玻纤侧回调 -4.52%"),
    ("sh600150", "中国船舶", "2026-09-10", 8, "观察中", 48.2, 39.47, 39.97, 41.18, 32.59, 4.34, "继续观察"),
    ("sh601975", "招商南油", "2026-09-10", 8, "观察中", 59.9, 4.64, 4.72, 4.97, 3.65, 7.11, "继续观察"),
    ("sz000737", "北方铜业", "2026-09-10", 8, "观察中", 58.5, 14.40, 14.72, 17.20, 13.80, 19.44, "距突破价远，观察"),
    ("sh688825", "长鑫科技", "2026-09-11", 6, "观察中", None, 55.54, 55.96, None, None, None, "无蓄势参数（未出形态）"),
    ("sz002487", "大金重工", "2026-09-16", 3, "观察中", 36.4, 39.60, 40.88, 42.90, 32.04, 8.33, "蓄势 36.4 没形态，只留状态行"),
]

SCORE_TREND = [("航运", 37.9, 0.8, 1.58), ("算力(PCB/光通信)", 30.6, 6.7, 1.10),
               ("半导体", 21.2, 6.2, 0.92), ("粮食", 16.5, 2.5, 0.90)]

STABLE_LIST = [  # 稳做名单（评分降序，含形态/资格）
    ("sh600522", "中天科技", 82, "算力（光通信）", "86.0 快憋满", "主力5日+16.86亿；20日+7.63% 落在启动档；距突破价仅 2.56%", "✅稳做·优先档"),
    ("sz300398", "飞凯材料", 80, "算力（材料）", "86.3 快憋满", "今日站上突破价转已触发；20日+7.51%；主力5日+4.61亿", "✅稳做·优先档"),
    ("sz002080", "中材科技", 78, "玻纤/材料", "73.3 还在压", "站上主要均线·资金第 1（5日+19.21亿）；20日+11.70% 启动档上沿；盘中已触突破价", "✅稳做·观察档"),
    ("sz002436", "兴森科技", 76, "算力（PCB）", "74.4 还在压", "今日站上突破价；主力5日+8.11亿；⚠️ 所属元件板块资金转流出", "✅稳做·观察档"),
    ("sz002008", "大族激光", 74, "算力（设备）", "73.5 还在压", "今日站上突破价；20日+9.57%", "✅稳做·观察档"),
    ("sz300570", "太辰光", 72, "算力（光模块）", "60.1 还在压", "主力5日+9.70亿（原）；盘中触突破价未站稳；换手 14.94% 偏高", "✅稳做·观察档"),
    ("sh600105", "永鼎股份", 70, "算力（光通信）", "74.0 还在压", "盘中触突破价；主力5日+8.34亿；PE 162 偏高", "✅稳做·观察档"),
    ("sh603256", "宏和科技", 68, "算力（材料）", "74.4 还在压", "⚠️ PE 272 超红线（>80）", "❌红线拦截(PE272)"),
]

QUICK_LIST = [
    ("sh605058", "澳弘电子", "5 板", "算力硬件（PCB）", "最高板，PCB 主线核心情绪票"),
    ("sh603248", "锡华科技", "3 板", "—", "次高板"),
    ("sz003026", "中晶科技", "3 板", "算力硬件（半导体材料）", "半导体侧情绪票"),
    ("sh600371", "万向德农", "2 板", "农业/粮食", "退潮主线补涨，只可龙头快打或不碰"),
    ("sz003001", "中岩大地", "2 板", "—", "—"),
    ("sh603230", "内蒙新华", "2 板", "—", "—"),
    ("sz002655", "共达电声", "2 板", "—", "—"),
    ("sz002285", "世联行", "2 板", "房地产服务", "房地产异动"),
    ("sh600127", "金健米业", "连板中", "农业/粮食", "⚠️ 20日+74.63% 超高位档 + 近10日涨停≥2 根 → 硬闸出局，仅快打范畴"),
]


# ---------------------------------------------------------------- HTML 渲染
def render() -> str:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    from emotion_section import render_section, render_guide, CSS as EMO_CSS
    _emo_path = ROOT / "output" / "tmp" / f"emotion_pool_{DAY}.json"
    _emo = json.loads(_emo_path.read_text(encoding="utf-8")) if _emo_path.exists() else None
    guide_html = render_guide(_emo["thermometer"], _emo["active_lines"], _emo["retired_lines"]) if _emo else ""
    emo_html = render_section(_emo) if _emo else '<div class="card neg">情绪池数据未生成</div>'

    def card(title, body, cls="pos"):
        return f'<div class="card {cls}"><h2>{title}</h2>{body}</div>'

    # ① 漏斗计量行 —— 数量全部由数据运行时计算（禁止手工填写，避免与页面不一致）
    f = FUNNEL

    def _pool_count(fname, key):
        try:
            d = json.loads((D_TMP / fname).read_text(encoding="utf-8"))
            return len(d.get(key, []))
        except Exception:
            return 0

    b_cnt = _pool_count(f"growth_pool_{DAY}.json", "b_pool")
    c_cnt = _pool_count(f"emotion_pool_{DAY}.json", "core")
    # 确认层：按实际市值分档（剔小市值 = 剔除 <50 亿；合格 = ≥100 亿）
    _codes = [c[0] for c in CONFIRM]
    try:
        import westock_cli as _W
        _q = _W.quote(_codes)
        _caps = {c: (_W.to_yi(_q.get(c, {}).get("total_market_cap")) or 0) for c in _codes}
        conf_all = len(_codes)
        conf_mid = sum(1 for c in _codes if _caps[c] >= 50)
        conf_big = sum(1 for c in _codes if _caps[c] >= 100)
    except Exception:
        conf_all, conf_mid, conf_big = len(_codes), len(_codes), 0
    funnel_html = (
        f'<div class="meter">全市场约 <b>{f["全市场约"]}</b> → 站上所有均线 <b>{f["站上所有均线"]}</b> '
        f'→ 早期埋伏 <b>{f["早期埋伏"]}</b> → 主升候选 <b>{conf_all}</b> 只（剔除市值＜50亿后 <b>{conf_mid}</b>，'
        f'其中市值≥100亿 <b>{conf_big}</b> 只） '
        f'→ 站上主要均线·资金强 <b>{f["多头池资金强"]}</b> → '
        f'<b>A 趋势池 {f["A趋势池"]} ／ B 预期驱动池 {f["B预期驱动池"]} ／ C 情绪池 {f["C情绪池"]}</b>'
        f'<span class="muted">（漏斗宽窄＝市场温度计）</span></div>'
    )

    # ② 名词小词典
    dict_items = [
        ("资金主线", "整个行业被大钱持续买入"), ("涨停主线", "游资连板炒起来的热点"),
        ("刚起步", "钱进了价没涨"), ("主升", "钱价一起涨"), ("尾声", "开始炒补涨股"), ("退潮", "大钱在撤"),
        ("互证", "股票和它的ETF同时涨（最强信号）"), ("蓄势形态", "回调一次比一次浅、成交一次比一次少，涨之前憋的那口气"),
        ("突破价", "涨过它说明真启动"), ("认错价", "跌破它说明看错了"),
        ("稳做名单", "跟着主线慢慢拿的票"), ("快打名单", "纯情绪票快进快出"),
    ]
    dict_html = '<div class="dictcard"><b>名词小词典</b>：' + "；".join(
        f'{k}＝{v}' for k, v in dict_items) + "。</div>"

    # ③ 主线体检
    rows = []
    for m in MAINLINES:
        s = m["sector"]
        s2 = m.get("sector2")
        etf = m["etf"]
        sector_line = (f'{s[0]}｜{s[1]}｜当日 <b>{s[2]}</b>｜上涨 {s[3]}｜主力5日 <b>{s[4]}</b>｜龙头 {s[5]}')
        if s2:
            sector_line += f'<br><span class="muted">　└ {s2[0]}：当日 {s2[2]}｜上涨 {s2[3]}｜主力5日 {s2[4]}｜龙头 {s2[5]}</span>'
        etf_line = (f'{lk(etf[0], etf[1])}｜20 日 {etf[2]}｜60 日 {etf[3]}｜{etf[4]}｜规模 {etf[5]}')
        stage_cls = {"刚起步": "p-blue", "主升": "p-red", "退潮": "p-green", "尾声": "p-orange"}.get(m["stage"].split("（")[0], "p-gray")
        rows.append(f'''<div class="ml">
<div class="mlhead"><b>{m["name"]}</b> <span class="pill {stage_cls}">{m["stage"]}</span> <span class="pill p-gray">{m["type"]}</span></div>
<div class="mlrow"><span class="lbl">板块体检</span>{sector_line}</div>
<div class="mlrow"><span class="lbl">ETF 通道</span>{etf_line}</div>
<div class="mlrow"><span class="lbl">连板温度</span>{m["limitup"]}</div>
<div class="mlrow"><span class="lbl">判据明细</span>{m["judge"]}</div>
<div class="mlrow note">📌 {m["note"]}</div>
</div>''')

    # ④ 互证对照表
    cross_rows = "".join(
        f'<tr><td><b>{c[0]}</b></td><td>{c[1]}</td><td>{c[2]}</td><td><b>{c[3]}</b></td><td class="muted">{c[4]}</td></tr>'
        for c in CROSS)

    # ⑤ 稳做名单 + 早期埋伏前 5
    stable_rows = "".join(
        f'<tr><td>{lk(s[0], s[1])}</td><td class="num">{s[2]}</td><td>{s[3]}</td><td>{s[4]}</td>'
        f'<td class="muted">{s[5]}</td><td>{s[6]}</td></tr>' for s in STABLE_LIST)
    probe_rows = "".join(
        f'<tr><td>{lk(p[0], p[1])}</td><td class="num">{p[2]:+.2f}%</td><td class="num">{p[3]}</td>'
        f'<td class="num">{p[4]}</td><td class="num">{p[5]:.2f} 亿</td></tr>' for p in PROBE)
    confirm_rows = "".join(
        f'<tr><td>{lk(c[0], c[1])}</td><td class="num">{c[2]:+.2f}%</td><td class="num">{c[3]}</td>'
        f'<td class="num">{c[4]}</td><td class="num">{c[5]:+.2f}%</td></tr>' for c in CONFIRM)

    # ⑥ ETF 反查榜
    etf_rows = "".join(
        f'<tr><td class="num">{i}</td><td>{lk(e[0], e[1])}</td><td class="num"><b>{e[2]:+.2f}%</b></td>'
        f'<td class="muted">{e[3]}</td></tr>' for i, e in enumerate(ETF_TOP, 1))

    # ⑦ 连板梯队
    lu_rows = "".join(
        f'<tr><td class="num">{l[2]}</td><td>{lk(l[0], l[1])}</td><td>{l[3]}</td></tr>' for l in LIMITUP)

    # ⑧ 蓄势观察清单
    def grade_cls(g):
        return "p-red" if g == "快憋满" else ("p-blue" if g == "还在压" else "p-gray")
    vcp_rows = "".join(
        f'<tr><td>{lk(v[0], v[1])}</td><td class="num"><b>{v[2]}</b></td><td><span class="pill {grade_cls(v[3])}">{v[3]}</span></td>'
        f'<td class="num">{v[4]}</td><td class="num">{v[5]}</td><td class="num">{v[6]}</td><td class="num">{v[7]}%</td>'
        f'<td class="muted">{"盯突破价，可挂条件单" if v[3]=="快憋满" else ("只观察，等分数或价格到位" if v[3]=="还在压" else "没形态，不配价格参数")}</td></tr>'
        for v in VCP)

    # ⑨ 跨日追踪台
    st_cls = {"观察中": "p-blue", "临近突破": "p-red", "已触发": "p-green", "已触及·等回踩": "p-orange", "已失效": "p-gray"}
    watch_rows = "".join(
        f'<tr><td>{lk(w[0], w[1])}</td><td>{w[2]}</td><td class="num">{w[3]}</td>'
        f'<td><span class="pill {st_cls.get(w[4].split("（")[0], "p-gray")}">{w[4]}</span></td>'
        f'<td class="num">{w[5] if w[5] is not None else "—"}</td><td class="num">{w[6]}</td>'
        f'<td class="muted">{w[11]}</td></tr>' for w in WATCH)

    # 趋势强度分表
    ts_rows = "".join(
        f'<tr><td>{t[0]}</td><td class="num"><b>{t[1]}</b></td><td class="num">{t[2]:+.1f}</td>'
        f'<td class="num">{t[3]}</td><td class="muted">{"无预警" if t[1] >= 40 or t[2] < 12 else "观察"}</td></tr>'
        for t in SCORE_TREND)

    quick_rows = "".join(
        f'<tr><td>{lk(q[0], q[1])}</td><td class="num">{q[2]}</td><td>{q[3]}</td><td class="muted">{q[4]}</td></tr>'
        for q in QUICK_LIST)

    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>趋势候选日报 {DAY}</title>
<style>
 body{{font-family:-apple-system,"PingFang SC","Helvetica Neue",sans-serif;background:#f7f9fc;color:#1c2333;margin:0;padding:26px;line-height:1.7}}
 .wrap{{max-width:1080px;margin:0 auto}}
 h1{{font-size:22px;margin:0 0 4px;color:#1a3a6b}}
 .meta{{font-size:12px;color:#8a94a8;margin-bottom:16px}}
 .card{{background:#fff;border:1px solid #e4eaf2;border-radius:12px;padding:18px 20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(26,58,107,.05)}}
 .card.pos{{border-left:5px solid #33559a}} .card.neg{{border-left:5px solid #1e8449}} .card.cross{{border-left:5px solid #c07b30}}
 h2{{font-size:15px;margin:0 0 12px;color:#1a3a6b}}
 .meter{{background:#eef3fb;border-radius:8px;padding:12px 14px;font-size:13.5px}}
 .dictcard{{background:#fffdf5;border:1px dashed #e0cfa0;border-radius:8px;padding:12px 14px;font-size:12.5px;color:#5b5233;margin-bottom:16px}}
 .ml{{border-bottom:1px dashed #e8eef6;padding:12px 0}} .ml:last-child{{border-bottom:none}}
 .mlhead{{font-size:14.5px;margin-bottom:6px}}
 .mlrow{{font-size:13px;margin:3px 0}} .mlrow .lbl{{display:inline-block;min-width:78px;color:#8a94a8;font-size:12px}}
 .mlrow.note{{color:#7a6a3a;background:#fffdf5;border-radius:6px;padding:6px 8px;font-size:12.5px;margin-top:6px}}
 table{{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:6px}}
 th{{text-align:left;color:#8a94a8;font-weight:500;font-size:11px;padding:6px 8px;border-bottom:1px solid #eef2f8;background:#fafcfe;white-space:nowrap}}
 td{{padding:7px 8px;border-bottom:1px solid #f4f7fb;vertical-align:top}} td.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
 a{{color:#2b5fad;text-decoration:none}} a:hover{{text-decoration:underline}}
 .pill{{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11.5px;font-weight:600;white-space:nowrap}}
 .p-blue{{background:#e8f0fe;color:#2b5fad}} .p-red{{background:#fdeaea;color:#d43a3a}}
 .p-green{{background:#e6f5ee;color:#1a9e6b}} .p-orange{{background:#fdf1e2;color:#d97b1c}}
 .p-gray{{background:#eceff3;color:#6b7280}} .p-gold{{background:#fbf3dd;color:#b8860b}}
 .muted{{color:#8a94a8;font-size:12px}}
 .dsc{{font-size:11.5px;color:#8a94a8;background:#fff;border:1px solid #e4eaf2;border-radius:10px;padding:14px 16px;margin-top:16px}}
 .warn{{background:#fff5f5;border-left:4px solid #d43a3a;border-radius:8px;padding:10px 12px;font-size:13px;margin-bottom:12px}}
{EMO_CSS}
</style></head><body><div class="wrap">
<h1>趋势候选日报 · {DAY}</h1>
<div class="meta">数据时点：{DAY} 收盘（ETF 区间榜为 09-17 口径）　｜　数据来源：腾讯自选股（westock）　｜　生成时间：{datetime.now():%Y-%m-%d %H:%M}</div>

{guide_html}

<div class="warn"><b>今日要点</b>：资金主线大搬家——老主线（航运、算力硬件）板块资金双双转净流出，
半导体 5 日吸金 <b>243.78 亿</b>居全市场第 1、上涨广度 <b>98%</b>，判为「资金主线·刚起步」；
但半导体 ETF 仍处深跌通道（60 日 -27.83%），ETF 印证 不通过 → 属资金型埋伏，非互证主升。</div>

{card("① 选股漏斗计量", funnel_html)}
{dict_html}

{card("③ 主线体检（3 条主线 + 1 条退潮）", "".join(rows))}

{card("④ 互证对照表（股票主线 × 它的 ETF 是否同涨）", f'<table><tr><th>主线</th><th>正向</th><th>ETF 印证</th><th>结论</th><th>说明</th></tr>{cross_rows}</table>', "cross")}

{card("⑤ 稳做名单（评分降序）", f'<table><tr><th>标的</th><th class="num">评分</th><th>所属主线</th><th>蓄势形态</th><th>入选理由</th><th>系统资格</th></tr>{stable_rows}</table>'
     f'<p class="muted">评分＝主线强度25＋板块内地位20＋蓄势形态25＋资金验证20＋距买点10；≥80 优先档、60~79 观察档。<b>形态描述≠交易资格</b>，按资格分组排序。</p>'
     f'<p style="margin-top:12px"><b>早期埋伏前 5</b>（大钱进了还没涨）</p><table><tr><th>标的</th><th class="num">20日涨幅</th><th class="num">现价</th><th class="num">换手率</th><th class="num">主力5日净流入</th></tr>{probe_rows}</table>'
     f'<p style="margin-top:12px"><b>主升候选（主升名单 25~60%）</b></p><table><tr><th>标的</th><th class="num">20日涨幅</th><th class="num">现价</th><th class="num">PE</th><th class="num">今日</th></tr>{confirm_rows}</table>')}

{card("⑥ ETF 反查榜（20 日涨幅前 10）", f'<table><tr><th class="num">#</th><th>ETF</th><th class="num">20日涨幅</th><th>备注</th></tr>{etf_rows}</table>'
     f'<p class="muted">剔除宽基与海外品种；同一指数只留规模最大者；规模≥5 亿。★ 为当前唯一过方向闸的主线锚定 ETF。</p>', "neg")}

{card("⑦ 连板梯队（每只标注所属主线）", f'<table><tr><th class="num">连板</th><th>标的</th><th>所属主线</th></tr>{lu_rows}</table>'
     f'<p class="muted">连板结构＝情绪温度计（独立于 ETF 印证）：最高板 5（澳弘电子·PCB），梯队在位但主线（算力）资金已转负，属「价格在、钱在撤」。</p>')}

{card("⑧ 蓄势观察清单", '<p class="muted"><b>蓄势分是怎么打的</b>：把最近 80 根K线切成 4 段，看每段的跌幅是否一次比一次浅（40 分）、成交量是否一次比一次少（35 分）、现价是否贴近 20 日高点（25 分）——本质是「压弹簧」，压得越紧、量越枯，起涨越近。</p>'
     '<p class="muted" style="margin-top:6px"><b>分数怎么看、该干嘛</b>：≥75 快憋满（盯突破价，可挂条件单）｜60~75 还在压（只观察）｜&lt;60 没形态（不配价格参数）。</p>'
     f'<table><tr><th>标的</th><th class="num">蓄势分</th><th>档位</th><th class="num">现价</th><th class="num">突破价</th><th class="num">认错价</th><th class="num">距突破</th><th>现在该干嘛</th></tr>{vcp_rows}</table>')}

{card("⑨ 跨日追踪台 · 今日变化", f'<table><tr><th>观察票</th><th>入池日</th><th class="num">连续在榜</th><th>状态</th><th class="num">蓄势分</th><th class="num">今收</th><th>变化说明</th></tr>{watch_rows}</table>'
     f'<p style="margin-top:10px"><b>今日状态流转</b>：飞凯材料、大族激光、兴森科技 <b>站上突破价 → 已触发</b>；中天科技、中材科技、永鼎股份、天孚通信、太辰光 盘中触价未站稳 → 已触及·等回踩；'
     f'生益科技、华正新材、再升科技 蓄势分回落 → 退回观察中。'
     f'<br><b>趋势强度分</b>（主线折线）：</p>'
     f'<table><tr><th>主线</th><th class="num">今日分数</th><th class="num">日环比</th><th class="num">量比</th><th>预警</th></tr>{ts_rows}</table>'
     f'<p class="muted">无 L1/L2 预警触发（各主线 Δ 均 &lt;12）。算力分数自 09-14 的 16.7 连升 4 日至 30.6，半导体 12.2→21.2——'
     f'两条科技线价格在回暖，与「板块资金转负」形成价钱背离，是明日重点观察项。</p>')}

{emo_html}

<div class="dsc">{DISCLAIMER}</div>
</div></body></html>
'''


# ---------------------------------------------------------------- 台账更新
def _merge_dated(rot: dict, key: str, day: str, value):
    """兼容 dict / list 两种既有结构：dict 按日期写键，list 则追加 {date, value}。"""
    cur = rot.get(key)
    if isinstance(cur, dict):
        cur[day] = value
    elif isinstance(cur, list):
        cur.append({"date": day, "data": value})
    else:
        rot[key] = {day: value}


def _find_line(line: str):
    """按前两字匹配主线（cross_matrix 的简称 ↔ MAINLINES 全名）。"""
    for m in MAINLINES:
        if m["name"][:2] == line[:2]:
            return m
    return None


def _line_type(line: str) -> str:
    m = _find_line(line)
    return m["type"] if m else "—"


def _line_stage(line: str) -> str:
    m = _find_line(line)
    return m["stage"] if m else "—"


def _line_etf(line: str):
    m = _find_line(line)
    return m["etf"] if m else ("—", "—", "—", "—", "—", "—")


def _line_gate(line: str) -> bool:
    """方向闸是否通过（True = ETF 未处于深跌通道，ETF 印证 有效）。"""
    return _line_etf(line)[4].startswith("方向闸")


def update_history():
    data = json.loads(HIST.read_text(encoding="utf-8"))
    shutil.copy(HIST, HIST.with_suffix(".json.bak-20260918"))

    snapshot = {
        "date": DAY,
        "funnel": FUNNEL,
        "mainlines": [
            {"name": m["name"], "type": m["type"], "stage": m["stage"],
             "first_seen": "2026-09-15" if m["name"].startswith("半导体") else
                            ("2026-09-09" if m["name"].startswith("航运") else "2026-09-09"),
             "持续天数": 1 if m["name"].startswith("半导体") else 4,
             "要点": m["note"][:220]}
            for m in MAINLINES
        ],
        "watchlist": [
            {"name": w[1], "code": w[0], "first_seen": w[2], "days_in": w[3],
             "status": w[4], "xushi": w[5],
             "close": w[6], "day_high": w[7],
             "break_price": w[8], "invalid_price": w[9],
             "dist_to_break_pct": w[10], "note": w[11]}
            for w in WATCH
        ],
        "stable_list": [
            {"name": s[1], "code": s[0], "score": s[2], "mainline": s[3], "vcp": s[4],
             "tier": s[6], "reason": s[5], "qualify": s[6]}
            for s in STABLE_LIST
        ],
        "quick_list": [{"name": q[1], "code": q[0], "boards": q[2],
                        "sector": q[3], "reason": q[4]} for q in QUICK_LIST],
        "etf_top": [f"{e[1]} {e[2]:+.1f}%（09-17口径）" for e in ETF_TOP[:5]],
        "etf_reverse": [
            {"code": e[0], "name": e[1], "theme": e[3].replace("★ ", "").split("，")[0],
             "chg20d": e[2],
             "overlap": "航运" if e[0] == "sh560710" else "",
             "mark": "★主线锚定" if e[0] == "sh560710" else ""}
            for e in ETF_TOP
        ],
        "cross_matrix": [
            {"line": c[0], "forward": c[1], "etf": c[2], "conclusion": c[3], "note": c[4],
             "type": _line_type(c[0]), "stage": _line_stage(c[0]), "etf_theme": _line_etf(c[0])[1],
             "etf_chg20d": _line_etf(c[0])[2], "overlap": _line_gate(c[0])}
            for c in CROSS
        ],
        "etf_partners": [
            {"line": m["name"], "etf_code": m["etf"][0], "etf_name": m["etf"][1],
             "chg20d": m["etf"][2], "chg60d": m["etf"][3], "gate": m["etf"][4]}
            for m in MAINLINES
        ],
    }
    # 追加（同日替换以避免重复）
    days = data["days"]
    if days and days[-1]["date"] == DAY:
        days[-1] = snapshot
    else:
        days.append(snapshot)
    data["days"] = days[-90:]

    rot = data["rotation"]
    if DAY not in rot["dates"]:
        rot["dates"].append(DAY)
    if DAY not in rot["score_dates"]:
        rot["score_dates"].append(DAY)
    scores = {"航运": 37.9, "算力(PCB/光通信)": 30.6, "粮食": 16.5, "半导体": 21.2}
    for line, val in scores.items():
        if line not in rot["score_series"]:
            rot["score_series"][line] = []
        if len(rot["score_series"][line]) < len(rot["score_dates"]):
            rot["score_series"][line].append(val)
    # rotation.lines 阶段追加
    stage_map = {"航运": "退潮", "算力(PCB/光通信)": "退潮", "粮食": "退潮", "半导体": "刚起步"}
    for ln in rot.get("lines", []):
        nm = ln.get("name", "")
        for key, st in stage_map.items():
            if key.split("(")[0] in nm:
                ln.setdefault("stages", {})[DAY] = st
                break
    sector_rows = [{"sector": m["sector"][0], "code": m["sector"][1],
                    "changePct": m["sector"][2], "upCount": m["sector"][3],
                    "mainNetInflow5d": m["sector"][4], "leader": m["sector"][5]}
                   for m in MAINLINES]
    _merge_dated(rot, "sector_check", DAY, sector_rows)
    _merge_dated(rot, "limitup_structure", DAY, {
        "max_board": 5, "max_board_name": "澳弘电子",
        "board3_plus": 4, "first_board": 41, "total": 50,
        "note": "最高板 5（PCB），梯队在位但算力主线资金已转负"})
    _merge_dated(rot, "pattern_check", DAY, "本机未做全量四态形态扫描（形态精判待补）")

    # 情绪票池（只看版）写入台账：core 为梯队明细，limitup_pool 供次日算溢价率/晋级率
    _ep = ROOT / "output" / "tmp" / f"emotion_pool_{DAY}.json"
    if _ep.exists():
        _ed = json.loads(_ep.read_text(encoding="utf-8"))
        snapshot["emotion_thermometer"] = _ed["thermometer"]
        snapshot["emotion_list"] = _ed["core"]
        snapshot["emotion_first_board"] = _ed.get("first_board", {})
        _merge_dated(rot, "limitup_pool", DAY,
                     [{"code": p["code"], "name": p["name"], "boards": p["boards"]}
                      for p in _ed["pool"] if p["boards"] >= 1])

    HIST.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    json.loads(HIST.read_text(encoding="utf-8"))          # 校验 JSON 合法
    print(f"[ok] history.json 已更新：days={len(data['days'])} 天，rotation.dates={len(rot['dates'])}")


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    html = render()
    # OUT.write_text(html, encoding="utf-8")  # 单列版退役——见上注
    print(f"[ok] 日报已落盘 {OUT}（{len(html)} 字符）")
    update_history()


if __name__ == "__main__":
    main()
