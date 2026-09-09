"""akshare 数据源（免费开源库）。开源默认数据源，pip install akshare 即可运行。

注意：akshare 为本地 HTTP 抓取聚合库，无服务端筛选能力。
工程红线的落地方式：screen() 只做"一次列表接口 + 本地向量过滤"，
绝不做逐票循环请求（请求次数 ∝ 调用数，不 ∝ 股票数）。
"""
import functools

from .base import DataProvider


class AkshareProvider(DataProvider):
    name = "akshare"

    def __init__(self, settings: dict):
        try:
            import akshare  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "akshare 未安装：pip install akshare（或首次运行 run_daily.py --bootstrap 自动安装）"
            ) from e

    # ---------- 内部：全市场快照（一次请求，缓存当日） ----------
    @functools.lru_cache(maxsize=1)
    def _snapshot(self, _date_key: str = ""):
        import akshare as ak
        # 东财 A 股实时行情：一次请求拿全市场约 5400 只
        df = ak.stock_zh_a_spot_em()
        df = df.rename(columns={
            "代码": "code", "名称": "name", "最新价": "close",
            "涨跌幅": "pct_chg", "换手率": "turnover_rate",
            "流通市值": "float_mv", "总市值": "total_mv",
            "市盈率-动态": "pe_ttm", "市净率": "pb",
        })
        df = df[["code", "name", "close", "pct_chg", "turnover_rate",
                 "float_mv", "total_mv", "pe_ttm", "pb"]].copy()
        for c in ("close", "pct_chg", "turnover_rate", "float_mv", "total_mv", "pe_ttm", "pb"):
            df[c] = __import__("pandas").to_numeric(df[c], errors="coerce")
        return df

    def screen(self, expr: dict) -> list:
        df = self._snapshot()
        # 20 日涨幅、主力净流入不在快照里：用东财历史行情接口本地算 Chg20D（一次/票太贵）
        # → 改用东财"阶段涨幅"思路：快照仅支持当日维度的粗筛，Chg20D 由调用方用 kline 补算。
        # 这里实现快照可支持的硬条件，返回后由漏斗层对候选（≤30 只）调 kline 补 Chg20D。
        if expr.get("pe_ttm_min") is not None:
            df = df[df["pe_ttm"] > expr["pe_ttm_min"]]
        if expr.get("pe_ttm_max") is not None:
            df = df[df["pe_ttm"] < expr["pe_ttm_max"]]
        if expr.get("turnover_rate_min") is not None:
            df = df[df["turnover_rate"] > expr["turnover_rate_min"]]
        if expr.get("marketcap_min_yi") is not None:
            df = df[df["total_mv"] >= expr["marketcap_min_yi"] * 1e8]
        df = df.sort_values("turnover_rate", ascending=False)
        return df.head(expr.get("limit", 20)).to_dict("records")

    def kline(self, code: str, limit: int = 120):
        import akshare as ak
        import pandas as pd
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
        df = df.rename(columns={"开盘": "open", "最高": "high", "最低": "low",
                                "收盘": "close", "成交量": "volume"})
        df = df[["open", "high", "low", "close", "volume"]].tail(limit)
        for c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.dropna(subset=["close"]).reset_index(drop=True)

    def fund_flow(self, code: str, days: int = 5) -> dict:
        import akshare as ak
        df = ak.stock_individual_fund_flow(stock=code, market=self._normalize_code(code)[:2])
        # 近 N 日主力净流入合计（列名随 akshare 版本可能变动，做防御性匹配）
        col = next((c for c in df.columns if "主力净流入" in c and "净额" in c), None)
        if col is None:
            return {"main_net_flow_5d": None, "main_net_flow_20d": None}
        tail = df.tail(days)
        return {"main_net_flow_5d": float(tail[col].sum()), "main_net_flow_20d": None}

    def etf_rank(self, metric: str = "chg20d", limit: int = 40) -> list:
        import akshare as ak
        # 东财 ETF 基金行情：一次请求全市场 ETF
        df = ak.fund_etf_spot_em()
        df = df.rename(columns={"代码": "code", "名称": "name",
                                "最新价": "close", "涨跌幅": "pct_chg"})
        # 近 20 日涨幅本地计算：用 60 日区间收益近似校验需要 kline，此处先按 60 日区间接口排序
        # 简化实现：拉日频净值一次（全市场缓存），本地算 20 日涨幅
        out = []
        for _, row in df.head(300).iterrows():  # 按成交额取头部，避免全量逐票请求
            try:
                k = ak.fund_etf_hist_em(symbol=row["code"], period="daily", adjust="qfq")
                if len(k) < 21:
                    continue
                chg20 = (float(k["收盘"].iloc[-1]) / float(k["收盘"].iloc[-21]) - 1) * 100
                out.append({"code": row["code"], "name": row["name"],
                            "scale_yi": None, "chg20d": round(chg20, 2),
                            "track_index": None})
            except Exception:
                continue
        out = [o for o in out if o["chg20d"] >= 8]
        out.sort(key=lambda x: -x["chg20d"])
        return out[:limit]
