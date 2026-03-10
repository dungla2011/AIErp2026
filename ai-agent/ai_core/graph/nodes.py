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

    query = (
        state.get("originalQuery")
        or state.get("question")
        or (messages[-1].content if messages else "")
    )
    query = query.strip()

    if not query:
        print("analyze_query: empty query")

        return {
            "analysis": QueryAnalysis(query=""),
            "originalQuery": "",
        }

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

    except ValidationError:
        print("analyze_query: validation fallback")

        analysis = QueryAnalysis(
            query=query,
            questions=[query],
            intent="general",
            domain="general",
            confidence=0.3
        )

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

    if analysis.confidence is None:
        analysis.confidence = 0.5

    analysis.confidence = max(0.0, min(1.0, analysis.confidence))

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

    print("analyze_query done")
    print("target_agent:", analysis.target_agent)

    # =====================
    # IMPORTANT: return dict
    # =====================

    return {
        "analysis": analysis,
        "originalQuery": query,  # VERY IMPORTANT
        "questions": analysis.questions,
        "entities": analysis.entities,
        "keywords": analysis.keywords,
        "target_agent": analysis.target_agent,
        "use_rag": analysis.use_rag,
        "use_tools": analysis.use_tools,
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

    try:

        messages = state.get("messages", [])

        if not messages:
            logger.warning("rewrite_query: no messages in state")
            return state

        last_message = messages[-1]
        user_query = last_message.content.strip()

        # -----------------------------
        # SKIP rewrite for simple query
        # -----------------------------
        if not should_rewrite(user_query):

            logger.info("rewrite_query: skip rewrite (simple query)")

            return {
                "questionIsClear": True,
                "question": user_query,
                "originalQuery": user_query,
                "rewrittenQuestions": [user_query]
            }

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

        response = None

        # -----------------------------
        # retry mechanism
        # -----------------------------
        for attempt in range(MAX_RETRY):

            try:

                response = llm_structured.invoke([
                    SystemMessage(content=get_rewrite_query_prompt()),
                    HumanMessage(content=context_section),
                ])

                break

            except Exception as e:

                logger.warning(
                    f"rewrite_query LLM attempt {attempt+1} failed: {e}"
                )

        # -----------------------------
        # fallback if LLM crash
        # -----------------------------
        if response is None:

            logger.error("rewrite_query: LLM failed completely")

            return {
                "questionIsClear": True,
                "question": user_query,
                "originalQuery": user_query,
                "rewrittenQuestions": [user_query],
            }

        # -----------------------------
        # clarification branch
        # -----------------------------
        if response.needs_clarification:

            clarification_message = (
                "Your question is not clear enough. "
                "Could you provide more details?"
            )

            logger.info("rewrite_query: clarification required")

            return {
                "questionIsClear": False,
                "messages": [AIMessage(content=clarification_message)],
            }

        # -----------------------------
        # multi-query generation
        # -----------------------------
        queries = response.questions or [user_query]

        queries = _expand_queries(queries, user_query)
        queries = _safe_queries(queries, user_query)

        # -----------------------------
        # confidence guard
        # -----------------------------
        if response.confidence < 0.2:

            logger.warning(
                "rewrite_query: low confidence, fallback to original query"
            )

            queries = [user_query]

        logger.info(f"[rewrite_query] generated queries: {queries}")

        # -----------------------------
        # message cleanup
        # -----------------------------
        delete_msgs = [
            RemoveMessage(id=m.id)
            for m in messages[:-1]
            if isinstance(m, (AIMessage, ToolMessage))
        ]

        # -----------------------------
        # state update
        # -----------------------------
        return {
            "questionIsClear": True,
            "messages": delete_msgs,
            "question": user_query,
            "originalQuery": user_query,
            "rewrittenQuestions": queries
        }

    except Exception as e:

        logger.exception(f"rewrite_query fatal error: {e}")

        query = state["messages"][-1].content

        return {
            "questionIsClear": True,
            "question": query,
            "originalQuery": query,
            "rewrittenQuestions": [query],
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

    context_summary = state.get("context_summary", "").strip()
    memory_context = state.get("memory_context", "").strip()

    # ===== System Prompt =====
    base_prompt = get_orchestrator_prompt()

    # Inject long-term memory vào system prompt
    if memory_context:
        base_prompt = (
            f"{base_prompt}\n\n"
            f"### User Long-Term Memory:\n"
            f"{memory_context}\n"
        )

    sys_msg = SystemMessage(content=base_prompt)

    # ===== Inject compressed context =====
    summary_injection = []
    if context_summary:
        summary_injection.append(
            HumanMessage(content=f"[COMPRESSED CONTEXT]\n\n{context_summary}")
        )

    # ===== Get question safely =====
    question = (
        state.get("question")
        or state.get("originalQuery")
        or state["messages"][-1].content
    )

    # ===== First iteration =====
    if state.get("iteration_count", 0) == 0:
        human_msg = HumanMessage(content=question)

        response = llm.invoke(
            [sys_msg] + summary_injection + [human_msg]
        )

        tool_calls = getattr(response, "tool_calls", [])
        print("🔥 TOOL CALLS:", tool_calls)

        prev_iteration = state.get("iteration_count", 0)
        prev_tool_calls = state.get("tool_call_count", 0)

        return {
            "messages": [human_msg, response],
            "tool_call_count": prev_tool_calls + (len(tool_calls) if tool_calls else 0),
            "iteration_count": prev_iteration + 1
        }

    # ===== Subsequent iterations =====
    response = llm.invoke(
        [sys_msg] + summary_injection + state["messages"]
    )

    tool_calls = getattr(response, "tool_calls", [])
    print("🔥 TOOL CALLS:", tool_calls)

    prev_iteration = state.get("iteration_count", 0)
    prev_tool_calls = state.get("tool_call_count", 0)

    return {
        "messages": [response],
        "tool_call_count": prev_tool_calls + (len(tool_calls) if tool_calls else 0),
        "iteration_count": prev_iteration + 1
    }
# End multi-hop reasoning

# =========================================================
# FALLBACK
# =========================================================
def fallback_response(state: AgentState, llm):
    print("🟢 NODE → fallback_response")

    seen = set()
    unique_contents = []
    for m in state["messages"]:
        if isinstance(m, ToolMessage) and m.content not in seen:
            unique_contents.append(m.content)
            seen.add(m.content)

    context_summary = state.get("context_summary", "").strip()

    context_parts = []
    if context_summary:
        context_parts.append(f"## Compressed Research Context (from prior iterations)\n\n{context_summary}")
    if unique_contents:
        context_parts.append(
            "## Retrieved Data (current iteration)\n\n" +
            "\n\n".join(f"--- DATA SOURCE {i} ---\n{content}" for i, content in enumerate(unique_contents, 1))
        )

    context_text = "\n\n".join(context_parts) if context_parts else "No data was retrieved from the documents."

    prompt_content = (
        f"USER QUERY: {state.get('question')}\n\n"
        f"{context_text}\n\n"
        f"INSTRUCTION:\nProvide the best possible answer using only the data above."
    )
    response = llm.invoke([SystemMessage(content=get_fallback_response_prompt()), HumanMessage(content=prompt_content)])
    return {"messages": [response]}

# =========================================================
# CONTEXT COMPRESSION
# =========================================================
def compress_context(state: AgentState, llm):
    messages = state["messages"]
    existing_summary = state.get("context_summary", "").strip()

    if not messages:
        return {}

    conversation_text = f"USER QUESTION:\n{state.get('question')}\n\nConversation to compress:\n\n"
    if existing_summary:
        conversation_text += f"[PRIOR COMPRESSED CONTEXT]\n{existing_summary}\n\n"

    for msg in messages[1:]:
        if isinstance(msg, AIMessage):
            tool_calls_info = ""
            if getattr(msg, "tool_calls", None):
                calls = ", ".join(f"{tc['name']}({tc['args']})" for tc in msg.tool_calls)
                tool_calls_info = f" | Tool calls: {calls}"
            conversation_text += f"[ASSISTANT{tool_calls_info}]\n{msg.content or '(tool call only)'}\n\n"
        elif isinstance(msg, ToolMessage):
            tool_name = getattr(msg, "name", "tool")
            conversation_text += f"[TOOL RESULT — {tool_name}]\n{msg.content}\n\n"

    summary_response = safe_llm_invoke(llm, [...])
    new_summary = summary_response.content

    retrieved_ids: Set[str] = state.get("retrieval_keys", set())
    if retrieved_ids:
        parent_ids = sorted(r for r in retrieved_ids if r.startswith("parent::"))
        search_queries = sorted(r.replace("search::", "") for r in retrieved_ids if r.startswith("search::"))

        block = "\n\n---\n**Already executed (do NOT repeat):**\n"
        if parent_ids:
            block += "Parent chunks retrieved:\n" + "\n".join(f"- {p.replace('parent::', '')}" for p in parent_ids) + "\n"
        if search_queries:
            block += "Search queries already run:\n" + "\n".join(f"- {q}" for q in search_queries) + "\n"
        new_summary += block

    return {"context_summary": new_summary, "messages": [RemoveMessage(id=m.id) for m in messages[1:]]}

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

    last_message = state["messages"][-1]
    is_valid = isinstance(last_message, AIMessage) and last_message.content and not last_message.tool_calls
    answer = last_message.content if is_valid else "Unable to generate an answer."
    return {
        "final_answer": answer,
        "agent_answers": [{"index": state["question_index"], "question": state["question"], "answer": answer}]
    }
# --- End of Agent Nodes---


# =========================================================
# PLANNER NODE
# =========================================================
def planner(state: AgentState, llm):

    print("🟢 NODE → planner")

    # =========================
    # Get question
    # =========================
    question = (
        state.get("question")
        or state.get("originalQuery")
        or state["messages"][-1].content
    )

    # =========================
    # Query analysis
    # =========================
    analysis = state.get("analysis")

    domain = "general"
    intent = "general"
    use_rag = False
    use_tools = False
    entities = []

    if analysis:
        domain = getattr(analysis, "domain", "general")
        intent = getattr(analysis, "intent", "general")
        use_rag = getattr(analysis, "use_rag", False)
        use_tools = getattr(analysis, "use_tools", False)
        entities = getattr(analysis, "entities", [])

    # =========================
    # Context summary
    # =========================
    context_summary = state.get("conversation_summary", "")

    # =========================
    # Tool cost guard
    # =========================
    tool_call_count = state.get("tool_call_count", 0)

    if tool_call_count > 10:
        return {
            "plan": "Tool usage limit reached. Answer using available context only.",
            "tool_strategy": "NO_TOOLS"
        }

    # =========================
    # Planner prompt
    # =========================
    prompt = f"""
You are the planning engine for an AI ERP system.

Your job is to decide:

1. Which tool category should be used
2. Whether the answer can be generated without tools
3. The safest strategy to retrieve information

------------------------------------

ERP Domain:
{domain}

Intent:
{intent}

Entities:
{entities}

User Question:
{question}

Conversation Context:
{context_summary}

------------------------------------

Available tool categories:

ERP_DB
- ERP internal database
- invoices
- accounting entries
- inventory records
- stock transactions

RAG
- company documents
- regulations
- tax law
- policies
- manuals

API
- external services
- payment gateway
- e-invoice provider
- exchange rate API

ANALYTICS
- reports
- financial analysis
- forecasting
- dashboards

------------------------------------

Planning rules:

1. If the question is about ERP data → use ERP_DB
2. If the question is about regulations or documents → use RAG
3. If the question requires external service → use API
4. If the question requires calculations or reports → use ANALYTICS
5. If the answer can be generated from context → use NO_TOOLS

------------------------------------

Anti-hallucination rules:

- NEVER invent ERP data
- NEVER fabricate financial numbers
- If no reliable source exists → request tool usage

------------------------------------

Return a short plan with:

- TOOL_CATEGORY
- TOOL_STRATEGY
- REASONING
"""

    response = llm.invoke([
        SystemMessage(content="You are a planning module for an ERP AI agent system."),
        HumanMessage(content=prompt)
    ])

    plan_text = response.content

    # =========================
    # Basic plan parsing
    # =========================
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

    sorted_answers = sorted(state["agent_answers"], key=lambda x: x["index"])
    formatted_answers = "\n".join(
        f"Answer {i}:\n{ans['answer']}"
        for i, ans in enumerate(sorted_answers, start=1)
    )

    user_message = HumanMessage(content=(
        f"Original user question: {state['originalQuery']}\n"
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