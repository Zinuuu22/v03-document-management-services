from sentence_transformers import SentenceTransformer
import torch
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.common.embedding.models import embeddingBaseModel

class dekEmbedding(embeddingBaseModel):
    def __init__(self) -> None:
        self.name = 'dekEmbedding'
        self.source_link = 'https://huggingface.co/huyydangg/DEk21_hcmute_embedding'
        self.dimension = 768
        self.model = SentenceTransformer('/root/.cache/huggingface/hub/models--huyydangg--DEk21_hcmute_embedding/snapshots/501df2abd66bfecf9f294c4d17741b0d9f3ebb7e', device ='cpu')
        self.max_chunk = 512

    def get_embeddings(self, sentences):        
        doc_embeddings = self.model.encode(sentences)
        return doc_embeddings

if __name__ == '__main__':
    dekEmbedding = dekEmbedding()
    
    # Define query (câu hỏi pháp luật) và docs (điều luật)
    import time
    start_time = time.time()
    query = "Điều kiện để kết hôn hợp pháp là gì?"
    docs = [
        "Điều 8 Bộ luật Dân sự 2015 quy định về quyền và nghĩa vụ của công dân trong quan hệ gia đình.",
        "Điều 18 Luật Hôn nhân và gia đình 2014 quy định về độ tuổi kết hôn của nam và nữ.",
        "Điều 14 Bộ luật Dân sự 2015 quy định về quyền và nghĩa vụ của cá nhân khi tham gia hợp đồng.",
        "Điều 27 Luật Hôn nhân và gia đình 2014 quy định về các trường hợp không được kết hôn.",
        "Điều 51 Luật Hôn nhân và gia đình 2014 quy định về việc kết hôn giữa công dân Việt Nam và người nước ngoài."
    ]

    # Encode query and documents
    query_embedding = dekEmbedding.get_embeddings([query])
    doc_embeddings = dekEmbedding.get_embeddings(docs)
    similarities = torch.nn.functional.cosine_similarity(
        torch.tensor(query_embedding), torch.tensor(doc_embeddings)
    ).flatten()

    # Sort documents by cosine similarity
    sorted_indices = torch.argsort(similarities, descending=True)
    sorted_docs = [docs[idx] for idx in sorted_indices]
    sorted_scores = [similarities[idx].item() for idx in sorted_indices]

    # Log sorted documents with their cosine scores
    for doc, score in zip(sorted_docs, sorted_scores):
        logger.info("similarity_result", action="main", doc_len=len(doc), score=round(score, 4))
    end_time = time.time()
    logger.info("execution_completed", action="main", elapsed_seconds=round(end_time - start_time, 2))