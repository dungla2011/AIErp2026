"""
User Memory — Long-term per-user memory via incremental summarization.

Flow:
  At end of conversation (or every SUMMARIZE_EVERY turns):
    old_memory + new_conversation → Claude Haiku → new_memory
    → saved to user_memory table
  
  At start of conversation:
    Load memory → inject into system prompt
"""

import asyncio
import json
import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
from database import UserMemoryDB, UsageStatsDB, get_db

load_dotenv(dotenv_path=Path(__file__).parent / '.env', override=True)

# Use cheap Haiku for summarization — enough for this task
SUMMARIZE_MODEL = os.getenv("MEMORY_MODEL", "claude-3-haiku-20240307")

# Trigger summarize after this many messages in conversation (user+bot = 2 per turn)
SUMMARIZE_EVERY = 6   # trigger every 6 user turns

_client: Optional[Anthropic] = None

def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")) 
    return _client


MEMORY_SUMMARIZER_PROMPT = """Bạn là hệ thống quản lý bộ nhớ dài hạn cho AI assistant bán hàng.

Nhiệm vụ: Đọc [Bộ nhớ cũ] và [Conversation mới], tạo ra [Bộ nhớ mới] đã được merge và cập nhật.

Quy tắc:
- Giữ tối đa 400 từ
- Ưu tiên: thông tin kinh doanh, thói quen hỏi, sở thích giao tiếp
- Xóa thông tin lỗi thời nếu có update mới thay thế
- Viết dạng bullet points ngắn gọn, tiếng Việt
- KHÔNG giải thích, KHÔNG thêm lời mở đầu/kết thúc

Chỉ trả về nội dung theo format:
## Thông tin cơ bản
- ...

## Nghiệp vụ / Business context
- ...

## Thói quen & sở thích
- ...

## Ghi chú khác
- ..."""


def _do_summarize(user_id: str, conversation: list[dict]) -> None:
    """
    Synchronous summarize — runs in a thread via asyncio.to_thread().
    conversation = list of {"role": "user"|"assistant", "content": str}
    """
    if not user_id or not conversation:
        return

    # Filter to simple text messages only (skip tool_use / tool_result blocks)
    def to_text(msg: dict) -> Optional[str]:
        content = msg.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
            return " ".join(parts).strip() or None
        return None

    lines = []
    for msg in conversation:
        text = to_text(msg)
        if text:
            role_label = "USER" if msg["role"] == "user" else "BOT"
            lines.append(f"{role_label}: {text}")

    if not lines:
        return

    conv_text = "\n".join(lines)
    old_memory = UserMemoryDB.get_memory(user_id) or "(chưa có bộ nhớ)"

    prompt_content = (
        f"## Bộ nhớ cũ\n{old_memory}\n\n"
        f"## Conversation mới\n{conv_text}"
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model=SUMMARIZE_MODEL,
            max_tokens=600,
            system=MEMORY_SUMMARIZER_PROMPT,
            messages=[{"role": "user", "content": prompt_content}]
        )

        new_memory = response.content[0].text.strip()

        # Log token usage (don't miss cost tracking)
        if hasattr(response, "usage"):
            UsageStatsDB.log_request(
                model=SUMMARIZE_MODEL,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        UserMemoryDB.upsert_memory(user_id, new_memory)
        print(f"🧠 Memory summarized for {user_id[:8]}... ({len(new_memory)} chars)")

    except Exception as e:
        print(f"⚠️ Memory summarize failed for {user_id[:8]}...: {e}")


async def update_user_memory_async(user_id: str, conversation: list[dict]) -> None:
    """
    Async wrapper — runs _do_summarize in a thread pool so it doesn't block.
    Call with asyncio.create_task() from the /chat endpoint.
    """
    await asyncio.to_thread(_do_summarize, user_id, conversation)


def should_summarize(user_id: int) -> bool:
    """
    Return True when it's time to update memory for this user.
    Triggers at every SUMMARIZE_EVERY user messages (6, 12, 18...).
    Also triggers once as catch-up if count >= SUMMARIZE_EVERY but no memory saved yet.
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()
            row = cur.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE user_id=? AND sender='user'",
                (user_id,)
            ).fetchone()
            cnt = row["cnt"] if row else 0
            if cnt < SUMMARIZE_EVERY:
                return False
            # Normal trigger: exact multiple
            if cnt % SUMMARIZE_EVERY == 0:
                return True
            # Catch-up: past threshold but no memory saved yet
            has_memory = cur.execute(
                "SELECT 1 FROM user_memory WHERE user_id=?", (str(user_id),)
            ).fetchone()
            return has_memory is None
    except Exception:
        return False
