#!/usr/bin/env python3
"""
根据热度数据生成发帖文案(模板拼接,不调用LLM,稳定省token)。

用法:
  python3 draft.py hot_coins.json --rank 0 --out draft.txt
"""
import argparse
import json
import sys


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


def trend_word(pct):
    """根据涨跌幅正负,返回"涨幅"或"跌幅" """
    if pct is None:
        return "振幅"
    return "涨幅" if pct >= 0 else "跌幅"


def bias_label(pct):
    """
    红涨绿跌配色(国内习惯,跟国际/币圈默认的"绿涨红跌"相反):
    看多 = 红色上涨图标, 看空 = 绿色下跌图标
    """
    if pct is None:
        return "方向不明", ""
    if pct >= 0:
        return "看多", "🔴⬆️"
    return "看空", "🟢⬇️"


def build_text(coin: dict) -> str:
    symbol = coin["symbol"]
    pct = coin.get("change_pct")
    change = fmt_change(pct)
    volume = fmt_volume(coin.get("quote_volume"))
    bias_text, bias_emoji = bias_label(pct)

    lines = [
        f"${symbol} 全市场热度榜 #1",
        f"24h{trend_word(pct)} {change} ,成交额冲到 {volume}",
        f"{bias_text} {bias_emoji} ｜ 热度分 {coin['hot_score']}/100",
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
