# from core.common.embedding.models.VNsBERT import VNsBERT
# from core.common.embedding.models.allMiniLML6v2 import allMiniLML6v2
# from core.common.embedding.models.multilingualE5Large import multilingualE5Large
# from core.common.embedding.models.embedNomic import embedNommic
# from core.common.embedding.models.embedMxbai import embedMxbai
from core.common.embedding.models.vietnameseEmbedding import vietnameseEmbedding
from core.common.embedding.models.vietnameseEmbeddingLongContext import vietnameseEmbeddingLongContext
from core.common.embedding.models.dekEmbedding import dekEmbedding
from core.common.embedding.embeddingMain import CacheEmbedding


# Initialize embedding models
EMBEDDING_MODELS = {
    # "VNsBERT": CacheEmbedding(VNsBERT),
    # "allMiniLML6v2": CacheEmbedding(allMiniLML6v2),
    # "multilingualE5Large": CacheEmbedding(multilingualE5Large),
    # "embedNomic": CacheEmbedding(embedNommic),
    # "embedMxbai": CacheEmbedding(embedMxbai),
    "vietnameseEmbedding": CacheEmbedding(vietnameseEmbedding),
    "vietnameseEmbeddingLongContext": CacheEmbedding(vietnameseEmbeddingLongContext),
    "dekEmbedding": CacheEmbedding(dekEmbedding)
}