from core.common.mongo.client import get_mongo_client
import os
import sys
import structlog
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Thiết lập môi trường ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.common.elastic import ElasticIndexer
from jobs.law.supports.utils import get_doc_content
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

MAX_WORKERS = 10 

# --- Khởi tạo Clients ---
# Pymongo, Minio và Elastic clients thường thread-safe và có connection pool riêng
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_RAW_DB]
document_segment_colection = db[MongoDBCollectionConfig.RAW_DOCUMENTS_SEGMENTS_COLLECTION_NAME]
elastic_client = ElasticIndexer()

def process_document(document):
    """Hàm xử lý cho từng tài liệu đơn lẻ"""
    doc_code = document.get('code', 'unknown')
    
    # Kiểm tra trạng thái trước khi xử lý
    is_in_elastic = document.get("is_in_elastic", "FAIL")
    if is_in_elastic != "FAIL":
        return None

    try:        
        resource_code = document.get("storage_code", None)
        if not resource_code:
            logger.error(action="process_document", event="resource_code_missing", **{"error.code": "DB", "error.message": "Missing resource code"}, doc_code=doc_code)   
            return f"{doc_code}: MISSING_RESOURCE_CODE"
        
        # Lấy nội dung văn bản (Tác vụ nặng về I/O)
        content = get_doc_content(resource_code)
        if content == "" or content is None:
            logger.warning(action="process_document", event="content_empty", doc_code=doc_code)   
        document["description"] = content
        
        # Cập nhật lên Elasticsearch
        elastic_client.update_document_to_elastic(document)
        
        # Cập nhật trạng thái vào MongoDB
        document_segment_colection.update_one(
            {"code": doc_code},
            {"$set": {"is_in_elastic": "SUCCESS"}}
        )
        logger.info(action="process_document", event="document_processed", doc_code=doc_code)
        return None

    except Exception as e:
        logger.error(action="process_document", event="document_processing_failed", **{"error.code": "EXT", "error.message": str(e)}, doc_code=doc_code, exc_info=True)
        return f"{doc_code}: ERROR"

def main():
    # Lấy danh sách tài liệu cần xử lý (chuyển sang list để tránh lỗi cursor timeout trong đa luồng)
    documents = list(document_segment_colection.find({}))
    total = len(documents)
    logger.info(action="main", event="migration_started", total=total)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_document, doc): doc for doc in documents}
        count = 0
        for future in as_completed(futures):
            count += 1
            future.result()
            if count % 10 == 0:
                logger.info(action="main", event="migration_progress", count=count, total=total)

if __name__ == "__main__":
    main()