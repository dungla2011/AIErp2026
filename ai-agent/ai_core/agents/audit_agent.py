def audit_agent(state, llm):

    question = state["originalQuery"]

    response = llm.invoke(
        f"""
You are an ERP Audit AI agent.

User question:
{question}

Understand the audit request and prepare reasoning
for the planner.
"""
    )

    return {
        "agent_reasoning": response.content,
        "agent_type": "audit"
}