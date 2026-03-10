# Mục tiêu: nếu câu hỏi giống về ngữ nghĩa → trả lời từ cache, giảm latency và chi phí LLM.

from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import numpy as np


class SemanticCache:
    """
    Semantic cache using embeddings similarity
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en",
        similarity_threshold: float = 0.92
    ):
        self.embedder = SentenceTransformer(model_name)
        self.similarity_threshold = similarity_threshold

        self.cache_embeddings = []
        self.cache_data = []

    def _cosine_similarity(self, a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def get(self, query: str) -> Optional[str]:

        if not self.cache_embeddings:
            return None

        query_emb = self.embedder.encode(query)

        best_score = 0
        best_idx = -1

        for idx, emb in enumerate(self.cache_embeddings):

            score = self._cosine_similarity(query_emb, emb)

            if score > best_score:
                best_score = score
                best_idx = idx

        if best_score >= self.similarity_threshold:
            return self.cache_data[best_idx]["answer"]

        return None

    def add(self, query: str, answer: str):

        emb = self.embedder.encode(query)

        self.cache_embeddings.append(emb)

        self.cache_data.append({
            "query": query,
            "answer": answer
        })