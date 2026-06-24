import structlog
import os
import sys
from kafka import KafkaProducer
import json
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)
from constants import KafkaConfig, TreeClassifierConfig
from logs.logger_conf import setup_logging, KafkaTraceTool

setup_logging()
logger = structlog.get_logger()


producer = KafkaProducer(
            bootstrap_servers=[KafkaConfig.BOOTSTRAP_SERVERS],
            value_serializer=lambda x: json.dumps(x).encode('utf-8'))
        

def send_message_to_kafka(data):
    """
    Gửi message đến Kafka
    """
    try:
        producer.send(TreeClassifierConfig.TREE_CLASSIFIER_QUERY_TOPIC, value=data, headers=KafkaTraceTool.get_headers())
        producer.flush()
        return True
    except Exception as e:
        logger.error("send_message_to_kafka_failed", action="send_message_to_kafka", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
        return False