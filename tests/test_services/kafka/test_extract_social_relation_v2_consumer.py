"""
Kafka producer test for the QHXH v2 multi-stage handler (ExtractSocialRelationV2Handler).

This script ONLY publishes one Kafka message; it does not call the core
extractor directly and does not write to MongoDB itself. It assumes the Kafka
manager/consumer (services/kafka/manager/extract.py) is already running with
ExtractSocialRelationV2Handler registered for the topic below -- that consumer
is what fetches the doc's articles, runs the multi-stage pipeline, and writes
law_social_relation_group / law_social_relation / law_social_relation_mapping.

Style/pattern reused as-is from test_extract_law_authority_multi_consumer.py
(same producer construction, same _send_message_to_kafka_topic helper, same
"send and exit" behavior -- no response consuming, matching that basis script).
"""

import json
import uuid
from kafka import KafkaProducer
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from constants import KafkaConfig, PreprocessTopics

producer = KafkaProducer(
    bootstrap_servers=[KafkaConfig.BOOTSTRAP_SERVERS],
    api_version=(0, 11, 5),
)


def _send_message_to_kafka_topic(data, kafka_topic):
    message_value = json.dumps(data).encode("utf-8")
    producer.send(kafka_topic, value=message_value)
    producer.flush()


def send_request(data):
    _send_message_to_kafka_topic(data, kafka_topic=PreprocessTopics.EXTRACT_SOCIAL_RELATION_QUERY_TOPIC)


if __name__ == "__main__":
    doc_id = "296884"
    request_id = str(uuid.uuid4())
    data = {
        "request_id": request_id,
        "doc_id": doc_id,
    }
    send_request(data)

    print("=== Kafka message sent ===")
    print(f"topic:          {PreprocessTopics.EXTRACT_SOCIAL_RELATION_QUERY_TOPIC}")
    print(f"doc_id:         {doc_id}")
    print(f"request_id:     {request_id}  (correlation_id)")
    print()
