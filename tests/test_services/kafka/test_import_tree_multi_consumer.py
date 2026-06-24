import json
from kafka import KafkaProducer
import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
print(f"PROJECT_ROOT: {PROJECT_ROOT}")

sys.path.append(PROJECT_ROOT)
from constants import KafkaConfig, ImportTreeConfig

        
producer = KafkaProducer(bootstrap_servers=[KafkaConfig.BOOTSTRAP_SERVERS],
                        api_version=(0,11,5))

def _send_message_to_kafka_topic(data, kafka_topic):
    message_value = json.dumps(data).encode("utf-8")
    producer.send(kafka_topic, value=message_value)        
    producer.flush()
#     producer.close()

def send_result_validate(data):    
    _send_message_to_kafka_topic(data, kafka_topic=ImportTreeConfig.IMPORT_TREE_QUERY_TOPIC)

data = {
    "request_id": "01JBXH5P4MCPBZE93DT3Q7GKF9_TEST",
    "tree_id": "01JBXH5P4MCPBZE93DT3Q7GKF9_TEST",
    "excel_file_path": "/home/ubuntu/projects/AI/git/users/giangnv/v03/v03-document-management-services-dev/core/v03/tree_processor/Bộ Pháp điển 2025 04 28 Short.xlsx",
    "created_by": "ROOT_TEST"
}
    

if __name__ == "__main__":
    send_result_validate(data)




