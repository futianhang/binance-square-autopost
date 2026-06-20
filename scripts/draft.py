#!/usr/bin/env python3
"""
根据热度数据生成发帖文案(模板拼接,不调用LLM,稳定省token)。

用法:
  python3 draft.py hot_coins.json --rank 0 --out draft.txt
  (--rank 0 表示取热度榜第1名)
"""
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta

CN_TZ = timezone(timedelta(hours=8))

TOPIC_TAGS = "#市场热点 #加密货币"


def fmt_change(pct):
    if pct is None:
        return "N/A"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def fmt_volume(qv):
    if qv is None:
        return "N/A"
    if qv >= 1e8:
        return f"{qv/1e8:.2f}亿U"
    return f"{qv/1e4:.1f}万U"


def build_text(coin: dict) -> str:
    symbol = coin["symbol"]
    now = datetime.now(CN_TZ).strftime("%m-%d %H:%M")
    change = fmt_change(coin.get("change_pct"))
    volume = fmt_volume(coin.get("quote_volume"))
    futures_link = f"https://www.binance.com/zh-CN/futures/{symbol}USDT"

    lines = [
        f"${symbol} 热度观察 ({now})",
        "",
        f"24h涨跌: {change}   24h成交额: {volume}",
        f"热度综合分: {coin['hot_score']}  (命中{coin['signals_hit']}/3个热度信号)",
        "",
        f"行情详情: {futures_link}",
        "",
        TOPIC_TAGS,
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hot_coins_json", help="hot_coins.py 输出的json文件路径")
    ap.add_argument("--rank", type=int, default=0, help="取榜单第几名,0=第1名")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    with open(args.hot_coins_json, encoding="utf-8") as f:
        coins = json.load(f)

    if not coins:
        print("[错误] 热度列表是空的,没有币种可以生成文案", file=sys.stderr)
        sys.exit(1)
    if args.rank >= len(coins):
        print(f"[错误] --rank {args.rank} 超出范围,榜单只有 {len(coins)} 个币种", file=sys.stderr)
        sys.exit(1)

    text = build_text(coins[args.rank])

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已写入 {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
