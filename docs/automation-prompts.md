# 自动化 prompt 全文快照（配置事实源）

> **用途**：换机器 / 重建自动化时**复制即用**。这些 prompt 原本只存在于 WorkBuddy 客户端，
> 不在仓库里——2026-09-17 发现此缺口后导出落盘。
> **导出时间**：2026-09-20（v3.1 结构版：脚本移至根 scripts/ · 产物按日历目录 output/daily/<日期>/ · 含 v0.3 三池流水线步骤 9.5 · 数据通道优先 CLI · data_day 禁 today）　｜　**同步方式**：改完 prompt 后需重新导出本文件（见文末方法）
> ⚠️ prompt 内的绝对路径为本机值，换机时按 `docs/automation-daily.md` 的「路径替换表」调整。

## 任务一：每日盘后趋势候选扫描（主任务）

| 项 | 值 |
|---|---|
| ID | `880e6067-8bbd-4137-96de-079100af9452` |
| 调度 | 每交易日（周一~周五）15:30 |
| cwd | `/Users/liuliang19/Desktop/fast-trend-trade` |
| 状态 | ACTIVE |

```text
【每日盘后趋势候选扫描】

【启动检查与补跑（每次运行的第一步，必做）】权威定义见 /Users/liuliang19/Desktop/fast-trend-trade/docs/automation-daily.md 的「二·补：补跑检查」章节——执行前先读。精简规则：
1) `westock trade-calendar --date <今天>` 判断今天是否交易日（禁用"周几"粗判）；
2) 算「最近应有报告日」：今天若为交易日且当前时间 ≥15:30 → 今天；否则取 `westock trade-calendar --end <今天> --trading-only --limit 5` 中 ≤今天 的最大交易日；
3) **区间比对找缺口**：起点 = history.json 的 days 数组最早快照日期，`westock trade-calendar --start <起点> --end <最近应有报告日> --trading-only` 列出区间全部交易日，与 days 实际日期集合做差 → 缺失清单（不能只比最后一个快照日期，否则漏掉中间缺失，如 09-11 夹在 09-10/09-14 之间）；
4) 缺失为空 → 直接结束；
5) 缺失非空 → 逐个补跑（数据用目标交易日收盘口径：CLI 加 --date、MCP 用 date 参数；产物 output/daily/<该日>.html；days 按日期补记快照；不重算后续状态机）；
6) 今天是交易日但当前 <15:30 → 只补历史缺口，不生成今日报告；
7) 接口不支持历史日期 → 报告内标注"该日数据缺失，已用最近可得数据替代"，不静默。

参数权威（v0.2 铁律，优先级次于语言规范）：一切阈值以 config/settings.json 为单一事实源。关键现值：探测层 chg20d 0~12；确认层 chg20d 25~60；硬闸 PE-TTM∈[0,80]、PB≤8、近10日涨停≥2 出局；阶段四词＝刚起步/主升/尾声/退潮；T3 含 trend_guard 方向闸（ETF 须站上 MA20 且 60 日涨幅 ≥-10%）；ETF 资金通道独立于 T3（价×钱四象限）；连板温度计独立于 T3（limitup_lane）；**个股形态状态机**（mainline.stock_pattern：trend_up/range/rebound_in_fall/collapse 四态，引用个股趋势必先算形态）。

路径（本机固定值，勿改写）：仓库根＝/Users/liuliang19/Desktop/fast-trend-trade；托管 python＝/Users/liuliang19/.workbuddy/binaries/python/envs/default/bin/python；westock 工具＝node /Users/liuliang19/.workbuddy/plugins/cache/cb_teams_marketplace/finance-data/1.5.0/skills/westock-tool/scripts/index.js；蓄势引擎＝/Users/liuliang19/.workbuddy/plugins/cache/cb_teams_marketplace/finance-data/1.5.0/skills/wb-finance-skill/scripts/run_signal.py。生成 Python 脚本须兼容 **Python 3.9+**：禁止 f-string 表达式内反斜杠转义，需内嵌引号的片段预先定义为模块常量。

语言规范（铁律，优先级最高）：禁止黑话。统一用语对照——A轨→「资金主线」；B轨→「涨停主线」；预热→「刚起步」；确认→「主升」；扩散尾声→「尾声」；共振→「互证」；正向漏斗→「选股漏斗」；反向漏斗→「ETF反查」；探测层→「早期埋伏名单」；确认层→「主升名单」；VCP→「蓄势形态」；触发价→「突破价」；失效价→「认错价」；趋势池→「稳做名单」；博弈池→「快打名单」；独立趋势池→「单飞名单」；多头池→「站上所有主要均线的股票」。日报开头固定放「名词小词典」区块，驾驶舱顶部同款。自查：正文不得残留 A轨/B轨/VCP/预热区/共振区/左翼/右翼（"蓄势形态（VCP）"括号注记允许）。

执行步骤：
1. 用 Bash 依次运行（可执行文件：node /Users/liuliang19/.workbuddy/plugins/cache/cb_teams_marketplace/finance-data/1.5.0/skills/westock-tool/scripts/index.js，下称 wt；补跑历史时加 --date）：
   a. wt filter "intersect([Chg20D >= 0, Chg20D < 12, MainNetFlow5D > 0, TurnoverRate > 2, PE_TTM > 0])" --orderby MainNetFlow5D --desc --limit 15   # 早期埋伏名单
   b. wt filter "intersect([Chg20D > 25, Chg20D < 60, PE_TTM > 0, PE_TTM < 50, TurnoverRate > 3])" --orderby Chg20D --desc --limit 20   # 主升名单候选（25~60）
   c. wt ranking cap_main_5d --within-strategy ma_long --limit 15
   d. wt ranking limitup_days --limit 20
   **连板温度计（settings.mainline.limitup_lane）**：梯队每只票**标注所属主线**（如 澳弘电子→算力硬件），统计**主线内连板结构**（最高板数/连板家数/断板家数/首板家数）——写进主线体检行。连板断层=情绪退潮先于价格退潮。
1.5 板块体检（mcp__westock-mcp__data_sector，详见 docs/sector-data-integration.md）：
   a. data_sector(mode="ranking", kind="industry", type="mainNetInflow5d", order="desc", limit=60)：name/code/changePct/upCount/mainNetInflow5d/leader。
   b. 每条候选主线摘"板块体检"行：板块名｜板块码｜当日涨跌｜上涨家数占比｜主力5日净流入位次｜龙头涨幅。
   c. 机判映射（人终审）：T1←upCount占比≥50%；T2←位次前20；T4←龙头涨幅为正且板块上涨。**T1 计数不含被基本面闸拦截者**（PB>8/PE>80/扣非亏损一律不计入 ≥3 家的计数）。
   d. 板块名对不上用 mode="search" 校正；找不到则标注"板块数据缺失，T1/T2 转人判"。
   e. **单位＝万元** → 报告折算为亿元（÷10000，两位小数）。
2. 主线判定（输出 1~3 条，标注【类型】与【阶段：刚起步/主升/尾声/退潮】）：
   资金主线（②⑤必要；①③④至少一条为真→成立且刚起步；①与③同时为真→主升）：
   - ①涨的票够多：主升口径=板块内四维趋势池≥3家（剔除红线票后计数）；启动口径=Chg5D>5%且量比>1.5的≥5家；机判辅证=upCount占比≥50%
   - ②板块被大钱买（必要）：主力5日净流入居板块前列；机判辅证=mainNetInflow5d位次前20
   - ③ETF也涨（**trend_guard 方向闸**）：20日≥8% 或创60日新高，**且** ETF 站上 MA20、60日涨幅≥-10%。任一不满足→T3=✗，写明「ETF 深跌通道，涨幅仅为反弹，不计为印证」
   - ④大块头领涨：百亿级个股 Chg20D∈[10%,60%]
   - ⑤题材有后劲（人判；必要）
   - 阶段续：中军 Chg20D>60% 或 ETF 乖离>25%=尾声；资金转流出或 ETF 破 20 日线=退潮
   涨停主线：①最高连板≥3 ②涨停≥5家连续≥3天 ③板块资金前列 ④题材有后劲 ⑤ETF同步向上=真主线。
   一票否决红线：近10日涨停≥2→快打；PE-TTM为负或>80、PB>8、扣非亏损→不得进稳做/单飞（以 settings.species_hard_gate 为准）。
2.5 **个股形态标注（v0.2 新增，settings.mainline.stock_pattern 四态状态机）**：对候选主线内全部个股、稳做/观察池、ETF 前三大权重股，用 data_kline（120根）计算 MA20/MA60/chg60d/高低点序列，按 stock_pattern.states 判定四态之一：**趋势上行/收敛震荡/深跌反弹/崩塌下行**——输出形态标签供 ③⑤⑥⑧ 各表与主线体检聚合使用。**每条形态标注必须同时输出「系统资格」**（名单归属/红线状态，如 "✅稳做观察档"/"❌红线拦截(PB13.2)"/"❌快打名单"）——形态描述≠交易资格，两层合并输出；**表格按资格分组排序**（✅稳做→观察→❌拦截/快打），禁止把排除项排在首位。铁律：引用个股「趋势/强势」必附形态标签，禁止凭涨幅/名气贴标签（实证教训：沪电 60日-20.33% 收敛震荡曾被误标趋势强势，澳弘 5连板曾被误列首位）。
3. ETF反查：wt ranking qt_chg_interval --asset etf --orderby ChgPct20D --min-ChgPct20D 8 --limit 40 → 剔宽基 → 同指数留最大 → 规模≥5亿 → 前10，标注与主线重合 + 是否通过 trend_guard。
4. 主线 ETF 通道：每条主线筛选主题贴合、规模≥5亿的前 3 只 ETF 搭档；单飞名单须明示无板块 ETF。
4.5 **ETF 资金通道（价×钱四象限）**；工具 mcp__westock-mcp__data_etf aspect="overview"：对每条主线的锚定 ETF 拉 etfInFlow/etfInFlowMAvg/etfSizeMChg/etfSizeWChg/etfSize/chgPct20D。四象限（价=chgPct20D>0 或站上MA20；钱=etfInFlow>0 或 etfSizeMChg>0 或 etfSizeWChg>0）：价涨钱进=健康主升｜价涨钱走=**衰竭预警**（摘要高亮）｜价跌钱进=**资金型埋伏**｜价跌钱走=无信号。小规模降权（etfSize<2亿）。etfInFlow 只用正负号与均值比较做方向判断。
4.6 **ETF 持仓快照**：每条主线的锚定 ETF 用 data_etf aspect="holdings" 拉前三大权重个股（名称/代码/权重%），data_quote 补当日涨跌与**个股形态标签**；写入 history.json 的 rotation.etf_holdings（覆盖式更新最新日期）。
5. 互证对照表：主线×ETF 主题交叉。T3 结论前先做锚定有效性校验（anchor_validation：holdings 前十大权重与板块成分比对，重合<3 只 → 「锚定无效，不参与互证」）。主线✓+ETF✓（过方向闸）=互证成功；✗✓=值得期待；✓✗=缺印证（注明"ETF 深跌中"或"锚定错配"）；✗✗=没信号。个股级互证：主线强度满分 25。
6. 蓄势形态精判（稳做+单飞+早期埋伏前5共≤10只）：run_signal.py --engine vcp --source westock --code <代码> --limit 120 --pretty。score≥75=快憋满；60~75=还在压；<60=没形态。每票：蓄势分＋档位＋突破价＋认错价＋形态标签＋"现在该干嘛"。
   **候选池扩充（断板→蓄势跟踪）**：**主线未退潮**的连板票**断板**后，自动进入蓄势评分候选池（连板票的「下半场」：等它落地喘气后以蓄势形态回归）。断板首日只观察；蓄势分≥60 才进观察池。只给观察资格，买入仍以突破价/认错价状态机执行。
7. 稳做名单综合评分：红线否决。主线强度 25（主升×1.0/刚起步×0.8/尾声×0.5；互证个股满分；单飞换催化强度）+ 板块内地位 20 + 蓄势 25 + 资金验证 20 + 距买点 10。≥80 优先档、60~79 观察、<60 不入池。单飞仓位减半。
8. 生成日报 HTML 落盘 output/daily/YYYY-MM-DD.html。结构：①漏斗计量行②名词小词典③主线体检（每条主线：板块体检行 + ETF资金通道行 + 连板温度行 + **形态分布行**（主线内：趋势X/震荡Y/反弹Z/崩塌W 只）+ 判据明细）④互证对照表⑤稳做名单（每票含**形态标签**+入选理由）+早期埋伏前5⑥ETF反查榜前10+各主线ETF搭档（权重股含形态标签）⑦连板梯队（每票标注所属主线）⑧蓄势观察清单（含形态标签）⑨跨日追踪台·今日变化⑩免责声明（固定文案见历史日报）。图表纯 HTML/CSS/SVG（禁 JS 图表库）。**所有出现的标的（个股/ETF）均包成可点击链接**：`<a href="https://gu.qq.com/{code}" target="_blank">{名称}</a>`（腾讯自选股详情页，与 westock 生态一致；无 code 时降级纯文本）。
9. 历史台账维护与驾驶舱：
   a. 拉价格：读 history.json，昨日 watchlist 用 mcp__westock-mcp__data_quote 拉收盘/最高/涨跌。
   b. 状态机（收盘价推进）：观察中→临近突破（蓄势≥75 或距突破价≤1%）→已触发/已触及·等回踩/已失效（≤认错价，保留5天）。
   c. 写 history.json：days 快照（90天）；rotation（dates/lines/score_dates/score_series/score_series_partial/alert_events/sector_check/etf_flow_check/etf_holdings/limitup_structure/**pattern_check 形态分布**），250 个交易日。JSON 校验。
   c2. 预警（settings.score_alert）：L1/L2 规则不变；ETF 资金通道「衰竭预警」（价涨钱走）与连板断层均摘要高亮。**新增**：主线内形态分布从「趋势票>0」转「趋势票=0 且情绪票连板」时，提示「主线进入刚起步/蓄势期微观结构」。
   d. 重建驾驶舱：**优先直接运行 `python3 /Users/liuliang19/Desktop/fast-trend-trade/scripts/build_dashboard_full.py`**（确定性脚本）；若报错再手工生成。三段式定义：
      第一段 ▶ 个股趋势→ETF 趋势（anchor-card pos）：漏斗链 + 稳做名单（按主线分组，含形态标签）+ 主线→锚定ETF流向表（方向闸/资金四象限/形态分布）。
      第二段 ◀ ETF 趋势→龙头个股（anchor-card neg）：ETF 榜 + 重点ETF→龙头个股反查表（权重%/当日涨跌/**形态标签**；数据 rotation.etf_holdings）。
      第三段 ⇄ 双向交叉验证（anchor-card cross）：互证表（含锚定校验/方向闸/资金四象限/**形态分布**列）+ 四象限图例。
   e. 轮动叙事：主线阶段变化 + ETF 关键行情 + 板块体检跨日变化 + ETF 资金通道变化 + 连板结构变化 + **形态分布变化**（如主线内趋势票清零），必须给日期和数字。
9.5 **v0.3 三池流水线（2026-09-19 新增，在步骤 9 之后、步骤 10 之前运行）**：用托管 python 依次执行（cwd=仓库根）：
   a. `python scripts/build_growth_pool.py` —— B 预期驱动池（全市场财务筛+技术面买点，输出 output/tmp/growth_pool_<台账日>.json）
   b. `python scripts/build_etf_holdings.py` —— ETF 持仓反查（双来源，输出 etf_holdings_<台账日>.json）
   c. `python scripts/build_emotion_pool.py` —— 情绪票池（温度计+梯队+红旗）
   d. `python scripts/track_pools.py` —— 三池跟踪台账（record+price+backfill；**20 日裁决的数据来源，不可跳过**）
   e. `python scripts/score_stable.py --json` —— A 池规则分（供 f 引用，须在 f 之前）
   f. `python scripts/render_v3_layered.py` —— 四层架构日报 output/daily/<台账日>-layered.html（末尾自动跑术语自检，不过=不能提交）
   产物核对：growth_pool / etf_holdings / emotion_pool 三个 JSON + layered.html；台账 pool_tracking.entries 应包含当日 A/B/C 全部标的。
   注：脚本日期用 data_day()（台账最后快照日），跨零点运行不错位。资金类判据统一 filter 口径（MainNetFlow5D，单位元；ranking 榜实测存在缺票）。

10. present_files 展示日报，简版摘要（含补跑情况、漏斗、主线记分与阶段、板块体检行、各主线 ETF 资金通道四象限结论、连板温度、**形态分布**、稳做名单、互证要点、ETF搭档、蓄势观察、追踪台与曲线变化、预警、指数档位）。
```

## 任务二：早间补漏检查（日报缺口补齐）

| 项 | 值 |
|---|---|
| ID | `be934866-3aac-4630-9d4d-300a17537e48` |
| 调度 | 每交易日（周一~周五）09:05 |
| cwd | `/Users/liuliang19/Desktop/fast-trend-trade` |
| 状态 | ACTIVE |
| 设计意图 | 主任务只在 15:30 触发；若那时客户端未运行则当天无报告。本任务在**早间**独立复查缺口并补齐（静默优先：无缺口不打扰） |

```text
【早间补漏检查】目的：杜绝"收盘后客户端未运行导致日报永久缺失"。历史案例 2026-09-11（周五）：15:30 客户端未运行 → 调度未触发；调度器自带的 12 小时补跑窗口落在周六，被当时的"当天休市则结束"规则跳过 → 该日日报永久缺失。

权威逻辑见 /Users/liuliang19/Desktop/fast-trend-trade/docs/automation-daily.md 的「二·补：补跑检查」章节——**执行前先读该章节**。

执行（务必静默优先）：
1) 计算「缺失交易日清单」：用 `westock trade-calendar --start <output/ledger/history.json 中最早快照日期> --end <最近应有报告日> --trading-only` 列出区间全部交易日，与 /Users/liuliang19/Desktop/fast-trend-trade/output/ledger/history.json 的 days 日期集合**做差**（区间比对，不是只比最后一个日期——中间缺失同样要抓出来）。
2) 清单为空 → **立即静默结束**：不产出任何文件、不发送任何消息、不改动任何数据。
3) 清单非空 → 逐个补跑缺失交易日：
   - 优先执行 `python3 /Users/liuliang19/Desktop/fast-trend-trade/scripts/backfill_daily.py <日期>`（拉目标交易日收盘数据 + 生成产物 + 补记台账）
   - 补跑后核对 v3.1 目录结构：`output/daily/<该日>/` 下应有 `report.html` / `dashboard.html` / `index.html` / `data/` / `screen/`；若缺失，再执行 `python3 /Users/liuliang19/Desktop/fast-trend-trade/scripts/daily_pipeline.py` 补齐（四层日报 layered.html 与三池产物）
   - 数据一律用**目标交易日**收盘口径（CLI 命令加 `--date <该日>`；MCP 用 date 参数）；**优先 CLI**（westock / westock-tool），MCP 仅兜底
   - 在 `output/ledger/history.json` 的 days 数组**按日期顺序补记**该日快照（字段与既有快照一致）；只补报告与台账，**不重算后续日期的状态机**
   - 补完后简要汇报：补了哪几天、原因、数据口径
4) 若今天是交易日且当前时间 <15:30 → 只补历史缺口，不生成今日报告（今日报告由 15:30 的盘后扫描负责）。
5) 阈值与判据一律以 config/settings.json 为准；生成的 Python 脚本须兼容 Python 3.9+（禁止 f-string 表达式内使用反斜杠转义）；脚本内日期用 `data_day()`（台账最后快照日），**禁止 today()**；报告须通过术语自检（`python3 scripts/lint_report.py`）——不过不算完成。
```

## 如何重新导出本文件（改完 prompt 后必做）

1. 用 `automation_update` 的 `view` 模式读取两个任务的最新 prompt（ID 见上表）
2. 将返回的 `prompt` 字段原文替换本文件对应代码块
3. 更新顶部「导出时间」
4. commit + push

> **为什么必须同步**：prompt 只存在于 WorkBuddy 客户端，不在仓库。若只改客户端不导出，
> 换机器时无法复现，且「仓库是事实源」的原则被破坏（2026-09-17 发现的缺口）。


---

## v0.3 增补（2026-09-18/19）—— ✅ 已于 2026-09-20 合并进上述任务一 prompt（步骤 9.5）

以下为合并前的原始记录，保留作为设计依据：

### 每日流程新增步骤（在现有 run_daily 之后按序执行）
1. `build_growth_pool.py` —— B 预期驱动池（全市场财务筛 + 技术面买点，产出 growth_pool_<date>.json）
2. `build_etf_holdings.py` —— ETF 持仓反查（双来源：指数成分精确 / 板块市值近似）
3. `build_emotion_pool.py` —— 情绪票池（温度计 + 梯队 + 红旗）
4. `track_pools.py` —— 三池跟踪台账（record + price + backfill + stats，**20 日数据裁决的数据来源**）
5. `render_v3_layered.py` —— 四层架构日报（末尾自动跑术语自检）

### 数据通道变更（重要）
- **统一走 CLI**（westock / westock-tool），MCP 仅兜底——MCP 当日反复限频，CLI 全程顺畅且数值一致
  （详见 sector-data-integration.md 第七节）
- 脚本日期用 `data_day()`（台账最后快照日），**禁止用 today()**（跨零点运行会错位）

### ⚠️ 硬性原则
- **术语自检不过 = 不能提交**（黑话 / T1~T5 编号 / 缺名词小词典都会被抓，清单见 lint_report.py）
- B 池买点状态四档：已触发 / 临近突破（≤2%）/ 蓄势充分（形态憋满但离买点远）/ 观察中
- 台账 `pool_tracking` 为 append-only，不覆盖历史
