"""DataProvider 抽象基类：所有数据源适配器实现这 4 个方法。"""
from abc import ABC, abstractmethod


class DataProvider(ABC):
    name = "base"

    @abstractmethod
    def screen(self, expr: dict) -> list:
        """条件筛选（优先服务端执行）。expr 为统一筛选字典：
        {"chg20d_min":0, "chg20d_max":12, "main_net_flow_5d_min":0,
         "turnover_rate_min":2, "pe_ttm_min":0, "marketcap_min_yi":100, ...}
        返回 list[dict]，每只至少含 code/name/chg20d/pe_ttm/turnover_rate/close。
        工程红线：筛选逻辑尽量在服务端/SQL 端完成，禁止本地全量循环高频请求。"""
        ...

    @abstractmethod
    def kline(self, code: str, limit: int = 120) -> "pd.DataFrame":
        """日 K 线（前复权），DataFrame 列名固定 open/high/low/close/volume，按日期升序。
        code 统一用 6 位数字字符串（如 "600737"），适配层内部自行转换市场前缀。"""
        ...

    @abstractmethod
    def fund_flow(self, code: str, days: int = 5) -> dict:
        """主力资金：{"main_net_flow_5d": float, "main_net_flow_20d": float}（单位：元）"""
        ...

    @abstractmethod
    def etf_rank(self, metric: str = "chg20d", limit: int = 40) -> list:
        """ETF 排行。metric 固定 "chg20d"（近 20 日涨幅%）。
        返回 list[dict]：code/name/scale_yi/chg20d/track_index（主题或跟踪指数）。"""
        ...

    @staticmethod
    def _normalize_code(code: str) -> str:
        """6 位代码 → 带市场前缀（6 开头 sh，其余 sz；北交所不支持）。"""
        c = code.lstrip("shz").zfill(6)
        return ("sh" if c.startswith(("6", "9")) else "sz") + c
