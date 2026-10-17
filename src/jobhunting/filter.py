"""关键词过滤 + 评分"""
from __future__ import annotations

import re
from .models import Job


def apply_filters(
    jobs: list[Job],
    exclude_keywords: list[str],
) -> list[Job]:
    """排除包含禁用关键词的职位"""
    patterns = [re.compile(kw, re.IGNORECASE) for kw in exclude_keywords]

    def is_excluded(job: Job) -> bool:
        text = f"{job.title} {job.description} {job.company}".lower()
        return any(p.search(text) for p in patterns)

    return [j for j in jobs if not is_excluded(j)]


def score_jobs(
    jobs: list[Job],
    core_keywords: list[str],
    secondary_keywords: list[str],
    core_weight: float = 15.0,
    secondary_weight: float = 5.0,
    salary_bonus: float = 10.0,
    max_score: float = 100.0,
) -> list[Job]:
    """对职位进行匹配度评分"""

    def _score(job: Job) -> tuple[float, dict]:
        text = f"{job.title} {job.description}".lower()
        breakdown: dict[str, float] = {}

        # 核心词匹配
        core_hits = sum(1 for kw in core_keywords if kw.lower() in text)
        breakdown["core_hits"] = core_hits
        core_score = core_hits * core_weight

        # 标题专属加成（列表页无描述时，标题命中更重要）
        title_text = job.title.lower()
        title_hits = sum(1 for kw in core_keywords if kw.lower() in title_text)
        breakdown["title_hits"] = title_hits
        title_bonus = title_hits * 10.0

        # 次要词匹配
        sec_hits = sum(1 for kw in secondary_keywords if kw.lower() in text)
        breakdown["secondary_hits"] = sec_hits
        sec_score = sec_hits * secondary_weight

        # 薪资透明加成
        has_salary = 1.0 if job.salary and job.salary not in ("", "0", "null") else 0.0
        breakdown["salary_bonus"] = has_salary * salary_bonus

        total = min(core_score + title_bonus + sec_score + breakdown["salary_bonus"], max_score)
        return total, breakdown

    scored = []
    for job in jobs:
        s, bd = _score(job)
        job.score = s
        job.score_breakdown = bd
        scored.append(job)

    scored.sort(key=lambda j: j.score, reverse=True)
    return scored
