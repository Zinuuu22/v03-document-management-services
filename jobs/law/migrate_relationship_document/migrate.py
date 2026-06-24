from core.common.mongo.client import get_mongo_client
import uuid
import os
import sys
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import tqdm
import asyncio
import structlog
from pymongo import MongoClient
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig, ExtractBatchConfig
from core.v03.relationship_extractor.extractor import extract_relationship_level_document
from core.common.elastic import search_document_content
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

MAX_WORKERS = 5
LAST_MODIFIED_BY = ''
CREATED_DATE = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

MAP_TYPE_AND_REASON = {
    'base': 'Được văn bản đầu vào sử dụng làm căn cứ',
    'amend': 'Bị sửa đổi bởi văn bản đầu vào',
    'add': 'Bị bổ sung bởi văn bản đầu vào',
    'replace': 'Bị thay thế bởi văn bản đầu vào',
    'repeal_apart': 'Bị bãi bỏ một phần bởi văn bản đầu vào',
    'repeal_full': 'Bị bãi bỏ toàn bộ bởi văn bản đầu vào',
    'detail': 'Được quy định chi tiết bởi văn bản đầu vào',
}

client = get_mongo_client()
core_db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_articles_collection = core_db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
law_references_collection = core_db[MongoDBCollectionConfig.LAW_REFERENCE_COLLECTION_NAME]
law_relationship_collection = core_db[MongoDBCollectionConfig.LAW_RELATIONSHIP_DOCUMENT_COLLECTION_NAME]

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

    
async def process_single_document(doc):
    doc_id = doc.get('doc_id')
    doc_code = doc.get('doc_code')
    doc_title = doc.get('doc_title')
    doc_effective_status = doc.get('doc_effective_status', '')
    batch_size = ExtractBatchConfig.RELATIONSHIP_BATCH_SIZE
    status = "SUCCESS"
    try:
        doc_content = search_document_content(doc_id)
        segments = list(law_articles_collection.find({'doc_id': doc_id}))
        if doc_content and doc_title and segments and doc_code:
            relationships, final_mapping_relationships = await extract_relationship_level_document(doc_content, doc_title, segments, doc_code, batch_size)
            if relationships:
                for key, names in relationships.items():
                    if len(names) != 0:
                        for name in names:
                            data =  {'name': name,
                                'rel_type': key,
                                'type': MAP_TYPE_AND_REASON[key],
                                'doc_id': doc_id}
                            law_relationship_collection.update_one({'doc_id': doc_id, 'name': name}, {"$set": data}, upsert=True)             
                logger.info(action="process_single_document", event="document_relationship_raw_found", doc_id=doc_id)
            
            if final_mapping_relationships:
                for record in final_mapping_relationships:
                    rel_type = record.get('rel_type', '')

                    if rel_type == "base":
                        reference_type = "BASIS"
                    elif rel_type in ["amend", "add", "repeal_apart"]:
                        reference_type = "AMENDED"
                    elif rel_type in ["replace", "repeal_full"]:
                        reference_type = "REPLACED"
                    else:
                        reference_type = rel_type.upper() if rel_type else ""

                    reference = {
                        "reference_id": str(uuid.uuid4()),
                        "source_id": doc_id,
                        "source_type": "DOCUMENT",
                        "target_id": record.get('code', ''),
                        "target_type": "DOCUMENT",
                        "reference_status": doc_effective_status,
                        "reference_type": reference_type,
                        "last_modified_by": LAST_MODIFIED_BY,
                        "created_date": CREATED_DATE
                    }
                    law_references_collection.update_one({'source_id': doc_id, 'target_id': record.get('code','')}, 
                                                         {'$set': reference},
                                                         upsert=True)                
                logger.info(action="process_single_document", event="document_relationships_migrated", doc_id=doc_id)
    except Exception as e:
        logger.error(action="process_single_document", event="process_single_document_failed", **{"error.code": "LLM", "error.message": str(e)}, doc_id=doc_id, exc_info=True)
        status = "FAIL"

    law_documents_collection.update_one(
        {"doc_id": doc_id},
        {"$set": {"is_extract_relationship_document": status}}
    )
    return doc_id, status

def run_process_single_document(doc):
    return asyncio.run(process_single_document(doc))

def migrate_data():
    logger.info(action="migrate_data", event="fetching_scope_doc_ids")
    scoped_doc_ids = get_scope_doc_ids()

    if not scoped_doc_ids:
        logger.warning(action="migrate_data", event="no_docs_in_scope")
        return

    query = {
        'doc_id': {'$in': scoped_doc_ids},
        "$or": [
            {"is_extract_relationship_document": "FAIL"},
            {"is_extract_relationship_document": {"$exists": False}}
        ]
    }    
    documents = list(law_documents_collection.find(query, {'doc_id': 1, 'doc_code': 1,
                                                           'doc_title': 1, 'doc_effective_status': 1, '_id': 0}))
    if not documents:
        logger.info(action="migrate_data", event="migration_skipped")
        return

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(run_process_single_document, doc): doc for doc in documents}
        for future in tqdm.tqdm(as_completed(futures), total=len(documents), desc="Migrating Document Relationships"):
            doc_id, status = future.result()


def main():
    try:
        logger.info(action="main", event="migration_process_started")
        start_time = time.time()
        migrate_data()
        logger.info(action="main", event="migration_process_completed", duration=f"{time.time() - start_time:.2f}s")
    except Exception as e:
        logger.error(action="main", event="migration_process_failed", **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
        raise


if __name__ == "__main__":
    main()