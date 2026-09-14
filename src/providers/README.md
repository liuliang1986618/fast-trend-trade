# 数据源适配层

## 架构：自动检测 + 优雅降级链

```
启动 → 探测 westock（CLI 存在 + 真实调通）
     → 失败 → 探测 akshare（import 成功 + 真实调通；缺失时自动 pip 安装）
     → 全链失败 → 报错 + 给出手动兜底指引
```

- `resolver.py` — 探测调度器。两级验证（存在性 + 真实最小调用），第一个通过的被采用
- `westock_provider.py` — 腾讯自选股（本机私有资产，服务端筛选，最快）
- `akshare_provider.py` — 免费开源库（clone 即跑的默认兜底，`pip install akshare`）
- `base.py` — DataProvider 抽象接口：实现 4 个方法即可接入任何数据源

## 自检命令

```bash
python3 src/check_provider.py
```

输出当前生效的数据源与完整探测链路。

## 接入新数据源

实现 `DataProvider` 的 4 个方法（screen / kline / fund_flow / etf_rank），
放入本目录命名为 `<name>_provider.py`，类名 `<Name>Provider`，再在
`config/settings.json` 的 `data_source.order` 里加上 `<name>` 即可被自动发现。

## 板块维度契约（v0.2，契约先行、实现后补）

主线判据 T1–T4 需要板块维度数据（对应工程债 E1）。接口定义在 `base.py`，
**三个方法都是非抽象的、默认返回 `None`**——`None` 表示"本数据源不支持"，
**不是错误、不抛异常**；调用方见此即降级为人判（见路线图 §0 半自动定位）。
因此**现有 provider 无需任何改动即可继续工作**，实现可以按需分批补齐。

| 能力名（capabilities） | 方法 | 返回形状 | 服务的判据 |
|---|---|---|---|
| `sector_of` | `sector_of(codes)` | `{code: 板块名}`（批量 ≤200/次） | T1 板块内涨的票够多、T4 百亿中军 |
| `sector_to_etf` | `sector_to_etf(sector, min_scale_yi)` | `[{code,name,scale_yi,chg20d,track_index}]` 按规模降序 | T3 ETF 互证、日报"ETF 搭档" |
| `sector_flow_rank` | `sector_flow_rank(metric, limit)` | `[{sector,main_net_flow_5d,chg20d,stock_count}]` | T2 板块被大钱买 |
| `screen_by_sector` | `screen({...,"sector":名})` | 同 screen；服务端按板块过滤 | T1 双口径计数 |

**实现 checklist（每实现一项）**

1. 覆盖方法 → 2. 把能力名加入 `capabilities` → 3. 跑 `python3 src/check_provider.py` 确认探测链不变
   → 4. 用一只已知票验证返回形状（字段名/单位/排序）→ 5. 在 `docs/settings-v0.2-decisions.md` 或本文件记录口径

**口径要求（契约违约判定）**

- `main_net_flow_5d` 单位统一为**元**（与 `fund_flow` 一致）
- 板块 `chg20d` 必须注明加权方式（等权 / 市值加权）——口径不明会污染 T1/T4 判定
- `sector` 命名只需**同一 provider 内自洽**；跨 provider 不一致时必须重跑主线判定
- 聚合一律在数据源侧完成，禁止逐票循环（工程红线 #1）

## 工程红线

筛选逻辑尽量在服务端/SQL 端完成，禁止把全市场数据拉到本地循环过滤。
（请求次数 ∝ 命令数，不是股票数——全量下载模式会被接口方封禁。）

## 已知坑（实测记录）

- `jsonpath`（akshare 依赖）的 sdist 在部分环境 pip 解包报
  `EEXIST: file already exists`。兜底：`curl` 下载 sdist → `tar` 手动解压 →
  `pip install <解压目录>`。resolver 的 auto_install 已内置重试与提示。
- akshare 部分接口无服务端筛选能力，screen() 的实现策略是
  "一次列表请求 + 本地向量过滤"，绝不做逐票循环请求。
