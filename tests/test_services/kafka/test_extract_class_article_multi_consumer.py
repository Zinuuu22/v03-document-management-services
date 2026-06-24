import json
from kafka import KafkaProducer
import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

sys.path.append(PROJECT_ROOT)
from constants import KafkaConfig, MongoDBConfig, AppConfig, PreprocessTopics, MongoDBCollectionConfig

        
producer = KafkaProducer(bootstrap_servers=[KafkaConfig.BOOTSTRAP_SERVERS],
                        api_version=(0,11,5))

def _send_message_to_kafka_topic(data, kafka_topic):
    message_value = json.dumps(data).encode("utf-8")
    producer.send(kafka_topic, value=message_value)        
    producer.flush()
#     producer.close()

def send_result_validate(data):    
    _send_message_to_kafka_topic(data, kafka_topic=PreprocessTopics.CLASSIFICATION_ARTICLE_QUERY_TOPIC)

if __name__ == "__main__":    
    # doc_id = "f215c5fa-c48a-4a4a-867b-30e535b71e13"
    # data = {
    #     "request_id": doc_id,
    #     "doc_id": doc_id,
    #     "doc_code": "",
    #     "top_k":10
    # }


    data = {
        "request_id":"3bdf5894-ac2c-4c4c-bc07-46b896f2be0f", 
        "doc_id": "468069"
        }
    send_result_validate(data)
