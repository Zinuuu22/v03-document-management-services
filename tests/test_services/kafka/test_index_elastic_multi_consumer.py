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
    _send_message_to_kafka_topic(data, kafka_topic=PreprocessTopics.INDEX_ELASTIC_QUERY_TOPIC)


if __name__ == "__main__":
    from pymongo import MongoClient

    client = get_mongo_client()

    db = client[MigrateConfig.MIGRATE_CORE_DB]
    
    data = {
        "request_id":"TEST_3bdf5894-ac2c-4c4c-bc07-46b896f2be0f", 
        "doc_id":"634027"
    }
    send_request(data)
