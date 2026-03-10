from abc import ABC, abstractmethod
from typing import List


class BaseEmbedding(ABC):

    @abstractmethod
    def embed_query(self, text):
        pass

    @abstractmethod
    def embed_documents(self, texts):
        pass