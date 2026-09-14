"""fast-trend-trade 运行入口与数据源适配层。

模块结构：
    src.config             配置加载（settings.json + local.json 深合并）
    src.check_provider     数据源自检命令（clone 后第一步）
    src.providers.base     DataProvider 统一接口
    src.providers.resolver 数据源探测与降级总线（本目录下的包标记文件不可删）
"""
