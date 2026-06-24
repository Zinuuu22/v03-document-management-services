from core.common.mongo.client import get_mongo_client
import os
from dotenv import load_dotenv
load_dotenv() # MUST be loaded before importing anything else

import structlog
import sys
from pymongo import MongoClient, UpdateOne, DeleteOne

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

mongo_client = get_mongo_client()
db = mongo_client['hunghv']
document_segment_collection = db['raw_document_new_v1']
pipeline_document_duplicate = db['pipeline_document_duplicate_v1']

core_db = mongo_client['v03_core_11032026']
core_document_collection = core_db['law_documents']

def run_deduplication():
    # 1. Fetch documents from raw_document_new_v1
    logger.info("fetching_documents_from_raw_document_new_v1")
    raw_docs = list(document_segment_collection.find({}))
    logger.info("fetched_raw_docs", count=len(raw_docs))
    
    if not raw_docs:
        logger.info("no_documents_to_process")
        return

    # 2. Pre-fetch existing doc_codes from core database
    logger.info("pre_fetching_existing_doc_codes_from_core")
    existing_docs = core_document_collection.find(
        {"doc_code": {"$exists": True}},
        {"doc_code": 1, "agency_ids": 1, "_id": 0}
    )
    existing_map = {}
    for edge in existing_docs:
        doc_code = edge.get("doc_code")
        a_ids = edge.get("agency_ids", [])
        if doc_code not in existing_map:
            existing_map[doc_code] = []
        existing_map[doc_code].append(a_ids)
    logger.info("fetched_existing_map", total_doc_codes=len(existing_map))

    # 3. Process deduplication
    inserts = []
    deletes = []
    dup_count = 0

    for doc in raw_docs:
        doc_id = doc.get("doc_id")
        doc_code = doc.get("doc_code")
        
        is_dup = False
        if doc_code in existing_map:
            agencies = doc.get("issue_agencies", [])
            current_agency_ids = [a.get("id") for a in agencies]

            # If any agency failed to resolve in Step 1, we skip dedup (similar to Step 1 logic)
            if any(id == "" or id is None for id in current_agency_ids):
                continue

            current_agency_ids = sorted([str(i) for i in current_agency_ids])
            
            # Check against all known agency sets for this doc_code
            for target_agency_ids in existing_map[doc_code]:
                target_ids_sorted = sorted([str(i) for i in target_agency_ids])
                if current_agency_ids == target_ids_sorted:
                    is_dup = True
                    break
        
        if is_dup:
            # Prepare to move to duplicate collection
            inserts.append(UpdateOne({"doc_id": doc_id}, {"$set": doc}, upsert=True))
            # Prepare to remove from raw collection
            deletes.append(DeleteOne({"doc_id": doc_id}))
            dup_count += 1

    if inserts:
        logger.info("moving_duplicates", count=dup_count)
        # We use a transaction-like approach (though not a formal Mongo transaction)
        # Insert first, then delete.
        pipeline_document_duplicate.bulk_write(inserts)
        document_segment_collection.bulk_write(deletes)
        logger.info("deduplication_complete", duplicates_moved=dup_count)
    else:
        logger.info("no_duplicates_found")

if __name__ == "__main__":
    run_deduplication()
