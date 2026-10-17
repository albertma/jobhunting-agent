"""职位数据模型"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class Job:
    """标准化职位数据（所有来源统一格式）"""

    id: str                          # 来源:来源ID，确保全局唯一
    source: Literal["remotive", "cryptjobslist", "web3career"]
    title: str                       # 岗位名称
    company: str                     # 公司名
    url: str                        # 原文链接
    description: str                 # 原始描述（用于关键词匹配）
    tags: list[str] = field(default_factory=list)  # 技术标签
    location: str = ""              # 地点（remote / 具体城市）
    salary: str = ""                # 薪资（原文）
    salary_low: int | None = None   # 年薪下限（USD，仅当明确时）
    salary_high: int | None = None  # 年薪上限（USD）
    job_type: str = ""              # full_time / contract / part_time
    posted_at: str = ""             # 发布时间（原文）
    score: float = 0.0             # 匹配度评分（0-100）
    score_breakdown: dict = field(default_factory=dict)  # 评分明细
    applied: bool = False           # 是否已投递

    def __post_init__(self):
        # 强制唯一 ID 前缀
        self.id = f"{self.source}:{self.id}"

    @property
    def score_label(self) -> str:
        if self.score >= 80:
            return "🔥 强匹配"
        elif self.score >= 60:
            return "✅ 中匹配"
        else:
            return "⚪ 低匹配"

    def to_summary(self) -> str:
        salary_line = f" 💰 {self.salary}" if self.salary else ""
        return (
            f"**{self.title}** @ {self.company}\n"
            f"{self.location or '🌍 Remote'}{salary_line}\n"
            f"{self.score_label}（{self.score:.0f}分）\n"
            f"🔗 {self.url}"
        )
