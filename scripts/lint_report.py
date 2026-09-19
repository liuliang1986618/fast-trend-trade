#!/usr/bin/env python3
"""日报术语自检 —— 把项目「语言规范（铁律，优先级最高）」变成可执行检查。

【立此脚本的原因】（2026-09-19）
    四层架构重构时丢失了「名词小词典」区块，并把内部判据编号 T1~T5 直接暴露给读者
    （共 20 处），违反 prompt 的禁黑话铁律，用户当场提出质疑。
    为避免同类问题再犯，把规范固化为检查：任何日报/驾驶舱产物在提交前都过一遍。

【检查项】
    1. 禁用黑话（按 prompt 的「统一用语对照」表）
    2. 内部判据编号 T1~T5（不得出现在面向读者的正文）
    3. 必需的「名词小词典」区块是否存在

【白名单】（允许出现的形态）
    · 「蓄势形态（VCP）」——括号注记形式，prompt 明文允许
    · 「A 趋势池 / B 预期驱动池 / C 情绪池」——物种名（用户在对话中使用过「趋势票/情绪票」，
      且词典内有解释），不属于黑话

用法：
    python3 output/scripts/lint_report.py [html路径 ...]
    （无参数 → 自动检查 output/daily/ 下最新的 *-layered.html 与 *.html）
退出码：0 = 通过；1 = 发现违规（可直接用于 CI / 提交前钩子）
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# prompt「统一用语对照」表 —— 左为禁用词，右为规范用语
JARGON = {
    "A轨": "资金主线", "B轨": "涨停主线",
    "预热区": "刚起步", "预热": "刚起步",
    "扩散尾声": "尾声",
    "共振区": "互证", "共振": "互证",
    "正向漏斗": "选股漏斗", "反向漏斗": "ETF反查",
    "探测层": "早期埋伏名单", "确认层": "主升名单",
    "触发价": "突破价", "失效价": "认错价",
    "趋势池": "稳做名单", "博弈池": "快打名单", "独立趋势池": "单飞名单",
    "多头池": "站上所有主要均线的股票",
    "左翼": "（删去）", "右翼": "（删去）",
}

# 内部判据编号（不得出现在正文）
CODED_TERMS = ["T1", "T2", "T3", "T4", "T5"]

# 白名单：先移除这些片段，再扫描
WHITELIST = [
    r"蓄势形态\s*[（(]\s*VCP\s*[）)]",          # prompt 明文允许的括号注记
    r"[ABC]\s*(趋势池|预期驱动池|情绪池|情绪)",  # 三池物种名
    r"稳做名单|快打名单|单飞名单",               # 规范用语本身
]

# 必须存在的区块（prompt 要求「日报开头固定放」）
REQUIRED_BLOCKS = [("名词小词典", "prompt 要求日报开头固定放名词小词典区块")]


def lint(path: Path) -> list:
    """返回违规清单 [(类型, 词, 建议, 上下文)]。"""
    html = path.read_text(encoding="utf-8")
    # 去标签后检查正文（避免 CSS/属性名误伤）
    text = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    # 移除白名单片段
    for pat in WHITELIST:
        text = re.sub(pat, " ", text)

    issues = []
    for bad, good in JARGON.items():
        for m in re.finditer(re.escape(bad), text):
            i = m.start()
            issues.append(("黑话", bad, good, text[max(0, i - 40):i + 40]))
    for t in CODED_TERMS:
        for m in re.finditer(rf"\b{t}\b", text):
            i = m.start()
            issues.append(("内部编号", t, "改为口语表达（如 T1→上涨面）",
                           text[max(0, i - 40):i + 40]))
    for block, why in REQUIRED_BLOCKS:
        if block not in text:
            issues.append(("缺失区块", block, why, "（未找到）"))
    return issues


def main() -> int:
    args = sys.argv[1:]
    if args:
        paths = [Path(a) for a in args]
    else:
        d = ROOT / "output" / "daily"
        cands = sorted(d.glob("*-layered.html")) + sorted(d.glob("2*.html"))
        paths = list(dict.fromkeys(cands))[-2:] if cands else []

    if not paths:
        print("未找到待检查的日报文件")
        return 1

    total = 0
    for p in paths:
        if not p.exists():
            print(f"⚠️  {p} 不存在，跳过")
            continue
        issues = lint(p)
        total += len(issues)
        print(f"{'✅' if not issues else '❌'} {p.name} —— {'通过' if not issues else f'{len(issues)} 处违规'}")
        for kind, word, fix, ctx in issues[:12]:
            print(f"     [{kind}] 「{word}」→ 应为「{fix}」")
            print(f"        上下文：…{ctx.strip()}…")
        if len(issues) > 12:
            print(f"     …另有 {len(issues) - 12} 处")

    print()
    if total:
        print(f"❌ 合计 {total} 处违规 —— 请按 prompt「语言规范」修正后再提交")
        return 1
    print("✅ 术语自检通过（黑话 / 内部编号 / 必需区块 三项检查）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
