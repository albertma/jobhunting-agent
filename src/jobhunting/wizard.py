"""交互式初始化向导：根据个人情况生成 profile.yaml + config.yaml

  python main.py init
"""
from __future__ import annotations

from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PROFILE = _PROJECT_ROOT / "profile.yaml"
_CONFIG = _PROJECT_ROOT / "config.yaml"

# ── 地域模板：按所在地生成 location 评分词表 ───────────────
_REGIONS = {
    "cn": {
        "match": ("china", "shanghai", "beijing", "shenzhen", "hangzhou",
                  "chengdu", "guangzhou", "hong kong", "hongkong", "taiwan", "中国", "上海", "北京", "深圳"),
        "eligible": ["worldwide", "global", "anywhere", "apac", "asia",
                     "singapore", "china", "hong kong", "taiwan", "japan", "seoul"],
        "restricted": ["usa", "u.s.", "united states", "northern america",
                       "north america", "europe", "emea", "uk only",
                       "latam only", "canada only"],
    },
    "eu": {
        "match": ("germany", "berlin", "france", "paris", "netherlands", "amsterdam",
                  "spain", "italy", "poland", "sweden", "switzerland", "uk", "london",
                  "europe", "德国", "法国", "荷兰"),
        "eligible": ["worldwide", "global", "anywhere", "europe", "emea", "eu"],
        "restricted": ["usa only", "u.s. only", "north america", "americas only",
                       "china only", "apac only"],
    },
    "us": {
        "match": ("usa", "u.s.", "united states", "new york", "san francisco",
                  "seattle", "austin", "texas", "boston", "chicago", "denver"),
        "eligible": ["worldwide", "global", "anywhere", "usa", "u.s.",
                     "north america", "americas"],
        "restricted": ["europe only", "eu only", "uk only", "apac only", "china only"],
    },
}
_DEFAULT_REGION = {
    "eligible": ["worldwide", "global", "anywise", "anywhere", "remote"],
    "restricted": [],
}


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val or default


def _ask_lines(prompt: str, end_hint: str = "（空行结束）") -> list[str]:
    print(f"{prompt} {end_hint}")
    lines = []
    while True:
        try:
            line = input("  > ").strip()
        except EOFError:
            break
        if not line:
            break
        lines.append(line)
    return lines


def _detect_region(location: str) -> dict:
    loc = location.lower()
    for profile in _REGIONS.values():
        if any(k in loc for k in profile["match"]):
            return profile
    return _DEFAULT_REGION


def _build_profile(answers: dict) -> dict:
    return {
        "name": answers["name"],
        "location": answers["location"],
        "timezone_flexibility": answers["tz"],
        "years_experience": answers["years"],
        "headline": answers["headline"],
        "links": {"github": answers["github"], "linkedin": answers["linkedin"], "portfolio": ""},
        "skills": answers["skills"],
        "highlights": [
            {"title": t, "what": w, "impact": i}
            for t, w, i in answers["highlights"]
        ],
        "preferences": {
            "expected_salary": "",
            "work_mode": answers["work_mode"],
            "english_level": answers["english"],
        },
        "tone": "confident, concise, no fluff",
    }


def _build_config(answers: dict, region: dict) -> str:
    kws = [f'    - "{k}"' for k in answers["keywords"]]
    kw_block = "\n".join(kws)
    src = "\n".join(f'    - "{k}"' for k in answers["source_keywords"] or answers["keywords"])
    eligible = "\n".join(f'    - "{k}"' for k in region["eligible"])
    restricted = "\n".join(f'    - "{k}"' for k in region["restricted"])

    return f"""# JobHunting 配置 — 由 init 向导生成，可随时手工编辑

sources:
  remotive:
    enabled: true
    keywords:
{src}
    exclude_keywords:
      - "intern"
      - "internship"
      - "part time"
    max_results: 100

  cryptjobslist:
    enabled: true
    keywords:
{src}
    exclude_keywords:
      - "intern"
    max_results: 50

  web3career:
    enabled: true
    keywords:
{src}
    exclude_keywords:
      - "intern"
    max_results: 50

  remoteok:
    enabled: true
    keywords:
{src}
    exclude_keywords:
      - "intern"
      - "part time"
    max_results: 60

scoring:
  # 你方向的匹配词（标题命中权重最高）
  core_keywords:
{kw_block}

  secondary_keywords:
    - "python"
    - "kubernetes"
    - "docker"
    - "aws"
    - "gcp"
    - "postgresql"
    - "redis"
    - "git"
    - "ci/cd"
    - "devops"

  title_weight: 20.0
  core_weight: 10.0
  desc_core_cap: 3
  secondary_weight: 5.0
  secondary_cap: 4
  salary_bonus: 10.0
  talent_penalty: -30.0
  talent_companies:
    - "lemon.io"
    - "toptal"
    - "torc"
    - "andela"
    - "adeva"
    - "arc.dev"
    - "turing.com"
    - "x-team"
    - "gun.io"
    - "braintrust"
    - "talent500"
    - "crossover"

  # 地域适配（基于你的所在地: {answers['location']}）
  location_bonus: 10.0
  location_penalty: -50.0
  location_eligible:
{eligible}
  location_restricted:
{restricted}

  min_score: 40.0
  max_score: 100.0

notify:
  enabled: true
  daily_max: 15

dedup_days: 7
retention_days: 90
followup_days: 7
log_level: INFO
"""


def run_wizard() -> None:
    print("=" * 60)
    print("🤖 JobHunting 初始化向导 — 根据你的情况定制求职 Agent")
    print("=" * 60)

    if _PROFILE.exists() or _CONFIG.exists():
        ok = _ask("\n⚠️ 已存在 profile.yaml / config.yaml，覆盖? (y/N)", "n")
        if ok.lower() != "y":
            print("已取消，现有配置未改动")
            return

    print("\n── 第 1 步：基本信息 ──")
    name = _ask("你的名字（英文，用于信件落款）", "Your Name")
    location = _ask("所在地（城市, 国家）", "Shanghai, China")
    tz = _ask(
        "时区弹性（英文一句话）",
        f"Based in {location} (UTC+8), flexible to overlap 3-4 hours with target team timezone.",
    )
    years = _ask("工作年限", "5")
    headline = _ask("一句话定位（headline）", "Backend Engineer")

    print("\n── 第 2 步：链接 ──")
    github = _ask("GitHub 主页（可空）")
    linkedin = _ask("LinkedIn 主页（可空）")

    print("\n── 第 3 步：核心技能（每行一条：'类别: 年限/项目 + 量化结果'）──")
    print("   例: Go: 5 years building trading services (50k QPS)")
    skills = _ask_lines("输入技能:")
    if not skills:
        skills = ["TODO: 填写你的技能（编辑 profile.yaml）"]

    print("\n── 第 4 步：亮点项目（最多 3 个）──")
    highlights = []
    for i in range(1, 4):
        t = _ask(f"项目 {i} 名称（回车跳过）")
        if not t:
            break
        w = _ask("  做了什么（技术栈/架构）")
        im = _ask("  量化结果")
        highlights.append((t, w, im))
    if not highlights:
        highlights = [("TODO 项目名", "做了什么", "量化结果")]

    print("\n── 第 5 步：求职方向（决定搜索关键词和评分核心词）──")
    print("   例: ai agent, llm, golang, blockchain")
    kw_raw = _ask("方向关键词（逗号分隔）", "backend")
    keywords = [k.strip().lower() for k in kw_raw.replace("，", ",").split(",") if k.strip()]

    english = _ask("英语水平", "Fluent working proficiency")
    work_mode = _ask("工作模式偏好", "Full-time remote preferred")

    answers = {
        "name": name, "location": location, "tz": tz, "years": years,
        "headline": headline, "github": github, "linkedin": linkedin,
        "skills": skills, "highlights": highlights, "keywords": keywords,
        "english": english, "work_mode": work_mode, "source_keywords": [],
    }

    region = _detect_region(location)

    # 写 profile.yaml
    with open(_PROFILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            _build_profile(answers), f, allow_unicode=True, sort_keys=False, width=100
        )
    print(f"\n✅ 已生成 {_PROFILE}")

    # 写 config.yaml
    _CONFIG.write_text(_build_config(answers, region), encoding="utf-8")
    print(f"✅ 已生成 {_CONFIG}（地域适配: {location}）")

    print("\n── 最后一步：通知渠道 ──")
    print("复制 .env.example 为 .env，填入飞书或 Telegram 任一通道：")
    print("  飞书:   FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_CHAT_ID")
    print("  Telegram: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
    print("\n然后运行: python main.py run --push   # 抓取 + 推送")
    print("生成申请包: python main.py draft <job_id>")
