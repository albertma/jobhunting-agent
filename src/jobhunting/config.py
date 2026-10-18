"""配置管理：config.yaml + .env"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ── 项目根目录（src/ 上两级） ──────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"
_ENV_PATH = _PROJECT_ROOT / ".env"


@dataclass
class SourceConfig:
    """单个职位来源配置"""
    enabled: bool = True
    keywords: list[str] = field(default_factory=lambda: [
        "ai agent", "llm", "langchain", "openai", "gpt", "blockchain",
        "defi", "smart contract", "solidity", "web3", "crypto",
    ])
    exclude_keywords: list[str] = field(default_factory=lambda: [
        "intern", "internship",  # 排除实习
    ])
    max_results: int = 50  # 每批次最多抓取数


@dataclass
class ScoringConfig:
    """评分配置"""
    # 核心关键词（高权重）
    core_keywords: list[str] = field(default_factory=lambda: [
        "ai agent", "llm", "langchain", "openai api", "gpt-4",
        "defi", "smart contract", "solidity", "web3", "blockchain",
        "crypto", "trading", "quantitative",
    ])
    # 次要关键词（普通权重）
    secondary_keywords: list[str] = field(default_factory=lambda: [
        "python", "golang", "rust", "fastapi", "kubernetes",
        "docker", "microservice", "backend", "full stack",
    ])
    title_weight: float = 20.0      # 标题核心词命中（最强信号，不封顶）
    core_weight: float = 10.0       # 描述核心词每命中 +10 分
    desc_core_cap: int = 3          # 描述核心词计分封顶（防堆词）
    secondary_weight: float = 5.0   # 次要词每命中 +5 分
    secondary_cap: int = 4          # 次要词计分封顶
    # 薪资透明加成
    salary_bonus: float = 10.0
    # 人才库/中介惩罚（负分）
    talent_penalty: float = -30.0
    talent_companies: list[str] = field(default_factory=lambda: [
        "lemon.io", "toptal", "torc", "andela", "adeva", "arc.dev",
        "turing.com", "x-team", "gun.io", "braintrust", "talent500",
        "crossover", "wing", "alistagency",
    ])
    # 地域适配（候选人所在地：上海/中国）
    location_bonus: float = 10.0      # 地点含 APAC/Worldwide 等可入职地区
    location_penalty: float = -50.0   # 限定美/欧时区（无法入职）
    location_eligible: list[str] = field(default_factory=lambda: [
        "worldwide", "global", "anywhere", "apac", "asia",
        "singapore", "china", "hong kong", "taiwan", "japan", "seoul",
    ])
    location_restricted: list[str] = field(default_factory=lambda: [
        "usa", "u.s.", "united states", "northern america", "north america",
        "europe", "emea", "uk only", "latam only", "canada only",
    ])
    # 匹配度门槛（低于此分不入报告）
    min_score: float = 50.0
    max_score: float = 100.0


@dataclass
class NotifyConfig:
    """推送配置：飞书 + Telegram（至少配一个，都不配则不推送）"""
    enabled: bool = True
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_chat_id: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # 每天最多推送 N 条（避免刷屏）
    daily_max: int = 15


@dataclass
class AppConfig:
    """全局配置"""
    sources: dict[str, SourceConfig] = field(default_factory=dict)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    # 去重窗口（天内不去重）
    dedup_days: int = 7
    # 职位数据保留天数（超期自动清理，已投递的永久保留）
    retention_days: int = 90
    # 投递后 N 天无回复则提醒跟进
    followup_days: int = 7
    # 日志级别
    log_level: str = "INFO"


def _flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """扁平化嵌套 dict，用于 .env 覆盖"""
    out: dict[str, Any] = {}
    for k, v in d.items():
        full = f"{prefix}{k}".upper()
        if isinstance(v, dict):
            out.update(_flatten(v, f"{full}_"))
        else:
            out[full] = v
    return out


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def load() -> AppConfig:
    """加载 config.yaml 并用 .env 覆盖"""
    data = _load_yaml(_CONFIG_PATH)
    env = _load_env(_ENV_PATH)

    def get(key: str, default: Any = None) -> Any:
        return env.get(key.upper(), data.get(key.lower(), default))

    # 解析 sources
    raw_sources: dict[str, Any] = data.get("sources", {})
    sources = {
        name: SourceConfig(
            enabled=src.get("enabled", True),
            keywords=src.get("keywords", []),
            exclude_keywords=src.get("exclude_keywords", []),
            max_results=src.get("max_results", 50),
        )
        for name, src in raw_sources.items()
    }
    if not sources:
        sources["remotive"] = SourceConfig()
        sources["cryptjobslist"] = SourceConfig()
        sources["web3career"] = SourceConfig()

    # 解析 scoring
    raw_scoring: dict[str, Any] = data.get("scoring", {})
    scoring = ScoringConfig(
        core_keywords=raw_scoring.get("core_keywords", []),
        secondary_keywords=raw_scoring.get("secondary_keywords", []),
        title_weight=float(raw_scoring.get("title_weight", 20.0)),
        core_weight=float(raw_scoring.get("core_weight", 10.0)),
        desc_core_cap=int(raw_scoring.get("desc_core_cap", 3)),
        secondary_weight=float(raw_scoring.get("secondary_weight", 5.0)),
        secondary_cap=int(raw_scoring.get("secondary_cap", 4)),
        salary_bonus=float(raw_scoring.get("salary_bonus", 10.0)),
        talent_penalty=float(raw_scoring.get("talent_penalty", -30.0)),
        talent_companies=raw_scoring.get("talent_companies", []),
        location_bonus=float(raw_scoring.get("location_bonus", 10.0)),
        location_penalty=float(raw_scoring.get("location_penalty", -50.0)),
        location_eligible=raw_scoring.get("location_eligible", []),
        location_restricted=raw_scoring.get("location_restricted", []),
        min_score=float(raw_scoring.get("min_score", 50.0)),
        max_score=float(raw_scoring.get("max_score", 100.0)),
    )

    # 解析 notify
    raw_notify: dict[str, Any] = data.get("notify", {})
    notify = NotifyConfig(
        enabled=raw_notify.get("enabled", True),
        feishu_app_id=env.get("FEISHU_APP_ID", raw_notify.get("feishu_app_id", "")),
        feishu_app_secret=env.get("FEISHU_APP_SECRET", raw_notify.get("feishu_app_secret", "")),
        feishu_chat_id=env.get("FEISHU_CHAT_ID", raw_notify.get("feishu_chat_id", "")),
        telegram_bot_token=env.get("TELEGRAM_BOT_TOKEN", raw_notify.get("telegram_bot_token", "")),
        telegram_chat_id=env.get("TELEGRAM_CHAT_ID", raw_notify.get("telegram_chat_id", "")),
        daily_max=int(raw_notify.get("daily_max", 15)),
    )

    return AppConfig(
        sources=sources,
        scoring=scoring,
        notify=notify,
        dedup_days=int(data.get("dedup_days", 7)),
        retention_days=int(data.get("retention_days", 90)),
        followup_days=int(data.get("followup_days", 7)),
        log_level=data.get("log_level", "INFO"),
    )
