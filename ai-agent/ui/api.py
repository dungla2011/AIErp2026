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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uuid
from bot import chat_with_claude
from database import UsageStatsDB, ConversationDB, UserMemoryDB, init_database, get_db, get_user_by_id, get_role_label
from memory import update_user_memory_async, should_summarize
from docs_api import router as docs_router
from rag import retrieve as rag_retrieve, format_context, get_allowed_categories

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

class ChatResponse(BaseModel):
    conversation_id: str
    user_message: str
    bot_response: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    timestamp: str

# Routes
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
async def chat(request: ChatRequest):
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
        retrieved_context = ""
        restricted_access = False   # True when role has a limited category whitelist
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
        
        # Save user message to DB
        _db_uid = db_user["id"] if db_user else None
        ConversationDB.add_message(conv_id, content=request.message, sender='user', user_id=_db_uid)
        
        # Get bot response (run sync function in thread to not block event loop)
        bot_response, history, usage = await asyncio.to_thread(
            chat_with_claude, request.message, history, conv_id,
            user_memory, retrieved_context, effective_role, restricted_access
        )

        # Save bot response to DB — user_id same as the user being served so history filters work
        ConversationDB.add_message(
            conv_id, content=bot_response, sender='bot',
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cost_usd=usage.get("cost_usd"),
            user_id=_db_uid,
        )
        
        # Store conversation in memory (for backward compatibility)
        conversations[conv_id] = history
        
        # Trigger async memory update in background (non-blocking)
        # Use DB message count per user_id instead of in-memory history length
        if _db_uid and should_summarize(_db_uid):
            print(f"   🧠 Scheduling memory update for user_id={_db_uid}...")
            asyncio.create_task(update_user_memory_async(str(_db_uid), history))
        
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
    """Get conversation history from database"""
    history = ConversationDB.get_conversation_history(conversation_id, limit=100)
    
    if not history:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Convert to format expected by frontend
    formatted_history = [
        {"role": msg["role"], "content": msg["content"], "timestamp": msg["created_at"]}
        for msg in history
    ]
    
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
            SELECT m.id, m.sender, m.content, m.input_tokens, m.output_tokens, m.cost_usd,
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
