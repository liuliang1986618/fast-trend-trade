# 数据源适配层

实现 `DataProvider` 接口（见仓库 README），放入本目录即可被 run_daily.py 发现。

- `akshare_provider.py` — 模板：基于 akshare（pip install akshare）实现，字段映射见方法 docstring
- 任何数据源都可以：本地数据库、付费 API、券商接口——只要实现 4 个方法

工程红线：筛选逻辑尽量在服务端/SQL 端完成，禁止把全市场数据拉到本地循环过滤
（请求次数 ∝ 命令数，不是股票数——全量下载模式会被接口方封禁）。
