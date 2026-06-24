from kafka import KafkaProducer
from constants import KafkaConfig
import json
import structlog
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from logs.logger_conf import setup_logging, KafkaTraceTool

setup_logging()
logger = structlog.get_logger()

producer = KafkaProducer(bootstrap_servers=[KafkaConfig.BOOTSTRAP_SERVERS],
                        api_version=(0,11,5),
                        max_request_size=104857600)

def _send_message_to_kafka_topic(data, kafka_topic, consumer_id):
    logger.info("send_kafka_message_started", action="_send_message_to_kafka_topic", consumer_id=consumer_id, topic=kafka_topic)
    message_value = json.dumps(data).encode('utf-8')
    producer.send(kafka_topic, value=message_value, headers=KafkaTraceTool.get_headers())
    producer.flush()

def send_message(data, kafka_topic, consumer_id="API"):
    _send_message_to_kafka_topic(data, kafka_topic, consumer_id)