"""职位搜索主 Pipeline"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime

from .config import AppConfig, load as load_config
from .db import log_run, save_jobs, seen_jobs
from .filter import apply_filters, score_jobs
from .models import Job
from .notify import feishu_notify, feishu_notify_text
from .sources import get_source


def run(config: AppConfig | None = None) -> list[Job]:
    """执行一次完整抓取流程，返回推荐职位列表"""
    if config is None:
        config = load_config()

    seen = seen_jobs(days=config.dedup_days)
    all_jobs: list[Job] = []

    print(f"[Pipeline] 开始抓取 | {datetime.now():%H:%M:%S}")

    for name, src_cfg in config.sources.items():
        if not src_cfg.enabled:
            continue
        print(f"[Pipeline] 来源: {name}")
        source = get_source(name, src_cfg.__dict__)
        if not source:
            print(f"[Pipeline] 未知来源: {name}")
            continue

        try:
            raw_jobs = source.fetch()
        except Exception as e:
            print(f"[Pipeline] {name} fetch 失败: {e}")
            log_run(name, found=0, new=0, skipped=0, error=str(e))
            continue

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

        print(f"  → {name}: 获取 {len(raw_jobs)} 条，新 {len(normalized)} 条")
        all_jobs.extend(normalized)
        log_run(name, found=len(raw_jobs), new=len(normalized), skipped=len(raw_jobs) - len(normalized))

    # 过滤
    exclude_kw: list[str] = []
    for src_cfg in config.sources.values():
        exclude_kw.extend(src_cfg.exclude_keywords)
    all_jobs = apply_filters(all_jobs, exclude_kw)
    print(f"[Pipeline] 过滤后: {len(all_jobs)} 条")

    # 评分
    cfg = config.scoring
    all_jobs = score_jobs(
        all_jobs,
        core_keywords=cfg.core_keywords,
        secondary_keywords=cfg.secondary_keywords,
        core_weight=cfg.core_weight,
        secondary_weight=cfg.secondary_weight,
        salary_bonus=cfg.salary_bonus,
        max_score=cfg.max_score,
    )
    print(f"[Pipeline] 评分完成，最高分: {all_jobs[0].score:.1f}" if all_jobs else "")

    # 只保留高于门槛的
    recommended = [j for j in all_jobs if j.score >= cfg.min_score]
    print(f"[Pipeline] 入围（≥{cfg.min_score}分）: {len(recommended)} 条")

    # 入库
    if all_jobs:
        saved, skipped = save_jobs(all_jobs)
        print(f"[Pipeline] 入库: {saved} 新, {skipped} 重复")

    return recommended


def push_to_feishu(jobs: list[Job], config: AppConfig) -> None:
    """推送推荐职位到飞书"""
    nc = config.notify
    if not nc.enabled or not nc.feishu_app_id:
        print("[Pipeline] 飞书推送未启用或未配置，跳过")
        return

    top_jobs = jobs[: nc.daily_max]
    title = f"🤖 Remote 职位推送 {datetime.now():%m/%d}"

    try:
        feishu_notify(
            title=title,
            jobs=top_jobs,
            app_id=nc.feishu_app_id,
            app_secret=nc.feishu_app_secret,
            chat_id=nc.feishu_chat_id,
        )
    except Exception as e:
        print(f"[Pipeline] 飞书推送异常: {e}")
        traceback.print_exc()
        feishu_notify_text(
            title="JobHunting 推送失败",
            body=str(e),
            app_id=nc.feishu_app_id,
            app_secret=nc.feishu_app_secret,
            chat_id=nc.feishu_chat_id,
        )
