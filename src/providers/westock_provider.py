"""westock 数据源（腾讯自选股 CLI）。仅在检测到本机 westock 环境时可用。"""
import shutil
import subprocess
import json
from pathlib import Path

from .base import DataProvider


class WestockProvider(DataProvider):
    name = "westock"

    def __init__(self, settings: dict):
        ds = settings.get("data_source", {})
        self.cli = shutil.which("westock") or ds.get("westock_cli", "westock")
        tool = ds.get("westock_tool_js")
        self.tool_js = tool if tool and Path(tool).exists() else None
        if not self.cli:
            raise RuntimeError("westock CLI 未找到")

    def _tool(self, *args) -> str:
        if not self.tool_js:
            raise RuntimeError("westock-tool 路径未配置")
        r = subprocess.run(["node", self.tool_js, *args],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise RuntimeError(r.stderr or r.stdout)
        return r.stdout

    def _cli(self, *args) -> str:
        r = subprocess.run([self.cli, *args], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise RuntimeError(r.stderr or r.stdout)
        return r.stdout

    def screen(self, expr: dict) -> list:
        # 服务端条件筛选：把统一筛选字典翻译成 westock filter 表达式
        conds = []
        fmap = {"chg20d_min": "Chg20D > {v}", "chg20d_max": "Chg20D < {v}",
                "pe_ttm_min": "PE_TTM > {v}", "pe_ttm_max": "PE_TTM < {v}",
                "turnover_rate_min": "TurnoverRate > {v}"}
        for k, tpl in fmap.items():
            if k in expr:
                conds.append(tpl.format(v=expr[k]))
        if expr.get("main_net_flow_5d_min") is not None:
            conds.append(f"MainNetFlow5D > {expr['main_net_flow_5d_min']}")
        out = self._tool("filter", f"intersect([{', '.join(conds)}])",
                         "--limit", str(expr.get("limit", 20)))
        return self._parse_md(out)

    def kline(self, code: str, limit: int = 120):
        import pandas as pd
        out = self._cli("kline", self._normalize_code(code), "--period", "day", "--limit", str(limit))
        rows, header = [], None
        for line in out.splitlines():
            if not line.strip().startswith("|") or "---" in line:
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if header is None:
                header = cells
            else:
                rows.append(cells)
        df = pd.DataFrame(rows, columns=header)
        df = df.rename(columns={"open": "open", "last": "close", "high": "high",
                                "low": "low", "volume": "volume"})
        for c in ("open", "high", "low", "close", "volume"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.dropna(subset=["close"]).reset_index(drop=True)

    def fund_flow(self, code: str, days: int = 5) -> dict:
        out = self._cli("fund", "flow", self._normalize_code(code))
        for line in out.splitlines():
            if "MainNetFlow5D" in line and "|" in line:
                cells = [c.strip() for c in line.split("|")]
                # 列名行与数据行成对出现，取数据行
        # 简化：直接返回原始文本交给上层容错解析（结构随接口版本变动）
        return {"_raw": out, "main_net_flow_5d": None, "main_net_flow_20d": None}

    def etf_rank(self, metric: str = "chg20d", limit: int = 40) -> list:
        out = self._tool("ranking", "qt_chg_interval", "--asset", "etf",
                         "--orderby", "ChgPct20D", "--min-ChgPct20D", "8",
                         "--limit", str(limit))
        return self._parse_md(out)

    @staticmethod
    def _parse_md(md: str) -> list:
        rows, header = [], None
        for line in md.splitlines():
            if not line.strip().startswith("|") or "---" in line:
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if header is None:
                header = cells
            elif header and len(cells) == len(header):
                rows.append(dict(zip(header, cells)))
        return rows
