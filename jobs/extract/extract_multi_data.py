import uuid
from pymongo import MongoClient
from core.common.mongo.client import get_mongo_client
import structlog
import sys
import time

PROJECT_ROOT = "/home/ubuntu/projects/AI/git/users/giangnv/v03/v03-document-management-services"
sys.path.append(PROJECT_ROOT)

from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig  # sửa lại đường dẫn

from services.api.biz.upload.utils import send_requests_to_kafka_extract  # sửa lại đường dẫn


logger = structlog.get_logger(__name__)

# ===================== CONFIG =====================
MONGO_QUERY = {
    "doc_content": {"$exists": True, "$nin": ["", None]},
    "data_source": "tvpl-01042026"
}
BATCH_SIZE = 10
# ==================================================


def _process_batch(batch: list):
    success_count = 0
    error_count = 0

    for doc in batch:
        doc_id = doc.get("doc_id")
        doc_content = doc.get("doc_content", "")
        request_id = str(uuid.uuid4())

        try:
            status = send_requests_to_kafka_extract(
                request_id=request_id,
                doc_id=doc_id,
                doc_content=doc_content
            )
            if status:
                logger.info(action="_process_batch", event="kafka_sent", doc_id=doc_id)
                success_count += 1
            else:
                logger.error(action="_process_batch", event="kafka_failed", doc_id=doc_id, reason="status=False")
                error_count += 1
        except Exception as e:
            logger.error(action="_process_batch", event="kafka_error", doc_id=doc_id, error=str(e))
            error_count += 1

    return {"success_count": success_count, "error_count": error_count}


def main():
    # --- Kết nối MongoDB ---
    mongo_client = get_mongo_client()
    db             = mongo_client[MigrateConfig.MIGRATE_CORE_DB]
    law_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
    logger.info(action="main", event="mongodb_connected")

    # --- Thống kê ---
    total_docs    = law_collection.count_documents(MONGO_QUERY)
    success_count = 0
    error_count   = 0
    batch         = []

    logger.info(action="main", event="kafka_send_started", total_docs=total_docs, batch_size=BATCH_SIZE)

    try:
        cursor = law_collection.find(
            MONGO_QUERY,
            {"doc_id": 1, "doc_content": 1}
        ).batch_size(BATCH_SIZE)
        
        logger.info(action="main", event="cursor_created", batch_size=BATCH_SIZE)
        
        for doc in cursor:
            batch.append(doc)

            if len(batch) >= BATCH_SIZE:
                result = _process_batch(batch)
                success_count += result["success_count"]
                error_count   += result["error_count"]
                logger.info(
                    action="main",
                    event="batch_sent",
                    success_count=success_count,
                    error_count=error_count,
                    remaining=total_docs - success_count - error_count,
                )
                batch = []
                time.sleep(100) 

        # Flush batch cuối
        if batch:
            result = _process_batch(batch)
            success_count += result["success_count"]
            error_count   += result["error_count"]

    finally:
        cursor.close()
        mongo_client.close()
        logger.info(action="main", event="mongodb_disconnected")

    logger.info(
        action="main",
        event="kafka_send_completed",
        total_docs=total_docs,
        success_count=success_count,
        error_count=error_count,
    )


if __name__ == "__main__":
    main()