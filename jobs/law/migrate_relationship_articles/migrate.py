from core.common.mongo.client import get_mongo_client
import argparse
import os
import sys
import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import structlog
from pymongo import MongoClient
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.v03.relationship_extractor.articles import process_article_async
from core.v03.relationship_extractor.utils import convert_relationships_to_records
import asyncio
import httpx
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

MAX_WORKERS = 8

client = get_mongo_client()
core_db = client[MigrateConfig.MIGRATE_CORE_DB]
document_collection = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
article_collection = core_db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
law_rel_article_collection = core_db[MongoDBCollectionConfig.LAW_REFERENCE_ARTICLE_COLLECTION_NAME]
law_rel_article_draft_collection = core_db[MongoDBCollectionConfig.LAW_REFERENCE_ARTICLE_DRAFT_COLLECTION_NAME]
law_relationship_article_collection = core_db[MongoDBCollectionConfig.LAW_RELATIONSHIP_ARTICLE_COLLECTION_NAME]

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
    doc_id = doc_data.get('doc_id')
    doc_title = doc_data.get('doc_title', '')
    status = "SUCCESS"
    try:
        articles = list(article_collection.find({'doc_id': doc_id}))
        async with httpx.AsyncClient(timeout=60.0) as client:
            sem = asyncio.Semaphore(5)
            for article in articles:
                article_id = article.get('article_id')
                
                if law_rel_article_collection.find_one({'doc_id': doc_id, 'article_id': article_id}):
                    continue

                results = await process_article_async(article, doc_title, client, sem)

                if results:
                    law_relationship_article_collection.insert_many(results)
                    logger.info(action="process_single_document", event="article_migrated", article_id=article_id)
                    convert_data, draft_data = convert_relationships_to_records(results, collect_drafts=True)
                    if convert_data:
                        law_rel_article_collection.insert_many(convert_data)
                        logger.info(action="process_single_document", event="article_records_migrated", article_id=article_id)
                    else:
                        logger.warning(action="process_single_document", event="article_relationship_not_found", article_id=article_id)
                    # References whose target document is not (yet) in the DB → draft collection.
                    if draft_data:
                        law_rel_article_draft_collection.insert_many(draft_data)
                        logger.info(action="process_single_document", event="article_draft_records_migrated", article_id=article_id, count=len(draft_data))
                else:
                    logger.warning(action="process_single_document", event="article_relationship_not_found", article_id=article_id)
    except Exception as e:
        logger.error(action="process_single_document", event="process_single_document_failed", **{"error.code": "LLM", "error.message": str(e)}, doc_id=doc_id, exc_info=True)
        status = "FAIL"

    document_collection.update_one(
        {"doc_id": doc_id},
        {"$set": {"is_extract_relationship_article": status}}
    )
    return doc_id, status

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
            {"is_extract_relationship_article": "FAIL"},
            {"is_extract_relationship_article": {"$exists": False}}
        ]
    }
    documents = list(document_collection.find(query, {"_id": 0, 'doc_id': 1, "doc_title": 1}))
    if not documents:
        logger.info(action="migrate_data", event="migration_skipped")
        return

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(run_process_single_document, doc): doc for doc in documents}
        for future in tqdm.tqdm(as_completed(futures), total=len(documents), desc="Migrating Relationships"):
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