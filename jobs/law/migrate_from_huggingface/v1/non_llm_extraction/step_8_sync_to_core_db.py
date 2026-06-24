from core.common.mongo.client import get_mongo_client
import os
from dotenv import load_dotenv
load_dotenv() 

import structlog
import sys
from pymongo import MongoClient, UpdateOne
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

# --- Connections ---
mongo_client = get_mongo_client()

# Source and Destination Databases
source_db = mongo_client['hunghv']
dest_db = mongo_client['v03_core_11032026']

# Collection Mapping: { source_name: (dest_name, unique_id_field) }
COLLECTION_MAPPINGS = {
    "law_agencies": ("law_agencies", "agency_id"),
    "law_doc_types": ("law_doc_types", "type_id"),
    "law_doc_category": ("law_doc_category", "category_id"),
    "law_documents_v1": ("law_documents", "doc_id"),
    "law_articles_v1": ("law_articles", "article_id"),
    "law_document_storage_v1": ("law_document_storage", "storage_id")
}

def migrate_to_core(update=False):
    logger.info("core_migration_started", source="hunghv", destination="v03_core_11032026", mode="update" if update else "insert_only")

    BATCH_SIZE = 100

    for src_name, (dest_name, id_field) in COLLECTION_MAPPINGS.items():
        logger.info("migrating_collection", source=src_name, destination=dest_name, key=id_field)

        src_coll = source_db[src_name]
        dest_coll = dest_db[dest_name]

        cursor = src_coll.find({})
        batch = []
        total_processed = 0

        for doc in cursor:
            target_id = doc.get(id_field)
            if not target_id:
                logger.warning("skipping_record_missing_id", collection=src_name, doc_id=str(doc.get("_id")))
                continue

            clean_doc = {k: v for k, v in doc.items() if k != "_id"}

            if update:
                operation = UpdateOne(
                    {id_field: target_id},
                    {"$set": clean_doc},
                    upsert=True
                )
            else:
                operation = UpdateOne(
                    {id_field: target_id},
                    {"$setOnInsert": clean_doc},
                    upsert=True
                )
            batch.append(operation)
            
            if len(batch) >= BATCH_SIZE:
                try:
                    result = dest_coll.bulk_write(batch, ordered=False)
                    upserted = result.upserted_count
                    matched = result.matched_count
                except Exception as e:
                    logger.error("bulk_write_error", collection=dest_name, error=str(e))
                    if hasattr(e, 'details'):
                        for err in e.details.get('writeErrors', []):
                            logger.error("document_validation_error", error=err)
                    upserted = e.details.get('nUpserted', 0) if hasattr(e, 'details') else 0
                    matched = e.details.get('nMatched', 0) if hasattr(e, 'details') else 0

                total_processed += len(batch)
                logger.info("batch_migrated", 
                            collection=dest_name, 
                            total=total_processed,
                            new_inserted=upserted,
                            skipped_existing=matched)
                batch = []
                
        # Flush remaining
        if batch:
            try:
                result = dest_coll.bulk_write(batch, ordered=False)
                upserted = result.upserted_count
                matched = result.matched_count
            except Exception as e:
                logger.error("bulk_write_error_final", collection=dest_name, error=str(e))
                if hasattr(e, 'details'):
                    for err in e.details.get('writeErrors', []):
                        logger.error("document_validation_error", error=err)
                upserted = e.details.get('nUpserted', 0) if hasattr(e, 'details') else 0
                matched = e.details.get('nMatched', 0) if hasattr(e, 'details') else 0

            total_processed += len(batch)
            logger.info("migration_collection_completed", 
                        collection=dest_name, 
                        total=total_processed,
                        new_inserted=upserted,
                        skipped_existing=matched)

    logger.info("all_migrations_completed")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true", help="Use $set to update existing records instead of skipping them.")
    args = parser.parse_args()
    migrate_to_core(update=args.update)