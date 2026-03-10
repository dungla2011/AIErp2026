# Mục tiêu: rewrite câu hỏi để retrieval tốt hơn
# Example: 
#   User: "chính sách hoàn thuế"
#   Rewrite: "quy định hoàn thuế VAT cho doanh nghiệp tại Việt Nam"

import requests


class QueryRewriter:
    """
    Rewrite user query for better retrieval
    """

    def __init__(
        self,
        model: str = "qwen2.5:3b",
        ollama_url: str = "http://localhost:11434/api/generate"
    ):
        self.model = model
        self.url = ollama_url

    def rewrite(self, query: str) -> str:

        prompt = f"""
Rewrite the following question to improve semantic search.

Original question:
{query}

Rewrite query:
"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        r = requests.post(self.url, json=payload)

        if r.status_code != 200:
            return query

        text = r.json()["response"].strip()

        return text if text else query