#!/usr/bin/env python3
"""数据源检测命令：python3 src/check_provider.py
只做探测不跑策略，用于 clone 后第一步自检。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from providers.resolver import resolve_provider, ProviderUnavailable  # noqa: E402
from config import load_config  # noqa: E402


def main():
    print("=" * 46)
    print("fast-trend-trade 数据源自检")
    print("=" * 46)
    try:
        cfg = load_config()
        provider, notes = resolve_provider(cfg)
        for n in notes:
            print("  ·", n)
        print("-" * 46)
        print(f"✅ 数据源就绪：{provider.name}")
        print("   下一步：每日自动化见 docs/automation-daily.md")
        print("   （src/run_daily.py 属 v0.2 待开发项，见 docs/TODO-optimization-roadmap.md §7）")
        return 0
    except ProviderUnavailable as e:
        print("  ·", e)
        print("❌ 所有数据源均不可用")
        print("   手动安装兜底源：pip install akshare")
        return 1


if __name__ == "__main__":
    sys.exit(main())
