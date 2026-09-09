# src/

## 当前状态（v0.1）

| 模块 | 状态 |
|---|---|
| `config.py` | ✅ 配置加载（settings + local 深合并，私有路径零泄漏） |
| `check_provider.py` | ✅ 数据源自检命令（clone 后第一步跑这个） |
| `providers/` | ✅ 数据源自动检测 + 降级链（westock → akshare），详见 `providers/README.md` |
| `run_daily.py` | 🚧 开发中——每日主循环（正向漏斗 → 反向漏斗 → 共振矩阵 → 评分 → 日报渲染） |

## run_daily.py 设计约定（开发时遵守）

```
入口流程：load_config() → resolve_provider() → 各漏斗 → 评分 → 渲染 output/
```

- 全部阈值从 `config/settings.json` 读取，代码内不出现魔法数字
- 数据访问只经 DataProvider 接口，禁止直接 import 某个 provider
- 中间层只输出数量（漏斗计量），名单只出终产物 + 探测层头部
- 日报 HTML 含内联 JS 时必须语法校验后交付

## 自检

```bash
python3 src/check_provider.py
```
