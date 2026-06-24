"""
Classify Article Handler
Classifies law articles and writes results to law_article_class collection.
"""

import os
import sys
import time
import asyncio
import httpx
from typing import Dict, Any, List
import structlog
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import PreprocessTopics, AppConfig, SignalRConfig, MongoDBCollectionConfig, MigrateConfig

logger = structlog.get_logger()


class ClassifyArticleHandler(BaseConsumer):

    TOPIC       = PreprocessTopics.CLASSIFICATION_ARTICLE_QUERY_TOPIC
    GROUP_ID    = PreprocessTopics.CLASSIFICATION_ARTICLE_GROUP
    NUM_WORKERS = AppConfig.EXTRACT_ARTICLE_CLASS_NUMBER_WORKER

    def __init__(self):
        super().__init__()
        self._classify_segment_async = self._load_classifier()
        self._db = self._init_db(extra_collections={
            "articles":      MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME,
            "article_class": MongoDBCollectionConfig.LAW_ARTICLE_CLASS_COLLECTION_NAME,
            "pipeline":      MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME,
        })

    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------

    def get_handler_name(self) -> str:
        return "classify_article"
    
    # THÊM HÀM NÀY VÀO ĐÂY:
    def _get_response_topic(self) -> str:
        """
        Trả về tên Kafka Topic mà Handler này sẽ gửi message kết quả (response) tới.
        Bạn cần thay PreprocessTopics.YOUR_RESPONSE_TOPIC bằng biến cấu hình thực tế của bạn.
        """
        return "CLASSIFICATION_ARTICLE_RESPONSE_TOPIC"
    
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

        try:
            self._db["pipeline"].update_one(
                {"doc_id": doc_id},
                {
                    "$set": {
                        "article_classification": step_info,
                        "last_modified_at":       finish_at,
                        "last_modified_by":       "admin",
                    },
                    "$setOnInsert": {
                        "doc_id":     doc_id,
                        "created_at": finish_at,
                        "created_by": "admin",
                    },
                },
                upsert=True,
            )
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
            "summary": {
                "articles_total":      0,
                "articles_classified": 0,
                "articles_skipped":    0,
                "articles_failed":     0,
            },
        }

    # ------------------------------------------------------------------
    # Main message processor
    # ------------------------------------------------------------------

    async def process_message(self, raw_message) -> None:
        # --- Trace context ---
        self._init_trace_context(raw_message)
        bind_contextvars(task="KafkaClassifyArticle")

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
            # --- Step 1: Fetch articles ---
            bind_contextvars(step="step_1_fetch_articles")
            articles = self._fetch_articles(doc_id)

            if not articles:
                response["status"] = False
                logger.error(
                    "classify_article_failed", action="process_message",
                    **{"event.status": "failed", "error.code": "NOART", "error.message": "No articles found for doc_id"},
                    doc_id=doc_id_str,
                )
            else:
                # --- Step 2: Classify articles ---
                bind_contextvars(step="step_2_classify_articles")
                cls_start = time.time()
                summary   = await self._classify_all(articles, doc_id_str)
                cls_duration = round(time.time() - cls_start, 3)

                logger.info(
                    "classify_article_success", action="process_message",
                    **{"event.duration": cls_duration, "event.status": "success"},
                    doc_id=doc_id_str, **summary,
                )
                response["summary"] = summary
                response["status"]  = True

        except Exception as e:
            response["status"] = False
            self._update_pipeline_state(doc_id_str, "FAILED", start_at)
            logger.error(
                "classify_article_failed", action="process_message",
                **{"event.status": "failed", "event.duration": round(time.time() - start, 3),
                   "error.code": "SYS", "error.message": str(e)},
                exc_info=True,
            )

        # --- Step 3: Send Kafka response ---
        bind_contextvars(step="step_3_send_kafka_response")
        self._send_response(response)

        # --- SignalR notification ---
        logger.debug("send_signalr_notification_started", action="process_message", doc_id=doc_id_str)
        self.push_to_signalr_api(
            api_url=SignalRConfig.API_URL,
            topic=SignalRConfig.UPLOAD_TOPIC,
            message={
                "request_id":                  request_id,
                "status":                      response["status"],
                "classify_article_status":     response["status"],
            },
        )

        # --- Step 4: Update pipeline state ---
        bind_contextvars(step="step_4_update_pipeline_state")
        pipeline_status = "PROCESSED" if response["status"] else "FAILED"
        self._update_pipeline_state(doc_id_str, pipeline_status, start_at)

        total_duration = round(time.time() - start, 3)
        if response["status"]:
            logger.info(
                "process_classify_article_message_success", action="process_message",
                **{"event.duration": total_duration, "event.status": "success"},
                doc_id=doc_id_str,
            )
        else:
            logger.error(
                "process_classify_article_message_failed", action="process_message",
                **{"event.duration": total_duration, "event.status": "failed"},
                doc_id=doc_id_str,
            )

    # ------------------------------------------------------------------
    # Fetch helpers
    # ------------------------------------------------------------------

    def _fetch_articles(self, doc_id) -> List[Dict]:
        """Lấy danh sách articles theo doc_id từ MongoDB."""
        logger.debug("fetch_articles_started", action="_fetch_articles", doc_id=doc_id)
        try:
            cursor   = self._db["articles"].find(
                {"doc_id": doc_id},
                {"_id": 0, "article_id": 1, "article_title": 1, "article_content": 1},
            )
            articles = list(cursor)
            logger.debug("fetch_articles_success", action="_fetch_articles", count=len(articles), doc_id=doc_id)
            return articles
        except Exception as e:
            logger.error("fetch_articles_failed", action="_fetch_articles", doc_id=doc_id,
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            return []

    def _fetch_existing_classes(self, article_ids: List[str]) -> set:
        """Batch check: 1 query lấy tập article_id đã có class, tránh N+1 query."""
        existing = set()
        if not article_ids:
            return existing
        try:
            cursor = self._db["article_class"].find(
                {
                    "article_id": {"$in": article_ids},
                    "class":      {"$exists": True, "$ne": []},
                },
                {"article_id": 1},
            )
            for doc in cursor:
                existing.add(doc["article_id"])
        except Exception as e:
            logger.error("fetch_existing_classes_failed", action="_fetch_existing_classes",
                         **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
        return existing

    # ------------------------------------------------------------------
    # Classification logic
    # ------------------------------------------------------------------

    async def _classify_all(self, articles: List[Dict], doc_id_str: str) -> Dict[str, int]:
        """
        Classify tất cả articles song song theo batch.
        - Batch check DB trước (1 query) để skip article đã có class.
        - asyncio.gather + semaphore kiểm soát số LLM request đồng thời.
        - httpx.AsyncClient dùng chung toàn batch (connection pooling).
        """
        total = len(articles)
        now   = self._now()

        # --- Batch check: 1 query thay vì N query ---
        all_ids            = [a.get("article_id") for a in articles if a.get("article_id")]
        existing_class_ids = self._fetch_existing_classes(all_ids)
        logger.debug("fetch_existing_classes_done", action="_classify_all",
                     total=total, already_classified=len(existing_class_ids), doc_id=doc_id_str)

        batch_size = AppConfig.EXTRACT_ARTICLE_CLASS_NUMBER_WORKER
        semaphore  = asyncio.Semaphore(batch_size)
        timeout    = httpx.Timeout(120.0, connect=10.0)
        limits     = httpx.Limits(max_keepalive_connections=batch_size, max_connections=batch_size * 2)

        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:

            async def classify_one(article: Dict) -> str:
                """Trả về: 'classified' | 'skipped' | 'failed'"""
                article_id      = article.get("article_id")
                article_title   = (article.get("article_title")   or "").strip()
                article_content = (article.get("article_content") or "").strip()

                if not article_id:
                    logger.warning("classify_article_missing_id", action="_classify_all")
                    return "skipped"

                # Skip nếu đã có class (dùng kết quả batch query)
                if article_id in existing_class_ids:
                    logger.debug("classify_article_already_exists", action="_classify_all", article_id=article_id)
                    return "skipped"

                content = f"{article_title}\n{article_content}".strip()
                if not content:
                    logger.warning("classify_article_empty_content", action="_classify_all", article_id=article_id)
                    return "skipped"

                # --- Gọi LLM async (semaphore giới hạn đồng thời) ---
                try:
                    classes_map   = await self._classify_segment_async(
                        segment=content,
                        client=client,
                        semaphore=semaphore,
                    )
                    article_class = [k for k, v in classes_map.items() if v]
                except Exception as e:
                    logger.error(
                        "classify_article_llm_failed", action="_classify_all",
                        **{"error.code": "LLM", "error.message": str(e)},
                        article_id=article_id, exc_info=True,
                    )
                    return "failed"

                # --- Upsert kết quả vào article_class collection ---
                try:
                    self._db["article_class"].update_one(
                        {"article_id": article_id},
                        {
                            "$set": {
                                "class":            article_class,
                                "last_modified_at": now,
                                "last_modified_by": "CLASSIFY_HANDLER",
                            },
                            "$setOnInsert": {
                                "article_id":      article_id,
                                "article_title":   article_title,
                                "article_content": article_content,
                                "doc_id":          doc_id_str,
                                "created_at":      now,
                                "created_by":      "CLASSIFY_HANDLER",
                                "version":         MigrateConfig.MIGRATE_CLASSIFY_ARTICLE_LEVEL_OLLAMA,
                            },
                        },
                        upsert=True,
                    )
                    logger.info("classify_article_upserted", action="_classify_all",
                                article_id=article_id, article_class=article_class)
                    return "classified"
                except Exception as e:
                    logger.error(
                        "classify_article_upsert_failed", action="_classify_all",
                        **{"error.code": "MONGO", "error.message": str(e)},
                        article_id=article_id, exc_info=True,
                    )
                    return "failed"

            # --- Chạy toàn bộ articles song song ---
            tasks   = [classify_one(article) for article in articles]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        classified = skipped = failed = 0
        for res in results:
            if isinstance(res, Exception):
                logger.error("classify_article_task_exception", action="_classify_all",
                             **{"error.code": "SYS", "error.message": str(res)}, exc_info=res)
                failed += 1
            elif res == "classified":
                classified += 1
            elif res == "skipped":
                skipped += 1
            else:
                failed += 1

        logger.info("classify_all_done", action="_classify_all", doc_id=doc_id_str,
                    total=total, classified=classified, skipped=skipped, failed=failed)
        return {
            "articles_total":      total,
            "articles_classified": classified,
            "articles_skipped":    skipped,
            "articles_failed":     failed,
        }

    # ------------------------------------------------------------------
    # Classifier loader
    # ------------------------------------------------------------------

    @staticmethod
    def _load_classifier():
        from core.v03.segments_classifier.extractor import classify_segment_async
        logger.debug("load_classifier_success", action="_load_classifier")
        return classify_segment_async