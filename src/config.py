"""配置加载：settings.json（开源默认）+ config/local.json（本机私有，gitignored）深合并。

local.json 中的键优先。存在意义：开源仓库保持零机器相关路径，
私有数据源参数留在本地——泄漏面为 0。
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _deep_merge(base: dict, overlay: dict) -> dict:
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(root: Path = ROOT) -> dict:
    """加载并合并配置。settings.json 必须存在；local.json 可选。"""
    settings_path = root / "config" / "settings.json"
    cfg = json.loads(settings_path.read_text(encoding="utf-8"))
    local_path = root / "config" / "local.json"
    if local_path.exists():
        _deep_merge(cfg, json.loads(local_path.read_text(encoding="utf-8")))
    return cfg
