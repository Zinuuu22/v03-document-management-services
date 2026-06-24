"""
Article Embedding Handler
Lắng nghe topic, embed nội dung article (theo khoản/clause) lên Qdrant
và cập nhật pipeline_document_state.
"""

import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List
from concurrent.futures import ThreadPoolExecutor

import structlog
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import PreprocessTopics, AppConfig, MongoDBCollectionConfig, MigrateConfig, QdrantConfig

logger = structlog.get_logger()


class ArticleEmbeddingHandler(BaseConsumer):

    TOPIC       = PreprocessTopics.ARTICLE_EMBEDDING_QUERY_TOPIC
    GROUP_ID    = PreprocessTopics.ARTICLE_EMBEDDING_GROUP
    NUM_WORKERS = AppConfig.ARTICLE_EMBEDDING_NUMBER_WORKER

    def __init__(self):
        super().__init__()
        self._embedding_model, self._qdrant, self._knowledge_name = self._load_embedder()
        self._db = self._init_db(
            extra_collections={
                "pipeline": MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME,
                "articles": MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME,
                "clauses":  MongoDBCollectionConfig.LAW_CLAUSE_COLLECTION_NAME,
            }
        )

    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------

    def get_handler_name(self) -> str:
        return "article_embedding"

    def _get_response_topic(self) -> str:
        return None

    @staticmethod
    def _make_response(request_id: str) -> Dict[str, Any]:
        return {}

    # ------------------------------------------------------------------
    # Main message processor
    # ------------------------------------------------------------------

    def process_message(self, raw_message) -> None:
        # --- Trace context ---
        self._init_trace_context(raw_message)
        bind_contextvars(task="KafkaEmbeddingArticle")

        # --- Parse message ---
        data       = self._parse_message(raw_message)
        _          = self._bind_request_context(data)
        doc_id     = data.get("doc_id")

        start    = time.time()
        start_at = self._now()

        try:
            # 1. Kiểm tra trạng thái article_embedding trong pipeline
            bind_contextvars(step="step_1_check_pipeline_state")
            if self._is_already_embedded(doc_id):
                logger.info("article_embedding_skipped", action="process_message",
                            doc_id=doc_id)
                return

            # 2. Fetch toàn bộ articles của document
            bind_contextvars(step="step_2_fetch_data")
            articles = self._fetch_articles(doc_id)
            if not articles:
                logger.error("fetch_articles_failed", action="process_message",
                             doc_id=doc_id,
                             **{"error.code": "DB", "error.message": "No articles found for doc_id"})
                bind_contextvars(step="step_4_update_pipeline_state")
                self._update_pipeline_state(doc_id, "FAILED", start_at)
                total_duration = round(time.time() - start, 3)
                logger.error("process_article_embedding_message_failed", action="process_message",
                             doc_id=doc_id,
                             **{"event.status": "failed", "event.duration": total_duration})
                return

            # 3. Embed từng article
            
            # bind_contextvars(step="step_3_generate_embedding")
            # success_count = 0
            # error_count   = 0
            # for article in articles:
            #     ok = self._process_article(doc_id, article)
            #     if ok:
            #         success_count += 1
            #     else:
            #         error_count += 1

            bind_contextvars(step="step_3_generate_embedding")
            with ThreadPoolExecutor(max_workers=min(32, len(articles))) as executor:
                results = list(executor.map(lambda a: self._process_article(doc_id, a), articles))
            
            success_count = sum(1 for r in results if r)
            error_count   = sum(1 for r in results if not r)

            # 4. Cập nhật pipeline state theo kết quả
            if error_count == 0:
                status = "PROCESSED"
            elif success_count == 0:
                status = "FAILED"
            else:
                status = "PARTIAL"

            embed_duration = round(time.time() - start, 3)
            embed_status   = "success" if status == "PROCESSED" else ("partial" if status == "PARTIAL" else "failed")
            logger.info("embed_articles_success" if status != "FAILED" else "embed_articles_failed",
                        action="process_message",
                        doc_id=doc_id, success_count=success_count, error_count=error_count,
                        **{"event.status": embed_status, "event.duration": embed_duration})

            bind_contextvars(step="step_4_update_pipeline_state")
            self._update_pipeline_state(doc_id, status, start_at)

        except Exception as e:
            bind_contextvars(step="step_4_update_pipeline_state")
            logger.error("process_article_embedding_message_failed", action="process_message",
                         doc_id=doc_id,
                         **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
            self._update_pipeline_state(doc_id, "FAILED", start_at)
            total_duration = round(time.time() - start, 3)
            logger.error("process_article_embedding_message_failed", action="process_message",
                         doc_id=doc_id,
                         **{"event.status": "failed", "event.duration": total_duration})
            return

        total_duration = round(time.time() - start, 3)
        final_status   = "success" if status == "PROCESSED" else ("partial" if status == "PARTIAL" else "failed")
        if status == "FAILED":
            logger.error("process_article_embedding_message_failed", action="process_message",
                         doc_id=doc_id,
                         **{"event.status": final_status, "event.duration": total_duration})
        else:
            logger.info("process_article_embedding_message_success", action="process_message",
                        doc_id=doc_id,
                        **{"event.status": final_status, "event.duration": total_duration})

    # ------------------------------------------------------------------
    # Check pipeline state
    # ------------------------------------------------------------------

    def _is_already_embedded(self, doc_id: str) -> bool:
        """Trả về True nếu article_embedding.status == "PROCESSED" → skip."""
        try:
            state = self._db["pipeline"].find_one(
                {"doc_id": doc_id},
                {"_id": 0, "article_embedding.status": 1},
            )
            if not state:
                logger.warning("pipeline_state_not_found", action="_is_already_embedded", doc_id=doc_id)
                return False

            status = (state.get("article_embedding") or {}).get("status")
            return status == "PROCESSED"

        except Exception as e:
            logger.error("pipeline_state_check_failed", action="_is_already_embedded", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Fetch articles
    # ------------------------------------------------------------------

    def _fetch_articles(self, doc_id: str) -> List[Dict[str, Any]]:
        """Lấy toàn bộ articles của document từ law_articles."""
        try:
            articles = list(self._db["articles"].find(
                {"doc_id": doc_id},
                {"_id": 0, "article_id": 1, "doc_id": 1,
                 "article_title": 1, "article_content": 1},
            ))
            logger.debug("articles_fetched", action="_fetch_articles", doc_id=doc_id, count=len(articles))
            return articles
        except Exception as e:
            logger.error("articles_fetch_failed", action="_fetch_articles", doc_id=doc_id,
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Process single article
    # ------------------------------------------------------------------

    # def _process_article(self, doc_id: str, article: Dict[str, Any]) -> bool:
    #     """
    #     Embed một article: dùng clauses nếu có, fallback về article_content.

    #     Returns:
    #         True nếu thành công, False nếu thất bại.
    #     """
    #     article_id = article.get("article_id")
    #     try:
    #         clauses = list(self._db["clauses"].find(
    #             {"article_id": article_id},
    #             {"_id": 0, "claud_order_index": 1, "claud_summary_content": 1},
    #         ))
    #         logger.debug("clauses_fetched", action="_process_article",
    #                      article_id=article_id, count=len(clauses))

    #         segments_id    = []
    #         segments_index = []
    #         segments_text  = []

    #         if clauses:
    #             # Embed theo từng khoản (claud_summary_content)
    #             for clause in clauses:
    #                 content = self._clean_text(clause.get("claud_summary_content", ""))
    #                 if not content:
    #                     continue
    #                 segments_id.append(article_id)
    #                 segments_index.append(clause.get("claud_order_index", 0))
    #                 segments_text.append(content)
    #         else:
    #             # Fallback: embed toàn bộ article_title + article_content
    #             title   = article.get("article_title", "").strip()
    #             content = article.get("article_content", "").strip()
    #             full    = self._clean_text(f"{title}\n{content}")
    #             if not full:
    #                 logger.warning("article_content_empty", action="_process_article",
    #                                article_id=article_id)
    #                 return False
    #             segments_id.append(article_id)
    #             segments_index.append(0)
    #             segments_text.append(full)

    #         if not segments_text:
    #             logger.warning("no_segments_to_embed", action="_process_article",
    #                            article_id=article_id)
    #             return False

    #         # Embed và lưu vào Qdrant
    #         payloads = self._embedding_model.embed_segments_batch(
    #             segments_id, segments_index, segments_text
    #         )
    #         for payload in payloads:
    #             self._qdrant.add_vector(
    #                 collection_name=self._knowledge_name,
    #                 document_id=doc_id,
    #                 segment_id=payload["segment_id"],
    #                 segment_index=payload["segment_index"],
    #                 chunk_id=payload["chunk_id"],
    #                 chunk_index=payload["chunk_index"],
    #                 text=payload["text"],
    #                 vector=payload["vector"],
    #                 hash_text=None,
    #                 metadata=None,
    #                 model_type=MigrateConfig.MIGRATE_EMBEDDING_MODEL_ARTICLE,
    #             )

    #         logger.debug("embed_article_success", action="_process_article",
    #                      article_id=article_id, segments=len(segments_text))
    #         return True

    #     except Exception as e:
    #         logger.error("embed_article_failed", action="_process_article",
    #                      article_id=article_id,
    #                      **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
    #         return False
    
    def _process_article(self, doc_id: str, article: Dict[str, Any], upsert_batch_size: int = 100, max_workers: int = 4) -> bool:
        article_id = article.get("article_id")
        try:
            clauses = list(self._db["clauses"].find(
                {"article_id": article_id},
                {"_id": 0, "claud_order_index": 1, "claud_summary_content": 1},
            ))
            logger.debug("clauses_fetched", action="_process_article",
                         article_id=article_id, count=len(clauses))
    
            segments_id    = []
            segments_index = []
            segments_text  = []
    
            if clauses:
                for clause in clauses:
                    content = self._clean_text(clause.get("claud_summary_content", ""))
                    if not content:
                        continue
                    segments_id.append(article_id)
                    segments_index.append(clause.get("claud_order_index", 0))
                    segments_text.append(content)
            else:
                title   = article.get("article_title", "").strip()
                content = article.get("article_content", "").strip()
                full    = self._clean_text(f"{title}\n{content}")
                if not full:
                    logger.warning("article_content_empty", action="_process_article",
                                   article_id=article_id)
                    return False
                segments_id.append(article_id)
                segments_index.append(0)
                segments_text.append(full)
    
            if not segments_text:
                logger.warning("no_segments_to_embed", action="_process_article",
                               article_id=article_id)
                return False
    
            payloads = self._embedding_model.embed_segments_batch(
                segments_id, segments_index, segments_text
            )
    
            upsert_batches = [
                [
                    {
                        "chunk_id"     : payload["chunk_id"],
                        "segment_id"   : payload["segment_id"],
                        "segment_index": payload["segment_index"],
                        "chunk_index"  : payload["chunk_index"],
                        "text"         : payload["text"],
                        "vector"       : payload["vector"],
                    }
                    for payload in payloads[i:i + upsert_batch_size]
                ]
                for i in range(0, len(payloads), upsert_batch_size)
            ]
    
            for batch in upsert_batches:
                self._qdrant.add_vectors_batch(
                    collection_name=self._knowledge_name,
                    document_id=doc_id,
                    segment_id=article_id,
                    vectors=batch,
                    hash_text=None,
                    metadata=None,
                    model_type=MigrateConfig.MIGRATE_EMBEDDING_MODEL_ARTICLE,
                )
    
            logger.debug("embed_article_success", action="_process_article",
                         article_id=article_id, segments=len(segments_text))
            return True
    
        except Exception as e:
            logger.error("embed_article_failed", action="_process_article",
                         article_id=article_id,
                         **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Update pipeline_document_state
    # ------------------------------------------------------------------

    def _update_pipeline_state(self, doc_id: str, status: str, start_at: str) -> None:
        """Cập nhật trạng thái bước article_embedding trong pipeline_document_state."""
        if not doc_id:
            return

        finish_at = self._now()
        step_info = {
            "status":        status,
            "start_at":      start_at,
            "finish_at":     finish_at,
            "duration_time": self._duration(start_at, finish_at),
        }

        try:
            self._db["pipeline"].update_one(
                {"doc_id": doc_id},
                {
                    "$set": {
                        "article_embedding": step_info,
                        "last_modified_at":  finish_at,
                        "last_modified_by":  self.get_handler_name(),
                    },
                    "$setOnInsert": {
                        "doc_id": doc_id,
                        "created_at":  finish_at,
                        "created_by":  self.get_handler_name(),
                    },
                },
                upsert=True,
            )
            event_status = "success" if status == "PROCESSED" else "failed"
            logger.info("update_pipeline_state_success", action="_update_pipeline_state",
                        doc_id=doc_id, **{"event.status": event_status})
        except Exception as e:
            logger.error("pipeline_state_update_failed", action="_update_pipeline_state", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)

    # ------------------------------------------------------------------
    # Embedder loader
    # ------------------------------------------------------------------

    @staticmethod
    def _load_embedder():
        from core.common.embedding import EMBEDDING_MODELS
        from core.common.qdrant import QdrantStorageManager

        model   = MigrateConfig.MIGRATE_EMBEDDING_MODEL_ARTICLE
        version = MigrateConfig.MIGRATE_EMBEDDING_VERSION
        size    = MigrateConfig.MIGRATE_EMBEDDING_EMBEDDING_SIZE

        knowledge_name  = MigrateConfig.MIGRATE_EMBEDDING_KNOWLEDGE_ARTICLE
        embedding_model = EMBEDDING_MODELS[model]
        qdrant          = QdrantStorageManager(host=QdrantConfig.HOST, port=QdrantConfig.PORT)

        # if not qdrant.check_qdrant_collection_exists(collection_name=knowledge_name):
        #     qdrant.create_collection(collection_name=knowledge_name, embedding_size=size)
        #     logger.info("qdrant_collection_created", action="_load_embedder", collection=knowledge_name)
        # else:
        #     logger.debug("qdrant_collection_exists", action="_load_embedder", collection=knowledge_name)

        return embedding_model, qdrant, knowledge_name