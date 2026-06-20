#!/usr/bin/env python3
"""
热度抓取与打分 —— 最终版,只用Binance官方交易所数据。

数据源: 24h涨跌幅 + 成交额 (data-api.binance.vision, 不受地域限制的官方公开数据镜像)
打分: 0.5*成交额百分位 + 0.5*涨跌幅百分位
过滤: 24h成交额 < MIN_QUOTE_VOLUME 直接剔除

用法:
  python3 hot_coins.py [--top N] [--out hot_coins.json]
"""
import argparse
import json
import sys

import requests

# data-api.binance.vision 是Binance官方维护的公开市场数据镜像,
# 路径/参数/返回格式跟 api.binance.com 完全一致,但不受美国IP地域限制(451)。
SPOT_24HR_URL = "https://data-api.binance.vision/api/v3/ticker/24hr"

MIN_QUOTE_VOLUME = 5_000_000  # 24h成交额门槛(USDT),低于这个直接剔除
TIMEOUT = 10


def percentile_rank(values: list[float], target: float) -> float:
    """target 在 values 里的百分位(0~100)"""
    if not values:
        return 0.0
    below = sum(1 for v in values if v <= target)
    return 100.0 * below / len(values)


def fetch_price_volume_signal() -> dict[str, dict]:
    """
    返回 {symbol: {"score": float, "change_pct": float, "quote_volume": float}}
    只看 USDT 现货交易对, 用成交额做流动性门槛。
    """
    try:
        r = requests.get(SPOT_24HR_URL, timeout=TIMEOUT)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        print(f"[警告] 24hr ticker获取失败: {e}", file=sys.stderr)
        return {}

    usdt_rows = []
    for row in rows:
        if not row["symbol"].endswith("USDT"):
            continue
        try:
            qv = float(row["quoteVolume"])
            chg = float(row["priceChangePercent"])
        except (KeyError, ValueError):
            continue
        if qv < MIN_QUOTE_VOLUME:
            continue
        usdt_rows.append((row["symbol"][:-4], qv, chg))

    if not usdt_rows:
        return {}

    qv_list = [r[1] for r in usdt_rows]
    abs_chg_list = [abs(r[2]) for r in usdt_rows]

    result = {}
    for symbol, qv, chg in usdt_rows:
        qv_pct = percentile_rank(qv_list, qv)
        chg_pct = percentile_rank(abs_chg_list, abs(chg))
        score = 0.5 * qv_pct + 0.5 * chg_pct
        result[symbol] = {"score": score, "change_pct": chg, "quote_volume": qv}
    return result


def build_hot_list(top_n: int = 10) -> list[dict]:
    pv = fetch_price_volume_signal()
    print(f"[诊断] 24h量价命中 {len(pv)} 个币种(过滤成交额<{MIN_QUOTE_VOLUME}后)", file=sys.stderr)

    candidates = []
    for sym, data in pv.items():
        candidates.append({
            "symbol": sym,
            "hot_score": round(data["score"], 2),
            "change_pct": data["change_pct"],
            "quote_volume": data["quote_volume"],
        })

    candidates.sort(key=lambda x: x["hot_score"], reverse=True)
    return candidates[:top_n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", type=str, default=None, help="写入文件路径,不指定则打印到stdout")
    args = ap.parse_args()

    hot_list = build_hot_list(top_n=args.top)

    if not hot_list:
        print("[警告] 量价信号也没有结果,可能是data-api.binance.vision被限流/不可达", file=sys.stderr)

    output = json.dumps(hot_list, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"已写入 {args.out} ({len(hot_list)} 个币种)", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
