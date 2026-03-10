# Mục tiêu: thêm knowledge graph retrieval (GraphRAG).
# GraphRAG giúp tìm:
#   Entity → relationship → document
# Ví dụ:
#   VAT tax → regulation → document

import networkx as nx
from typing import List, Dict

class GraphRAG:

    def __init__(self):
        self.graph = nx.Graph()

    def add_triplet(self, subject: str, relation: str, obj: str, source_doc: str):

        self.graph.add_edge(
            subject,
            obj,
            relation=relation,
            source=source_doc
        )

    def build_from_documents(self, documents: List[Dict]):

        for doc in documents:
            text = doc["content"]
            words = text.split()

            if len(words) < 3:
                continue

            subject = words[0]
            relation = words[1]
            obj = words[2]

            source = doc["metadata"].get("source")
            self.add_triplet(subject, relation, obj, source)

    def query(self, entity: str, depth: int = 2):

        if entity not in self.graph:
            return []

        nodes = nx.single_source_shortest_path_length(
            self.graph,
            entity,
            cutoff=depth
        )

        results = []

        for node in nodes:

            for neighbor in self.graph.neighbors(node):
                edge = self.graph.get_edge_data(node, neighbor)
                results.append({
                    "subject": node,
                    "relation": edge["relation"],
                    "object": neighbor,
                    "source": edge["source"]
                })

        return results