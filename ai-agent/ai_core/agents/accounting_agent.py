def accounting_agent(state, llm):

    question = state.get("originalQuery") or state["messages"][-1].content

    response = llm.invoke(
        f"""
    You are an ERP Accounting AI agent.

    User question:
    {question}

    Your task:
    Understand accounting intent and prepare structured reasoning
    for the planner.
    """
    )

    return {
        "agent_reasoning": response.content,
        "agent_type": "accounting"
    }