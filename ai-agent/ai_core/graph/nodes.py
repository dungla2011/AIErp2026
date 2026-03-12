import logging
import time
from typing import Literal, Set, Dict, Any, List
from pydantic import ValidationError

from langchain_core.messages import (
    SystemMessage, 
    HumanMessage, 
    AIMessage, 
    ToolMessage
)
from langgraph.graph.message import RemoveMessage
from langgraph.types import Command

from .state import State, AgentState
from ..prompts.system_prompt import *
from ..prompts.tool_prompt import *
from ..prompts.router_prompt import *
from schemas.ai.query_analysis import QueryAnalysis

from utils import estimate_context_tokens
from config import BASE_TOKEN_THRESHOLD, TOKEN_GROWTH_FACTOR

from ai_core.agents.accounting_agent import accounting_agent
from ai_core.agents.inventory_agent import inventory_agent
from ai_core.agents.audit_agent import audit_agent

# memory nodes
from memory.memory_manager import memory_manager

logger = logging.getLogger(__name__)
MAX_RETRY = 3
MAX_QUERY_EXPANSION = 4
MAX_QUERY_LENGTH = 300

MAX_ITERATIONS = 8
MAX_TOOL_CALLS = 20

# =========================================================
# SAFE LLM CALL
# =========================================================
def safe_llm_invoke(llm, messages, retries=3):

    for attempt in range(retries):

        try:
            return llm.invoke(messages)
        except Exception as e:
            logger.warning(f"LLM call failed {attempt+1}: {e}")
            time.sleep(0.5 * (attempt + 1))

    raise RuntimeError("LLM failed after retries")

# =========================================================
# MEMORY
# =========================================================
def load_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load long-term memory for user and inject into state.
    """

    user_id = state.get("user_id")

    if not user_id:
        return {}

    memory = memory_manager.load_user_memory(user_id)

    if not memory:
        return {}

    return {
        "memory_context": memory or ""
    }
def save_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save important info from conversation into long-term memory.
    """

    user_id = state.get("user_id")
    messages = state.get("messages", [])

    if not user_id or not messages:
        return {}

    # Lấy câu trả lời cuối cùng
    last_message = messages[-1]

    # Tuỳ muốn lưu gì:
    # Option 1: Lưu toàn bộ answer
    content_to_store = last_message.content if hasattr(last_message, "content") else str(last_message)

    # Option 2 (production tốt hơn):
    # Chỉ lưu thông tin quan trọng bằng cách gọi LLM summarize

    memory_manager.save_user_memory(user_id, content_to_store)

    return {}
# ===============================

# ===============================
# Query Analysis Node
# ===============================

def analyze_query(state: Dict[str, Any], llm) -> Dict[str, Any]:
    """
    Analyze user query and produce structured QueryAnalysis.

    Responsibilities:
    - detect intent
    - classify ERP domain
    - determine whether RAG/tools are needed
    - generate multi-query retrieval
    - extract entities & keywords
    """
    print("🟢 NODE → analyze_query")

    messages = state.get("messages", [])
    query = messages[-1].content.strip() if messages else ""

    if not query:
        return {"analysis": QueryAnalysis(query="")}

    system_prompt = """
        You are a senior AI query analysis engine for an ERP assistant.

        Your job is to analyze the user's query and produce structured analysis.

        The analysis will be used by:
        - agent router
        - RAG retrieval
        - tool orchestration
        """

    user_prompt = f"""
        User Query:

        {query}

        Generate a QueryAnalysis JSON object.
        """

    structured_llm = llm.with_structured_output(QueryAnalysis)

    try:

        analysis: QueryAnalysis = structured_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

    except Exception as e:
        print("analyze_query error:", e)
        analysis = QueryAnalysis(
            query=query,
            questions=[query],
            intent="general",
            domain="general",
            confidence=0.2
        )

    # safety guards    
    if not analysis.questions:
        analysis.questions = [query]

    analysis.questions = analysis.questions[:5]

    # =====================
    # Router hints
    # =====================
    if analysis.domain in ["inventory", "stock", "warehouse"]:
        analysis.target_agent = "inventory"

    elif analysis.domain in ["accounting", "finance"]:
        analysis.target_agent = "accounting"

    elif analysis.domain in ["audit", "compliance"]:
        analysis.target_agent = "audit"

    if analysis.requires_data:
        analysis.use_tools = True

    # =====================
    # IMPORTANT: return dict
    # =====================
    return {
        "analysis": analysis
    }
#=====================================================================

def summarize_history(state: State, llm):
    print("🟢 NODE → summarize_history")    

    if len(state["messages"]) < 4:
        return {"conversation_summary": ""}
    
    relevant_msgs = [
        msg for msg in state["messages"][:-1]
        if isinstance(msg, (HumanMessage, AIMessage)) and not getattr(msg, "tool_calls", None)
    ]

    if not relevant_msgs:
        return {"conversation_summary": ""}
    
    conversation = "Conversation history:\n"
    for msg in relevant_msgs[-6:]:
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        conversation += f"{role}: {msg.content}\n"

    summary_response = llm.with_config(temperature=0.2).invoke([SystemMessage(content=get_conversation_summary_prompt()), HumanMessage(content=conversation)])
    return {"conversation_summary": summary_response.content, "agent_answers": [{"__reset__": True}]}

def _safe_queries(queries: List[str], original_query: str) -> List[str]:
    """
    Clean queries before sending to retriever
    """

    cleaned = []

    for q in queries:

        if not q:
            continue

        q = q.strip()

        if len(q) < 3:
            continue

        if len(q) > MAX_QUERY_LENGTH:
            q = q[:MAX_QUERY_LENGTH]

        cleaned.append(q)

    # remove duplicates
    cleaned = list(dict.fromkeys(cleaned))

    # fallback
    if not cleaned:
        cleaned = [original_query]

    return cleaned[:MAX_QUERY_EXPANSION]

def _expand_queries(queries: List[str], original_query: str) -> List[str]:
    """
    Multi query expansion
    """

    expanded = list(queries)

    if len(expanded) == 1:

        q = expanded[0]

        expanded.append(f"{q} explanation")
        expanded.append(f"{q} details")
        expanded.append(f"{q} examples")

    if not expanded:
        expanded = [original_query]

    return expanded[:MAX_QUERY_EXPANSION]

def should_rewrite(question: str) -> bool:
    """
    Skip rewrite if question too simple
    """

    if not question:
        return False

    # quá ngắn
    if len(question.split()) < 3:
        return False

    # toán đơn giản
    if question.strip().isdigit():
        return False

    return True

# =========================================================
# QUERY REWRITE
# =========================================================
def rewrite_query(state: Dict[str, Any], llm) -> Dict[str, Any]:
    """
    LangGraph node:
    - analyze query
    - generate multi-query retrieval
    - guard against hallucination
    - safe state update
    """
    print("🟢 NODE → rewrite_query")

    analysis: QueryAnalysis = state.get("analysis")

    if not analysis:
        return {}

    user_query = analysis.query

    if not should_rewrite(user_query):
        logger.info("rewrite_query: skip rewrite (simple query)")
        return {"analysis": analysis}

    conversation_summary = state.get("conversation_summary", "")
    context_section = ""
    if conversation_summary.strip():
        context_section += (
            f"Conversation Context:\n{conversation_summary}\n\n"
        )

    context_section += f"User Query:\n{user_query}\n"

    logger.info(f"[rewrite_query] query: {user_query}")

    llm_structured = (
        llm.with_config(temperature=0.1)
        .with_structured_output(QueryAnalysis)
    )

    response = llm_structured.invoke([
        SystemMessage(content=get_rewrite_query_prompt()),
        HumanMessage(content=context_section),
    ])

    queries = response.questions or [user_query]

    queries = _expand_queries(queries, user_query)
    queries = _safe_queries(queries, user_query)

    if response.confidence < 0.2:
        queries = [user_query]

    analysis.questions = queries

    return {
        "analysis": analysis,
        "questionIsClear": not response.needs_clarification
    }

def request_clarification(state: State, llm):
    print("🟢 NODE → request_clarification")
    
    question = state.get("originalQuery") or state["messages"][-1].content

    prompt = f"""
        User question is unclear:

        {question}

        Ask the user a short clarification question.
        """

    response = llm.invoke(prompt)

    return {
        "agent_answers": [response.content]
    }

# =========================================================
# ORCHESTRATOR
# =========================================================
# multi-hop reasoning
def orchestrator(state: State, llm):
    print("🟢 NODE → orchestrator")

    analysis: QueryAnalysis = state.get("analysis")

    question = analysis.query if analysis else ""

    context_summary = state.get("context_summary", "").strip()
    memory_context = state.get("memory_context", "").strip()

    base_prompt = get_orchestrator_prompt()

    if memory_context:
        base_prompt += f"\n\nUser Memory:\n{memory_context}"

    sys_msg = SystemMessage(content=base_prompt)

    summary_injection = []

    if context_summary:
        summary_injection.append(
            HumanMessage(content=f"[COMPRESSED CONTEXT]\n{context_summary}")
        )

    human_msg = HumanMessage(content=question)

    response = llm.invoke(
        [sys_msg] + summary_injection + [human_msg]
    )

    tool_calls = getattr(response, "tool_calls", [])

    prev_iteration = state.get("iteration_count", 0)
    prev_tool_calls = state.get("tool_call_count", 0)

    return {
        "messages": [human_msg, response],
        "tool_call_count": prev_tool_calls + len(tool_calls),
        "iteration_count": prev_iteration + 1
    }
# End multi-hop reasoning

# =========================================================
# FALLBACK
# =========================================================
def fallback_response(state: AgentState, llm):
    print("🟢 NODE → fallback_response")

    analysis: QueryAnalysis = state.get("analysis")
    question = analysis.query if analysis else ""

    seen = set()
    unique_contents = []

    for m in state["messages"]:
        if isinstance(m, ToolMessage) and m.content not in seen:
            unique_contents.append(m.content)
            seen.add(m.content)

    context_summary = state.get("context_summary", "").strip()

    context_parts = []

    if context_summary:
        context_parts.append(
            f"## Compressed Research Context (from prior iterations)\n\n{context_summary}"
        )

    if unique_contents:
        context_parts.append(
            "## Retrieved Data (current iteration)\n\n"
            + "\n\n".join(
                f"--- DATA SOURCE {i} ---\n{content}"
                for i, content in enumerate(unique_contents, 1)
            )
        )

    context_text = "\n\n".join(context_parts) if context_parts else "No data retrieved."

    prompt_content = (
        f"USER QUERY: {question}\n\n"
        f"{context_text}\n\n"
        f"INSTRUCTION:\nProvide the best possible answer using only the data above."
    )

    response = llm.invoke([
        SystemMessage(content=get_fallback_response_prompt()),
        HumanMessage(content=prompt_content)
    ])

    return {"messages": [response]}

# =========================================================
# CONTEXT COMPRESSION
# =========================================================
def compress_context(state: AgentState, llm):
    analysis: QueryAnalysis = state.get("analysis")
    question = analysis.query if analysis else ""

    messages = state["messages"]
    existing_summary = state.get("context_summary", "").strip()

    if not messages:
        return {}

    conversation_text = f"USER QUESTION:\n{question}\n\nConversation to compress:\n\n"

    if existing_summary:
        conversation_text += f"[PRIOR COMPRESSED CONTEXT]\n{existing_summary}\n\n"

    for msg in messages[1:]:

        if isinstance(msg, AIMessage):

            tool_calls_info = ""

            if getattr(msg, "tool_calls", None):
                calls = ", ".join(
                    f"{tc['name']}({tc['args']})"
                    for tc in msg.tool_calls
                )

                tool_calls_info = f" | Tool calls: {calls}"

            conversation_text += (
                f"[ASSISTANT{tool_calls_info}]\n"
                f"{msg.content or '(tool call only)'}\n\n"
            )

        elif isinstance(msg, ToolMessage):

            tool_name = getattr(msg, "name", "tool")

            conversation_text += (
                f"[TOOL RESULT — {tool_name}]\n"
                f"{msg.content}\n\n"
            )

    summary_response = safe_llm_invoke(llm, [...])

    new_summary = summary_response.content

    return {
        "context_summary": new_summary,
        "messages": [RemoveMessage(id=m.id) for m in messages[1:]]
    }

# =========================================================
# TOKEN CONTROL
# =========================================================
def should_compress_context(state: AgentState) -> Command[Literal["compress_context", "orchestrator"]]:
    messages = state["messages"]

    new_ids: Set[str] = set()
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                if tc["name"] == "retrieve_parent_chunks":
                    raw = tc["args"].get("parent_id") or tc["args"].get("id") or tc["args"].get("ids") or []
                    if isinstance(raw, str):
                        new_ids.add(f"parent::{raw}")
                    else:
                        new_ids.update(f"parent::{r}" for r in raw)

                elif tc["name"] == "search_child_chunks":
                    query = tc["args"].get("query", "")
                    if query:
                        new_ids.add(f"search::{query}")
            break

    updated_ids = state.get("retrieval_keys", set()) | new_ids

    current_token_messages = estimate_context_tokens(messages)
    current_token_summary = estimate_context_tokens([HumanMessage(content=state.get("context_summary", ""))])
    current_tokens = current_token_messages + current_token_summary

    max_allowed = BASE_TOKEN_THRESHOLD + int(current_token_summary * TOKEN_GROWTH_FACTOR)

    goto = "compress_context" if current_tokens > max_allowed else "orchestrator"
    return Command(update={"retrieval_keys": updated_ids}, goto=goto)
# End context compression

# =========================================================
# ANSWER COLLECTION
# =========================================================
def collect_answer(state: AgentState):
    print("🟢 NODE → collect_answer")

    analysis: QueryAnalysis = state.get("analysis")
    question_index = state.get("question_index", 0)

    # fallback query
    question = ""

    if analysis:
        if analysis.questions and question_index < len(analysis.questions):
            question = analysis.questions[question_index]
        else:
            question = analysis.query

    last_message = state["messages"][-1]

    is_valid = (
        isinstance(last_message, AIMessage)
        and last_message.content
        and not last_message.tool_calls
    )

    answer = last_message.content if is_valid else "Unable to generate an answer."

    return {
        "final_answer": answer,
        "agent_answers": [
            {
                "index": question_index,
                "question": question,
                "answer": answer
            }
        ]
    }
# --- End of Agent Nodes---


# =========================================================
# PLANNER NODE
# =========================================================
def planner(state: AgentState, llm):

    print("🟢 NODE → planner")

    analysis: QueryAnalysis = state.get("analysis")

    question = analysis.query if analysis else ""

    domain = getattr(analysis, "domain", "general")
    intent = getattr(analysis, "intent", "general")
    entities = getattr(analysis, "entities", [])

    context_summary = state.get("conversation_summary", "")

    prompt = f"""
ERP Domain: {domain}
Intent: {intent}
Entities: {entities}

User Question:
{question}

Conversation Context:
{context_summary}
"""

    response = llm.invoke([
        SystemMessage(content="You are a planning module for an ERP AI agent system."),
        HumanMessage(content=prompt)
    ])

    plan_text = response.content

    tool_strategy = "UNKNOWN"

    if "ERP_DB" in plan_text:
        tool_strategy = "ERP_DB"

    elif "RAG" in plan_text:
        tool_strategy = "RAG"

    elif "API" in plan_text:
        tool_strategy = "API"

    elif "ANALYTICS" in plan_text:
        tool_strategy = "ANALYTICS"

    elif "NO_TOOLS" in plan_text:
        tool_strategy = "NO_TOOLS"

    return {
        "plan": plan_text,
        "tool_strategy": tool_strategy
    }

# =========================================================
# AGGREGATION
# =========================================================

def aggregate_answers(state: State, llm):
    if not state.get("agent_answers"):
        return {"messages": [AIMessage(content="No answers were generated.")]}

    analysis: QueryAnalysis = state.get("analysis")
    question = analysis.query if analysis else ""

    sorted_answers = sorted(
        state["agent_answers"],
        key=lambda x: x["index"]
    )

    formatted_answers = "\n".join(
        f"Answer {i}:\n{ans['answer']}"
        for i, ans in enumerate(sorted_answers, start=1)
    )

    user_message = HumanMessage(content=(
        f"Original user question: {question}\n"
        f"Retrieved answers:\n{formatted_answers}"
    ))

    response = safe_llm_invoke(llm, [
        SystemMessage(content=get_aggregation_prompt()),
        user_message
    ])

    return {"messages": [response]}


# =========================================================
# AGENTS
# =========================================================
def accounting_node(state, llm):
    return accounting_agent(state, llm)
def inventory_node(state, llm):
    return inventory_agent(state, llm)
def audit_node(state, llm):
    return audit_agent(state, llm)