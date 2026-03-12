# ai_core/graph/state.py

from typing import List, Annotated, Set, Optional
from langgraph.graph import MessagesState
import operator

from schemas.ai.query_analysis import QueryAnalysis

# =========================
# Custom reducers
# Trong LangGraph, reducer quyết định cách merge dữ liệu mới vào state cũ 
# khi nhiều node cùng ghi vào một field. 
# Nếu không có reducer thì LangGraph sẽ overwrite (ghi đè).
# Hai hàm này dùng để merge state khi nhiều node cập nhật cùng field:
# accumulate_or_reset → append list hoặc reset
# set_union           → gộp set không trùng
# =========================

# Hàm này dùng cho list kết quả của agent.
def accumulate_or_reset(existing: List[dict], new: List[dict]) -> List[dict]:

    if not new:
        return existing

    reset = any(item.get('__reset__') for item in new)

    filtered = [
        item for item in new
        if isinstance(item, dict) and not item.get('__reset__')
    ]

    if reset:
        return filtered

    return existing + filtered


# Hàm này dùng để gộp 2 set lại với nhau.
def set_union(a: Set[str], b: Set[str]) -> Set[str]:
    return a | b

# =========================
# GLOBAL GRAPH STATE
# =========================
class State(MessagesState):
    # --- Query clarity ---
    questionIsClear: bool = False

    # --- Conversation summary ---
    conversation_summary: str = ""

    # --- User query ---
    question: str = ""                  
    originalQuery: str = ""
    rewrittenQuestions: List[str] = []

    # --- Query analysis ---
    analysis: Optional[QueryAnalysis] = None

    # --- Router output ---
    agent_domain: str = ""
    agent_type: str = ""
    agent_reasoning: str = ""

    # --- Planner ---
    plan: str = ""

    # --- Retrieval hints ---
    retrieval_keys: Annotated[Set[str], set_union] = set()

    # --- Agent answers ---
    agent_answers: Annotated[List[dict], accumulate_or_reset] = []

    # --- Final result ---
    final_answer: str = ""


# =========================
# PER-AGENT STATE
# =========================
class AgentState(MessagesState):

    # --- Multi-question index ---
    question_index: int = 0

    # --- Domain routing ---
    domain: str = ""

    # --- Planning ---
    plan: str = ""

    # --- Query analysis ---
    analysis: Optional[QueryAnalysis] = None

    # --- User identity ---
    user_id: Optional[str] = None

    # --- Long term memory ---
    memory_context: Optional[str] = None

    # --- Context compression ---
    context_summary: str = ""

    # --- Retrieval tracking ---
    retrieval_keys: Annotated[Set[str], set_union] = set()

    # --- Tool usage ---
    tool_call_count: Annotated[int, operator.add] = 0

    # --- Iteration tracking ---
    iteration_count: Annotated[int, operator.add] = 0

    # --- Final answer ---
    final_answer: str = ""

    # --- Answers from sub-questions ---
    agent_answers: List[dict] = []