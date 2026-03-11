from pathlib import Path


class DocumentService:

    def __init__(
        self,
        chunker,
        vector_store_manager,
        parent_store_manager,
        collection_name: str,
    ):
        self.chunker = chunker
        self.vector_store_manager = vector_store_manager
        self.parent_store_manager = parent_store_manager
        self.collection_name = collection_name

    def ingest(self, file_path: str):

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"{file_path} not found")

        # 1️. Chunking
        parent_chunks, child_chunks = (
            self.chunker.create_chunks_single(file_path)
        )

        if not child_chunks:
            return 0, 0

        # 2. Save to vector store
        collection = self.vector_store_manager.get_collection(
            self.collection_name
        )
        collection.add_documents(child_chunks)

        # 3️. Save parent chunks
        self.parent_store_manager.save_many(parent_chunks)

        return len(parent_chunks), len(child_chunks)