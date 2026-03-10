def inventory_agent(state, llm):

    question = state["originalQuery"]

    response = llm.invoke(
        f"""
You are an ERP Inventory AI agent.

User question:
{question}

Understand the inventory request and prepare reasoning
for the planner.
"""
    )

    return {
        "agent_reasoning": response.content,
        "agent_type": "inventory"
}