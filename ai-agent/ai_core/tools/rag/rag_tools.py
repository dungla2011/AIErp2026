from typing import List
from langchain_core.tools import tool
from knowledge.stores.parent_store.parent_store_manager import ParentStoreManager


class RagTools:

    def __init__(self, collection):

        self.collection = collection
        self.parent_store_manager = ParentStoreManager()

    # ==========================
    # CHILD CHUNK SEARCH
    # ==========================
    @tool
    def _search_child_chunks(self, query: str, limit: int = 5) -> str:
        """
        Search relevant child chunks from the vector database using similarity search.
        Returns formatted chunks including parent_id, file name, and content.
        """

        try:

            results = self.collection.similarity_search(query, k=limit)

            if not results:
                return "NO_RELEVANT_CHUNKS"

            formatted = []

            for doc in results:

                formatted.append(
                    f"Parent ID: {doc.metadata.get('parent_id', '')}\n"
                    f"File Name: {doc.metadata.get('source', '')}\n"
                    f"Content: {doc.page_content.strip()}"
                )

            return "\n\n".join(formatted)

        except Exception as e:

            return f"RETRIEVAL_ERROR: {str(e)}"

    # ==========================
    # PARENT RETRIEVAL
    # ==========================
    @tool
    def _retrieve_parent_chunks(self, parent_id: str) -> str:

        """
        Retrieve the full parent document using the parent_id from the parent store.
        """

        try:

            parent = self.parent_store_manager.load_content(parent_id)

            if not parent:
                return "NO_PARENT_DOCUMENT"

            return (
                f"Parent ID: {parent.get('parent_id', 'n/a')}\n"
                f"File Name: {parent.get('metadata', {}).get('source', 'unknown')}\n"
                f"Content: {parent.get('content', '').strip()}"
            )

        except Exception as e:

            return f"PARENT_RETRIEVAL_ERROR: {str(e)}"

    # ==========================
    # TOOL EXPORT
    # ==========================

    def get_tools(self) -> List:

        return [
            tool("search_child_chunks")(self._search_child_chunks),
            tool("retrieve_parent_chunks")(self._retrieve_parent_chunks),
        ]