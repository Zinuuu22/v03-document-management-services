"""
Extract Social Relation Handler v2

Same Kafka input contract as extract_social_relation.py (doc_id payload, same
TOPIC/GROUP_ID/response topic), but extraction runs through the multi-stage
core.v03.social_extractor_v2 pipeline (source selection -> frame extraction ->
frame cleaning -> relation rendering -> group assignment -> final validation)
instead of the old single LLM call, and writes 3 Mongo collections instead of 2:
    - law_social_relation_group  (NEW master collection)
    - law_social_relation        (existing master collection)
    - law_social_relation_mapping (existing mapping collection)

Write policy (masters are never deleted, only reused/updated by name; mapping is
a full-replace per processed scope — see _clear_old_mappings):
    - group:    upsert by social_relation_group_name_norm (unchanged key); doc_id
                is set/overwritten to the current run's doc_id on every write
                (insert or reuse) -- single doc_id per group, last writer wins,
                no multi-doc model this round.
    - relation: upsert by (social_relation_name_norm, social_relation_group_id)
    - mapping:  clear old rows for (doc_id, article_id in processed_article_ids),
                then insert/upsert by (doc_id, article_id, social_relation_id)

extract_social_relation.py (the old single-call handler) is left untouched on
disk; the Kafka manager simply no longer loads it for the "extractor" flow (see
services/kafka/manager/extract.py). No Elasticsearch sync here.
"""

import os
import sys
import time
from datetime import datetime
from uuid import uuid4
from typing import Dict, Any
import structlog
from structlog.contextvars import bind_contextvars
from pymongo import ReturnDocument

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import PreprocessTopics, AppConfig, SignalRConfig, MongoDBCollectionConfig, ExtractBatchConfig
from core.v03.social_extractor_v2.utils import normalize_name_fold_d

logger = structlog.get_logger()


class ExtractSocialRelationV2Handler(BaseConsumer):

    TOPIC       = PreprocessTopics.EXTRACT_SOCIAL_RELATION_QUERY_TOPIC
    GROUP_ID    = PreprocessTopics.EXTRACT_SOCIAL_RELATION_GROUP
    NUM_WORKERS = AppConfig.EXTRACT_NORM_SOCIAL_RELATION_NUMBER_WORKER

    def __init__(self):
        super().__init__()
        (
            self._generate_social_relations_for_segments,
            self._compose_formal_records,
        ) = self._load_extractor()
        self._db = self._init_db(extra_collections={
            "articles":                MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME,
            "article_class":           MongoDBCollectionConfig.LAW_ARTICLE_CLASS_COLLECTION_NAME,
            "social_relation_group":   MongoDBCollectionConfig.LAW_SOCIAL_RELATION_GROUP_COLLECTION_NAME,
            "social_relation":         MongoDBCollectionConfig.LAW_SOCIAL_RELATION_COLLECTION_NAME,
            "social_relation_mapping": MongoDBCollectionConfig.LAW_SOCIAL_RELATION_MAPPING_COLLECTION_NAME,
            "pipeline":                MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME,
        })

    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------

    def get_handler_name(self) -> str:
        return "extract_social_relation_v2"

    def _get_response_topic(self) -> str:
        return PreprocessTopics.EXTRACT_SOCIAL_RELATION_RESPONSE_TOPIC

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

        # Các field pipeline cần kiểm tra (giữ nguyên key "social_relation_extraction"
        # vì các handler khác trong pipeline_document_state đang dựa vào key này).
        extraction_fields = [
            "metadata_extraction",
            "keyword_extraction",
            "relationship_extraction",
            "article_relationship_extraction",
            "regulated_entity_extraction",
            "social_relation_extraction",
            "authority_extraction"
            ]

        try:
            self._db["pipeline"].update_one(
                {"doc_id": doc_id},
                {
                    "$set": {
                        "social_relation_extraction": step_info,
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
                    logger.debug("update_pipeline_all_steps_completed", action="_update_pipeline_state", doc_id=doc_id)

            logger.debug("update_pipeline_state_success", action="_update_pipeline_state", doc_id=doc_id, status=status)
        except Exception as e:
            logger.error("update_pipeline_state_failed", action="_update_pipeline_state", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)

    @staticmethod
    def _make_response(request_id: str) -> Dict[str, Any]:
        return {
            "request_id": request_id,
            "status":     True,
            "doc_id":     None,
            "segments":   [],
            "summary":    {"relations_count": 0, "segments_processed": 0},
        }

    # ------------------------------------------------------------------
    # Main message processor
    # ------------------------------------------------------------------

    async def process_message(self, raw_message) -> None:
        # --- Trace context ---
        self._init_trace_context(raw_message)

        # --- Bind task ---
        bind_contextvars(task="KafkaExtractSocialRelationV2")

        # --- Parse message ---
        data       = self._parse_message(raw_message)
        request_id = self._bind_request_context(data)
        doc_id     = data.get("doc_id")
        doc_id_str = str(doc_id) if doc_id is not None else None

        start_at = self._now()
        start    = time.time()
        response = self._make_response(request_id)
        response["doc_id"] = doc_id_str

        logger.debug("consume_kafka_message_parsed", action="process_message", doc_id=doc_id_str)

        try:
            # --- Step 1: Fetch segments ---
            bind_contextvars(step="step_1_fetch_segments")
            segments = self._fetch_segments(doc_id)

            if not segments:
                response["status"] = False
                logger.error("extract_social_relation_v2_failed", action="process_message", **{"event.status": "failed", "error.code": "NOSEG", "error.message": "No segments found for doc_id"}, doc_id=doc_id)
            else:
                # --- Step 2: Extract social relations (multi-stage) + write Mongo ---
                bind_contextvars(step="step_2_extract_social_relation")
                ext_start = time.time()
                segments_resp, summary = await self._extract_all(segments, doc_id_str)
                ext_duration = round(time.time() - ext_start, 3)
                logger.info("extract_social_relation_v2_success", action="process_message", **{"event.duration": ext_duration, "event.status": "success"}, doc_id=doc_id_str, **summary)

                response["segments"] = segments_resp
                response["summary"]  = summary
                response["status"]   = True

        except Exception as e:
            response["status"] = False
            logger.error("extract_social_relation_v2_failed", action="process_message", **{"event.status": "failed", "event.duration": round(time.time() - start, 3), "error.code": "SYS", "error.message": str(e)}, exc_info=True)

        # --- Update pipeline state (single point, before notification) ---
        bind_contextvars(step="step_3_update_pipeline_state")
        if response["status"]:
            self._update_pipeline_state(doc_id, "PROCESSED", start_at)
        else:
            self._update_pipeline_state(doc_id, "FAILED", start_at)

        # --- Step 4: Send Response to Kafka ---
        bind_contextvars(step="step_4_send_kafka_response")
        self._send_response(response)

        # --- SignalR notification ---
        logger.debug("send_signalr_notification_started", action="process_message", doc_id=doc_id_str)
        self.push_to_signalr_api(
            api_url=SignalRConfig.API_URL,
            topic=SignalRConfig.UPLOAD_TOPIC,
            message={
                "request_id": request_id,
                "status":     response["status"],
                "extract_social_relation_status": response["status"],
            },
        )

        total_duration = round(time.time() - start, 3)
        if response["status"]:
            logger.info("process_social_relation_v2_message_success",
                        action="process_message",
                        **{"event.duration": total_duration, "event.status": "success"},
                        doc_id=doc_id_str)
        else:
            logger.error("process_social_relation_v2_message_failed",
                         action="process_message",
                         **{"event.duration": total_duration, "event.status": "failed"},
                         doc_id=doc_id_str)

    # ------------------------------------------------------------------
    # Segment helpers
    # ------------------------------------------------------------------

    def _fetch_segments(self, doc_id) -> list:
        logger.debug("fetch_segments_started", action="_fetch_segments", doc_id=doc_id)
        try:
            cursor = self._db["articles"].find(
                {"doc_id": doc_id},
                {"_id": 0, "article_id": 1, "article_title": 1, "article_content": 1, "article_index": 1},
            )
            segments = list(cursor)
            logger.debug("fetch_segments_success", action="_fetch_segments", count=len(segments), doc_id=doc_id)
            return segments
        except Exception as e:
            logger.error("fetch_segments_failed", action="_fetch_segments", doc_id=doc_id,
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
            logger.error("fetch_classes_map_failed", action="_fetch_classes_map",
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
        return classes_map

    # ------------------------------------------------------------------
    # Extraction logic (multi-stage pipeline + 3-collection Mongo write)
    # ------------------------------------------------------------------

    async def _extract_all(self, segments: list, doc_id_str: str):
        from core.v03.social_extractor_v2 import PromptNotConfiguredError

        article_ids = [seg.get("article_id") for seg in segments if isinstance(seg, dict)]
        classes_map = self._fetch_classes_map(article_ids)

        # core.v03.social_extractor_v2 expects {"article_id","title","content","index"}.
        segments_payload = [
            {
                "article_id": seg.get("article_id"),
                "title":      (seg.get("article_title") or "").strip(),
                "content":    (seg.get("article_content") or "").strip(),
                "index":      seg.get("article_index"),
            }
            for seg in segments if isinstance(seg, dict)
        ]

        concurrency = ExtractBatchConfig.SOCIAL_RELATION_BATCH_SIZE

        try:
            result = await self._generate_social_relations_for_segments(
                segments_payload, classes_map, concurrency=concurrency, debug=True,
            )
        except PromptNotConfiguredError as e:
            # Production stages never fall back silently; surface this clearly and
            # treat the whole doc as "no relations extracted this run" (segments
            # still get a clean response, but no new mapping is written below).
            logger.error("extract_social_relation_v2_prompt_not_configured", action="_extract_all",
                         doc_id=doc_id_str, **{"error.code": "PROMPT", "error.message": str(e)})
            result = {"segments": [], "source_selection_summary": {}}

        # Single timestamp snapshot for this whole doc run (group/relation/mapping
        # all share it, so a run never straddles two different "now" values).
        now_dt  = datetime.now().astimezone()
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Mapping is a full-replace per processed scope (doc_id + processed article_ids).
        # Group/relation masters are NEVER deleted here.
        mappings_deleted = self._clear_old_mappings(doc_id_str, article_ids)

        segments_resp: list = []
        total_relations          = 0
        groups_upserted          = 0
        relations_upserted       = 0
        mappings_inserted        = 0
        raw_frames_count         = 0
        clean_frames_count       = 0
        candidate_relations_count = 0
        group_assignments_count  = 0
        prompt_errors            = 0

        for seg in result.get("segments", []):
            article_id           = seg.get("article_id")
            article_class_values = seg.get("article_class", []) if isinstance(seg.get("article_class"), list) else []
            social_relations     = seg.get("extraction", {}).get("social_relations", []) if isinstance(seg.get("extraction"), dict) else []
            pipeline_debug       = seg.get("debug") if isinstance(seg.get("debug"), dict) else {}

            raw_frames_count          += len(pipeline_debug.get("raw_frames", []) or [])
            clean_frames_count        += len(pipeline_debug.get("clean_frames", []) or [])
            candidate_relations_count += len(pipeline_debug.get("candidate_relations", []) or [])
            group_assignments_count   += len(pipeline_debug.get("group_assignments", []) or [])

            seg_error = seg.get("error")
            if seg_error and "not configured" in str(seg_error).lower():
                prompt_errors += 1

            segments_resp.append({
                "article_id":       article_id,
                "article_class":    article_class_values,
                "social_relations": social_relations,
            })
            total_relations += len(social_relations)

            if not social_relations:
                continue

            formal = self._compose_formal_records(
                social_relations, doc_id=doc_id_str, article_id=article_id,
                article_class=article_class_values, created_by="admin", now=now_dt,
            )

            group_id_remap: Dict[str, str] = {}
            for g in formal.get("groups", []):
                group_name = g["social_relation_group_name"]
                group_name_norm = normalize_name_fold_d(group_name)
                resolved_group_id = self._upsert_group(group_name, group_name_norm, doc_id_str, now_str)
                group_id_remap[g["social_relation_group_id"]] = resolved_group_id
                groups_upserted += 1

            relation_id_remap: Dict[str, str] = {}
            for r in formal.get("relations", []):
                resolved_group_id = group_id_remap.get(r["social_relation_group_id"], r["social_relation_group_id"])
                relation_name = r["social_relation_name"]
                relation_name_norm = normalize_name_fold_d(relation_name)
                resolved_relation_id = self._upsert_relation(
                    relation_name=relation_name,
                    relation_name_norm=relation_name_norm,
                    social_relation=r["social_relation"],
                    group_id=resolved_group_id,
                    group_name=r["social_relation_group_name"],
                    now_str=now_str,
                )
                relation_id_remap[r["social_relation_id"]] = resolved_relation_id
                relations_upserted += 1

            for m in formal.get("mappings", []):
                mapping_record = dict(m)
                mapping_record["social_relation_id"] = relation_id_remap.get(
                    m.get("social_relation_id"), m.get("social_relation_id")
                )
                if self._upsert_mapping(mapping_record):
                    mappings_inserted += 1

        if prompt_errors:
            logger.error("extract_social_relation_v2_prompt_not_configured", action="_extract_all",
                         doc_id=doc_id_str,
                         **{"error.code": "PROMPT", "error.message": "one or more segments hit an unconfigured prompt"},
                         segments_with_prompt_error=prompt_errors)

        summary = {
            "relations_count":            total_relations,
            "segments_processed":         len(segments_resp),
            "raw_frames_count":           raw_frames_count,
            "clean_frames_count":         clean_frames_count,
            "candidate_relations_count":  candidate_relations_count,
            "group_assignments_count":    group_assignments_count,
            "groups_upserted_count":      groups_upserted,
            "relations_upserted_count":   relations_upserted,
            "mappings_inserted_count":    mappings_inserted,
            "mappings_deleted_count":     mappings_deleted,
        }
        return segments_resp, summary

    # ------------------------------------------------------------------
    # Mongo write helpers (3-collection schema, upsert/reuse by norm key)
    # ------------------------------------------------------------------

    def _upsert_group(self, group_name: str, group_name_norm: str, doc_id_str: str, now_str: str) -> str:
        """Reuse an existing group by social_relation_group_name_norm, or insert a new one.

        Upsert key is unchanged (social_relation_group_name_norm only) -- this is
        still a single-doc-id-per-group model, not multi-doc. `doc_id` is set to
        the current run's doc_id on every insert AND every reuse (last writer
        wins); no doc_ids list, no cross-doc sharing logic this round."""
        result = self._db["social_relation_group"].find_one_and_update(
            {"social_relation_group_name_norm": group_name_norm},
            {
                "$set": {
                    "doc_id":           doc_id_str,
                    "social_relation_group_name": group_name,
                    "status":           "ACTIVE",
                    "last_modified_at": now_str,
                    "last_modified_by": "admin",
                },
                "$setOnInsert": {
                    "social_relation_group_id":      str(uuid4()),
                    "social_relation_group_name_norm": group_name_norm,
                    "created_at": now_str,
                    "created_by": "admin",
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return result["social_relation_group_id"]

    def _upsert_relation(self, *, relation_name: str, relation_name_norm: str, social_relation: str,
                         group_id: str, group_name: str, now_str: str) -> str:
        """Reuse an existing relation by (social_relation_name_norm, social_relation_group_id), or insert a new one."""
        result = self._db["social_relation"].find_one_and_update(
            {"social_relation_name_norm": relation_name_norm, "social_relation_group_id": group_id},
            {
                "$set": {
                    "social_relation":             social_relation,
                    "social_relation_group_name":  group_name,
                    "status":           "ACTIVE",
                    "last_modified_at": now_str,
                    "last_modified_by": "admin",
                },
                "$setOnInsert": {
                    "social_relation_id":        str(uuid4()),
                    "social_relation_name":      relation_name,
                    "social_relation_name_norm": relation_name_norm,
                    "social_relation_group_id":  group_id,
                    "created_at": now_str,
                    "created_by": "admin",
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return result["social_relation_id"]

    def _clear_old_mappings(self, doc_id_str: str, article_ids: list) -> int:
        """Full-replace cleanup scoped to (doc_id, article_id in article_ids).
        Never touches group/relation master collections."""
        if not doc_id_str or not article_ids:
            return 0
        try:
            result = self._db["social_relation_mapping"].delete_many(
                {"doc_id": doc_id_str, "article_id": {"$in": article_ids}}
            )
            logger.debug("clear_old_mappings_success", action="_clear_old_mappings",
                        doc_id=doc_id_str, deleted=result.deleted_count)
            return result.deleted_count
        except Exception as e:
            logger.error("clear_old_mappings_failed", action="_clear_old_mappings", doc_id=doc_id_str,
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            return 0

    def _upsert_mapping(self, record: dict) -> bool:
        """Insert a mapping row, unique on (doc_id, article_id, social_relation_id)."""
        if not record.get("doc_id") or not record.get("article_id") or not record.get("social_relation_id"):
            logger.warning("upsert_mapping_skipped_missing_keys", action="_upsert_mapping",
                           article_id=record.get("article_id"), social_relation_id=record.get("social_relation_id"))
            return False
        try:
            self._db["social_relation_mapping"].update_one(
                {
                    "doc_id":             record["doc_id"],
                    "article_id":         record["article_id"],
                    "social_relation_id": record["social_relation_id"],
                },
                {"$setOnInsert": record},
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error("upsert_mapping_failed", action="_upsert_mapping",
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Extractor loader
    # ------------------------------------------------------------------

    @staticmethod
    def _load_extractor():
        from core.v03.social_extractor_v2 import generate_social_relations_for_segments_async, compose_formal_records
        logger.debug("load_social_relation_extractor_v2_success", action="_load_extractor")
        return generate_social_relations_for_segments_async, compose_formal_records
