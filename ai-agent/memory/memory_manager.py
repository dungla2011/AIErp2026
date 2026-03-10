# memory/memory_manager.py

from typing import Optional, Dict


class MemoryManager:
    def __init__(self):
        # Demo: in-memory store
        # Production: thay bằng Redis / Postgres
        self.store: Dict[str, str] = {}

    def load_user_memory(self, user_id: str) -> Optional[str]:
        return self.store.get(user_id)

    def save_user_memory(self, user_id: str, content: str):
        self.store[user_id] = content


# Singleton instance
memory_manager = MemoryManager()