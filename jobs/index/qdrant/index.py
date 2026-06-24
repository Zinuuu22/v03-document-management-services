import json
import uuid
import time
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from kafka import KafkaProducer
from pymongo import MongoClient
from core.common.mongo.client import get_mongo_client
import structlog

from constants import (
    KafkaConfig, MongoDBConfig, MigrateConfig,
    PreprocessTopics, MongoDBCollectionConfig
)

logger = structlog.get_logger()

# ------------------------------------------------------------------
# Kafka Producer
# ------------------------------------------------------------------
producer = KafkaProducer(
    bootstrap_servers=[KafkaConfig.BOOTSTRAP_SERVERS],
    api_version=(0, 11, 5),
    max_request_size=104857600,
)

TOPICS = [
    PreprocessTopics.TITLE_EMBEDDING_QUERY_TOPIC,
    # PreprocessTopics.CONTENT_EMBEDDING_QUERY_TOPIC,
    # PreprocessTopics.ARTICLE_EMBEDDING_QUERY_TOPIC,
]

# ------------------------------------------------------------------
# Throttle config — chỉnh 2 biến này để kiểm soát tốc độ
# ------------------------------------------------------------------
BATCH_SIZE        = 10    # số document gửi mỗi batch
DELAY_PER_MSG     = 0.1   # giây nghỉ giữa mỗi message trong batch
DELAY_PER_BATCH   = 3.0   # giây nghỉ sau mỗi batch


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _send_to_topic(data: dict, topic: str) -> None:
    message_value = json.dumps(data).encode("utf-8")
    producer.send(topic, value=message_value)
    producer.flush()
    logger.info(action="_send_to_topic",
                event="message_sent",
                topic=topic,
                doc_id=data.get("doc_id"),
                request_id=data.get("request_id"))


def send_embedding_request(doc_id: str) -> dict:
    request_id = str(uuid.uuid4())
    data = {
        "request_id": request_id,
        "doc_id":     doc_id,
    }
    for topic in TOPICS:
        try:
            _send_to_topic(data, topic)
        except Exception as e:
            logger.error(action="send_embedding_request",
                         event="send_failed",
                         topic=topic,
                         doc_id=doc_id,
                         **{"error.code": "KAF", "error.message": str(e)},
                         exc_info=True)
    return data


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

if __name__ == "__main__":
    client = get_mongo_client()
    db         = client[MigrateConfig.MIGRATE_CORE_DB]
    collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]

    query = {"status_in_system": "IN"}
    total = collection.count_documents(query)
    logger.info(action="main",
                event="embedding_job_started",
                total_documents=total,
                topics=TOPICS,
                batch_size=BATCH_SIZE,
                delay_per_msg=DELAY_PER_MSG,
                delay_per_batch=DELAY_PER_BATCH)

    success_count = 0
    failed_docs   = []
    batch_count   = 0

    for i, document in enumerate(collection.find(query, {"doc_id": 1}), start=1):
        doc_id = document.get("doc_id")
        if not doc_id:
            logger.warning(action="main", event="skipped_missing_doc_id", index=i)
            continue

        try:
            send_embedding_request(doc_id)
            success_count += 1
            logger.info(action="main",
                        event="document_sent",
                        index=i,
                        total=total,
                        doc_id=doc_id,
                        progress=f"{i}/{total}")

            # Delay giữa mỗi message
            time.sleep(DELAY_PER_MSG)

            # Delay thêm sau mỗi batch
            if i % BATCH_SIZE == 0:
                batch_count += 1
                logger.info(action="main",
                            event="batch_completed",
                            batch=batch_count,
                            sent=i,
                            total=total,
                            remaining=total - i)
                logger.info(action="main", event="batch_sleeping", seconds=DELAY_PER_BATCH)
                time.sleep(DELAY_PER_BATCH)

        except Exception as e:
            failed_docs.append(doc_id)
            logger.error(action="main",
                         event="document_failed",
                         index=i,
                         doc_id=doc_id,
                         **{"error.code": "SYS", "error.message": str(e)},
                         exc_info=True)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    logger.info(action="main",
                event="embedding_job_completed",
                total=total,
                success=success_count,
                failed=len(failed_docs),
                batches=batch_count)

    if failed_docs:
        logger.warning(action="main",
                       event="failed_documents_summary",
                       count=len(failed_docs),
                       doc_ids=failed_docs)

    producer.close()
    client.close()