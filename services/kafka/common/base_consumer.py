"""
Base Consumer Abstract Class
Provides common functionality for all Kafka consumers
"""

import json
import time
import uuid
import threading
import inspect
import asyncio
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

import requests
from core.common.elastic import search_document_content
from kafka import KafkaConsumer, KafkaProducer
import structlog
from logs.logger_conf import generate_trace_id, generate_request_id
from structlog.contextvars import bind_contextvars, clear_contextvars

logger = structlog.get_logger()


class BaseConsumer(ABC):
    """Abstract base class for all Kafka consumers"""

    TOPIC: str = None
    GROUP_ID: str = None
    NUM_WORKERS: int = 1

    _producer: KafkaProducer = None

    def __init__(self):
        self.consumer: Optional[KafkaConsumer] = None
        self.running = False
        self.worker_threads: Dict[int, threading.Thread] = {}

    # ------------------------------------------------------------------
    # Abstract interface - subclasses must implement
    # ------------------------------------------------------------------

    @abstractmethod
    def process_message(self, raw_message) -> None:
        """Entry point called by worker pool for each raw Kafka message."""
        pass

    @abstractmethod
    def get_handler_name(self) -> str:
        """Return a human-readable name for this handler."""
        pass

    @abstractmethod
    def _make_response(self, request_id: str) -> Dict[str, Any]:
        """Return the default response skeleton for this handler."""
        pass

    @abstractmethod
    def _get_response_topic(self) -> str:
        """Return the Kafka topic to publish responses to."""
        pass

    # ------------------------------------------------------------------
    # Trace / message parsing helpers
    # ------------------------------------------------------------------

    def _extract_trace_id(self, raw_message) -> str:
        """
        Extract trace.id from raw Kafka message headers.
        Falls back to a new UUID and logs a warning when missing.
        """
        raw_headers = dict(raw_message.headers) if raw_message.headers else {}
        trace_id_bytes = raw_headers.get("trace.id")

        if trace_id_bytes:
            return trace_id_bytes.decode("utf-8")

        trace_id = generate_trace_id()
        logger.warning(
            "consume_trace_id_missing",
            action="_extract_trace_id",
            **{"trace.id": trace_id},
            handler=self.get_handler_name(),
        )
        return trace_id

    def _init_trace_context(self, raw_message) -> str:
        """
        Clear contextvars, extract trace.id, bind it, and return it.
        Call this at the very start of process_message().
        """
        clear_contextvars()
        trace_id = self._extract_trace_id(raw_message)
        bind_contextvars(**{"trace.id": trace_id})
        return trace_id

    def _parse_message(self, raw_message) -> Dict[str, Any]:
        """Decode and JSON-parse a raw Kafka ConsumerRecord value."""
        return json.loads(raw_message.value.decode("utf-8"))

    def _bind_request_context(self, data: Dict[str, Any]) -> str:
        """
        Extract request_id from parsed data (or generate one),
        bind it to structlog contextvars, and return it.
        """
        request_id = data.get("request_id")
        if not request_id:
            request_id = generate_request_id()
            logger.warning(
                "consume_request_id_missing",
                action="_bind_request_context",
                **{"request.id": request_id},
                handler=self.get_handler_name(),
            )
        bind_contextvars(**{"request.id": request_id})
        return request_id

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _init_db(self, extra_collections: Optional[Dict[str, str]] = None) -> Dict:
        """
        Initialize MongoDB and return a dict of collection handles.

        Base collections provided:
            - "documents"   → LAW_DOCUMENT_COLLECTION_NAME
            - "biz_uploads" → BIZ_UPLOAD_DOCUMENTS_COLLECTION_NAME

        Pass `extra_collections` to add handler-specific collections:
            extra_collections={"articles": MongoDBCollectionConfig.LAW_ARTICLE_DRAFT_COLLECTION_NAME}
        """
        from core.common.mongo.client import get_mongo_client
        from constants import MigrateConfig, MongoDBCollectionConfig

        client = get_mongo_client()
        db = client[MigrateConfig.MIGRATE_CORE_DB]

        collections = {
            "documents":   db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME],
        }

        if extra_collections:
            for alias, collection_name in extra_collections.items():
                collections[alias] = db[collection_name]

        return collections

    def _fetch_raw_content(self, doc_id: str) -> str:
        """
        Fetch doc_content for doc_id, checking biz_uploads before documents.
        Returns empty string when not found.
        """
        content = search_document_content(doc_id)

        if len(content):
            logger.debug("fetch_document_content_success", action="_fetch_raw_content", doc_id=doc_id)
            return content

        logger.warning("fetch_document_content_not_found", action="_fetch_raw_content", doc_id=doc_id)
        return ""

    # ------------------------------------------------------------------
    # Kafka producer
    # ------------------------------------------------------------------

    @classmethod
    def _get_producer(cls) -> KafkaProducer:
        """Lazy singleton Kafka producer shared across all instances of a subclass."""
        if cls._producer is None:
            from constants import KafkaConfig

            cls._producer = KafkaProducer(
                bootstrap_servers=[KafkaConfig.BOOTSTRAP_SERVERS],
                api_version=(0, 11, 5),
                max_request_size=104857600,
            )
        return cls._producer

    def _send_response(self, data: Dict[str, Any]) -> None:
        """Serialize `data` as JSON and publish it to the handler's response topic."""
        from logs.logger_conf import KafkaTraceTool

        try:
            producer = self._get_producer()
            topic    = self._get_response_topic()
            payload  = json.dumps(data).encode("utf-8")

            producer.send(topic, value=payload, headers=KafkaTraceTool.get_headers())
            producer.flush()

            logger.info("send_kafka_response_success", action="_send_response", topic=topic, size_bytes=len(payload))
        except Exception as e:
            logger.error("send_kafka_response_failed", action="_send_response", **{"error.code": "KAF", "error.message": str(e)}, exc_info=True)

    def _now(self) -> str:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    def _duration(self, start: str, finish: str) -> float:
        fmt = "%Y-%m-%d %H:%M:%S"
        try:
            return (datetime.strptime(finish, fmt) - datetime.strptime(start, fmt)).total_seconds()
        except Exception:
            return 0.0
    
    def _clean_text(self, text: str) -> str:
        return text.strip().replace("\r\n", "\n").replace("\n\n", "\n")

    # ------------------------------------------------------------------
    # SignalR
    # ------------------------------------------------------------------
    def push_to_signalr_api(
        self,
        api_url: str = None,
        topic: str = None,
        message: dict = None,
        broadcast_count: int = 5,
        token: str = None,
    ) -> bool:
        """
        Push data to SignalR hub via HTTP API synchronously.

        Args:
            api_url: API endpoint URL (e.g. 'http://192.168.1.200:5097/broadcast').
                     Defaults to SignalRConfig.API_URL.
            topic: SignalR hub method or topic (e.g. 'DOCUMENT_SEGMENT_RECORD_SEND').
                   Defaults to SignalRConfig.UPLOAD_TOPIC.
            message: Message data to broadcast.
            broadcast_count: Number of broadcasts or group ID (default: 5).
            token: Bearer token for authentication. Defaults to None.

        Returns:
            True if the request was successful, False otherwise.
        """
        from constants import SignalRConfig

        api_url = api_url or SignalRConfig.API_URL
        topic   = topic   or SignalRConfig.UPLOAD_TOPIC

        try:
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            payload = {
                "topic":           topic,
                "message":         json.dumps(message),
                "broadcast_count": broadcast_count,
            }

            logger.debug("push_signalr_notification_sending", action="push_to_signalr_api",
                         api_url=api_url, topic=topic, payload_len=len(json.dumps(payload)))

            response = requests.post(api_url, headers=headers, json=payload, timeout=10)

            if response.status_code == 200:
                logger.debug("push_signalr_notification_success", action="push_to_signalr_api",
                             api_url=api_url, topic=topic)
                return True

            logger.error("push_signalr_notification_failed", action="push_to_signalr_api",
                         **{"error.code": "EXT", "error.message": "HTTP error pushing to SignalR"},
                         api_url=api_url, topic=topic, status_code=response.status_code)
            return False

        except requests.exceptions.RequestException as e:
            logger.error("push_signalr_notification_failed", action="push_to_signalr_api",
                         **{"error.code": "EXT", "error.message": str(e)},
                         api_url=api_url, topic=topic, exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Worker / lifecycle
    # ------------------------------------------------------------------

    def create_consumer(self) -> KafkaConsumer:
        return KafkaConsumer(self.TOPIC, **self._build_consumer_config())

    def _build_consumer_config(self) -> Dict[str, Any]:
        """Override to customise KafkaConsumer kwargs."""
        return {}

    def start_consumer(self, worker_id: int):
        try:
            self.consumer = self.create_consumer()
            logger.info(
                "consume_worker_started",
                action="start_consumer",
                topic=self.TOPIC,
                group_id=self.GROUP_ID,
                worker_id=worker_id,
                handler=self.get_handler_name(),
            )

            for raw_message in self.consumer:
                if not self.running:
                    break

                try:
                    logger.info(
                        "consume_kafka_message_received",
                        action="start_consumer",
                        topic=raw_message.topic,
                        partition=raw_message.partition,
                        offset=raw_message.offset,
                        worker_id=worker_id,
                        handler=self.get_handler_name(),
                    )

                    start_time = time.time()
                    result = self.process_message(raw_message)
                    if inspect.iscoroutine(result):
                        asyncio.run(result)
                    duration = round(time.time() - start_time, 3)
                    logger.info(
                        "consume_kafka_message_processed",
                        action="start_consumer",
                        **{"event.duration": duration, "event.status": "success"},
                        worker_id=worker_id,
                        handler=self.get_handler_name(),
                    )

                    self.consumer.commit()

                except Exception as e:
                    duration = round(time.time() - start_time, 3) if 'start_time' in dir() else 0.0
                    logger.error(
                        "consume_kafka_message_failed",
                        action="start_consumer",
                        **{"event.duration": duration, "event.status": "failed", "error.code": "SYS", "error.message": str(e)},
                        topic=raw_message.topic,
                        partition=raw_message.partition,
                        offset=raw_message.offset,
                        worker_id=worker_id,
                        handler=self.get_handler_name(),
                        exc_info=True,
                    )
                    continue

        except Exception as e:
            logger.error(
                "consume_worker_failed",
                action="start_consumer",
                **{"error.code": "SYS", "error.message": str(e)},
                worker_id=worker_id,
                handler=self.get_handler_name(),
                exc_info=True,
            )
        finally:
            if self.consumer:
                self.consumer.close()
            logger.info(
                "consume_worker_stopped",
                action="start_consumer",
                worker_id=worker_id,
                handler=self.get_handler_name(),
            )

    def start(self, num_workers: Optional[int] = None):
        self.running = True
        workers = num_workers or self.NUM_WORKERS

        for worker_id in range(workers):
            thread = threading.Thread(
                target=self.start_consumer,
                args=(worker_id,),
                name=f"{self.get_handler_name()}-worker-{worker_id}",
            )
            self.worker_threads[worker_id] = thread
            thread.start()

        logger.info(
            "consume_workers_started",
            action="start",
            handler=self.get_handler_name(),
            topic=self.TOPIC,
            num_workers=workers,
        )

    def stop(self):
        logger.info(
            "consume_workers_stopping",
            action="stop",
            handler=self.get_handler_name(),
            topic=self.TOPIC,
        )
        self.running = False

        for worker_id, thread in self.worker_threads.items():
            if thread.is_alive():
                thread.join(timeout=5)
                if thread.is_alive():
                    logger.warning(
                        "consume_worker_stop_timeout",
                        action="stop",
                        worker_id=worker_id,
                        handler=self.get_handler_name(),
                    )

        if self.consumer:
            self.consumer.close()

        logger.info("consume_workers_stopped", action="stop", handler=self.get_handler_name())

    # ------------------------------------------------------------------
    # Misc helpers (kept for backward compatibility)
    # ------------------------------------------------------------------

    def validate_message(self, message_data: Dict[str, Any]) -> bool:
        for field in ("request_id",):
            if field not in message_data:
                logger.error(
                    "consume_message_validation_failed",
                    action="validate_message",
                    **{"error.code": "400-VAL", "error.message": f"Missing required field: {field}"},
                    field=field,
                    handler=self.get_handler_name(),
                )
                return False
        return True

    def create_error_response(self, error_message: str, request_id: str) -> Dict[str, Any]:
        return {
            "status":     "error",
            "message":    error_message,
            "request_id": request_id,
            "timestamp":  time.time(),
        }

    def create_success_response(self, data: Any, request_id: str) -> Dict[str, Any]:
        return {
            "status":     "success",
            "data":       data,
            "request_id": request_id,
            "timestamp":  time.time(),
        }