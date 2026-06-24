from core.common.mongo.client import get_mongo_client
from uuid import uuid4
import json
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import structlog
import httpx
import asyncio
from pymongo import MongoClient
import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig, ExtractBatchConfig
from core.v03.social_extractor.extractor import generate_social_relations_async, compose_formal_records
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

MAX_WORKERS = 8
CREATED_BY = 'System'
CREATED_DATE = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

client = get_mongo_client()
core_db = client[MigrateConfig.MIGRATE_CORE_DB]
law_articles_collection = core_db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
law_articles_class_collection = core_db[MongoDBCollectionConfig.LAW_ARTICLE_CLASS_COLLECTION_NAME]
law_documents_collection = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_social_relations_collection = core_db[MongoDBCollectionConfig.LAW_SOCIAL_RELATION_COLLECTION_NAME]
law_social_relations_mapping_collection = core_db[MongoDBCollectionConfig.LAW_SOCIAL_RELATION_MAPPING_COLLECTION_NAME]

# Raw Database (for scoping)
raw_db = client['hunghv']
new_law_docs_collection = raw_db['law_documents_v1']

def get_scope_doc_ids():
    """
    Fetch all the doc_ids from the raw collection ('hunghv.law_documents_v1') 
    so we can limit our extraction scope.
    """
    cursor = new_law_docs_collection.find({"doc_id": {"$exists": True}}, {"doc_id": 1, "_id": 0})
    doc_ids = []
    for doc in cursor:
        did = str(doc.get("doc_id", ""))
        if did:
            doc_ids.append(did)
            if did.isdigit():
                doc_ids.append(int(did))
    return doc_ids
    
async def process_single_document(doc_data):
    """
    Hàm xử lý trọn gói cho một Document
    """
    doc_id = doc_data.get('doc_id')
    try:
        # 1. Lấy danh sách articles của document này
        articles = list(law_articles_collection.find({'doc_id': doc_id}))
        if not articles:
            law_documents_collection.update_one({"doc_id": doc_id}, {"$set": {"is_social_relations_extract": "SUCCESS"}})
            return doc_id, "SUCCESS" 

        all_articles_ok = True
        for article in articles:
            article_id = article.get('article_id','')
            article_title = article.get('article_title','')
            article_content = article.get('article_content','')
            content = f"{article_title}\n{article_content}"
            
            article_class = []
            batch_size = ExtractBatchConfig.SOCIAL_RELATION_BATCH_SIZE
            relations_data = await generate_social_relations_async(content, article_class, httpx.AsyncClient(), asyncio.Semaphore(batch_size))
            
            if relations_data and relations_data.get("social_relations", []):
                formal_records = compose_formal_records(article_id, article_class, relations_data, CREATED_BY, doc_id)
                relations = formal_records.get("relations", [])
                mappings = formal_records.get("mappings", [])
                
                if relations:
                    law_social_relations_collection.insert_many(relations)
                if mappings:
                    law_social_relations_mapping_collection.insert_many(mappings)
            
        # 2. Cập nhật trạng thái sau khi xử lý xong các article của doc
        final_status = "SUCCESS" if all_articles_ok else "FAIL"
        law_documents_collection.update_one(
            {"doc_id": doc_id}, 
            {"$set": {"is_social_relations_extract": final_status}}
        )
        return doc_id, final_status
    except Exception as e:
        logger.error(action="process_single_document", event="process_single_document_failed", **{"error.code": "LLM", "error.message": str(e)}, doc_id=doc_id, exc_info=True)
        law_documents_collection.update_one({"doc_id": doc_id}, {"$set": {"is_social_relations_extract": "FAIL"}})
        return doc_id, "FAIL"

def run_process_single_document(doc_data):
    return asyncio.run(process_single_document(doc_data))

def migrate_data():
    logger.info(action="migrate_data", event="fetching_scope_doc_ids")
    scoped_doc_ids = get_scope_doc_ids()
    
    if not scoped_doc_ids:
        logger.warning(action="migrate_data", event="no_docs_in_scope")
        return

    query = {
        'doc_id': {'$in': scoped_doc_ids},
        "$or": [
            {"is_social_relations_extract": "FAIL"},
            {"is_social_relations_extract": {"$exists": False}}
        ]
    }

    documents = list(law_documents_collection.find(query, {"_id": 0, 'doc_id': 1}))
    if not documents:
        logger.info(action="migrate_data", event="migration_skipped")
        return

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(run_process_single_document, doc): doc for doc in documents}        
        for future in tqdm.tqdm(as_completed(futures), total=len(documents), desc="Migrating Documents"):
            doc_id, status = future.result()
            logger.debug(action="migrate_data", event="document_processing_finished", doc_id=doc_id, status=status)


if __name__ == '__main__':
    migrate_data()
    

        


    