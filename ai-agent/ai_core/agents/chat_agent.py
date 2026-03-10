from schemas.query_schema import QueryAnalysis

class ChatAgent:

    def analyze_query(self, query: str) -> QueryAnalysis:

        query_lower = query.lower()

        if "tồn kho" in query_lower:
            return QueryAnalysis(
                query=query,
                intent="inventory_query",
                target_agent="inventory_agent",
                use_tools=True
            )

        if "sổ cái" in query_lower or "kế toán" in query_lower:
            return QueryAnalysis(
                query=query,
                intent="accounting_query",
                target_agent="accounting_agent",
                use_tools=True
            )

        return QueryAnalysis(
            query=query,
            intent="general",
            target_agent="rag_agent"
        )