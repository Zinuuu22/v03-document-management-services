"""
Extract Keywords Handler
Migrated from services/kafka/v03/extract_keywords/consumer.py
"""

import os
import sys
import time
import uuid
from typing import Dict, Any, List
import structlog
import re
import httpx
import asyncio
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import PreprocessTopics, AppConfig, SignalRConfig, MongoDBCollectionConfig, ExtractBatchConfig

logger = structlog.get_logger()


class ExtractKeywordsHandler(BaseConsumer):

    TOPIC       = PreprocessTopics.EXTRACT_KEYWORD_QUERY_TOPIC
    GROUP_ID    = PreprocessTopics.EXTRACT_KEYWORD_GROUP
    NUM_WORKERS = AppConfig.EXTRACT_NORM_KEYWORDS_NUMBER_WORKER

    def __init__(self):
        super().__init__()
        self._extractor = self._load_extractor()
        self._db = self._init_db(extra_collections={
            "articles":         MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME,
            "pipeline":         MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME,
            "keywords":         MongoDBCollectionConfig.LAW_KEYWORD_COLLECTION_NAME
        })

    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------

    def get_handler_name(self) -> str:
        return "extract_keywords"

    def _get_response_topic(self) -> str:
        return PreprocessTopics.EXTRACT_KEYWORD_RESPONSE_TOPIC

    def _update_pipeline_state(self, doc_id: str, status: str, start_at: str) -> None:
        if not doc_id:
            return

        finish_at = self._now()
        step_info = {
            "status":        status,
            "start_at":      start_at,
            "finish_at":     finish_at,
            "duration_time": self._duration(start_at, finish_at),
        }


        # Các field pipeline cần kiểm tra
        extraction_fields = [
            "metadata_extraction",
            "keyword_extraction",
            "relationship_extraction",
            "article_relationship_extraction",
            "regulated_entity_extraction",
            "social_relation_extraction",
            "authority_extraction",
                        ]

        try:
            self._db["pipeline"].update_one(
                {"doc_id": doc_id},
                {
                    "$set": {
                        "keyword_extraction": step_info,
                        "last_modified_at":   finish_at,
                        "last_modified_by":   "admin",
                    },
                    "$setOnInsert": {
                        "doc_id": doc_id,
                        "created_at":  finish_at,
                        "created_by":  "admin",
                    },
                },
                upsert=True,
            )

            # Đọc lại record để kiểm tra toàn bộ trạng thái
            record = self._db["pipeline"].find_one({"doc_id": doc_id})
            if record:
                all_processed = all(
                    (record.get(field) or {}).get("status") == "PROCESSED"
                    for field in extraction_fields
                )
                if all_processed:
                    self._db["pipeline"].update_one(
                        {"doc_id": doc_id},
                        {"$set": {
                            "status":           "DONE",
                            "last_modified_at": self._now(),
                            "last_modified_by": "admin",
                        }}
                    )
                    logger.debug("update_pipeline_all_steps_completed", action="_update_pipeline_state",
                                doc_id=doc_id)

            logger.debug("update_pipeline_state_success", action="_update_pipeline_state",
                         doc_id=doc_id, status=status)
        except Exception as e:
            logger.error("pipeline_state_update_failed", action="_update_pipeline_state", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)



    @staticmethod
    def _make_response(request_id: str) -> Dict[str, Any]:
        return {
            "request_id": request_id,
            "status":     True,
            "responses":  [],
        }

    # ------------------------------------------------------------------
    # Main message processor
    # ------------------------------------------------------------------

    async def process_message(self, raw_message) -> None:
        # --- Trace context ---
        self._init_trace_context(raw_message)
        bind_contextvars(task="KafkaExtractKeywords")

        # --- Parse message ---
        data       = self._parse_message(raw_message)
        request_id = self._bind_request_context(data)
        doc_id     = data.get("doc_id")
        top_k      = data.get("top_k", 10)


        start_at = self._now()
        start    = time.perf_counter()
        response = self._make_response(request_id)

        try:
            # --- Step 1: Fetch segments ---
            bind_contextvars(step="step_1_fetch_segments")
            segments = self._fetch_segments(doc_id)
            batch_size = ExtractBatchConfig.KEYWORD_BATCH_SIZE
            if not segments:
                response["status"] = False
                logger.error("extract_keywords_failed", action="process_message",
                             **{"event.status": "failed", "error.code": "NOSEG",
                                "error.message": "No segments found for doc_id"},
                             doc_id=doc_id)
            else:
                # --- Step 2: Extract keywords ---
                bind_contextvars(step="step_2_extract_keywords")
                content   = self._build_content(segments)
                ext_start = time.perf_counter()
                keywords  = await self._extract_keywords(content, top_k, batch_size)
                ext_duration = round(time.perf_counter() - ext_start, 3)
                logger.info("extract_keywords_success", action="process_message",
                            **{"event.duration": ext_duration, "event.status": "success"},
                            doc_id=doc_id, keywords_total=len(keywords))

                response["responses"] = keywords

        except Exception as e:
            response["status"] = False
            self._update_pipeline_state(doc_id, "FAILED", start_at)
            logger.error("extract_keywords_failed", action="process_message",
                         **{"event.status": "failed",
                            "event.duration": round(time.perf_counter() - start, 3),
                            "error.code": "SYS", "error.message": str(e)}, exc_info=True)

        # --- Step 3: Insert keywords to MongoDB ---
        bind_contextvars(step="step_3_insert_keywords_to_mongodb")
        if response["status"]:
            insert_status = self._insert_keywords_to_documents(doc_id, response)
            if not insert_status:
                self._update_pipeline_state(doc_id, "FAILED", start_at)
            else:
                self._update_pipeline_state(doc_id, "PROCESSED", start_at)

        # --- Step 4: Send Response to Kafka ---
        bind_contextvars(step="step_4_send_kafka_response")
        self._send_response(response)

        # --- SignalR notification ---
        self.push_to_signalr_api(
            api_url=SignalRConfig.API_URL,
            topic=SignalRConfig.UPLOAD_TOPIC,
            message={
                "request_id": request_id,
                "status":     response["status"],
                "extract_keyword_status": response["status"],
            },
        )

        total_duration = round(time.perf_counter() - start, 3)
        if response["status"]:
            logger.info("process_keywords_message_success", action="process_message",
                        **{"event.duration": total_duration, "event.status": "success"},
                        doc_id=doc_id)
        else:
            logger.error("process_keywords_message_failed", action="process_message",
                         **{"event.duration": total_duration, "event.status": "failed"},
                         doc_id=doc_id)

    # ------------------------------------------------------------------
    # Insert keywords
    # ------------------------------------------------------------------

    def _insert_keywords_to_documents(
        self,
        doc_id: str,
        response: Dict[str, Any],
    ) -> bool:
        """
        Upsert keywords vào documents.
        Chỉ thực hiện khi extraction thành công (status=True).
        Trường hợp extraction thành công nhưng không có keyword vẫn được coi là DONE.
        """
        if not doc_id:
            logger.warning("insert_keywords_skipped_null_doc_id")
            return False

        if not response.get("status"):
            logger.warning("insert_keywords_skipped_failed_extraction", doc_id=doc_id)
            return False

        try:
            now       = self._now()
            responses = response.get("responses") or []
            keywords  = [r["key"] for r in responses if r.get("key")]

            if not keywords:
                logger.warning("extraction_succeeded_no_keywords", doc_id=doc_id)
            for keyword in keywords:
                
                keyword_id = self._resolve_catalog(
                    collection=self._db["keywords"],
                    match_field="keyword_name",
                    match_value= keyword,
                    id_field="keyword_id",
                    now=now,
                )

                self._db["documents"].update_one(
                    {"doc_id": doc_id},
                    {
                        "$addToSet": {
                            "keyword_ids": keyword_id
                        },
                        "$set": {
                            "last_modified_at": now,
                            "last_modified_by": "admin",
                        },
                        "$setOnInsert": {
                            "doc_id":     doc_id,
                            "created_at": now,
                            "created_by": "admin",
                        },
                    },
                    upsert=True,
                )
            logger.debug("insert_keywords_to_documents_success", action="_insert_keywords_to_documents",
                         doc_id=doc_id, keywords_count=len(keywords))

        except Exception as e:
            logger.error("insert_keywords_failed", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)
            return False
        return True

    # ------------------------------------------------------------------
    # Segment helpers
    # ------------------------------------------------------------------

    def _fetch_segments(self, doc_id) -> list:
        candidates = self._build_id_candidates(doc_id)
        try:
            fetch_start = time.perf_counter()
            cursor = self._db["articles"].find(
                {"doc_id": {"$in": candidates}},
                {
                    "_id":             0,
                    "article_title":   1,
                    "article_content": 1,
                    "article_index":   1,
                },
            )
            segments = list(cursor)
            logger.debug("fetch_segments_success", action="_fetch_segments",
                         doc_id=doc_id, segments_count=len(segments),
                         duration_ms=f"{(time.perf_counter() - fetch_start) * 1000:.1f}")
            return segments
        except Exception as e:
            logger.error("fetch_segments_failed", doc_id=doc_id,
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Extraction logic
    # ------------------------------------------------------------------

    async def _extract_keywords(self, content: str, top_k: int, batch_size: int) -> List[Dict]:
        from services.kafka.handlers.extractor.utils.keywords_utils import get_keywords_from_base
        from core.v03.keywords_extractor import get_keywords_async

        keywords = []

        # Extract from content
        try:
            kw_start = time.perf_counter()
            custom_timeout = httpx.Timeout(600.0, connect=10.0)
            semaphore = asyncio.Semaphore(batch_size)
            limits = httpx.Limits(max_keepalive_connections=batch_size, max_connections=batch_size * 2)
            async with httpx.AsyncClient(limits=limits, timeout=custom_timeout) as client:
                keywords = await get_keywords_async(content, client, semaphore, top_k=top_k)
            logger.debug("extract_keywords_from_content_success", action="_extract_keywords",
                         keywords_count=len(keywords), duration_ms=f"{(time.perf_counter() - kw_start) * 1000:.1f}")
        except Exception as e:
            logger.error("extract_keywords_from_content_failed",
                         **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

        # Extract from base tree
        keywords_from_base = []
        try:
            base_start         = time.perf_counter()
            keywords_from_base = get_keywords_from_base(content=content)
            logger.debug("extract_keywords_from_base_success", action="_extract_keywords",
                         keywords_count=len(keywords_from_base),
                         duration_ms=f"{(time.perf_counter() - base_start) * 1000:.1f}")
        except Exception as e:
            logger.error("extract_keywords_from_base_failed",
                         **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

        # Merge: base keywords prepended if not already present
        merge_start   = time.perf_counter()
        existing_keys = {kw["key"] for kw in keywords}
        added         = 0
        for keyword in keywords_from_base:
            if keyword not in existing_keys:
                keywords.insert(0, {"key": keyword, "value": 100, "reason": "from base"})
                added += 1
        logger.debug("merge_keywords_done", action="_extract_keywords",
                     existing=len(existing_keys), added_from_base=added, total=len(keywords),
                     duration_ms=f"{(time.perf_counter() - merge_start) * 1000:.1f}")

        return keywords

    def _resolve_catalog(
        self,
        collection,
        match_field: str,
        match_value: str,
        id_field: str,
        now: str,
    ) -> str:
        """
        Lookup catalog theo match_field. Tạo mới nếu chưa tồn tại.
        Trả về id tương ứng, hoặc "" nếu match_value rỗng.
        """
        if not match_value:
            return ""

        existing = collection.find_one({
            match_field: {"$regex": f"^{re.escape(match_value.strip())}$", "$options": "i"}
        })
        if existing:
            return existing[id_field]

        new_id = str(uuid.uuid4())
        collection.insert_one({
            id_field:           new_id,
            match_field:        match_value,
            "status":           "ACTIVE",
            "created_at":       now,
            "created_by":       "admin",
            "last_modified_at": now,
            "last_modified_by": "admin",
        })
        logger.info("catalog_entry_created",
                    collection=collection.name, value=match_value)
        return new_id
        
    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _build_content(segments: list) -> str:
        parts = []
        for seg in segments:
            title    = (seg.get("article_title") or "").strip()
            body     = (seg.get("article_content") or "").strip()
            seg_text = f"{title}\n{body}".strip()
            if seg_text:
                parts.append(seg_text)
        return "\n\n".join(parts)

    @staticmethod
    def _build_id_candidates(doc_id) -> list:
        if doc_id is None:
            return []
        candidates = [doc_id]
        try:
            s = str(doc_id)
            if s not in candidates:
                candidates.append(s)
            if s.isdigit():
                iv = int(s)
                if iv not in candidates:
                    candidates.append(iv)
        except Exception:
            pass
        return candidates
    # ------------------------------------------------------------------
    # Extractor loader
    # ------------------------------------------------------------------

    @staticmethod
    def _load_extractor():
        from core.v03.keywords_extractor import get_keywords
        logger.debug("load_keywords_extractor_success", action="_load_extractor")
        return get_keywords