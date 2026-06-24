import json
from kafka import KafkaProducer
import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

sys.path.append(PROJECT_ROOT)
from constants import KafkaConfig, MongoDBConfig, AppConfig, PreprocessTopics

        
producer = KafkaProducer(bootstrap_servers=[KafkaConfig.BOOTSTRAP_SERVERS],
                        api_version=(0,11,5))

def _send_message_to_kafka_topic(data, kafka_topic):
    message_value = json.dumps(data).encode("utf-8")
    producer.send(kafka_topic, value=message_value)        
    producer.flush()
#     producer.close()

def send_result_validate(data):    
    _send_message_to_kafka_topic(data, kafka_topic=PreprocessTopics.EXTRACT_KEYWORD_QUERY_TOPIC)

if __name__ == "__main__":
    data = {
        "request_id": "test-request-id",
        "doc_id": "376719"
    }
    
    send_result_validate(data)
    