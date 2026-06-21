#!/usr/bin/env python3
"""
整合编排:抓取行情(涨跌幅绝对值前5名) -> 生成纯文本文案 -> (可选)发布到Square

用法:
  # 测试模式: 只生成文案到本地,不真实发帖
  python3 run_once.py --dry-run

  # 真实发帖(需要先装好vendor/square-post并设置BINANCE_SQUARE_OPENAPI_KEY)
  python3 run_once.py
"""
import argparse
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SQUARE_POST_DIR = os.path.join(PROJECT_ROOT, "vendor", "square-post", "scripts")


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    # 子进程的stderr(诊断信息/警告)无论成功失败都打出来,不要吞掉
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    if result.returncode != 0:
        print(f"[错误] 命令失败: {' '.join(cmd)}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5, help="市场热点取前N名(按24h涨跌幅绝对值排序)")
    ap.add_argument("--dry-run", action="store_true", help="只生成文案,不真实发帖")
    ap.add_argument("--workdir", default=os.path.join(PROJECT_ROOT, "data", "tmp"))
    args = ap.parse_args()

    os.makedirs(args.workdir, exist_ok=True)
    stamp = int(time.time())
    market_json_path = os.path.join(args.workdir, f"market_{stamp}.json")
    draft_path = os.path.join(args.workdir, f"draft_{stamp}.txt")

    print("== Step A: 抓取行情数据(涨跌幅绝对值前5名) ==")
    run([sys.executable, os.path.join(SCRIPT_DIR, "market_data.py"),
         "--top", str(args.top), "--out", market_json_path])

    print("== Step B: 生成文案 ==")
    draft_text = run([sys.executable, os.path.join(SCRIPT_DIR, "draft.py"), market_json_path])
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(draft_text)

    print("\n----- 文案预览 -----")
    print(draft_text)
    print("--------------------\n")

    if args.dry_run:
        print("[DRY RUN] 不会真实发帖。本地产物已保存:")
        print(f"  文案: {draft_path}")
        return

    print("== Step C: 发布到 Binance Square(纯文本) ==")
    post_script = os.path.join(SQUARE_POST_DIR, "post-text.mjs")
    if not os.path.exists(post_script):
        print(f"[错误] 找不到发帖脚本: {post_script}\n请先把 square-post skill 放到 vendor/square-post/", file=sys.stderr)
        sys.exit(1)
    if not os.environ.get("BINANCE_SQUARE_OPENAPI_KEY"):
        print("[错误] 未设置环境变量 BINANCE_SQUARE_OPENAPI_KEY", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        ["node", post_script, "--text", draft_text],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print("[错误] 发帖失败:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
