# ai_core/graph/state.py

from typing import List, Annotated, Set, Optional
from langgraph.graph import MessagesState
import operator

from schemas.ai.query_analysis import QueryAnalysis

# =========================
# Custom reducers
# =========================
def accumulate_or_reset(existing: List[dict], new: List[dict]) -> List[dict]:
    if new and any(item.get('__reset__') for item in new):
        return []
    return existing + new

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
    queryAnalysis: Optional[QueryAnalysis] = None

    # --- Router output ---
    agent_domain: str = ""
    agent_type: str = ""
    agent_reasoning: str = ""

    # --- Planner ---
    plan: str = ""

    # --- Retrieval hints ---
    questions: List[str] = []
    entities: List[str] = []
    keywords: List[str] = []
    filters: List[str] = []

    # --- Agent answers ---
    agent_answers: Annotated[List[dict], accumulate_or_reset] = []

    # --- Final result ---
    final_answer: str = ""


# =========================
# PER-AGENT STATE
# =========================

class AgentState(MessagesState):

    # --- Query ---
    question: str = ""
    originalQuery: str = ""
    rewrittenQuestions: List[str] = []

    # --- Multi-question index ---
    question_index: int = 0

    # --- Domain routing ---
    domain: str = ""

    # --- Planning ---
    plan: str = ""

    # --- Query analysis ---
    queryAnalysis: Optional[QueryAnalysis] = None

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