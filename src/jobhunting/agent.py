"""交互式 Agent REPL

运行:
  python main.py agent

特点:
  - 启动时展示最近匹配职位
  - 输入编号选择职位，进入对话
  - 自然语言问任何职位相关问题
  - 内置命令: /fit /draft /apply /jobs /quit
  - LLM 不可用时优雅降级到规则分析
"""
from __future__ import annotations

import sys
import textwrap
from typing import Optional

from .config import load as load_config
from .db import get_job, mark_applied, recent_jobs
from .draft import load_profile
from .log import setup_logging
from .llm import chat_about_job, cover_letter, is_llm_enabled, job_fit_analysis

logger = setup_logging()

_PROMPT = "\n🧑 你 > "
_INDENT = "    "


def _print_wrapped(text: str, width: int = 72) -> None:
    for line in textwrap.wrap(text, width=width):
        print(line)


def _print_job(job, idx: int = 0) -> None:
    tag = f"[{idx}] " if idx else "  "
    score_emoji = "🔥" if job.score >= 80 else "✅" if job.score >= 60 else "⚪"
    print(f"{tag}{score_emoji} [{job.score:.0f}分] {job.title}")
    print(f"{_INDENT}@{job.company}  |  {job.location or '🌍 Remote'}"
          + (f"  💰 {job.salary}" if job.salary else ""))
    print(f"{_INDENT}来源: {job.source}")


def _is_llm_available() -> bool:
    try:
        return is_llm_enabled()
    except Exception:
        return False


def _build_system_prompt(profile: dict) -> str:
    skills = "\n".join(f"- {s}" for s in profile.get("skills", [])[:5])
    highlights = profile.get("highlights") or []
    hl = ""
    if highlights:
        h = highlights[0]
        hl = f"\n最相关项目: {h.get('title')}\n  {h.get('what', '')[:120]}\n  成果: {h.get('impact', '')[:80]}"
    return (
        "你是一位专业的求职顾问。用户在看一个职位，请用中文回答，"
        "分析直接诚实，帮助用户做出明智决策。"
        "不要罗列职位描述内容，要给用户真正有价值的洞察。\n"
        f"用户背景: {profile.get('headline', '')}，"
        f"{profile.get('years_experience', 0)} 年经验，"
        f"时区: {profile.get('timezone_flexibility', '')[:50]}\n"
        f"核心技能:\n{skills}{hl}"
    )


def _session(job, profile: dict, llm_ok: bool) -> None:
    """单职位对话循环"""
    print(f"\n{'='*60}")
    print(f"📋 {job.title} @ {job.company}")
    if job.salary:
        print(f"   💰 {job.salary}")
    print(f"   🌍 {job.location or 'Remote'}")
    print(f"   🔗 {job.url}")
    print(f"{'='*60}")
    print("\n内置命令: /fit (匹配分析)  /draft (Cover Letter)  /apply (标记投递)  /jobs (重新选职位)  /quit\n")

    # 记住对话历史（每轮附带系统上下文）
    system = _build_system_prompt(profile)
    history: list[dict] = []

    while True:
        try:
            user_input = input(_PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n已退出对话")
            return

        if not user_input:
            continue

        cmd = user_input.lstrip("/").lower()

        # ── 内置命令 ──
        if cmd == "quit" or cmd == "q":
            print("已退出对话")
            return

        if cmd == "jobs":
            print("\n切换职位...")
            return  # 外层会重新显示职位列表

        if cmd == "apply":
            mark_applied(job.id)
            print(f"✅ 已标记投递: {job.title} @ {job.company}")
            print("收到回复后运行: main.py replied <job_id>")
            continue

        if cmd == "fit":
            print("\n🔍 正在分析...", end="", flush=True)
            if not llm_ok:
                print("\n⚠️ LLM 未启用，跳过智能分析")
                continue
            try:
                profile_skills = "\n".join(str(s) for s in profile.get("skills", []))
                result = job_fit_analysis(
                    job.title, job.description or "", profile_skills,
                    profile.get("years_experience", 0),
                )
                if "error" in result:
                    print(f"\n❌ 分析失败: {result['error']}")
                else:
                    print(f"\n📊 匹配分: {result['match_score']}/100")
                    _print_wrapped(f"📝 {result['fit_summary']}")
                    print(f"\n✅ 优势:")
                    for s in result.get("strengths", []):
                        print(f"   · {s}")
                    gaps = result.get("gaps", [])
                    if gaps:
                        print(f"\n⚠️ 缺口:")
                        for g in gaps:
                            print(f"   · {g}")
                    salary = result.get("salary_hint")
                    if salary and salary != "JD 未提及":
                        print(f"\n💰 薪资: {salary}")
                    print(f"\n🎯 推荐: {result['apply_recommendation']}")
            except Exception as e:
                print(f"\n❌ 分析出错: {e}")
            continue

        if cmd == "draft":
            if not llm_ok:
                print("\n⚠️ LLM 未启用，无法生成定制 Cover Letter")
                print("   运行以下命令启用 LLM：")
                print("   1. config.yaml: llm.enabled = true")
                print("   2. 配置 API Key（见 README）")
                continue
            print("\n✍️  正在生成定制 Cover Letter ...", end="", flush=True)
            try:
                prompt = _build_cover_prompt(job, profile)
                letter = cover_letter(prompt)
                print(f"\n{'='*60}")
                print(letter)
                print(f"{'='*60}")
                print(f"\n🔗 {job.url}")
            except Exception as e:
                print(f"\n❌ 生成失败: {e}")
            continue

        # ── 自然语言问答 ──
        if llm_ok:
            try:
                print("\n🤖 Agent ...", end="", flush=True)
                history.append({"role": "user", "content": user_input})
                full_history = [{"role": "system", "content": system}] + history
                resp = chat_about_job(
                    job.id, user_input, job.title, job.description or "", ""
                )
                history.append({"role": "assistant", "content": resp})
                print(f"\n🤖 Agent:\n{textwrap.indent(resp, _INDENT)}\n")
            except Exception as e:
                print(f"\n❌ Agent 出错: {e}")
        else:
            # LLM 不可用时的降级
            print(
                "\n⚠️  LLM 未启用，开启规则分析模式:\n"
                "   直接描述你的问题，我来帮你分析。\n"
                "   示例:\n"
                "   · 这个职位适合我吗？\n"
                "   · 我最大的优势是什么？\n"
                "   · 这个 JD 最大的风险点是什么？\n"
                "   · 如何定制简历？\n"
            )


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
        hl = f"\nMost relevant project: {h.get('title')}\n  {h.get('what', '')}\n  Impact: {h.get('impact', '')}"
    return (
        f"Write a cover letter for the following position. Be specific, no generic phrases.\n\n"
        f"Position: {job.title}\nCompany: {job.company}\n"
        f"Location: {job.location or 'Remote'}\nSalary: {job.salary or 'Not specified'}\n\n"
        f"Description (key parts):\n{job.description[:2000] if job.description else 'See posting'}\n\n"
        f"Candidate:\nName: {name}\nHeadline: {headline}\n"
        f"Experience: {years} years\nTimezone: {tz}\nSkills:\n{skills}{hl}\n\n"
        "Requirements:\n"
        "- 250-350 words\n"
        "- No template phrases, no buzzword lists\n"
        "- Lead with the strongest match\n"
        "- Address timezone proactively\n"
        "- End with a specific call to action"
    )


def run_repl() -> None:
    config = load_config()
    llm_ok = _is_llm_available()

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║          🤖  JobHunting Agent — 求职对话助手               ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    if llm_ok:
        print("  LLM: ✅ 已启用（MiniMax）")
    else:
        print("  LLM: ⚠️  未启用，部分功能受限（/fit /draft 需要 LLM）")
        print("  启用方式: config.yaml → llm.enabled: true + 配置 API Key")
    print()

    # 加载画像
    try:
        profile = load_profile()
        print(f"  画像: {profile.get('name', '未命名')} | {profile.get('headline', '')}")
    except Exception:
        profile = {}
        print("  ⚠️ 未找到 profile.yaml，部分功能受限")

    # 显示最近匹配职位
    print(f"\n{'─'*60}")
    print("最近入库的匹配职位（输入编号选择，进入对话）：")
    jobs = recent_jobs(limit=15)
    applied = {j.id for j in jobs if getattr(j, "applied", False)}

    if not jobs:
        print("  暂无职位，先运行: main.py run")
    else:
        for i, job in enumerate(jobs):
            applied_tag = " ✅" if job.id in applied else ""
            _print_job(job, idx=i + 1)
            if applied_tag:
                print(f"{_INDENT}（已投递）")

    print(f"{'─'*60}")

    # 主循环
    while True:
        try:
            choice = input("\n选择职位（1-15）或输入 job_id > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            return

        if not choice:
            continue

        # 内置命令
        if choice.lstrip("/").lower() in ("quit", "q", "exit"):
            print("再见！")
            return

        if choice.lstrip("/").lower() == "run":
            print("运行: main.py run --push 抓取新职位\n")
            continue

        # 解析选择
        job = None
        if choice.isdigit() and 1 <= int(choice) <= len(jobs):
            job = jobs[int(choice) - 1]
        else:
            # 当 job_id 处理
            job = get_job(choice)

        if not job:
            print(f"❌ 未找到职位: {choice}（输入 1-{len(jobs)} 选择，或 job_id）")
            continue

        # 进入对话
        _session(job, profile, llm_ok)


def cmd_agent() -> None:
    """CLI 入口: main.py agent"""
    run_repl()
