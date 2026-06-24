from core.common.mongo.client import get_mongo_client
import uuid
import os
import sys
import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from datetime import datetime
import structlog
from pymongo import MongoClient


# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from core.common.elastic import search_document_content
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.v03.keywords_extractor.extractor import get_keywords
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

# Constants
CREATED_BY = 'System'
VERSION = 'Qwen3-30B-A3B-Instruct-2507-GGUF:UD-Q6_K_XL'
LAST_MODIFIED_BY = ''
CREATED_DATE = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
MAX_WORKERS = 5

client = get_mongo_client()

# Initialize MongoDB client for this thread
core_db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_articles_collection = core_db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
law_keywords_collection = core_db[MongoDBCollectionConfig.LAW_KEYWORD_COLLECTION_NAME]


def process_single_document(doc):
    doc_id = doc.get('doc_id')
    status = "SUCCESS"

    try:
        logger.info(action="process_single_document", event="document_processing_started", doc_id=doc_id)
        doc_content = search_document_content(doc_id)
        keywords = get_keywords(doc_content)

        keyword_entities = []
        if len(keywords) > 1:
            for keyword in keywords:
                logger.info(action="process_single_document", event="keyword_found", keyword=keyword)
                record = {
                    "keyword_id": str(uuid.uuid4()),
                    "keyword_name": keyword,
                    "created_by": CREATED_BY,
                    "last_modified_by": VERSION,
                    "last_modified": LAST_MODIFIED_BY,
                    "created_date": CREATED_DATE,
                    "status": "ACTIVE"
                }
                law_keywords_collection.insert_one(record)
                keyword_entities.append(record.get("keyword_id"))
            
            logger.info(action="process_single_document", event="document_keywords_summary", count=len(keyword_entities), doc_id=doc_id)
    except Exception as e:
        logger.error(action="process_single_document", event="keyword_extraction_failed", **{"error.code": "LLM", "error.message": str(e)}, doc_id=doc_id, exc_info=True)
        status = "FAIL"

    law_documents_collection.update_one(
        {"doc_id": doc_id},
        {"$set": {"is_extract_keywords": status}}
    )
    return doc_id, status


def migrate():
    query = {
        "$or": [
            {"is_extract_keywords": "FAIL"},
            {"is_extract_keywords": {"$exists": False}}
        ]
    }
    
    documents = list(law_documents_collection.find(query, {"_id": 0, 'doc_id': 1}))
    
    if not documents:
        logger.info(action="migrate", event="no_documents_to_process")
        return
    
    logger.info(action="migrate", event="migration_started", count=len(documents), workers=MAX_WORKERS)
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_document, doc): doc for doc in documents}
        
        for future in tqdm.tqdm(as_completed(futures), total=len(documents), desc="Migrating Keywords"):
            doc_id, status = future.result()

if __name__ == '__main__':
    migrate()
    