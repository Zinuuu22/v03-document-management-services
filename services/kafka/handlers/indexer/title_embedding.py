"""
Embedding Title Handler
Lắng nghe topic, embed doc_title lên Qdrant và cập nhật pipeline_document_state.
"""

import os
import sys
import time
import uuid  
from datetime import datetime
from typing import Any, Dict

import structlog

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import PreprocessTopics, AppConfig, MongoDBCollectionConfig, MigrateConfig, QdrantConfig

logger = structlog.get_logger()


class EmbeddingTitleHandler(BaseConsumer):

    TOPIC       = PreprocessTopics.TITLE_EMBEDDING_QUERY_TOPIC
    GROUP_ID    = PreprocessTopics.TITLE_EMBEDDING_GROUP
    NUM_WORKERS = AppConfig.TITLE_EMBEDDING_NUMBER_WORKER

    def __init__(self):
        super().__init__()
        self._embedding_model, self._qdrant, self._knowledge_name = self._load_embedder()
        self._db = self._init_db(
            extra_collections={
                "pipeline": MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME,
            }
        )

    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------

    def get_handler_name(self) -> str:
        return "title_embedding"

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
    
        # --- Parse message ---
        data   = self._parse_message(raw_message)
        _      = self._bind_request_context(data)
        doc_id = data.get("doc_id")
        
        start    = time.time()
        start_at = self._now()
    
        try:
            # 1. Check pipeline state
            if self._is_already_embedded(doc_id):
                print(f"[TITLE] already embedded, skipping", flush=True)
                logger.info("title_already_embedded_skip", doc_id=doc_id)
                return
    
            # 2. Fetch document
            document = self._fetch_document(doc_id)
            if not document:
                logger.error("document_not_found", doc_id=doc_id, **{"error.code": "DB"})
                self._update_pipeline_state(doc_id, "FAILED", start_at)
                return
    
            # 3. Embed title
            doc_title = document.get("doc_title", "").strip()
            if not doc_title:
                logger.warning("doc_title_empty", doc_id=doc_id)
                self._update_pipeline_state(doc_id, "FAILED", start_at)
                return
    
            self._embed_title(doc_id, doc_title)
    
            logger.info("title_embedded", doc_id=doc_id, duration_s=f"{time.time() - start:.3f}")
            self._update_pipeline_state(doc_id, "PROCESSED", start_at)
    
        except Exception as e:
            logger.error("process_message_failed", error=str(e), doc_id=doc_id,
                         **{"error.code": "SYS"}, exc_info=True)
            self._update_pipeline_state(doc_id, "FAILED", start_at)
    
        logger.info("message_processed", process_time=f"{time.time() - start:.3f}")

    # ------------------------------------------------------------------
    # Check pipeline state
    # ------------------------------------------------------------------

    def _is_already_embedded(self, doc_id: str) -> bool:
        """
        Kiểm tra xem document đã được embed title thành công chưa.
        Trả về True nếu title_embedding.status == "PROCESSED" → skip.
        """
        try:
            state = self._db["pipeline"].find_one(
                {"doc_id": doc_id},
                {"_id": 0, "title_embedding.status": 1},
            )
            if not state:
                logger.warning("pipeline_state_not_found", doc_id=doc_id)
                return False

            status = (state.get("title_embedding") or {}).get("status")
            return status == "PROCESSED"

        except Exception as e:
            logger.error("pipeline_state_check_failed", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Fetch document từ MongoDB
    # ------------------------------------------------------------------

    def _fetch_document(self, doc_id: str) -> Dict[str, Any] | None:
        """Lấy doc_id và doc_title từ law_documents."""
        try:
            doc = self._db["documents"].find_one(
                {"doc_id": doc_id},
                {"_id": 0, "doc_id": 1, "doc_title": 1},
            )
            if doc:
                logger.info("document_fetched", doc_id=doc_id)
            else:
                logger.warning("document_not_found_in_db", doc_id=doc_id)
            return doc
        except Exception as e:
            logger.error("document_fetch_failed", doc_id=doc_id,
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Embed title
    # ------------------------------------------------------------------

    def _embed_title(self, doc_id: str, doc_title: str) -> None:
        """Embed doc_title và lưu vào Qdrant."""
        payloads = self._embedding_model.embed_segments(
            segments_text=[doc_title],
        )
        for payload in payloads:
            chunk_id = str(uuid.uuid4())
            self._qdrant.add_vector(
                collection_name=self._knowledge_name,
                document_id=doc_id,
                segment_id=doc_id,
                segment_index=0,
                chunk_id=chunk_id,
                chunk_index=payload["chunk_index"],
                text=payload["text"],
                vector=payload["vector"],
                hash_text=None,
                metadata=None,
                model_type=MigrateConfig.MIGRATE_EMBEDDING_MODEL_TITLE,
            )

    # ------------------------------------------------------------------
    # Update pipeline_document_state
    # ------------------------------------------------------------------

    def _update_pipeline_state(self, doc_id: str, status: str, start_at: str) -> None:
        """
        Cập nhật trạng thái bước title_embedding trong pipeline_document_state.

        Args:
            doc_id: ID văn bản.
            status: "PROCESSED" hoặc "FAILED".
            start_at: Thời điểm bắt đầu xử lý.
        """
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
                        "title_embedding":  step_info,
                        "last_modified_at": finish_at,
                        "last_modified_by": self.get_handler_name(),
                    },
                    "$setOnInsert": {
                        "doc_id": doc_id,
                        "created_at":  finish_at,
                        "created_by":  self.get_handler_name(),
                    },
                },
                upsert=True,
            )
            logger.info("pipeline_state_updated", doc_id=doc_id, status=status)
        except Exception as e:
            logger.error("pipeline_state_update_failed", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)

    # ------------------------------------------------------------------
    # Embedder loader
    # ------------------------------------------------------------------

    @staticmethod
    def _load_embedder():
        from core.common.embedding import EMBEDDING_MODELS
        from core.common.qdrant import QdrantStorageManager

        model   = MigrateConfig.MIGRATE_EMBEDDING_MODEL_TITLE
        version = MigrateConfig.MIGRATE_EMBEDDING_VERSION
        size    = MigrateConfig.MIGRATE_EMBEDDING_EMBEDDING_SIZE

        knowledge_name  = MigrateConfig.MIGRATE_EMBEDDING_KNOWLEDGE_TITLE
        embedding_model = EMBEDDING_MODELS[model]
        qdrant          = QdrantStorageManager(host=QdrantConfig.HOST, port=QdrantConfig.PORT)

        # Tạo collection nếu chưa tồn tại
        # if not qdrant.check_qdrant_collection_exists(collection_name=knowledge_name):
        #     qdrant.create_collection(collection_name=knowledge_name, embedding_size=size)
        #     logger.info("qdrant_collection_created", collection=knowledge_name)
        # else:
        #     logger.info("qdrant_collection_exists", collection=knowledge_name)

        return embedding_model, qdrant, knowledge_name
