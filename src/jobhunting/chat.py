"""对话模式：用户用自然语言询问职位相关问题

  main.py chat <job_id> <question>
  main.py chat <job_id>          # 交互模式，逐条提问
  main.py chat --fit <job_id>   # 快速 LLM 匹配分析
"""
from __future__ import annotations

from pathlib import Path

from .db import get_job
from .draft import load_profile
from .log import setup_logging
from .llm import chat_about_job, cover_letter, job_fit_analysis
from .config import load as load_config

logger = setup_logging()


def cmd_chat(job_id: str | None, question: str | None, fit_only: bool,
              draft_only: bool, profile_path: Path | None) -> None:
    """对话入口"""
    from .config import load as load_config
    from .draft import load_profile

    if fit_only:
        _cmd_fit(job_id)
        return
    if draft_only:
        _cmd_draft_llm(job_id, profile_path)
        return

    config = load_config()
    job = get_job(job_id) if job_id else None
    if not job:
        print(f"未找到职位: {job_id}")
        return

    profile = load_profile()
    profile_text = _profile_summary(profile)
    job_text = f"【{job.title}】@{job.company}\n{job.description[:3000]}"

    # 单次问答模式
    if question:
        resp = chat_about_job(job.id, question, job.title,
                               job.description, profile_text)
        print(f"\n🤖 Agent:\n{resp}")
        return

    # 交互模式
    print(f"\n💬 Agent 模式：关于 【{job.title} @{job.company}】")
    print("   可问：值不值得投 / 我的经验是否匹配 / 面试会问什么 / 如何定制简历...\n")
    print("   输入 quit 退出\n")
    while True:
        try:
            q = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出")
            break
        if q in ("quit", "q", "exit"):
            print("已退出")
            break
        if not q:
            continue
        try:
            resp = chat_about_job(job.id, q, job.title,
                                   job.description, profile_text)
            print(f"\n🤖 Agent: {resp}\n")
        except Exception as e:
            print(f"❌ 出错了: {e}\n")


def _cmd_fit(job_id: str | None) -> None:
    """LLM 深度匹配分析（快速版）"""
    from .draft import load_profile
    profile = load_profile()
    job = get_job(job_id)
    if not job:
        print(f"未找到职位: {job_id}")
        return
    print(f"\n🔍 正在分析: {job.title} @{job.company} ...", end="", flush=True)
    profile_skills = "\n".join(str(s) for s in profile.get("skills", []))
    result = job_fit_analysis(job.title, job.description or "",
                              profile_skills, profile.get("years_experience", 0))
    if "error" in result:
        print(f"\n❌ LLM 调用失败: {result['error']}")
        return
    print(" done\n")
    print(f"  📊 匹配分: {result['match_score']}/100")
    print(f"  📝 评价: {result['fit_summary']}")
    print(f"  ✅ 优势:")
    for s in result.get("strengths", []):
        print(f"     · {s}")
    if result.get("gaps"):
        print(f"  ⚠️ 缺口:")
        for g in result["gaps"]:
            print(f"     · {g}")
    if result.get("salary_hint"):
        print(f"  💰 薪资: {result['salary_hint']}")
    print(f"  🎯 推荐: {result['apply_recommendation']}")


def _cmd_draft_llm(job_id: str | None, profile_path: Path | None) -> None:
    """LLM 增强版申请包生成"""
    from .draft import load_profile
    config = load_config()
    job = get_job(job_id)
    if not job:
        print(f"未找到职位: {job_id}")
        return
    profile = load_profile()

    print(f"\n✍️  正在生成定制 Cover Letter ...")
    prompt = _build_cover_prompt(job, profile)
    letter = cover_letter(prompt)
    print(f"\n📄 定制 Cover Letter:\n{'='*50}\n{letter}\n{'='*50}")
    print(f"\n🔗 职位链接: {job.url}")


def _build_cover_prompt(job, profile) -> str:
    name = profile.get("name", "Candidate")
    headline = profile.get("headline", "")
    years = profile.get("years_experience", 0)
    tz = profile.get("timezone_flexibility", "")
    skills = "\n".join(f"- {s}" for s in profile.get("skills", []))
    highlights = profile.get("highlights") or []
    hl = ""
    if highlights:
        h = highlights[0]
        hl = f"\n我最相关的项目: {h.get('title')}\n  {h.get('what')}\n  成果: {h.get('impact')}"
    return f"""Write a cover letter for the following position. Follow all instructions in the system prompt.

## Position
Title: {job.title}
Company: {job.company}
Location: {job.location or 'Remote'}
Salary: {job.salary or 'Not specified'}
Description (key parts):
{job.description[:2000] if job.description else 'See full posting'}

## Candidate
Name: {name}
Headline: {headline}
Experience: {years} years
Timezone: {tz}
Key skills:
{skills}
{hl}

## Instructions
- 250-350 words
- Address the letter to "Dear Hiring Team"
- Open with the single most compelling reason you're a fit (no generic opening)
- Weave in 1-2 specific accomplishments from the candidate's background that directly match the job requirements
- Address any location/timezone question proactively
- End with a specific call to action
- No padding, no buzzword lists
"""


def _profile_summary(profile: dict) -> str:
    lines = [
        f"姓名: {profile.get('name','')}",
        f"定位: {profile.get('headline','')}",
        f"工作年限: {profile.get('years_experience',0)} 年",
        f"时区: {profile.get('timezone_flexibility','')}",
        f"\n核心技能:",
    ]
    for s in profile.get("skills", []):
        lines.append(f"  - {s}")
    lines.append("\n亮点项目:")
    for h in (profile.get("highlights") or [])[:2]:
        lines.append(f"  · {h.get('title')}: {h.get('what','')[:80]} — {h.get('impact','')[:60]}")
    return "\n".join(lines)
