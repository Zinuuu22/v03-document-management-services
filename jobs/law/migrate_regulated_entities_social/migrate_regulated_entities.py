from core.common.mongo.client import get_mongo_client
import os
import sys
import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import structlog
from pymongo import MongoClient
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.v03.regulated_entities.extractor import generate_regulated_entities, convert_to_data_model, llm_instance
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

MAX_WORKERS = 5
CREATED_BY = 'System'
VERSION = 'Qwen3-30B-A3B-Instruct-2507-GGUF:UD-Q6_K_XL'

client = get_mongo_client()

law_db = client['hunghv']
new_law_documents = law_db['law_documents_v1']

core_db = client[MigrateConfig.MIGRATE_CORE_DB]
law_regulated_object = core_db[MongoDBCollectionConfig.LAW_REGULATED_OBJECT_COLLECTION_NAME]
law_regulated_object_mapping = core_db[MongoDBCollectionConfig.LAW_REGULATED_OBJECT_MAPPING_COLLECTION_NAME]
law_documents_collection = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_articles_collection = core_db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]

def get_scope_doc_ids():
    """
    Fetch all the doc_ids from the raw collection ('hunghv.law_documents_v1') 
    so we can limit our extraction scope.
    """
    cursor = new_law_documents.find({"doc_id": {"$exists": True}}, {"doc_id": 1, "_id": 0})
    doc_ids = []
    for doc in cursor:
        did = str(doc.get("doc_id", ""))
        if did:
            doc_ids.append(did)
            if did.isdigit():
                doc_ids.append(int(did))
    return doc_ids

def process_single_document(doc_data):
    """
    Xử lý thực thể điều chỉnh cho từng Document
    """
    doc_id = doc_data.get('doc_id')
    status = "SUCCESS"
    try:
        # 1. Tìm điều luật "Phạm vi điều chỉnh" của document này
        # Lưu ý: dùng find_one vì thường mỗi luật chỉ có 1 điều về phạm vi điều chỉnh
        article = law_articles_collection.find_one({
            'doc_id': doc_id, 
            "article_title": {"$regex": "Phạm vi điều chỉnh"}
        })

        if article:
            article_id = article.get('article_id', '')
            article_title = article.get('article_title', '')
            article_content = article.get('article_content', '')
            content = f"{article_title}\n{article_content}"
        else:
            content = doc_data.get("doc_title", "")
            article_id = ""
            
        if len(content) != 0:
            result = llm_instance.llms_post_process(generate_regulated_entities(content))
            if result:
                data = {
                    'doc_id': doc_id,
                    'article_id': article_id,
                    'content': content,
                    'results': result
                }             
                converted_results, converted_mappings = convert_to_data_model(data)                
                if converted_results:
                    law_regulated_object.insert_many(converted_results)
                if converted_mappings:
                    law_regulated_object_mapping.insert_many(converted_mappings)                                    
    except Exception as e:
        logger.error(action="process_single_document", event="process_single_document_failed", **{"error.code": "LLM", "error.message": str(e)}, doc_id=doc_id, exc_info=True)
        status = "FAIL"

    law_documents_collection.update_one(
        {"doc_id": doc_id}, 
        {"$set": {"is_regulated_entites_extract": status}}
    )
    return doc_id, status


def migrate_data():
    logger.info(action="migrate_data", event="fetching_scope_doc_ids")
    scoped_doc_ids = get_scope_doc_ids()
    
    if not scoped_doc_ids:
        logger.warning(action="migrate_data", event="no_docs_in_scope")
        return

    query = {
        'doc_id': {'$in': scoped_doc_ids},
        "$or": [
            {"is_regulated_entites_extract": "FAIL"},
            {"is_regulated_entites_extract": {"$exists": False}}
        ]
    }

    documents = list(law_documents_collection.find(query, {"_id": 0, 'doc_id': 1, "doc_title": 1}))
    
    if not documents:
        logger.info(action="migrate_data", event="migration_skipped")
        return

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_document, doc): doc for doc in documents}
        
        for future in tqdm.tqdm(as_completed(futures), total=len(documents), desc="Migrating Documents"):
            doc_id, status = future.result()


def main():
    try:
        logger.info(action="main", event="migration_process_started")
        import time
        start_time = time.time()
        migrate_data()
        logger.info(action="main", event="migration_process_completed", duration=f"{time.time() - start_time:.2f}s")
    except Exception as e:
        logger.error(action="main", event="migration_process_failed", **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
        raise


if __name__ == '__main__':
    main()