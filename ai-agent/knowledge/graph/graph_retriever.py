from typing import List, Dict
from knowledge.graph.graph_rag import GraphRAG


class GraphRetriever:
    """
    Graph Retrieval layer for GraphRAG
    Used by RAGAgentController
    """

    def __init__(self):
        self.graph = GraphRAG()
        self.graph_built = False

    # ===============================
    # Build Graph
    # ===============================
    def build_graph(self, documents: List[Dict]):
        """
        Build knowledge graph from documents
        """

        if not documents:
            return

        self.graph.build_from_documents(documents)
        self.graph_built = True

    # ===============================
    # Build Graph from ParentStore
    # ===============================
    def build_from_parent_store(self, parent_store):
        """
        Build graph automatically from parent store
        """

        docs = []

        try:
            files = parent_store.list_all()
        except:
            files = []

        for file in files:
            try:
                docs.append(parent_store.load_content(file))
            except:
                continue

        if docs:
            self.build_graph(docs)

    # ===============================
    # Entity Extraction
    # ===============================
    def _extract_entity(self, query: str) -> str:
        """
        Very simple entity extraction
        (production nên dùng NER)
        """

        words = query.split()

        if not words:
            return ""

        return words[0]

    # ===============================
    # Retrieve
    # ===============================
    def retrieve(
        self,
        query: str,
        depth: int = 2,
        top_k: int = 10
    ) -> List[Dict]:
        """
        Query graph for related entities
        """

        if not self.graph_built:
            return []

        entity = self._extract_entity(query)

        if not entity:
            return []

        results = self.graph.query(entity, depth)

        return results[:top_k]