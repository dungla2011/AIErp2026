# Mục tiêu: giảm token context trước khi đưa vào LLM.
#           ➡️ Có thể giảm 60–80% token.

import requests
from typing import List, Dict


class ContextCompressor:
    """
    Compress retrieved documents before sending to LLM
    """

    def __init__(
        self,
        model: str = "qwen2.5:3b",
        ollama_url: str = "http://localhost:11434/api/generate",
        max_docs: int = 5
    ):
        self.model = model
        self.url = ollama_url
        self.max_docs = max_docs

    def compress(
        self,
        query: str,
        documents: List[Dict]
    ) -> str:

        documents = documents[: self.max_docs]

        context = "\n\n".join([doc["content"] for doc in documents])

        prompt = f"""
Extract only the information relevant to the question.

Question:
{query}

Documents:
{context}

Relevant information:
"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        r = requests.post(self.url, json=payload)

        if r.status_code != 200:
            return context

        return r.json()["response"]