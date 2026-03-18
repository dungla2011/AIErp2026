"""
doc_processor.py — Parse, chunk, embed, and save documents.

Supported formats: PDF, DOCX, TXT, MD
Chunking: ~500 tokens per chunk, 50 token overlap
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
import tiktoken
from database import get_db
from embeddings import embed_batch, to_blob

CHUNK_SIZE   = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(doc_id: str, msg: str, original_filename: str = "") -> None:
    """Append a timestamped log line to logs/{doc_id}.log and print to console."""
    prefix = f"[{_ts()}]"
    file_tag = f" | {original_filename}" if original_filename else ""
    line = f"{prefix}{file_tag} {msg}"
    print(line, flush=True)
    log_path = LOGS_DIR / f"{doc_id}.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# Tokenizer used only for counting / splitting
_tokenizer = None

def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = tiktoken.get_encoding("cl100k_base")
    return _tokenizer


def _clean_pdf_text(text: str) -> str:
    """Light whitespace cleanup for pdfplumber output (already geometry-aware)."""
    import re
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ── Parsers ──────────────────────────────────────────────────────────────────

def _parse_pdf(path: Path, doc_id: str = "", original_name: str = "") -> list[dict]:
    """Return list of {page: int, text: str} using pdfplumber (geometry-aware, better spacing)."""
    import pdfplumber
    LOG_EVERY = 10
    pages = []
    with pdfplumber.open(str(path)) as pdf:
        total_pages = len(pdf.pages)
        if doc_id:
            _log(doc_id, f"📖 PDF {total_pages} trang — bắt đầu đọc...", original_name)
        for i, pg in enumerate(pdf.pages):
            text = pg.extract_text(x_tolerance=2, y_tolerance=3) or ""
            text = _clean_pdf_text(text)
            if text:
                pages.append({"page": i + 1, "text": text})
            if doc_id and (i + 1) % LOG_EVERY == 0:
                _log(doc_id, f"📖 Đọc trang {i + 1}/{total_pages}...", original_name)
    return pages


def _parse_docx(path: Path) -> list[dict]:
    from docx import Document
    doc = Document(str(path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [{"page": 1, "text": text}]


def _parse_txt(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [{"page": 1, "text": text}]


def parse_file(path: Path, doc_id: str = "", original_name: str = "") -> list[dict]:
    """Parse a document into pages. Returns [{page, text}, ...]"""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path, doc_id, original_name)
    elif suffix in (".docx", ".doc"):
        return _parse_docx(path)
    elif suffix in (".txt", ".md"):
        return _parse_txt(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


# ── Chunker ───────────────────────────────────────────────────────────────────

def chunk_text(text: str, page: int = 1) -> list[dict]:
    """
    Split text into chunks of ~CHUNK_SIZE tokens with CHUNK_OVERLAP overlap.
    Returns [{chunk_index, page, text, token_count}, ...]
    """
    enc = _get_tokenizer()
    tokens = enc.encode(text)
    chunks = []
    start = 0
    idx   = 0
    while start < len(tokens):
        end          = min(start + CHUNK_SIZE, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_str    = enc.decode(chunk_tokens)

        # Trim to word boundary (avoid cutting mid-word) when not at end of text
        if end < len(tokens):
            last_space = chunk_str.rfind(' ')
            if last_space > 0:
                chunk_str    = chunk_str[:last_space]
                chunk_tokens = enc.encode(chunk_str)

        chunk_str = chunk_str.strip()
        if chunk_str:
            chunks.append({
                "chunk_index": idx,
                "page":        page,
                "text":        chunk_str,
                "token_count": len(chunk_tokens),
            })

        if end == len(tokens):
            break

        start += max(1, len(chunk_tokens) - CHUNK_OVERLAP)
        idx   += 1
    return chunks


# ── Main entry point ──────────────────────────────────────────────────────────

def process_document(doc_id: str, file_path: Path, category_id: str) -> int:
    """
    Parse → chunk → embed → save to DB.
    Writes detailed progress to logs/{doc_id}.log.
    Returns number of chunks created.
    """
    # Look up original filename for log labelling
    with get_db() as conn:
        row = conn.cursor().execute(
            "SELECT original_filename, filename FROM documents WHERE id=?", (doc_id,)
        ).fetchone()
    original_name = row["original_filename"] if row else file_path.name

    # Clear / start log file
    log_path = LOGS_DIR / f"{doc_id}.log"
    log_path.write_text("", encoding="utf-8")  # reset

    _log(doc_id, f"🚀 Bắt đầu xử lý", original_name)
    pages = parse_file(file_path, doc_id, original_name)
    _log(doc_id, f"📄 Đọc xong: {len(pages)} trang có text", original_name)

    all_chunks = []
    for pg in pages:
        all_chunks.extend(chunk_text(pg["text"], pg["page"]))

    if not all_chunks:
        _log(doc_id, "⚠️  Không trích xuất được text", original_name)
        return 0

    total = len(all_chunks)
    _log(doc_id, f"✂️  Chia được {total} chunks — bắt đầu embed...", original_name)

    MINI_BATCH = 32
    saved = 0

    with get_db() as conn:
        cursor = conn.cursor()

        for start in range(0, total, MINI_BATCH):
            batch = all_chunks[start:start + MINI_BATCH]
            texts = [c["text"] for c in batch]
            vecs  = embed_batch(texts, show_progress=False)

            rows = [(
                str(uuid.uuid4()), doc_id, category_id,
                c["chunk_index"], c["text"], c["page"], c["token_count"],
                to_blob(v),
            ) for c, v in zip(batch, vecs)]

            cursor.executemany("""
                INSERT INTO doc_chunks
                    (id, doc_id, category_id, chunk_index, content, page_num, token_count, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()

            saved += len(rows)
            pct = saved * 100 // total
            _log(doc_id, f"📥 {saved}/{total} chunks ({pct}%)", original_name)

        cursor.execute(
            "UPDATE documents SET total_chunks = ? WHERE id = ?",
            (saved, doc_id)
        )

    _log(doc_id, f"✅ Hoàn tất — {saved} chunks", original_name)
    return saved
