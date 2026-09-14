# src/

## 当前状态（v0.1）

| 模块 | 状态 |
|---|---|
| `config.py` | ✅ 配置加载（settings + local 深合并，私有路径零泄漏） |
| `check_provider.py` | ✅ 数据源自检命令（clone 后第一步跑这个） |
| `providers/` | ✅ 数据源自动检测 + 降级链（westock → akshare），详见 `providers/README.md` |
| `run_daily.py` | ✅ **v0.2 最小闭环可用**——正向漏斗（探测层+确认层）+ 反向漏斗（ETF 20 日榜）→ 日报 HTML 落盘 `output/daily-run/`。**不含**（由 WorkBuddy 每日自动化负责）：主线判定 T1-T4 / 互证矩阵 / 蓄势形态 / 观察池状态机 / 驾驶舱 / 台账 |

## run_daily.py 用法

```bash
python3 src/run_daily.py --dry-run     # 只打印统计，不写文件
python3 src/run_daily.py               # 落盘 output/daily-run/YYYY-MM-DD.html
python3 src/run_daily.py --out /tmp/x.html
```

产物与 WorkBuddy 每日自动化**分离**（`output/daily-run/` vs `output/daily/`），互不覆盖。

## run_daily.py 设计约定（开发时遵守）

```
入口流程：load_config() → resolve_provider() → 各漏斗 → 评分 → 渲染 output/
```

- 全部阈值从 `config/settings.json` 读取，代码内不出现魔法数字
- 数据访问只经 DataProvider 接口，禁止直接 import 某个 provider
- 中间层只输出数量（漏斗计量），名单只出终产物 + 探测层头部
- 日报 HTML 含内联 JS 时必须语法校验后交付
- 请求次数控制：单次运行 = 探测层 1 + 确认层 1 + ETF 榜 1（工程红线 #1）

## 自检

```bash
python3 src/check_provider.py
```
