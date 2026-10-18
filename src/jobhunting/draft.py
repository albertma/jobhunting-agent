"""申请包生成器：根据职位 JD + 个人画像生成定制申请材料

用法: main.py draft <job_id>

输出 drafts/<job_id>.md，包含：
  1. Fit 快评       —— 该职位值不值得投（地域/分数/红线）
  2. Cover Letter   —— 英文定制信（ woven 进 JD 命中的技能）
  3. 简历重点建议    —— JD 关键词 × 你的技能对照表
  4. 面试可能问题    —— 按命中技术生成的准备清单
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

import yaml

from .config import load as load_config
from .db import get_job
from .filter import score_with_config
from .log import setup_logging
from .models import Job

logger = setup_logging()

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PROFILE_PATH = _PROJECT_ROOT / "profile.yaml"
_DRAFTS_DIR = _PROJECT_ROOT / "drafts"

# 常见 mojibake 修复（RemoteOK 等源的数据常见）
_MOJIBAKE_FIXES = {
    "â€™": "'", "â€œ": '"', "â€\x9d": '"', "â€”": "—",
    "â€“": "–", "â€¦": "…", "Ã©": "é", "Â ": " ",
}


def clean_text(text: str) -> str:
    for bad, good in _MOJIBAKE_FIXES.items():
        text = text.replace(bad, good)
    # 去不可见控制字符
    text = "".join(c for c in text if unicodedata.category(c) != "Cc" or c == "\n")
    return re.sub(r"[ \t]+", " ", text)


def load_profile() -> dict:
    if not _PROFILE_PATH.exists():
        raise FileNotFoundError(
            f"未找到 {_PROFILE_PATH}，请先填写个人画像（参考文件内注释）"
        )
    with open(_PROFILE_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _is_placeholder(profile: dict) -> list[str]:
    """检查画像里未填的占位符，返回警告列表"""
    warns = []
    if "TODO" in str(profile.get("name", "")) or "你的" in str(profile.get("name", "")):
        warns.append("profile.yaml 的 name 还是占位符")
    skills_text = "\n".join(profile.get("skills") or [])
    if "TODO" in skills_text:
        warns.append("profile.yaml 的 skills 还有 TODO 未填")
    hl = "\n".join(str(h) for h in (profile.get("highlights") or []))
    if "TODO" in hl:
        warns.append("profile.yaml 的 highlights 还有 TODO 未填")
    return warns


# ── 关键词匹配分析 ────────────────────────────────────────

_STOPWORDS = {
    "the", "and", "for", "with", "you", "can", "all", "that", "this", "are",
    "our", "your", "from", "will", "have", "has", "not", "but", "its",
    "their", "they", "who", "how", "what", "when", "new", "use", "using",
    "run", "into", "per", "via", "was", "were", "been",
}


def _tokens(s: str) -> set[str]:
    """分词：斜杠拆开、去停用词、保留 ≥2 字符（ai/llm/go 这种短词很关键）"""
    s = s.lower().replace("/", " ")
    return {w for w in re.findall(r"[a-z][a-z+#.-]{1,}", s) if w not in _STOPWORDS}


def match_analysis(job: Job, cfg) -> dict:
    """JD 命中了哪些核心关键词（全文 + 标题）"""
    text = f"{job.title} {job.description}".lower()
    title_text = job.title.lower()
    core_hits = [kw for kw in cfg.core_keywords if kw.lower() in text]
    title_hits = [kw for kw in cfg.core_keywords if kw.lower() in title_text]
    return {"core": core_hits, "title": title_hits}


def skill_evidence_for(job: Job, profile: dict, matched: dict | None = None) -> list[str]:
    """从画像 skills 里挑出与 JD 相关的条目（按相关度排序）

    相关度 = JD 词重叠 + 5×命中 JD 核心关键词的词（如 "ai agent" 的 ai/agent）
    """
    skills: list[str] = [str(s) for s in (profile.get("skills") or [])]
    # 角色泛词不是领域信号（engineer/senior/lead...），别让它拉高无关技能行
    role_generic = {"engineer", "developer", "senior", "staff", "lead",
                    "manager", "junior", "principal", "founding", "build"}
    jd_tokens = _tokens(f"{job.title} {job.description}") - role_generic

    # JD 命中的核心关键词拆词；多词关键词更具体，加权更高
    matched_kws: list[list[str]] = [
        [w for w in _tokens(kw) if len(w) >= 2]
        for kw in (matched or {}).get("core", [])
    ]

    def relevance(skill_line: str) -> int:
        t = _tokens(skill_line)
        base = len(t & jd_tokens)
        # 命中一个核心关键词：3分 × 该关键词的词数（"ai agent"=6 分，"backend"=3 分）
        bonus = sum(3 * len(words) for words in matched_kws if t & set(words))
        return base + bonus

    return sorted(skills, key=relevance, reverse=True)


# ── 各部分生成 ────────────────────────────────────────────

def gen_fit_notes(job: Job, config) -> list[str]:
    notes: list[str] = []
    scored = score_with_config([job], config.scoring)[0]
    bd = scored.score_breakdown

    loc = bd.get("location", "unknown")
    if loc == "eligible":
        notes.append("✅ 地域：JD 明确覆盖你的地区（APAC/Worldwide）")
    elif loc == "restricted":
        notes.append("❌ 地域：限定美/欧时区，上海无法入职 —— 建议跳过")
    elif loc == "onsite":
        notes.append("❌ 地域：指定城市坐班 —— 建议跳过")
    else:
        notes.append("⚠️ 地域：JD 未明确地区，投递前到官网确认是否接受中国远程")

    if bd.get("talent_penalty"):
        notes.append("⚠️ 该公司是人才库/中介（先进池子再匹配，非具体岗位）")

    if not job.salary:
        notes.append("💡 JD 未写薪资：首轮沟通时记得确认预算范围")
    else:
        notes.append(f"💰 薪资：{job.salary}")

    if job.posted_at:
        notes.append(f"📅 发布时间：{job.posted_at[:10]}（超过 3 周的职位回复率会明显下降）")

    notes.append(f"📊 匹配分：{scored.score:.0f}/100（标题命中 {bd.get('title_hits', 0)} 个核心词）")
    return notes


def gen_cover_letter(job: Job, profile: dict, matched: list[str]) -> str:
    name = profile.get("name", "[Your Name]")
    headline = profile.get("headline", "Software Engineer")
    years = profile.get("years_experience", "5")
    tz = profile.get("timezone_flexibility", "Based in Shanghai (UTC+8), flexible overlap with US/EU hours.")

    skills_top = [s.split("：")[0].split(":")[0].strip() for s in matched[:3]]
    skills_line = ", ".join(skills_top) if skills_top else "backend development"

    highlights = profile.get("highlights") or []
    hl_para = ""
    if highlights:
        h = highlights[0]
        hl_para = (
            f"\nMost recently, {h.get('what', 'I led a project')} — {h.get('impact', 'with measurable impact')}."
        )

    links = profile.get("links") or {}
    signature = [name]
    if links.get("github"):
        signature.append(f"GitHub: {links['github']}")
    if links.get("linkedin"):
        signature.append(f"LinkedIn: {links['linkedin']}")
    sig = "\n".join(signature)

    return f"""Dear Hiring Team,

I'm applying for the {job.title} role at {job.company}. I'm a {headline} with {years}+ years of experience, and your posting lines up closely with what I do best: {skills_line}.

What drew me to this role specifically:{hl_para if hl_para else ''}

A few reasons I think I'd be a strong fit:
{chr(10).join(f"- {s}" for s in matched[:4]) if matched else "- Strong engineering fundamentals and fast ramp-up on new domains."}

{tz} — async-friendly, documentation-first, and comfortable owning features end-to-end.

Resume attached. I'd love to walk you through how my experience maps to what you're building.

Best regards,
{sig}
"""


def gen_resume_focus(job: Job, profile: dict, matched: dict) -> str:
    lines = [
        f"**JD 核心关键词（简历里要能找到对应证据）：** {', '.join(matched['core'][:8]) or '无'}",
        "",
        f"**标题关键词（放简历最顶部 Skills 区）：** {', '.join(matched['title'][:5]) or '无'}",
        "",
        "**你的技能 × JD 相关度排序（重新排列简历 bullet 顺序）：**",
    ]
    ranked = skill_evidence_for(job, profile, matched)
    if ranked:
        for i, s in enumerate(ranked[:5], 1):
            lines.append(f"  {i}. {s}")
    else:
        lines.append("  （画像 skills 为空，先填 profile.yaml）")
    lines += [
        "",
        "**改写建议：**",
        "- 每条 bullet 用动词开头 + 量化结果（X% improvement, N users, $M revenue）",
        "- JD 反复出现的词，确保简历原文有一模一样的写法（ATS 关键词匹配是精确匹配）",
        "- 没有相关经验的领域不要硬凑，用“快速学习证据”替代（如 side project）",
    ]
    return "\n".join(lines)


# 面试问题库：按技术关键词映射
_QUESTION_BANK = {
    "blockchain": "讲一个你交付过的链上系统：架构、gas 优化、安全审计怎么做的？",
    "smart contract": "智能合约出过事故吗？如何做防御性编程和升级策略？",
    "solidity": "Solidity 的重入/整型溢出你是怎么防的？用过哪些审计工具？",
    "defi": "讲讲你熟悉的 DeFi 协议机制（AMM/借贷/清算），有没有集成经验？",
    "ai agent": "你搭过的 Agent 架构：工具调用失败怎么处理？如何评估效果？",
    "llm": "LLM 应用怎么控成本和延迟？幻觉问题在你的场景怎么缓解？",
    "langchain": "用过 LangChain/LangGraph 吗？复杂多步任务的状态管理怎么设计？",
    "gpt": "怎么评测 prompt 改动效果？有没有做回归测试集？",
    "golang": "Go：并发模型（goroutine/channel）实战案例；怎么排查内存泄漏？",
    "rust": "Rust：所有权模型解决过什么实际问题？和 Go 的取舍？",
    "trading": "交易系统：低延迟设计、幂等性、对账怎么做？",
    "quantitative": "量化场景：数据清洗和信号回测的工程化经验？",
    "microservice": "微服务拆分的边界怎么定？服务间一致性怎么保证？",
    "fastapi": "FastAPI 的高并发部署：异步 DB、连接池、限流？",
    "kubernetes": "K8s 排障案例：OOM/网络策略/滚动发布事故？",
    "backend": "设计一个高吞吐 API：限流、缓存、水平扩展怎么考虑？",
}


def gen_interview_questions(matched: dict) -> str:
    qs = []
    seen = set()
    for kw in matched["title"] + matched["core"]:
        q = _QUESTION_BANK.get(kw)
        if q and q not in seen:
            seen.add(q)
            qs.append(f"- **{kw}** → {q}")
    if not qs:
        qs.append("- 通用：系统设计（和 JD 业务场景结合）+ 过往项目深挖")
    return "\n".join(qs[:6])


# ── 主入口 ────────────────────────────────────────────────

def generate_draft(job_id: str) -> Path:
    profile = load_profile()
    config = load_config()
    job = get_job(job_id)
    if not job:
        raise SystemExit(f"未找到职位 {job_id}，用 main.py list 查看可用 ID")

    job.description = clean_text(job.description or "")

    matched = match_analysis(job, config.scoring)
    matched_skills = skill_evidence_for(job, profile, matched)

    fit = gen_fit_notes(job, config)
    letter = gen_cover_letter(job, profile, matched_skills)
    resume = gen_resume_focus(job, profile, matched)
    questions = gen_interview_questions(matched)

    warns = _is_placeholder(profile)

    md = [
        f"# 申请包 · {job.title} @ {job.company}",
        f"> 生成于 {datetime.now():%Y-%m-%d %H:%M} | 匹配分见下 | {job.url}",
        "",
        "## 0️⃣ 值不值得投（Fit 快评）",
        *[f"- {n}" for n in fit],
        "",
        "## 1️⃣ Cover Letter（英文草稿，改成你的语气后发送）",
        "```",
        letter.strip(),
        "```",
        "",
        "## 2️⃣ 简历重点定制建议",
        resume,
        "",
        "## 3️⃣ 面试可能被问到",
        questions,
        "",
        "---",
        f"🔗 原文：{job.url}",
    ]
    if warns:
        md += ["", "## ⚠️ 画像未填完", *[f"- {w}（现在填 profile.yaml，重新生成效果更好）" for w in warns]]

    _DRAFTS_DIR.mkdir(exist_ok=True)
    safe_id = job.id.replace(":", "-").replace("/", "-")
    out = _DRAFTS_DIR / f"{safe_id}.md"
    out.write_text("\n".join(md), encoding="utf-8")
    logger.info(f"[Draft] 已生成 {out}")
    return out
