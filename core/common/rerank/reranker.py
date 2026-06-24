from core.common.mongo.client import get_mongo_client
import numpy as np
import sys
import os
import time
from sentence_transformers import SentenceTransformer, CrossEncoder
from transformers import AutoTokenizer
from typing import List, Tuple, Dict
import torch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

class LawReranker:
    """A class to rerank law articles using BAAI/bge-m3 model on CPU."""
    
    def __init__(self, model_name: str = "BAAI/bge-m3", max_length: int = 2048, batch_size: int = 1):
        """
        Initialize the LawReranker with bge-m3 model on CPU.
        
        Args:
            model_name (str): Name of the model to use (default: "BAAI/bge-m3").
            max_length (int): Maximum token length for input (default: 2048 to reduce memory).
            batch_size (int): Batch size for reranking (default: 1 for CPU efficiency).
        """
        start_t = time.time()
        logger.info("reranker_initializing", action="__init__", model=model_name, device="cpu")
        try:
            self.model = CrossEncoder(model_name, max_length=max_length, device="cpu")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.max_length = max_length
            self.batch_size = batch_size
            self.device = torch.device("cpu")  # Force CPU usage               
            logger.info("reranker_model_loaded", action="__init__", **{"event.duration": time.time()-start_t, "event.status": "success"}, device=str(self.device))
        except Exception as e:
            logger.error("reranker_init_failed", action="__init__", **{"error.code": "ML", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            raise

    def preprocess_text(self, text: str) -> str:
        """Preprocess the text by removing extra spaces and normalizing newlines."""
        text = " ".join(text.split())
        text = text.replace("\n\n", "\n").strip()
        return text

    def truncate_text(self, text: str, max_tokens: int = 2000) -> str:
        """Truncate text to a maximum number of tokens."""
        tokens = self.tokenizer.tokenize(text)
        if len(tokens) > max_tokens:
            tokens = tokens[:max_tokens]
            text = self.tokenizer.convert_tokens_to_string(tokens)
            logger.debug("text_truncated", action="truncate_text", max_tokens=max_tokens)
        return text

    def rerank_laws(self, query: str, laws: List[Dict], top_k: int = 5) -> List[Dict]:
        """Rerank law articles based on their relevance to the query."""
        start_t = time.time()
        try:
            if not laws:
                logger.warning("no_laws_for_reranking", action="rerank_laws")
                return []

            query = self.preprocess_text(query)
            processed_laws = []
            for law in laws:
                law_text = self.preprocess_text(law['text'])
                law_text = self.truncate_text(law_text, max_tokens=self.max_length)
                processed_laws.append({'id': law['id'], 'text': law_text})

            pairs = [(query, law['text']) for law in processed_laws]
            logger.info("reranking_started", action="rerank_laws", article_count=len(pairs), device="cpu")

            
            scores = self.model.predict(
                    pairs,
                    batch_size=self.batch_size,
                    show_progress_bar=True,
                    convert_to_numpy=True
                )

            ranked_results = [
                {'id': law['id'], 'text': law['text'], 'score': float(score)}
                for law, score in zip(processed_laws, scores)
            ]
            ranked_results.sort(key=lambda x: x['score'], reverse=True)
            logger.info("reranking_completed", action="rerank_laws", **{"event.duration": time.time()-start_t, "event.status": "success"}, result_count=len(ranked_results))

            top_results = ranked_results[:min(top_k, len(ranked_results))]
            logger.info("top_results_selected", action="rerank_laws", count=len(top_results), ids=[r['id'] for r in top_results])
            return top_results
        except Exception as e:
            logger.error("reranking_failed", action="rerank_laws", **{"error.code": "ML", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            raise

if __name__ == "__main__":
    
    
    from pymongo import MongoClient
    import os
    import sys    
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    sys.path.append(PROJECT_ROOT)
    
    from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig

    client = get_mongo_client()

    db = client[MigrateConfig.MIGRATE_CORE_DB]
    article_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
    
    
    # Initialize reranker with CPU settings
    reranker = LawReranker(model_name="vinai/phobert-base", max_length=400, batch_size=10)


    # Example data
    query = "Xe máy khi tham gia giao thông không có bảo hiểm xe máy phạt tiền bao nhiêu"    

    import json
    sample = json.load(open("/home/ubuntu/projects/AI/git/users/giangnv/law-document-sync-core-service/core/common/rerank/sample.json"))
    result = sample['payloads'][0]['search']
    
    # post process result
    laws = []
    for item in result:
        article_id = item["segment_id"]
        article = article_collection.find_one({"article_id": article_id})
        if article:
            # article_title = article['article_title']
            # article_content = article['article_content']
            # article_full_content = article_title + "\n" + article_content
            # article_full_content = article_full_content.replace("\n\n", "\n")
            # item["text"] = article_full_content      
            item["id"] = item["code"]           
            laws.append(item)

    # Rerank laws
    reranked_laws = reranker.rerank_laws(query, laws, top_k=5)
    for law in reranked_laws:
        logger.info("reranked_law", action="main", law_id=law['id'], score=round(law['score'], 4), text_len=len(law['text']))