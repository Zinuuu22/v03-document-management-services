"""
Extract Regulated Entities Handler
Migrated from services/kafka/v03/extract_regulated_entities/consumer.py
"""

import os
import sys
import time
from typing import Dict, Any
import structlog
import json
import httpx
import asyncio
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import PreprocessTopics, AppConfig, SignalRConfig, MongoDBCollectionConfig, ExtractBatchConfig

logger = structlog.get_logger()


class ExtractRegulatedEntitiesHandler(BaseConsumer):

    TOPIC       = PreprocessTopics.EXTRACT_REGULATED_ENTITIES_QUERY_TOPIC
    GROUP_ID    = PreprocessTopics.EXTRACT_REGULATED_ENTITIES_GROUP
    NUM_WORKERS = AppConfig.EXTRACT_NORM_REGULATED_ENTITY_NUMBER_WORKER

    def __init__(self):
        super().__init__()
        self._extractor = self._load_extractor()
        self._db = self._init_db(extra_collections={
            "articles":                               MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME,
            "article_class":                          MongoDBCollectionConfig.LAW_ARTICLE_CLASS_COLLECTION_NAME,
            "regulated_object":                       MongoDBCollectionConfig.LAW_REGULATED_OBJECT_COLLECTION_NAME,
            "regulated_object_mapping":               MongoDBCollectionConfig.LAW_REGULATED_OBJECT_MAPPING_COLLECTION_NAME,
            "pipeline":                               MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME,
        })

    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------

    def get_handler_name(self) -> str:
        return "extract_regulated_entities"

    def _get_response_topic(self) -> str:
        return PreprocessTopics.EXTRACT_REGULATED_ENTITIES_RESPONSE_TOPIC

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
                        "regulated_entity_extraction": step_info,
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
            "summary":    {"entities_count": 0, "segments_processed": 0},
        }

    # ------------------------------------------------------------------
    # Main message processor
    # ------------------------------------------------------------------

    async def process_message(self, raw_message) -> None:
        # --- Trace context ---
        self._init_trace_context(raw_message)
        bind_contextvars(task="KafkaExtractRegulatedObject")

        # --- Parse message ---
        data       = self._parse_message(raw_message)
        request_id = self._bind_request_context(data)
        doc_id     = data.get("doc_id")
        doc_id_str = str(doc_id) if doc_id is not None else None

        start_at = self._now()
        start    = time.time()
        response = self._make_response(request_id)
        response["doc_id"] = doc_id_str

        try:
            # --- Step 1: Fetch segments ---
            bind_contextvars(step="step_1_fetch_segments")
            segments = self._fetch_segments(doc_id)
            batch_size = ExtractBatchConfig.REGULATED_OBJECT_BATCH_SIZE
            if not segments:
                response["status"] = False
                logger.error("extract_regulated_object_failed", action="process_message",
                             **{"event.status": "failed", "error.code": "NOSEG",
                                "error.message": "No segments found for doc_id"},
                             doc_id=doc_id)
            else:
                # --- Step 2: Extract regulated objects ---
                bind_contextvars(step="step_2_extract_regulated_object")
                classes_map = self._fetch_classes_map(segments)
             
                ext_start = time.time()
                segments_resp, records, total_entities = await self._extract_all(
                    segments, classes_map, batch_size=batch_size
                )
                ext_duration = round(time.time() - ext_start, 3)
                logger.info("extract_regulated_object_success", action="process_message",
                            **{"event.duration": ext_duration, "event.status": "success"},
                            doc_id=doc_id, segments_count=len(segments),
                            total_entities=total_entities)

                response["segments"] = segments_resp
                response["records"]  = records
                response["summary"]  = {
                    "entities_count":    total_entities,
                    "segments_processed": len(segments_resp),
                }

        except Exception as e:
            response["status"] = False
            self._update_pipeline_state(doc_id, "FAILED", start_at)
            logger.error("extract_regulated_object_failed", action="process_message",
                         **{"event.status": "failed",
                            "event.duration": round(time.time() - start, 3),
                            "error.code": "SYS", "error.message": str(e)}, exc_info=True)

        # --- Step 3: Insert regulated entities to MongoDB ---
        bind_contextvars(step="step_3_insert_regulated_object_to_mongodb")
        insert_status = self._insert_regulated_entities(doc_id, request_id, response)
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
                "extract_regulated_entities_status": response["status"],
            },
        )

        total_duration = round(time.time() - start, 3)
        if response["status"]:
            logger.info("process_regulated_object_message_success", action="process_message",
                        **{"event.duration": total_duration, "event.status": "success"},
                        doc_id=doc_id)
        else:
            logger.error("process_regulated_object_message_failed", action="process_message",
                         **{"event.duration": total_duration, "event.status": "failed"},
                         doc_id=doc_id)

    # ------------------------------------------------------------------
    # Insert regulated entities
    # ------------------------------------------------------------------

    def _insert_regulated_entities(
        self,
        doc_id: str,
        request_id: str,
        response: Dict[str, Any],
    ) -> bool:
        """
        Insert regulated objects + mappings vào draft collections,
        Chỉ thực hiện khi extraction thành công (status=True).
        """
        if not doc_id:
            logger.warning("insert_regulated_entities_skipped_null_doc_id")
            return False

        if not response.get("status"):
            logger.warning("insert_regulated_entities_skipped_failed_extraction", doc_id=doc_id)
            return False

        try:
            now = self._now()

            # --- Upsert regulated objects + mappings ---
            formal_records = response.get("records", [])
            if formal_records:
                regulated_object         = self._db["regulated_object"]
                regulated_object_mapping = self._db["regulated_object_mapping"]

                for record in formal_records:
                    regulated_object_id   = record.get("regulated_entity_id")
                    regulated_object_name = record.get("regulated_entity_name")

                    if not regulated_object_id or not regulated_object_name:
                        logger.warning("skipping_record_missing_fields", record=record)
                        continue

                    regulated_object.update_one(
                        {"regulated_object_id": regulated_object_id},
                        {"$setOnInsert": {
                            "regulated_object_id":        regulated_object_id,
                            "regulated_object_name":      regulated_object_name,
                            "description":                record.get("description", ""),
                            "regulated_object_name_norm": record.get("regulated_entity_name_norm", ""),
                            "status":                     "ACTIVE",
                            "created_at":                 now,
                            "created_by":                 "admin",
                            "last_modified_at":           now,
                            "last_modified_by":           "admin",
                        }},
                        upsert=True,
                    )

                    regulated_object_mapping.insert_one({
                        "doc_id":               request_id,
                        "regulated_object_id":  regulated_object_id,
                        "relation_type":        record.get("relation_type", "PRIMARY"),
                        "created_at":           now,
                        "created_by":           "admin",
                        "last_modified_at":     now,
                        "last_modified_by":     "admin",
                    })

                logger.debug("insert_regulated_objects_summary", action="_insert_regulated_entities",
                             count=len(formal_records), doc_id=doc_id)

            logger.debug("upload_documents_update_complete", action="_insert_regulated_entities",
                         doc_id=doc_id)

        except Exception as e:
            logger.error("insert_regulated_entities_failed", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)
            return False
        return True

    # ------------------------------------------------------------------
    # Segment helpers
    # ------------------------------------------------------------------

    def _fetch_segments(self, doc_id) -> list:
        candidates = self._build_id_candidates(doc_id)
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
            logger.error("fetch_segments_failed", doc_id=doc_id,
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            return []

    def _fetch_classes_map(self, segments: list) -> Dict:
        article_ids = [s.get("article_id") for s in segments if isinstance(s, dict)]
        classes_map = {}
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

    async def _extract_all(self, segments: list, classes_map: Dict, batch_size: int = 10):
        from services.kafka.handlers.extractor.utils.regulated_object_utils import compose_formal_records
        from core.v03.regulated_entities.extractor import generate_regulated_entities_async

        segments_resp  = []
        records        = []
        total_entities = 0

        custom_timeout = httpx.Timeout(600.0, connect=10.0)
        limits = httpx.Limits(max_keepalive_connections=batch_size, max_connections=batch_size * 2)
        semaphore = asyncio.Semaphore(batch_size)
        
        async with httpx.AsyncClient(limits=limits, timeout=custom_timeout) as client:
            
            async def wrap_process(seg):
                article_id            = seg.get("article_id")
                article_title         = (seg.get("article_title") or "").strip()
                article_content       = (seg.get("article_content") or "").strip()
                seg_content           = f"{article_title}\n{article_content}".strip()
                article_class_values  = classes_map.get(article_id, [])

                try:
                    raw_ents = await generate_regulated_entities_async(seg_content, client, semaphore)
                except Exception as e:
                    logger.error("extractor_failed", article_id=article_id,
                                 **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
                    raw_ents = []
                return article_id, article_class_values, raw_ents

            results = []
            for i in range(0, len(segments), batch_size):
                chunk = segments[i : i + batch_size]
                logger.info("processing_batch", 
                            start_index=i, 
                            end_index=i + len(chunk), 
                            total=len(segments))    
                tasks = [wrap_process(seg) for seg in chunk]
                chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
                results.extend(chunk_results)

            for res in results:
                if isinstance(res, Exception):
                    continue
                article_id, article_class_values, raw_ents = res

                entity_list = self._clean_entities(raw_ents)

                if entity_list:
                    try:
                        recs = compose_formal_records(
                            article_id=article_id,
                            article_class=article_class_values,
                            entities=entity_list,
                            created_by="root",
                        )
                        if isinstance(recs, list):
                            records.extend(recs)
                    except Exception as e:
                        logger.error("compose_formal_records_failed",
                                     **{"error.code": "COMPOSE", "error.message": str(e)}, exc_info=True)

                    segments_resp.append({
                        "article_id":         article_id,
                        "article_class":      article_class_values,
                        "regulated_entities": entity_list,
                    })
                    total_entities += len(entity_list)

        return segments_resp, records, total_entities

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_entities(raw_ents) -> list:
        if not raw_ents:
            return []
        # nếu là string thì parse json
        if isinstance(raw_ents, str):
            try:
                raw_ents = json.loads(raw_ents)
            except json.JSONDecodeError:
                return []
        # nếu là dict thì lấy list bên trong
        if isinstance(raw_ents, dict):
            raw_ents = raw_ents.get("doi_tuong_dieu_chinh", [])
        if not isinstance(raw_ents, list):
            return []
        result = []
        for it in raw_ents:
            if not isinstance(it, str):
                continue
            cleaned = it.strip().strip('"').strip()
            if cleaned:
                result.append({"name": cleaned})
        return result

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
        from core.v03.regulated_entities import generate_regulated_entities
        logger.debug("load_regulated_entities_extractor_success", action="_load_extractor")
        return generate_regulated_entities