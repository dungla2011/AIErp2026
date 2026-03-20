"""
Telegram Bot MVP với Claude API + Function Calling
"""
import sys
# Fix UTF-8 encoding on Windows terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
from database import UsageStatsDB, ConversationDB, init_database, get_role_label
from skills import TOOLS, process_tool_call

# Debug: Print current working directory
print("="*60)
print("🔍 DEBUG - bot.py initialization")
print(f"📁 Current working directory: {os.getcwd()}")
print(f"📄 bot.py location: {Path(__file__).parent}")

# Load environment variables
env_path = Path(__file__).parent / '.env'
print(f"🔧 Looking for .env at: {env_path}")
print(f"✓ .env exists: {env_path.exists()}")

if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        print("📝 .env file contents (first 3 lines):")
        for i, line in enumerate(f):
            if i < 3:
                print(f"   {line.rstrip()}")

load_dotenv(dotenv_path=env_path, override=True)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Anthropic client with API key from environment
api_key = os.getenv("ANTHROPIC_API_KEY")
print(f"🔑 API Key from os.getenv: {api_key[:30] if api_key else 'None'}...{api_key[-10:] if api_key and len(api_key) > 40 else ''}")
print(f"📏 Key length: {len(api_key) if api_key else 0}")

if not api_key:
    raise ValueError("❌ ANTHROPIC_API_KEY not found in .env file!")

print(f"✅ Creating Anthropic client with key...")
client = Anthropic(api_key=api_key)
print(f"✅ Anthropic client created successfully")

# Initialize database
init_database()

# Get Claude model from environment
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
BASE_PROMPT = os.getenv("BASE_PROMPT", "Bạn là chatbot bán hàng thông minh. Trả lời tiếng Việt, thân thiện, hữu ích.")
print(f"🤖 Claude Model: {CLAUDE_MODEL}")
print("="*60)

# Main bot function
def build_system_prompt(user_memory: str = "", retrieved_context: str = "",
                        user_role: str = "customer",
                        restricted_access: bool = False,
                        topic: str = "business") -> str:
    base = BASE_PROMPT

    # Fetch display name from DB (roles.name) — no hardcoding
    role_label = get_role_label(user_role)

    # ── Topic guidance ───────────────────────────────────────────────────
    if topic == "business":
        base += (
            f"\n\n---\n## Chế độ: Số liệu Kinh doanh\n"
            f"Người dùng muốn hỏi về: đơn hàng, doanh thu, thống kê, hiệu suất bán hàng.\n"
            f"TỰ ĐỘNG gọi các tools: get_orders, query_invoices, get_invoice_stats\n"
            f"để truy vấn SQL Server. KHÔNG dùng RAG tài liệu."
        )
    else:  # topic == "documents"
        base += (
            f"\n\n---\n## Chế độ: Tài liệu\n"
            f"Người dùng muốn hỏi về: hướng dẫn, quy định, chứng chỉ, chính sách.\n"
            f"Dùng thông tin từ tài liệu đã được tải (RAG context bên dưới).\n"
            f"KHÔNG cần gọi tools SQL để trả lời."
        )

    # ── Role boundary (always injected — label comes from DB) ───────────
    base += (
        f"\n\n---\n## Vai trò hiện tại\n"
        f"Bạn đang phục vụ người dùng với vai trò **{role_label}**. "
        f"Chỉ cung cấp thông tin phù hợp với quyền hạn của vai trò này."
    )

    # ── Long-term memory ─────────────────────────────────────────────────
    if user_memory:
        base += f"\n\n---\n## Thông tin người dùng này (từ các cuộc trò chuyện trước)\n{user_memory}"

    # ── RAG context ────────────────────────────────────────────────
    if retrieved_context:
        base += (
            f"\n\n---\n{retrieved_context}"
            f"\n\nHãy trả lời CHỈ dựa trên tài liệu tham khảo ở trên. "
            f"Nếu không tìm thấy thông tin, hãy nói rõ 'Tôi không tìm thấy thông tin này trong tài liệu.'"
        )
    elif restricted_access:
        # Role has a limited category whitelist but no matching docs found—
        # explicitly forbid Claude from answering from general knowledge or conversation history.
        base += (
            f"\n\n---\n## Không có tài liệu phù hợp\n"
            f"Không có tài liệu nào trong phạm vi quyền hạn của vai trò **{role_label}** "
            f"có liên quan đến câu hỏi này. "
            f"TUYỆT ĐỐI KHÔNG trả lời dựa trên kiến thức chung, lịch sử trò chuyện, hay bất kỳ nguồn nào khác. "
            f"Hãy trả lời: 'Xin lỗi, tôi không có thông tin này trong tài liệu dành cho {role_label}.'"
        )

    return base


def chat_with_claude(user_message, conversation_history=None, conversation_id=None,
                     user_memory: str = "", retrieved_context: str = "",
                     user_role: str = "customer", restricted_access: bool = False,
                     topic: str = "business"):
    """
    Chat với Claude, tự động gọi tools khi cần
    """
    if conversation_history is None:
        conversation_history = []
    
    # Add user message
    conversation_history.append({
        "role": "user",
        "content": user_message
    })
    
    # System prompt with injected user memory
    system_prompt = build_system_prompt(user_memory, retrieved_context, user_role, restricted_access, topic)

    # Accumulate token usage across all API calls (incl. tool-use rounds)
    _total_input = 0
    _total_output = 0

    # Call Claude with tools
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=system_prompt,
        tools=TOOLS,
        messages=conversation_history
    )
    
    # Track usage
    if hasattr(response, 'usage'):
        _total_input += response.usage.input_tokens
        _total_output += response.usage.output_tokens
        UsageStatsDB.log_request(
            model=CLAUDE_MODEL,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            conversation_id=conversation_id
        )
    
    # Process response
    while response.stop_reason == "tool_use":
        # Find tool use block
        tool_use_block = None
        for block in response.content:
            if block.type == "tool_use":
                tool_use_block = block
                break
        
        if not tool_use_block:
            break
        
        # Execute tool
        tool_result = process_tool_call(
            tool_use_block.name,
            tool_use_block.input,
            user_role=user_role
        )
        
        # Log SQL query to messages if tool_result contains debug info
        if tool_use_block.name in ["query_invoices", "get_orders"] and isinstance(tool_result, dict):
            sql_debug = tool_result.get("_debug") or tool_result.get("sql")
            if sql_debug:
                # Save SQL query as debug message (no user_id needed for debug logs)
                try:
                    ConversationDB.add_message(
                        conversation_id,
                        content=f"🔍 [SQL Query]\n```sql\n{sql_debug}\n```",
                        sender='bot',
                        user_id=None
                    )
                except Exception as e:
                    print(f"   ⚠️ Failed to log SQL: {e}")
            # Remove debug fields before sending to Claude
            tool_result.pop("_debug", None)
            tool_result.pop("_sql", None)
        
        # Add assistant response and tool result to history
        conversation_history.append({
            "role": "assistant",
            "content": response.content
        })
        
        conversation_history.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_block.id,
                    "content": json.dumps(tool_result)
                }
            ]
        })
        
        # Get next response
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system_prompt,
            tools=TOOLS,
            messages=conversation_history
        )
        
        # Track usage for follow-up
        if hasattr(response, 'usage'):
            _total_input += response.usage.input_tokens
            _total_output += response.usage.output_tokens
            UsageStatsDB.log_request(
                model=CLAUDE_MODEL,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                conversation_id=conversation_id
            )
    
    # Extract final text response
    final_response = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_response = block.text
            break
    
    # Add final response to history
    conversation_history.append({
        "role": "assistant",
        "content": final_response
    })

    # Build usage summary for this full exchange (all tool-use rounds combined)
    _pricing = UsageStatsDB.PRICING.get(CLAUDE_MODEL, {"input": 3.0, "output": 15.0})
    _cost = (_total_input * _pricing["input"] + _total_output * _pricing["output"]) / 1_000_000
    usage = {"input_tokens": _total_input, "output_tokens": _total_output, "cost_usd": round(_cost, 6)}

    return final_response, conversation_history, usage


if __name__ == "__main__":
    # Test
    print("Bot MVP - Claude + Function Calling")
    history = None
    
    while True:
        user_input = input("\nBạn: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit"]:
            break
        
        response, history = chat_with_claude(user_input, history)
        print(f"\nBot: {response}")
