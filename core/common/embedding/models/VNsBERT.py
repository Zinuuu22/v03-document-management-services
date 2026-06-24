from sentence_transformers import SentenceTransformer
from core.common.embedding.models import embeddingBaseModel

class VNsBERT(embeddingBaseModel):
    def __init__(self) -> None:
        self.name = 'vietnamese-sBERT'
        self.source_link = 'https://huggingface.co/keepitreal/vietnamese-sbert'
        self.dimension = 768
        self.model = SentenceTransformer('keepitreal/vietnamese-sbert', device ='cpu')
        self.max_chunk = 1000
    
    def get_embeddings(self, sentences):
        return self.model.encode(sentences)