# ai_core/memory/conversation_memory.py

from typing import Optional
from .thread_manager import ThreadManager


class ConversationMemory:
    """
    High-level conversation memory abstraction.
    Responsible for loading and saving summarized memory per user.
    """

    def __init__(self):
        self.thread_manager = ThreadManager()

    def load(self, user_id: str) -> Optional[str]:
        """
        Load summarized conversation memory for a user.
        """
        if not user_id:
            return None

        return self.thread_manager.get_summary(user_id)

    def save(self, user_id: str, summary: str) -> None:
        """
        Persist updated conversation summary.
        """
        if not user_id or not summary:
            return

        self.thread_manager.save_summary(user_id, summary)