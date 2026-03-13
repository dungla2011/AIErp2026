# ai_core/graph/router.py

from typing import Literal
from langgraph.types import Send
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from .state import State, AgentState
from config import MAX_ITERATIONS, MAX_TOOL_CALLS

############################################################
# QUERY ROUTER
# kiểm tra query hợp lệ trước khi pipeline chạy
############################################################
def query_router(state: State) -> Literal["process", "fallback_response"]:

    query = state.get("originalQuery")

    if not query and state.get("messages"):
        query = state["messages"][-1].content

    if not query or len(query.strip()) == 0:
        return "fallback_response"

    return "process"

############################################################
# AGENT ROUTER (LLM classification nếu analyzer chưa rõ)
############################################################
def agent_router(state: State, llm):

    print("🟢 NODE → agent_router")

    analysis = state.get("analysis")
    # 1️. Use analysis result first
    if analysis and analysis.target_agent:

        domain = analysis.target_agent

        if domain.endswith("_agent"):
            domain = domain.replace("_agent", "")

        return {
            "agent_domain": domain
        }

    # 2️. fallback LLM classification
    query = analysis.query if analysis and analysis.query else None

    if not query and state.get("messages"):
        query = state["messages"][-1].content

    prompt = f"""
            Classify this ERP query.

            Query:
            {query}

            Choose ONE:

            accounting
            inventory
            audit
            """

    response = llm.invoke([
        HumanMessage(content=prompt)
    ])

    domain = response.content.strip().lower()

    if domain not in ["accounting", "inventory", "audit"]:
        domain = "accounting"

    return {
        "agent_domain": domain
    }

############################################################
# AGENT DOMAIN ROUTER
############################################################
def route_agent(state: State) -> Literal["accounting", "inventory", "audit"]:

    analysis = state.get("analysis")

    # 1️. analyzer priority
    if analysis and analysis.target_agent:

        domain = analysis.target_agent

        if domain.endswith("_agent"):
            domain = domain.replace("_agent", "")

        print("ROUTER → analysis:", domain)

        if domain in ["accounting", "inventory", "audit"]:
            return domain

    # 2️. fallback router result        
    domain = state.get("agent_domain")

    print("ROUTER → fallback:", domain)

    if domain in ["accounting", "inventory", "audit"]:
        return domain

    return "accounting"

############################################################
# RAG ROUTER
############################################################
def rag_router(state: State) -> Literal["rag", "no_rag"]:

    analysis = state.get("analysis")

    if analysis and getattr(analysis, "use_rag", False):
        return "rag"

    return "no_rag"

############################################################
# ROUTER AFTER QUERY REWRITE
############################################################
def route_after_rewrite(state: State) -> Literal["request_clarification", "agent"]:

    if not state.get("questionIsClear", True):
        return "request_clarification"

    return "agent"

############################################################
# LOOP GUARD (anti infinite loop)
############################################################
def loop_guard(state: AgentState) -> bool:

    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        return False

    if state.get("tool_call_count", 0) > MAX_TOOL_CALLS:
        return False

    return True

############################################################
# TOOL ROUTER
############################################################
def tool_router(state: AgentState) -> Literal["tools", "fallback_response", "final"]:

    if not loop_guard(state):
        return "fallback_response"

    if not state.get("messages"):
        return "fallback_response"

    last = state["messages"][-1]

    # 1️. standard tool call
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        if len(last.tool_calls) > 0:
            return "tools"

    # 2️. function call fallback
    if isinstance(last, AIMessage) and getattr(last, "additional_kwargs", None):
        if "tool_calls" in last.additional_kwargs:
            return "tools"

        if "function_call" in last.additional_kwargs:
            return "tools"

    # 3️. planner hint
    plan = state.get("plan", "").lower()

    tool_keywords = ["erp", "database", "rag", "query", "lookup"]

    if any(k in plan for k in tool_keywords):
        return "tools"

    return "final"

############################################################
# ROUTER AFTER TOOL
############################################################
def route_after_tool(state: AgentState):

    tool_messages = [m for m in state["messages"] if isinstance(m, ToolMessage)]

    if tool_messages:
        last_tool = tool_messages[-1]
        if "NO_RELEVANT" in last_tool.content:
            return "fallback_response"

    return "should_compress_context"

############################################################
# AFTER CONTEXT COMPRESSION
############################################################
def route_after_compression(state: AgentState):
    return "orchestrator"   

def route_after_orchestrator_call(state: AgentState):
    # stop condition
    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        return "fallback_response"

    if state.get("tool_call_count", 0) > MAX_TOOL_CALLS:
        return "fallback_response"

    if not state.get("messages"):
        return "fallback_response"
    
    last = state["messages"][-1]

    # 1️. Standard LangChain tool call
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        if len(last.tool_calls) > 0:
            return "tools"

    # 2️. Some models return function_call instead
    if isinstance(last, AIMessage) and getattr(last, "additional_kwargs", None):
        if "tool_calls" in last.additional_kwargs:
            return "tools"
        if "function_call" in last.additional_kwargs:
            return "tools"

    # 3️. Fallback using planner hint
    plan = state.get("plan", "").lower()

    tool_keywords = ["erp", "database", "rag", "query", "lookup"]

    if any(k in plan for k in tool_keywords):
        return "tools"

    return "fallback_response"


