#!/usr/bin/env python3
"""情绪梯队封板时间分析（批次 5）—— 用分钟线回溯每只梯队票的首封时间与尾盘封板状态。

判据：
    涨停价 = quote.price_ceiling
    首封时间 = 分时中第一次 price ≥ 涨停价×0.999 的时刻
    尾盘封板 = 14:45 后最后一个分时价仍 ≥ 涨停价×0.999（否则记「炸板」）
产出：写回 emotion_pool JSON 的 core[].seal_time / seal_eod，供日报梯队卡展示。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import westock_cli as W  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    import datetime
    day = None
    try:
        h = json.loads((ROOT / "output" / "ledger" / "history.json").read_text(encoding="utf-8"))
        day = (h.get("days") or [{}])[-1].get("date")
    except Exception:
        pass
    day = day or datetime.date.today().isoformat()

    ep = ROOT / "output" / "daily" / day / "data" / "emotion_pool.json"
    if not ep.exists():
        print(f"情绪池文件不存在：{ep}")
        return 1
    emo = json.loads(ep.read_text(encoding="utf-8"))
    core = emo.get("core", [])
    if not core:
        print("梯队为空")
        return 0

    codes = [p["code"] for p in core]
    q = W.quote(codes)

    print(f"=== 封板时间分析（{day}，梯队 {len(core)} 只）===")
    for p in core:
        code, name = p["code"], p["name"]
        ceil = W.num(q.get(code, {}).get("price_ceiling"))
        if not ceil:
            p["seal_time"], p["seal_eod"] = None, None
            print(f"  {name:<8} 涨停价数据缺失")
            continue
        try:
            rows = W.parse_table(W._run(["westock", "minute", code], timeout=60))
        except Exception as e:
            p["seal_time"], p["seal_eod"] = None, None
            print(f"  {name:<8} 分钟线失败：{str(e)[:40]}")
            continue

        seal_time = None
        for r in rows:
            px = W.num(r.get("price"))
            t = r.get("time", "")
            if px and px >= ceil * 0.999 and t.isdigit():
                seal_time = f"{t[:2]}:{t[2:]}"
                break
        late = [W.num(r.get("price")) for r in rows
                if r.get("time", "").isdigit() and int(r.get("time")) >= 1445
                and W.num(r.get("price"))]
        seal_eod = bool(late and late[-1] and late[-1] >= ceil * 0.999)

        p["seal_time"] = seal_time
        p["seal_eod"] = seal_eod
        tag = "✅ 尾盘封死" if seal_eod else ("⚠️ 炸板" if seal_time else "—")
        print(f"  {name:<8} 涨停价 {ceil:.2f} ｜ 首封 {seal_time or '未封'} ｜ {tag}")

    ep.write_text(json.dumps(emo, ensure_ascii=False, indent=1), encoding="utf-8")
    sealed = sum(1 for p in core if p.get("seal_eod"))
    print(f"\n✅ 已写回 {ep.name}（尾盘封死 {sealed}/{len(core)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
