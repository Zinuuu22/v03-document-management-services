"""
Extract Relationship Handler
Migrated from services/kafka/v03/extract_relationship/consumer.py
"""

import os
import sys
import time
import uuid
import asyncio
import httpx
from datetime import datetime
from typing import Dict, Any, List
import structlog
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import PreprocessTopics, AppConfig, SignalRConfig, MongoDBCollectionConfig, ExtractBatchConfig

logger = structlog.get_logger()

REFERENCE_TYPE_MAPPING = {
    "base":         "BASIS",
    "amend":        "AMENDED",
    "add":          "AMENDED",
    "repeal_apart": "AMENDED",
    "replace":      "REPLACED",
    "repeal_full":  "REPLACED",
    "detail":       "DETAIL",
    "referential":  "REFERENTIAL",
}
DEFAULT_SOURCE_TYPE = "DOCUMENT"
DEFAULT_TARGET_TYPE = "DOCUMENT"

# Các loại quan hệ do module trích xuất quan hệ văn bản này quản lý. Reconcile chỉ xoá/ghi
# lại trong phạm vi này để không đụng tới reference do hệ thống khác tạo cho cùng văn bản.
MANAGED_REFERENCE_TYPES = sorted(set(REFERENCE_TYPE_MAPPING.values()))


class ExtractRelationshipHandler(BaseConsumer):

    TOPIC      = PreprocessTopics.EXTRACT_RELATIONSHIP_QUERY_TOPIC
    GROUP_ID   = PreprocessTopics.EXTRACT_RELATIONSHIP_GROUP
    NUM_WORKERS = AppConfig.EXTRACT_NORM_RELATIONSHIP_NUMBER_WORKER

    def __init__(self):
        super().__init__()
        self._relationship_extractor = self._load_relationship_extractor()
        self._metadata_extractor     = self._load_metadata_extractor()
        self._db = self._init_db(
            extra_collections={
                "articles": MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME,
                "pipeline": MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME,
                "references": MongoDBCollectionConfig.LAW_REFERENCE_COLLECTION_NAME,
                "references_draft": MongoDBCollectionConfig.LAW_REFERENCE_DRAFT_COLLECTION_NAME,
            }
        )

    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------

    def get_handler_name(self) -> str:
        return "extract_relationship"

    def _get_response_topic(self) -> str:
        return PreprocessTopics.EXTRACT_RELATIONSHIP_RESPONSE_TOPIC

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
                        "relationship_extraction": step_info,
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
            "request_id":   request_id,
            "status":       True,
            "base":         [],
            "amend":        [],
            "add":          [],
            "replace":      [],
            "repeal_apart": [],
            "repeal_full":  [],
            "detail":       [],
            "referential":  [],
        }

    # ------------------------------------------------------------------
    # Main message processor
    # ------------------------------------------------------------------

    async def process_message(self, raw_message) -> None:
        # --- Trace context ---
        self._init_trace_context(raw_message)
        bind_contextvars(task="KafkaExtractRelationship")

        # --- Parse message ---
        data       = self._parse_message(raw_message)
        request_id = self._bind_request_context(data)
        doc_id     = data.get("doc_id")
        doc_content = data.get("doc_content")

        start_at = self._now()
        start    = time.time()
        response = self._make_response(request_id)
        mapping_relationships: List[Dict] = []
        batch_size = ExtractBatchConfig.RELATIONSHIP_BATCH_SIZE

        try:
            # --- Step 1: Fetch content ---
            bind_contextvars(step="step_1_fetch_content")
            if doc_content and len(doc_content) > 1:
                content = doc_content
            else:
                content = self._fetch_raw_content(doc_id=doc_id)

            if not content:
                response["status"] = False
                logger.error("extract_relationship_failed", action="process_message",
                             **{"event.status": "failed", "error.code": "DB",
                                "error.message": "Content not found for doc_id"},
                             doc_id=doc_id)
            else:
                # --- Step 2: Extract metadata + relationships ---
                bind_contextvars(step="step_2_extract_relationship")
                document = self._db["documents"].find_one({"doc_id": doc_id}) or {}
                document_code = document.get("doc_code")
                document_name = document.get("doc_title")

                segments = self._fetch_segments(doc_id)

                if not segments:
                    response["status"] = False
                    logger.error("extract_relationship_failed", action="process_message",
                                 **{"event.status": "failed", "error.code": "NOSEG",
                                    "error.message": "No segments found for doc_id"},
                                 doc_id=doc_id)
                else:
                    if not content:
                        content = self._build_content_from_segments(segments)
                    ext_start = time.time()


                    _, mapping_relationships = await self._relationship_extractor(
                        document_content=content,
                        document_name=document_name,
                        segments=segments,
                        document_code=document_code,
                        batch_size=batch_size
                    )
                    mapping_relationships = mapping_relationships or []
                    response.update(self._post_process(mapping_relationships))
                    ext_duration = round(time.time() - ext_start, 3)
                    logger.info("extract_relationship_success", action="process_message",
                                **{"event.duration": ext_duration, "event.status": "success"},
                                doc_id=doc_id,
                                relationships_count=len(mapping_relationships))

        except Exception as e:
            response["status"] = False
            self._update_pipeline_state(doc_id, "FAILED", start_at)
            logger.error("extract_relationship_failed", action="process_message",
                         **{"event.status": "failed",
                            "event.duration": round(time.time() - start, 3),
                            "error.code": "SYS", "error.message": str(e)}, exc_info=True)

        # --- Step 3: Insert relationships to MongoDB ---
        bind_contextvars(step="step_3_insert_relationship_to_mongodb")
        insert_status = self._insert_relationships(doc_id, response)
        # Quan hệ chưa resolve được target doc_id (code == "") -> lưu draft để không bị mất.
        if response.get("status"):
            self._insert_draft_relationships(doc_id, mapping_relationships)
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
                "extract_relationship_status": response["status"],
            },
        )

        total_duration = round(time.time() - start, 3)
        if response["status"]:
            logger.info("process_relationship_message_success", action="process_message",
                        **{"event.duration": total_duration, "event.status": "success"},
                        doc_id=doc_id)
        else:
            logger.error("process_relationship_message_failed", action="process_message",
                         **{"event.duration": total_duration, "event.status": "failed"},
                         doc_id=doc_id)

    # ------------------------------------------------------------------
    # Post-process
    # ------------------------------------------------------------------

    @staticmethod
    def _post_process(mapping_relationships: List[Dict]) -> Dict[str, Any]:
        final_relationships = {
            "base":         [],
            "amend":        [],
            "add":          [],
            "replace":      [],
            "repeal_apart": [],
            "repeal_full":  [],
            "detail":       [],
            "referential":  [],
        }
        for relationship in mapping_relationships:
            code     = relationship["code"]
            rel_type = relationship["rel_type"]
            final_relationships.setdefault(rel_type, []).append(code)
        return final_relationships

    # ------------------------------------------------------------------
    # Insert relationships
    # ------------------------------------------------------------------

    def _insert_relationships(
        self,
        doc_id: str,
        response: Dict[str, Any],
    ) -> bool:
        """
        Flatten extracted relationships and store them as draft reference documents.
        Only executed when extraction is successful (status=True).
        """
        if not doc_id:
            logger.warning("insert_relationships_skipped_null_doc_id")
            return False

        if not response.get("status"):
            logger.warning("insert_relationships_skipped_failed_extraction", doc_id=doc_id)
            return False

        try:
            now = self._now()

            # --- Fetch source metadata ---
            document_metadata = self._db["documents"].find_one({"doc_id": doc_id}) or {}
            source_id         = str(document_metadata.get("doc_id") or doc_id)
            effective_status_id = document_metadata.get("effective_status_id", "Còn hiệu lực")

            # --- Reconcile: lần trích xuất mới THAY THẾ hoàn toàn kết quả cũ của hệ thống cho
            # văn bản này. Xoá reference do hệ thống ghi trước đó (giữ lại bản do người dùng thêm)
            # để tránh tồn đọng/nhân đôi tích lũy qua nhiều lần chạy lại.
            self._db["references"].delete_many({
                "source_id": source_id,
                "created_by": "system",
                "reference_type": {"$in": MANAGED_REFERENCE_TYPES},
            })

            # --- Flatten relationships ---
            flattened = []
            seen_pairs: set = set()

            for relation_key, targets in response.items():
                if relation_key in {"request_id", "status"}:
                    continue
                if isinstance(targets, dict):
                    targets = list(targets.values())
                if not isinstance(targets, (list, tuple, set)):
                    logger.debug("unexpected_relationship_type",
                                relation_key=relation_key, type=type(targets))
                    continue

                mapped_type = REFERENCE_TYPE_MAPPING.get(relation_key, relation_key.upper())

                for target in targets:
                    if target in (None, "", []):
                        continue

                    target_id = str(target)
                    pair_key  = (source_id, target_id, mapped_type)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    flattened.append({
                        "reference_id":     str(uuid.uuid4()),
                        "source_id":        source_id,
                        "target_id":        target_id,
                        "effective_status_id": effective_status_id,
                        "reference_type":   mapped_type,
                        "created_at":     now,
                        "created_by":     "system",
                        "last_modified_at": now,
                        "last_modified_by": "system",
                    })

            references = self._db["references"]
            if flattened:
                for r in flattened:
                    references.update_one(
                        {"source_id": r["source_id"],"target_id": r["target_id"],"reference_type": r["reference_type"]},  
                        {"$set": r},  
                        upsert=True
                    )
                logger.debug("insert_references_success", action="_insert_relationships",
                             doc_id=doc_id, inserted=len(flattened))
            else:
                logger.debug("insert_references_empty", action="_insert_relationships",
                             doc_id=doc_id)

        except Exception as e:
            logger.error("insert_relationships_failed", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)
            return False
        return True

    # ------------------------------------------------------------------
    # Insert draft relationships (quan hệ chưa map được target doc_id)
    # ------------------------------------------------------------------

    def _insert_draft_relationships(
        self,
        doc_id: str,
        mapping_relationships: List[Dict],
    ) -> bool:
        """
        Lưu các quan hệ không resolve được sang văn bản trong DB (code == "")
        vào collection law_reference_draft, giữ lại target_doc_title + target_doc_code
        để tránh mất dữ liệu. Chỉ chạy khi extraction thành công.
        """
        if not doc_id:
            logger.warning("insert_draft_relationships_skipped_null_doc_id")
            return False

        try:
            now = self._now()
            source_id = str(doc_id)

            # --- Reconcile: xoá draft do hệ thống ghi trước đó cho văn bản này để lần trích
            # xuất mới thay thế hoàn toàn (giữ lại bản do người dùng thêm thủ công).
            self._db["references_draft"].delete_many({
                "source_id": source_id,
                "created_by": "system",
                "reference_type": {"$in": MANAGED_REFERENCE_TYPES},
            })

            if not mapping_relationships:
                logger.debug("insert_draft_relationships_empty", action="_insert_draft_relationships", doc_id=doc_id)
                return True

            drafts = []
            seen_pairs: set = set()

            for relationship in mapping_relationships:
                if not isinstance(relationship, dict):
                    continue
                # Chỉ lấy quan hệ chưa resolve được target doc_id.
                if relationship.get("code"):
                    continue

                target_doc_title = (relationship.get("name") or "").strip()
                if not target_doc_title:
                    continue

                rel_type = relationship.get("rel_type", "")
                reference_type = REFERENCE_TYPE_MAPPING.get(rel_type, rel_type.upper() if rel_type else "")
                target_doc_code = (relationship.get("document_code") or "").strip()

                pair_key = (source_id, target_doc_title, reference_type)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                drafts.append({
                    "reference_id":     str(uuid.uuid4()),
                    "source_id":        source_id,
                    "target_doc_code":  target_doc_code,
                    "target_doc_title": target_doc_title,
                    "reference_type":   reference_type,
                    "rel_type":         rel_type,
                    "created_at":       now,
                    "created_by":       "system",
                    "last_modified_at": now,
                    "last_modified_by": "system",
                })

            references_draft = self._db["references_draft"]
            if drafts:
                for d in drafts:
                    references_draft.update_one(
                        {"source_id": d["source_id"], "target_doc_title": d["target_doc_title"], "reference_type": d["reference_type"]},
                        {"$set": d},
                        upsert=True
                    )
                logger.debug("insert_draft_references_success", action="_insert_draft_relationships",
                             doc_id=doc_id, inserted=len(drafts))
            else:
                logger.debug("insert_draft_references_empty", action="_insert_draft_relationships",
                             doc_id=doc_id)

        except Exception as e:
            logger.error("insert_draft_relationships_failed", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)
            return False
        return True

    # ------------------------------------------------------------------
    # Segment helpers
    # ------------------------------------------------------------------

    def _fetch_segments(self, doc_id) -> List[Dict]:
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

        try:
            cursor = self._db["articles"].find(
                {"doc_id": {"$in": candidates}},
                {
                    "_id":             0,
                    "article_id":      1,
                    "article_title":   1,
                    "article_content": 1,
                    "article_index":   1,
                },
            )
            return list(cursor)
        except Exception as e:
            logger.error("fetch_segments_failed", action="_fetch_segments",
                         doc_id=doc_id,
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
        return []

    @staticmethod
    def _build_content_from_segments(segments: List[Dict]) -> str:
        parts = []
        for seg in segments:
            title    = (seg.get("article_title") or "").strip()
            body     = (seg.get("article_content") or "").strip()
            seg_text = f"{title}\n{body}".strip()
            if seg_text:
                parts.append(seg_text)
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Metadata helper
    # ------------------------------------------------------------------

    async def _extract_metadata(self, content: str, batch_size: int = 10) -> Dict[str, Any]:  
        return await self._metadata_extractor(
            content=content,
            metadata_names=["document_code", "document_type", "document_name"],
            batch_size=batch_size,
        )

    # ------------------------------------------------------------------
    # Extractor loaders
    # ------------------------------------------------------------------

    @staticmethod
    def _load_relationship_extractor():
        from core.v03.relationship_extractor import extract_relationship_level_document
        logger.debug("load_relationship_extractor_success", action="_load_relationship_extractor")
        return extract_relationship_level_document

    @staticmethod
    def _load_metadata_extractor():
        from core.v03.metadata_extractor import extract_metadata_async
        logger.debug("load_metadata_extractor_success", action="_load_metadata_extractor")
        return extract_metadata_async