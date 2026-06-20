#!/usr/bin/env python3
"""
整合编排:热度抓取 -> 选币 -> 画K线图 -> 生成文案 -> (可选)发布到Square

用法:
  # 测试模式: 只生成文案+图片到本地,不真实发帖
  python3 run_once.py --rank 0 --dry-run

  # 真实发帖(需要先装好vendor/square-post并设置BINANCE_SQUARE_OPENAPI_KEY)
  python3 run_once.py --rank 0
"""
import argparse
import json
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SQUARE_POST_DIR = os.path.join(PROJECT_ROOT, "vendor", "square-post", "scripts")


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[错误] 命令失败: {' '.join(cmd)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rank", type=int, default=0, help="取热度榜第几名,0=第1名")
    ap.add_argument("--top", type=int, default=10, help="抓取热度榜前N名")
    ap.add_argument("--interval", default="4h", help="K线周期")
    ap.add_argument("--bars", type=int, default=48, help="K线根数")
    ap.add_argument("--dry-run", action="store_true", help="只生成文案和图片,不真实发帖")
    ap.add_argument("--workdir", default=os.path.join(PROJECT_ROOT, "data", "tmp"))
    args = ap.parse_args()

    os.makedirs(args.workdir, exist_ok=True)
    stamp = int(time.time())
    hot_json_path = os.path.join(args.workdir, f"hot_{stamp}.json")
    chart_path = os.path.join(args.workdir, f"chart_{stamp}.png")
    draft_path = os.path.join(args.workdir, f"draft_{stamp}.txt")

    print("== Step A: 抓取热度榜 ==")
    run([sys.executable, os.path.join(SCRIPT_DIR, "hot_coins.py"), "--top", str(args.top), "--out", hot_json_path])

    with open(hot_json_path, encoding="utf-8") as f:
        coins = json.load(f)
    if not coins:
        print("[错误] 热度榜为空,中止本次任务(不发帖)", file=sys.stderr)
        sys.exit(1)
    if args.rank >= len(coins):
        print(f"[错误] --rank {args.rank} 超出范围(榜单只有{len(coins)}个)", file=sys.stderr)
        sys.exit(1)

    symbol = coins[args.rank]["symbol"]
    print(f"== 选中币种: {symbol} (热度分 {coins[args.rank]['hot_score']}) ==")

    print("== Step B: 生成K线图 ==")
    run([sys.executable, os.path.join(SCRIPT_DIR, "chart.py"), symbol,
         "--interval", args.interval, "--bars", str(args.bars), "--out", chart_path])

    print("== Step C: 生成文案 ==")
    draft_text = run([sys.executable, os.path.join(SCRIPT_DIR, "draft.py"), hot_json_path,
                       "--rank", str(args.rank)])
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(draft_text)

    print("\n----- 文案预览 -----")
    print(draft_text)
    print(f"----- K线图: {chart_path} -----\n")

    if args.dry_run:
        print("[DRY RUN] 不会真实发帖。本地产物已保存:")
        print(f"  文案: {draft_path}")
        print(f"  图片: {chart_path}")
        return

    print("== Step D: 发布到 Binance Square ==")
    post_script = os.path.join(SQUARE_POST_DIR, "post-image.mjs")
    if not os.path.exists(post_script):
        print(f"[错误] 找不到发帖脚本: {post_script}\n请先把 square-post skill 放到 vendor/square-post/", file=sys.stderr)
        sys.exit(1)
    if not os.environ.get("BINANCE_SQUARE_OPENAPI_KEY"):
        print("[错误] 未设置环境变量 BINANCE_SQUARE_OPENAPI_KEY", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        ["node", post_script, "--text", draft_text, "--images", chart_path],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print("[错误] 发帖失败:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
