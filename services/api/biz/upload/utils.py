from core.common.mongo.client import get_mongo_client
import structlog
import os
import sys
import uuid
from pymongo import MongoClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)
from constants import PreprocessTopics, MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from services.api.utils import send_kafka_message
from jobs.law.utils import get_last_modified_by, parse_datetime
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()
                
client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
law_references_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_COLLECTION_NAME]

def send_requests_to_kafka_extract(request_id: str, doc_id: str, doc_content: str) -> bool:
    """
    Gửi tin nhắn đến các Kafka topics để xử lý bóc tách thông tin từ tài liệu
    
    Args:
        request_id: ID của request
        doc_id: ID của document
        doc_content: Nội dung tài liệu cần xử lý
        
    Returns:
        bool: True nếu gửi thành công tất cả các message, False nếu có lỗi
    """
    message = {
        "request_id": request_id,
        "doc_id": doc_id,
        "doc_content": doc_content,
        "top_k": 10
    }
    
    topics = [
        (PreprocessTopics.EXTRACT_METADATA_QUERY_TOPIC, "metadata extraction"),
        (PreprocessTopics.EXTRACT_RELATIONSHIP_QUERY_TOPIC, "document relationship extraction"),
        (PreprocessTopics.EXTRACT_KEYWORD_QUERY_TOPIC, "keyword extraction"),
        (PreprocessTopics.EXTRACT_ARTICLE_RELATIONSHIP_QUERY_TOPIC, "article relationship extraction"),
        (PreprocessTopics.EXTRACT_REGULATED_ENTITIES_QUERY_TOPIC, "regulated entities extraction"),
        (PreprocessTopics.EXTRACT_SOCIAL_RELATION_QUERY_TOPIC, "social relation extraction"),
        (PreprocessTopics.EXTRACT_LAW_AUTHORITY_QUERY_TOPIC, "law authority extraction")
    ]
    
    has_error = False
    
    for topic, description in topics:
        try:
            logger.debug("send_extract_kafka_sending", action="send_requests_to_kafka_extract", topic=topic, description=description, doc_id=doc_id)
            send_kafka_message(topic, message)
            logger.info("send_extract_kafka_success", action="send_requests_to_kafka_extract", topic=topic, description=description, doc_id=doc_id)
        except Exception as e:
            has_error = True
            logger.error("send_extract_kafka_failed", action="send_requests_to_kafka_extract", **{"error.code": "EXT", "error.message": str(e)}, topic=topic, description=description, doc_id=doc_id, exc_info=True)
    return not has_error



def send_requests_to_kafka_index(request_id: str, doc_id: str):
    """
    Gửi tin nhắn đến các Kafka topics để index tài liệu
    
    Args:
        request_id: ID của request
        doc_id: ID của document
        
    Returns:
        bool: True nếu gửi thành công tất cả các message, False nếu có lỗi
    """
    message = {
        "request_id": request_id,
        "doc_id": doc_id,
        "top_k": 10
    }
    
    topics = [
        (PreprocessTopics.INDEX_ELASTIC_QUERY_TOPIC, "elastic indexing"),
        (PreprocessTopics.TITLE_EMBEDDING_QUERY_TOPIC, "title embedding"),
        (PreprocessTopics.CONTENT_EMBEDDING_QUERY_TOPIC, "content embedding"),
        (PreprocessTopics.ARTICLE_EMBEDDING_QUERY_TOPIC, "article embedding"),
        (PreprocessTopics.CLASSIFICATION_ARTICLE_QUERY_TOPIC, "articles classification")
    ]
    
    has_error = False
    
    for topic, description in topics:
        try:
            logger.debug("send_index_kafka_sending", action="send_requests_to_kafka_index", topic=topic, description=description, doc_id=doc_id)
            send_kafka_message(topic, message)
            logger.info("send_index_kafka_success", action="send_requests_to_kafka_index", topic=topic, description=description, doc_id=doc_id)
        except Exception as e:
            has_error = True
            logger.error("send_index_kafka_failed", action="send_requests_to_kafka_index", **{"error.code": "EXT", "error.message": str(e)}, topic=topic, description=description, doc_id=doc_id, exc_info=True)
    return not has_error




def add_relationship_to_db(document):
    try:
        add_documents = document.get('add', []) + document.get('amend', []) + document.get('repeal_apart', [])
        basis_documents = document.get('base', [])
        replace_documents = document.get('replace', []) + document.get('repeal_full', [])
        detail_documents = document.get('detail', [])
        
        reference_types = [
                    ('AMEND', add_documents),
                    ('BASIS', basis_documents),
                    ('REPLACE', replace_documents),
                    ('DETAIL', detail_documents)
                ]

        references_to_insert = []
        for ref_type, ref_docs in reference_types:
            for target_id in ref_docs:
                reference = {
                    'reference_id': str(uuid.uuid4()),
                    'source_id': str(document['doc_id']),
                    'source_type': 'DOCUMENT',
                    'target_id': str(target_id),
                    'target_type': 'DOCUMENT',
                    'reference_status': document.get('decree_status', ''),
                    'reference_type': ref_type,
                    'created_date': parse_datetime(document.get('created_date', None)),
                    'last_modified': get_last_modified_by(document),
                    'last_modified_by': document.get('last_modified_by', '')
                }
                references_to_insert.append(reference)
        
        if references_to_insert:
            law_references_collection.insert_many(references_to_insert, ordered=False)
            logger.info("add_relationship_to_db_success", action="add_relationship_to_db", count=len(references_to_insert), source_doc_code=document.get('doc_code', ''))
    except Exception:
        logger.error("add_relationship_to_db_failed", action="add_relationship_to_db", **{"error.code": "DB", "error.message": "Failed to add relationship to DB"}, exc_info=True)
        return False    
    return True


if __name__ == "__main__":
    biz_upload_documents_collection = db[MongoDBCollectionConfig.BIZ_UPLOAD_DOCUMENTS_COLLECTION_NAME]
    biz_upload_documents_collection.create_index([('doc_id', 1)])
    document = biz_upload_documents_collection.find_one({'doc_id': 'c5f72000-2359-470f-8a56-a1f948599be6'})
    logger.debug("get_upload_document_result", action="__main__", result=document)
    status = add_relationship_to_db(document)
