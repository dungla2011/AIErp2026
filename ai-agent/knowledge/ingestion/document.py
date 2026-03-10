from dataclasses import dataclass
from typing import Dict


@dataclass
class Document:
    """
    Lightweight document object
    thay thế LangChain Document
    """

    page_content: str
    metadata: Dict