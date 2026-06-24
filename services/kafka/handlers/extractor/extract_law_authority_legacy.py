"""
Extract Law Authority Handler
Migrated from services/kafka/v03/extract_law_authority/consumer.py
"""

import os
import sys
import time
import uuid
from typing import Dict, Any
import structlog
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import PreprocessTopics, AppConfig, SignalRConfig, MongoDBCollectionConfig

logger = structlog.get_logger()


class ExtractLawAuthorityHandler(BaseConsumer):

    TOPIC       = PreprocessTopics.EXTRACT_LAW_AUTHORITY_QUERY_TOPIC
    GROUP_ID    = PreprocessTopics.EXTRACT_LAW_AUTHORITY_GROUP
    NUM_WORKERS = AppConfig.EXTRACT_NORM_LAW_AUTHORITY_NUMBER_WORKER

    def __init__(self):
        super().__init__()
        self._set_agency_list, self._extract_segment_assignments, self._compose_formal_records = self._load_extractor()
        self._db = self._init_db(extra_collections={
            "articles":                  MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME,
            "article_class":             MongoDBCollectionConfig.LAW_ARTICLE_CLASS_COLLECTION_NAME,
            "law_agencies":              MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME,
            "pipeline":                  MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME,
            "law_authority":             MongoDBCollectionConfig.LAW_AUTHORITY_COLLECTION_NAME,
            "authority_mapping":         MongoDBCollectionConfig.LAW_AUTHORITY_MAPPING_COLLECTION_NAME
        })
        self._prefetch_agencies()

    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------

    def get_handler_name(self) -> str:
        return "extract_law_authority"

    def _get_response_topic(self) -> str:
        return PreprocessTopics.EXTRACT_LAW_AUTHORITY_RESPONSE_TOPIC

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
                        "authority_extraction": step_info,
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

            logger.info("update_pipeline_state_success", action="_update_pipeline_state",
                        doc_id=doc_id, status=status)
        except Exception as e:
            logger.error("pipeline_state_update_failed", action="_update_pipeline_state", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)

    @staticmethod
    def _make_response(request_id: str) -> Dict[str, Any]:
        return {
            "request_id": request_id,
            "status":     True,
            "doc_id":     None,
            "segments":   [],
            "records":    [],
            "summary":    {"assignments_count": 0, "segments_processed": 0},
        }

    # ------------------------------------------------------------------
    # Main message processor
    # ------------------------------------------------------------------

    def process_message(self, raw_message) -> None:
        # --- Trace context ---
        self._init_trace_context(raw_message)
        bind_contextvars(task="KafkaExtractLawAuthority")

        # --- Parse message ---
        data       = self._parse_message(raw_message)
        request_id = self._bind_request_context(data)
        doc_id     = data.get("doc_id")
        doc_content = data.get("doc_content")

        start_at = self._now()
        start    = time.time()
        response = self._make_response(request_id)
        response["doc_id"] = str(doc_id) if doc_id is not None else None

        try:
            # --- Step 1: Fetch segments ---
            bind_contextvars(step="step_1_fetch_segments")
            segments = self._fetch_segments(doc_id)
            if not segments:
                response["status"] = False
                logger.error("extract_law_authority_failed", action="process_message",
                             **{"event.status": "failed", "error.code": "NOSEG",
                                "error.message": "No segments found for doc_id"},
                             doc_id=doc_id)
            else:
                # --- Step 2: Extract law authority ---
                bind_contextvars(step="step_2_extract_law_authority")
                ext_start = time.time()
                segments_resp, records, total_assignments = self._extract_all(segments)
                ext_duration = round(time.time() - ext_start, 3)
                logger.info("extract_law_authority_success", action="process_message",
                            **{"event.duration": ext_duration, "event.status": "success"},
                            doc_id=doc_id, total_assignments=total_assignments,
                            segments_processed=len(segments_resp))

                response["segments"] = segments_resp
                response["records"]  = records
                response["summary"]  = {
                    "assignments_count":  total_assignments,
                    "segments_processed": len(segments_resp),
                }
                response["status"] = True

        except Exception as e:
            response["status"] = False
            self._update_pipeline_state(doc_id, "FAILED", start_at)
            logger.error("extract_law_authority_failed", action="process_message",
                         **{"event.status": "failed",
                            "event.duration": round(time.time() - start, 3),
                            "error.code": "SYS", "error.message": str(e)}, exc_info=True)

        # --- Step 3: Insert law authority to MongoDB ---
        bind_contextvars(step="step_3_insert_law_authority_to_mongodb")
        insert_status = self._insert_law_authority(doc_id, response)
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
            },
        )

        total_duration = round(time.time() - start, 3)
        if response["status"]:
            logger.info("process_law_authority_message_success", action="process_message",
                        **{"event.duration": total_duration, "event.status": "success"},
                        doc_id=doc_id)
        else:
            logger.error("process_law_authority_message_failed", action="process_message",
                         **{"event.duration": total_duration, "event.status": "failed"},
                         doc_id=doc_id)

    # --------------------------------------------------------------    ----
    # Insert law authority
    # ------------------------------------------------------------------
    def _insert_law_authority(
            self,
            doc_id: str,
            response: Dict[str, Any],
        ) -> bool:
        """
        Insert authority records + mappings vào draft collections.
        Chỉ thực hiện khi extraction thành công (status=True).
        """
        if not doc_id:
            logger.warning("insert_law_authority_skipped_null_doc_id")
            return False

        if not response.get("status"):
            logger.warning("insert_law_authority_skipped_failed_extraction", doc_id=doc_id)
            return False

        try:
            now            = self._now()
            formal_records = response.get("records", [])
            # --- Insert law_authorities + law_authority_mapping ---
            authorities_created, mappings_created = 0, 0

            for record in formal_records:
                try:
                    authority_id  = str(uuid.uuid4())
                    article_id    = record.get("article_id")
                    lookup_doc_id = None

                    if article_id:
                        article_doc = self._db["articles"].find_one(
                            {"article_id": article_id}, {"doc_id": 1}
                        )
                        if article_doc:
                            lookup_doc_id = article_doc.get("doc_id")

                    # --- Insert law_authorities ---
                    self._db["law_authority"].insert_one({
                        "authority_id":       authority_id,
                        "authority_content":  record.get("authority_content", ""),
                        "doc_effective_date": "",
                        "doc_expiry_date":    "",
                        "effective_status_id": "",
                        "status":             "ACTIVE",
                        "created_at":         now,
                        "created_by":         "admin",
                        "last_modified_at":   now,
                        "last_modified_by":   "admin",
                    })
                    authorities_created += 1

                    # --- Insert law_authority_mapping ---
                    if lookup_doc_id and article_id:
                        existing = self._db["authority_mapping"].find_one({
                            "doc_id":       lookup_doc_id,
                            "article_id":   article_id,
                            "authority_id": authority_id,
                            "agency_id":    record.get("agency_id"),
                        })
                        if not existing:
                            self._db["authority_mapping"].insert_one({
                                "authority_id":     authority_id,
                                "doc_id":           lookup_doc_id,
                                "article_id":       article_id,
                                "agency_id":        record.get("agency_id") or "",
                                "created_at":       now,
                                "created_by":       "admin",
                                "last_modified_at": now,
                                "last_modified_by": "admin",
                            })
                            mappings_created += 1
                    else:
                        logger.warning("mapping_skipped_missing_ids",
                                    authority_id=authority_id,
                                    doc_id=lookup_doc_id, article_id=article_id)

                except Exception as e:
                    logger.error("authority_record_processing_failed",
                                **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
                    continue

            logger.debug("insert_law_authority_summary", action="_insert_law_authority",
                         doc_id=doc_id, total=len(formal_records),
                         authorities_created=authorities_created,
                         mappings_created=mappings_created)

        except Exception as e:
            logger.error("insert_law_authority_failed", doc_id=doc_id,
                        **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)
            return False
        return True

    # ------------------------------------------------------------------
    # Segment helpers
    # ------------------------------------------------------------------

    def _prefetch_agencies(self) -> None:
        """Fetch active agencies and set the core extractor's AGENCY_LIST."""
        try:
            cursor = self._db["law_agencies"].find(
                {"status": {"$in": ["ACTIVE", "Active", "active", None]}},
                {"_id": 0, "agency_name": 1},
            )
            names = [
                d["agency_name"].strip()
                for d in cursor
                if isinstance(d.get("agency_name"), str) and d["agency_name"].strip()
            ]
            self._set_agency_list(names)
        except Exception as e:
            logger.error("prefetch_agencies_failed",
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            self._set_agency_list([])

    def _fetch_segments(self, doc_id) -> list:
        candidates = []
        if doc_id is not None:
            candidates.append(doc_id)
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

        try:
            cursor = self._db["articles"].find(
                {"doc_id": {"$in": candidates}},
                {"_id": 0, "article_id": 1, "article_title": 1, "article_content": 1, "article_index": 1},
            )
            segments = list(cursor)
            logger.debug("segments_fetched", count=len(segments), doc_id=doc_id)
            return segments
        except Exception as e:
            logger.error("fetch_segments_failed", doc_id=doc_id,
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            return []

    def _fetch_classes_map(self, article_ids: list) -> dict:
        classes_map: dict = {}
        if not article_ids:
            return classes_map
        try:
            cursor = self._db["article_class"].find(
                {"article_id": {"$in": article_ids}},
                {"article_id": 1, "class": 1},
            )
            for doc in cursor:
                aid     = doc.get("article_id")
                cls_val = doc.get("class", [])
                classes_map[aid] = cls_val if isinstance(cls_val, list) else []
        except Exception as e:
            logger.error("fetch_classes_map_failed",
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
        return classes_map

    def _resolve_agency_id(self, agency_name) -> Any:
        if not isinstance(agency_name, str) or not agency_name.strip():
            return None
        try:
            ag = self._db["law_agencies"].find_one(
                {"agency_name": agency_name}, {"_id": 0, "agency_id": 1}
            )
            return ag.get("agency_id") if ag else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Extraction logic
    # ------------------------------------------------------------------

    def _extract_all(self, segments: list):
        article_ids = [seg.get("article_id") for seg in segments if isinstance(seg, dict)]
        classes_map = self._fetch_classes_map(article_ids)

        segments_resp:     list = []
        records:           list = []
        total_assignments        = 0

        for seg in segments:
            article_id           = seg.get("article_id")
            article_title        = (seg.get("article_title") or "").strip()
            article_content      = (seg.get("article_content") or "").strip()
            seg_content          = f"{article_title}\n{article_content}".strip()
            article_class_values = classes_map.get(article_id, [])

            try:
                assignment = self._extract_segment_assignments(seg_content)
            except Exception as e:
                logger.error("extract_assignments_failed",
                             **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
                assignment = {"has_pattern": False, "agency": None, "items": []}

            agency_name = assignment.get("agency") if isinstance(assignment, dict) else None
            agency_id   = self._resolve_agency_id(agency_name)
            items       = (assignment.get("items") if isinstance(assignment, dict) else []) or []

            logger.debug("segment_result",
                         article_id=article_id,
                         agency=agency_name,
                         has_pattern=assignment.get("has_pattern") if isinstance(assignment, dict) else None,
                         items_count=len(items))

            if items:
                try:
                    recs = self._compose_formal_records(
                        article_id=article_id,
                        article_class=article_class_values,
                        agency_name=agency_name if isinstance(agency_name, str) else "",
                        agency_id=agency_id,
                        items=items,
                        created_by="root",
                    )
                    if isinstance(recs, list):
                        records.extend(recs)
                except Exception as e:
                    logger.error("compose_formal_records_failed",
                                 **{"error.code": "COMPOSE", "error.message": str(e)}, exc_info=True)

                segments_resp.append({
                    "article_id":    article_id,
                    "article_class": article_class_values,
                    "agency_name":   agency_name,
                    "agency_id":     agency_id,
                    "assignments":   items,
                })
                total_assignments += len(items)

        return segments_resp, records, total_assignments

    # ------------------------------------------------------------------
    # Extractor loader
    # ------------------------------------------------------------------

    @staticmethod
    def _load_extractor():
        from services.kafka.handlers.extractor.utils.authority_utils import (
            set_agency_list,
            extract_segment_assignments,
            compose_formal_records,
        )
        logger.debug("load_law_authority_extractor_success", action="_load_extractor")
        return set_agency_list, extract_segment_assignments, compose_formal_records