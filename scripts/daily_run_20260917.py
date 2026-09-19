#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-17 盘后台账更新：days 快照追加 + 补 09-16 分数点 + rotation 维护。"""
import json
import copy

ROOT = '/Users/liuliang19/Desktop/fast-trend-trade'
HIST = ROOT + '/output/history.json'

with open(HIST) as f:
    h = json.load(f)

rot = h['rotation']
days = h['days']

# ---------- 1. 补 09-16 / 追加 09-17 分数点（增量校准法：新点=旧末值+锚定ETF当日涨跌x2.5，限幅±8） ----------
def clamp8(x):
    return max(-8.0, min(8.0, x))

# 09-16 锚定ETF当日涨跌：通信+4.9(滚动窗口口径)，船舶-0.84，粮食+0.58
# 09-17：通信+0.15，船舶+1.70，粮食+2.81
seq = {
    '算力(PCB/光通信)': [(4.9, '2026-09-16'), (0.15, '2026-09-17')],
    '航运': [( -0.84, '2026-09-16'), (1.70, '2026-09-17')],
}
partial_seq = {
    '粮食': [(0.58, '2026-09-16'), (2.81, '2026-09-17')],
}

for name, moves in seq.items():
    for pct, dstr in moves:
        if dstr in rot['score_dates']:
            continue
        prev = rot['score_series'][name][-1]
        rot['score_series'][name].append(round(prev + clamp8(pct * 2.5), 1))
        rot['score_dates'].append(dstr)

p = rot.get('score_series_partial', {}).get('粮食')
if p:
    for pct, dstr in partial_seq['粮食']:
        if dstr in p['dates']:
            continue
        prev = p['scores'][-1]
        p['scores'].append(round(prev + clamp8(pct * 2.5), 1))
        p['dates'].append(dstr)

rot['score_series_note'] = ('增量校准法：新点=旧末值+锚定ETF当日涨跌x2.5（限幅±8）。'
    '09-16/09-17 两点按通信ETF+4.9%/+0.15%、船舶ETF-0.84%/+1.70%、粮食ETF+0.58%/+2.81% 校准。'
    '09-16 分数点系补记（09-16 运行遗漏 rotation 追加，09-17 运行时发现并补齐）。')

# ---------- 2. lines 主线时间线（MM-DD 键） ----------
lines_by_name = {l['name']: l for l in rot['lines']}
stage_patch = {
    '航运/船舶': {'09-16': '刚起步', '09-17': '主升*'},
    '算力(PCB/光通信)': {'09-16': '刚起步', '09-17': '刚起步'},
    '农业/粮食': {'09-16': '退潮', '09-17': '退潮'},
}
for name, patch in stage_patch.items():
    if name in lines_by_name:
        lines_by_name[name]['stages'].update(patch)

# 候补主线入时间线（若无则建）
for nm, etf in (('风电设备', '—'), ('医疗服务', '—')):
    if nm not in lines_by_name:
        newl = {'name': nm, 'etf': etf, 'stages': {}}
        rot['lines'].append(newl)
        lines_by_name = {l['name']: l for l in rot['lines']}
lines_by_name['风电设备']['stages'].update({'09-16': '埋伏', '09-17': '埋伏'})
lines_by_name['医疗服务']['stages'].update({'09-17': '埋伏'})
rot['dates'].append('09-16')
rot['dates'].append('09-17')

# ---------- 3. 连板结构 ----------
rot.setdefault('limitup_structure', []).append({
    'date': '2026-09-17',
    'by_mainline': {
        '算力硬件': {'最高板': 5, '连板家数': 3, '断板家数': 3, '首板家数': 2,
                   '明细': '澳弘电子5板/西陇科学2板/中晶科技2板；断板=华正新材(-9.45%)/超声电子(-3.58%)/双星新材(-3.94%)',
                   '预警': '断层预警：断板3家骤增，情绪退潮先于价格退潮'},
        '风电设备': {'最高板': 3, '连板家数': 1, '断板家数': 0, '首板家数': 0,
                   '明细': '锡华科技3板(龙头)'},
        '航运船舶': {'最高板': 0, '连板家数': 0, '断板家数': 0, '首板家数': 1,
                   '明细': '招商轮船首板涨停(+10.02%,趋势票非情绪票)'},
        '电力(非主线)': {'最高板': 6, '连板家数': 0, '断板家数': 1, '首板家数': 0,
                    '明细': '闽东电力6板断板(-2.76%)，全场最高板终结'},
        '农业反抽': {'最高板': 1, '连板家数': 0, '断板家数': 0, '首板家数': 1,
                  '明细': '敦煌种业反复开板再封板(+10.05%)，退潮中的反抽'},
    },
})

# ---------- 4. 板块体检 ----------
rot.setdefault('sector_check', []).append({
    'date': '2026-09-17',
    'rows': [
        {'板块': '通信设备', '码': 'pt01801102', '当日涨跌': '+0.27%', '上涨占比': '32%', '5日流入': '+53.88亿', '位次': '1', '龙头': '世嘉科技+10.01%'},
        {'板块': '玻璃玻纤', '码': 'pt01801712', '当日涨跌': '+1.00%', '上涨占比': '69%', '5日流入': '+41.44亿', '位次': '2', '龙头': '三峡新材+10.03%'},
        {'板块': '电子化学品Ⅱ', '码': 'pt01801086', '当日涨跌': '-0.52%', '上涨占比': '29%', '5日流入': '+35.10亿', '位次': '3', '龙头': '海星股份+4.09%'},
        {'板块': '风电设备', '码': 'pt01801736', '当日涨跌': '+1.02%', '上涨占比': '55%', '5日流入': '+17.14亿', '位次': '4', '龙头': '锡华科技+10.00%(3板)'},
        {'板块': '医疗服务', '码': 'pt01801156', '当日涨跌': '+1.32%', '上涨占比': '76%', '5日流入': '+16.52亿', '位次': '5', '龙头': '南华生物+10.04%'},
        {'板块': '航运港口', '码': 'pt01801992', '当日涨跌': '+2.21%', '上涨占比': '59%', '5日流入': '-1.02亿', '位次': '转负(当日+5.26亿第6)', '龙头': '招商轮船+10.02%'},
        {'板块': '航海装备Ⅱ', '码': 'pt01801744', '当日涨跌': '+2.75%', '上涨占比': '60%', '5日流入': '-25.95亿', '位次': '流出', '龙头': '松发股份+4.14%'},
        {'板块': '元件', '码': 'pt01801083', '当日涨跌': '-2.41%', '上涨占比': '20%', '5日流入': '+5.94亿', '位次': '由第1骤降', '龙头': '澳弘电子+9.99%(5板)'},
        {'板块': '种植业', '码': 'pt01801016', '当日涨跌': '+3.83%', '上涨占比': '95%', '5日流入': '-7.19亿', '位次': '流出', '龙头': '敦煌种业+10.05%'},
    ],
})

# ---------- 5. ETF 资金四象限 ----------
rot.setdefault('etf_flow_check', []).append({
    'date': '2026-09-17',
    'items': [
        {'etf': '通信ETF国泰', 'code': 'sh515880', '主线': '算力硬件', '价20日': '+5.06%(T-1口径)/+3.31%(当日)', '钱': '当日-2.51亿/月+6.17%/周+2.98%',
         '象限': '价涨钱进(边际改善)', '备注': 'etfInFlow当日仍流出但月份额转增6.17%，衰竭预警解除；T3仍拦截(20日<8%,60日-27.2%深跌)'},
        {'etf': '船舶ETF富国', 'code': 'sh560710', '主线': '航运船舶', '价20日': '+8.26%(当日口径,重过8%线)', '钱': '当日-2446.6万/月-5.0%/周-7.97%',
         '象限': '价涨钱走=衰竭预警(第3日)', '备注': '方向闸首次通过(20日+8.26%>=8%,站上MA20,60日+6.45%)；但份额持续萎缩，互证打折扣'},
        {'etf': '粮食ETF南方', 'code': 'sz159063', '主线': '农业/粮食', '价20日': '-1.05%', '钱': '当日-51.6万/月+7.02%/周-14.08%',
         '象限': '价跌钱走(周)≈无信号', '备注': '规模仅0.61亿<2亿，信号降权；今日+2.81%超跌反抽不改退潮'},
    ],
})

# ---------- 6. ETF 持仓快照（覆盖式更新：移除同主线旧条目再追加） ----------
eh = rot.setdefault('etf_holdings', [])
eh = [x for x in eh if x.get('date') == '2026-09-17' or x.get('mainline') not in ('航运船舶', '农业/粮食', '算力硬件')]
eh.extend([
    {'date': '2026-09-17', 'mainline': '航运船舶', 'etf_code': 'sh560710', 'top3': [
        {'code': '600150', 'name': '中国船舶', 'ratio': 15.41, 'chg_pct': '+3.10%'},
        {'code': '600482', 'name': '中国动力', 'ratio': 14.67, 'chg_pct': '+1.68%'},
        {'code': '300008', 'name': '天海防务', 'ratio': 10.43, 'chg_pct': '+0.79%'}]},
    {'date': '2026-09-17', 'mainline': '算力硬件(锚定错配·光模块)', 'etf_code': 'sh515880', 'top3': [
        {'code': '300502', 'name': '新易盛', 'ratio': 15.6, 'chg_pct': '+0.15%'},
        {'code': '300308', 'name': '中际旭创', 'ratio': 14.61, 'chg_pct': '-1.30%'},
        {'code': '601138', 'name': '工业富联', 'ratio': 9.12, 'chg_pct': '-1.70%'}]},
    {'date': '2026-09-17', 'mainline': '农业/粮食', 'etf_code': 'sz159063', 'top3': [
        {'code': '002385', 'name': '大北农', 'ratio': 5.51, 'chg_pct': '+0.95%'},
        {'code': '600598', 'name': '北大荒', 'ratio': 4.69, 'chg_pct': '+0.88%'}]},
])
rot['etf_holdings'] = eh

# ---------- 7. days 快照 ----------
watchlist = [
    {'name': '中天科技', 'code': 'sh600522', 'group': '算力硬件·主线内', 'xushi': 86.6, 'status': '临近突破', 'close': 36.39, 'day_high': 36.47, 'break_price': 36.47, 'invalid_price': 31.31, 'dist_to_break_pct': -0.2, 'first_seen': '2026-09-16', 'days_in': 2, 'note': '临近突破：蓄势86.6完成，距突破价仅-0.2%；PE33.4/PB3.2全合规=今日唯一光通信可挂单重点'},
    {'name': '飞凯材料', 'code': 'sz300398', 'group': '算力硬件·主线内', 'xushi': 86.5, 'status': '临近突破', 'close': 37.12, 'day_high': 37.33, 'break_price': 37.33, 'invalid_price': 31.6, 'dist_to_break_pct': -0.6, 'first_seen': '2026-09-16', 'days_in': 2, 'note': '临近突破：蓄势86.5完成，距突破价-0.6%；PE48/PB4.08合规，可挂单'},
    {'name': '再升科技', 'code': 'sh603601', 'group': '主线内', 'xushi': 86.2, 'status': '临近突破', 'close': 10.02, 'day_high': 10.7, 'break_price': 10.96, 'invalid_price': 8.52, 'dist_to_break_pct': -8.6, 'first_seen': '2026-09-14', 'days_in': 4, 'note': '蓄势86.2但PE281红线炸线，只看不挂单'},
    {'name': '中材科技', 'code': 'sz002080', 'group': '算力硬件·主线内', 'xushi': 73.9, 'status': '观察中', 'close': 58.69, 'day_high': 61.47, 'break_price': 61.47, 'invalid_price': 46.59, 'dist_to_break_pct': -4.5, 'first_seen': '2026-09-16', 'days_in': 2, 'note': '蓄势73.9还在压；今日+5.03%盘中61.47正好触突破价回落；PE48.6/PB4.8合规'},
    {'name': '中国巨石', 'code': 'sh600176', 'group': '算力硬件·主线内', 'xushi': 61.1, 'status': '观察中', 'close': 47.15, 'day_high': 47.9, 'break_price': 51.68, 'invalid_price': 37.83, 'dist_to_break_pct': -8.8, 'first_seen': '2026-09-17', 'days_in': 1, 'note': '重新入池：玻纤中军5日主力+10.89亿，蓄势61.1还在压；PE41.6/PB5.7合规；突破价51.68'},
    {'name': '大族激光', 'code': 'sz002008', 'group': '主线内', 'xushi': 73.8, 'status': '观察中', 'close': 94.81, 'day_high': 98.4, 'break_price': 99.5, 'invalid_price': 82.33, 'dist_to_break_pct': -4.7, 'first_seen': '2026-09-09', 'days_in': 7, 'note': '蓄势73.8还在压，距突破价-4.7%'},
    {'name': '永鼎股份', 'code': 'sh600105', 'group': '算力硬件·主线内', 'xushi': 74.0, 'status': '观察中', 'close': 45.14, 'day_high': 46.99, 'break_price': 46.99, 'invalid_price': 36.56, 'dist_to_break_pct': -3.9, 'first_seen': '2026-09-17', 'days_in': 1, 'note': '新面孔：5日主力+17.53亿多头池第2，光通信/海缆/超导；蓄势74.0；PE158红线只看'},
    {'name': '生益科技', 'code': 'sh600183', 'group': '主线内', 'xushi': 87.2, 'status': '已触及·等回踩', 'close': 146.03, 'day_high': 157.27, 'break_price': 157.28, 'invalid_price': 122.05, 'dist_to_break_pct': -7.2, 'first_seen': '2026-09-09', 'days_in': 7, 'note': '已触及·等回踩第2日：盘中157.27距突破价157.28仅差1分未站稳，-5.47%大回落'},
    {'name': '兴森科技', 'code': 'sz002436', 'group': '主线内', 'xushi': 73.9, 'status': '已触及·等回踩', 'close': 41.2, 'day_high': 42.7, 'break_price': 42.73, 'invalid_price': 31.81, 'dist_to_break_pct': -3.6, 'first_seen': '2026-09-14', 'days_in': 4, 'note': '已触发后回落：收盘跌破突破价42.73达-3.6%，回踩观察；认错价31.81尚远(-22.8%)'},
    {'name': '华正新材', 'code': 'sh603186', 'group': '主线内', 'xushi': 76.7, 'status': '已触及·等回踩', 'close': 230.0, 'day_high': 253.0, 'break_price': 251.57, 'invalid_price': 160.67, 'dist_to_break_pct': -8.6, 'first_seen': '2026-09-10', 'days_in': 6, 'note': '已触发后回落：盘中253触突破价未站稳，收-9.45%大阴线；仍高于认错价160.67(+43%)'},
    {'name': '招商轮船', 'code': 'sh601872', 'group': '主线内', 'xushi': 62.0, 'status': '已触发', 'close': 21.85, 'day_high': 21.85, 'break_price': 21.7, 'invalid_price': 17.79, 'dist_to_break_pct': 0.7, 'first_seen': '2026-09-09', 'days_in': 7, 'note': '已触发：涨停+10.02%收21.85≥突破价21.70；涨停封板不追等回踩；PE16.3/PB3.8合规'},
    {'name': '招商南油', 'code': 'sh601975', 'group': '主线内', 'xushi': 59.9, 'status': '观察中', 'close': 4.6, 'day_high': 4.68, 'break_price': 4.97, 'invalid_price': 3.65, 'dist_to_break_pct': -7.4, 'first_seen': '2026-09-09', 'days_in': 7, 'note': '+3.60%反弹，距突破价-7.4%'},
    {'name': '中国船舶', 'code': 'sh600150', 'group': '主线内', 'xushi': 48.2, 'status': '观察中', 'close': 38.96, 'day_high': 39.32, 'break_price': 41.18, 'invalid_price': 32.59, 'dist_to_break_pct': -5.4, 'first_seen': '2026-09-09', 'days_in': 7, 'note': '+3.10%反弹，距突破价-5.4%；船舶ETF第一大权重(15.41%)'},
    {'name': '天孚通信', 'code': 'sz300394', 'group': '主线内', 'xushi': 47.2, 'status': '观察中', 'close': 277.65, 'day_high': 282.6, 'break_price': 289.7, 'invalid_price': 237.8, 'dist_to_break_pct': -4.2, 'first_seen': '2026-09-10', 'days_in': 6, 'note': '+3.41%，距突破价-4.2%；PB53红线只看'},
    {'name': '太辰光', 'code': 'sz300570', 'group': '主线内', 'xushi': 60.1, 'status': '观察中', 'close': 215.98, 'day_high': 217.69, 'break_price': 230.46, 'invalid_price': 178.18, 'dist_to_break_pct': -6.3, 'first_seen': '2026-09-14', 'days_in': 4, 'note': '+4.65%反弹；蓄势60.1边缘；PE162红线只看'},
    {'name': '香农芯创', 'code': 'sz300475', 'group': '主线内', 'xushi': 71.9, 'status': '观察中', 'close': 164.03, 'day_high': 169.88, 'break_price': 187.52, 'invalid_price': 147.2, 'dist_to_break_pct': -12.5, 'first_seen': '2026-09-09', 'days_in': 7, 'note': '蓄势71.9；PB10.8红线只看'},
    {'name': '北方铜业', 'code': 'sz000737', 'group': '主线外', 'xushi': 58.5, 'status': '观察中', 'close': 14.06, 'day_high': 14.45, 'break_price': 17.2, 'invalid_price': 13.8, 'dist_to_break_pct': -18.3, 'first_seen': '2026-09-09', 'days_in': 7, 'note': '铜主线外，距突破价-18.3%渐远，连续7日无进展，关注移出'},
    {'name': '长鑫科技', 'code': 'sh688825', 'group': '主线内', 'xushi': None, 'status': '观察中', 'close': 53.47, 'day_high': 54.99, 'break_price': None, 'invalid_price': None, 'dist_to_break_pct': None, 'first_seen': '2026-09-10', 'days_in': 6, 'note': '存储龙头观察，无蓄势价'},
    {'name': '大金重工', 'code': 'sz002487', 'group': '主线外(风电)', 'xushi': 37.3, 'status': '观察中', 'close': 41.21, 'day_high': 42.9, 'break_price': None, 'invalid_price': None, 'dist_to_break_pct': None, 'first_seen': '2026-09-16', 'days_in': 2, 'note': '风电候补主线先锋：5日主力+11.57亿第2、今日+5.23%；蓄势37.3没形态，等落地喘气'},
]

day = {
    'date': '2026-09-17',
    'funnel': {'全市场约': 5577, '站上所有均线': 370, '早期埋伏': 15, '主升候选(25~60)': 16, '多头池资金强': 15, '稳做名单': 5, '快打名单': 7},
    'mainlines': [
        {'name': '算力硬件(PCB/覆铜板/光通信)', 'type': '资金主线', 'stage': '刚起步', 'first_seen': '2026-09-10(候补)', '转正日': '2026-09-14', '持续天数': 8,
         '要点': '刚起步第4日·内部分化加剧：资金三箭头仍在(通信设备5日+53.88亿第1/玻璃玻纤+41.44亿第2/电子化学品+35.10亿第3)，但元件当日-77.59亿巨额流出+板块-2.41%(20/61上涨)=PCB高位失血，元件5日口径从136亿骤降至+5.94亿；超声电子Chg20D+64.9%>60%=中军过热尾声信号；T3✗通信ETF 20日+3.31%(当日口径)<8%且60日-27.18%深跌通道→拦截；锚定错配维持(前十大全为光模块/光通信,无PCB股)；连板温度：澳弘电子5板+西陇/中晶2板,断板3家(华正/超声/双星)=断层预警；玻璃玻纤(69%上涨)与光通信(天孚+3.4%/中天+3.4%)接棒'},
        {'name': '航运船舶', 'type': '资金主线', 'stage': '主升*', 'first_seen': '2026-09-09', '持续天数': 9,
         '要点': '刚起步第9日→主升边缘(待②确认)：当日+2.21%资金+5.26亿第6回流、宽度59%、招商轮船涨停+10.02%/中国船舶+3.10%/招商南油+3.60%中军齐动；T3首次通过=船舶ETF 20日+8.26%重过8%线+站上MA20(0.957>0.9205)+60日+6.45%；①与③同真按规则升主升，但②5日口径-1.02亿短暂转负(09-10大额流入14亿滚出窗口所致,当日+5.26亿回流)→标主升*待确认，明日5日回正则确认，否则退回刚起步；ETF资金通道连续第3日衰竭预警(月-5.0%/周-7.97%)——中期价涨但份额持续缩，互证打折扣'},
        {'name': '农业/粮食', 'type': '涨停主线', 'stage': '退潮', 'first_seen': '2026-09-09', '持续天数': 9,
         '要点': '退潮第6日·超跌反抽：种植业当日+3.83%(19/20上涨95%)+敦煌种业反复开板再封板+10.05%+粮食ETF今日+2.81%；但5日资金-7.19亿流出未止、粮食ETF 20日-1.05%、规模0.61亿<2亿降权；只可龙头快打或不碰，反抽一日游不抄底'},
    ],
    'candidates': [
        {'name': '风电设备', 'type': '候补·资金主线', 'stage': '埋伏',
         '要点': '候补第2日：5日主力+17.14亿升第4、当日+1.02%资金+3.33亿第9、宽度55%(17/31)、龙头锡华科技3板、大金重工今日+5.23%(5日+11.57亿)；无板块ETF锚定(T3无从谈起)；连续两日资金前10，若明日续守前10可转正'},
        {'name': '医疗服务', 'type': '候补观察', 'stage': '埋伏',
         '要点': '第2次冒头：5日+16.52亿第5、当日资金+12.69亿第3、宽度76%(39/51)、龙头南华生物涨停；09-15曾冒头次日即回落被否决，本次重新观察；催化待人判'},
    ],
    'watchlist': watchlist,
    'etf_top': [
        '能源化工 +16.21%(35.9亿) [09-16口径]',
        '巴西ETF易方达 +12.09%',
        '标普油气ETF嘉实 +9.17%',
        '船舶 +8.26%(09-17当日口径,重过8%线,主线锚定)',
        '通信 +3.31%(09-17当日口径,方向闸拦截)',
        '豆粕 +7.63% [09-16口径]',
    ],
}

# 替换或追加
days = [d for d in days if d['date'] != '2026-09-17']
days.append(day)
if len(days) > 90:
    days = days[-90:]
h['days'] = days

with open(HIST, 'w') as f:
    json.dump(h, f, ensure_ascii=False, indent=1)

# 校验
with open(HIST) as f:
    check = json.load(f)
print('JSON 校验通过；days=', len(check['days']), 'score_dates 末3=', check['rotation']['score_dates'][-3:])
print('score_series 算力末3=', check['rotation']['score_series']['算力(PCB/光通信)'][-3:])
print('score_series 航运末3=', check['rotation']['score_series']['航运'][-3:])
print('粮食 partial 末3=', check['rotation']['score_series_partial']['粮食']['scores'][-3:])
