from core.common.mongo.client import get_mongo_client
from datetime import datetime
from typing import Any, Dict, List, Union
from dateutil.parser import parse as parse_date
import re
import json
import sys
import os
import structlog

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import KafkaConfig, MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from kafka import KafkaProducer

from .reader import read_file_docx
from .minio import upload_to_minio
from .response import make_response
from .migrate import preprocess_document_from_storage_code, preprocess_document_from_stream
from logs.logger_conf import setup_logging, KafkaTraceTool

setup_logging()
logger = structlog.get_logger()


def send_kafka_message(topic: str, message: dict):
    try:
        producer = KafkaProducer(bootstrap_servers=[KafkaConfig.BOOTSTRAP_SERVERS],
                        api_version=(0,11,5),
                        max_request_size=104857600)

        logger.debug("send_kafka_message_started", action="send_kafka_message", topic=topic)
        producer.send(topic, value=json.dumps(message).encode('utf-8'), headers=KafkaTraceTool.get_headers())
        producer.flush()
    except Exception as e:
        raise Exception(f"Failed to send message to Kafka: {e}")
    


def convert_to_custom_date_format(data: Any) -> Any:
    """
    Recursively convert all datetime fields in a document to 'HH:MM:SS DD/MM/YY' format.
    
    Args:
        data: Input data (dict, list, str, datetime, or other types).
    
    Returns:
        Converted data with all datetime fields in 'HH:MM:SS DD/MM/YY' format.
    """
    def try_parse_date(value: str) -> datetime:
        """Attempt to parse a string to datetime."""
        try:
            return parse_date(value, dayfirst=True)
        except ValueError:
            return None

    if isinstance(data, dict):
        # Process each key-value pair in dictionary
        results = {}
        for key, value in data.items():
            try:
                results[key] = convert_to_custom_date_format(value)
            except Exception as e:
                logger.error("convert_date_format_failed", action="convert_to_custom_date_format", **{"error.code": "PARSE", "error.message": str(e)}, key=key, exc_info=True)
                results[key] = value
        return results    
    elif isinstance(data, list):
        return [convert_to_custom_date_format(item) for item in data]
    
    elif isinstance(data, datetime):
        return data.strftime("%Y-%m-%d %H:%M:%S")
    
    elif isinstance(data, str):
        # Try parsing string as date
        dt = try_parse_date(data)
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # Handle specific formats manually if needed
        date_patterns = [
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$",  # ISO: 2024-12-06T00:00:00
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$",  # 2025-05-30 08:08:50
        ]
        for pattern in date_patterns:
            if re.match(pattern, data):
                dt = try_parse_date(data)
                if dt:
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                logger.warning("convert_date_format_parse_failed", action="convert_to_custom_date_format", data=data)
                return data
        
        return data
    
    elif data is None:
        # Keep null values unchanged
        return None
    
    return data


def validate_id(id_or_code: str) -> str:
    if not id_or_code or not isinstance(id_or_code, str):
        raise ValueError('idOrCode must be a non-empty string')
    return id_or_code


if __name__ == "__main__":
    # Example document
    from pymongo import MongoClient
    from tqdm import tqdm
    client = get_mongo_client()
    db = client[MigrateConfig.MIGRATE_CORE_DB]
    law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]

    documents = law_documents_collection.find({})    
    for document in tqdm(documents):
        try:
            update_documents = convert_to_custom_date_format(document)
            law_documents_collection.update_one({"doc_id": document["doc_id"]}, {"$set": update_documents})                    
        except Exception as e:
            logger.error("main", **{"error.code": "DB", "error.message": str(e)}, doc_id=document.get('doc_id'), exc_info=True)





    # data = {'request_id': 'd54454c1-5e87-4937-ac72-5b6ee2469c45', 
    # 'status': True, 
    # 'document_name': 'SỬA ĐỔI, BỔ SUNG MỘT SỐ ĐIỀU CỦA NGHỊ ĐỊNH SỐ 14/2018/NĐ-CP NGÀY 23 THÁNG 01 NĂM 2018 CỦA CHÍNH PHỦ QUY ĐỊNH CHI TIẾT VỀ HOẠT ĐỘNG THƯƠNG MẠI BIÊN GIỚI', 
    # 'document_code': '122/2024/NĐ-CP', 
    # 'document_type': 'NGHỊ ĐỊNH', 
    # 'agency': ['CHÍNH PHỦ'], 
    # 'human_sign': 
    # [{'human_name': 'Phạm Minh Chính', 'human_title': 'THỦ TƯỚNG', 'human_agency': 'CHÍNH PHỦ'}],
    #  'effective_date': '01/12/2024', 
    #  'issue_date': '04/10/2024', 
    #  'end_effective_date': '', 
    #  'effective_status': '', 
    #  'document_category': 'Văn bản Pháp Luật', 
    #  'document_level': 'Trung Ương'} 

    # output = convert_to_custom_date_format(data)

    
        # Input string in dd/mm/yyyy format
        # input_date = "31/12/2023"

        # # Parse the input string to a datetime object
        # date_obj = datetime.strptime(input_date, "%d/%m/%Y")

        # # Convert to the desired format: %Y-%d-%m %H:%M:%S
        # output_date = date_obj.strftime("%Y-%d-%m %H:%M:%S")