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


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BATCH_SIZE = 500

MONGO_QUERY = {
    "status_in_system": "IN",
    "doc_content": {"$exists": True, "$nin": ["", None]},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _build_operations(doc_ids: list, now: str) -> list:
    return [
        UpdateOne(
            {"document_id": doc_id},
            {
                "$set": {
                    "elastic_indexing": {
                        "status":        "PROCESSED",
                        "start_at":      now,
                        "finish_at":     now,
                        "duration_time": 0.0,
                    },
                    "last_modified_at": now,
                    "last_modified_by": "ADMIN",
                },
                "$setOnInsert": {
                    "document_id": doc_id,
                    "created_at":  now,
                    "created_by":  "ADMIN",
                },
            },
            upsert=True,
        )
        for doc_id in doc_ids
    ]


def _flush(pipeline_collection, doc_ids: list, now: str):
    if not doc_ids:
        return 0, 0
    try:
        result = pipeline_collection.bulk_write(
            _build_operations(doc_ids, now), ordered=False
        )
        return result.modified_count + result.upserted_count, 0
    except Exception as e:
        logger.error("flush_failed", action="flush", **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)
        return 0, len(doc_ids)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    mongo_client = get_mongo_client()
    db                  = mongo_client[MigrateConfig.MIGRATE_CORE_DB]
    law_collection      = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
    pipeline_collection = db[MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME]
    logger.info("mongodb_connected", action="main")

    total_docs     = law_collection.count_documents(MONGO_QUERY)
    updated_count  = 0
    error_count    = 0
    batch          = []

    logger.info("sync_started", action="main", total_docs=total_docs, batch_size=BATCH_SIZE)

    try:
        cursor = law_collection.find(
            MONGO_QUERY,
            {"_id": 0, "doc_id": 1},   # chỉ lấy doc_id, không kéo toàn bộ document
            no_cursor_timeout=True,
        )

        for doc in cursor:
            doc_id = doc.get("doc_id")
            if doc_id:
                batch.append(doc_id)

            if len(batch) >= BATCH_SIZE:
                now = _now()
                ok, err = _flush(pipeline_collection, batch, now)
                updated_count += ok
                error_count   += err
                logger.info(
                    "batch_synced",
                    action="main",
                    updated_count=updated_count,
                    error_count=error_count,
                    remaining=total_docs - updated_count - error_count,
                )
                batch = []

        # Flush batch cuối
        if batch:
            now = _now()
            ok, err = _flush(pipeline_collection, batch, now)
            updated_count += ok
            error_count   += err

    finally:
        cursor.close()
        mongo_client.close()
        logger.info("mongodb_disconnected", action="main")

    logger.info(
        "sync_completed",
        action="main",
        total_docs=total_docs,
        updated_count=updated_count,
        error_count=error_count,
    )


if __name__ == "__main__":
    main()