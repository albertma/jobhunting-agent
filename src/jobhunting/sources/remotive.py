"""Remotive.com — 免费 Remote Job API

API Docs: https://remotive.com/api/remote-jobs
- 无需认证，每分钟最多 2 次（免费层）
- 支持关键词搜索、分类筛选
- 每次最多返回 100 条（可分页）
"""
from __future__ import annotations

import httpx
from .base import JobSource

REMOTIVE_API = "https://remotive.com/api/remote-jobs"


class RemotiveSource(JobSource):
    """Remotive.com API 数据源"""

    name = "remotive"
    source_type = "api"

    def fetch(self) -> list[dict[str, Any]]:
        keywords = self.config.get("keywords", [])
        max_results = self.config.get("max_results", 100)

        # 主关键词分别搜索，再合并去重
        all_jobs: dict[str, dict] = {}
        for kw in keywords:
            for page in range(3):  # 最多 3 页 × 100 = 300 条/关键词
                params = {
                    "search": kw,
                    "limit": min(max_results, 100),
                    "offset": page * 100,
                }
                try:
                    resp = httpx.get(
                        REMOTIVE_API,
                        params=params,
                        timeout=15.0,
                        follow_redirects=True,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    jobs = data.get("job-registry", data.get("jobs", []))
                    if not jobs:
                        break
                    for job in jobs:
                        job_id = str(job.get("id", ""))
                        if job_id and job_id not in all_jobs:
                            all_jobs[job_id] = job
                except Exception as e:
                    # 单次失败不阻塞，继续下一个
                    print(f"[Remotive] 关键词「{kw}」第{page+1}页失败: {e}")
                    continue

        return list(all_jobs.values())

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(raw.get("id", "")),
            "title": raw.get("job_title", ""),
            "company": raw.get("company_name", ""),
            "url": raw.get("url", ""),
            "description": raw.get("description", ""),
            "tags": raw.get("tags", []),
            "location": raw.get("candidate_required_location", "Remote"),
            "salary": raw.get("salary", ""),
            "job_type": raw.get("job_type", ""),
            "posted_at": raw.get("publication_date", ""),
        }
