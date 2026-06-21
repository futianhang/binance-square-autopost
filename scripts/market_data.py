#!/usr/bin/env python3
"""
拉取行情数据 —— 只用Binance官方交易所数据,不做K线、不做热度加权打分。

市场热点: 24h涨跌幅绝对值最大的前N名(剔除稳定币/杠杆代币,且过滤掉成交额太低的噪音币)

数据源: data-api.binance.vision (Binance官方维护的公开市场数据镜像,
        路径/参数/返回格式跟 api.binance.com 完全一致,但不受美国IP地域限制(451))

用法:
  python3 market_data.py [--top 5] [--out market.json]
"""
import argparse
import json
import sys

import requests

SPOT_24HR_URL = "https://data-api.binance.vision/api/v3/ticker/24hr"

# "市场热点"的成交额门槛(USDT),低于这个直接剔除,避免极小盘噪音币靠涨跌幅刷榜
MIN_QUOTE_VOLUME = 5_000_000

# 稳定币涨跌幅没有参考意义,杠杆代币(UP/DOWN/BULL/BEAR)波动是杠杆放大的,也排除
EXCLUDE_SYMBOLS = {
    "USDC", "FDUSD", "TUSD", "USDP", "DAI", "BUSD", "USTC", "USDD", "EUR", "GBP", "AEUR",
}
EXCLUDE_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR", "3L", "3S", "2L", "2S", "5L", "5S")

TIMEOUT = 10


def fetch_all_tickers() -> list[dict]:
    try:
        r = requests.get(SPOT_24HR_URL, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[警告] 24hr ticker获取失败: {e}", file=sys.stderr)
        return []


def parse_row(row: dict) -> dict | None:
    symbol = row.get("symbol", "")
    if not symbol.endswith("USDT"):
        return None
    try:
        return {
            "symbol": symbol[:-4],
            "last_price": float(row["lastPrice"]),
            "change_pct": float(row["priceChangePercent"]),
            "quote_volume": float(row["quoteVolume"]),
        }
    except (KeyError, ValueError):
        return None


def is_excluded(symbol: str) -> bool:
    if symbol in EXCLUDE_SYMBOLS:
        return True
    if symbol.endswith(EXCLUDE_SUFFIXES):
        return True
    return False


def build_market_data(top_n: int = 5) -> dict:
    rows = fetch_all_tickers()
    parsed = [p for p in (parse_row(r) for r in rows) if p is not None]

    candidates = [
        p for p in parsed
        if not is_excluded(p["symbol"])
        and p["quote_volume"] >= MIN_QUOTE_VOLUME
    ]
    candidates.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    movers = candidates[:top_n]

    return {"movers": movers}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5, help="市场热点取前N名(按24h涨跌幅绝对值排序)")
    ap.add_argument("--out", type=str, default=None, help="写入文件路径,不指定则打印到stdout")
    args = ap.parse_args()

    data = build_market_data(top_n=args.top)

    if not data["movers"]:
        print("[警告] 没有抓到任何行情数据,可能是data-api.binance.vision被限流/不可达", file=sys.stderr)

    output = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"已写入 {args.out} (热点 {len(data['movers'])} 个)", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
