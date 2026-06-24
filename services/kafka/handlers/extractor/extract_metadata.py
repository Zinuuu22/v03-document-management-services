"""
Extract Metadata Handler
Migrated from services/kafka/v03/extract_metadata/consumer.py
"""

import os
import sys
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import re
import structlog
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import PreprocessTopics, AppConfig, SignalRConfig, MongoDBCollectionConfig, ExtractBatchConfig

logger = structlog.get_logger()


class ExtractMetadataHandler(BaseConsumer):

    TOPIC = PreprocessTopics.EXTRACT_METADATA_QUERY_TOPIC
    GROUP_ID = PreprocessTopics.EXTRACT_METADATA_GROUP
    NUM_WORKERS = AppConfig.EXTRACT_NORM_METADATA_NUMBER_WORKER

    def __init__(self):
        super().__init__()
        self._extractor = self._load_extractor()
        self._db = self._init_db(extra_collections={
            "pipeline": MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME,
            "law_doc_types": MongoDBCollectionConfig.LAW_DOCUMENT_TYPE_COLLECTION_NAME,
            "law_doc_category": MongoDBCollectionConfig.LAW_DOCUMENT_CATEGORY_COLLECTION_NAME,
            "law_issuing_level": MongoDBCollectionConfig.LAW_ISSUING_LEVEL_COLLECTION_NAME,
            "law_effective_status": MongoDBCollectionConfig.LAW_EFFECTIVE_STATUS_COLLECTION_NAME,
            "law_agencies": MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME,
            "law_signers": MongoDBCollectionConfig.LAW_SIGNERS_COLLECTION_NAME,
            "law_positions": MongoDBCollectionConfig.LAW_POSITIONS_COLLECTION_NAME,
        })

    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------

    def get_handler_name(self) -> str:
        return "extract_metadata"

    def _get_response_topic(self) -> str:
        return PreprocessTopics.EXTRACT_METADATA_RESPONSE_TOPIC

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
                        "metadata_extraction": step_info,
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
            "request_id":        request_id,
            "status":            True,
            "document_name":     None,
            "doc_code":          None,
            "document_type":     None,
            "agency":            None,
            "human_sign":        None,
            "effective_date":    None,
            "issue_date":        None,
            "end_effective_date": None,
            "effective_status":  None,
            "document_category": None,
            "document_level":    None,
        }

    # ------------------------------------------------------------------
    # Main message processor
    # ------------------------------------------------------------------

    async def process_message(self, raw_message) -> None:
        # --- Trace context ---
        self._init_trace_context(raw_message)
        bind_contextvars(task="KafkaExtractMetadata")

        # --- Parse message ---
        data       = self._parse_message(raw_message)
        request_id = self._bind_request_context(data)
        doc_id     = data.get("doc_id", "")
        doc_content = data.get("doc_content", "")

        start_at = self._now()
        start    = time.time()
        response = self._make_response(request_id)

        try:
            # --- Step 1: Fetch content ---
            bind_contextvars(step="step_1_fetch_content")
            if len(doc_content) > 1:
                raw_content = doc_content
            else:
                raw_content = self._fetch_raw_content(doc_id)

            batch_size = ExtractBatchConfig.METADATA_BATCH_SIZE
            if not raw_content:
                response["status"] = False
                logger.error("extract_metadata_failed", action="process_message",
                             **{"event.status": "failed", "error.code": "DB",
                                "error.message": "Content not found for doc_id"},
                             doc_id=doc_id)
            else:
                # --- Step 2: Extract metadata ---
                bind_contextvars(step="step_2_extract_metadata")
                ext_start = time.time()
                metadata  = await self._extractor(content=raw_content, batch_size=batch_size)
                response.update(metadata)

                # Normalize doc_code
                if not response.get("doc_code") and response.get("document_code"):
                    response["doc_code"] = response["document_code"]

                ext_duration = round(time.time() - ext_start, 3)
                logger.info("extract_metadata_success", action="process_message",
                            **{"event.duration": ext_duration, "event.status": "success"},
                            doc_id=doc_id)

        except Exception as e:
            response["status"] = False
            self._update_pipeline_state(doc_id, "FAILED", start_at)
            logger.error("extract_metadata_failed", action="process_message",
                         **{"event.status": "failed",
                            "event.duration": round(time.time() - start, 3),
                            "error.code": "SYS", "error.message": str(e)}, exc_info=True)

        # --- Step 3: Insert metadata to MongoDB ---
        bind_contextvars(step="step_3_insert_metadata_to_mongodb")
        insert_status = self._insert_metadata_to_law_documents(doc_id, response)
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
                "extract_metadata_status": response["status"],
            },
        )

        total_duration = round(time.time() - start, 3)
        if response["status"]:
            logger.info("process_metadata_message_success", action="process_message",
                        **{"event.duration": total_duration, "event.status": "success"},
                        doc_id=doc_id)
        else:
            logger.error("process_metadata_message_failed", action="process_message",
                         **{"event.duration": total_duration, "event.status": "failed"},
                         doc_id=doc_id)

    # ------------------------------------------------------------------
    # Insert metadata
    # ------------------------------------------------------------------

    def _insert_metadata_to_law_documents(self, doc_id: str, response: Dict[str, Any]) -> None:
        """
        Upsert metadata vào law_documents và resolve các collection vệ tinh.
        Chỉ thực hiện khi extraction thành công (status=True).
        """
        if not doc_id:
            logger.warning("insert_metadata_skipped_null_doc_id")
            return False

        if not response.get("status"):
            logger.warning("insert_metadata_skipped_failed_extraction", doc_id=doc_id)
            return False

        try:
            now = self._now()

            # --- Resolve collection vệ tinh ---
            type_id = self._resolve_catalog(
                collection=self._db["law_doc_types"],
                match_field="doc_type_name",
                match_value=response.get("document_type", ""),
                id_field="type_id",
                now=now,
            )

            category_id = self._resolve_catalog(
                collection=self._db["law_doc_category"],
                match_field="doc_category",
                match_value=response.get("document_category", ""),
                id_field="category_id",
                now=now,
            )

            issuing_level_id = self._resolve_catalog(
                collection=self._db["law_issuing_level"],
                match_field="issuing_level_name",
                match_value=response.get("document_level", ""),
                id_field="issuing_level_id",
                now=now,
            )

            effective_status_id = self._resolve_catalog(
                collection=self._db["law_effective_status"],
                match_field="effective_status_name",
                match_value=response.get("effective_status", ""),
                id_field="effective_status_id",
                now=now,
            )

            agency_ids = []
            for agency_name in (response.get("agency") or []):
                if not agency_name:
                    continue
                aid = self._resolve_catalog(
                    collection=self._db["law_agencies"],
                    match_field="agency_name",
                    match_value=agency_name,
                    id_field="agency_id",
                    now=now,
                )
                if aid:
                    agency_ids.append(aid)

            signer_ids  = []
            position_ids = []
            for signer in (response.get("human_sign") or []):
                if not signer.get("human_name"):
                    continue

                sid = self._resolve_signer(signer, now)
                if sid:
                    signer_ids.append(sid)

                if signer.get("human_title"):
                    pid = self._resolve_catalog(
                        collection=self._db["law_positions"],
                        match_field="position_name",
                        match_value=signer["human_title"],
                        id_field="position_id",
                        now=now,
                    )
                    if pid and pid not in position_ids:
                        position_ids.append(pid)

            # --- Build payload ---
            doc_payload = {
                "doc_code":              response.get("doc_code", ""),
                "doc_title":             response.get("document_name", ""),
                "doc_short_description": response.get("document_name", ""),
                "doc_issue_date":        self._parse_date(response.get("issue_date", "")),
                "doc_effective_date":    self._parse_date(response.get("effective_date", "")),
                "doc_expiry_date":       self._parse_date(response.get("end_effective_date", "")),
                "type_id":               type_id or "",
                "category_id":           category_id or "",
                "issuing_level_id":      issuing_level_id or "",
                "effective_status_id":   effective_status_id or "",
                "agency_ids":            agency_ids or [""],
                "signer_ids":            signer_ids or [""],
                "position_ids":          position_ids or [""],
                "industry_sector_ids":   [""],
                "keyword_ids":           [""],
                "tree_ids":              [""],
                "data_source":           "SYSTEM",
                "status_in_system":      "OUT",
                "last_modified_at":      now,
                "last_modified_by":      "admin",
            }

            # --- Upsert ---
            self._db["documents"].update_one(
                {"doc_id": doc_id},
                {
                    "$set": doc_payload,
                    "$setOnInsert": {
                        "doc_id":     doc_id,
                        "created_at": now,
                        "created_by": self.get_handler_name(),
                    },
                },
                upsert=True,
            )
            logger.debug("insert_law_documents_success", action="_insert_metadata_to_law_documents",
                         doc_id=doc_id)

        except Exception as e:
            logger.error("insert_metadata_failed", action="_insert_metadata_to_law_documents", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)
            return False
        return True

    # ------------------------------------------------------------------
    # Catalog helpers
    # ------------------------------------------------------------------

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
        logger.debug("resolve_catalog_entry_created", action="_resolve_catalog",
                     collection=collection.name, value=match_value)
        return new_id

    def _resolve_signer(self, signer: dict, now: str) -> str:
        """
        Lookup signer theo human_name. Tạo mới nếu chưa tồn tại.
        """
        name = signer.get("human_name", "").strip()
        role = signer.get("human_title", "").strip()

        if not name:
            return ""

        existing = self._db["law_signers"].find_one({
            "signer_name": {"$regex": f"^{re.escape(name.strip())}$", "$options": "i"}
        })

        if existing:
            return existing["signer_id"]

        new_id = str(uuid.uuid4())
        self._db["law_signers"].insert_one({
            "signer_id":        new_id,
            "signer_name":      name,
            "signer_role":      role,
            "status":           "ACTIVE",
            "created_at":       now,
            "created_by":       "admin",
            "last_modified_at": now,
            "last_modified_by": "admin",
        })
        logger.debug("resolve_signer_created", action="_resolve_signer", signer_name=name)
        return new_id

    @staticmethod
    def _parse_date(raw: str) -> str:
        """
        Chuyển dd/MM/yyyy hoặc yyyy-MM-dd sang %Y-%m-%d %H:%M:%S.
        Trả về "" nếu không parse được.
        """
        if not raw:
            return ""
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        logger.warning("date_parse_failed", raw=raw)
        return ""

    # ------------------------------------------------------------------
    # Extractor loader
    # ------------------------------------------------------------------

    @staticmethod
    def _load_extractor():
        from core.v03.metadata_extractor import extract_metadata_async
        logger.debug("load_metadata_extractor_success", action="_load_extractor")
        return extract_metadata_async