#!/usr/bin/env python3
"""
根据行情数据生成发帖文案(纯文本模板拼接,不调用LLM,稳定省token)。

文案分两段:
  1. 摘要区(前几行): BTC/ETH合并一行 + 市场热点逐行,这是广场feed流默认展示的部分
     (App里超过5行会被折叠成"查看更多")
  2. 详情区: 每个币种的完整数据(价格/涨跌幅/成交额/市场情绪),折叠在"查看更多"后面

用法:
  python3 draft.py market.json --out draft.txt
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

BEIJING_TZ = timezone(timedelta(hours=8))

# 广场每帖最多只认3个 $cashtag,超过会被API拒绝(220095 Coin pair count exceeds the allowed limit)。
# BTC/ETH固定推送但不带$cashtag,"市场热点"最多前3个占满cashtag上限(摘要区、详情区各出现一次,
# 但都是同一个币种,不会重复计数)。万一movers数量配置超过3,从第4个开始自动降级成纯文本。
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


def fmt_volume(qv: float) -> str:
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


def build_teaser(data: dict) -> list[str]:
    """摘要区(目标控制在5行以内): 标题 + BTC/ETH合并一行 + 热点逐行(最多3个,带$cashtag)"""
    now_bj = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M")
    lines = [f"行情快报（{now_bj} 北京时间）"]

    focus_parts = [
        f"{coin['symbol']} {fmt_price(coin['last_price'])} {fmt_change(coin['change_pct'])}"
        for coin in data.get("focus", [])
    ]
    if focus_parts:
        lines.append(" | ".join(focus_parts))

    movers = data.get("movers", [])[:MAX_CASHTAGS]
    for i, coin in enumerate(movers):
        text = f"${coin['symbol']} {fmt_price(coin['last_price'])} {fmt_change(coin['change_pct'])}"
        lines.append(f"热点：{text}" if i == 0 else text)

    return lines


def coin_block(coin: dict, use_cashtag: bool) -> str:
    """详情区单个币种的完整数据块,只有市场情绪那行带图标"""
    pct = coin["change_pct"]
    prefix = "$" if use_cashtag else ""
    return "\n".join([
        f"{prefix}{coin['symbol']}",
        f"最新价：{fmt_price(coin['last_price'])}",
        f"24h涨跌幅：{fmt_change(pct)}",
        f"24h成交额：{fmt_volume(coin['quote_volume'])}",
        f"市场情绪：{sentiment(pct)}",
    ])


def build_text(data: dict) -> str:
    lines = build_teaser(data)
    lines.append("")

    for coin in data.get("focus", []):
        lines.append(coin_block(coin, use_cashtag=False))
        lines.append("")

    for i, coin in enumerate(data.get("movers", [])):
        lines.append(coin_block(coin, use_cashtag=(i < MAX_CASHTAGS)))
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
