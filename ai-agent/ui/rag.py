"""
rag.py — Retrieval-Augmented Generation: find relevant chunks for a query.

Strategy: cosine similarity between query embedding and all chunk embeddings,
filtered by allowed categories (access control).
Vector store: SQLite BLOB (no external DB needed for MVP).
"""

import numpy as np
from typing import Optional
from database import get_db
from embeddings import embed, from_blob, cosine_similarity

# ── Access control ────────────────────────────────────────────────────────────

def get_allowed_categories(user_role: str) -> Optional[list[str]]:
    """
    Return list of allowed category IDs for this role (from DB).
    Returns None to signal "all categories" only when every category is covered.
    Returns [] when the role has no permissions at all.
    """
    with get_db() as conn:
        rows = conn.cursor().execute(
            "SELECT category_id FROM role_category_access WHERE role_id = ?",
            (user_role,)
        ).fetchall()

    if not rows:
        # Unknown role or no permissions — deny everything
        return []

    allowed = [r["category_id"] for r in rows]

    # Check if this covers ALL existing categories (treat as "unrestricted")
    with get_db() as conn:
        total = conn.cursor().execute(
            "SELECT COUNT(*) as cnt FROM doc_categories"
        ).fetchone()["cnt"]

    if len(allowed) >= total:
        return None   # None = all categories allowed

    return allowed


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    user_role: str = "customer",
    top_k: int = 5,
    min_score: float = 0.30,
    category_hint: Optional[str] = None,
) -> list[dict]:
    """
    Find the most relevant document chunks for `query`.

    Args:
        query:         User question
        user_role:     "customer" | "staff" | "admin"
        top_k:         Max chunks to return
        min_score:     Minimum cosine similarity threshold
        category_hint: Optional specific category the user selected in UI

    Returns:
        List of {content, category_id, source_file, page_num, score}
    """
    if not query.strip():
        return []

    allowed = get_allowed_categories(user_role)

    # If user chose a specific category, use it (only if it's in their allowed set)
    if category_hint:
        if allowed is None or category_hint in allowed:
            allowed = [category_hint]

    # Load chunks (with embeddings) filtered by allowed categories
    with get_db() as conn:
        cursor = conn.cursor()

        if allowed is None:
            # All categories
            cursor.execute("""
                SELECT c.id, c.content, c.category_id, c.page_num, c.embedding,
                       c.token_count,
                       d.filename
                FROM doc_chunks c
                JOIN documents d ON c.doc_id = d.id
                WHERE d.is_active = 1
                  AND c.embedding IS NOT NULL
                  AND c.token_count >= 30
            """)
        else:
            placeholders = ",".join("?" * len(allowed))
            cursor.execute(f"""
                SELECT c.id, c.content, c.category_id, c.page_num, c.embedding,
                       c.token_count,
                       d.filename
                FROM doc_chunks c
                JOIN documents d ON c.doc_id = d.id
                WHERE c.category_id IN ({placeholders})
                  AND d.is_active = 1
                  AND c.embedding IS NOT NULL
                  AND c.token_count >= 30
            """, allowed)

        rows = cursor.fetchall()

    if not rows:
        return []

    # Embed query
    query_vec = embed(query)

    # Score all chunks
    scored = []
    for row in rows:
        try:
            chunk_vec = from_blob(row["embedding"])
            score = cosine_similarity(query_vec, chunk_vec)
            if score >= min_score:
                scored.append({
                    "content":     row["content"],
                    "category_id": row["category_id"],
                    "source_file": row["filename"],
                    "page_num":    row["page_num"],
                    "score":       round(score, 4),
                })
        except Exception:
            continue

    # Sort by score descending, take top_k
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def format_context(chunks: list[dict]) -> str:
    """
    Format retrieved chunks into a context block for the system prompt.
    """
    if not chunks:
        return ""

    parts = ["=== Tài liệu tham khảo ==="]
    for i, c in enumerate(chunks, 1):
        source = f"{c['source_file']}"
        if c.get("page_num"):
            source += f", trang {c['page_num']}"
        parts.append(f"\n[{i}] Nguồn: {source} (score: {c['score']})\n{c['content']}")
    parts.append("\n=== Kết thúc tài liệu ===")
    return "\n".join(parts)
