# ai_core/memory/thread_manager.py

from typing import Dict, Optional


class ThreadManager:
    """
    Manages conversation threads and summaries.
    Production: Replace with Redis / DB persistence.
    """

    def __init__(self):
        self._store: Dict[str, str] = {}

    def get_summary(self, user_id: str) -> Optional[str]:
        return self._store.get(user_id)

    def save_summary(self, user_id: str, summary: str) -> None:
        self._store[user_id] = summary