import os

# ==========================================================
# --- Directory Configuration ---
# ==========================================================

_BASE_DIR = os.path.dirname(__file__)

MARKDOWN_DIR = os.path.join(_BASE_DIR, "markdown_docs")
PARENT_STORE_PATH = os.path.join(_BASE_DIR, "parent_store")
QDRANT_DB_PATH = os.path.join(_BASE_DIR, "qdrant_db")


# ==========================================================
# --- Qdrant Configuration ---
# ==========================================================

CHILD_COLLECTION = "document_child_chunks"
SPARSE_VECTOR_NAME = "sparse"


# ==========================================================
# --- Embedding Models ---
# ==========================================================

DENSE_MODEL = "sentence-transformers/all-mpnet-base-v2"
SPARSE_MODEL = "Qdrant/bm25"


# ==========================================================
# --- Dynamic Multi-Model Routing (Private Ollama) ---
# ==========================================================

"""
LIGHT  → Simple queries (definition, short Q&A)
MEDIUM → Normal reasoning, RAG orchestration
HEAVY  → Complex analysis, multi-step reasoning
"""

# =========================
# LLM CONFIG
# =========================

LLM_MODEL = "qwen2.5:7b-instruct"
OLLAMA_URL = "http://localhost:11434"

# ----------------------------
# LIGHT MODEL
# ----------------------------
LIGHT_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
LIGHT_TEMPERATURE = 0


# ----------------------------
# MEDIUM MODEL
# ----------------------------
MEDIUM_MODEL = "deepseek-r1:7b"
MEDIUM_TEMPERATURE = 0


# ----------------------------
# HEAVY MODEL
# ----------------------------
HEAVY_MODEL = "moonshot:latest"
HEAVY_TEMPERATURE = 0


# ==========================================================
# --- Optional: Dedicated Role-based Models (Enterprise) ---
# ==========================================================

RETRIEVAL_MODEL = MEDIUM_MODEL
RETRIEVAL_TEMPERATURE = 0

SUMMARIZATION_MODEL = LIGHT_MODEL
SUMMARIZATION_TEMPERATURE = 0

COMPRESSION_MODEL = LIGHT_MODEL
COMPRESSION_TEMPERATURE = 0

AGGREGATION_MODEL = HEAVY_MODEL
AGGREGATION_TEMPERATURE = 0


# ==========================================================
# --- Agent Configuration ---
# ==========================================================

MAX_TOOL_CALLS = 8
MAX_ITERATIONS = 10

BASE_TOKEN_THRESHOLD = 2000
TOKEN_GROWTH_FACTOR = 0.9


# ==========================================================
# --- Text Splitter Configuration ---
# ==========================================================

# ===== RAG CHUNK CONFIG =====

# =========================
# RAG CONFIG
# =========================

EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"

VECTOR_DB_PATH = "./vector_db"

PARENT_CHUNK_SIZE = 1200    # kích thước đoạn context lớn
PARENT_CHUNK_OVERLAP = 150  # overlap giữa parent

CHILD_CHUNK_SIZE = 350      # chunk nhỏ để embed
CHILD_CHUNK_OVERLAP = 70   # overlap cho vector search

MIN_PARENT_SIZE = 2000
MAX_PARENT_SIZE = 4000

HEADERS_TO_SPLIT_ON = [
    ("#", "H1"),
    ("##", "H2"),
    ("###", "H3"),
]