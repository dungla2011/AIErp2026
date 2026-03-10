from pydantic import BaseModel, Field
from typing import List, Optional


class QueryAnalysis(BaseModel):

    # ======================
    # RAW QUERY
    # ======================

    query: str

    # multi-query for RAG retrieval
    questions: List[str] = Field(default_factory=list)

    # ======================
    # INTENT
    # ======================

    intent: str = "general"
    domain: str = "general"
    subdomain: Optional[str] = None

    # ======================
    # ROUTING
    # ======================

    target_agent: Optional[str] = None

    # ======================
    # RAG / TOOLS
    # ======================

    use_rag: bool = True
    retrieval_mode: str = "hybrid"
    # vector | keyword | hybrid

    top_k: int = 5

    # =====================
    # TOOL USAGE
    # =====================

    use_tools: bool = False
    requires_data: bool = False

    # ======================
    # QUERY STRUCTURE
    # ======================

    complexity: str = "simple"
    # simple | multi_hop | analytical

    needs_clarification: bool = False

    # ======================
    # RETRIEVAL
    # ======================

    entities: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    filters: List[str] = Field(default_factory=list)
    retrieval_hints: List[str] = Field(default_factory=list)

    # ======================
    # CONFIDENCE
    # ======================

    confidence: float = 0.0