"""RemoteOK.com — Remote-only 职位聚合

API: https://remoteok.com/api （免费公开 JSON，无需认证）
- 单次请求返回全量列表（约 100 条），本地按关键词过滤
- 遵守其 ToS：带自定义 User-Agent、低频率访问（每次运行只请求 1 次）
- 返回数组第一个元素是法律声明（无 position 字段），需过滤
"""
from __future__ import annotations

import re

import httpx

from .base import JobSource
from ..log import setup_logging

logger = setup_logging()

REMOTEOK_API = "https://remoteok.com/api"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "jobhunting-bot/1.0 (personal job search)"
)


class RemoteOKSource(JobSource):
    """RemoteOK.com API 数据源"""

    name = "remoteok"
    source_type = "api"

    def fetch(self) -> list[dict[str, Any]]:
        keywords = [k.lower() for k in self.config.get("keywords", [])]
        max_results = self.config.get("max_results", 100)

        try:
            resp = httpx.get(
                REMOTEOK_API,
                headers={"User-Agent": _UA},
                timeout=20.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"[RemoteOK] 请求失败: {e}")
            return []

        # 过滤法律声明行 + 无效条目
        jobs = [
            d for d in data
            if isinstance(d, dict) and d.get("position") and d.get("slug")
        ]

        # 本地关键词过滤：命中 position / tags / company 任一即保留
        def match(j: dict) -> bool:
            if not keywords:
                return True
            tags = " ".join(j.get("tags") or [])
            text = f"{j.get('position', '')} {tags} {j.get('company', '')}".lower()
            return any(kw in text for kw in keywords)

        return [j for j in jobs if match(j)][:max_results]

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        # 薪资：min/max（USD/年）→ 展示格式
        salary = ""
        smin, smax = raw.get("salary_min") or 0, raw.get("salary_max") or 0
        if smin and smax and smin > 0:
            if smin == smax:
                salary = f"${smin / 1000:.0f}k"
            else:
                salary = f"${smin / 1000:.0f}k - ${smax / 1000:.0f}k"

        return {
            "id": raw.get("slug", ""),
            "title": raw.get("position", ""),
            "company": raw.get("company", ""),
            "url": raw.get("url", ""),
            # 描述是 HTML，去标签便于评分
            "description": _strip_html(raw.get("description", "")),
            "tags": raw.get("tags") or [],
            "location": raw.get("location") or "Remote",
            "salary": salary,
            "job_type": "full_time",
            "posted_at": raw.get("date", ""),
        }


def _strip_html(html: str) -> str:
    """粗略去 HTML 标签 + 压缩空白"""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()
