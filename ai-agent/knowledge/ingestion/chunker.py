from typing import List, Tuple, Dict
from pathlib import Path
import glob
import os
import uuid
import config
from langchain_text_splitters import RecursiveCharacterTextSplitter


class Document:
    """
    Simple document structure
    """

    def __init__(self, page_content: str, metadata: Dict = None, id: str = None):
        self.page_content = page_content
        self.metadata = metadata or {}
        self.id = id or str(uuid.uuid4())


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
        
        self.__min_parent_size = getattr(config, "MIN_PARENT_SIZE", 2000)
        self.__max_parent_size = getattr(config, "MAX_PARENT_SIZE", 4000)
        
        self.__child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_chunk_size,
            chunk_overlap=child_chunk_overlap
        )

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
    
    def create_chunks(self, path_dir=config.MARKDOWN_DIR):
    
        all_parent_chunks, all_child_chunks = [], []

        for doc_path_str in sorted(glob.glob(os.path.join(path_dir, "*.md"))):
            doc_path = Path(doc_path_str)
            parent_chunks, child_chunks = self.create_chunks_single(doc_path)

            all_parent_chunks.extend(parent_chunks)
            all_child_chunks.extend(child_chunks)

        return all_parent_chunks, all_child_chunks

    def create_chunks_single(self, md_path):

        md_path = Path(md_path)

        with open(md_path, "r", encoding="utf-8") as f:
            text = f.read()

        doc = Document(
            page_content=text,
            metadata={"source": md_path.name}
        )
        parent_docs, child_docs = self.split_documents([doc])

        return parent_docs, child_docs

    def __merge_small_parents(self, chunks):
        if not chunks:
            return []
        
        merged, current = [], None
        
        for chunk in chunks:
            if current is None:
                current = chunk
            else:
                current.page_content += "\n\n" + chunk.page_content
                for k, v in chunk.metadata.items():
                    if k in current.metadata:
                        current.metadata[k] = f"{current.metadata[k]} -> {v}"
                    else:
                        current.metadata[k] = v

            if len(current.page_content) >= self.__min_parent_size:
                merged.append(current)
                current = None
        
        if current:
            if merged:
                merged[-1].page_content += "\n\n" + current.page_content
                for k, v in current.metadata.items():
                    if k in merged[-1].metadata:
                        merged[-1].metadata[k] = f"{merged[-1].metadata[k]} -> {v}"
                    else:
                        merged[-1].metadata[k] = v
            else:
                merged.append(current)
        
        return merged

    def __split_large_parents(self, chunks):
        split_chunks = []
        
        for chunk in chunks:
            if len(chunk.page_content) <= self.__max_parent_size:
                split_chunks.append(chunk)
            else:
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.__max_parent_size,
                    chunk_overlap=config.CHILD_CHUNK_OVERLAP
                )
                sub_chunks = splitter.split_documents([chunk])
                split_chunks.extend(sub_chunks)
        
        return split_chunks

    def __clean_small_chunks(self, chunks):
        cleaned = []
        
        for i, chunk in enumerate(chunks):
            if len(chunk.page_content) < self.__min_parent_size:
                if cleaned:
                    cleaned[-1].page_content += "\n\n" + chunk.page_content
                    for k, v in chunk.metadata.items():
                        if k in cleaned[-1].metadata:
                            cleaned[-1].metadata[k] = f"{cleaned[-1].metadata[k]} -> {v}"
                        else:
                            cleaned[-1].metadata[k] = v
                elif i < len(chunks) - 1:
                    chunks[i + 1].page_content = chunk.page_content + "\n\n" + chunks[i + 1].page_content
                    for k, v in chunk.metadata.items():
                        if k in chunks[i + 1].metadata:
                            chunks[i + 1].metadata[k] = f"{v} -> {chunks[i + 1].metadata[k]}"
                        else:
                            chunks[i + 1].metadata[k] = v
                else:
                    cleaned.append(chunk)
            else:
                cleaned.append(chunk)
        
        return cleaned

    def __create_child_chunks(self, all_parent_pairs, all_child_chunks, parent_chunks, doc_path):
        for i, p_chunk in enumerate(parent_chunks):
            parent_id = f"{doc_path.stem}_parent_{i}"
            p_chunk.metadata.update({"source": str(doc_path.stem)+".pdf", "parent_id": parent_id})
            
            all_parent_pairs.append((parent_id, p_chunk))
            all_child_chunks.extend(self.__child_splitter.split_documents([p_chunk]))