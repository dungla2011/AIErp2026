from typing import List, Dict
from knowledge.stores.parent_store.parent_store_manager import ParentStoreManager
from langchain.schema import Document


class RetrieverService:

    def __init__(self, vector_store, parent_store: ParentStoreManager):
        self.vector_store = vector_store
        self.parent_store = parent_store

    def retrieve(
        self,
        query: str,
        k: int = 8
    ) -> List[Dict]:
        """
        Retrieve parent documents from query
        """

        child_docs: List[Document] = self.vector_store.similarity_search(
            query,
            k=k
        )

        parent_ids = []

        for doc in child_docs:
            parent_id = doc.metadata.get("parent_id")

            if parent_id:
                parent_ids.append(parent_id)

        parents = self.parent_store.load_content_many(parent_ids)

        return parents

    def retrieve_context(
        self,
        query: str,
        k: int = 8
    ) -> str:
        """
        Return formatted context for LLM
        """

        parents = self.retrieve(query, k)

        context_blocks = []

        for p in parents:

            content = p["content"]

            context_blocks.append(content)

        return "\n\n".join(context_blocks)