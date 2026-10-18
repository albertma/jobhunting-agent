"""职位搜索主 Pipeline"""
from __future__ import annotations

import traceback
from datetime import datetime

from .config import AppConfig, load as load_config
from .db import (
    due_followups,
    log_run,
    mark_followup_sent,
    prune_jobs,
    prune_run_log,
    save_jobs,
    seen_jobs,
)
from .filter import apply_filters, score_with_config
from .log import setup_logging
from .models import Job
from .notify import feishu_notify, notify_text, telegram_send_text
from .sources import get_source

logger = setup_logging()

# 最近一次 run 的状态（供 CLI 判断是否需要告警）
run_status: dict[str, dict] = {}


def run(config: AppConfig | None = None) -> list[Job]:
    """执行一次完整抓取流程，返回推荐职位列表"""
    global run_status
    run_status = {}
    if config is None:
        config = load_config()

    seen = seen_jobs(days=config.dedup_days)
    all_jobs: list[Job] = []

    logger.info(f"[Pipeline] 开始抓取 | {datetime.now():%H:%M:%S}")

    for name, src_cfg in config.sources.items():
        if not src_cfg.enabled:
            continue
        logger.info(f"[Pipeline] 来源: {name}")
        source = get_source(name, src_cfg.__dict__)
        if not source:
            logger.warning(f"[Pipeline] 未知来源: {name}")
            continue

        try:
            raw_jobs = source.fetch()
        except Exception as e:
            logger.error(f"[Pipeline] {name} fetch 失败: {e}")
            log_run(name, found=0, new=0, skipped=0, error=str(e))
            run_status[name] = {"ok": False, "error": str(e), "new": 0}
            continue
        run_status[name] = {"ok": True, "found": len(raw_jobs)}

        # 标准化
        normalized = []
        for raw in raw_jobs:
            try:
                n = source.normalize(raw)
                job = Job(
                    id=n["id"],
                    source=source.name,
                    title=n["title"],
                    company=n["company"],
                    url=n["url"],
                    description=n["description"],
                    tags=n.get("tags", []),
                    location=n.get("location", "Remote"),
                    salary=n.get("salary", ""),
                    job_type=n.get("job_type", ""),
                    posted_at=n.get("posted_at", ""),
                )
                # 去重
                if job.id not in seen:
                    normalized.append(job)
            except Exception:
                continue

        logger.info(f"  → {name}: 获取 {len(raw_jobs)} 条，新 {len(normalized)} 条")
        all_jobs.extend(normalized)
        log_run(name, found=len(raw_jobs), new=len(normalized), skipped=len(raw_jobs) - len(normalized))

    # 过滤
    exclude_kw: list[str] = []
    for src_cfg in config.sources.values():
        exclude_kw.extend(src_cfg.exclude_keywords)
    all_jobs = apply_filters(all_jobs, exclude_kw)
    logger.info(f"[Pipeline] 过滤后: {len(all_jobs)} 条")

    # 评分
    all_jobs = score_with_config(all_jobs, config.scoring)
    if all_jobs:
        logger.info(f"[Pipeline] 评分完成，最高分: {all_jobs[0].score:.1f}")

    # 只保留高于门槛的
    recommended = [j for j in all_jobs if j.score >= config.scoring.min_score]
    logger.info(f"[Pipeline] 入围（≥{config.scoring.min_score}分）: {len(recommended)} 条")

    # 入库
    if all_jobs:
        saved, skipped = save_jobs(all_jobs)
        logger.info(f"[Pipeline] 入库: {saved} 新, {skipped} 重复")

    # 数据保鲜：清理过期数据（已投递的永久保留）
    pruned = prune_jobs(days=config.retention_days)
    if pruned:
        logger.info(f"[Pipeline] 数据清理: 删除 {pruned} 条超过 {config.retention_days} 天的旧职位")
    log_pruned = prune_run_log(keep=500)
    if log_pruned:
        logger.info(f"[Pipeline] 运行日志清理: 删除 {log_pruned} 条")

    return recommended


def push_followup_reminders(config: AppConfig) -> int:
    """检查投递超时未回复的职位，推送跟进提醒；返回成功推送的条数"""
    due = due_followups(days=config.followup_days)
    if not due:
        return 0

    nc = config.notify
    lines = []
    for j in due[:10]:
        days = ""
        if j["applied_at"]:
            try:
                applied = datetime.fromisoformat(j["applied_at"])
                days = f"（{(datetime.now() - applied).days} 天前投递）"
            except ValueError:
                pass
        lines.append(f"• {j['title']} @ {j['company']} {days}\n  {j['url']}")

    body = (
        f"以下 {len(due)} 个职位投递已超过 {config.followup_days} 天无回复，\n"
        f"建议发一封简短跟进邮件：\n\n" + "\n".join(lines)
        + "\n\nℹ️ 收到回复后用 main.py replied <job_id> 登记，不再提醒"
    )

    logger.info(f"[Followup] {len(due)} 个投递待跟进")
    if nc.enabled:
        ok = notify_text(
            title=f"📬 投递跟进提醒（{len(due)} 个）",
            body=body,
            feishu_app_id=nc.feishu_app_id,
            feishu_app_secret=nc.feishu_app_secret,
            feishu_chat_id=nc.feishu_chat_id,
            telegram_token=nc.telegram_bot_token,
            telegram_chat_id=nc.telegram_chat_id,
        )
        if ok:
            mark_followup_sent([j["id"] for j in due])
            return len(due)
        logger.warning("[Followup] 推送失败，下次运行重试")
    return 0


def push_to_feishu(jobs: list[Job], config: AppConfig) -> None:
    """推送推荐职位（飞书富文本 / Telegram Markdown，按配置自动选择）"""
    nc = config.notify
    if not nc.enabled:
        logger.info("[Pipeline] 推送未启用，跳过")
        return

    top_jobs = jobs[: nc.daily_max]
    title = f"🤖 Remote 职位推送 {datetime.now():%m/%d}"

    has_feishu = bool(nc.feishu_app_id and nc.feishu_app_secret and nc.feishu_chat_id)
    has_telegram = bool(nc.telegram_bot_token and nc.telegram_chat_id)
    if not has_feishu and not has_telegram:
        logger.info("[Pipeline] 未配置任何通知通道（飞书/Telegram），跳过推送")
        return

    try:
        sent = False
        if has_feishu:
            sent |= feishu_notify(
                title=title,
                jobs=top_jobs,
                app_id=nc.feishu_app_id,
                app_secret=nc.feishu_app_secret,
                chat_id=nc.feishu_chat_id,
            )
        if has_telegram:
            sent |= telegram_send_text(
                title=title,
                body=_jobs_as_markdown(top_jobs),
                bot_token=nc.telegram_bot_token,
                chat_id=nc.telegram_chat_id,
            )
        if not sent:
            logger.warning("[Pipeline] 全部通道推送失败")
    except Exception as e:
        logger.error(f"[Pipeline] 推送异常: {e}")
        try:
            notify_text(
                title="JobHunting 推送失败",
                body=str(e),
                feishu_app_id=nc.feishu_app_id,
                feishu_app_secret=nc.feishu_app_secret,
                feishu_chat_id=nc.feishu_chat_id,
                telegram_token=nc.telegram_bot_token,
                telegram_chat_id=nc.telegram_chat_id,
            )
        except Exception as e2:
            logger.error(f"[Pipeline] 告警消息也发送失败: {e2}")


def _jobs_as_markdown(jobs: list[Job]) -> str:
    """职位列表 → Telegram Markdown 文本"""
    lines: list[str] = []
    for j in jobs:
        salary = f" 💰{j.salary}" if j.salary else ""
        lines.append(
            f"*{j.title}* @ {j.company}\n"
            f"{j.score_label}({j.score:.0f}分) | {j.location or '🌍 Remote'}{salary}\n"
            f"{j.url}"
        )
    return "\n\n".join(lines)
