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
    _send_message_to_kafka_topic(data, kafka_topic=PreprocessTopics.EXTRACT_LAW_AUTHORITY_QUERY_TOPIC)


if __name__ == "__main__":
    doc_id = "5d30fc6b-6847-461d-9f08-4d874d7793eb"
    data = {
        "request_id": "doc_id",
        "doc_id": doc_id,
    }
    send_request(data)
