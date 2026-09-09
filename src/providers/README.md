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

## 工程红线

筛选逻辑尽量在服务端/SQL 端完成，禁止把全市场数据拉到本地循环过滤。
（请求次数 ∝ 命令数，不是股票数——全量下载模式会被接口方封禁。）

## 已知坑（实测记录）

- `jsonpath`（akshare 依赖）的 sdist 在部分环境 pip 解包报
  `EEXIST: file already exists`。兜底：`curl` 下载 sdist → `tar` 手动解压 →
  `pip install <解压目录>`。resolver 的 auto_install 已内置重试与提示。
- akshare 部分接口无服务端筛选能力，screen() 的实现策略是
  "一次列表请求 + 本地向量过滤"，绝不做逐票循环请求。
