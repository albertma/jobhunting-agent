#!/usr/bin/env python3
"""JobHunting CLI

用法:
  python main.py run          # 抓取 + 评分 + 入库
  python main.py run --push   # 抓取 + 推送飞书
  python main.py list         # 查看最近入库职位
  python main.py applied <job_id>  # 标记已投递
  python main.py config       # 打印当前配置

环境变量 / .env:
  FEISHU_APP_ID       飞书应用 App ID
  FEISHU_APP_SECRET   飞书应用 Secret
  FEISHU_CHAT_ID      飞书推送目标 chat_id
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# 把 src 加入 path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from jobhunting.config import load as load_config
from jobhunting.db import get_applied, mark_applied, recent_jobs
from jobhunting.pipeline import push_to_feishu, run


def cmd_run(push: bool) -> None:
    config = load_config()
    jobs = run(config)
    if not jobs:
        print("没有匹配职位")
        return

    # 打印报告
    applied = get_applied()
    print(f"\n{'='*60}")
    print(f"推荐职位（{len(jobs)} 个） | {datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'='*60}")
    for i, job in enumerate(jobs[:20], 1):
        applied_tag = " ✅已投递" if job.id in applied else ""
        print(f"\n{i}. {job.title} @ {job.company}{applied_tag}")
        print(f"   {job.score_label}（{job.score:.0f}分）| {job.location or '🌍 Remote'}")
        if job.salary:
            print(f"   💰 {job.salary}")
        print(f"   🔗 {job.url}")

    if push:
        push_to_feishu(jobs, config)


def cmd_list(limit: int = 20) -> None:
    jobs = recent_jobs(limit=limit)
    applied = get_applied()
    print(f"\n最近入库职位（{len(jobs)} 条）")
    for job in jobs:
        tag = "✅" if job.id in applied else "  "
        print(f"{tag} [{job.score:.0f}分] {job.title} @ {job.company} ({job.source})")
    if applied:
        print(f"\n已投递: {len(applied)} 个")


def cmd_config() -> None:
    config = load_config()
    print("=== 当前配置 ===")
    print(f"来源: {[n for n, s in config.sources.items() if s.enabled]}")
    print(f"核心关键词: {config.scoring.core_keywords}")
    print(f"飞书推送: {'启用' if config.notify.enabled and config.notify.feishu_app_id else '未启用'}")
    print(f"去重窗口: {config.dedup_days} 天")


def cmd_applied(job_id: str) -> None:
    mark_applied(job_id)
    print(f"已标记: {job_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote Job Hunting CLI")
    sub = parser.add_subparsers(dest="cmd")

    r = sub.add_parser("run", help="抓取职位")
    r.add_argument("--push", action="store_true", help="推送飞书")
    r.add_argument("--dry", action="store_true", help="仅抓取不入库")

    sub.add_parser("list", help="查看最近职位").add_argument(
        "-n", "--limit", type=int, default=20
    )

    applied_p = sub.add_parser("applied", help="标记已投递")
    applied_p.add_argument("job_id", help="Job ID（如 remotive:12345）")

    sub.add_parser("config", help="打印配置")

    args = parser.parse_args()

    if args.cmd == "run":
        cmd_run(push=args.push)
    elif args.cmd == "list":
        cmd_list(limit=args.limit)
    elif args.cmd == "applied":
        cmd_applied(args.job_id)
    elif args.cmd == "config":
        cmd_config()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
