"""数据源自动检测 + 优雅降级。

探测顺序（可在 settings.json data_source.order 配置）：
  westock → akshare

每级探测包含两阶段验证（缺一不可）：
  1. 存在性：命令/库是否存在
  2. 可用性：实际发起一次最小化真实调用，成功才算通过

akshare 缺失时按 settings.data_source.auto_install 自动 pip 安装（默认开）。
"""
import importlib
import subprocess
import sys


class ProviderUnavailable(Exception):
    pass


def discover_westock_tool_js() -> str:
    """自动发现 westock-tool 脚本（WorkBuddy 插件缓存目录）。

    插件目录含版本号（如 finance-data/1.5.0），换机器/升级插件后路径会变，
    因此不要在 local.json 里写死——留空时按 glob 匹配并取版本最高者。
    匹配失败再回退到 local.json 的手填路径。
    """
    from pathlib import Path
    pattern = ".workbuddy/plugins/cache/*/finance-data/*/skills/westock-tool/scripts/index.js"
    hits = sorted(Path.home().glob(pattern))
    return str(hits[-1]) if hits else ""


def _probe_westock(settings: dict) -> bool:
    """westock 双级探测：脚本存在 + 真实调通一次。

    脚本定位优先级：local.json 手填 → 自动发现（跨机器免配置的关键）。
    """
    import shutil
    from pathlib import Path
    ds = settings.get("data_source", {})
    cli = shutil.which("westock") or ds.get("westock_cli", "")
    tool_js = ds.get("westock_tool_js", "") or discover_westock_tool_js()
    if not cli and not (tool_js and Path(tool_js).exists()):
        return False
    if tool_js and Path(tool_js).exists() and not shutil.which("node"):
        print("[resolver] westock 脚本已找到，但缺少 node 运行时（请安装 Node.js ≥18）")
        return False
    try:
        if tool_js and Path(tool_js).exists():
            r = subprocess.run(["node", tool_js, "filter",
                                "intersect([PE_TTM > 0])", "--limit", "1"],
                               capture_output=True, text=True, timeout=30)
        else:
            r = subprocess.run([cli, "--version"], capture_output=True, text=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


def _probe_akshare(settings: dict, auto_install: bool = True) -> bool:
    """akshare 双级探测：import 成功 + 一次真实行情调用成功。"""
    try:
        importlib.import_module("akshare")
    except ImportError:
        if not auto_install:
            return False
        print("[resolver] akshare 未安装，自动执行 pip install akshare ...")
        for extra in ([], ["--no-cache-dir"]):
            r = subprocess.run([sys.executable, "-m", "pip", "install",
                                "akshare", "-q", *extra],
                               capture_output=True, text=True, timeout=600)
            if r.returncode == 0:
                break
            last_err = (r.stderr or r.stdout)[-500:]
            # 已知坑：jsonpath sdist 在部分环境解包报 EEXIST，
            # 先装 jsonpath 的替代：失败时提示手动处理
        else:
            print("[resolver] akshare 安装失败：", last_err)
            print("[resolver] 兜底方案：pip install jsonpath 失败时，"
                  "手动 curl 下载 sdist 解压后 pip install <解压目录>")
            return False
    try:
        import akshare as ak
        # 最小化真实调用：东财 ETF 现货列表（一次请求，验证网络与接口存活）
        df = ak.fund_etf_spot_em()
        return df is not None and len(df) > 0
    except Exception as e:
        print("[resolver] akshare 探测调用失败：", repr(e))
        return False


PROBES = {"westock": _probe_westock, "akshare": _probe_akshare}
CLASSES = {}


def _load_class(name: str):
    if name not in CLASSES:
        mod = importlib.import_module(f".{name}_provider", package=__package__)
        CLASSES[name] = getattr(mod, name.capitalize() + "Provider")
    return CLASSES[name]


def resolve_provider(settings: dict):
    """按配置顺序探测，返回第一个通过验证的 provider 实例。

    返回 (provider, fallback_note)；全链失败抛 ProviderUnavailable。
    fallback_note 记录降级路径，供日报"数据来源"小节如实标注。
    """
    ds = settings.get("data_source", {})
    order = ds.get("order", ["westock", "akshare"])
    notes = []
    for name in order:
        ok = PROBES[name](settings, ds.get("auto_install", True)) \
            if name == "akshare" else PROBES[name](settings)
        if not ok:
            notes.append(f"{name}: 不可用")
            continue
        try:
            cls = _load_class(name)
            provider = cls(settings)
            notes.append(f"{name}: ✓ 当前使用")
            print(f"[resolver] 数据源 = {name}（探测链：{' → '.join(notes)}）")
            return provider, notes
        except Exception as e:
            notes.append(f"{name}: 实例化失败 {e!r}")
    raise ProviderUnavailable("；".join(notes))
