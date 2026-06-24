from core.common.mongo.client import get_mongo_client
import json
from kafka import KafkaProducer
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from constants import KafkaConfig, MongoDBConfig, MigrateConfig, PreprocessTopics, MongoDBCollectionConfig


producer = KafkaProducer(bootstrap_servers=[KafkaConfig.BOOTSTRAP_SERVERS],
                        api_version=(0,11,5))


def _send_message_to_kafka_topic(data, kafka_topic):
    message_value = json.dumps(data).encode("utf-8")
    producer.send(kafka_topic, value=message_value)
    producer.flush()


def send_request(data):
    _send_message_to_kafka_topic(data, kafka_topic=PreprocessTopics.EXTRACT_KEYWORD_QUERY_TOPIC)


if __name__ == "__main__":
    from pymongo import MongoClient

    client = get_mongo_client()

    db = client[MigrateConfig.MIGRATE_CORE_DB]
    biz_upload_articles_collection = db[MongoDBCollectionConfig.BIZ_UPLOAD_ARTICLES_COLLECTION_NAME]

    target_doc_id = os.getenv('TEST_DOC_ID', '517486')
    candidates = [target_doc_id]
    try:
        candidates.append(int(target_doc_id))
    except Exception:
        pass

    sample = biz_upload_articles_collection.find_one(
        {'status': 'ACTIVE', 'doc_id': {'$in': candidates}},
        {'doc_id': 1}
    )
    if not sample or not sample.get('doc_id'):
        raise RuntimeError(f"No ACTIVE articles found for doc_id {target_doc_id} in {MongoDBCollectionConfig.BIZ_UPLOAD_ARTICLES_COLLECTION_NAME}. Seed data before running this test.")

    doc_id_str = str(sample['doc_id'])
    data = {
        "request_id": doc_id_str,
        "doc_id": doc_id_str,
        "top_k": 10
    }

    send_request(data)
