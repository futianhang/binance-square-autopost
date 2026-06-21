#!/usr/bin/env python3
"""
根据行情数据生成发帖文案(纯文本模板拼接,不调用LLM,稳定省token)。

用法:
  python3 draft.py market.json --out draft.txt
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8))


def fmt_price(price: float) -> str:
    """
    自适应精度:大币种(BTC/ETH等)用千分位+2位小数,
    小价格的meme币(PEPE/SHIB这种 $0.00001234)按数量级加小数位,避免显示成 $0.00
    """
    if price >= 1:
        return f"${price:,.2f}"
    if price >= 0.01:
        return f"${price:.4f}"
    if price >= 0.0001:
        return f"${price:.6f}"
    return f"${price:.8f}"


def fmt_change(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def fmt_volume(qv: float) -> str:
    """统一用 $X.XB / $X.XM / $X.XK 这种简写,贴近示例格式"""
    if qv >= 1e9:
        return f"${qv / 1e9:.1f}B"
    if qv >= 1e6:
        return f"${qv / 1e6:.1f}M"
    return f"${qv / 1e3:.1f}K"


def sentiment(pct: float) -> str:
    """
    按24h涨跌幅划分5档情绪标签,阈值是按经验拍的,
    嫌太敏感/太迟钝可以直接改这几个数字。
    """
    if pct >= 5:
        return "🔥 强势看涨"
    if pct >= 1:
        return "📈 温和看涨"
    if pct > -1:
        return "😐 横盘整理"
    if pct > -5:
        return "📉 温和看跌"
    return "🥶 恐慌下跌"


def coin_block(coin: dict) -> str:
    pct = coin["change_pct"]
    return "\n".join([
        f"${coin['symbol']}",
        f"💰 最新价：{fmt_price(coin['last_price'])}",
        f"📈 24h涨跌幅：{fmt_change(pct)}",
        f"📊 24h成交额：{fmt_volume(coin['quote_volume'])}",
        f"😊 市场情绪：{sentiment(pct)}",
    ])


def build_text(data: dict) -> str:
    now_bj = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M")
    lines = [f"行情快报（{now_bj} 北京时间）", ""]

    for coin in data.get("focus", []):
        lines.append(coin_block(coin))
        lines.append("")

    movers = data.get("movers", [])
    if movers:
        lines.append("🔥 市场热点：")
        lines.append("")
        for coin in movers:
            lines.append(coin_block(coin))
            lines.append("")

    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("market_json", help="market_data.py 输出的json文件路径")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    with open(args.market_json, encoding="utf-8") as f:
        data = json.load(f)

    if not data.get("focus") and not data.get("movers"):
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
