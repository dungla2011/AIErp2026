"""
docs_api.py — FastAPI router for document management endpoints.

Endpoints:
  GET  /docs/categories           List all categories
  GET  /docs/list                 List all uploaded documents
  POST /docs/upload               Upload a new document
  DELETE /docs/{doc_id}           Delete a document and all its chunks
"""

import uuid
import asyncio
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from database import get_db
from doc_processor import process_document, UPLOADS_DIR, LOGS_DIR

router = APIRouter(prefix="/docs", tags=["Documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories")
def list_categories():
    """List all document categories."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, is_public, description,
                   (SELECT COUNT(*) FROM documents WHERE category_id = doc_categories.id AND is_active = 1) as doc_count
            FROM doc_categories
            ORDER BY is_public DESC, name
        """)
        return [dict(r) for r in cursor.fetchall()]


# ── Documents ─────────────────────────────────────────────────────────────────

@router.get("/list")
def list_documents(category_id: str = None):
    """List all uploaded documents, optionally filtered by category."""
    with get_db() as conn:
        cursor = conn.cursor()
        if category_id:
            cursor.execute("""
                SELECT d.*, c.name as category_name, c.is_public
                FROM documents d
                JOIN doc_categories c ON d.category_id = c.id
                WHERE d.category_id = ? AND d.is_active = 1
                ORDER BY d.created_at DESC
            """, (category_id,))
        else:
            cursor.execute("""
                SELECT d.*, c.name as category_name, c.is_public
                FROM documents d
                JOIN doc_categories c ON d.category_id = c.id
                WHERE d.is_active = 1
                ORDER BY d.created_at DESC
            """)
        rows = [dict(r) for r in cursor.fetchall()]

    # Attach processing status from per-doc log files
    for row in rows:
        log_path = LOGS_DIR / f"{row['id']}.log"
        if not log_path.exists():
            row["processing_status"] = "pending"
        else:
            content = log_path.read_text(encoding="utf-8")
            if "✅ Hoàn tất" in content:
                row["processing_status"] = "done"
            elif content.strip():
                row["processing_status"] = "processing"
            else:
                row["processing_status"] = "pending"

    return rows


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    category_id: str = Form(...),
    file: UploadFile = File(...),
    description: str = Form(""),
    uploaded_by: str = Form("admin"),
):
    """
    Upload a document and trigger background processing (chunking + embedding).
    Returns immediately with doc_id; processing happens in background.
    """
    # Validate extension
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Validate category exists
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM doc_categories WHERE id = ?", (category_id,))
        if not cursor.fetchone():
            raise HTTPException(400, f"Category '{category_id}' not found")

    # Save file to uploads/
    doc_id = str(uuid.uuid4())
    safe_name = f"{doc_id}{suffix}"
    dest_path = UPLOADS_DIR / safe_name

    content = await file.read()
    dest_path.write_bytes(content)

    # Register in DB
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO documents (id, category_id, filename, original_filename, file_type, file_size,
                                   description, uploaded_by, total_chunks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            doc_id, category_id,
            safe_name,
            file.filename,
            suffix.lstrip("."),
            len(content),
            description,
            uploaded_by,
        ))

    # Process in background (chunking + embedding can take seconds)
    background_tasks.add_task(_process_in_background, doc_id, dest_path, category_id)

    return {
        "doc_id": doc_id,
        "filename": file.filename,
        "category_id": category_id,
        "file_size": len(content),
        "status": "processing",
        "message": "File uploaded. Chunking and embedding running in background.",
    }


def _process_in_background(doc_id: str, file_path: Path, category_id: str):
    """Run doc_processor synchronously in background task."""
    try:
        n = process_document(doc_id, file_path, category_id)
        print(f"✅ Document {doc_id[:8]} ready: {n} chunks")
    except Exception as e:
        print(f"❌ Failed to process doc {doc_id[:8]}: {e}")
        # Mark as failed
        with get_db() as conn:
            conn.cursor().execute(
                "UPDATE documents SET is_active = 0 WHERE id = ?", (doc_id,)
            )


@router.get("/{doc_id}")
def get_document(doc_id: str):
    """Get document info and chunk count."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.*, c.name as category_name,
                   COUNT(ch.id) as chunk_count
            FROM documents d
            JOIN doc_categories c ON d.category_id = c.id
            LEFT JOIN doc_chunks ch ON ch.doc_id = d.id
            WHERE d.id = ?
            GROUP BY d.id
        """, (doc_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Document not found")
        return dict(row)


@router.delete("/{doc_id}")
def delete_document(doc_id: str):
    """Soft-delete a document and remove all its chunks."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Document not found")

        # Delete chunks
        cursor.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (doc_id,))
        # Hard-delete document record
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

        # Try to remove file from disk
        try:
            file_path = UPLOADS_DIR / row["filename"]
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass

    return {"status": "deleted", "doc_id": doc_id}


@router.get("/{doc_id}/log")
def get_doc_log(doc_id: str):
    """Return raw processing log for the document. Used by admin UI to show progress."""
    log_path = LOGS_DIR / f"{doc_id}.log"
    if not log_path.exists():
        return {"status": "pending", "content": ""}
    content = log_path.read_text(encoding="utf-8")
    if "\u2705 Ho\u00e0n t\u1ea5t" in content:
        status = "done"
    elif content.strip():
        status = "processing"
    else:
        status = "pending"
    return {"status": status, "content": content}


@router.post("/{doc_id}/reprocess")
def reprocess_document(doc_id: str, background_tasks: BackgroundTasks):
    """
    Delete existing chunks and re-run chunking + embedding on the stored file.
    Useful when doc_processor logic has been updated (e.g. better PDF cleaning).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, category_id FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Document not found")

        file_path = UPLOADS_DIR / row["filename"]
        if not file_path.exists():
            raise HTTPException(400, f"Source file missing on disk: {row['filename']}")

        # Wipe old chunks
        cursor.execute("DELETE FROM doc_chunks WHERE doc_id = ?", (doc_id,))
        cursor.execute("UPDATE documents SET total_chunks = 0, is_active = 1 WHERE id = ?", (doc_id,))

    background_tasks.add_task(_process_in_background, doc_id, file_path, row["category_id"])
    return {"status": "reprocessing", "doc_id": doc_id,
            "message": "Old chunks deleted. Re-embedding running in background."}
