"""DataProvider 抽象基类：所有数据源适配器实现这 4 个方法。

v0.2 新增「板块维度契约」（见下方 SectorContract 区块）：
为 T1-T4 主线判据自动化提供数据基础（对应工程债 E1）。
**契约先行、实现后补**——板块方法是非抽象的，默认返回 None 表示"本数据源不支持"，
调用方见此即降级为人判（见 docs/TODO-optimization-roadmap.md §0 半自动定位），
因此现有 provider 无需任何改动即可继续工作。
"""
from abc import ABC, abstractmethod


class DataProvider(ABC):
    name = "base"

    #: 已声明的板块维度能力集合（子类按需覆盖，并在实现后同步声明）。
    #: 取值："sector_of" | "sector_to_etf" | "sector_flow_rank" | "screen_by_sector"
    capabilities: frozenset = frozenset()

    def supports(self, cap: str) -> bool:
        """查询是否支持某项板块能力。调用方据此决定走高自动化还是人判降级。"""
        return cap in self.capabilities

    @abstractmethod
    def screen(self, expr: dict) -> list:
        """条件筛选（优先服务端执行）。expr 为统一筛选字典：
        {"chg20d_min":0, "chg20d_max":12, "main_net_flow_5d_min":0,
         "turnover_rate_min":2, "pe_ttm_min":0, "marketcap_min_yi":100, ...}
        可选键 "sector"：板块名，要求**服务端按板块过滤**（服务 T1 双口径计数的"主升口径"）。
        不支持板块过滤的 provider 必须忽略该键并在 note 中显式标注——不得静默假装已过滤（工程债 E3 教训）。
        返回 list[dict]，每只至少含 code/name/chg20d/pe_ttm/turnover_rate/close。
        工程红线：筛选逻辑尽量在服务端/SQL 端完成，禁止本地全量循环高频请求。"""
        ...

    @abstractmethod
    def kline(self, code: str, limit: int = 120) -> "pd.DataFrame":
        """日 K 线（前复权），DataFrame 列名固定 open/high/low/close/volume，按日期升序。
        code 统一用 6 位数字字符串（如 "600000"），适配层内部自行转换市场前缀。"""
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

    # ================= SectorContract：板块维度契约（v0.2） =================
    # 设计原则：
    #   1) 契约先行、实现后补 —— 三个方法均为**非抽象**，默认返回 None（= 本数据源不支持），
    #      不抛异常；调用方见 None 即降级为人判，系统照常运行。
    #   2) 实现方在覆盖方法后，须把对应能力名加入 self.capabilities。
    #   3) 服务端优先：所有方法都必须尽量在数据源侧完成聚合，禁止逐票循环请求。
    #   4) 命名空间统一：三个方法的 sector 字段共用同一套板块命名（同一 provider 内自洽即可，
    #      跨 provider 不要求一致；跨源切换时须重跑主线判定）。

    def sector_of(self, codes: list) -> "dict | None":
        """个股 → 板块归属（批量）。服务 T1（板块内涨的票够不够多）与 T4（板块内百亿中军）。

        :param codes: 6 位代码列表（单次 ≤200 个；适配层内部自行分批，禁止逐票请求）
        :return: {"600150": "船舶制造", ...}；无归属的 code 不出现在结果中；不支持返回 None
        """
        return None

    def sector_to_etf(self, sector: str, min_scale_yi: float = 5.0) -> "list | None":
        """板块 → 锚定 ETF（服务 T3 互证判定与日报"ETF 搭档"输出）。

        :param sector: 板块名（与 sector_of / sector_flow_rank 的 sector 同一命名空间）
        :param min_scale_yi: 规模下限（亿元），低于此的 ETF 过滤掉
        :return: [{"code":"sh560710","name":"船舶ETF富国","scale_yi":15.97,
                   "chg20d":8.44,"track_index":"中证船舶"}, ...]，按 scale_yi 降序；
                 有板块但无匹配 ETF 返回 []；不支持返回 None
        """
        return None

    def sector_flow_rank(self, metric: str = "main_net_flow_5d", limit: int = 20) -> "list | None":
        """板块资金排名（服务 T2"板块被大钱买"必要判据）。

        :param metric: 固定 "main_net_flow_5d"（板块主力 5 日净流入合计，单位：元，与 fund_flow 同口径）
        :param limit: 返回前 N 名（按 metric 降序）
        :return: [{"sector":"船舶制造","main_net_flow_5d":1.23e9,"chg20d":9.1,
                   "stock_count":42}, ...]；不支持返回 None
        :note: chg20d 的加权口径（等权 / 市值加权）由 provider 在返回值附带键 "note" 中注明，
               或在其类文档中声明——口径不明会污染 T1/T4 判定，视为契约违约。
        """
        return None

    @staticmethod
    def _normalize_code(code: str) -> str:
        """6 位代码 → 带市场前缀（6 开头 sh，其余 sz；北交所不支持）。"""
        c = code.lstrip("shz").zfill(6)
        return ("sh" if c.startswith(("6", "9")) else "sz") + c
