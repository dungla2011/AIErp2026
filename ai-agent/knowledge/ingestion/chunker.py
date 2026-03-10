from typing import List, Tuple, Dict
import uuid
import config


class Document:
    """
    Simple document structure
    """

    def __init__(self, page_content: str, metadata: Dict = None):
        self.page_content = page_content
        self.metadata = metadata or {}


class DocumentChunker:
    """
    Split documents into:
    - Parent chunks
    - Child chunks
    """

    def __init__(
        self,
        parent_chunk_size: int = getattr(config, "PARENT_CHUNK_SIZE", 1200),
        parent_chunk_overlap: int = getattr(config, "PARENT_CHUNK_OVERLAP", 150),
        child_chunk_size: int = getattr(config, "CHILD_CHUNK_SIZE", 400),
        child_chunk_overlap: int = getattr(config, "CHILD_CHUNK_OVERLAP", 80),
    ):

        self.parent_chunk_size = parent_chunk_size
        self.parent_chunk_overlap = parent_chunk_overlap
        self.child_chunk_size = child_chunk_size
        self.child_chunk_overlap = child_chunk_overlap

    def _split_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:

        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:

            end = start + chunk_size
            chunk = text[start:end]

            chunks.append(chunk)

            start = end - overlap

            if start < 0:
                start = 0

        return chunks

    def split_documents(
        self,
        documents: List[Document],
    ) -> Tuple[List[Tuple[str, Document]], List[Document]]:

        parent_docs: List[Tuple[str, Document]] = []
        child_docs: List[Document] = []

        for doc in documents:

            parent_chunks = self._split_text(
                doc.page_content,
                self.parent_chunk_size,
                self.parent_chunk_overlap
            )

            for idx, parent_text in enumerate(parent_chunks):

                parent_id = f"{uuid.uuid4()}_parent_{idx}"

                parent_doc = Document(
                    page_content=parent_text,
                    metadata={**doc.metadata, "parent_id": parent_id}
                )

                parent_docs.append((parent_id, parent_doc))

                child_chunks = self._split_text(
                    parent_text,
                    self.child_chunk_size,
                    self.child_chunk_overlap
                )

                for child_text in child_chunks:

                    child_doc = Document(
                        page_content=child_text,
                        metadata={"parent_id": parent_id}
                    )

                    child_docs.append(child_doc)

        return parent_docs, child_docs