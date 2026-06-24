"""
Index Elastic Handler
Lắng nghe topic, index document lên Elasticsearch và cập nhật pipeline_document_state.
"""

import os
import sys
import time
from datetime import datetime
from typing import Any, Dict

import structlog
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import PreprocessTopics, AppConfig, MongoDBCollectionConfig

logger = structlog.get_logger()



class IndexElasticHandler(BaseConsumer):
 
    TOPIC      = PreprocessTopics.INDEX_ELASTIC_QUERY_TOPIC
    GROUP_ID   = PreprocessTopics.INDEX_ELASTIC_GROUP
    NUM_WORKERS = AppConfig.INDEX_ELASTIC_NUMBER_WORKER
 
    def __init__(self):
        super().__init__()
        self._indexer = self._load_indexer()
        self._db = self._init_db(
            extra_collections={
                "pipeline": MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME,
            }
        )
 
    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------
 
    def get_handler_name(self) -> str:
        return "index_elastic"
 
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
        bind_contextvars(task="KafkaIndexElastic")

        # --- Parse message ---
        data       = self._parse_message(raw_message)
        _          = self._bind_request_context(data)
        doc_id     = data.get("doc_id")

        start      = time.time()
        start_at   = self._now()

        try:
            # 1. Kiểm tra trạng thái elastic_indexing trong pipeline
            bind_contextvars(step="step_1_check_pipeline_state")
            if self._is_already_indexed(doc_id):
                logger.info("index_elastic_skipped", action="process_message",
                            doc_id=doc_id)
                return

            # 2. Fetch document từ MongoDB
            bind_contextvars(step="step_2_fetch_document")
            document = self._fetch_document(doc_id)

            if not document:
                logger.error("fetch_document_failed", action="process_message",
                             doc_id=doc_id,
                             **{"error.code": "DB", "error.message": "Document not found in MongoDB"})
                self._update_pipeline_state(doc_id, "FAILED", start_at)
                total_duration = round(time.time() - start, 3)
                logger.error("process_elastic_index_message_failed", action="process_message",
                             doc_id=doc_id,
                             **{"event.status": "failed", "event.duration": total_duration})
                return

            # 3. Index lên Elasticsearch
            bind_contextvars(step="step_3_index_to_elasticsearch")
            ok = self._indexer.index_document(document)

            if ok:
                logger.info("index_document_success", action="process_message",
                            doc_id=doc_id,
                            **{"event.duration": round(time.time() - start, 3)})
                bind_contextvars(step="step_4_update_pipeline_state")
                self._update_pipeline_state(doc_id, "PROCESSED", start_at)
            else:
                logger.error("index_document_failed", action="process_message",
                             doc_id=doc_id,
                             **{"error.code": "ES", "error.message": "ElasticIndexer.index_document returned False"})
                bind_contextvars(step="step_4_update_pipeline_state")
                self._update_pipeline_state(doc_id, "FAILED", start_at)

        except Exception as e:
            bind_contextvars(step="step_4_update_pipeline_state")
            logger.error("process_elastic_index_message_failed", action="process_message",
                         doc_id=doc_id,
                         **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
            self._update_pipeline_state(doc_id, "FAILED", start_at)
            total_duration = round(time.time() - start, 3)
            logger.error("process_elastic_index_message_failed", action="process_message",
                         doc_id=doc_id,
                         **{"event.status": "failed", "event.duration": total_duration})
            return

        total_duration = round(time.time() - start, 3)
        if ok:
            logger.info("process_elastic_index_message_success", action="process_message",
                        doc_id=doc_id,
                        **{"event.status": "success", "event.duration": total_duration})
        else:
            logger.error("process_elastic_index_message_failed", action="process_message",
                         doc_id=doc_id,
                         **{"event.status": "failed", "event.duration": total_duration})

    # ------------------------------------------------------------------
    # Check pipeline state
    # ------------------------------------------------------------------
 
    def _is_already_indexed(self, doc_id: str) -> bool:
        """
        Kiểm tra xem document đã được index thành công chưa.
        Trả về True nếu elastic_indexing.status == "PROCESSED" → skip.

        Args:
            doc_id: ID văn bản cần kiểm tra.

        Returns:
            True nếu đã PROCESSED, False nếu chưa hoặc lỗi.
        """
        try:
            state = self._db["pipeline"].find_one(
                {"doc_id": doc_id},
                {"_id": 0, "elastic_indexing.status": 1},
            )
            if not state:
                logger.warning("pipeline_state_not_found", action="_is_already_indexed", doc_id=doc_id)
                return False

            status = (state.get("elastic_indexing") or {}).get("status")
            return status == "PROCESSED"

        except Exception as e:
            logger.error("pipeline_state_check_failed", action="_is_already_indexed", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)
            return False
 
    # ------------------------------------------------------------------
    # Fetch document từ MongoDB
    # ------------------------------------------------------------------
 
    def _fetch_document(self, doc_id: str) -> Dict[str, Any] | None:
        """
        Lấy document đầy đủ từ law_documents theo doc_id.

        Returns:
            Dict document, hoặc None nếu không tìm thấy.
        """
        try:
            doc = self._db["documents"].find_one(
                {"doc_id": doc_id},
                {"_id": 0},
            )
            if doc:
                logger.debug("document_fetched", action="_fetch_document", doc_id=doc_id)
            else:
                logger.warning("document_not_found_in_db", action="_fetch_document", doc_id=doc_id)
            return doc
        except Exception as e:
            logger.error("document_fetch_failed", action="_fetch_document", doc_id=doc_id,
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            return None
 
    # ------------------------------------------------------------------
    # Update pipeline_document_state
    # ------------------------------------------------------------------
 
    def _update_pipeline_state(self, doc_id: str, status: str, start_at: str) -> None:
        """
        Cập nhật trạng thái bước elastic_indexing trong pipeline_document_state.

        Args:
            doc_id: ID văn bản.
            status: "PROCESSED" hoặc "FAILED".
            start_at: Thời điểm bắt đầu xử lý (chuỗi %Y-%m-%d %H:%M:%S).
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
                        "elastic_indexing":  step_info,
                        "last_modified_at":  finish_at,
                        "last_modified_by":  self.get_handler_name(),
                    }
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
    # Indexer loader
    # ------------------------------------------------------------------
 
    @staticmethod
    def _load_indexer():
        from core.common.elastic.index import ElasticIndexer
        logger.debug("load_elastic_indexer_success", action="_load_indexer")
        return ElasticIndexer()