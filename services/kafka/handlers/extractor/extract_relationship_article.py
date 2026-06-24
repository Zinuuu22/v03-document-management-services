"""
Extract Relationship Article Handler
Migrated from services/kafka/v03/extract_relationship_article/consumer.py
"""

import os
import sys
import time
import asyncio
import httpx
from typing import Dict, Any
import structlog
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import PreprocessTopics, AppConfig, SignalRConfig, MongoDBCollectionConfig, ExtractBatchConfig

logger = structlog.get_logger()


class ExtractRelationshipArticleHandler(BaseConsumer):

    TOPIC       = PreprocessTopics.EXTRACT_ARTICLE_RELATIONSHIP_QUERY_TOPIC
    GROUP_ID    = PreprocessTopics.EXTRACT_ARTICLE_RELATIONSHIP_GROUP
    NUM_WORKERS = AppConfig.EXTRACT_NORM_RELATIONSHIP_ARTICLE_NUMBER_WORKER

    def __init__(self):
        super().__init__()
        self._process_article, self._post_process_response = self._load_extractor()
        self._metadata_extractor = self._load_metadata_extractor()
        self._db = self._init_db(extra_collections={
            "documents":                   MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME,
            "articles":                    MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME,
            "article_relationships":       MongoDBCollectionConfig.LAW_REFERENCE_ARTICLE_COLLECTION_NAME,
            "article_relationships_draft": MongoDBCollectionConfig.LAW_REFERENCE_ARTICLE_DRAFT_COLLECTION_NAME,
            "pipeline":                    MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME,
        })

    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------

    def get_handler_name(self) -> str:
        return "extract_relationship_article"

    def _get_response_topic(self) -> str:
        return PreprocessTopics.EXTRACT_ARTICLE_RELATIONSHIP_RESPONSE_TOPIC

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
                        "article_relationship_extraction": step_info,
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
            "request_id":    request_id,
            "status":        "success",
            "relationships": [],
            "doc_id":        None,
        }

    # ------------------------------------------------------------------
    # Main message processor
    # ------------------------------------------------------------------

    async def process_message(self, raw_message) -> None:
        # --- Trace context ---
        self._init_trace_context(raw_message)
        bind_contextvars(task="KafkaExtractRelationshipArticle")

        # --- Parse message ---
        data       = self._parse_message(raw_message)
        request_id = self._bind_request_context(data)
        doc_id     = data.get("doc_id")

        start_at = self._now()
        start    = time.time()
        response = self._make_response(request_id)
        response["doc_id"] = doc_id

        try:
            # --- Step 1: Fetch document ---
            bind_contextvars(step="step_1_fetch_document")
            document = self._fetch_document(doc_id)
            batch_size = ExtractBatchConfig.RELATIONSHIP_ARTICLE_BATCH_SIZE
            if not document:
                response["status"] = "error"
                logger.error("extract_relationship_article_failed", action="process_message",
                             **{"event.status": "failed", "error.code": "DB",
                                "error.message": "Document not found for doc_id"},
                             doc_id=doc_id)
            else:
                # --- Step 2: Fetch articles ---
                bind_contextvars(step="step_2_fetch_articles")
                articles = self._fetch_articles(doc_id)
                if not articles:
                    response["status"] = "error"
                    logger.warning("extract_relationship_article_no_articles", action="process_message",
                                   doc_id=doc_id)
                else:
                    # --- Step 3: Extract relationships ---
                    bind_contextvars(step="step_3_extract_relationship_article")
                    doc_title = document.get("doc_title", "")
                    doc_content = document.get("doc_content", "")
                    metadata  = await self._extract_metadata(doc_content, batch_size=batch_size)
                    doc_title = metadata.get("document_name", doc_title)

                    ext_start = time.time()
                    
                    relationships = await self._extract_all(articles, doc_title, doc_id, batch_size=batch_size)

                    response["relationships"] = relationships
                    ext_duration = round(time.time() - ext_start, 3)
                    logger.info("extract_relationship_article_success", action="process_message",
                                **{"event.duration": ext_duration, "event.status": "success"},
                                doc_id=doc_id, relationships_count=len(relationships))

        except Exception as e:
            response["status"] = "error"
            self._update_pipeline_state(doc_id, "FAILED", start_at)
            logger.error("extract_relationship_article_failed", action="process_message",
                         **{"event.status": "failed",
                            "event.duration": round(time.time() - start, 3),
                            "error.code": "SYS", "error.message": str(e)}, exc_info=True)

        # --- Step 4: Insert article relationships to MongoDB ---
        bind_contextvars(step="step_4_insert_article_relationships_to_mongodb")
        insert_status = self._insert_article_relationships(doc_id, response)
        if not insert_status:
            self._update_pipeline_state(doc_id, "FAILED", start_at)
        else:
            self._update_pipeline_state(doc_id, "PROCESSED", start_at)

        # --- Step 5: Send Response to Kafka ---
        bind_contextvars(step="step_5_send_kafka_response")
        self._send_response(response)

        # --- SignalR notification ---
        self.push_to_signalr_api(
            api_url=SignalRConfig.API_URL,
            topic=SignalRConfig.UPLOAD_TOPIC,
            message={
                "request_id": request_id,
                "status":     response["status"] == "success",
                "extract_article_relationship_status": response["status"],
            },
        )

        total_duration = round(time.time() - start, 3)
        ok = (response["status"] == "success")
        if ok:
            logger.info("process_relationship_article_message_success", action="process_message",
                        **{"event.duration": total_duration, "event.status": "success"},
                        doc_id=doc_id)
        else:
            logger.error("process_relationship_article_message_failed", action="process_message",
                         **{"event.duration": total_duration, "event.status": "failed"},
                         doc_id=doc_id)

    # ------------------------------------------------------------------
    # Insert article relationships
    # ------------------------------------------------------------------

    def _insert_article_relationships(
        self,
        doc_id: str,
        response: Dict[str, Any],
    ) -> bool:
        """
        Convert relationships sang records rồi insert vào law_article_relationships.
        Chỉ thực hiện khi extraction thành công (status="success").
        """
        if not doc_id:
            logger.warning("insert_article_relationships_skipped_null_doc_id")
            return False

        if response.get("status") != "success":
            logger.warning("insert_article_relationships_skipped_failed_extraction", doc_id=doc_id)
            return False

        try:
            from core.v03.relationship_extractor.utils import convert_relationships_to_records

            now     = self._now()
            raw     = response.get("relationships", [])
            records, drafts = convert_relationships_to_records(raw, collect_drafts=True)

            # References whose target document is not (yet) in the DB → draft collection.
            # Stored with raw display fields so the FE can render them without a doc lookup.
            if drafts:
                try:
                    self._db["article_relationships_draft"].insert_many(drafts, ordered=False)
                    logger.debug("insert_article_relationship_drafts_success",
                                 action="_insert_article_relationships", doc_id=doc_id, inserted=len(drafts))
                except Exception as e:
                    logger.error("insert_article_relationship_drafts_failed", doc_id=doc_id,
                                 **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)

            if not records:
                logger.info("article_relationships_empty", doc_id=doc_id)
                return True

            payloads = [
                {
                    "relationship_id":   rec.get("relationship_id", ""),
                    "source_doc_id":     rec.get("source_doc_id", ""),
                    "source_article_id": rec.get("source_article_id", ""),
                    "source_clause":     rec.get("source_clause", ""),
                    "source_point":      rec.get("source_point", ""),
                    "target_doc_id":     rec.get("target_doc_id", ""),
                    "target_article_id": rec.get("target_article_id", ""),
                    "target_article":    rec.get("target_article", ""),
                    "target_clause":     rec.get("target_clause", ""),
                    "target_point":      rec.get("target_point", ""),
                    "relationship_type": rec.get("relationship_type", ""),
                    "created_at":        now,
                    "created_by":        "admin",
                    "last_modified_at":  now,
                    "last_modified_by":  "admin",
                }
                for rec in records
            ]

            self._db["article_relationships"].insert_many(payloads, ordered=False)
            logger.debug("insert_article_relationships_success", action="_insert_article_relationships",
                         doc_id=doc_id, inserted=len(payloads))

        except Exception as e:
            logger.error("insert_article_relationships_failed", doc_id=doc_id,
                         **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)
            return False
        return True

    # ------------------------------------------------------------------
    # Fetch helpers
    # ------------------------------------------------------------------

    def _fetch_document(self, doc_id) -> dict | None:
        """Look up document in law_documents."""
        document = self._db["documents"].find_one({"doc_id": doc_id})
        if document:
            return document
        logger.error("document_not_found", doc_id=doc_id, **{"error.code": "DB"})
        return None

    def _fetch_articles(self, doc_id) -> list:
        try:
            articles = list(self._db["articles"].find({"doc_id": doc_id}))
            logger.debug("articles_fetched", count=len(articles), doc_id=doc_id)
            return articles
        except Exception as e:
            logger.error("fetch_articles_failed", doc_id=doc_id, action="_fetch_articles",
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Extraction logic
    # ------------------------------------------------------------------

    async def _extract_all(self, articles: list, doc_title: str, doc_id: str, batch_size: int) -> list:
        custom_timeout = httpx.Timeout(600.0, connect=10.0)
        limits = httpx.Limits(max_keepalive_connections=batch_size, max_connections=batch_size * 2)
        semaphore = asyncio.Semaphore(batch_size)
        async with httpx.AsyncClient(limits=limits, timeout=custom_timeout) as client:
            relationships = []
            
            async def wrap_process(article):
                article_id = article["article_id"]
                start_time = time.time()
                try:
                    relationships_rs    = await self._process_article(article, doc_title, client, semaphore)
                    relationships_rs_pp = self._post_process_response(
                        relationships_result=relationships_rs,
                        article_id=article_id,
                        doc_id=doc_id,
                    )
                except Exception as e:
                    logger.error("process_article_failed", article_id=article_id, action="_extract_all",
                                **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
                    relationships_rs_pp = {
                        "doc_id":          doc_id,
                            "article_id":      article_id,
                            "status":          "error",
                        "error_message":   str(e),
                        "relationships":   [],
                        "processing_time": time.time() - start_time,
                    }
                return relationships_rs_pp

            results = []
            for i in range(0, len(articles), batch_size):
                chunk = articles[i : i + batch_size]
                logger.info("processing_batch", 
                            start_index=i, 
                            end_index=i + len(chunk), 
                            total=len(articles))    
                tasks = [wrap_process(article) for article in chunk]
                chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
                results.extend(chunk_results)
            
            logger.info("processing_all_completed", action="_extract_all", total=len(results))
            for res in results:
                if res is not None and not isinstance(res, Exception):
                    relationships.append(res)

        return relationships

    # ------------------------------------------------------------------
    # Extractor loader
    # ------------------------------------------------------------------

    @staticmethod
    def _load_extractor():
        from core.v03.relationship_extractor.articles import process_article_async
        from services.kafka.handlers.extractor.utils.relationship_article_utils import post_process_response
        logger.debug("load_relationship_article_extractor_success", action="_load_extractor")
        return process_article_async, post_process_response

    async def _extract_metadata(self, content: str, batch_size: int = 10) -> Dict[str, Any]:
        return await self._metadata_extractor(
            content=content,
            metadata_names=["document_code", "document_type", "document_name"],
            batch_size=batch_size,
        )

    @staticmethod
    def _load_metadata_extractor():
        from core.v03.metadata_extractor import extract_metadata_async
        logger.debug("load_metadata_extractor_success", action="_load_metadata_extractor")
        return extract_metadata_async
