from typing import List, Optional, Dict, Any, Set
from pydantic import BaseModel, Field


# ==============================
# QUERY ANALYSIS
# ==============================

class QueryAnalysis(BaseModel):
    """
    Output from query analyzer node.
    """

    is_clear: bool
    requires_clarification: bool
    clarification_question: Optional[str] = None
    intent: Optional[str] = None


# ==============================
# AGENT STATE
# ==============================

class AgentState(BaseModel):
    """
    Global state shared across LangGraph nodes.
    """

    # ===== User Input =====
    user_input: str
    question: Optional[str] = None
    question_index: int = 0

    # ===== Conversation =====
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    context_summary: Optional[str] = None

    # ===== Query Analysis =====
    query_analysis: Optional[QueryAnalysis] = None

    # ==========================
    # DOMAIN / PLANNER
    # ==========================

    domain: Optional[str] = None
    plan: Optional[str] = None

    # ===== Tool Decision =====
    tool_decision: Optional[Dict[str, Any]] = None

    # ===== Tool Execution =====
    tool_result: Optional[Dict[str, Any]] = None
    tool_call_count: int = 0

    # ===== RAG Context =====
    rag_context: Optional[str] = None
    retrieval_keys: Set[str] = Field(default_factory=set)

    # ===== Final Response =====
    final_answer: Optional[str] = None
    final_response: Optional[str] = None

    # ===== Loop Control =====
    iteration_count: int = 0
    max_iterations: int = 5

    # ===== Metadata =====
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    memory_context: Optional[str] = None