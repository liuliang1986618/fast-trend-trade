# fast-trend-trade

> **三物种分诊的 A 股趋势交易筛选框架**：四层架构（筛选 → 分诊 → 执行 → 验证）。
> 正向漏斗（个股→主线）× 反向漏斗（ETF→成分股）→ 交叉验证 → 分物种纪律 → 数据裁决。

> ⚠️ **免责声明（请先阅读）**：本项目仅为量化筛选框架与个人研究工具，不构成任何投资建议。市场有风险，投资需谨慎。任何投资决策应结合个人风险承受能力、资金状况和投资目标独立判断，必要时咨询持牌专业机构。过往表现不预示未来收益。

> 🚧 **当前版本 v3.0**（2026-09-19）：三池分诊台、四层架构日报、五维规则化评分、三池跟踪台账、术语自检、CLI 数据通道已全部就位。**验证期进行中**——三池胜率对比将于约 20 个交易日后（10 月中下旬）出结果，届时用数据裁决 PE 硬闸去留与五维阈值校准。

> 🧭 **定位**：本系统是**半自动决策支持系统**——机器筛漏斗、算分、盯状态机；人做终审与催化判断。这不是待修复的缺陷，是设计定位。完整人机分工表见 `docs/TODO-optimization-roadmap.md` §0。

> 🔁 **换机器/新设备**：直接看 `docs/setup-new-machine.md`（clone 后 5 分钟跑通 + 环境坑 5 条速查）；每日自动化的重建见 `docs/automation-daily.md`。

## 它解决什么问题

动量策略的经典困境是"确认即滞后"：等四维指标（均线多头/涨幅/量价/资金）全部确认，趋势已经走完一半。本框架的解法：

1. **双向锚定**：正向漏斗（个股→主线）与反向漏斗（ETF→成分股反查）交叉验证，双确认 = 互证，信号最强
2. **三物种分诊**：A 趋势池 / B 预期驱动池（未盈利但成长性可验证）/ C 情绪池——筛选与分类分离，判别错物种 = 用错打法 = 亏损第一原因
3. **成长性有出口**：PE 硬闸从「入口门卫」改为「分诊台」——未盈利但成长性可验证（营收≥30%+研发≥15%）的票不再被静默丢弃，进入独立账本接受数据检验
4. **状态机执行**：R 单位仓位法 + 移动止盈，赚"看对时拿满、看错时亏小"的期望值

## 架构（v3.0 四层）

```
第一层 筛选：正向（个股→主线，技术趋势+资金）× 反向（ETF→成分股）→ 互证矩阵 → 候选集
第二层 分诊：A 趋势池（PE∈[0,80]·PB≤8·扣非盈利）｜B 预期驱动池（营收≥30%·研发≥15%·增速未转负）
             ｜C 情绪池（涨停/连板）｜D 淘汰
第三层 执行：A 仓位≤20%·让利润奔跑 ｜ B 仓位≤10%·独立账本·止损-5% ｜ C 机动仓≤5%·快进快出
第四层 验证：三池分别记录 T+3/5/10/20 表现 → 20 交易日对比胜率 → 跑输者重校规则（数据裁决）
```

完整方法论（判据、反闸、纪律、数据出处）见 `docs/strategy-handbook.html`（v3.0）。

## 快速开始

```bash
git clone https://github.com/liuliang1986618/fast-trend-trade.git
cd fast-trend-trade
# 数据通道安装与已知坑 → docs/setup-new-machine.md（5 分钟）
# 每日运行 → docs/automation-daily.md（含运行顺序表）
```

### 数据源（可插拔）

本项目不绑定任何数据源。当前主力为腾讯自选股 CLI（`westock`），`src/providers/` 下实现统一接口即可接入其他源：

```python
class DataProvider:
    def screen(self, expr: dict) -> list: ...                  # 条件筛选（服务端优先）
    def kline(self, code: str, limit: int) -> DataFrame: ...   # OHLCV
    def fund_flow(self, code: str, days: int) -> dict: ...     # 主力资金
    def etf_rank(self, metric: str) -> list: ...               # ETF 排行
```

筛选逻辑尽量下沉到服务端（避免全量下载——请求次数 ∝ 命令数而非股票数，这是本项目最重要的工程约束）。

## 常用命令速查

| 命令 | 用途 |
|---|---|
| `python3 scripts/daily_pipeline.py` | **每日全流程**（三池 + 台账 + 四层日报）|
| `python3 scripts/lint_report.py` | 术语自检（黑话/内部编号/必需区块）|
| `python3 scripts/track_pools.py stats` | 三池跟踪统计 |
| `python3 scripts/score_stable.py` | A 池五维规则分 |
| `python3 tests/test_smoke.py` | **冒烟测试（提交前必跑，10 秒）**|
| `python3 scripts/push_via_api.py` | 推送远端（自动读 `.env` token）|

## 目录

```
config/     一切阈值的单一事实源（settings.json，17 个配置块含判据出处）
src/        官方框架（run_daily 主流程 + providers 数据源抽象）
docs/       13 份文档（方法手册 / 自动化 / 数据接入 / 规范 / 归档）
output/     产物（daily 日报 / dashboard 驾驶舱 / history.json 台账 / scripts 施工脚本）
tests/      最小冒烟测试（语法 / import / 术语 / 台账 schema / 单位哨兵）
```

## 文档索引

| 文档 | 内容 |
|---|---|
| `docs/strategy-handbook.html` | **总方法论文档**（v3.0：判据/纪律/演进记录）|
| `docs/automation-daily.md` | 每日自动化配置与运行顺序表 |
| `docs/automation-prompts.md` | 自动化 prompt 快照（配置事实源）|
| `docs/sector-data-integration.md` | 板块数据接入 + CLI/MCP 通道对照 |
| `docs/commit-convention.md` | 提交规范（六要素 + 自查清单）|
| `docs/changelog-2026-09-18.md` / `-19.md` | 两日变更归档 |
| `docs/validation-plan.md` | 验证体系与三池裁决 |
| `docs/setup-new-machine.md` | 换机指南 + 环境坑 |

## 调参

所有策略参数集中在 `config/settings.json`——改配置就是改策略，不要改代码。每个字段带 `_desc` 说明设计意图，判据出处见 `species_classifier._refs`。
