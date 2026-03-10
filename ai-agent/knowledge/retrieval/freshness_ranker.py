# Mục tiêu: ưu tiên tài liệu mới hơn.
# Ví dụ metadata document:
# {
#  "source": "law_document",
#  "timestamp": "2024-11-02"
# }
from typing import List, Dict
from datetime import datetime


class FreshnessRanker:
    """
    Rank documents by freshness + relevance score
    """

    def __init__(self, freshness_weight: float = 0.2):
        self.freshness_weight = freshness_weight

    def _freshness_score(self, timestamp: str):

        try:
            doc_time = datetime.fromisoformat(timestamp)
        except Exception:
            return 0

        now = datetime.utcnow()

        age_days = (now - doc_time).days

        return max(0, 1 - age_days / 365)

    def rerank(self, documents: List[Dict]) -> List[Dict]:

        for doc in documents:

            base_score = doc.get("score", 0)

            metadata = doc.get("metadata", {})

            timestamp = metadata.get("timestamp")

            freshness = self._freshness_score(timestamp) if timestamp else 0

            final_score = base_score + self.freshness_weight * freshness

            doc["final_score"] = final_score

        ranked = sorted(documents, key=lambda x: x["final_score"], reverse=True)

        return ranked