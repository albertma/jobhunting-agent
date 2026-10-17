"""职位来源基类"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class JobSource(ABC):
    """职位来源抽象基类"""

    name: str = ""          # 如 "remotive"
    source_type: str = ""   # 如 "api" 或 "scraper"

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        """获取原始职位数据列表（字典格式）"""
        ...

    def normalize(self, raw: dict[str, Any]) -> dict[str, Any]:
        """子类可覆盖：将原始字典映射为标准化字段"""
        return {
            "id": raw.get("id", ""),
            "title": raw.get("title", ""),
            "company": raw.get("company", ""),
            "url": raw.get("url", raw.get("link", "")),
            "description": raw.get("description", ""),
            "tags": raw.get("tags", []),
            "location": raw.get("location", ""),
            "salary": raw.get("salary", ""),
            "job_type": raw.get("job_type", ""),
            "posted_at": raw.get("posted_at", raw.get("publication_date", "")),
        }
