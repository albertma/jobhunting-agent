"""通知服务：飞书 + Telegram 双通道"""
from __future__ import annotations

import json
from typing import Any

import httpx

from .log import setup_logging

logger = setup_logging()

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
_TOKEN_URL = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
_SEND_URL = f"{FEISHU_API_BASE}/im/v1/messages"

TELEGRAM_API = "https://api.telegram.org"

_HTTP_TIMEOUT = 10.0


def _get_token(app_id: str, app_secret: str) -> str | None:
    """获取 tenant_access_token"""
    try:
        resp = httpx.post(
            _TOKEN_URL,
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0:
            return data["tenant_access_token"]
    except Exception as e:
        logger.warning(f"[Feishu] 获取 token 失败: {e}")
    return None


def _send_message(
    token: str,
    chat_id: str,
    content: dict[str, Any],
) -> bool:
    """发送富文本消息（post 类型）"""
    try:
        resp = httpx.post(
            _SEND_URL,
            params={"receive_id_type": "chat_id"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "receive_id": chat_id,
                "msg_type": "post",
                "content": json.dumps(content),
            },
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("code") == 0
    except Exception as e:
        logger.warning(f"[Feishu] 发送消息失败: {e}")
        return False


def telegram_send_text(
    title: str,
    body: str,
    bot_token: str,
    chat_id: str,
) -> bool:
    """发送 Telegram 消息（Markdown 格式），失败不抛异常"""
    if not (bot_token and chat_id):
        return False
    try:
        resp = httpx.post(
            f"{TELEGRAM_API}/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": f"*{title}*\n\n{body}",
                "parse_mode": "Markdown",
            },
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("ok", False)
    except Exception as e:
        logger.warning(f"[Telegram] 发送失败: {e}")
        return False


def notify_text(
    title: str,
    body: str,
    *,
    feishu_app_id: str = "",
    feishu_app_secret: str = "",
    feishu_chat_id: str = "",
    telegram_token: str = "",
    telegram_chat_id: str = "",
) -> bool:
    """向所有已配置的通道发送纯文本；任一成功即 True"""
    sent = False
    if feishu_app_id and feishu_app_secret and feishu_chat_id:
        sent |= feishu_notify_text(title, body, feishu_app_id, feishu_app_secret, feishu_chat_id)
    if telegram_token and telegram_chat_id:
        sent |= telegram_send_text(title, body, telegram_token, telegram_chat_id)
    if not sent:
        logger.info("[Notify] 无可用通道或全部失败")
    return sent


def feishu_notify(
    title: str,
    jobs: list,  # list[Job]
    app_id: str,
    app_secret: str,
    chat_id: str,
) -> bool:
    """发送职位汇总飞书消息，失败不抛异常"""
    if not (app_id and app_secret and chat_id):
        logger.info("[Feishu] 配置不完整，跳过推送")
        return False

    token = _get_token(app_id, app_secret)
    if not token:
        return False

    # 构建 post 消息（飞书富文本格式）
    # 按匹配度分组
    strong = [j for j in jobs if j.score >= 80]
    medium = [j for j in jobs if 60 <= j.score < 80]
    other = [j for j in jobs if j.score < 60]

    content: dict[str, Any] = {
        "zh_cn": {
            "title": title,
            "content": [
                # 标题行
                [{"tag": "text", "text": title, "text_style": {"bold": True, "font_size": "16px"}}],
            ]
        }
    }

    def job_blocks(jobs_batch: list, label: str) -> list:
        blocks = [[{"tag": "text", "text": f"\n📌 {label}（{len(jobs_batch)} 个）"}]]
        for j in jobs_batch[:10]:  # 每组最多 10 条
            blocks.append(
                [
                    {"tag": "text", "text": "\n"},
                    {"tag": "text", "text": j.title, "text_style": {"bold": True}},
                    {"tag": "text", "text": f" @ {j.company}"},
                    {"tag": "text", "text": f"  {j.score_label}({j.score:.0f}分)"},
                    {"tag": "text", "text": f"\n🔗 {j.url}"},
                ]
            )
        return blocks

    # 合并所有块
    all_blocks: list[list] = content["zh_cn"]["content"]
    if strong:
        all_blocks.extend(job_blocks(strong, "🔥 强匹配"))
    if medium:
        all_blocks.extend(job_blocks(medium, "✅ 中匹配"))
    if other:
        all_blocks.extend(job_blocks(other[:5], "⚪ 其他"))

    # footer
    all_blocks.append(
        [{"tag": "text", "text": f"\n— 由 JobHunting Bot 自动推送 | {len(jobs)} 个职位"}]
    )

    ok = _send_message(token, chat_id, content)
    if ok:
        logger.info(f"[Feishu] 推送成功：{len(jobs)} 个职位")
    else:
        logger.warning("[Feishu] 推送失败")
    return ok


def feishu_notify_text(
    title: str,
    body: str,
    app_id: str,
    app_secret: str,
    chat_id: str,
) -> bool:
    """发送纯文本消息（用于错误告警）"""
    if not (app_id and app_secret and chat_id):
        return False
    token = _get_token(app_id, app_secret)
    if not token:
        return False
    content = {
        "zh_cn": {
            "title": title,
            "content": [[{"tag": "text", "text": body}]],
        }
    }
    return _send_message(token, chat_id, content)
