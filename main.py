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
from jobhunting.db import (
    all_jobs,
    due_followups,
    get_applied,
    mark_applied,
    mark_replied,
    recent_jobs,
    top_jobs,
    update_scores,
)
from jobhunting.draft import generate_draft
from jobhunting.filter import score_with_config
from jobhunting import pipeline as pl
from jobhunting.notify import notify_text
from jobhunting.pipeline import push_to_feishu, run


def cmd_run(push: bool) -> None:
    config = load_config()
    jobs = run(config)

    # 全部数据源都失败时告警（无人值守时能及时发现异常）
    status = pl.run_status
    enabled = [n for n, s in config.sources.items() if s.enabled]
    all_failed = enabled and all(not status.get(n, {}).get("ok") for n in enabled)
    if all_failed:
        nc = config.notify
        errors = "\n".join(f"{n}: {status[n]['error'][:80]}" for n in enabled if n in status)
        print(f"\n⚠️ 全部数据源抓取失败！\n{errors}")
        if push and nc.enabled:
            notify_text(
                title="⚠️ JobHunting 全部数据源失败",
                body=f"{datetime.now():%Y-%m-%d %H:%M}\n{errors}",
                feishu_app_id=nc.feishu_app_id,
                feishu_app_secret=nc.feishu_app_secret,
                feishu_chat_id=nc.feishu_chat_id,
                telegram_token=nc.telegram_bot_token,
                telegram_chat_id=nc.telegram_chat_id,
            )
        return

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
        # 投递跟进提醒（独立推送）
        push_followup_reminders(config)


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
    print(f"已标记投递: {job_id}")
    print("收到回复后用 replied 命令登记，跟进提醒会自动停止")


def cmd_replied(job_id: str) -> None:
    mark_replied(job_id)
    print(f"已登记回复: {job_id}（不再提醒跟进）")


def cmd_followups(push: bool) -> None:
    config = load_config()
    due = due_followups(days=config.followup_days)
    if not due:
        print(f"暂无待跟进的投递（超过 {config.followup_days} 天无回复的）")
        return
    print(f"待跟进投递（{len(due)} 个）：")
    for j in due:
        d = j["applied_at"][:10] if j["applied_at"] else "?"
        print(f"  [{d} 投递] {j['title']} @ {j['company']}")
        print(f"    {j['url']}")
        print(f"    ID: {j['id']}")
    if push:
        from jobhunting.pipeline import push_followup_reminders
        n = push_followup_reminders(config)
        print(f"已推送飞书（{n} 条）" if n else "⚠️ 推送失败或未启用，下次运行重试")


def cmd_rescore() -> None:
    """用当前 config.yaml 重算全库评分（调参后使用）"""
    config = load_config()
    jobs = all_jobs()
    if not jobs:
        print("库为空")
        return
    scored = score_with_config(jobs, config.scoring)
    n = update_scores(scored)
    print(f"已重算 {n} 条。当前 Top 10：")
    applied = get_applied()
    for i, j in enumerate(scored[:10], 1):
        tag = " ✅" if j.id in applied else ""
        print(f"{i:2d}. [{j.score:5.0f}分] {j.title} @ {j.company}{tag}")


def cmd_push(days: int) -> None:
    """从库中取最近 N 天最高分职位推送飞书（不抓取）"""
    config = load_config()
    nc = config.notify
    jobs = top_jobs(days=days, limit=nc.daily_max)
    if not jobs:
        print("最近没有可推送的职位")
        return
    print(f"将推送 {len(jobs)} 条：")
    for j in jobs:
        print(f"  [{j.score:5.0f}分] {j.title} @ {j.company}")
    push_to_feishu(jobs, config)


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote Job Hunting CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("init", help="交互式初始化（生成 profile.yaml + config.yaml）")
    sub.add_parser("agent", help="交互式 Agent 对话界面（自然语言选职位、聊 JD、生成材料）")

    r = sub.add_parser("run", help="抓取职位")
    r.add_argument("--push", action="store_true", help="推送飞书")
    r.add_argument("--dry", action="store_true", help="仅抓取不入库")

    sub.add_parser("list", help="查看最近职位").add_argument(
        "-n", "--limit", type=int, default=20
    )

    applied_p = sub.add_parser("applied", help="标记已投递（开始计时，N 天无回复提醒跟进）")
    applied_p.add_argument("job_id", help="Job ID（如 remotive:12345）")

    replied_p = sub.add_parser("replied", help="登记已收到回复（停止跟进提醒）")
    replied_p.add_argument("job_id", help="Job ID")

    chat_p = sub.add_parser("chat", help="LLM 对话：询问职位 ")
    chat_p.add_argument("--fit", action="store_true", help="LLM 深度匹配分析（job_fit_analysis）")
    chat_p.add_argument("--draft", action="store_true", help="LLM 生成定制 Cover Letter（完整自然语言版）")
    chat_p.add_argument("job_id", nargs="?", help="Job ID")
    chat_p.add_argument("question", nargs="?", help="直接提问（不加 --fit/--draft 时生效）")

    sub.add_parser("rescore", help="重算全库评分（调参后使用）")

    push_p = sub.add_parser("push", help="推送库内最高分职位到飞书（不抓取）")
    push_p.add_argument("-d", "--days", type=int, default=7, help="取最近 N 天")

    draft_p = sub.add_parser("draft", help="生成定制申请包（cover letter + 简历建议 + 面试题）")
    draft_p.add_argument("job_id", help="Job ID（main.py list 查看，如 remoteok:xxx）")

    sub.add_parser("config", help="打印配置")

    args = parser.parse_args()

    if args.cmd == "agent":
        from jobhunting.agent import cmd_agent
        cmd_agent()
    elif args.cmd == "init":
        from jobhunting.wizard import run_wizard
        run_wizard()
    elif args.cmd == "run":
        cmd_run(push=args.push)
    elif args.cmd == "list":
        cmd_list(limit=args.limit)
    elif args.cmd == "applied":
        cmd_applied(args.job_id)
    elif args.cmd == "replied":
        cmd_replied(args.job_id)
    elif args.cmd == "chat":
        from jobhunting.chat import cmd_chat
        cmd_chat(
            job_id=args.job_id,
            question=args.question,
            fit_only=args.fit,
            draft_only=args.draft,
            profile_path=None,
        )
    elif args.cmd == "followups":
        cmd_followups(push=args.push)
    elif args.cmd == "rescore":
        cmd_rescore()
    elif args.cmd == "push":
        cmd_push(days=args.days)
    elif args.cmd == "draft":
        out = generate_draft(args.job_id)
        print(f"\n✅ 申请包已生成: {out}")
        print("   先填 profile.yaml 再生成，效果更好")
    elif args.cmd == "config":
        cmd_config()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
