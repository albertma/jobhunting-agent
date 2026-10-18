"""LLM 服务：支持 OpenAI / Anthropic 兼容（MiniMax/DeepSeek/Ollama）

配置优先级：config.yaml 的 llm.* > 环境变量 > 默认 MiniMax（复用 FI-Agent）

用法:
  from jobhunting.llm import llm
  resp = llm.chat("hello")
  result = llm.chat_json(prompt, {"type":"object","properties":{"answer":{"type":"string"}}})
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

from .log import setup_logging

logger = setup_logging()

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"
_CACHE_DIR = _PROJECT_ROOT / "data" / "llm_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── 配置加载 ─────────────────────────────────────────────────────────

def _env_path() -> Path:
    p = _PROJECT_ROOT / ".env"
    if p.exists():
        return p
    # 复用 FI-Agent 的 .env（如果存在）
    fi_env = Path.home() / "sourcecode" / "workspace" / "python" / "FI-Agent" / ".env"
    if fi_env.exists():
        return fi_env
    return p



def _load_llm_config() -> dict[str, Any]:
    """从 config.yaml + .env 加载 LLM 配置，优先级: .env > config.yaml > 默认"""
    # config.yaml
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        cfg = data.get("llm") or {}
        if not isinstance(cfg, dict):
            cfg = {}
    except Exception:
        cfg = {}

    # .env（优先级更高，覆盖 config.yaml）
    env_vars: dict[str, str] = {}
    try:
        with open(_env_path(), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()
    except Exception:
        pass

    # 合并：env 覆盖 config.yaml
    def _e(key: str, fallback: str = "") -> str:
        return env_vars.get(key, cfg.get(key, fallback))

    return {
        "enabled": cfg.get("enabled", False) or bool(env_vars.get("LLM_API_KEY")),
        "provider": _e("LLM_PROVIDER", "anthropic"),
        "api_key": _e("LLM_API_KEY", "FIXME_set_api_key"),
        "base_url": _e("LLM_BASE_URL", "https://api.minimaxi.com/anthropic"),
        "model": _e("LLM_MODEL", "MiniMax-M2.7-highspeed"),
    }


def _resolve_provider(cfg: dict) -> dict[str, str]:
    """解析 provider + api_key + base_url + model

    配置优先级: .env > config.yaml > 默认 MiniMax
    """
    return {
        "provider": cfg.get("provider", "anthropic"),
        "api_key": cfg.get("api_key", "FIXME_set_api_key"),
        "base_url": cfg.get("base_url", "https://api.minimaxi.com/anthropic"),
        "model": cfg.get("model", "MiniMax-M2.7-highspeed"),
    }


# ── LLM 客户端（懒加载）─────────────────────────────────────────────

_client: Any = None


def is_llm_enabled() -> bool:
    """检查 LLM 是否可用（config.yaml / .env 已配置 LLM_API_KEY）"""
    cfg = _load_llm_config()
    return bool(cfg.get("enabled", False) or cfg.get("api_key", "") not in ("", "FIXME_set_api_key"))


def _build_client() -> Any:
    cfg = _resolve_provider(_load_llm_config())
    logger.info(f"[LLM] provider={cfg['provider']} model={cfg['model']} base={cfg['base_url']}")

    # Anthropic-compatible 路由：MiniMax / DeepSeek 等用 ChatAnthropic
    # OpenAI-compatible 路由：OpenAI / DeepSeek / Groq / Ollama 用 ChatOpenAI
    if cfg["provider"] == "anthropic" and "deepseek" not in cfg["model"].lower():
        if ChatAnthropic is None:
            raise SystemExit("pip install langchain-anthropic")
        return ChatAnthropic(
            model=cfg["model"],
            api_key=cfg["api_key"],
            base_url=cfg["base_url"],
            timeout=60.0,
            max_retries=2,
        )
    else:  # openai / deepseek / groq / ollama
        if ChatOpenAI is None:
            raise SystemExit("pip install langchain-openai")
        extra: dict[str, Any] = {}
        if cfg["base_url"]:
            extra["base_url"] = cfg["base_url"]
        return ChatOpenAI(
            model=cfg["model"],
            api_key=cfg["api_key"],
            timeout=60.0,
            max_retries=2,
            **extra,
        )


def _get_client() -> Any:
    global _client
    if _client is None:
        _client = _build_client()
    return _client


# ── 对话接口 ─────────────────────────────────────────────────────────

def chat(messages: list[dict[str, str]], *, model: str | None = None) -> str:
    """纯文本对话

    messages = [{"role":"system",...}, {"role":"user",...}]
    """
    client = _get_client()
    if model:
        # 临时换模型（暂不支持跨 provider）
        logger.warning("[LLM] model override not yet implemented for non-Anthropic providers")
    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        lc_msgs = []
        for m in messages:
            role = m.get("role", "user")
            if role == "system":
                lc_msgs.append(SystemMessage(content=m["content"]))
            elif role == "assistant":
                lc_msgs.append(AIMessage(content=m["content"]))
            else:
                lc_msgs.append(HumanMessage(content=m["content"]))
        resp = client.invoke(lc_msgs)
        # MiniMax-M2 系列含 thinking/reasoning block，过滤保留纯 text
        content = resp.content
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)
            raw = "\n".join(text_parts).strip()
        else:
            raw = str(content).strip()
        # 过滤 MiniMax 推理过程残留的 base64 签名行
        import re as _re
        _junk = _re.compile(r'^[A-Za-z0-9+/]{30,}={0,2}$', _re.MULTILINE)
        return "\n".join(
            l for l in raw.splitlines()
            if not _junk.match(l.strip())
        ).strip()
    except Exception as e:
        logger.error(f"[LLM] chat failed: {e}")
        raise


def chat_json(
    prompt: str,
    schema: dict,
    *,
    system: str = "You are a helpful assistant. Respond ONLY with valid JSON.",
) -> dict:
    """结构化 JSON 输出（用 LLM 原生 tool/JSON mode）"""
    client = _get_client()

    # 直接用标准库 json 解析

    text = chat([
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ])

    # 提取 JSON（允许代码块包裹）
    text = text.strip()
    for pattern in (
        r"```(?:json)?\s*(\{.*?\})\s*```",
        r"(\{[\s\S]*\})",
    ):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            text = m.group(1)
            break
    if not text.strip().startswith("{"):
        raise ValueError(f"LLM returned non-JSON: {text[:200]}")
    return json.loads(text)


# ── 磁盘缓存 ─────────────────────────────────────────────────────────

def _cache_key(prompt: str) -> str:
    import hashlib
    return hashlib.sha256(prompt.encode()).hexdigest()[:32]


def cached_llm(prompt: str, system: str = "") -> str:
    """带缓存的 chat（同一次运行内不重复调用 LLM）"""
    key = _cache_key(prompt + system)
    cache_file = _CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        logger.debug(f"[LLM] cache hit: {key[:8]}")
        return json.loads(cache_file.read_text())["content"]
    content = chat([{"role": "user", "content": prompt}]
                    + ([{"role": "system", "content": system}] if system else []))
    cache_file.write_text(json.dumps({"prompt": prompt, "content": content}, ensure_ascii=False))
    logger.info(f"[LLM] cached: {key[:8]}...")
    return content


# ── 快捷调用 ─────────────────────────────────────────────────────────

def job_fit_analysis(job_title: str, job_description: str, profile_skills: str,
                     years_exp: int) -> dict:
    """LLM 分析职位与候选人的匹配度（结构化 JSON 返回）"""
    schema = {
        "type": "object",
        "properties": {
            "match_score": {"type": "integer", "description": "0-100 匹配度估算"},
            "fit_summary": {"type": "string", "description": "2-3 句话的总体评价"},
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "你最强的 3 个匹配点（来自 JD 和简历）",
            },
            "gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "最明显的 2-3 个缺口或风险点",
            },
            "talking_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "面试时最有说服力的 3 个论据",
            },
            "salary_hint": {
                "type": "string",
                "description": "从 JD 推断的薪资范围（USD/年）或 'JD 未提及'",
            },
            "apply_recommendation": {
                "type": "string",
                "enum": ["强烈推荐", "推荐", "观望", "不推荐"],
                "description": "是否值得投递",
            },
        },
        "required": ["match_score", "fit_summary", "strengths", "gaps",
                     "talking_points", "apply_recommendation"],
    }
    prompt = f"""你是专业的求职顾问。请分析以下职位与候选人的匹配度。

## 职位
标题: {job_title}
描述: {job_description[:3000]}

## 候选人
经验年限: {years_exp}
核心技能:
{profile_skills}

请从以下维度评估：
1. match_score: 0-100，你对匹配度的主观评分（考虑技能重叠度、经验深度、领域相关性）
2. fit_summary: 2-3 句话总结
3. strengths: 候选人最强的 3 个匹配点（引用 JD 具体描述）
4. gaps: 最明显的 2-3 个缺口（诚实指出，不要过度乐观）
5. talking_points: 面试时最有说服力的 3 个论据（结合候选人真实经历）
6. salary_hint: 从 JD 推断的薪资范围，或 'JD 未提及'
7. apply_recommendation: 强烈推荐/推荐/观望/不推荐（给一个直接的判断）

请用 JSON 格式回复。"""
    try:
        return chat_json(prompt, schema,
                         system="你是一位资深求职顾问，评估直接、诚实、不废话。")
    except Exception as e:
        logger.warning(f"[LLM] job_fit_analysis failed: {e}")
        return {"error": str(e)}


def cover_letter(prompt: str) -> str:
    """LLM 生成定制 Cover Letter（prompt 已含 JD + 画像上下文）"""
    system = (
        "You are a professional career coach. Write a cover letter that is:\n"
        "- Confident and specific (no fluff or generic phrases)\n"
        "- 250-350 words\n"
        "- Uses first-person sparingly (\"I\" appears 3-5 times max)\n"
        "- Leads with the strongest match, not a generic greeting\n"
        "- Ends with a clear call to action\n"
        "- No templates or buzzword stuffing\n"
        "If the job posting includes salary, location or tech stack, address them directly."
    )
    return chat([{"role": "system", "content": system},
                 {"role": "user", "content": prompt}])


def chat_about_job(job_id: str, question: str, job_title: str,
                    job_description: str, profile: str) -> str:
    """对话模式：用户用自然语言询问关于某个职位的问题"""
    prompt = f"""你是求职顾问。用户在看一个职位，有问题想问你。

## 职位
标题: {job_title}
描述（摘录）: {job_description[:2000]}

## 用户背景
{profile}

## 用户的问题
{question}

请给出直接、有洞察的回答。如果问题超出职位信息本身（如询问市场价、签证等），请诚实说明。
不要罗列职位描述的内容，要给用户真正有价值的分析。"""
    return chat([{"role": "system",
                  "content": "你是求职顾问。回答直接、有见地，帮用户做出明智的求职决策。"},
                 {"role": "user", "content": prompt}])
