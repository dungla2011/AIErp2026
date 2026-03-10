# Agent tự sinh nhiều query để tăng recall
# Example:
# User query: "chính sách hoàn thuế"
# Generated queries:
# - quy định hoàn thuế VAT
# - điều kiện hoàn thuế doanh nghiệp
# - thủ tục hoàn thuế
# - chính sách hoàn thuế Việt Nam
# - VAT refund regulation

import requests
from typing import List


class MultiQueryRetriever:
    """
    Generate multiple queries to improve recall
    """

    def __init__(
        self,
        model: str = "qwen2.5:3b",
        ollama_url: str = "http://localhost:11434/api/generate",
        num_queries: int = 5
    ):
        self.model = model
        self.url = ollama_url
        self.num_queries = num_queries

    def generate_queries(self, query: str) -> List[str]:

        prompt = f"""
Generate {self.num_queries} different search queries related to the question.

Question:
{query}

Queries:
"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        r = requests.post(self.url, json=payload)

        if r.status_code != 200:
            return [query]

        text = r.json()["response"]

        queries = []

        for line in text.split("\n"):

            line = line.strip("- ").strip()

            if line:
                queries.append(line)

        if not queries:
            return [query]

        return queries[: self.num_queries]

    def retrieve(
        self,
        query: str,
        search_engine,
        metadata_filter=None
    ):

        queries = self.generate_queries(query)

        results = []

        for q in queries:

            docs = search_engine.search(
                q,
                metadata_filter=metadata_filter
            )

            results.extend(docs)

        # remove duplicates
        seen = set()
        unique_docs = []

        for doc in results:

            key = doc["content"][:100]

            if key not in seen:
                seen.add(key)
                unique_docs.append(doc)

        return unique_docs