#!/usr/bin/env python3
"""
拉取K线数据并画图,输出PNG。

用法:
  python3 chart.py BTC --interval 4h --bars 48 --out chart.png
"""
import argparse
import sys

import mplfinance as mpf
import pandas as pd
import requests

KLINES_URL = "https://api.binance.com/api/v3/klines"
TIMEOUT = 10


def fetch_klines(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    pair = f"{symbol.upper()}USDT"
    r = requests.get(KLINES_URL, params={"symbol": pair, "interval": interval, "limit": limit}, timeout=TIMEOUT)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise ValueError(f"没有拿到 {pair} 的K线数据,检查交易对是否存在")

    df = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore"
    ])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("open_time")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df[["open", "high", "low", "close", "volume"]]


def draw_chart(symbol: str, interval: str, bars: int, out_path: str):
    df = fetch_klines(symbol, interval, bars)
    mpf.plot(
        df,
        type="candle",
        style="binance",
        volume=True,
        title=f"\n{symbol.upper()}/USDT  {interval}",
        savefig=dict(fname=out_path, dpi=150, bbox_inches="tight"),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", help="如 BTC, ETH (不带USDT后缀)")
    ap.add_argument("--interval", default="4h", help="1m/5m/15m/1h/4h/1d 等,与Binance klines接口一致")
    ap.add_argument("--bars", type=int, default=48)
    ap.add_argument("--out", default="chart.png")
    args = ap.parse_args()

    try:
        draw_chart(args.symbol, args.interval, args.bars, args.out)
        print(f"已生成 {args.out}")
    except Exception as e:
        print(f"[错误] 生成K线图失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
