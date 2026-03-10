import uuid
from typing import Dict

import config

from ai_core.models.chat.ollama_client import OllamaClient
from ai_core.agents.rag_agent_controller import RAGAgentController

from ai_core.tools.factory import ToolFactory
from ai_core.graph.builder import create_agent_graph

from knowledge.stores.vector_store.vector_db_manager import VectorDbManager
from knowledge.stores.parent_store.parent_store_manager import ParentStoreManager

from knowledge.ingestion.chunker import DocumentChunker


class RAGSystem:
    """
    Enterprise RAG System

    Responsibilities:
    - Initialize LLM
    - Manage Vector DB
    - Manage Parent Store
    - Initialize RAG Agent Controller
    - Initialize LangGraph Agent
    """

    def __init__(self, collection_name=config.CHILD_COLLECTION):

        self.collection_name = collection_name

        self.vector_db = VectorDbManager()
        self.parent_store = ParentStoreManager()

        self.chunker = DocumentChunker()

        self.llm = None
        self.agent_controller = None
        self.agent_graph = None

        self.thread_id = str(uuid.uuid4())
        self.recursion_limit = 50

    # =========================================
    # Initialize system
    # =========================================

    def initialize(self):

        # create vector collection
        self.vector_db.create_collection(self.collection_name)

        collection = self.vector_db.get_collection(self.collection_name)

        # initialize LLM
        self.llm = OllamaClient(
            model=config.LLM_MODEL,
            base_url=config.OLLAMA_URL,
            temperature=0
        )

        # initialize RAG controller
        self.agent_controller = RAGAgentController(
            llm=self.llm,
            vector_db=collection,
            parent_store=self.parent_store
        )

        # build knowledge graph if possible
        try:
            self.agent_controller.graph_retriever.build_from_parent_store(
                self.parent_store
            )
        except Exception as e:
            print("Graph build skipped:", e)

        # build tools for agent
        tools = ToolFactory(self.agent_controller).create_tools()

        # build LangGraph agent
        self.agent_graph = create_agent_graph(self.llm, tools)

    # =========================================
    # Ask question
    # =========================================

    def ask(self, query: str) -> Dict:

        if not self.agent_graph:
            raise Exception("RAG system not initialized")

        config = self.get_config()

        result = self.agent_graph.invoke(
            {"input": query},
            config=config
        )

        return result

    # =========================================
    # Agent config
    # =========================================

    def get_config(self):

        return {
            "configurable": {
                "thread_id": self.thread_id
            },
            "recursion_limit": self.recursion_limit
        }

    # =========================================
    # Reset conversation
    # =========================================

    def reset_thread(self):

        try:
            self.agent_graph.checkpointer.delete_thread(self.thread_id)
        except Exception as e:
            print(f"Warning: Could not delete thread {self.thread_id}: {e}")

        self.thread_id = str(uuid.uuid4())

    # =========================================
    # Clear knowledge
    # =========================================

    def clear_knowledge(self):

        try:
            self.vector_db.delete_collection(self.collection_name)
        except:
            pass

        try:
            self.parent_store.clear_store()
        except:
            pass

        self.vector_db.create_collection(self.collection_name)