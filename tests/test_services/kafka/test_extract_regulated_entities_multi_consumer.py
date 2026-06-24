## TEST_DOC_ID=517486 python law-document-sync-core-service/tests/test_services/kafka/test_extract_regulated_entities_multi_consumer.py
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


def send_result_validate(data):    
    _send_message_to_kafka_topic(data, kafka_topic=PreprocessTopics.EXTRACT_REGULATED_ENTITIES_QUERY_TOPIC)


if __name__ == "__main__":    
    doc_id = "127280"
    data = {
        "request_id": doc_id,
        "doc_id": doc_id,
        "top_k": 10
    }
    send_result_validate(data)