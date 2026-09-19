# 新设备上手指南（clone 后 5 分钟跑通）

> 本文解决"换机器 clone 后跑不起来"的全部已知坑。请按顺序执行，每步都有验证命令。
> 配套：`docs/automation-daily.md`（每日自动化的重建步骤与 prompt 全文）。

## 0. 前置条件（WorkBuddy 环境）

| 组件 | 要求 | 检查方式 |
|---|---|---|
| WorkBuddy 桌面端 | 已安装并登录 | 能打开本仓库所在目录 |
| westock 连接器 | 已授权（腾讯自选股，connected） | WorkBuddy 连接器列表显示已连接 |
| Node.js | ≥18（westock-tool 需要） | `node -v` |
| Python | ≥3.9（推荐 WorkBuddy 托管版 3.13） | `~/.workbuddy/binaries/python/envs/default/bin/python -V` |

## 1. clone 与自检（第一次可能报错的点都在这里）

```bash
git clone <仓库地址> ~/Desktop/fast-trend-trade
cd ~/Desktop/fast-trend-trade

# 1) 建立依赖环境（akshare/pandas 是兜底数据源，westock 可用时非必需）
~/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -m venv ~/.workbuddy/binaries/python/envs/default 2>/dev/null || true
~/.workbuddy/binaries/python/envs/default/bin/pip install -r requirements.txt

# 2) 数据源自检（clone 后第一步，必须通过）
~/.workbuddy/binaries/python/envs/default/bin/python src/check_provider.py
```

**期望输出**：`✅ 数据源就绪：westock`。

## 2. 私有配置（通常不需要手动建）

`config/local.json` 是机器私有的（已 gitignore），**默认留空也能跑**——`src/providers/resolver.py` 会自动发现 westock 脚本：

```
~/.workbuddy/plugins/cache/*/finance-data/*/skills/westock-tool/scripts/index.js
```

只有当自动发现失败（比如插件装在非常规位置）时，才需要：

```bash
cp config/local.example.json config/local.json
# 然后把 westock_tool_js 填成实际路径
```

## 3. 每日自动化（本工程的实际运行入口）

`src/run_daily.py` 是 **v0.2 待开发项**，当前不存在——每日流程由 WorkBuddy 定时自动化驱动。
重建步骤见 `docs/automation-daily.md` 第二节（含调度时间、prompt 全文、路径替换表）。

## 4. 产物与工具

| 想做什么 | 命令 |
|---|---|
| 重建驾驶舱（读 history.json 渲染追踪台） | `<托管python> scripts/build_dashboard.py` |
| 看策略手册 | 浏览器打开 `docs/strategy-handbook.html` |
| 看趋势曲线（滑卷/全貌） | `output/trend-lines.svg` / `output/trend-lines-annual.svg` |

## 5. 已知坑速查（按报错关键字）

| 报错/现象 | 原因 | 解决 |
|---|---|---|
| `cannot lock ref ... File exists` / `Unable to create '.git/xxx.lock'` | git 操作被中断留下的锁残骸（常见于 push/fetch 被切断后） | `find .git -name "*.lock" -delete` 后重试；后续 git 网络操作需在允许网络的环境执行 |
| `ModuleNotFoundError: No module named 'providers'` | 缺包标记文件，或运行方式不被支持 | 已补齐 `src/__init__.py`、`src/providers/__init__.py`；确认用 `python3 src/check_provider.py` 或 `python3 -m src.check_provider` |
| `❌ 所有数据源均不可用` | westock 脚本没找到 + akshare 没装 | ①`node -v` 确认 Node 存在；②`ls ~/.workbuddy/plugins/cache/*/finance-data/*/skills/westock-tool/scripts/` 确认插件在；③否则 `pip install akshare` 走兜底 |
| `can't open file 'src/run_daily.py'` | 该文件是 v0.2 计划（路线图 §7 第③步），尚未开发 | 每日流程用自动化（见 `docs/automation-daily.md`） |
| `No such file or directory: .../finance-data/1.5.0/...` | 插件版本号变了，写死的路径失效 | 用自动发现（local.json 留空）或按 `*` 通配符定位实际版本目录 |
| 日报/驾驶舱没生成 | 自动化未建，或非交易日 | 见 `docs/automation-daily.md`；周末与法定节假日按设计不产出 |

## 6. 本机环境事实（新设备对照用）

| 项 | 本机值 |
|---|---|
| 仓库路径 | `/Users/liuliang19/Desktop/fast-trend-trade` |
| 托管 Python | `/Users/liuliang19/.workbuddy/binaries/python/envs/default/bin/python`（3.13.12） |
| westock-tool 脚本 | `~/.workbuddy/plugins/cache/cb_teams_marketplace/finance-data/1.5.0/skills/westock-tool/scripts/index.js` |
| 蓄势形态引擎 | `~/.workbuddy/plugins/cache/cb_teams_marketplace/finance-data/1.5.0/skills/wb-finance-skill/scripts/run_signal.py` |
| 每日自动化 | 每交易日 15:30（任务 ID `880e6067`，见 `docs/automation-daily.md`） |


---

## 环境坑补充（2026-09-18 实测，5 条）

| # | 坑 | 表现 | 解法 |
|---|---|---|---|
| 1 | 托管 Python 环境缺包 | run_signal.py 报 No module named numpy | 手动建 venv + pip install numpy pandas |
| 2 | westock-data CLI 缺装 | FileNotFoundError: westock-data | 跑官方 setup.sh -d ~/.local/bin（装出 westock v0.0.4） |
| 3 | MCP 限频 | data_kline/data_quote 反复失败 | 走 CLI（westock_cli.py 统一封装） |
| 4 | 本地代理阻断 github.com | git push 全失败（502/SSL error） | 走 push_via_api.py（Git Data API，SHA 一致无分叉） |
| 5 | 市值单位陷阱 | total_market_cap 是「元」不是「亿」 | to_yi() 自动判断；否则「≥100亿」校验静默失效 |

详细背景见 changelog-2026-09-18.md 第五节。
