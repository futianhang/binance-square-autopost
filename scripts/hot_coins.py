#!/usr/bin/env python3
"""
热度抓取与打分。
信号源:
  1. 社交热度榜 (Social Hype Leaderboard) -- 排名榜,指数衰减打分
  2. 趋势榜 (Trending, rankType=10)        -- 排名榜,指数衰减打分
  3. 24h量价 (涨跌幅 + 成交额)              -- 连续值,百分位打分

综合分: 0.4*社交热度 + 0.3*趋势榜 + 0.3*量价信号
过滤: 24h成交额 < MIN_QUOTE_VOLUME 直接剔除
降级机制: 如果社交热度榜+趋势榜都拿不到数据,自动降级成只用量价信号打分

用法:
  python3 hot_coins.py [--top N] [--out hot_coins.json]
"""
import argparse
import json
import sys

import requests

WEB3_RANK_URL = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/rank/list/ai"
WEB3_HYPE_URL = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/social/hype/rank/leaderboard/ai"
SPOT_24HR_URL = "https://api.binance.com/api/v3/ticker/24hr"

MIN_QUOTE_VOLUME = 5_000_000  # 24h成交额门槛(USDT),低于这个直接剔除
DECAY = 0.85                  # 排名榜指数衰减系数
HEADERS = {"Content-Type": "application/json", "Accept-Encoding": "identity"}
TIMEOUT = 10


def rank_decay_score(rank: int) -> float:
    """排名榜归一化: 第1名100分,之后按0.85^(rank-1)衰减"""
    return 100.0 * (DECAY ** (rank - 1))


def percentile_rank(values: list[float], target: float) -> float:
    """target 在 values 里的百分位(0~100)"""
    if not values:
        return 0.0
    below = sum(1 for v in values if v <= target)
    return 100.0 * below / len(values)


def fetch_social_hype(chain_id="56", limit=20) -> dict[str, float]:
    """返回 {symbol: score}"""
    try:
        r = requests.get(WEB3_HYPE_URL, params={"chainId": chain_id, "sentiment": "All", "socialLanguage": "ALL"},
                          headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        items = (data.get("data") or {}).get("list") or data.get("data") or []
        scores = {}
        for i, item in enumerate(items[:limit]):
            symbol = (item.get("symbol") or item.get("tokenSymbol") or "").upper()
            if symbol:
                scores[symbol] = rank_decay_score(i + 1)
        return scores
    except Exception as e:
        print(f"[警告] 社交热度榜获取失败: {e}", file=sys.stderr)
        return {}


def fetch_trending(chain_id="56", rank_type=10, limit=20) -> dict[str, float]:
    try:
        r = requests.post(WEB3_RANK_URL, json={"chainId": chain_id, "rankType": rank_type, "limit": limit},
                           headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        items = (data.get("data") or {}).get("list") or data.get("data") or []
        scores = {}
        for i, item in enumerate(items[:limit]):
            symbol = (item.get("symbol") or item.get("tokenSymbol") or "").upper()
            if symbol:
                scores[symbol] = rank_decay_score(i + 1)
        return scores
    except Exception as e:
        print(f"[警告] 趋势榜获取失败: {e}", file=sys.stderr)
        return {}


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
    hype = fetch_social_hype()
    trend = fetch_trending()
    pv = fetch_price_volume_signal()

    print(f"[诊断] 社交热度榜命中 {len(hype)} 个币种,趋势榜命中 {len(trend)} 个币种,"
          f"24h量价命中 {len(pv)} 个币种(过滤成交额<{MIN_QUOTE_VOLUME}后)", file=sys.stderr)

    degraded = (len(hype) == 0 and len(trend) == 0)
    min_hits = 1 if degraded else 2
    if degraded:
        print("[诊断] 社交热度榜+趋势榜均为空,降级为纯量价信号打分", file=sys.stderr)

    all_symbols = set(hype) | set(trend) | set(pv)
    candidates = []
    for sym in all_symbols:
        hits = sum([sym in hype, sym in trend, sym in pv])
        if hits < min_hits:
            continue
        hype_s = hype.get(sym, 0.0)
        trend_s = trend.get(sym, 0.0)
        pv_s = pv.get(sym, {}).get("score", 0.0)
        total = 0.4 * hype_s + 0.3 * trend_s + 0.3 * pv_s
        candidates.append({
            "symbol": sym,
            "hot_score": round(total, 2),
            "signals_hit": hits,
            "social_hype_score": round(hype_s, 2),
            "trending_score": round(trend_s, 2),
            "price_volume_score": round(pv_s, 2),
            "change_pct": pv.get(sym, {}).get("change_pct"),
            "quote_volume": pv.get(sym, {}).get("quote_volume"),
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
        print("[警告] 量价信号也没有结果,可能是api.binance.com被限流/不可达", file=sys.stderr)

    output = json.dumps(hot_list, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"已写入 {args.out} ({len(hot_list)} 个币种)", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
