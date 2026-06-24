"""
Extract Social Relation Handler
Migrated from services/kafka/v03/extract_social_relation/consumer.py
"""

import os
import sys
import time
import asyncio
import httpx
from typing import Dict, Any
import structlog
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import PreprocessTopics, AppConfig, SignalRConfig, MongoDBCollectionConfig, ExtractBatchConfig

logger = structlog.get_logger()


class ExtractSocialRelationHandler(BaseConsumer):

    TOPIC       = PreprocessTopics.EXTRACT_SOCIAL_RELATION_QUERY_TOPIC
    GROUP_ID    = PreprocessTopics.EXTRACT_SOCIAL_RELATION_GROUP
    NUM_WORKERS = AppConfig.EXTRACT_NORM_SOCIAL_RELATION_NUMBER_WORKER

    def __init__(self):
        super().__init__()
        self._generate_social_relations, self._compose_formal_records = self._load_extractor()
        self._db = self._init_db(extra_collections={
            "articles":                       MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME,
            "article_class":                  MongoDBCollectionConfig.LAW_ARTICLE_CLASS_COLLECTION_NAME,
            "social_relation":                MongoDBCollectionConfig.LAW_SOCIAL_RELATION_COLLECTION_NAME,
            "social_relation_mapping":        MongoDBCollectionConfig.LAW_SOCIAL_RELATION_MAPPING_COLLECTION_NAME,
            "pipeline":                       MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME,
        })

    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------

    def get_handler_name(self) -> str:
        return "extract_social_relation"

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


        # Các field pipeline cần kiểm tra
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
        bind_contextvars(task="KafkaExtractSocialRelation")

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
                logger.error("extract_social_relation_failed", action="process_message", **{"event.status": "failed", "error.code": "NOSEG", "error.message": "No segments found for doc_id"}, doc_id=doc_id)
            else:
                # --- Step 2: Extract social relations ---
                bind_contextvars(step="step_2_extract_social_relation")
                ext_start = time.time()
                segments_resp, summary = await self._extract_all(segments, doc_id_str)
                ext_duration = round(time.time() - ext_start, 3)
                logger.info("extract_social_relation_success", action="process_message", **{"event.duration": ext_duration, "event.status": "success"}, doc_id=doc_id_str, **summary)

                response["segments"] = segments_resp
                response["summary"]  = summary
                response["status"]   = True

        except Exception as e:
            response["status"] = False
            self._update_pipeline_state(doc_id, "FAILED", start_at)
            logger.error("extract_social_relation_failed", action="process_message", **{"event.status": "failed", "event.duration": round(time.time() - start, 3), "error.code": "SYS", "error.message": str(e)}, exc_info=True)

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

        # --- Step 3: Insert social relations to draft collections ---
        bind_contextvars(step="step_3_insert_social_relation_to_mongodb")
        if not response["status"]:
            self._update_pipeline_state(doc_id, "FAILED", start_at)
        else:
            self._update_pipeline_state(doc_id, "PROCESSED", start_at)

        total_duration = round(time.time() - start, 3)
        if response["status"]:
            logger.info("process_social_relation_message_success",
                        action="process_message",
                        **{"event.duration": total_duration, "event.status": "success"},
                        doc_id=doc_id_str)
        else:
            logger.error("process_social_relation_message_failed",
                         action="process_message",
                         **{"event.duration": total_duration, "event.status": "failed"},
                         doc_id=doc_id_str)

    # ------------------------------------------------------------------
    # Insert social relations
    # ------------------------------------------------------------------

    def _insert_social_relations(
        self,
        doc_id: str,
        response: Dict[str, Any],
    ) -> bool:
        """
        Upsert social relations + mappings vào draft collections,
        và update biz_documents với segments + summary.
        Chỉ thực hiện khi extraction thành công (status=True).
        """
        if not doc_id:
            logger.warning("insert_social_relations_skipped", action="_insert_social_relations",
                           **{"error.message": "doc_id is None"})
            return False

        if not response.get("status"):
            logger.warning("insert_social_relations_skipped", action="_insert_social_relations",
                           doc_id=doc_id, **{"error.message": "extraction failed, skipping insert"})
            return False

        try:
            now = self._now()

            # --- Log summary ---
            summary = response.get("summary", {})
            logger.debug("insert_social_relations_summary", action="_insert_social_relations",
                        doc_id=doc_id,
                        relations=summary.get("relations_count", 0),
                        segments=summary.get("segments_processed", 0),
                        upserted=summary.get("relations_upserted", "N/A"),
                        mappings=summary.get("mappings_inserted", "N/A"))

            # --- Upsert to documents ---
            self._db["documents"].update_one(
                {"doc_id": doc_id},
                {
                    "$set": {
                        "social_relations_segments": response.get("segments", []),
                        "social_relations_summary":  summary,
                        "last_modified_at":          now,
                        "last_modified_by":          "admin",
                    },
                    "$setOnInsert": {
                        "doc_id":  doc_id, 
                        "created_at": now,
                        "created_by": "admin",
                    },
                },
                upsert=True,
            )
            logger.debug("insert_social_relations_document_updated", action="_insert_social_relations", doc_id=doc_id)

        except Exception as e:
            logger.error("insert_social_relations_failed", action="_insert_social_relations", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)
            return False
        return True

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
    # Extraction logic
    # ------------------------------------------------------------------

    async def _extract_all(self, segments: list, doc_id_str: str):
        article_ids = [seg.get("article_id") for seg in segments if isinstance(seg, dict)]
        classes_map = self._fetch_classes_map(article_ids)

        segments_resp:        list = []
        all_relation_records: list = []
        all_mapping_records:  list = []
        total_relations             = 0
        batch_size = ExtractBatchConfig.SOCIAL_RELATION_BATCH_SIZE

        custom_timeout = httpx.Timeout(600.0, connect=10.0)
        semaphore = asyncio.Semaphore(batch_size)
        limits = httpx.Limits(max_keepalive_connections=batch_size, max_connections=batch_size * 2)
        async with httpx.AsyncClient(limits=limits, timeout=custom_timeout) as client:
            async def process_segment(seg):
                article_id           = seg.get("article_id")
                article_title        = (seg.get("article_title") or "").strip()
                article_content      = (seg.get("article_content") or "").strip()
                seg_content          = f"{article_title}\n{article_content}".strip()
                article_class_values = classes_map.get(article_id, [])

                try:
                    rels = await self._generate_social_relations(
                        article_content=seg_content,
                        article_class=article_class_values,
                        client=client,
                        semaphore=semaphore,
                    )
                except Exception as e:
                    logger.error("generate_social_relations_failed",
                                 **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
                    rels = {"social_relations": []}

                social_list = self._clean_social_list(
                    rels.get("social_relations", []) if isinstance(rels, dict) else []
                )

                recs_data = {"relations": [], "mappings": []}
                if social_list:
                    try:
                        recs = self._compose_formal_records(
                            article_id=article_id,
                            article_class=article_class_values,
                            relations={"social_relations": social_list},
                            created_by="root",
                            doc_id=doc_id_str,
                        )
                        if isinstance(recs, dict):
                            recs_data["relations"].extend(recs.get("relations", []))
                            recs_data["mappings"].extend(recs.get("mappings", []))
                    except Exception as e:
                        logger.error("compose_formal_records_failed",
                                     **{"error.code": "COMPOSE", "error.message": str(e)}, exc_info=True)

                return {
                    "resp": {
                        "article_id":       article_id,
                        "article_class":    article_class_values,
                        "social_relations": social_list,
                    },
                    "relations": recs_data["relations"],
                    "mappings": recs_data["mappings"],
                    "count": len(social_list)
                }

            tasks = [process_segment(seg) for seg in segments]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results:
                if isinstance(res, Exception):
                    logger.error("segment_extraction_failed", error=str(res), exc_info=res)
                    continue
                segments_resp.append(res["resp"])
                all_relation_records.extend(res["relations"])
                all_mapping_records.extend(res["mappings"])
                total_relations += res["count"]

        relations_upserted            = self._upsert_relations(all_relation_records)
        mappings_inserted, mappings_skipped = self._insert_mappings(all_mapping_records)

        summary = {
            "relations_count":               total_relations,
            "segments_processed":            len(segments_resp),
            "relations_upserted":            relations_upserted,
            "mappings_inserted":             mappings_inserted,
            "mappings_skipped_no_doc_id":    mappings_skipped,
        }
        return segments_resp, summary

    @staticmethod
    def _clean_social_list(items: list) -> list:
        social_list = []
        for it in items:
            if not isinstance(it, dict):
                continue
            txt  = it.get("relation_text")
            name = it.get("social_relation")
            if not isinstance(txt, str):
                continue
            cleaned_txt  = txt.strip().strip('"').strip()
            cleaned_name = name.strip().strip('"').strip() if isinstance(name, str) else None
            if cleaned_txt:
                obj = {"relation_text": cleaned_txt}
                if cleaned_name:
                    obj["social_relation"] = cleaned_name
                social_list.append(obj)
        return social_list

    def _upsert_relations(self, records: list) -> int:
        upserted = 0
        for rec in records:
            try:
                self._db["social_relation"].update_one(
                    {"social_relation_id": rec["social_relation_id"]},
                    {"$setOnInsert": rec},
                    upsert=True,
                )
                upserted += 1
            except Exception as e:
                logger.error("upsert_relation_failed", action="_upsert_relations",
                             **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
        logger.debug("upsert_relations_complete", action="_upsert_relations", upserted=upserted)
        return upserted

    def _insert_mappings(self, records: list):
        inserted = 0
        skipped  = 0
        for rec in records:
            if not rec.get("doc_id"):
                logger.warning("insert_mapping_skipped_missing_doc_id", action="_insert_mappings",
                               article_id=rec.get("article_id"),
                               social_relation_id=rec.get("social_relation_id"))
                skipped += 1
                continue
            try:
                self._db["social_relation_mapping"].update_one(
                    {"doc_id": rec["doc_id"], "article_id": rec["article_id"], "social_relation_id": rec["social_relation_id"]},
                    {"$setOnInsert": rec},
                    upsert=True,
                )
                inserted += 1
            except Exception as e:
                logger.error("insert_mapping_failed", action="_insert_mappings",
                             **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
        logger.debug("insert_mappings_complete", action="_insert_mappings", inserted=inserted, skipped=skipped)
        return inserted, skipped

    # ------------------------------------------------------------------
    # Extractor loader
    # ------------------------------------------------------------------

    @staticmethod
    def _load_extractor():
        from core.v03.social_extractor import generate_social_relations_async, compose_formal_records
        logger.debug("load_social_relation_extractor_success", action="_load_extractor")
        return generate_social_relations_async, compose_formal_records