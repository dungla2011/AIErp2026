"""
SQLite Database Manager for Bot MVP
Handles: conversation history, usage stats, messages
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import json
from utils import now_local_str, TZ_SQL

DB_PATH = "bot_data.db"


@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_database():
    """Initialize database with all required tables"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT UNIQUE NOT NULL,
                platform TEXT NOT NULL,  -- 'telegram' or 'web'
                user_id TEXT,  -- Telegram user_id or web session
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Messages table
        # If old schema (missing 'sender' column) exists, drop and recreate
        cursor.execute("PRAGMA table_info(messages)")
        _msg_cols = [r["name"] for r in cursor.fetchall()]
        if "role" in _msg_cols or "sender" not in _msg_cols:
            cursor.execute("DROP TABLE IF EXISTS messages")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER REFERENCES users(id),
                conversation_id TEXT NOT NULL,
                sender          TEXT NOT NULL DEFAULT 'user', -- 'user' | 'bot'
                content         TEXT NOT NULL,
                input_tokens    INTEGER,
                output_tokens   INTEGER,
                cost_usd        REAL,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender  ON messages(sender)")
        
        # Usage stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                conversation_id TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
            )
        """)
        
        # User memory table (long-term per-user memory)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_memory (
                user_id     TEXT PRIMARY KEY,
                memory      TEXT NOT NULL,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── RAG Document tables ───────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doc_categories (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                is_public   INTEGER DEFAULT 0,  -- 1=all users, 0=staff+admin only
                description TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id                TEXT PRIMARY KEY,
                category_id       TEXT REFERENCES doc_categories(id),
                filename          TEXT NOT NULL,      -- stored on disk (uuid+ext)
                original_filename TEXT,               -- original uploaded name
                file_type         TEXT,               -- pdf, docx, txt, md
                file_size         INTEGER,
                description       TEXT,
                total_chunks      INTEGER DEFAULT 0,
                uploaded_by       TEXT,
                is_active         INTEGER DEFAULT 1,
                created_at        TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doc_chunks (
                id          TEXT PRIMARY KEY,
                doc_id      TEXT REFERENCES documents(id),
                category_id TEXT,                    -- denorm for fast filter
                chunk_index INTEGER,
                content     TEXT NOT NULL,
                page_num    INTEGER,
                token_count INTEGER,
                embedding   BLOB,                    -- float32 bytes
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_category ON doc_chunks(category_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON doc_chunks(doc_id)")

        # ── User / Role tables ────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id          TEXT PRIMARY KEY,          -- "customer", "staff", "admin"
                name        TEXT NOT NULL,             -- display name (VN)
                description TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        # Migration: recreate users table if id column is still TEXT (old schema)
        _cols = {r["name"]: r["type"] for r in
                 cursor.execute("PRAGMA table_info(users)").fetchall()}
        if _cols and _cols.get("id", "") != "INTEGER":
            cursor.execute("DROP TABLE IF EXISTS users")
            print("   ♻️  Dropped old users table (TEXT id → INTEGER AUTOINCREMENT migration)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                role_id      TEXT NOT NULL REFERENCES roles(id),
                is_active    INTEGER DEFAULT 1,
                created_at   TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS role_category_access (
                role_id     TEXT NOT NULL REFERENCES roles(id),
                category_id TEXT NOT NULL REFERENCES doc_categories(id),
                PRIMARY KEY (role_id, category_id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role_id)")

        # Seed default categories if empty
        cursor.execute("SELECT COUNT(*) as cnt FROM doc_categories")
        if cursor.fetchone()["cnt"] == 0:
            default_cats = [
                ("customer_guide",   "Hướng dẫn khách hàng",  1, "Tài liệu hướng dẫn dành cho khách hàng"),
                ("product_faq",      "FAQ Sản phẩm",           1, "Câu hỏi thường gặp về sản phẩm/dịch vụ"),
                ("internal_policy",  "Nội quy nội bộ",         0, "Quy định, chính sách nội bộ doanh nghiệp"),
                ("internal_pricing", "Bảng giá nội bộ",        0, "Bảng giá chi phí, chiết khấu nội bộ"),
                ("hr_handbook",      "Quy chế nhân sự",        0, "Hợp đồng, nghỉ phép, lương thưởng..."),
                ("training",         "Tài liệu đào tạo",       0, "Tài liệu onboard, training nhân viên"),
            ]
            cursor.executemany(
                "INSERT INTO doc_categories (id, name, is_public, description) VALUES (?,?,?,?)",
                default_cats
            )
            print("   🌱 Seeded default doc categories")

        # Seed default roles if empty
        cursor.execute("SELECT COUNT(*) as cnt FROM roles")
        if cursor.fetchone()["cnt"] == 0:
            cursor.executemany(
                "INSERT INTO roles (id, name, description) VALUES (?,?,?)",
                [
                    ("customer", "Khách hàng", "Người dùng cuối, chỉ xem tài liệu công khai"),
                    ("staff",    "Nhân viên",  "Nhân viên nội bộ, xem được tài liệu nội bộ"),
                    ("admin",    "Quản trị",   "Quản trị viên, toàn quyền truy cập"),
                ]
            )
            print("   🌱 Seeded default roles")

        # Seed default users if empty
        cursor.execute("SELECT COUNT(*) as cnt FROM users")
        if cursor.fetchone()["cnt"] == 0:
            cursor.executemany(
                "INSERT INTO users (username, display_name, role_id) VALUES (?,?,?)",
                [
                    ("customer01", "Nguyễn Khách",    "customer"),
                    ("staff01",    "Trần Nhân Viên",  "staff"),
                    ("admin01",    "Lê Quản Trị",     "admin"),
                ]
            )
            print("   🌱 Seeded default users")

        # Seed role_category_access if empty
        cursor.execute("SELECT COUNT(*) as cnt FROM role_category_access")
        if cursor.fetchone()["cnt"] == 0:
            all_cat_ids = [r[0] for r in cursor.execute("SELECT id FROM doc_categories").fetchall()]
            public_cats = ["customer_guide", "product_faq"]
            entries = []
            for cat in public_cats:
                entries.append(("customer", cat))
            for cat in all_cat_ids:
                entries.append(("staff", cat))
                entries.append(("admin", cat))
            cursor.executemany(
                "INSERT OR IGNORE INTO role_category_access (role_id, category_id) VALUES (?,?)",
                entries
            )
            print("   🌱 Seeded default role_category_access")

        # Orders table (mock data — replace with real API source later)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id            TEXT PRIMARY KEY,
                customer      TEXT NOT NULL,
                amount        REAL NOT NULL,
                status        TEXT NOT NULL,   -- shipped, processing, delivered, cancelled
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expected_delivery DATE,
                delivered_at  TIMESTAMP
            )
        """)

        # Seed mock orders if table is empty
        cursor.execute("SELECT COUNT(*) as cnt FROM orders")
        if cursor.fetchone()["cnt"] == 0:
            mock_orders = [
                ("ORD001", "Nguyễn A", 500000, "shipped",   "2026-03-18", None),
                ("ORD002", "Trần B",   750000, "processing", "2026-03-20", None),
                ("ORD003", "Phạm C",   1200000, "delivered", None,         "2026-03-10 14:30:00"),
                ("ORD004", "Lê D",     320000, "delivered",  None,         "2026-03-12 09:15:00"),
                ("ORD005", "Hoàng E",   890000, "cancelled",  None,         None),
            ]
            cursor.executemany("""
                INSERT INTO orders (id, customer, amount, status, expected_delivery, delivered_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, mock_orders)
            print("   🌱 Seeded mock orders into DB")

        # Create indexes for faster queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_stats(timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_platform ON conversations(platform)")
        
        print("✅ Database initialized successfully")


class ConversationDB:
    """Manage conversations and messages"""
    
    @staticmethod
    def create_conversation(conversation_id: str, platform: str, user_id: Optional[str] = None):
        """Create new conversation"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO conversations (conversation_id, platform, user_id)
                VALUES (?, ?, ?)
            """, (conversation_id, platform, user_id))
    
    @staticmethod
    def add_message(conversation_id: str, content: str,
                    sender: str = 'user',
                    input_tokens: Optional[int] = None,
                    output_tokens: Optional[int] = None,
                    cost_usd: Optional[float] = None,
                    user_id: Optional[int] = None):
        """Add message to conversation.
        sender: 'user' for human messages, 'bot' for assistant replies.
        user_id should be set for BOTH user and bot turns (so history filters work by user).
        """
        with get_db() as conn:
            cursor = conn.cursor()
            # Update conversation timestamp
            cursor.execute("""
                UPDATE conversations 
                SET updated_at = ?
                WHERE conversation_id = ?
            """, (now_local_str(), conversation_id))

            # Insert message
            cursor.execute("""
                INSERT INTO messages (user_id, conversation_id, sender, content, input_tokens, output_tokens, cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, conversation_id, sender, content, input_tokens, output_tokens, cost_usd))
    
    @staticmethod
    def get_conversation_history(conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get conversation history. sender='bot' is mapped to 'assistant' for Claude."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    CASE WHEN sender = 'bot' THEN 'assistant' ELSE 'user' END AS role,
                    content,
                    created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            """, (conversation_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def get_all_conversations(platform: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all conversations, optionally filtered by platform"""
        with get_db() as conn:
            cursor = conn.cursor()
            if platform:
                cursor.execute("""
                    SELECT c.*, COUNT(m.id) as message_count
                    FROM conversations c
                    LEFT JOIN messages m ON c.conversation_id = m.conversation_id
                    WHERE c.platform = ?
                    GROUP BY c.conversation_id
                    ORDER BY c.updated_at DESC
                    LIMIT ?
                """, (platform, limit))
            else:
                cursor.execute("""
                    SELECT c.*, COUNT(m.id) as message_count
                    FROM conversations c
                    LEFT JOIN messages m ON c.conversation_id = m.conversation_id
                    GROUP BY c.conversation_id
                    ORDER BY c.updated_at DESC
                    LIMIT ?
                """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]


class UserMemoryDB:
    """Manage long-term per-user memory"""

    @staticmethod
    def get_memory(user_id: str) -> Optional[str]:
        """Return memory blob for a user, or None if not exists"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT memory FROM user_memory WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row["memory"] if row else None

    @staticmethod
    def upsert_memory(user_id: str, memory: str):
        """Insert or update memory blob for a user"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_memory (user_id, memory, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    memory = excluded.memory,
                    updated_at = excluded.updated_at
            """, (user_id, memory, now_local_str()))
        print(f"🧠 Memory updated for user: {user_id[:8] if isinstance(user_id, str) else user_id}...")

    @staticmethod
    def count_user_messages(user_id: int) -> int:
        """Count messages sent by this user (sender='user' turns only)."""
        try:
            with get_db() as conn:
                row = conn.cursor().execute(
                    "SELECT COUNT(*) as cnt FROM messages WHERE user_id=? AND sender='user'",
                    (user_id,)
                ).fetchone()
            return row["cnt"] if row else 0
        except Exception:
            return 0


# ── Standalone helpers (no class needed) ─────────────────────────────────────

def get_role_label(role_id: str) -> str:
    """Fetch role display name from the roles table. Falls back to role_id if missing."""
    try:
        with get_db() as conn:
            row = conn.cursor().execute(
                "SELECT name FROM roles WHERE id=?", (role_id,)
            ).fetchone()
        return row["name"] if row else role_id
    except Exception:
        return role_id


def get_user_by_id(user_id) -> Optional[Dict[str, Any]]:
    """
    Look up a user from the users table by INTEGER id.
    Accepts int or string representation of int.
    Returns dict with id, username, display_name, role_id, is_active — or None.
    """
    try:
        uid = int(user_id)
    except (ValueError, TypeError):
        return None
    try:
        with get_db() as conn:
            row = conn.cursor().execute(
                "SELECT id, username, display_name, role_id, is_active FROM users WHERE id=?",
                (uid,)
            ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


class OrdersDB:
    """
    Data access layer for orders.
    Currently reads from local SQLite (mock data).
    To switch to real API: replace method bodies only — callers stay the same.
    """

    @staticmethod
    def get_orders(limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent orders, newest first."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, customer, amount, status, expected_delivery, delivered_at, created_at
                FROM orders
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_order(order_id: str) -> Optional[Dict[str, Any]]:
        """Get a single order by ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_revenue(period: str = "today") -> Dict[str, Any]:
        """
        Compute revenue from orders table.
        period: 'today' | 'week' | 'month'
        """
        period_filter = {
            "today": f"DATE(created_at) = DATE(datetime('now', '{TZ_SQL}'))",
            "week":  f"created_at >= DATE(datetime('now', '{TZ_SQL}'), '-7 days')",
            "month": f"created_at >= DATE(datetime('now', '{TZ_SQL}'), '-30 days')",
        }.get(period, "1=1")

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT
                    COUNT(*) as order_count,
                    COALESCE(SUM(amount), 0) as revenue
                FROM orders
                WHERE status != 'cancelled'
                AND {period_filter}
            """)
            row = dict(cursor.fetchone())
            return {"period": period, "revenue": row["revenue"], "order_count": row["order_count"]}

    @staticmethod
    def upsert_order(order: Dict[str, Any]):
        """Insert or update an order (useful for syncing from real API)."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders (id, customer, amount, status, expected_delivery, delivered_at)
                VALUES (:id, :customer, :amount, :status, :expected_delivery, :delivered_at)
                ON CONFLICT(id) DO UPDATE SET
                    customer = excluded.customer,
                    amount = excluded.amount,
                    status = excluded.status,
                    expected_delivery = excluded.expected_delivery,
                    delivered_at = excluded.delivered_at
            """, order)


class UsageStatsDB:
    """Manage usage statistics"""
    
    # Pricing table (same as usage_tracker.py)
    PRICING = {
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
        "claude-3-7-sonnet-20250219": {"input": 3.0, "output": 15.0},
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
        "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
    }
    
    USD_TO_VND = 20000  # Exchange rate
    
    @staticmethod
    def log_request(model: str, input_tokens: int, output_tokens: int, conversation_id: Optional[str] = None):
        """Log API request usage"""
        # Calculate cost
        pricing = UsageStatsDB.PRICING.get(model, {"input": 3.0, "output": 15.0})
        cost_usd = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO usage_stats (model, input_tokens, output_tokens, cost_usd, conversation_id)
                VALUES (?, ?, ?, ?, ?)
            """, (model, input_tokens, output_tokens, cost_usd, conversation_id))
        
        print(f"📊 Logged usage: {input_tokens} in + {output_tokens} out = ${cost_usd:.4f}")
    
    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """Get aggregated usage statistics"""
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Total stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    SUM(cost_usd) as total_cost_usd
                FROM usage_stats
            """)
            totals = dict(cursor.fetchone())
            
            # Recent sessions (last 10)
            cursor.execute("""
                SELECT 
                    timestamp,
                    model,
                    input_tokens,
                    output_tokens,
                    cost_usd,
                    conversation_id
                FROM usage_stats
                ORDER BY timestamp DESC
                LIMIT 10
            """)
            recent = [dict(row) for row in cursor.fetchall()]
            
            # Calculate derived values
            total_tokens = (totals["total_input_tokens"] or 0) + (totals["total_output_tokens"] or 0)
            total_cost_vnd = (totals["total_cost_usd"] or 0) * UsageStatsDB.USD_TO_VND
            
            return {
                "total_requests": totals["total_requests"] or 0,
                "total_input_tokens": totals["total_input_tokens"] or 0,
                "total_output_tokens": totals["total_output_tokens"] or 0,
                "total_tokens": total_tokens,
                "total_cost_usd": round(totals["total_cost_usd"] or 0, 4),
                "total_cost_vnd": round(total_cost_vnd, 2),
                "recent_sessions": recent
            }
    
    @staticmethod
    def reset_stats():
        """Clear all usage statistics"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM usage_stats")
            print("🗑️ Usage stats reset")


# Initialize database when module is imported
if __name__ == "__main__":
    init_database()
    print("Database ready!")
