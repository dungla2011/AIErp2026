from typing import List, Dict

from typer.cli import docs
from knowledge.retrieval.hybrid_search_engine import HybridSearchEngine
from knowledge.retrieval.multi_query_retriever import MultiQueryRetriever
from knowledge.retrieval.reranker_service import RerankerService
from knowledge.retrieval.context_compressor import ContextCompressor

from knowledge.retrieval.freshness_ranker import FreshnessRanker
from knowledge.cache.semantic_cache import SemanticCache
from knowledge.citation.citation_engine import CitationEngine

from knowledge.verification.answer_verifier import AnswerVerifier
from knowledge.verification.hallucination_detector import HallucinationDetector

from knowledge.graph.graph_retriever import GraphRetriever
from knowledge.retrieval.query_rewriter import QueryRewriter


class RAGAgentController:
    """
    Enterprise RAG Controller
    """

    def __init__(
        self,
        llm,
        vector_db,
        parent_store
    ):
        self.llm = llm

        self.cache = SemanticCache()

        self.query_rewriter = QueryRewriter(llm)

        self.hybrid_search = HybridSearchEngine(vector_db)

        self.multi_query = MultiQueryRetriever(llm)

        self.reranker = RerankerService()

        self.compressor = ContextCompressor()

        self.freshness_ranker = FreshnessRanker()

        self.graph_retriever = GraphRetriever()
        self.graph_retriever.build_from_parent_store(parent_store)

        self.verifier = AnswerVerifier(llm)

        self.hallucination_detector = HallucinationDetector()

        self.citation_engine = CitationEngine(parent_store)

    def answer(self, query: str) -> Dict:
        """
        Main RAG pipeline
        """

        # 1️⃣ Semantic Cache
        cached = self.cache.lookup(query)
        if cached:
            return cached

        # 2️⃣ Rewrite Query
        rewritten_query = self.query_rewriter.rewrite(query)

        # 3️⃣ Multi Query Expansion
        queries = self.multi_query.generate_queries(rewritten_query)

        # 4️⃣ Retrieval
        docs = []

        for q in queries:
            docs.extend(self.hybrid_search.search(q))

        # 5️⃣ Graph Retrieval (if needed)
        if self._needs_graph_reasoning(query):
            graph_docs = self.graph_retriever.retrieve(query)
            docs.extend(graph_docs)

        # 6️⃣ Rerank
        docs = self.reranker.rerank(query, docs)

        # 7️⃣ Freshness Ranking
        docs = self.freshness_ranker.rank(docs)

        # 8️⃣ Build citation context
        context, sources = self.citation_engine.build_context(docs)

        # 9️⃣ Generate Answer
        answer = self.llm.invoke(
            f"""
            Answer the question based on context.

            Question:
            {query}

            Context:
            {context}
            """
        )

        answer_text = answer.content

        # 🔟 Verification
        verified = self.verifier.verify(query, answer_text)

        # 11️⃣ Hallucination Detection
        hallucination = self.hallucination_detector.detect(answer_text, docs)

        if hallucination["hallucination_score"] < 0.6:
            answer_text = self._self_correct(query, docs)

        # 12️⃣ Format answer with citations
        final_answer = self.citation_engine.format_answer(
            answer_text,
            sources
        )

        result = {
            "answer": final_answer,
            "sources": sources
        }

        # 13️⃣ Cache result
        self.cache.store(query, result)

        return result

    def _needs_graph_reasoning(self, query: str) -> bool:
        """
        Detect multi-hop question
        """

        keywords = [
            "relationship",
            "connection",
            "who works with",
            "dependency",
        ]

        for k in keywords:
            if k in query.lower():
                return True

        return False

    def _self_correct(self, query, docs):

        context = self.compressor.compress(query, docs)

        answer = self.llm.invoke(
            f"""
            The previous answer may contain hallucination.

            Re-answer carefully using only the context.

            Question:
            {query}

            Context:
            {context}
            """
        )

        return answer.content