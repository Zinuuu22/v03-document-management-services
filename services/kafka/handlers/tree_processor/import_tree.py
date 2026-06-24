"""
Import Tree Handler
Migrated from services/kafka/v03/import_tree/consumer.py
"""

import os
import sys
import time
from typing import Dict, Any

import structlog
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import (
    KafkaConfig,
    ImportTreeConfig,
    AppConfig,
    MongoDBCollectionConfig,
    SignalRConfig,
)
# from services.kafka.utils import push_to_signalr_api
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

_SERVICE_NAME = os.getenv("SERVICE_NAME", "")
if not _SERVICE_NAME:
    _SERVICE_NAME = "v03-sync-services"
    logger.warning(
        "import_tree_handler_init_fallback",
        action="init",
        fallback=_SERVICE_NAME,
    )


class ImportTreeHandler(BaseConsumer):

    TOPIC = ImportTreeConfig.IMPORT_TREE_QUERY_TOPIC
    GROUP_ID = ImportTreeConfig.IMPORT_TREE_GROUP
    NUM_WORKERS = AppConfig.IMPORT_TREE_NUMBER_WORKER

    def __init__(self):
        super().__init__()
        self._law_tree_manager = self._load_law_tree_manager()
        self._db = self._init_db()

    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------

    def get_handler_name(self) -> str:
        return "import_tree"

    def _get_response_topic(self) -> str:
        return ImportTreeConfig.IMPORT_TREE_RESPONSE_TOPIC

    @staticmethod
    def _make_response(request_id: str) -> Dict[str, Any]:
        return {
            "request_id": request_id,
            "status": True,
            "message": None,
            "failed_imports": None,
        }

    def _build_consumer_config(self) -> Dict[str, Any]:
        """Override: import-tree needs custom fetch/poll settings."""
        return {
            "api_version": (0, 11, 5),
            "group_id": self.GROUP_ID,
            "bootstrap_servers": [KafkaConfig.BOOTSTRAP_SERVERS],
            "max_partition_fetch_bytes": 104857600,
            "auto_offset_reset": "latest",
            "max_poll_interval_ms": 9000000,
            "enable_auto_commit": False,
        }

    def process_message(self, raw_message) -> None:
        # --- Trace context ---
        self._init_trace_context(raw_message)
        bind_contextvars(task="KafkaImportTree")

        # --- Parse message ---
        data = self._parse_message(raw_message)
        request_id = self._bind_request_context(data)

        tree_id = data.get("tree_id")
        excel_file_path = data.get("excel_file_path")
        created_by = data.get("created_by")

        logger.debug("import_tree_message_received", action="process_message", tree_id=tree_id)

        start = time.time()
        response = self._make_response(request_id)

        try:
            status, message, failed_imports, doc_ops = (
                self._law_tree_manager.import_tree_from_excel(
                    tree_id=tree_id,
                    excel_file_path=excel_file_path,
                    created_by=created_by,
                )
            )

            # --- SignalR notification ---
            logger.debug("sending_signalr_notification", action="process_message")
            self.push_to_signalr_api(
                api_url=SignalRConfig.API_URL,
                topic=SignalRConfig.IMPORT_TREE_TOPIC,
                message={
                    "request_id": request_id,
                    "status": status,
                    "tree_id": tree_id,
                    "failed_imports": len(failed_imports),
                },
            )

            # --- Bulk write to MongoDB ---
            if status and doc_ops:
                logger.debug("bulk_write_to_collection_started", action="process_message", count=len(doc_ops))
                self._bulk_write(doc_ops)

            logger.debug(
                "import_tree_from_excel_result",
                action="process_message",
                status=status,
                message=message,
                failed_imports_count=len(failed_imports),
            )

            response["status"] = status
            response["message"] = message
            response["failed_imports"] = failed_imports

        except Exception as e:
            response["status"] = False
            response["message"] = str(e)
            logger.error("import_tree_failed", action="process_message",
                         **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)

        finally:
            # --- Cleanup uploaded Excel file ---
            if excel_file_path and os.path.exists(excel_file_path):
                os.remove(excel_file_path)
                logger.debug("deleted_excel_file", action="process_message", path=excel_file_path)

        self._send_response(response)
        duration = round(time.time() - start, 3)
        status_str = "success" if response["status"] else "failed"
        logger.info("import_tree_message_processed",
                    action="process_message",
                    **{"event.status": status_str, "event.duration": duration})

    # ------------------------------------------------------------------
    # MongoDB bulk write
    # ------------------------------------------------------------------

    def _bulk_write(self, doc_ops) -> None:
        collection = self._db["documents"]
        batch_size = self._law_tree_manager.BATCH_SIZE

        for i in range(0, len(doc_ops), batch_size):
            batch = doc_ops[i: i + batch_size]
            start = time.time()
            collection.bulk_write(batch, ordered=False)
            logger.debug(
                "bulk_write_batch_done",
                action="_bulk_write",
                collection=collection.name,
                **{"event.duration": round(time.time() - start, 3)}
            )

    # ------------------------------------------------------------------
    # Loader
    # ------------------------------------------------------------------

    @staticmethod
    def _load_law_tree_manager():
        from core.v03.tree_processor.processor import LawTreeManager
        logger.debug("loaded_law_tree_manager", action="_load_law_tree_manager")
        return LawTreeManager()