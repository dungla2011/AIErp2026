from typing import List
from pypdf import PdfReader

from ..document import Document


def load_pdf(file_path: str) -> List[Document]:

    reader = PdfReader(file_path)

    docs = []

    for page_num, page in enumerate(reader.pages):

        text = page.extract_text()

        if not text:
            continue

        docs.append(
            Document(
                page_content=text,
                metadata={
                    "source": file_path,
                    "page": page_num
                }
            )
        )

    return docs