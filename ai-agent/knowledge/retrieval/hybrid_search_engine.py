# Hybrid search = Dense + Sparse (BM25) + Metadata filter

from typing import List, Dict, Optional
from qdrant_client.http import models as qmodels


class HybridSearchEngine:
    """
    Hybrid search using dense + sparse embeddings with optional metadata filter
    """

    def __init__(self, vector_store, top_k: int = 10):
        """
        vector_store: QdrantVectorStore instance
        """
        self.vector_store = vector_store
        self.top_k = top_k

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        metadata_filter: Optional[Dict] = None
    ) -> List[Dict]:

        k = top_k or self.top_k

        search_kwargs = {"k": k}

        if metadata_filter:
            filters = []

            for key, value in metadata_filter.items():
                filters.append(
                    qmodels.FieldCondition(
                        key=f"metadata.{key}",
                        match=qmodels.MatchValue(value=value)
                    )
                )

            search_kwargs["filter"] = qmodels.Filter(must=filters)

        results = self.vector_store.similarity_search_with_score(
            query,
            **search_kwargs
        )

        documents = []

        for doc, score in results:

            documents.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": float(score),
                "parent_id": doc.metadata.get("parent_id")
            })

        return documents