from core.common.mongo.client import get_mongo_client
import uuid
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import structlog
from pymongo import MongoClient
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.v03.content_extractor.extractor import extract_components
from core.common.elastic import search_document_content
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

CREATED_BY = 'SYSTEM'
MAX_WORKERS = 10  

client = get_mongo_client()
core_db = client[MigrateConfig.MIGRATE_CORE_DB]
document_collection = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
article_collection = core_db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
clause_collection = core_db[MongoDBCollectionConfig.LAW_CLAUSE_COLLECTION_NAME]


list_code_error = []
count_error = 0
count_success = 0

def process_document(doc):
    global list_code_error
    global count_error
    global count_success
    is_extract_article = doc.get("is_extract_article", "FAIL")
    if is_extract_article != "FAIL":
        return

    doc_id = doc["doc_id"]
    doc_code = doc["doc_code"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        # 1. Fetch content from Elasticsearch
        # 1. Fetch content from Elasticsearch
        logger.info(action="process_document", event="process_document_started", doc_id=doc_id)
        content = search_document_content(doc_id)
        logger.info(action="process_document", event="content_fetched", doc_id=doc_id)

        # 2. Extract articles and clauses
        articles = extract_components(content=content, document_code=doc_code)
        if articles:
            for idx, article in enumerate(articles):
                # 3. Save articles to law_articles
                article_doc = {
                    "article_id": article["code"],
                    "doc_id": doc_id,
                    "article_title": article["article_title"],
                    "article_content": article["article_content"],
                    "article_order_index": article["segment_index"],
                    "created_date": now,
                    "created_by": CREATED_BY,
                    "last_modified": now,
                    "last_modified_by": CREATED_BY,
                    "part": article.get("part"),
                    "chapter": article.get("chapter"),
                    "section": article.get("section"),
                    "sub_section": article.get("sub_section")                    
                }
                article_collection.insert_one(article_doc)
                logger.info(action="process_document", event="article_saved", article_code=article['code'], doc_id=doc_id)
                
                # 4. Save clauses to law_clauds
                clauds = article["clauds"]            
                description = article["article_content"].split('1.')[0].strip()
                for idx, claud in enumerate(clauds):  
                    claud_doc = {
                        "claud_id": str(uuid.uuid4()), 
                        "article_id": article["code"],
                        "claud_summary_content": f"{article['article_title']}\n{description}\n{claud['claud']}".strip(),
                        "claud_content": claud["claud"].strip(),
                        "claud_order_index": idx,
                        "created_date": now,
                        "created_by": CREATED_BY,
                        "last_modified": now,
                        "last_modified_by": CREATED_BY                        
                    }
                    clause_collection.insert_one(claud_doc)

            document_collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "is_extract_article": "SUCCESS"
                }}
            )
            
            logger.info(action="process_document", event="process_document_completed", doc_id=doc_id)
            count_success += 1
        else:
            list_code_error.append(doc_id)
            document_collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "is_extract_article": "FAIL"
                }}
            )
            logger.info(action="process_document", event="process_document_failed", doc_id=doc_id)
            count_error += 1

    except Exception as e:
        logger.error(action="process_document", event="process_document_failed", **{"error.code": "DB", "error.message": str(e)}, doc_id=doc_id, exc_info=True)
        document_collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {
                "is_extract_article": "FAIL"
            }}
        )

def migrate():
    """Migrate data from law_documents to law_articles and law_clauds using multithreading."""
    global list_code_error
    global count_error
    global count_success
    query = {}
    documents = list(document_collection.find(query))  

    logger.info(action="migrate", event="migration_started", total_docs=len(documents))
    if not documents:
        logger.info(action="migrate", event="migration_skipped")
        return
    logger.info(action="migrate", event="migration_started", count=len(documents))

    # Process documents in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_doc = {executor.submit(process_document, doc): doc["doc_id"] for doc in documents}
        for future in as_completed(future_to_doc):
            doc_id = future_to_doc[future]
            try:
                future.result()  
            except Exception as e:
                logger.error(action="migrate", event="future_failed", **{"error.code": "DB", "error.message": str(e)}, doc_id=doc_id, exc_info=True)

    logger.info(action="migrate", event="migration_summary", codes=list_code_error)
    logger.info(action="migrate", event="migration_summary", error_count=count_error)
    logger.info(action="migrate", event="migration_summary", success_count=count_success)
if __name__ == "__main__":
    migrate()