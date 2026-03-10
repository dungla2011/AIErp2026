from pathlib import Path
from typing import List, Dict

from knowledge.ingestion.chunker import DocumentChunker
from knowledge.stores.parent_store.parent_store_manager import ParentStoreManager
from knowledge.stores.vector_store.vector_db_manager import VectorDbManager
from knowledge.graph.graph_retriever import GraphRetriever

from knowledge.ingestion.loaders.pdf_loader import load_pdf
from knowledge.ingestion.loaders.docx_loader import load_docx
from knowledge.ingestion.loaders.html_loader import load_html
from knowledge.ingestion.loaders.csv_loader import load_csv

import config


class DocumentIngestionPipeline:
    """
    Production Document Ingestion Pipeline
    """

    def __init__(self, collection_name=config.CHILD_COLLECTION):

        self.vector_db_manager = VectorDbManager()
        self.parent_store = ParentStoreManager()

        self.vector_store = self.vector_db_manager.get_collection(collection_name)

        self.chunker = DocumentChunker()

        self.graph_builder = GraphRetriever()

    # ====================================
    # Main Ingest Entry
    # ====================================

    def ingest_directory(self, directory: str):

        path = Path(directory)

        files = list(path.glob("**/*"))

        for file in files:

            if file.is_file():

                try:
                    self.ingest_file(str(file))
                except Exception as e:
                    print("Failed ingest:", file, e)

    # ====================================
    # File Ingest
    # ====================================

    def ingest_file(self, file_path: str):

        ext = file_path.lower().split(".")[-1]

        documents = []

        if ext == "pdf":
            documents = load_pdf(file_path)

        elif ext == "docx":
            documents = load_docx(file_path)

        elif ext == "html":
            documents = load_html(file_path)

        elif ext == "csv":
            documents = load_csv(file_path)

        else:
            print("Unsupported file:", file_path)
            return

        if not documents:
            return

        parents, children = self.chunker.split_documents(documents)

        self._store_parents(parents)

        self._store_children(children)

        self._build_graph(parents)

    # ====================================
    # Parent Store
    # ====================================

    def _store_parents(self, parents):

        self.parent_store.save_many(parents)

    # ====================================
    # Vector Store
    # ====================================

    def _store_children(self, children):

        if not children:
            return

        self.vector_store.add_documents(children)

    # ====================================
    # Graph Builder
    # ====================================

    def _build_graph(self, parents):

        docs = []

        for parent_id, doc in parents:

            docs.append(
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                }
            )

        self.graph_builder.build_graph(docs)

    # ====================================
    # Clear Knowledge
    # ====================================

    def clear_knowledge(self):

        try:
            self.parent_store.clear_store()
        except:
            pass

        try:
            self.vector_db_manager.delete_collection(config.CHILD_COLLECTION)
        except:
            pass