# Mục tiêu: LLM tự kiểm chứng câu trả lời có được hỗ trợ bởi context hay không.
# Ý tưởng:
#       Query
#       Context docs
#       Answer
#       ↓ LLM kiểm tra
#       Supported / Not supported

import requests
from typing import Dict


class AnswerVerifier:

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        ollama_url: str = "http://localhost:11434/api/generate"
    ):
        self.model = model
        self.url = ollama_url

    def verify(self, query: str, context: str, answer: str) -> Dict:

        prompt = f"""
You are a fact-checking system.

Question:
{query}

Context:
{context}

Answer:
{answer}

Task:
Check if the answer is fully supported by the context.

Respond in JSON format:

{{
 "supported": true/false,
 "confidence": 0-1,
 "explanation": "short explanation"
}}
"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        r = requests.post(self.url, json=payload)

        if r.status_code != 200:
            return {"supported": False, "confidence": 0}

        text = r.json()["response"]

        try:
            import json
            return json.loads(text)
        except Exception:
            return {"supported": False, "confidence": 0}