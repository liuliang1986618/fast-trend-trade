"""数据源适配层：统一接口 + 自动探测降级总线。

包标记文件——`resolver._load_class` 依赖 `__package__` 解析子模块，
删除本文件会导致部分运行方式（python3 -m / 打包 / IDE 索引）下
报 "No module named 'providers'"，请勿删除。
"""
