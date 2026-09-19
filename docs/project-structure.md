# 工程结构说明（Project Structure）

> 更新：2026-09-19（v3.0 迁移后定版——scripts 迁出 output/、tests/ 新增）
> 配套文档：`README.md`（速查）、`docs/strategy-handbook.html`（方法论）、`docs/commit-convention.md`（提交规范）

---

## 一、目录树

```
fast-trend-trade/
├── README.md                     项目说明（v3.0：架构/速查/文档索引）
├── LICENSE                       MIT
├── requirements.txt              Python 依赖（akshare 兜底源 / pandas；numpy 未列但 vcp 引擎需要）
├── requirements.txt 注意事项      numpy 2.5 / pandas 3.0 与 vcp 引擎不兼容（见 setup-new-machine.md）
├── .env                          GITHUB_TOKEN（本机私有，gitignore，权限 600）
├── .gitignore
│
├── config/                       【配置层】一切阈值的单一事实源
│   ├── settings.json             ★ 17 个配置块（见第六节索引）
│   └── local.example.json        本地覆盖模板（机器私有）
│
├── src/                          【框架层】官方引擎（v0.1 起的骨架，一般不动）
│   ├── run_daily.py              官方日报主流程（数据源检测 → 筛选 → 出报告）
│   ├── config.py                 配置加载
│   ├── check_provider.py         数据源自检
│   └── providers/                数据源抽象
│       ├── base.py               接口基类
│       ├── westock_provider.py   腾讯自选股源（主力）
│       ├── akshare_provider.py   akshare 源（兜底）
│       └── resolver.py           源自动发现与降级
│
├── scripts/                      【施工层】每日流水线与工具（22 个，见第三节）
│
├── tests/                        【测试层】最小冒烟（提交前必跑）
│   └── test_smoke.py             5 项检查：语法 / import / 术语 / 台账 schema / 单位哨兵
│
├── docs/                         【文档层】13 份（见第七节索引）
│
└── output/                       【产物层】全部生成物（见第二节明细）
    ├── history.json              ★★ 台账（核心数据资产，append-only）
    ├── dashboard.html            驾驶舱（build_dashboard_full.py 重建）
    ├── daily/                    每日日报（<date>.html 单列版 + <date>-layered.html 四层版）
    ├── daily-run/                run_daily 官方产物
    ├── snapshots/                驾驶舱按日快照
    ├── trend-lines*.svg          趋势线图
    └── tmp/                      中间数据（gitignore：三池 JSON / 财务缓存 / 板块映射 / K线缓存）
```

---

## 二、output/ 结构与职责（v3.1 按日历组织）—— 以后按此设计日渐积累

### 2.1 顶层一览

```
output/
├── daily/<date>/     一天 = 一个目录（当天页面 + 过程数据全部在内）
├── ledger/           跨日台账（唯一按天演化的活资产）
├── cache/            与天无关的基础设施（可重建/覆盖更新）
├── charts/           趋势线 SVG（由 index 页内嵌引用）
├── archive/          本地备份（手动）
└── dashboard.html    驾驶舱独立版（兼容副本；主页面为 daily/<最新>/index.html）
```

### 2.2 每目录职责与积累规则

| 路径 | 职责 | 积累方式 | 入库 |
|---|---|---|---|
| `daily/<date>/index.html` | **当天唯一页面**：四层架构 + 驾驶舱全景合并（26 区块） | 每交易日 1 份（render_daily.py） | ✅ |
| `daily/<date>/dashboard.html` | 当日驾驶舱快照（独立版，历史回看用） | 每交易日 1 份（build_dashboard_full.py） | ✅ |
| `daily/<date>/data/growth_pool.json` | 当日 B 预期驱动池（含买点四档） | 每交易日覆盖写入 | ✅ |
| `daily/<date>/data/emotion_pool.json` | 当日情绪池（温度计/梯队/封板时间/红旗） | 每交易日覆盖写入 | ✅ |
| `daily/<date>/data/etf_holdings.json` | 当日 ETF 持仓反查（双来源） | 每交易日覆盖写入 | ✅ |
| `daily/<date>/data/a_pool_scored.json` | 当日 A 池五维规则分 | 每交易日覆盖写入（score_stable） | ✅ |
| `daily/<date>/data/screen/*` | 当日筛选中间产物（证据链：探测/确认/榜单 md） | 每交易日新增 | ✅ |
| `daily/<date>/report.html`、`layered.html` | 单列版/旧四层版（**已退役**，存量归位） | 不再新增 | ✅ 存量 |
| `ledger/history.json` | ★ 跨日台账：days 快照（滚动 90 天）+ rotation（滚动 250 天）+ pool_tracking（三池跟踪，append-only） | 每交易日更新 | ✅ |
| `cache/sector_map.json` | 板块成分映射（124 板块/5542 只，行业排除与板块标签依赖） | 建一次，板块变动时重建 | ❌ |
| `cache/kline/` | K线/榜单缓存（避免重复拉取） | 覆盖更新 | ❌ |
| `cache/cap5d.md` / `finance_cache.json` | 资金榜/财务缓存 | 每次重拉覆盖 | ❌ |
| `charts/trend-lines*.svg` | 趋势强度曲线（每日粒度）+ 一年全貌——index 页内嵌 | 每交易日覆盖更新（build_dashboard_full） | ✅ |
| `archive/` | 本地备份（.bak 等） | 偶发手动 | ❌ |
| `dashboard.html` | 驾驶舱独立版副本（兼容入口；与当日 index 同源不同排版） | 每交易日覆盖 | ✅ |

### 2.3 积累与滚动规则（设计约定）

1. **每交易日新增**：`output/daily/<当日>/` 一个目录（index.html + dashboard.html + data/）
2. **每交易日更新**：`ledger/history.json`、`cache/*`（覆盖）、`charts/*`（覆盖）、`dashboard.html`（覆盖）
3. **滚动**：台账 days 快照滚动保留 90 天；rotation 序列滚动 250 天（由 daily_run 的 update_history 执行）
4. **append-only**：`pool_tracking`（三池跟踪）不滚动、不覆盖——20 日裁决后按结论决定去留
5. **不自动清理**：daily/<date>/ 的历史档案全保留（约 200 KB/天，一年 ≈ 50 MB 可接受）；archive/ 手动管理
6. **已取消**：`tmp/`（过程数据归位到所属日期目录）；`daily-run/`（官方引擎冒烟产物已删）

## 三、scripts/ 脚本清单（22 个，4 类）

### A. 每日流水线（数据 → 池 → 台账 → 日报）

| 脚本 | 职责 | 输入 | 输出 |
|---|---|---|---|
| `daily_run_<date>.py` | 当日快照渲染器（数据硬编码 + 单列日报 + 台账快照） | 当日筛选实测 | `daily/<date>.html` + history.json |
| `build_growth_pool.py` | **B 预期驱动池**：全市场财务筛 → 分诊 → 行业排除 → 技术面买点 | filter + quote + finance | `tmp/growth_pool_<date>.json` |
| `build_emotion_pool.py` | **C 情绪池**：连板梯队 + 涨停池 + 温度计 + 五角色 + 红旗 | ranking + filter + quote | `tmp/emotion_pool_<date>.json` |
| `build_etf_holdings.py` | ETF 持仓反查（指数精确 / 板块市值近似，双来源） | index/sector + quote | `tmp/etf_holdings_<date>.json` |
| `score_stable.py` | **A 池五维规则分**（主线/地位/蓄势/资金/距买点） | STABLE_LIST + cap 榜 + VCP | `tmp/a_pool_scored.json` |
| `track_pools.py` | **三池跟踪台账**：record / price / backfill（T+3/5/10/20）/ stats | 三池 JSON + quote | history.json pool_tracking |
| `build_fengban.py` | 情绪梯队封板时间（分钟线回溯首封 + 尾盘封板状态） | minute + quote | 写回 emotion_pool JSON |
| `render_v3_layered.py` | **四层架构日报**（天气/汇合/分诊/双通道/时间，末尾自动术语自检） | daily_run + 各 JSON | `daily/<date>-layered.html` |
| `build_dashboard_full.py` | 驾驶舱（三段式 + 三池总览 + 形态分布） | history.json + JSON | `dashboard.html` |

### B. 数据通道

| 脚本 | 职责 |
|---|---|
| `westock_cli.py` | ★ CLI 统一封装（quote/kline/finance/sector/filter/ranking/build_sector_map）——规避 MCP 限频 |
| `fetch_kline.py` | K线转 CSV（环境兼容工具） |
| `vcp_score.py` | 蓄势分复刻（run_signal vcp 引擎同源公式） |
| `trend_score.py` | 主线趋势强度分复刻 |

### C. 工具

| 脚本 | 职责 |
|---|---|
| `daily_pipeline.py` | ★ 一键流水线（6 步串联，失败即停，幂等） |
| `lint_report.py` | 术语自检（黑话/T 编号/必需区块；prompt 语言规范的执行者） |
| `push_via_api.py` | 备用推送（Git Data API；token 从 .env 读） |
| `backfill_daily.py` | 历史日报补跑 |

### D. 历史保留

| 脚本 | 说明 |
|---|---|
| `build_dashboard.py` | 旧版驾驶舱（已被 _full 取代，留作参照） |
| `daily_run_20260915/17.py` | 历史日快照渲染器（每日复制制的旧模式，待参数化） |

---

## 四、每日数据流

```
每个交易日 15:30（WorkBuddy 自动化）
│
├─ ① run_daily 流程（AI 主任务，见 automation-prompts.md 任务一）
│     拉数据 → 漏斗筛选 → 主线判定 → 单列日报 → 台账 days 快照
│
└─ ② daily_pipeline.py（v0.3 流水线，或 AI 按步骤 9.5 逐个执行）
      a. build_growth_pool.py        B 池（含买点四档）
      b. build_etf_holdings.py       ETF 持仓反查
      c. build_emotion_pool.py       C 情绪池
      d. track_pools.py              台账 record + price + backfill   ← 20 日裁决数据源
      e. score_stable.py --json      A 池规则分
      f. render_v3_layered.py        四层日报（末尾自动术语自检）
      g. build_dashboard_full.py     驾驶舱（含三池总览）
      h. build_fengban.py            封板时间
```

---

## 五、config/settings.json 配置块索引（17 个）

| 块 | 职责 |
|---|---|
| `market` / `data_source` / `output` | 市场与输出基础配置 |
| `funnel` | 选股漏斗阈值（探测/确认/启动/主升档位） |
| `mainline` | 主线判定（资金/涨停双轨 + stock_pattern 四态） |
| `etf_funnel` | ETF 漏斗（T3 方向闸 + 资金四象限） |
| `score` | 评分框架 |
| **`species_classifier`** | **v0.3 物种分诊台**（A/B/C 判据 + 反闸 + 纪律 + `_refs` 判据出处 + 行业排除 + 验证规则） |
| `species_hard_gate` | 旧硬闸（已标 `_deprecated`，保留兼容） |
| `state_machine` | 观察池状态机（状态与推进规则） |
| `vcp` | 蓄势形态引擎参数 |
| `risk_switches` | 风控开关 |
| `tracking` / `tracking_score` | 跨日跟踪与趋势强度分 |
| `score_alert` | 预警规则（L1/L2） |
| `emotion_pool` | 情绪池（五指标阈值 + 五角色 + 高危红旗 + 视觉规范） |

---

## 六、全局约定

| 约定 | 内容 | 执行者 |
|---|---|---|
| **日期** | 脚本用 `data_day()`（台账最后快照日），禁用 today() | 各 build 脚本 |
| **资金口径** | 统一 filter 的 `MainNetFlow5D`（单位「元」）；ranking 榜有缺票，仅作参考 | score_stable / 日报 |
| **市值单位** | `total_market_cap` 是「元」→ 统一过 `to_yi()` | westock_cli.to_yi |
| **术语** | 禁黑话（统一用语对照见 lint_report.py；「蓄势形态（VCP）」括号注记允许） | lint_report.py |
| **名词小词典** | 日报开头 + 驾驶舱顶部必须有 | lint_report.py 必需区块检查 |
| **提交** | 六要素 message（背景/改动/成果/验证/影响/遗留） | docs/commit-convention.md |
| **提交前** | `python3 tests/test_smoke.py`（10 秒）+ `git status --short` 无残留 | tests/test_smoke.py |
| **判据出处** | 一切阈值改动的依据写入 settings.json 的 `_refs` / `_desc` | 人工 |

---

## 七、文档索引

见 `README.md`「文档索引」节（11 份导航）。
