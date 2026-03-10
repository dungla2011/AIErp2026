# Mục tiêu: trả lời kèm nguồn chính xác.
# Ví dụ output:
#  Theo tài liệu luật thuế [1], doanh nghiệp được hoàn thuế nếu ...
# Sources:
# [1] tax_law_2023.pdf
# [2] VAT_guideline.pdf

from typing import List, Dict

class CitationEngine:
    """
    Attach citations to answer
    """

    def __init__(self, parent_store):
        # lưu lại parent document store
        self.parent_store = parent_store

    def build_context(self, documents: List[Dict]):

        context_parts = []
        sources = []

        for idx, doc in enumerate(documents, start=1):

            content = doc["content"]
            source = doc["metadata"].get("source", "unknown")
            context_parts.append(f"[{idx}] {content}")

            sources.append({
                "index": idx,
                "source": source
            })

        context = "\n\n".join(context_parts)

        return context, sources

    def format_answer(self, answer: str, sources: List[Dict]):
        citation_lines = []

        for src in sources:
            citation_lines.append(f"[{src['index']}] {src['source']}")

        citations = "\n".join(citation_lines)

        return f"{answer}\n\nSources:\n{citations}"