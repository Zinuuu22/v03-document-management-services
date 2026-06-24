import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from pymongo import MongoClient, UpdateOne
from core.common.mongo.client import get_mongo_client

from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.common.elastic.index import ElasticIndexer


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BATCH_SIZE = 500

MONGO_QUERY = {
    # "status_in_system": "IN",
    "doc_content": {"$exists": True, "$nin": ["", None]},
    "data_source" : "tvpl-01042026"
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _duration(start: str, finish: str) -> float:
    """Tính duration_time (giây) giữa start_at và finish_at."""
    fmt = "%Y-%m-%d %H:%M:%S"
    try:
        return (datetime.strptime(finish, fmt) - datetime.strptime(start, fmt)).total_seconds()
    except Exception:
        return 0.0


def _build_pipeline_updates(doc_ids: list, status: str, start_at: str, finish_at: str) -> list:
    """
    Tạo danh sách UpdateOne để bulk write vào pipeline_document_state.

    Args:
        doc_ids: Danh sách document_id cần update.
        status: "PROCESSED" hoặc "FAILED".
        start_at: Thời điểm bắt đầu index batch.
        finish_at: Thời điểm hoàn thành index batch.

    Returns:
        Danh sách UpdateOne operations.
    """
    step_info = {
        "status": status,
        "start_at": start_at,
        "finish_at": finish_at,
        "duration_time": _duration(start_at, finish_at),
    }

    return [
        UpdateOne(
            {"document_id": doc_id},
            {
                "$set": {
                    "elastic_indexing": step_info,
                    "last_modified_at": finish_at,
                    "last_modified_by": "index_elastic_script",
                }
            },
            upsert=True,
        )
        for doc_id in doc_ids
    ]


def _flush_pipeline_state(pipeline_collection, doc_ids: list, status: str, start_at: str):
    """Bulk write trạng thái elastic_indexing vào pipeline_document_state."""
    if not doc_ids:
        return
    finish_at  = _now()
    operations = _build_pipeline_updates(doc_ids, status, start_at, finish_at)
    try:
        result = pipeline_collection.bulk_write(operations, ordered=False)
        logger.info(
            action="_flush_pipeline_state",
            event="pipeline_state_updated",
            matched=result.matched_count,
            modified=result.modified_count,
            status=status,
        )
    except Exception as e:
        logger.error(
            action="_flush_pipeline_state",
            event="pipeline_state_update_failed",
            **{"error.code": "MONGO", "error.message": str(e)},
            exc_info=True,
        )


def _process_batch(batch: list, indexer: ElasticIndexer, pipeline_collection):
    """
    Index một batch lên Elasticsearch và update pipeline_document_state tương ứng.
    Document index thành công → elastic_indexing.status = PROCESSED.
    Document index thất bại   → elastic_indexing.status = FAILED.
    """
    start_at = _now()
    result   = indexer.index_documents(batch)

    all_doc_ids = [doc.get("doc_id") for doc in batch if doc.get("doc_id")]

    if result["error_count"] == 0:
        # Toàn bộ batch thành công
        _flush_pipeline_state(pipeline_collection, all_doc_ids, "PROCESSED", start_at)

    elif result["success_count"] == 0:
        # Toàn bộ batch thất bại
        _flush_pipeline_state(pipeline_collection, all_doc_ids, "FAILED", start_at)

    else:
        # Một phần thành công — index lại từng document để xác định chính xác
        success_ids = []
        failed_ids  = []
        for doc in batch:
            doc_id = doc.get("doc_id")
            if not doc_id:
                continue
            ok = indexer.index_document(doc)
            (success_ids if ok else failed_ids).append(doc_id)

        _flush_pipeline_state(pipeline_collection, success_ids, "PROCESSED", start_at)
        _flush_pipeline_state(pipeline_collection, failed_ids,  "FAILED",    start_at)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # --- Kết nối MongoDB ---
    mongo_client = get_mongo_client()
    db                  = mongo_client[MigrateConfig.MIGRATE_CORE_DB]
    law_collection      = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
    pipeline_collection = db[MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME]
    logger.info(action="main", event="mongodb_connected")

    # --- Khởi tạo indexer ---
    indexer = ElasticIndexer()

    # --- Thống kê ---
    total_docs    = law_collection.count_documents(MONGO_QUERY)
    success_count = 0
    error_count   = 0
    batch         = []

    logger.info(action="main", event="migration_started", total_docs=total_docs, batch_size=BATCH_SIZE)

    try:
        cursor = law_collection.find(MONGO_QUERY, no_cursor_timeout=True)

        for doc in cursor:
            batch.append(doc)

            if len(batch) >= BATCH_SIZE:
                result = indexer.index_documents(batch)
                _process_batch(batch, indexer, pipeline_collection)
                success_count += result["success_count"]
                error_count   += result["error_count"]
                logger.info(
                    action="main",
                    event="batch_indexed",
                    success_count=success_count,
                    error_count=error_count,
                    remaining=total_docs - success_count - error_count,
                )
                batch = []

        # Flush batch cuối
        if batch:
            result = indexer.index_documents(batch)
            _process_batch(batch, indexer, pipeline_collection)
            success_count += result["success_count"]
            error_count   += result["error_count"]

    finally:
        cursor.close()
        mongo_client.close()
        logger.info(action="main", event="mongodb_disconnected")

    logger.info(
        action="main",
        event="migration_completed",
        total_docs=total_docs,
        success_count=success_count,
        error_count=error_count,
    )


if __name__ == "__main__":
    main()