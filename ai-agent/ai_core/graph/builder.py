#############################################################################
# Production Pipeline của builder.py
# START
#  ↓
# load_memory
#  ↓
# analyze_query
#  ↓
# summarize_history
#  ↓
# rewrite_query
#  ↓
# agent_router
#  ↓
# domain_agent
#  ↓
# planner
#  ↓
# orchestrator
#  ↓
# tool_executor
#  ↓
# compress_context
#  ↓
# orchestrator (loop)
#  ↓
# fallback_response
#  ↓
# collect_answer
#  ↓
# aggregate_answers
#  ↓
# save_memory
#  ↓
# END
#############################################################################

from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolNode
from functools import partial
from ai_core.graph.nodes import (
    accounting_node,
    inventory_node,
    audit_node
)

from .state import State, AgentState
from .nodes import *
from .router import *


def create_agent_graph(llm, tools_list):

    tool_node = ToolNode(tools_list)

    graph_builder = StateGraph(State)

    # ======================
    # MEMORY
    # ======================

    graph_builder.add_node("load_memory", load_memory)
    graph_builder.add_node("save_memory", save_memory)

    # ======================
    # QUERY PREPROCESS
    # ======================
    graph_builder.add_node("analyze_query", partial(analyze_query, llm=llm))
    graph_builder.add_node("summarize_history", partial(summarize_history, llm=llm))
    graph_builder.add_node("rewrite_query", partial(rewrite_query, llm=llm))

    # ======================
    # ROUTER
    # ======================

    graph_builder.add_node("agent_router", partial(agent_router, llm=llm))

    # ======================
    # DOMAIN AGENTS
    # ======================

    graph_builder.add_node("accounting_agent", partial(accounting_node, llm=llm))
    graph_builder.add_node("inventory_agent", partial(inventory_node, llm=llm))
    graph_builder.add_node("audit_agent", partial(audit_node, llm=llm))

    # ======================
    # PLANNER
    # ======================

    graph_builder.add_node("planner", partial(planner, llm=llm))

    # ======================
    # ORCHESTRATOR
    # ======================

    graph_builder.add_node(
        "orchestrator",
        partial(orchestrator, llm=llm)
    )

    # ======================
    # TOOL BUS
    # ======================

    graph_builder.add_node("tool_executor", tool_node)

    # ======================
    # RESPONSE
    # ======================
    graph_builder.add_node("fallback_response", partial(fallback_response, llm=llm))
    graph_builder.add_node("compress_context", partial(compress_context, llm=llm))
    graph_builder.add_node("collect_answer", collect_answer)
    graph_builder.add_node("aggregate_answers", partial(aggregate_answers, llm=llm))
    graph_builder.add_node("request_clarification", partial(request_clarification, llm=llm))

    # ======================
    # FLOW
    # ======================

    graph_builder.add_edge(START, "load_memory")
    graph_builder.add_edge("load_memory", "analyze_query")
    graph_builder.add_edge("analyze_query", "summarize_history")
    graph_builder.add_edge("summarize_history", "rewrite_query")
    
    graph_builder.add_conditional_edges(
        "rewrite_query",
        route_after_rewrite,
        {
            "request_clarification": "request_clarification",
            "agent": "agent_router"
        }
    )
    graph_builder.add_edge("request_clarification", "collect_answer")

    # ======================
    # AGENT ROUTING
    # ======================

    graph_builder.add_conditional_edges(
        "agent_router",
        route_agent,
        {
            "accounting": "accounting_agent",
            "inventory": "inventory_agent",
            "audit": "audit_agent",
        },
    )

    # ======================
    # DOMAIN → PLANNER
    # ======================

    graph_builder.add_edge("accounting_agent", "planner")
    graph_builder.add_edge("inventory_agent", "planner")
    graph_builder.add_edge("audit_agent", "planner")

    # ======================
    # PLANNER → ORCHESTRATOR
    # ======================

    graph_builder.add_edge("planner", "orchestrator")

    # ======================
    # ORCHESTRATOR ROUTING: orchestrator → tool
    # ======================
    
    graph_builder.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator_call,
        {
            "tools": "tool_executor",
            "fallback_response": "fallback_response",
            "final": "collect_answer"
        }
    )


    # ======================
    # FALLBACK
    # ======================
    graph_builder.add_edge("fallback_response", "collect_answer")

    # ======================
    # TOOL LOOP
    # ======================
    # tool → orchestrator loop
    graph_builder.add_edge("tool_executor", "compress_context")
    graph_builder.add_edge("compress_context", "orchestrator")

    # ======================
    # FINAL RESPONSE
    # ======================

    graph_builder.add_edge("collect_answer", "aggregate_answers")
    graph_builder.add_edge("aggregate_answers", "save_memory")
    graph_builder.add_edge("save_memory",END)

    return graph_builder.compile(
        checkpointer=InMemorySaver()
    )