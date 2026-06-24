import os
import sys
import argparse
from datetime import datetime
from pymongo import MongoClient, UpdateOne
from core.common.mongo.client import get_mongo_client

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()
from constants import MongoDBConfig
from core.common.elastic.index import ElasticIndexer

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BATCH_SIZE = 50

MONGO_QUERY = {
    "doc_content": {"$exists": True, "$nin": ["", None]},
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
            "pipeline_state_updated",
            matched=result.matched_count,
            modified=result.modified_count,
            status=status,
        )
    except Exception as e:
        logger.error(
            "pipeline_state_update_failed",
            **{"error.code": "MONGO", "error.message": str(e)},
            exc_info=True,
        )


def _process_batch(batch: list, indexer: ElasticIndexer, pipeline_collection) -> dict:
    """
    Index một batch lên Elasticsearch và update pipeline_document_state tương ứng.
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

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Index law documents to Elasticsearch.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-index all documents, including already-processed ones. Without this flag, only unfinished documents are indexed.",
    )
    args = parser.parse_args()

    # --- Kết nối MongoDB ---
    mongo_client = get_mongo_client()
    db                  = mongo_client['hunghv']
    law_collection      = db['law_documents_v1']
    pipeline_collection = db['pipeline_document_state_v1']
    logger.info("mongodb_connected")

    # --- Khởi tạo indexer ---
    indexer = ElasticIndexer()

    # --- Query construction ---
    query = dict(MONGO_QUERY)
    
    if not args.overwrite:
        logger.info("checking_processed_documents")
        # Fetch IDs that are already successfully processed
        processed_docs = pipeline_collection.find(
            {"elastic_indexing.status": "PROCESSED"},
            {"document_id": 1}
        )
        processed_ids = [d["document_id"] for d in processed_docs]
        
        if processed_ids:
            query["doc_id"] = {"$nin": processed_ids}
            logger.info("incremental_mode_active", skip_count=len(processed_ids))
        else:
            logger.info("no_processed_documents_found")
    else:
        logger.info("overwrite_mode_active")

    # --- Thống kê ---
    total_docs    = law_collection.count_documents(query)
    success_count = 0
    error_count   = 0
    batch         = []

    logger.info("migration_started", total_docs=total_docs, batch_size=BATCH_SIZE)

    try:
        cursor = law_collection.find(query, no_cursor_timeout=True)

        for doc in cursor:
            batch.append(doc)

            if len(batch) >= BATCH_SIZE:
                result = _process_batch(batch, indexer, pipeline_collection)
                success_count += result["success_count"]
                error_count   += result["error_count"]
                logger.info(
                    "batch_indexed",
                    success_count=success_count,
                    error_count=error_count,
                    remaining=total_docs - success_count - error_count,
                )
                batch = []

        # Flush batch cuối
        if batch:
            result = _process_batch(batch, indexer, pipeline_collection)
            success_count += result["success_count"]
            error_count   += result["error_count"]

    finally:
        cursor.close()
        mongo_client.close()
        logger.info("mongodb_disconnected")

    logger.info(
        "migration_completed",
        total_docs=total_docs,
        success_count=success_count,
        error_count=error_count,
    )


if __name__ == "__main__":
    main()