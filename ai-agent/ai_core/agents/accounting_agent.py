def accounting_agent(state, llm):

    question = state["originalQuery"]

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