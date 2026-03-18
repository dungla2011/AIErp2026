"""
embeddings.py — Sentence embedding wrapper using local MiniLM model.

Model: paraphrase-multilingual-MiniLM-L12-v2
- Supports Vietnamese well
- ~420MB download on first use (cached automatically)
- 384-dimensional embeddings, normalized (cosine similarity = dot product)
"""

import numpy as np
import os

MODEL_NAME = os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

_model = None


def get_model():
    global _model
    if _model is None:
        print(f"🔤 Loading embedding model: {MODEL_NAME} (first time may take a while)...")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
        print(f"✅ Embedding model loaded")
    return _model


def embed(text: str) -> np.ndarray:
    """
    Embed a single text string.
    Returns normalized float32 array of shape (384,).
    """
    return get_model().encode(text, normalize_embeddings=True).astype(np.float32)


def embed_batch(texts: list[str], show_progress: bool = False) -> np.ndarray:
    """
    Embed a list of strings.
    Returns float32 array of shape (N, 384).
    """
    return get_model().encode(
        texts,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=show_progress,
    ).astype(np.float32)


def to_blob(vec: np.ndarray) -> bytes:
    """Convert numpy float32 array to bytes for SQLite BLOB storage."""
    return vec.astype(np.float32).tobytes()


def from_blob(blob: bytes) -> np.ndarray:
    """Restore numpy float32 array from SQLite BLOB."""
    return np.frombuffer(blob, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two normalized vectors (= dot product)."""
    return float(np.dot(a, b))
