"""
FastAPI server để expose bot MVP thành API
"""
import sys
# Fix UTF-8 encoding on Windows terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
import os
from pathlib import Path
from dotenv import load_dotenv

# Debug: Print api.py initialization
print("="*60)
print("🔍 DEBUG - api.py initialization")
print(f"📁 Current working directory: {os.getcwd()}")
print(f"📄 api.py location: {Path(__file__).parent}")

# Load environment variables FIRST before importing bot
env_path = Path(__file__).parent / '.env'
print(f"🔧 Loading .env from: {env_path}")
print(f"✓ .env exists: {env_path.exists()}")
load_dotenv(dotenv_path=env_path, override=True)

api_key_check = os.getenv("ANTHROPIC_API_KEY")
print(f"🔑 API Key in api.py: {api_key_check[:30] if api_key_check else 'None'}...{api_key_check[-10:] if api_key_check and len(api_key_check) > 40 else ''}")
print("="*60)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uuid
import logging
from datetime import datetime
from pathlib import Path
from bot import chat_with_claude, build_system_prompt
from database import UsageStatsDB, ConversationDB, UserMemoryDB, init_database, get_db, get_user_by_id, get_role_label
from memory import update_user_memory_async, should_summarize
from docs_api import router as docs_router
from rag import retrieve as rag_retrieve, format_context, get_allowed_categories
from auth import verify_password, AUTH_PASSWORD_MD5

# Initialize chat log file
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
CHAT_LOG_FILE = LOGS_DIR / "chats.log"

def get_client_ip(request):
    """Extract client IP from request (handles proxies)"""
    if request.client:
        return request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return "unknown"

def log_chat_exchange(request, conv_id: str, user_id: Optional[int], role: str, channel: str,
                      user_message: str, system_prompt: str, bot_response: str,
                      input_tokens: Optional[int], output_tokens: Optional[int], cost_usd: Optional[float],
                      sql_queries: Optional[list] = None):
    """Log chat exchange to chats.log file"""
    try:
        client_ip = get_client_ip(request)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format SQL queries section from the list passed from AI execution
        sql_section = ""
        if sql_queries:
            sql_text = "\n".join(sql_queries)
            sql_section = f"""
{'─'*80}
[SQL QUERIES EXECUTED]
{'─'*80}
{sql_text}

"""
        
        log_entry = f"""
{'='*80}
[{timestamp}] 🔹 CHAT EXCHANGE
{'='*80}
📍 Client IP: {client_ip}
🆔 Conversation ID: {conv_id}
👤 User ID: {user_id or 'N/A'}
🎭 Role: {role}
📊 Channel: {channel}

{'─'*80}
[USER MESSAGE]
{'─'*80}
{user_message}

{'─'*80}
[SYSTEM PROMPT]
{'─'*80}
{system_prompt}

{'─'*80}
[BOT RESPONSE]
{'─'*80}
{bot_response}

{sql_section}{'─'*80}
[TOKENS & COST]
{'─'*80}
💬 Input Tokens: {input_tokens or '—'}
📤 Output Tokens: {output_tokens or '—'}
💰 Cost (USD): ${(cost_usd if cost_usd is not None else 0):.6f}

"""
        
        with open(CHAT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
        
        print(f"   ✅ Chat logged to {CHAT_LOG_FILE}")
    except Exception as e:
        print(f"   ⚠️ Failed to log chat: {e}")


app = FastAPI(title="Bot MVP API", version="1.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global error handler — ensures CORS headers are present even on unhandled 500s
from fastapi.responses import JSONResponse
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"},
    )

# Add request logging middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class AuthMiddleware(BaseHTTPMiddleware):
    """Check authentication token on all endpoints except /login and /health"""
    async def dispatch(self, request: Request, call_next):
        # Endpoints that don't require auth
        public_paths = ["/login", "/health", "/docs", "/openapi.json"]
        
        # Allow OPTIONS requests (CORS preflight) without auth
        if request.method == "OPTIONS" or request.url.path in public_paths:
            return await call_next(request)
        
        # Get token from Authorization header or query param
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = request.query_params.get("token")
        
        # Check token
        if token != AUTH_PASSWORD_MD5:
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized. Invalid or missing token."},
                headers={"Access-Control-Allow-Origin": "*"},
            )
        
        return await call_next(request)

app.add_middleware(AuthMiddleware)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        print(f"\n📨 [API] {request.method} {request.url.path}")
        response = await call_next(request)
        print(f"   ↳ Status: {response.status_code}")
        return response

app.add_middleware(LoggingMiddleware)

# Include routers
app.include_router(docs_router)

# Store conversations in memory (in production use database)
conversations = {}

# Models
class Message(BaseModel):
    content: str

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    user_id: Optional[int] = None        # DB user id (integer)
    user_role: Optional[str] = "customer" # customer | staff | admin
    category_hint: Optional[str] = None   # which doc category to search (optional)
    topic: Optional[str] = "business"      # "business" (SQL) or "documents" (RAG)

class ChatResponse(BaseModel):
    conversation_id: str
    user_message: str
    bot_response: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    timestamp: str

class LoginRequest(BaseModel):
    password: str

class LoginResponse(BaseModel):
    token: str
    message: str

# Routes

@app.post("/login")
def login(request: LoginRequest):
    """
    Authenticate with password and get API token
    
    Request:
    ```json
    {"password": "your_password"}
    ```
    
    Response:
    ```json
    {"token": "md5_hash_of_password", "message": "Login successful"}
    ```
    
    Use token in subsequent requests:
    - Header: Authorization: Bearer <token>
    - Query param: ?token=<token>
    """
    if verify_password(request.password):
        return LoginResponse(
            token=AUTH_PASSWORD_MD5,
            message="Login successful. Use this token in Authorization header or ?token= query param"
        )
    raise HTTPException(status_code=401, detail="Invalid password")
@app.get("/health")
def health_check():
    """Health check endpoint"""
    print("\n🔍 [API] GET /health called")
    print("   ✅ API is alive\n")
    return {"status": "ok"}

@app.get("/stats")
def get_stats():
    """Get usage statistics and cost"""
    return UsageStatsDB.get_stats()

@app.delete("/stats")
def reset_stats():
    """Reset usage statistics"""
    UsageStatsDB.reset_stats()
    return {"status": "reset", "message": "Statistics cleared"}

@app.post("/chat")
async def chat(request: ChatRequest, http_request: Request):
    """
    Chat with bot via API
    
    - If conversation_id is provided, continue existing conversation
    - Otherwise create new conversation
    - user_id enables long-term memory across conversations
    """
    print(f"\n🔍 [API] POST /chat called")
    print(f"   Message: {request.message[:50]}...")
    print(f"   Conv ID: {request.conversation_id}")
    print(f"   User ID: {request.user_id}")
    print(f"   Topic: {request.topic or 'business'}")
    
    try:
        # Get or create conversation
        conv_id = request.conversation_id or str(uuid.uuid4())
        history = conversations.get(conv_id, None)
        
        # Create conversation in DB if new
        if conv_id not in conversations:
            print(f"   ✅ Creating new conversation: {conv_id}")
            ConversationDB.create_conversation(conv_id, platform="web", user_id=request.user_id)
        
        import asyncio

        # ── Resolve authoritative role from DB ──────────────────────────
        # If user_id matches a row in the users table, trust DB role_id.
        # This prevents frontend from spoofing a higher-privilege role.
        effective_role = request.user_role or "customer"
        db_user = get_user_by_id(request.user_id) if request.user_id else None
        if db_user:
            effective_role = db_user["role_id"]
            print(f"   👤 Role from DB: '{effective_role}' (user: {db_user['username']})")
        else:
            print(f"   👤 Role from request (browser session): '{effective_role}'")

        # ── Long-term memory ─────────────────────────────────────────────
        user_memory = ""
        if request.user_id:
            user_memory = UserMemoryDB.get_memory(str(request.user_id)) or ""
            if user_memory:
                print(f"   🧠 Memory loaded ({len(user_memory)} chars) for user_id={request.user_id}")
            else:
                print(f"   🧠 No memory yet for user_id={request.user_id}")

        # RAG: retrieve relevant document chunks (based on user role + optional category)
        # ONLY if topic is "documents", skip for "business" topic
        retrieved_context = ""
        restricted_access = False   # True when role has a limited category whitelist
        
        topic = request.topic or "business"
        print(f"   📋 Processing topic: {topic}")
        
        if topic == "documents":
            # RAG mode - retrieve from documents
            try:
                allowed = await asyncio.to_thread(get_allowed_categories, effective_role)
                restricted_access = (allowed is not None)  # None = unrestricted (all categories)
                chunks = await asyncio.to_thread(
                    rag_retrieve, request.message,
                    effective_role,
                    5,   # top_k
                    0.30, # min_score
                    request.category_hint,
                )
                if chunks:
                    retrieved_context = format_context(chunks)
                    print(f"   📚 RAG: {len(chunks)} chunks retrieved (top score: {chunks[0]['score']}, role={effective_role}, restricted={restricted_access})")
                else:
                    print(f"   📚 RAG: 0 chunks (role={effective_role}, restricted={restricted_access}, no relevant docs in allowed categories)")
            except Exception as e:
                print(f"   ⚠️ RAG retrieval failed (non-blocking): {e}")
        else:
            # Business data mode - no RAG, will use SQL tools
            print(f"   📊 Business mode: skipping RAG, will use SQL tools for data")
        
        # Build system prompt for reference
        system_prompt = build_system_prompt(user_memory, retrieved_context, effective_role, restricted_access, topic)
        
        # Save user message to DB
        _db_uid = db_user["id"] if db_user else None
        ConversationDB.add_message(conv_id, content=request.message, sender='user', user_id=_db_uid, channel=topic)
        
        # Get bot response (run sync function in thread to not block event loop)
        bot_response, history, usage, sql_queries = await asyncio.to_thread(
            chat_with_claude, request.message, history, conv_id,
            user_memory, retrieved_context, effective_role, restricted_access, topic
        )

        # Save bot response to DB — user_id same as the user being served so history filters work
        ConversationDB.add_message(
            conv_id, content=bot_response, sender='bot',
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cost_usd=usage.get("cost_usd"),
            user_id=_db_uid,
            prompt=system_prompt,  # Save the system prompt for reference
            channel=topic,  # Save the topic/channel selected
        )
        
        # Store conversation in memory (for backward compatibility)
        conversations[conv_id] = history
        
        # Trigger async memory update in background (non-blocking)
        # Use DB message count per user_id instead of in-memory history length
        if _db_uid and should_summarize(_db_uid):
            print(f"   🧠 Scheduling memory update for user_id={_db_uid}...")
            asyncio.create_task(update_user_memory_async(str(_db_uid), history))
        
        # Log chat exchange to file
        log_chat_exchange(
            http_request,
            conv_id=conv_id,
            user_id=request.user_id,
            role=effective_role,
            channel=topic,
            user_message=request.message,
            system_prompt=system_prompt,
            bot_response=bot_response,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cost_usd=usage.get("cost_usd"),
            sql_queries=sql_queries
        )
        
        from utils import now_local
        print(f"   🤖 Bot: {bot_response[:100]}{'...' if len(bot_response) > 100 else ''}")
        print(f"   ✅ Chat response saved | {usage.get('input_tokens',0)}in+{usage.get('output_tokens',0)}out = ${usage.get('cost_usd',0):.5f}\n")
        return ChatResponse(
            conversation_id=conv_id,
            user_message=request.message,
            bot_response=bot_response,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cost_usd=usage.get("cost_usd"),
            timestamp=now_local().isoformat()
        )
    
    except Exception as e:
        print(f"   ❌ Error: {e}\n")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memory/{user_id}")
def get_user_memory(user_id: str):
    """Get current long-term memory for a user (for debugging)"""
    memory = UserMemoryDB.get_memory(user_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="No memory found for this user")
    return {"user_id": user_id, "memory": memory}

@app.delete("/memory/{user_id}")
def clear_user_memory(user_id: str):
    """Clear memory for a user"""
    UserMemoryDB.upsert_memory(user_id, "")
    return {"status": "cleared", "user_id": user_id}

@app.get("/conversations/latest")
def get_latest_conversation():
    """Get the most recent conversation from database"""
    print("\n🔍 [API] GET /conversations/latest called")
    conversations_list = ConversationDB.get_all_conversations(limit=1)
    print(f"   Found {len(conversations_list)} conversation(s)")
    
    if not conversations_list:
        print("   ❌ No conversations found!")
        raise HTTPException(status_code=404, detail="No conversations found")
    
    latest_conv = conversations_list[0]
    conversation_id = latest_conv["conversation_id"]
    print(f"   ✅ Latest conversation: {conversation_id}")
    
    # Get full history
    history = ConversationDB.get_conversation_history(conversation_id, limit=100)
    print(f"   📝 History has {len(history)} message(s)")
    
    # Convert to format expected by frontend
    formatted_history = [
        {"role": msg["role"], "content": msg["content"], "timestamp": msg["created_at"]}
        for msg in history
    ]
    
    print(f"   ✅ Returning conversation {conversation_id} with {len(formatted_history)} messages\n")
    return {"conversation_id": conversation_id, "history": formatted_history}

@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    """Get conversation history from database. Returns empty history if not found (no 404)."""
    history = ConversationDB.get_conversation_history(conversation_id, limit=100)
    
    # Convert to format expected by frontend (empty list if not found)
    formatted_history = [
        {"role": msg["role"], "content": msg["content"], "timestamp": msg["created_at"]}
        for msg in history
    ] if history else []
    
    return {"conversation_id": conversation_id, "history": formatted_history}

@app.get("/messages/user/{user_id}")
def get_messages_by_user(user_id: int, limit: int = 200):
    """Return all messages (user + bot) for a given user_id, oldest first.
    Also returns the latest conversation_id so the frontend can continue that conversation.
    """
    with get_db() as conn:
        rows = conn.cursor().execute("""
            SELECT sender, content, created_at, conversation_id
            FROM messages
            WHERE user_id = ?
            ORDER BY created_at ASC
            LIMIT ?
        """, (user_id, limit)).fetchall()

    if not rows:
        return {"user_id": user_id, "conversation_id": None, "history": []}

    history = [{"role": "user" if r["sender"] == "user" else "bot",
                "content": r["content"], "created_at": r["created_at"]} for r in rows]
    latest_conv = rows[-1]["conversation_id"]
    return {"user_id": user_id, "conversation_id": latest_conv, "history": history}

@app.get("/messages")
def list_messages(page: int = 1, per_page: int = 20, role: str = None):
    """List all messages with pagination, newest first. Optionally filter by role (user/assistant).
    Role is derived: input_tokens IS NOT NULL → 'assistant', else → 'user'.
    """
    offset = (page - 1) * per_page
    if role == "assistant" or role == "bot":
        where = "WHERE m.sender = 'bot'"
    elif role == "user":
        where = "WHERE m.sender = 'user'"
    else:
        where = ""
    with get_db() as conn:
        cursor = conn.cursor()
        total = cursor.execute(
            f"SELECT COUNT(*) FROM messages m {where}"
        ).fetchone()[0]

        rows = cursor.execute(f"""
            SELECT m.id, m.sender, m.channel, m.content, m.prompt, m.input_tokens, m.output_tokens, m.cost_usd,
                   m.created_at, m.conversation_id, m.user_id
            FROM messages m
            {where}
            ORDER BY m.created_at DESC
            LIMIT ? OFFSET ?
        """, (per_page, offset)).fetchall()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
        "messages": [dict(r) for r in rows],
    }


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    """Delete a conversation"""
    if conversation_id in conversations:
        del conversations[conversation_id]
        return {"message": "Conversation deleted"}
    raise HTTPException(status_code=404, detail="Conversation not found")


# ── Orders API ──────────────────────────────────────────────────────────────

@app.get("/orders")
def get_orders(limit: int = 10):
    """Get recent orders from database"""
    try:
        with get_db() as conn:
            rows = conn.cursor().execute("""
                SELECT id, customer, amount, status, created_at, expected_delivery, delivered_at
                FROM orders
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
        
        orders = []
        for row in rows:
            orders.append({
                "id": row["id"],
                "customer": row["customer"],
                "amount": row["amount"],
                "status": row["status"],
                "created_at": row["created_at"],
                "expected_delivery": row["expected_delivery"],
                "delivered_at": row["delivered_at"]
            })
        
        return {
            "total": len(orders),
            "orders": orders
        }
    except Exception as e:
        print(f"   ❌ Error fetching orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Invoice Statistics (from SQL Server) ────────────────────────────────────

@app.get("/invoice-stats")
def get_invoice_stats(stat_type: str = "total_revenue"):
    """Get invoice statistics from SQL Server kava_pos database"""
    print(f"\n🔍 [API] GET /invoice-stats called (stat_type={stat_type})")
    
    try:
        import requests
        sql_api = "http://118.70.146.150:8888/api/public/execute"
        
        # Map stat_type to SQL query
        queries = {
            "total_revenue": "SELECT SUM(tong_tien) as total_revenue FROM kava_pos.dbo.hoa_don",
            "total_paid": "SELECT SUM(tong_tien_chuyen_khoan) as total_paid FROM kava_pos.dbo.hoa_don",
            "invoice_count": "SELECT COUNT(*) as count FROM kava_pos.dbo.hoa_don",
            "avg_invoice": "SELECT AVG(tong_tien) as avg_value FROM kava_pos.dbo.hoa_don",
            "unpaid_count": "SELECT COUNT(*) as count FROM kava_pos.dbo.hoa_don WHERE trang_thai_thanh_toan = 0",
            "unreturned_count": "SELECT COUNT(*) as count FROM kava_pos.dbo.hoa_don WHERE trang_thai_tra_hang = 0",
        }
        
        if stat_type not in queries:
            raise HTTPException(status_code=400, detail=f"Unknown stat_type: {stat_type}")
        
        sql = queries[stat_type]
        print(f"   📊 Executing: {sql[:50]}...")
        
        response = requests.post(
            sql_api,
            headers={"Content-Type": "text/plain"},
            data=sql,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Result: {result}")
            return {
                "stat_type": stat_type,
                "data": result[0] if result else {}
            }
        else:
            raise HTTPException(status_code=500, detail=f"SQL API error: {response.text}")
    
    except Exception as e:
        print(f"   ❌ Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── User / Role management ──────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    username: str
    display_name: str
    role_id: str

class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    role_id: Optional[str] = None
    is_active: Optional[int] = None

class CreateRoleRequest(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

class UpdateRoleRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class UpdateRoleCategoriesRequest(BaseModel):
    category_ids: list[str]


@app.get("/users")
def list_users():
    with get_db() as conn:
        rows = conn.cursor().execute("""
            SELECT u.id, u.username, u.display_name, u.role_id, u.is_active, u.created_at,
                   r.name AS role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            ORDER BY u.created_at ASC
        """).fetchall()
    return [dict(r) for r in rows]


@app.post("/users", status_code=201)
def create_user(req: CreateUserRequest):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, display_name, role_id) VALUES (?,?,?)",
                (req.username, req.display_name, req.role_id)
            )
            new_id = cur.lastrowid
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": new_id, "username": req.username, "display_name": req.display_name, "role_id": req.role_id}


@app.put("/users/{user_id}")
def update_user(user_id: int, req: UpdateUserRequest):
    with get_db() as conn:
        cur = conn.cursor()
        user = cur.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if req.display_name is not None:
            cur.execute("UPDATE users SET display_name=? WHERE id=?", (req.display_name, user_id))
        if req.role_id is not None:
            cur.execute("UPDATE users SET role_id=? WHERE id=?", (req.role_id, user_id))
        if req.is_active is not None:
            cur.execute("UPDATE users SET is_active=? WHERE id=?", (req.is_active, user_id))
    return {"ok": True}


@app.delete("/users/{user_id}")
def delete_user(user_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        existing = cur.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="User not found")
        cur.execute("DELETE FROM users WHERE id=?", (user_id,))
    return {"ok": True}


@app.get("/roles")
def list_roles():
    with get_db() as conn:
        cur = conn.cursor()
        rows = cur.execute("""
            SELECT r.id, r.name, r.description, r.created_at,
                   COUNT(DISTINCT u.id) AS user_count,
                   COUNT(DISTINCT rc.category_id) AS category_count
            FROM roles r
            LEFT JOIN users u ON u.role_id = r.id
            LEFT JOIN role_category_access rc ON rc.role_id = r.id
            GROUP BY r.id
            ORDER BY r.created_at ASC
        """).fetchall()
    return [dict(r) for r in rows]


@app.post("/roles", status_code=201)
def create_role(req: CreateRoleRequest):
    try:
        with get_db() as conn:
            conn.cursor().execute(
                "INSERT INTO roles (id, name, description) VALUES (?,?,?)",
                (req.id, req.name, req.description)
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": req.id, "name": req.name}


@app.put("/roles/{role_id}")
def update_role(role_id: str, req: UpdateRoleRequest):
    with get_db() as conn:
        cur = conn.cursor()
        if not cur.execute("SELECT id FROM roles WHERE id=?", (role_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Role not found")
        if req.name is not None:
            cur.execute("UPDATE roles SET name=? WHERE id=?", (req.name, role_id))
        if req.description is not None:
            cur.execute("UPDATE roles SET description=? WHERE id=?", (req.description, role_id))
    return {"ok": True}


@app.delete("/roles/{role_id}")
def delete_role(role_id: str):
    with get_db() as conn:
        cur = conn.cursor()
        if not cur.execute("SELECT id FROM roles WHERE id=?", (role_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Role not found")
        user_count = cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE role_id=?", (role_id,)).fetchone()["cnt"]
        if user_count > 0:
            raise HTTPException(status_code=400, detail=f"Cannot delete: {user_count} user(s) still assigned to this role")
        cur.execute("DELETE FROM role_category_access WHERE role_id=?", (role_id,))
        cur.execute("DELETE FROM roles WHERE id=?", (role_id,))
    return {"ok": True}


@app.get("/roles/{role_id}/categories")
def get_role_categories(role_id: str):
    with get_db() as conn:
        rows = conn.cursor().execute(
            "SELECT category_id FROM role_category_access WHERE role_id=?", (role_id,)
        ).fetchall()
    return [r["category_id"] for r in rows]


@app.put("/roles/{role_id}/categories")
def set_role_categories(role_id: str, req: UpdateRoleCategoriesRequest):
    with get_db() as conn:
        cur = conn.cursor()
        if not cur.execute("SELECT id FROM roles WHERE id=?", (role_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Role not found")
        cur.execute("DELETE FROM role_category_access WHERE role_id=?", (role_id,))
        for cat_id in req.category_ids:
            cur.execute(
                "INSERT OR IGNORE INTO role_category_access (role_id, category_id) VALUES (?,?)",
                (role_id, cat_id)
            )
    return {"ok": True, "assigned": req.category_ids}


@app.get("/categories")
def list_categories():
    with get_db() as conn:
        rows = conn.cursor().execute(
            "SELECT id, name, is_public, description FROM doc_categories ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Database CRUD Management (Admin Only) ─────────────────────────────────
class DBRecord(BaseModel):
    table: str
    data: dict

@app.get("/db/tables")
def get_database_tables():
    """List all tables in bot_data.db SQLite
    
    Note: This API only manages SQLite (bot_data.db).
    SQL Server tables (kava_pos.dbo.*) are managed separately via /invoice-stats and /orders endpoints.
    """
    try:
        with get_db() as conn:
            tables = conn.cursor().execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        result = {"tables": [t["name"] for t in tables]}
        result["note"] = "SQLite tables only. SQL Server tables: /orders, /invoice-stats"
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/db/{table_name}")
def get_table_data(table_name: str, limit: int = 100, offset: int = 0):
    """Get records from a table with pagination"""
    try:
        # Dynamically check if table exists (no hardcoded whitelist)
        with get_db() as conn:
            table_check = conn.cursor().execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            ).fetchone()
            
            if not table_check:
                raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found in SQLite")
            
            # Get column info
            cols = conn.cursor().execute(f"PRAGMA table_info({table_name})").fetchall()
            columns = [c["name"] for c in cols]
            
            # Get total count
            count_result = conn.cursor().execute(f"SELECT COUNT(*) AS cnt FROM {table_name}").fetchone()
            total = count_result["cnt"] if count_result else 0
            
            # Get paginated data
            rows = conn.cursor().execute(
                f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        
        # Convert rows to dicts, handling encoding issues
        def safe_convert(value):
            """Convert value safely, handling encoding issues & binary data"""
            if isinstance(value, bytes):
                try:
                    return value.decode('utf-8')
                except UnicodeDecodeError:
                    # Binary data - convert to hex
                    hex_str = value.hex()
                    if len(hex_str) > 100:
                        return f"0x{hex_str[:100]}... ({len(value)} bytes)"
                    return f"0x{hex_str}"
            return value
        
        safe_rows = []
        for row in rows:
            row_dict = dict(row)
            safe_rows.append({k: safe_convert(v) for k, v in row_dict.items()})
        
        return {
            "table": table_name,
            "columns": columns,
            "total": total,
            "limit": limit,
            "offset": offset,
            "rows": safe_rows
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/db/{table_name}/count")
def get_table_count(table_name: str):
    """Get total record count for a table"""
    try:
        with get_db() as conn:
            # Check if table exists dynamically
            table_check = conn.cursor().execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            ).fetchone()
            
            if not table_check:
                raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
            
            result = conn.cursor().execute(f"SELECT COUNT(*) AS cnt FROM {table_name}").fetchone()
        
        return {"table": table_name, "count": result["cnt"] if result else 0}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/db/{table_name}")
def insert_record(table_name: str, record: dict):
    """Insert a new record into a table"""
    try:
        with get_db() as conn:
            # Check if table exists dynamically
            table_check = conn.cursor().execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            ).fetchone()
            
            if not table_check:
                raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
            
            # Get columns
            cols = conn.cursor().execute(f"PRAGMA table_info({table_name})").fetchall()
            column_names = [c["name"] for c in cols]
            
            # Filter record to only include valid columns
            filtered_record = {k: v for k, v in record.items() if k in column_names}
            
            if not filtered_record:
                raise HTTPException(status_code=400, detail="No valid fields provided")
            
            # Build INSERT query
            keys = list(filtered_record.keys())
            values = list(filtered_record.values())
            placeholders = ",".join(["?" for _ in keys])
            
            conn.cursor().execute(
                f"INSERT INTO {table_name} ({','.join(keys)}) VALUES ({placeholders})",
                values
            )
        
        return {"ok": True, "message": f"Record inserted into {table_name}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/db/{table_name}/{record_id}")
def update_record(table_name: str, record_id: str, updates: dict):
    """Update a record in a table"""
    try:
        with get_db() as conn:
            # Check if table exists dynamically
            table_check = conn.cursor().execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            ).fetchone()
            
            if not table_check:
                raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
            
            # Get columns
            cols = conn.cursor().execute(f"PRAGMA table_info({table_name})").fetchall()
            column_names = [c["name"] for c in cols]
            
            # Filter updates to only include valid columns
            filtered_updates = {k: v for k, v in updates.items() if k in column_names and k != "id"}
            
            if not filtered_updates:
                raise HTTPException(status_code=400, detail="No valid fields to update")
            
            # Build UPDATE query
            set_clause = ",".join([f"{k}=?" for k in filtered_updates.keys()])
            values = list(filtered_updates.values()) + [record_id]
            
            result = conn.cursor().execute(
                f"UPDATE {table_name} SET {set_clause} WHERE id=?",
                values
            )
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Record not found in {table_name}")
        
        return {"ok": True, "message": f"Record updated in {table_name}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/db/{table_name}/{record_id}")
def delete_record(table_name: str, record_id: str):
    """Delete a record from a table"""
    try:
        with get_db() as conn:
            # Check if table exists dynamically
            table_check = conn.cursor().execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            ).fetchone()
            
            if not table_check:
                raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
            
            result = conn.cursor().execute(
                f"DELETE FROM {table_name} WHERE id=?",
                (record_id,)
            )
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Record not found in {table_name}")
        
        return {"ok": True, "message": f"Record deleted from {table_name}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/db/{table_name}/truncate")
def truncate_table(table_name: str, confirm: bool = False):
    """Delete all records from a table (requires confirm=true)"""
    try:
        if not confirm:
            raise HTTPException(status_code=400, detail="Must pass confirm=true to truncate table")
        
        with get_db() as conn:
            # Check if table exists dynamically
            table_check = conn.cursor().execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            ).fetchone()
            
            if not table_check:
                raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
            
            # Protect certain tables
            protected_tables = ["conversations", "messages", "usage_stats", "user_memory"]
            if table_name in protected_tables:
                raise HTTPException(status_code=403, detail=f"Cannot truncate {table_name} - protected table")
            
            conn.cursor().execute(f"DELETE FROM {table_name}")
        
        return {"ok": True, "message": f"All records deleted from {table_name}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs/chats")
def get_chat_logs(chars: int = 10000):
    """Get last N characters from chats.log (default 10k)"""
    try:
        if not CHAT_LOG_FILE.exists():
            return {"logs": "", "total_size": 0, "returned_size": 0}
        
        # Get file size
        total_size = CHAT_LOG_FILE.stat().st_size
        
        # Read last N characters
        with open(CHAT_LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
            if total_size > chars:
                f.seek(total_size - chars)
            logs = f.read()
        
        return {
            "logs": logs,
            "total_size": total_size,
            "returned_size": len(logs),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "logs": f"Error reading logs: {str(e)}",
            "total_size": 0,
            "returned_size": 0,
            "error": str(e)
        }


@app.get("/")
def root():
    """API Info"""
    return {
        "name": "Bot MVP API",
        "version": "1.0",
        "endpoints": {
            "chat": "POST /chat",
            "get_conversation": "GET /conversations/{conversation_id}",
            "delete_conversation": "DELETE /conversations/{conversation_id}",
            "health": "GET /health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    # Get config from .env
    api_host = os.getenv("API_HOST", "0.0.0.0")
    api_port = int(os.getenv("API_PORT", "8000"))
    api_url = os.getenv("API_URL", "http://localhost:8000")
    
    print(f"\n{'='*50}")
    print(f"🚀 Bot MVP API Server")
    print(f"{'='*50}")
    print(f"📍 API URL: {api_url}")
    print(f"🔧 Host: {api_host}")
    print(f"🔌 Port: {api_port}")
    print(f"\n📚 Docs: http://localhost:{api_port}/docs")
    print(f"{'='*50}\n")
    
    uvicorn.run(app, host=api_host, port=api_port)
