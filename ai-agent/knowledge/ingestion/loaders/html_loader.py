from typing import List
from bs4 import BeautifulSoup

from ..document import Document


def load_html(file_path: str) -> List[Document]:

    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    docs = []

    paragraphs = soup.find_all("p")

    for i, p in enumerate(paragraphs):

        text = p.get_text().strip()

        if not text:
            continue

        docs.append(
            Document(
                page_content=text,
                metadata={
                    "source": file_path,
                    "paragraph": i,
                    "type": "html"
                }
            )
        )

    return docs