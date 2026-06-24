from sentence_transformers import SentenceTransformer
from core.common.embedding.models import embeddingBaseModel
from pyvi.ViTokenizer import tokenize

class vietnameseEmbeddingLongContext(embeddingBaseModel):
    def __init__(self) -> None:
        self.name = 'vietnameseEmbeddingLongContext'
        self.source_link = 'https://huggingface.co/dangvantuan/vietnamese-document-embedding'
        self.dimension = 768
        self.model = SentenceTransformer('/root/.cache/huggingface/hub/models--dangvantuan--vietnamese-document-embedding/snapshots/6fa4e2f8ed2d33120b0f4442cc81f8f973c3f56b', trust_remote_code=True, device='cpu')
        self.max_chunk = 1000

    def get_embeddings(self, sentences):        
        tokenizer_sent = [tokenize(sent) for sent in sentences]        
        embeddings = self.model.encode(tokenizer_sent)
        return embeddings        