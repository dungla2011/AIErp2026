# ai_core/memory/checkpoint.py

from langgraph.checkpoint.memory import InMemorySaver


def get_checkpointer():
    """
    Centralized checkpoint configuration.
    Replace with persistent checkpointer if needed.
    """
    return InMemorySaver()