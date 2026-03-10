from sentence_transformers import CrossEncoder
from ai_core.models.reranker.base_reranker import BaseReranker


class CrossEncoderReranker(BaseReranker):

    def __init__(self, model_name: str):
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, documents: list):
        pairs = [[query, doc] for doc in documents]
        scores = self.model.predict(pairs)

        ranked = sorted(
            zip(documents, scores),
            key=lambda x: x[1],
            reverse=True
        )

        return [doc for doc, _ in ranked]