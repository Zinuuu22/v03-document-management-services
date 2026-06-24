from abc import ABC, abstractmethod

class embeddingBaseModel(ABC):
    name = ""
    dimension = 768
    @abstractmethod
    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Embed search docs."""