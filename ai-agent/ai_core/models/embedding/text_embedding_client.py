import requests
from typing import List
from ai_core.models.base.circuit_breaker import CircuitBreaker
from ai_core.models.embedding.base_embedding import BaseEmbedding


class OllamaTextEmbedding(BaseEmbedding):

    def __init__(self, model, base_url="http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.breaker = CircuitBreaker()

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def _embed(self, text):
        if not self.breaker.call_allowed():
            raise RuntimeError("Embedding circuit open")

        payload = {
            "model": self.model,
            "prompt": text
        }

        response = requests.post(
            f"{self.base_url}/api/embeddings",
            json=payload,
            timeout=60
        )

        response.raise_for_status()
        self.breaker.record_success()
        return response.json()["embedding"]