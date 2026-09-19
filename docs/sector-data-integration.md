# 板块数据接入说明（v0.2 §7-② 落地的第一步）

> 目的：把「主线判定 T1-T4」从**纯人判**升级为**机判 + 人终审**。
> 状态：MCP 通道已实测可用并在当日验证；provider（纯 Python）层实现按下表按需补。

## 一、契约 ↔ 实际字段映射（重要：实测比契约更丰富）

契约定义在 `src/providers/base.py` 的 SectorContract。实际 MCP 工具
`mcp__westock-mcp__data_sector` 的返回字段可直接覆盖，且**多出两个高价值字段**：

| 契约字段 | data_sector 实际字段 | 说明 |
|---|---|---|
| `sector` | `name`（如 "元件"） | 板块名 |
| — | `code`（如 `pt01801083`） | **板块码**——可作 `tool_filter/tool_ranking --universe` 的取值 |
| `main_net_flow_5d` | `mainNetInflow5d` | ⚠️ **单位未标注，待校准**（见第三节） |
| `chg20d` | `changePct` | ⚠️ 实为**当日**涨跌幅，不是 20 日 |
| `stock_count` | `upCount`（"45/61"） | ★ **上涨家数/总家数**——T1 的现成数据 |
| — | `leader: {code,name,changePct}` | ★ 板块龙头及涨幅——服务 T4 |
| — | `turnover / turnoverRate / mainNetInflow / mainNetInflow20d` | 多口径备查 |

**调用方式**

```
data_sector(mode="ranking", kind="industry", type="mainNetInflow5d", order="desc", limit=60)
data_sector(mode="search", query="航运")      # 板块名不确定时校正
data_sector(mode="constituent", code="pt01801744")  # 取成分股
data_sector(mode="list", scope="sw1")          # 申万一级清单
```

## 二、判据映射（机判输入，人终审）

| 判据 | 机判输入 | 建议阈值（首版，随验证调整） |
|---|---|---|
| **T1** 涨的票够多 | `upCount` 上涨家数占比 | ≥50% 视为满足（或全市场板块排名前 30%） |
| **T2** 板块被大钱买 | `mainNetInflow5d` 在榜单的位次 | 前 20 名视为满足 |
| **T3** ETF 也涨 | ETF 数据（不变，走 ETF 反查） | ≥8% 或创 60 日新高 |
| **T4** 大块头领涨 | `leader.changePct` + 板块 `changePct` | 龙头涨幅为正且板块上涨（百亿级需另查个股） |

板块名与主线命名不一致时，先 `mode="search"` 校正；仍找不到则标注
**"板块数据缺失，T1/T2 转人判"**——不猜、不静默。

## 三、✅ 单位已校准：万元（2026-09-14 实测）

**校准方法（交叉验证）**：同一时点，用官方资金接口 `data_fund_flow`（返回单位明确为元）
与 CLI 工具比对同一只股票的 5 日主力净流入：

| 股票 | MCP `MainNetFlow5D`（元） | CLI `MainSum5d` | 比值 |
|---|---|---|---|
| 华正新材 sh603186 | 1,603,487,981（16.03 亿） | 160,348.80 | **10000.0** |
| 三环集团 sz300408 | 1,765,626,966（17.66 亿） | 176,562.69 | **10000.0** |

**结论**：CLI 与 `data_sector` 的资金字段单位 = **万元**（1 万元 = 10000 元）。
→ 元件板块 `mainNetInflow5d = 1,454,297.12 万元 = 145.43 亿元`
（此前日报写的"145.4亿"**是正确的**；「禁止绝对值」的旧约束基于错误假设，已撤销）

**使用规范（校准后）**：可作绝对值引用，报告统一折算为**亿元**（÷10000），并保留两位小数。

## 四、当日实测示例（2026-09-14，上证 -1.81% 普跌日）

| 板块 | 板块码 | 涨跌幅 | 上涨家数 | 主力5日净流入位次 | 龙头 |
|---|---|---|---|---|---|
| 航海装备Ⅱ（航运所在） | pt01801744 | **-1.99%** | **0/10** | 靠后（净流出） | 松发股份 -1.01% |
| 医疗服务 | pt01801156 | **+4.65%** | **47/51** | 前列（净流入） | 万邦医药 +20% |
| 生物制品 | pt01801152 | +2.40% | 46/51 | 前列 | 近岸蛋白 +20% |
| 化学制药 | pt01801151 | +2.12% | 137/149 | 中游 | 诺诚健华 +11.93% |
| 种植业（粮食所在） | pt01801016 | **-5.09%** | 3/20 | 靠后（净流出） | 国投丰乐 +5.02% |
| 元件（资金流入第一） | pt01801083 | -0.21% | 45/61 | **第 1 名** | 科翔股份 +20% |

**判读**：航运（0/10 上涨 + 净流出）T1/T2 双不满足 → **转弱信号明确**；医药系四板块集体逆势（T1 满足），
但需 ETF 互证（T3）才能升级为主线——**下一步该查医药主题 ETF 的 20 日涨幅**。

## 五、provider 层实现候选（按需，不阻塞）

| 契约方法 | CLI 等价通道 | 状态 |
|---|---|---|
| `screen({"sector":...})` | `ranking/filter --universe <板块码>` | ✅ **2026-09-18 改判生效**（09-14 曾记录为「不生效」，疑为版本差异）：实测 40 板块拉出 2934 只，返回条数与该板块家数吻合（半导体 178 / 元件 59）。**更优替代见下条** |
| `sector_of` | **`westock sector constituent <板块码>`** | ✅ **CLI 原生可用**（2026-09-18 实测）——一次调用直接拿全成分并标注总数，无需条件表达式。已用它重建「个股→板块」映射（124 板块） |
| `sector_flow_rank` | **`westock sector ranking --type mainNetInflow5d`** | ✅ **CLI 原生可用**（2026-09-18 实测）——一次返回 124 个板块的 `changePct / mainNetInflow(5d/20d) / upCount / leader`，**数值与 MCP `data_sector` 完全一致**（半导体 2437776.21 万元 = 243.78 亿）→ 日常自动化可不再依赖 MCP |
| `sector_to_etf` | `label --asset etf` + 主题匹配 | ⏳ 待实现；⚠️ ETF 持仓明细仍不可得（见第七节） |
| `sector_members_with_weight` | — | ❌ 无权重字段（板块成分只返回 code/name） |

---

## 七、CLI 通道 vs MCP 通道（2026-09-18 实测：限频应对）

**核心发现**：MCP（`mcp__westock-mcp__*`）与 CLI（`westock` / `westock-tool`）是**两条独立接入路径**。
当天实测：MCP 反复返回「服务限频」（`data_kline` / `data_quote` / `data_etf(holdings)` 均中招），
而 **CLI 全程顺畅，且同一份数据数值完全一致**（已用板块资金榜交叉验证）。

→ **策略：数据获取统一切到 CLI，MCP 仅作兜底。**

| 数据 | CLI 命令 | 状态 |
|---|---|---|
| 行情快照（PE/PB/市值/换手/区间涨幅） | `westock quote <codes>` | ✅ |
| 日K | `westock kline <code> --period day --limit N` | ✅ |
| 分钟线（用于封板时间） | `westock kline <code> --period m1 --start --end` | ✅（需指定近 1 月区间） |
| 财务（营收/研发/毛利/增速，多期） | `westock finance <codes> --type income --limit N` | ✅ |
| 条件选股（**支持财务字段**，如 `TORGrowRate > 30`） | `westock-tool filter "<expr>"` | ✅ |
| 排行榜（含 `cap_main_5d` / `limitup_days` / `fin_growth`） | `westock-tool ranking <metric>` | ✅ |
| 板块清单 + 资金/涨跌/上涨家数/龙头 | `westock sector ranking --kind industry --type mainNetInflow5d` | ✅ |
| 板块成分 | `westock sector constituent <板块码>` | ✅ |
| 交易日历 / 龙虎榜 / 指数清单 | `westock trade-calendar` / `lhb` / `index list` | ✅ |
| **ETF / 指数持仓明细** | — | ❌ **两条通道同时故障**：MCP `data_etf(holdings)` 限频 + CLI `index constituent` 报 service error → 上游服务问题，非通道选择问题 |

**⚠️ 单位陷阱（同日修复）**：`westock quote` 的 `total_market_cap` 单位是**元**（长电科技 130,627,000,000 = 1306.27 亿），不是「亿」。
脚本统一用 `to_yi()` 自动判断（>1e6 视为元）。此前按「亿」处理导致两个校验**静默失效**：情绪池「小市值庄股」红旗、分诊台 B 池「市值≥100亿」。

**⚠️ ranking cap_main_5d 缺票实测（2026-09-19）**：
中天科技（filter 排第 4 / MainNetFlow5D 16.86 亿）在 `ranking cap_main_5d --limit 1500` 榜内
**前 1489 名查无此票**；且两源数值系统性不一致且方向不固定（中材 19.21 vs 21.63 亿、
新易盛 11.79 vs 5.53 亿）。→ **资金类判据统一用 filter 口径**（MainNetFlow5D，单位「元」），
ranking 榜仅作参考且需核对覆盖性。根因待查。

**封装**：`scripts/westock_cli.py` —— quote / kline / finance / sector_list / sector_members / filter_stocks / ranking / build_sector_map

**结论**：板块维度在日常自动化中**全程走 MCP 路径**（第一、二节）；纯 Python `run_daily` 若需板块能力，
`screen_by_sector` 用「本地按成分过滤」实现，其余按上表。实现时遵守 `providers/README.md` 的 checklist。

## 六、ETF 资金通道（v0.2 新增，独立于 T3 的「价×钱」四象限）

**原理**：ETF 价格 ≈ 成分股加权涨幅（与 T1 同源、滞后）；而 **ETF 资金净流入（etfInFlow）与份额变化（etfSizeMChg）才是「钱通过 ETF 进场」的直接证据**——独立且领先。

**四象限**（配置：`settings.mainline.etf_flow_channel`）：

| 价 \ 钱 | 钱进（etfInFlow>0 或份额↑） | 钱走 |
|---|---|---|
| **价涨** | 健康主升 | **衰竭预警**（比价格降级更早） |
| **价跌** | **资金型埋伏**（观察不追） | 无信号 |

**当日三主线实测（2026-09-15）**：

| 主线 | 锚定 ETF | 价 | 钱 | 四象限结论 |
|---|---|---|---|---|
| 航运 | 船舶ETF 15.74亿 | +4.12% | 净流出（月均−828）、份额月 −6.03% | **价涨钱走 → 衰竭预警** |
| 算力 | 通信ETF 421.57亿 | −8.62% | 净流入（月均 +14292）、份额周 +1.72% | **价跌钱进 → 资金型埋伏** |
| 农业 | 粮食ETF 0.65亿 | +7.34%（当日 −3.52%） | 净流入 +160、份额月 +16.07% | 混合——**规模太小降权**（<2亿规则） |

**使用约束**：etfInFlow 绝对值单位未校准（与规模相关），**用正负号与均值比较做方向判断**；规模 <2亿 的 ETF 信号降权。
