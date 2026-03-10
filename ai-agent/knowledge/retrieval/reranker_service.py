# Mục tiêu: sắp xếp lại kết quả retrieval theo độ liên quan thực sự (cross-encoder)
# ➡️ Thường tăng accuracy 30–50% so với chỉ vector search

from typing import List, Dict
from sentence_transformers import CrossEncoder


class RerankerService:
    """
    Cross-encoder reranker for RAG retrieval results
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        top_k: int = 5
    ):
        self.model = CrossEncoder(model_name)
        self.top_k = top_k

    def rerank(
        self,
        query: str,
        documents: List[Dict]
    ) -> List[Dict]:
        """
        documents format:
        [
            {
                "content": "...",
                "metadata": {...},
                "parent_id": "..."
            }
        ]
        """

        if not documents:
            return []

        pairs = [[query, doc["content"]] for doc in documents]

        scores = self.model.predict(pairs)

        for doc, score in zip(documents, scores):
            doc["score"] = float(score)

        ranked = sorted(documents, key=lambda x: x["score"], reverse=True)

        return ranked[: self.top_k]