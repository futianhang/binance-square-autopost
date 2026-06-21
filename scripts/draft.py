#!/usr/bin/env python3
"""
根据行情数据生成发帖文案(纯文本模板拼接,不调用LLM,稳定省token)。

文案格式: 涨跌幅绝对值前5名,每个币种一行,顺序为 名称/涨跌幅/看涨看跌/价格:
  $TNSR 📈+66.9% 🔥 看涨 💰$0.0489
  $STRAX 📈+26.2% 🔥 看涨 💰$0.0117

广场每帖最多只认3个 $cashtag,超过会被API拒绝(220095 Coin pair count exceeds the allowed limit),
所以前3行带$cashtag,第4、5行降级成纯文本(不带$)。

用法:
  python3 draft.py market.json --out draft.txt
"""
import argparse
import json
import sys

# 广场每帖最多只认3个 $cashtag
MAX_CASHTAGS = 3


def fmt_price(price: float) -> str:
    """
    统一价格精度: >=100取整;10~100保留2位小数;低于10保留4位小数。
    额外保险: 低于0.0001的超微价格(比如PEPE这种meme币)延到8位小数,
    避免直接显示成 $0.0000。
    """
    if price >= 100:
        return f"${price:,.0f}"
    if price >= 10:
        return f"${price:,.2f}"
    if price >= 0.0001:
        return f"${price:,.4f}"
    return f"${price:.8f}"


def fmt_change(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def trend_line(coin: dict, use_cashtag: bool) -> str:
    pct = coin["change_pct"]
    prefix = "$" if use_cashtag else ""
    arrow = "📈" if pct >= 0 else "📉"
    mood = "🔥" if pct >= 0 else "🧊"
    label = "看涨" if pct >= 0 else "看跌"
    return f"{prefix}{coin['symbol']} {arrow}{fmt_change(pct)} {mood} {label} 💰{fmt_price(coin['last_price'])}"


def build_text(data: dict) -> str:
    movers = data.get("movers", [])[:5]
    lines = [
        trend_line(coin, use_cashtag=(i < MAX_CASHTAGS))
        for i, coin in enumerate(movers)
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("market_json", help="market_data.py 输出的json文件路径")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    with open(args.market_json, encoding="utf-8") as f:
        data = json.load(f)

    if not data.get("movers"):
        print("[错误] 行情数据是空的,没有内容可以生成文案", file=sys.stderr)
        sys.exit(1)

    text = build_text(data)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已写入 {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
