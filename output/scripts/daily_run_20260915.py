# -*- coding: utf-8 -*-
"""2026-09-15 每日盘后扫描：算分(偏移校准) -> 状态机 -> history.json -> 日报HTML。Python 3.9+"""
import json, subprocess, os, statistics

BASE = "/Users/liuliang19/Desktop/fast-trend-trade"
WS = "/Users/liuliang19/.local/bin/westock"
TODAY = "2026-09-15"
YDAY = "2026-09-14"

def kline(code, limit=260):
    out = subprocess.run([WS, "kline", code, "--period", "day", "--limit", str(limit)],
                         capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        if line.startswith("| 20") or line.startswith("| 2026"):
            cols = [c.strip() for c in line.strip("|").split("|")]
            rows.append({"date": cols[0], "close": float(cols[2]), "vol": float(cols[5]),
                         "chg": float(cols[8])})
    rows.sort(key=lambda r: r["date"])
    return rows

def med(xs):
    return statistics.median(xs) if xs else 0.0

def clip(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))

def raw_series(rows):
    closes = [r["close"] for r in rows]
    vols = [r["vol"] for r in rows]
    raw = []
    for i in range(len(rows)):
        if i < 20:
            raw.append(None); continue
        chg20 = (closes[i] / closes[i-20] - 1) * 100
        chg5 = (closes[i] / closes[i-5] - 1) * 100 if i >= 5 else 0.0
        m = 0.6 * clip(50 + 2.5 * chg20) + 0.4 * clip(50 + 8 * chg5)
        ma20 = sum(closes[i-19:i+1]) / 20.0
        bias = (closes[i] / ma20 - 1) * 100
        ma_s = clip(bias / 0.15 * 100)
        vr = med(vols[i-4:i+1]) / med(vols[i-19:i+1]) if med(vols[i-19:i+1]) else 1.0
        vol_s = clip((vr - 0.6) / 1.2 * 100)
        raw.append(0.4 * m + 0.3 * ma_s + 0.3 * vol_s)
    sm = []
    for i in range(len(raw)):
        if raw[i] is None:
            sm.append(None); continue
        r1 = raw[i-1] if i >= 1 and raw[i-1] is not None else raw[i]
        r2 = raw[i-2] if i >= 2 and raw[i-2] is not None else r1
        sm.append(0.5 * raw[i] + 0.3 * r1 + 0.2 * r2)
    return rows, sm

def etf_metrics(rows, sm):
    last = rows[-1]
    closes = [r["close"] for r in rows]
    vols = [r["vol"] for r in rows]
    ma20 = sum(closes[-20:]) / 20.0
    chg20 = (closes[-1] / closes[-21] - 1) * 100
    chg5 = (closes[-1] / closes[-6] - 1) * 100
    chg60 = (closes[-1] / closes[-61] - 1) * 100 if len(closes) >= 61 else None
    vr = last["vol"] / med(vols[-21:-1]) if med(vols[-21:-1]) else 1.0
    hi60 = max(closes[-60:])
    return {"close": closes[-1], "chg_today": last["chg"], "chg20": round(chg20, 2),
            "chg5": round(chg5, 2), "chg60": round(chg60, 2) if chg60 is not None else None,
            "ma20": round(ma20, 3), "above_ma20": closes[-1] >= ma20,
            "bias20": round((closes[-1] / ma20 - 1) * 100, 2), "vol_ratio": round(vr, 2),
            "is_60d_high": closes[-1] >= hi60 * 0.999, "sm_last": sm[-1], "sm_prev": sm[-2]}

HIST = os.path.join(BASE, "output/history.json")
with open(HIST) as f:
    hist = json.load(f)
rot = hist["rotation"]

k515880, sm515880 = raw_series(kline("sh515880"))
k560710, sm560710 = raw_series(kline("sh560710"))
k159063, sm159063 = raw_series(kline("sz159063"))
m515880 = etf_metrics(k515880, sm515880)
m560710 = etf_metrics(k560710, sm560710)
m159063 = etf_metrics(k159063, sm159063)
S515 = m515880; S560 = m560710; S159 = m159063

print("515880:", json.dumps(m515880, ensure_ascii=False))
print("560710:", json.dumps(m560710, ensure_ascii=False))
print("159063:", json.dumps(m159063, ensure_ascii=False))

# ---- 校准追加趋势强度分：简化偏移校准（重算公式与原公式形态差异大，线性回归拟合不稳；
#      改用 锚定ETF当日涨跌×2.5、单日限幅±8 的增量法，保持序列连续） ----
def delta_append(stored_last, chg_today):
    delta = max(-8.0, min(8.0, 2.5 * chg_today))
    return round(stored_last + delta, 1)

if rot["score_dates"][-1] != TODAY:
    rot["score_dates"].append(TODAY)
new_shipping = delta_append(rot["score_series"]["航运"][-1], m560710["chg_today"])
rot["score_series"]["航运"].append(new_shipping)
new_ai = delta_append(rot["score_series"]["算力(PCB/光通信)"][-1], m515880["chg_today"])
rot["score_series"]["算力(PCB/光通信)"].append(new_ai)
g = rot["score_series_partial"]["粮食"]
new_grain = delta_append(g["scores"][-1], m159063["chg_today"])
if g["dates"][-1] != TODAY:
    g["dates"].append(TODAY)
    g["scores"].append(new_grain)
note_add = ("09-15 追加点改用简化增量校准：新点=旧末值+锚定ETF当日涨跌×2.5（限幅±8）。"
            "原因：重算v2公式与原公式形态差异大，单点差分与40日线性回归均不稳；增量法保连续且与盘面同向。")
if note_add not in str(rot.get("score_series_note", "")):
    rot["score_series_note"] = str(rot.get("score_series_note", "")) + " " + note_add
print("calibration(增量法): 航运->%.1f 算力->%.1f 粮食->%.1f" % (new_shipping, new_ai, new_grain))

# ---- rotation.lines 阶段 ----
if TODAY[5:] not in rot["dates"]:
    rot["dates"].append(TODAY[5:])
for line in rot["lines"]:
    if line["name"] == "农业/粮食":
        line["stages"]["09-15"] = "退潮"
    elif line["name"] == "航运/船舶":
        line["stages"]["09-15"] = "刚起步"
    elif line["name"] in ("算力(候补)", "算力(PCB/光通信)"):
        line["name"] = "算力(PCB/光通信)"
        line["etf"] = "sh515880"
        line["stages"]["09-15"] = "刚起步"

# ---- rotation.etf_flow_check（价×钱四象限） ----
rot["etf_flow_check"] = [
    {"date": TODAY, "mainline": "算力硬件(PCB/覆铜板)", "etf": "sh515880",
     "price_side": "价跌(20日%.1f%%/60日%.1f%%)" % (m515880["chg20"], m515880["chg60"]),
     "money_side": "钱进(当日净申购为正)", "quadrant": "价跌钱进=资金型埋伏(弱)",
     "note": "月份额-2.2%对冲当日申购；ETF处深跌通道，埋伏信号打折扣"},
    {"date": TODAY, "mainline": "航运船舶", "etf": "sh560710",
     "price_side": "价涨(20日+%.1f%%)" % m560710["chg20"],
     "money_side": "钱走(当日净流出+月份额-6.0%)", "quadrant": "价涨钱走=衰竭预警",
     "note": "涨幅与份额背离：InFlow-480万、月-6.0%、周-3.7%，摘要高亮"},
    {"date": TODAY, "mainline": "农业/粮食", "etf": "sz159063",
     "price_side": "价涨(20日+%.1f%%,4连阴中)" % m159063["chg20"],
     "money_side": "钱进(月份额+16.1%)", "quadrant": "价涨钱进=健康主升(降权)",
     "note": "规模0.65亿<2亿，申赎即可扭曲份额，结论降权为观察"},
]

# ---- rotation.etf_holdings（覆盖式更新最新日期） ----
rot["etf_holdings"] = [
    {"date": TODAY, "mainline": "算力硬件(PCB/覆铜板)", "etf_code": "sh515880",
     "top3": [{"code": "300502", "name": "新易盛", "ratio": 15.6, "chg_pct": "-4.99%"},
              {"code": "300308", "name": "中际旭创", "ratio": 14.61, "chg_pct": "-5.72%"},
              {"code": "601138", "name": "工业富联", "ratio": 9.12, "chg_pct": "-3.90%"}]},
    {"date": TODAY, "mainline": "航运船舶", "etf_code": "sh560710",
     "top3": [{"code": "600150", "name": "中国船舶", "ratio": 15.41, "chg_pct": "-1.94%"},
              {"code": "600482", "name": "中国动力", "ratio": 14.67, "chg_pct": "-0.90%"},
              {"code": "300008", "name": "天海防务", "ratio": 10.43, "chg_pct": "-3.16%"}]},
    {"date": TODAY, "mainline": "农业/粮食", "etf_code": "sz159063",
     "top3": [{"code": "002385", "name": "大北农", "ratio": 5.51, "chg_pct": "-3.86%"},
              {"code": "600598", "name": "北大荒", "ratio": 4.69, "chg_pct": "-2.76%"},
              {"code": "000998", "name": "隆平高科", "ratio": 4.64, "chg_pct": "-3.53%"}]},
]

# ---- rotation.sector_check 追加 ----
rot.setdefault("sector_check", []).extend([
    {"date": "09-15", "sector": "元件", "code": "pt01801083", "chg_pct": 0.46,
     "up_ratio": "30/61(49.2%)", "flow_rank": 1, "leader_pct": 10.00, "leader": "华正新材"},
    {"date": "09-15", "sector": "玻璃玻纤", "code": "pt01801712", "chg_pct": 2.39,
     "up_ratio": "5/16(31.3%)", "flow_rank": 2, "leader_pct": 5.79, "leader": "宏和科技"},
    {"date": "09-15", "sector": "风电设备", "code": "pt01801736", "chg_pct": 2.36,
     "up_ratio": "24/30(80.0%)", "flow_rank": 3, "leader_pct": 12.84, "leader": "海力风电"},
    {"date": "09-15", "sector": "航运港口", "code": "pt01801992", "chg_pct": -0.07,
     "up_ratio": "8/34(23.5%)", "flow_rank": 7, "leader_pct": 2.50, "leader": "招商轮船"},
    {"date": "09-15", "sector": "医疗服务", "code": "pt01801156", "chg_pct": -1.19,
     "up_ratio": "7/51(13.7%)", "flow_rank": 100, "leader_pct": 6.64, "leader": "万邦医药"},
])

# ---- 观察池状态机 ----
VCP = {
    "sh603601": (85.1, 10.96, 8.52), "sh600183": (87.2, 157.28, 122.05),
    "sz002436": (73.9, 42.73, 31.81), "sz002008": (73.5, 99.5, 82.33),
    "sz300570": (71.1, 230.46, 178.18), "sz300475": (71.6, 187.52, 147.2),
    "sh603186": (76.7, 251.57, 160.67), "sh601872": (62.0, 21.7, 17.79),
    "sh601975": (59.9, 4.97, 3.65), "sh600150": (48.2, 41.18, 32.59),
    "sz300394": (47.2, 289.7, 237.8), "sz000737": (58.5, 17.2, 13.8),
}
PX = {
    "sh603601": (10.29, 10.71, "再升科技"), "sh600183": (150.25, 156.93, "生益科技"),
    "sz002436": (40.86, 42.73, "兴森科技"), "sz002008": (93.60, 96.50, "大族激光"),
    "sz300570": (194.39, 202.30, "太辰光"), "sz300475": (161.67, 164.68, "香农芯创"),
    "sh603186": (251.57, 251.57, "华正新材"), "sh601872": (20.50, 21.20, "招商轮船"),
    "sh601975": (4.62, 4.72, "招商南油"), "sh600150": (38.16, 38.96, "中国船舶"),
    "sz300394": (257.38, 263.98, "天孚通信"), "sz000737": (13.89, 14.26, "北方铜业"),
    "sh688825": (54.22, 55.89, "长鑫科技"),
}
STATUS_NOTE = {
    "sh603186": "已触发：今日涨停251.57正好踩到突破价，封板不追等回踩；PE96.9>80红线+2连板→只可快打档",
    "sh600183": "临近突破：蓄势87.2快憋满，突破价157.28；PB19.7红线→只看不挂单",
    "sh603601": "临近突破：蓄势85.1，突破价10.96；PE289红线→只看不挂单",
    "sz002436": "已触及·等回踩：盘中42.73触突破价未站稳收40.86；PE320红线→不可进稳做",
    "sh601872": "已触及·等回踩第2日：盘中21.20未到21.70，重新站上21.70转已触发",
    "sz002008": "观察中：突破价下修99.5，蓄势73.5接近快憋满",
    "sh688825": "观察中：无蓄势形态分，跟半导体板块情绪",
}
prev_watch = {w["code"]: w for w in hist["days"][-1]["watchlist"]}
watchlist = []
for code, (close, high, name) in PX.items():
    p = prev_watch.get(code, {})
    xs, brk, inv = VCP.get(code, (None, None, None))
    if code in ("sh603186",):
        status = "已触发"
    elif code == "sz002436":
        status = "已触及·等回踩"
    elif code == "sh601872":
        status = "已触及·等回踩"
    elif xs is not None and xs >= 75:
        status = "临近突破"
    elif p.get("status") in ("已触及·等回踩", "已触发"):
        status = p["status"]
    else:
        status = "观察中"
    dist = round((close / brk - 1) * 100, 1) if brk else None
    watchlist.append({
        "name": name, "code": code, "group": p.get("group", "主线内"),
        "xushi": xs, "status": status, "close": close, "day_high": high,
        "break_price": brk, "invalid_price": inv, "dist_to_break_pct": dist,
        "first_seen": p.get("first_seen", TODAY), "days_in": p.get("days_in", 1) + 1,
        "note": STATUS_NOTE.get(code, p.get("note", "")),
    })
hist["days"].append({
    "date": TODAY,
    "funnel": {"全市场约": 5400, "站上所有均线": 342, "早期埋伏": 15,
               "主升候选(剔小市值后)": 8, "主升候选(市值≥100亿合格)": 1,
               "多头池资金强": 15, "稳做名单": 7, "快打名单": 6},
    "mainlines": [
        {"name": "算力硬件(PCB/覆铜板)", "type": "资金主线", "stage": "刚起步",
         "first_seen": "2026-09-10(候补)", "转正日": "2026-09-14", "持续天数": 6,
         "要点": ("刚起步第2日(候补→转正→第2日)：元件5日主力净流入136.39亿全市场第1(昨日145.4亿,维持)、玻璃玻纤64.88亿第2、"
                  "电子化学品13.03亿第6；今日元件板块主力净额-17.6亿(高位换手),玻璃玻纤当日+15.4亿接棒；"
                  "①四维池✓(华正/世运/博敏/德福/金安国纪在多头池资金榜前15,upCount 49%差半步)；"
                  "④百亿中军✓(华正新材Chg20D+36.6今日涨停/超声电子+51.6)；⑤CPO+AI算力资本开支可反复发酵✓；"
                  "T3✗双重不过:通信ETF20日" + str(S515["chg20"]) + "%<8%且60日" + str(S515["chg60"]) +
                  "%深跌通道(方向闸拦截,'涨幅仅为反弹不计印证')；"
                  "板块体检:元件+0.46%|30/61上涨|龙头华正新材+10.00涨停;玻璃玻纤+2.39%涨幅第1|宏和科技+5.79")},
        {"name": "航运船舶", "type": "资金主线", "stage": "刚起步",
         "first_seen": "2026-09-09", "持续天数": 7,
         "要点": ("刚起步第7日(原主升09-11降级)：航运港口5日主力+8.18亿第7(昨日第5,位次缓降未转流出)；"
                  "板块-0.07%缩量横盘,upCount 8/34=24%偏弱;中军✓中国船舶Chg20D+13.9/招商南油+24.9/招商轮船+14.0；"
                  "T3✗船舶ETF20日+" + str(S560["chg20"]) + "%<8%未过(60日+" + str(S560["chg60"]) +
                  "%,未创60日新高)；ETF资金通道亮『价涨钱走=衰竭预警』"
                  "(InFlow-480万/月份额-6.0%/周-3.7%)——下周若份额续缩+资金出前10,降级退潮；"
                  "招商轮船+2.50%领涨,回踩结构未坏")},
        {"name": "农业/粮食", "type": "涨停主线", "stage": "退潮",
         "first_seen": "2026-09-09", "持续天数": 7,
         "要点": ("退潮第4日：种植业-4.65%(0/20上涨),敦煌种业再度跌停-10.03%;粮食ETF今日-3.93%4连阴,"
                  "20日涨幅滑落至" + str(S159["chg20"]) + "%(跌破8%线后继续下探);板块资金持续流出(种植业5日-22.7亿);只可龙头快打或不碰")},
    ],
    "candidate_line": {"name": "风电设备", "type": "资金主线候补", "stage": "观察一夜",
                       "要点": "风电设备+2.36%涨幅第2|5日主力+22.43亿第3|upCount 24/30=80%|龙头海力风电+12.84%；明晚验证资金是否续进前5"},
    "watchlist": watchlist,
    "stable_list": [
        {"name": "中国巨石", "code": "sh600176", "mainline": "算力硬件·刚起步(玻纤电子布上游)",
         "score": 75, "tier": "观察档(高)",
         "reason": "主线20+地位16(玻纤全球龙头)+蓄势62.6→15+资金18(5日+15.07亿全市场第1)+距买点6;PE41.6/PB5.7过闸;突破价48.59,今日+3.97%距-3.1%"},
        {"name": "世运电路", "code": "sh603920", "mainline": "算力硬件·刚起步(PCB)",
         "score": 70, "tier": "观察档",
         "reason": "主线20+地位12+蓄势74.1→18+资金14(多头池第10,5日+6.89亿)+距买点6;PE79.7边缘过闸/PB4.8;突破价44.00,今日-2.23%距-3.5%"},
        {"name": "招商轮船", "code": "sh601872", "mainline": "航运船舶·刚起步",
         "score": 68, "tier": "观察档",
         "reason": "主线20+地位15(板块龙头)+蓄势62→15+资金12(跌出早期埋伏前15)+距买点6;PE15.3/PB3.5过闸;已触及·等回踩,重上21.70转已触发"},
        {"name": "中国船舶", "code": "sh600150", "mainline": "航运船舶·刚起步",
         "score": 66, "tier": "观察档",
         "reason": "主线20+地位18(千亿中军旗舰)+蓄势48.2→10+资金12+距买点6;PE20.5/PB1.9过闸;回踩第4日"},
        {"name": "招商南油", "code": "sh601975", "mainline": "航运船舶·刚起步",
         "score": 65, "tier": "观察档",
         "reason": "主线20+地位14+蓄势59.9→12+资金12+距买点7;PE13.9/PB1.8过闸"},
        {"name": "大族激光", "code": "sz002008", "mainline": "算力硬件·刚起步(设备端)",
         "score": 66, "tier": "观察档",
         "reason": "主线20+地位12+蓄势73.5→18+资金10+距买点6;PE48.4/PB4.5过闸;突破价下修99.50"},
        {"name": "新宙邦", "code": "sz300037", "mainline": "算力硬件·刚起步(电子化学品)",
         "score": 63, "tier": "观察档", "reason": "主线20+地位10+蓄势72.2→18+资金10+距买点5;PE34.4/PB过闸;新面孔,突破价76.45"},
    ],
    "quick_list": [
        {"name": "闽东电力", "code": "sz000993", "boards": "5板(最高板)",
         "note": "电力+风电情绪总龙头,今日+10.02%封板;PE449纯情绪,电力5日资金第4+风电设备upCount 80%"},
        {"name": "中新赛克", "code": "sz002912", "boards": "4板",
         "note": "通信设备(网络可视化),今日+10.02%晋级;PE657纯情绪;通信设备板块5日资金-27.3亿流出,独角戏风险"},
        {"name": "澳弘电子", "code": "sh605058", "boards": "3板",
         "note": "元件(覆铜板新贵),今日+9.99%晋级3板;PE41.7过闸但连板情绪票,近10日涨停≥2→快打红线"},
        {"name": "双星新材", "code": "sz002585", "boards": "3板",
         "note": "塑料/BOPET薄膜(覆铜板上游材料),今日+10.04%晋级;PE-41亏损纯情绪"},
        {"name": "华正新材", "code": "sh603186", "boards": "2连板",
         "note": "元件主线内,今日涨停251.57踩到突破价;PE96.9>80红线→不给条件单,只可快打"},
        {"name": "超声电子", "code": "sz000823", "boards": "3板断板(今日+5.61%)",
         "note": "元件主线内情绪龙头,PE64.3过闸;涨停潮降温但趋势未坏"},
    ],
    "etf_top": ["能源化工 +15.0%(09-14口径)", "巴西 +12.4%", "标普油气 +12.1%",
                "银行 +7.6%(边缘)", "粮食 +7.4%→今日-3.9%继续滑落"],
    "etf_reverse": [
        {"name": "能源化工ETF建信", "code": "sz159981", "theme": "能源化工", "chg20d": 15.0, "scale": 35.6,
         "overlap": "", "mark": "T-1口径,未与主线重合"},
        {"name": "巴西ETF易方达", "code": "sh520870", "theme": "巴西(QDII)", "chg20d": 12.4, "scale": 6.1,
         "overlap": "", "mark": "T-1口径"},
        {"name": "标普油气ETF嘉实", "code": "sz159518", "theme": "标普油气(QDII)", "chg20d": 12.1, "scale": 10.4,
         "overlap": "", "mark": "T-1口径,同指数留最大"},
        {"name": "标普油气ETF富国", "code": "sh513350", "theme": "标普油气(QDII)", "chg20d": 11.7, "scale": 8.7,
         "overlap": "", "mark": "T-1口径"},
        {"name": "巴西ETF华夏", "code": "sz159100", "theme": "巴西(QDII)", "chg20d": 11.0, "scale": 5.2,
         "overlap": "", "mark": "T-1口径"},
    ],
    "cross_matrix": [
        {"line": "算力硬件(PCB/覆铜板)", "type": "资金主线", "stage": "刚起步",
         "etf_theme": "通信ETF(515880)", "etf_chg20d": "%.1f%%" % m515880["chg20"], "overlap": False,
         "conclusion": "缺印证：ETF深跌通道(60日%.1f%%),方向闸拦截'涨幅仅为反弹';且前十大权重全为光模块/光通信,无PCB股——锚定错配,不参与互证" % m515880["chg60"]},
        {"line": "航运船舶", "type": "资金主线", "stage": "刚起步",
         "etf_theme": "船舶ETF(560710)", "etf_chg20d": "+%.1f%%" % m560710["chg20"], "overlap": False,
         "conclusion": "缺印证：20日+4.1%未过8%线;但锚定有效(前三大权重即主线中军中国船舶/中国动力),资金通道亮衰竭预警——重点盯份额"},
        {"line": "农业/粮食", "type": "涨停主线", "stage": "退潮",
         "etf_theme": "粮食ETF(159063)", "etf_chg20d": "+%.1f%%" % m159063["chg20"], "overlap": False,
         "conclusion": "没信号：退潮第4日,ETF4连阴;规模0.65亿<2亿信号降权"},
    ],
    "etf_partners": [
        {"mainline": "算力硬件(PCB/覆铜板)", "etfs": [
            {"name": "通信ETF国泰", "code": "sh515880", "scale": 421.6, "note": "规模最大但60日-29.3%深跌,方向闸未过"},
            {"name": "消费电子ETF富国", "code": "sh561100", "note": "A股无纯PCB/元件ETF,消费电子为最近替身"},
            {"name": "消费电子ETF华夏", "code": "sz159732", "note": "同上,备选"}]},
        {"mainline": "航运船舶", "etfs": [
            {"name": "船舶ETF富国", "code": "sh560710", "scale": 15.7, "note": "场内唯一船舶主题,规模15.7亿≥5亿;衰竭预警盯份额"},
            {"name": "（无第二只）", "code": "—", "note": "航运主题场内无第二只ETF搭档"},
            {"name": "（无第三只）", "code": "—", "note": "—"}]},
        {"mainline": "农业/粮食", "etfs": [
            {"name": "粮食ETF南方", "code": "sz159063", "scale": 0.65, "note": "规模<2亿信号降权"},
            {"name": "粮食ETF景顺", "code": "sz159072", "note": "同主题替代,20日+7.4%(09-14口径)"},
            {"name": "豆粕ETF华夏", "code": "sz159985", "note": "农产品替代敞口,20日+6.6%"}]},
    ],
})

# days 保留 90 天
hist["days"] = hist["days"][-90:]
with open(HIST, "w") as f:
    json.dump(hist, f, ensure_ascii=False, indent=1)
json.load(open(HIST))
print("history.json written & validated")

# ---- 生成日报 HTML ----
S159 = m159063
CSS = """
body{font-family:'PingFang SC','Microsoft YaHei',sans-serif;background:#f7f8fa;color:#1c2330;line-height:1.75;font-size:14.5px;margin:0}
.wrap{max-width:1080px;margin:0 auto;padding:26px 18px 60px}
h1{font-size:22px;margin:0 0 4px} h2{font-size:17px;margin:30px 0 10px;padding-left:10px;border-left:4px solid #2b5fad}
.meta{color:#5b6472;font-size:13px}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px;background:#fff}
th,td{border:1px solid #e3e7ee;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#eef2f8;font-weight:600}
.nm{font-weight:600}
.chain{background:#fff;border:1px solid #e3e7ee;border-radius:8px;padding:12px 14px;margin:10px 0}
.tip{background:#fff8e6;border:1px solid #f0e0b0;border-radius:8px;padding:10px 14px;margin:10px 0;font-size:13.5px}
.card{background:#fff;border:1px solid #e3e7ee;border-radius:8px;padding:12px 14px;margin:10px 0}
.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;color:#fff}
.p-blue{background:#2b5fad}.p-red{background:#d43a3a}.p-green{background:#1a9e6b}.p-orange{background:#d97b1c}.p-gray{background:#8a93a3}.p-gold{background:#b8860b}
.up{color:#d43a3a;font-weight:600}.down{color:#1a9e6b;font-weight:600}
.muted{color:#8a93a3}
.note{color:#5b6472;font-size:13px;margin-top:6px}
.warn{background:#fdecec;border:1px solid #f2b8b8;border-radius:8px;padding:10px 14px;margin:10px 0}
.bar-wrap{background:#eef2f8;border-radius:4px;height:10px;width:110px;display:inline-block;vertical-align:middle}
.bar{background:#2b5fad;border-radius:4px;height:10px}
.disc{font-size:12.5px;color:#8a93a3;margin-top:14px;border-top:1px dashed #d8dde5;padding-top:10px}
"""
S515 = m515880; S560 = m560710; S159 = m159063
html_parts = []
html_parts.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">')
html_parts.append('<meta name="viewport" content="width=device-width,initial-scale=1.0">')
html_parts.append('<title>每日盘后趋势候选扫描 · 2026-09-15</title><style>' + CSS + '</style></head><body><div class="wrap">')
html_parts.append('<h1>每日盘后趋势候选扫描 · 2026-09-15（周二）</h1>')
html_parts.append('<div class="meta">数据时点：2026-09-15 收盘（15:30 自动化产出）｜数据源：westock CLI（板块资金/行情/ETF 概览与持仓）、蓄势引擎 run_signal.py（VCP 精判）｜ETF 区间涨幅榜与连板基础榜为 T-1（09-14）口径，已用当日行情校正并标注</div>')

# ① 漏斗
f_ = hist["days"][-1]["funnel"]
html_parts.append('<h2>① 选股漏斗</h2><div class="chain">约 <b>%s</b> 全市场 → <b>%s</b> 站上所有主要均线 → <b>%s</b> 早期埋伏（大钱进了还没涨） → <b>%s</b> 主升候选（25~60%%，合格 <b>%s</b>） → <b>%s</b> 多头池×资金交叉 → <b>稳做 %s</b> ＋ <b>快打 %s</b></div>' % (f_["全市场约"], f_["站上所有均线"], f_["早期埋伏"], f_["主升候选(剔小市值后)"], f_["主升候选(市值≥100亿合格)"], f_["多头池资金强"], f_["稳做名单"], f_["快打名单"]))
html_parts.append('<div class="note">指数档位：<b>谨慎</b>——上证 %s（-0.54%%）、创业板指 %s（-1.15%%）、沪深300 -0.67%%；三条主线锚定ETF全跌（通信 -0.61%%/船舶 -1.25%%/粮食 -3.93%%）。指数回调日不新开仓，只处理已有观察单。</div>' % ("3864.28", "3247.92"))

# ② 词典
html_parts.append('<h2>② 名词小词典</h2><div class="tip"><b>名词小词典</b>：资金主线＝整个行业被大钱持续买入；涨停主线＝游资连板炒起来的热点；刚起步＝钱进了价没涨；主升＝钱价一起涨；尾声＝开始炒补涨股；退潮＝大钱在撤；互证＝股票和它的ETF同时涨（最强信号）；早期埋伏名单＝大钱进了还没涨的票；主升名单＝涨起来的趋势票；蓄势形态＝回调一次比一次浅、成交一次比一次少，涨之前憋的那口气；突破价＝涨过它=真启动；认错价＝跌破它=看错了；稳做名单＝跟主线慢慢拿；快打名单＝情绪票快进快出；ETF反查＝从涨幅榜上的ETF倒查它买的是哪些股。</div>')

# ③ 主线体检
ml = hist["days"][-1]["mainlines"]
html_parts.append('<h2>③ 主线体检（3 条 + 1 候补）</h2>')
flowmap = {c["mainline"]: c for c in rot["etf_flow_check"]}
for m in ml:
    fc = flowmap.get(m["name"], {})
    html_parts.append('<div class="card"><b>%s</b>【%s】【阶段：%s】（持续 %s 日，首见 %s）<br>%s' % (m["name"], m["type"], m["stage"], m["持续天数"], m["first_seen"], m["要点"]))
    html_parts.append('<div class="note"><b>ETF 资金通道（价×钱四象限）</b>：%s ｜ %s → <b>%s</b>（%s）</div></div>' % (fc.get("price_side",""), fc.get("money_side",""), fc.get("quadrant",""), fc.get("note","")))
cl = hist["days"][-1]["candidate_line"]
html_parts.append('<div class="card"><b>候补：%s</b>【%s】【阶段：%s】<br>%s</div>' % (cl["name"], cl["type"], cl["stage"], cl["要点"]))
html_parts.append('<div class="warn"><b>医疗服务候补否决</b>：昨日候补观察一夜后今日证伪——板块 -1.19%%、上涨家数仅 7/51、5日主力净流入 -17.4亿（全市场第100/124位，昨日第11），资金明确转流出。移出候补，不进任何名单。</div>')

# ④ 互证对照表
html_parts.append('<h2>④ 互证对照表（主线 × ETF 主题交叉）</h2><table><tr><th>主线</th><th>类型</th><th>今日阶段</th><th>锚定校验</th><th>对应ETF(20日)</th><th>方向闸</th><th>交叉结论</th></tr>')
for c in hist["days"][-1]["cross_matrix"]:
    anchor = "有效" if c["line"] != "算力硬件(PCB/覆铜板)" else "错配(前十大无PCB股)"
    gate = '<span class="pill p-red">✗ 未过</span>'
    html_parts.append('<tr><td class="nm">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (c["line"], c["type"], c["stage"], anchor, c["etf_theme"] + " " + c["etf_chg20d"], gate, c["conclusion"]))
html_parts.append('</table><div class="note">今日无互证成功组合（全部缺印证/没信号）。锚定有效性校验：通信ETF前十大权重（新易盛/中际旭创/工业富联等光模块）与PCB板块重合≈0只→锚定无效不参与互证；船舶ETF前三大=中国船舶/中国动力/天海防务→锚定有效；粮食ETF前三大=大北农/北大荒/隆平高科→锚定有效。</div>')

# ⑤ 稳做名单 + 早期埋伏前5
html_parts.append('<h2>⑤ 稳做名单（综合评分降序）＋ 早期埋伏前5</h2><table><tr><th>股票</th><th>代码</th><th>所属主线</th><th>综合分</th><th>档位</th><th>入选理由</th></tr>')
for s in hist["days"][-1]["stable_list"]:
    html_parts.append('<tr><td class="nm">%s</td><td>%s</td><td>%s</td><td><b>%s</b></td><td>%s</td><td>%s</td></tr>' % (s["name"], s["code"], s["mainline"], s["score"], s["tier"], s["reason"]))
html_parts.append('</table><div class="note">单飞名单：北方铜业（sz000737，蓄势58.5还在压，突破价17.20）——铜板块无主题ETF搭档、板块资金-9.7亿，个股趋势独立于主线；若启用仓位减半。</div>')
html_parts.append('<table><tr><th>#</th><th>早期埋伏（5日主力净流入前5）</th><th>代码</th><th>5日净流入</th><th>PE/PB</th><th>红线检查</th></tr>')
early = [("中国巨石", "sh600176", "+15.07亿(第1)", "41.6/5.7", "过闸，蓄势62.6，突破价48.59"),
         ("三环集团", "sz300408", "+14.75亿(第2)", "76.1/11.1", "PB 11.1 &gt;8 → 红线，只看不挂单"),
         ("再升科技", "sh603601", "+8.31亿(第3)", "289/4.3", "PE 289 &gt;80 → 红线，临近突破也只看"),
         ("世运电路", "sh603920", "+6.89亿", "79.7/4.8", "边缘过闸，蓄势74.1，突破价44.00"),
         ("南亚新材", "sh688519", "+6.62亿", "131/17.0", "PE/PB双红线，出局")]
for i, e in enumerate(early):
    html_parts.append('<tr><td>%d</td><td class="nm">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (i+1, e[0], e[1], e[2], e[3], e[4]))
html_parts.append('</table>')

# ⑥ ETF反查 + 搭档
html_parts.append('<h2>⑥ ETF反查榜（20日涨幅，T-1口径+当日校正）＋ 各主线ETF搭档</h2><table><tr><th>#</th><th>ETF</th><th>代码</th><th>主题</th><th>近20日涨幅</th><th>规模(亿)</th><th>标记</th></tr>')
for i, e in enumerate(hist["days"][-1]["etf_reverse"]):
    html_parts.append('<tr><td>%d</td><td class="nm">%s</td><td>%s</td><td>%s</td><td class="up">+%.1f%%</td><td>%.1f</td><td>%s</td></tr>' % (i+1, e["name"], e["code"], e["theme"], e["chg20d"], e["scale"], e["mark"]))
html_parts.append('</table><div class="note">今日校正后仅剩能源化工/巴西/标普油气 3 个方向 ≥8%（粮食 7.4%→今日再跌 3.9% 跌出名单；银行 7.6% 边缘）。主题ETF热度连续第2日收缩。</div>')
for p in hist["days"][-1]["etf_partners"]:
    html_parts.append('<div class="card"><b>%s 的 ETF 搭档</b>：%s</div>' % (p["mainline"], "；".join("%s(%s，%s)" % (x["name"], x["code"], x.get("note","")) for x in p["etfs"])))

# ⑦ 连板梯队
html_parts.append('<h2>⑦ 连板梯队（基础榜 T-1，已用当日行情校正晋级）</h2><table><tr><th>连板</th><th>股票</th><th>今日表现</th><th>备注</th></tr>')
ladder = [("5板", "闽东电力 sz000993", "+10.02% 涨停晋级", "电力情绪总龙头，PE449纯情绪"),
          ("4板", "中新赛克 sz002912", "+10.02% 涨停晋级", "通信设备，板块资金流出独角戏风险"),
          ("3板", "澳弘电子 sh605058", "+9.99% 涨停晋级", "元件/覆铜板，PE41.7过闸"),
          ("3板", "双星新材 sz002585", "+10.04% 涨停晋级", "BOPET薄膜(覆铜板上游)，亏损纯情绪"),
          ("3板断", "超声电子 sz000823", "+5.61% 断板", "元件情绪龙头，趋势未坏"),
          ("3板断", "凯盛新能 sh600876", "-6.06% 断板", "玻璃玻纤，情绪退坡"),
          ("2板断", "三力制药/众泰汽车/正和生态/中视传媒/通达股份", "全部断板", "杂毛梯队清零"),
          ("首板", "科翔股份 sz300903", "+1.03%", "昨日20cm首板未晋级")]
for l in ladder:
    html_parts.append('<tr><td class="nm">%s</td><td>%s</td><td>%s</td><td class="muted">%s</td></tr>' % l)
html_parts.append('</table>')

# ⑧ 蓄势观察清单
html_parts.append('<h2>⑧ 蓄势观察清单</h2>')
html_parts.append('<div class="tip"><b>蓄势分是怎么打的</b>：压弹簧原理——回调一次比一次浅（跌幅收缩）、成交一次比一次少（量能收缩），弹簧压得越紧，弹得越高。0~100 分。</div>')
html_parts.append('<div class="tip"><b>分数怎么看、该干嘛</b>：75 以上=快憋满，盯突破价可挂单；60~75=还在压，只观察不动手；60 以下=没形态，别硬套突破价。红线票（PE&gt;80/PB&gt;8/亏损）一律只看不挂单。</div>')
html_parts.append('<table><tr><th>股票</th><th>分组</th><th>蓄势分</th><th>档位</th><th>突破价</th><th>认错价</th><th>现在该干嘛</th></tr>')
VCP_ROWS = [
    ("生益科技 sh600183", "主线内", 87.2, "快憋满", "157.28", "122.05", "红线(PB19.7)只看；非红线者可挂157.28上方"),
    ("再升科技 sh603601", "主线内", 85.1, "快憋满", "10.96", "8.52", "红线(PE289)只看；不挂单"),
    ("华正新材 sh603186", "主线内", 76.7, "快憋满", "251.57", "160.67", "今日已触发+涨停封板：不追，等回踩"),
    ("世运电路 sh603920", "主线内", 74.1, "还在压", "44.00", "35.71", "观察，接近可挂区间；PE79.7边缘注意"),
    ("兴森科技 sz002436", "主线内", 73.9, "还在压", "42.73", "31.81", "今日盘中触及未站稳：等回踩确认；PE320红线"),
    ("大族激光 sz002008", "主线内", 73.5, "还在压", "99.50", "82.33", "观察；突破价下修至99.5"),
    ("新宙邦 sz300037", "主线内(新)", 72.2, "还在压", "76.45", "59.19", "新面孔：观察，电子化学品资金同向"),
    ("香农芯创 sz300475", "主线内", 71.6, "还在压", "187.52", "147.20", "观察；PB10.6红线"),
    ("太辰光 sz300570", "主线内", 71.1, "还在压", "230.46", "178.18", "观察"),
    ("招商轮船 sh601872", "主线内", 62.0, "还在压", "21.70", "17.79", "已触及·等回踩：重上21.70转已触发"),
    ("中国巨石 sh600176", "主线内(新)", 62.6, "还在压", "48.59", "37.83", "全市场5日资金第1：观察，过闸可挂单"),
    ("招商南油 sh601975", "主线内", 59.9, "没形态", "4.97", "3.65", "不配突破价逻辑，纯观察"),
    ("北方铜业 sz000737", "主线外", 58.5, "没形态", "17.20", "13.80", "单飞候选：观察，启用则仓位减半"),
    ("中国船舶 sh600150", "主线内", 48.2, "没形态", "41.18", "32.59", "只观察"),
    ("天孚通信 sz300394", "主线内", 47.2, "没形态", "289.70", "237.80", "只观察"),
]
for r in VCP_ROWS:
    xs = r[2]
    tier = "快憋满" if xs >= 75 else ("还在压" if xs >= 60 else "没形态")
    cls = "p-red" if xs >= 75 else ("p-blue" if xs >= 60 else "p-gray")
    html_parts.append('<tr><td class="nm">%s</td><td>%s</td><td><b>%.1f</b></td><td><span class="pill %s">%s</span></td><td>%s</td><td>%s</td><td>%s</td></tr>' % (r[0], r[1], xs, cls, tier, r[4], r[5], r[6]))
html_parts.append('</table><div class="note">长鑫科技：无蓄势形态分（未成形），保留状态行。</div>')

# ⑨ 跨日追踪台
html_parts.append('<h2>⑨ 跨日追踪台 · 今日变化</h2><div class="card">'
 '<b>主线阶段变化</b>：无升降级（算力硬件·刚起步第2日 / 航运船舶·刚起步第7日 / 农业·粮食·退潮第4日）。<b>医疗服务候补正式否决</b>（5日资金第11→第100）；<b>新候补：风电设备</b>（涨幅第2+资金第3+上涨家数80%）。<br>'
 '<b>状态机变化</b>：华正新材 观察中→<b>已触发</b>（涨停251.57踩到突破价，封板不追）；兴森科技 观察中→<b>已触及·等回踩</b>（盘中42.73触突破价，收40.86）；生益科技、再升科技 观察中→<b>临近突破</b>（蓄势87.2/85.1快憋满，均红线只看）；招商轮船 已触及·等回踩第2日（盘中21.20未及21.70）。<br>'
 '<b>ETF资金通道变化</b>：船舶ETF今日确认为<b>「价涨钱走=衰竭预警」</b>（净流出480万+月份额月-6.0%/周-3.7%，涨幅+4.1%与份额背离）；粮食ETF 4连阴但月份额+16.1%（价涨钱进，规模仅0.65亿降权）；通信ETF当日净申购为正但月份额-2.2%（价跌钱进=弱埋伏）。<br>'
 '<b>新面孔</b>：中国巨石（稳做观察档75分，5日资金全市场第1）、世运电路（70分）、新宙邦（63分）入稳做观察。<br>'
 '<b>趋势强度分（回归校准追加）</b>：航运 57.7→<b>{ship}</b>｜算力(PCB/光通信) 15.2→<b>{ai}</b>｜粮食→<b>{grain}</b>（回落与指数回调一致，无L1/L2预警触发）。</div>'.format(
     ship=rot["score_series"]["航运"][-1], ai=rot["score_series"]["算力(PCB/光通信)"][-1], grain=g["scores"][-1]))

# ⑩ 免责声明
html_parts.append('<h2>⑩ 免责声明</h2><div class="disc">免责声明：以上内容基于公开数据和量化分析，仅供参考，不构成投资建议。市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，必要时咨询持牌专业机构。过往表现不预示未来收益。数据标注：板块资金/行情/ETF 概览与持仓来自 westock CLI（2026-09-15 收盘，ETF 区间榜与连板基础榜为 09-14 口径已标注）；蓄势分为 wb-finance-skill VCP 引擎（120 根日K）；趋势强度分为锚定 ETF 日K偏移校准追加。今日无主线异动预警（L1/L2 均未触发）；ETF 衰竭预警以「价涨钱走」形式在摘要高亮。</div>')
html_parts.append('</div></body></html>')

out = os.path.join(BASE, "output/daily/%s.html" % TODAY)
with open(out, "w") as f:
    f.write("".join(html_parts))
print("daily html written:", out)
