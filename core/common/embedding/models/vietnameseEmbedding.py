from sentence_transformers import SentenceTransformer
from core.common.embedding.models import embeddingBaseModel
from pyvi.ViTokenizer import tokenize


class vietnameseEmbedding(embeddingBaseModel):
    def __init__(self) -> None:
        self.name = 'vietnameseEmbedding'
        self.source_link = 'https://huggingface.co/intfloat/multilingual-e5-large'
        self.dimension = 768
        self.model = SentenceTransformer('/root/.cache/huggingface/hub/models--dangvantuan--vietnamese-embedding/snapshots/4ab46e46ba5902328ba0742e489e75f787932f2b', device ='cpu')
        self.max_chunk = 180

    def get_embeddings(self, sentences):        
        tokenizer_sent = [tokenize(sent) for sent in sentences]        
        embeddings = self.model.encode(tokenizer_sent)
        return embeddings        