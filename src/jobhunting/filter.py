"""关键词过滤 + 评分

评分设计（标题优先，防止长描述堆词刷分）：
  标题核心词命中   title_weight × 命中数（最强信号，不封顶）
  描述核心词命中   core_weight × min(命中数, desc_core_cap)（封顶）
  次要词命中       secondary_weight × min(命中数, secondary_cap)（封顶）
  薪资透明         + salary_bonus
  人才库/中介      + talent_penalty（Lemon.io 等非具体岗位，负分）
  地域适配         地点含 APAC/Worldwide +bonus；限定美/欧时区 penalty（候选人所在地无法入职）
"""
from __future__ import annotations

import re

from .config import ScoringConfig
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
    core_weight: float = 10.0,
    secondary_weight: float = 5.0,
    salary_bonus: float = 10.0,
    max_score: float = 100.0,
    title_weight: float = 20.0,
    desc_core_cap: int = 3,
    secondary_cap: int = 4,
    talent_penalty: float = -30.0,
    talent_companies: list[str] | None = None,
    location_bonus: float = 10.0,
    location_penalty: float = -50.0,
    location_eligible: list[str] | None = None,
    location_restricted: list[str] | None = None,
) -> list[Job]:
    """对职位进行匹配度评分"""
    talent_companies = [c.lower() for c in (talent_companies or [])]
    eligible_pats = [re.compile(rf"\b{re.escape(k.lower())}\b") for k in (location_eligible or [])]
    restricted_pats = [re.compile(rf"\b{re.escape(k.lower())}\b") for k in (location_restricted or [])]
    # 各语言“远程”同义词（子串匹配），如西语 Remoto
    remote_synonyms = ("remote", "remoto", "trabajo remoto", "anywhere", "distributed")

    def _loc_adjust(job: Job) -> tuple[float, str]:
        """地域适配：
        1. 含 APAC/Worldwide 等可入职地区 → 加分
        2. 限定美/欧时区 → 重罚
        3. 含“远程”同义词 → 中性
        4. 具体城市坐班（如 Redwood City）→ 视同不可入职重罚
        """
        loc = (job.location or "").lower()
        if not loc:
            return 0.0, "unknown"
        if any(p.search(loc) for p in eligible_pats):
            return location_bonus, "eligible"
        if any(p.search(loc) for p in restricted_pats):
            return location_penalty, "restricted"
        if any(s in loc for s in remote_synonyms):
            return 0.0, "neutral"
        return location_penalty, "onsite"

    def _score(job: Job) -> tuple[float, dict]:
        # 防御：无标题不参与推荐
        if not job.title.strip():
            return 0.0, {"error": "empty_title"}

        text = f"{job.title} {job.description}".lower()
        breakdown: dict[str, float] = {}

        # ① 标题核心词命中（最强信号，不封顶）
        title_text = job.title.lower()
        title_hits = sum(1 for kw in core_keywords if kw.lower() in title_text)
        breakdown["title_hits"] = title_hits
        title_score = title_hits * title_weight

        # ② 描述核心词命中（封顶，防堆词）
        core_hits_raw = sum(1 for kw in core_keywords if kw.lower() in text)
        core_hits = min(core_hits_raw, desc_core_cap)
        breakdown["core_hits"] = core_hits_raw
        breakdown["core_hits_capped"] = core_hits
        core_score = core_hits * core_weight

        # ③ 次要词命中（封顶）
        sec_hits_raw = sum(1 for kw in secondary_keywords if kw.lower() in text)
        sec_hits = min(sec_hits_raw, secondary_cap)
        breakdown["secondary_hits"] = sec_hits_raw
        sec_score = sec_hits * secondary_weight

        # ④ 薪资透明加成
        has_salary = 1.0 if job.salary and job.salary not in ("", "0", "null") else 0.0
        breakdown["salary_bonus"] = has_salary * salary_bonus

        # ⑤ 人才库/中介惩罚（非具体岗位，先注册进池子）
        company_l = job.company.lower()
        is_talent = any(t in company_l for t in talent_companies)
        breakdown["talent_penalty"] = talent_penalty if is_talent else 0.0

        # ⑥ 地域适配（如上海无法入职 US/EU 时区限定的职位）
        loc_adj, loc_tag = _loc_adjust(job)
        breakdown["location"] = loc_tag
        breakdown["location_adj"] = loc_adj

        total = (
            title_score + core_score + sec_score
            + breakdown["salary_bonus"]
            + breakdown["talent_penalty"]
            + loc_adj
        )
        total = max(0.0, min(total, max_score))
        return total, breakdown

    scored = []
    for job in jobs:
        s, bd = _score(job)
        job.score = s
        job.score_breakdown = bd
        scored.append(job)

    scored.sort(key=lambda j: j.score, reverse=True)
    return scored


def score_with_config(jobs: list[Job], cfg: ScoringConfig) -> list[Job]:
    """统一入口：用 ScoringConfig 评分（pipeline / CLI 共用，避免参数漂移）"""
    return score_jobs(
        jobs,
        core_keywords=cfg.core_keywords,
        secondary_keywords=cfg.secondary_keywords,
        core_weight=cfg.core_weight,
        secondary_weight=cfg.secondary_weight,
        salary_bonus=cfg.salary_bonus,
        max_score=cfg.max_score,
        title_weight=cfg.title_weight,
        desc_core_cap=cfg.desc_core_cap,
        secondary_cap=cfg.secondary_cap,
        talent_penalty=cfg.talent_penalty,
        talent_companies=cfg.talent_companies,
        location_bonus=cfg.location_bonus,
        location_penalty=cfg.location_penalty,
        location_eligible=cfg.location_eligible,
        location_restricted=cfg.location_restricted,
    )
