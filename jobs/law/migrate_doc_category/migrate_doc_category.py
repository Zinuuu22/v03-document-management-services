from core.common.mongo.client import get_mongo_client
import os
import sys
import time
from datetime import datetime
from typing import Tuple
import structlog
from pymongo import MongoClient, UpdateOne
from pymongo.database import Database

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()


BATCH_SIZE = 1000
NEW_COLLECTION_NAME = 'law_doc_category'

DOC_CATEGORIES = [
    {
        'doc_category': 'Văn bản Pháp Luật',
        'doc_category_id': None  
    },
    {
        'doc_category': 'Văn bản Hành Chính',
        'doc_category_id': None
    }
]


def connect_to_databases() -> Tuple[MongoClient, Database]:
    try:
        client = get_mongo_client()
        core_db = client[MigrateConfig.MIGRATE_CORE_DB]
        return client, core_db
    except Exception as e:
        logger.error(action="connect_to_databases", event="connect_to_databases_failed", **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
        raise


def generate_doc_category_id(index: int) -> str:
    now = datetime.now()
    year_month = now.strftime("%Y%m")
    sequence = str(index).zfill(6)
    return f"{year_month}{sequence}QP"


def migrate_doc_category(dry_run: bool = False) -> None:
    logger.info(action="migrate_doc_category", event="connecting_to_mongodb")
    client, core_db = connect_to_databases()
    
    law_documents = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
    law_doc_category = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_CATEGORY_COLLECTION_NAME]
    
    try:
        law_doc_category.create_index([('doc_category_id', 1)], unique=True)
        law_doc_category.create_index([('doc_category', 1)])
    except Exception as e:
        logger.debug(action="migrate_doc_category", event="index_creation_skipped", error=str(e))
    logger.info(action="migrate_doc_category", event="connected_to_mongodb")
    
    existing_categories = list(law_doc_category.find({}))
    if len(existing_categories) >= 2:
        logger.debug(action="migrate_doc_category", event="existing_categories_found")
        category_map = {}
        for cat in existing_categories:
            category_map[cat['doc_category']] = cat['doc_category_id']
    else:
        logger.info(action="migrate_doc_category", event="creating_categories")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_user = "system"
        
        category_map = {}
        for i, cat_info in enumerate(DOC_CATEGORIES, start=1):
            doc_category_id = generate_doc_category_id(i)
            
            category_doc = {
                'doc_category_id': doc_category_id,
                'doc_category': cat_info['doc_category'],
                'created_date': current_time,
                'last_modified': current_time,
                'created_by': current_user,
                'last_modified_by': current_user,
                'status': 'ACTIVE'
            }
            
            if not dry_run:
                law_doc_category.insert_one(category_doc)
            
            category_map[cat_info['doc_category']] = doc_category_id
            logger.debug(action="migrate_doc_category", event="category_created", category=cat_info['doc_category'], id=doc_category_id)
    
    logger.info(action="migrate_doc_category", event="category_mapping", category_map=category_map)
    
    total_count = law_documents.count_documents({})
    logger.info(action="migrate_doc_category", event="total_documents_count", count=total_count)
    
    already_migrated = law_documents.count_documents({'doc_category_id': {'$exists': True, '$ne': None}})
    if already_migrated > 0:
        logger.warning(action="migrate_doc_category", event="documents_already_migrated", count=already_migrated)
    
    processed_count = 0
    error_count = 0
    start_time = time.time()
    
    for doc_category_value, doc_category_id in category_map.items():
        logger.info(action="migrate_doc_category", event="processing_documents", category=doc_category_value)
        
        query = {'doc_category': doc_category_value}
        count = law_documents.count_documents(query)
        logger.info(action="migrate_doc_category", event="documents_found", category=doc_category_value, count=count)
        
        if count == 0:
            continue
        
        if not dry_run:
            result = law_documents.update_many(
                query,
                {'$set': {'doc_category_id': doc_category_id}}
            )
            processed_count += result.modified_count
            logger.info(action="migrate_doc_category", event="documents_updated", count=result.modified_count, category=doc_category_value)
        else:
            processed_count += count
            logger.info(action="migrate_doc_category", event="documents_update_simulated", count=count, category=doc_category_value)
    
    null_category_count = law_documents.count_documents({
        '$or': [
            {'doc_category': {'$exists': False}},
            {'doc_category': None},
            {'doc_category': ''}
        ]
    })
    if null_category_count > 0:
        logger.warning(action="migrate_doc_category", event="documents_missing_category", count=null_category_count)
    
    elapsed = time.time() - start_time
    logger.info(action="migrate_doc_category", event="migration_completed", duration=elapsed)
    logger.info(action="migrate_doc_category", event="migration_summary", processed=processed_count, errors=error_count)
    
    if not dry_run:
        category_count = law_doc_category.count_documents({})
        logger.info(action="migrate_doc_category", event="verification_started", count=category_count)
        
        for doc_category_value, doc_category_id in category_map.items():
            count = law_documents.count_documents({'doc_category_id': doc_category_id})
            logger.info(action="migrate_doc_category", event="verification_results", category=doc_category_value, count=count)
    
    client.close()


def verify_migration() -> None:
    logger.info(action="verify_migration", event="verification_started")
    client, core_db = connect_to_databases()
    
    law_documents = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
    law_doc_category = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_CATEGORY_COLLECTION_NAME]
    
    total_docs = law_documents.count_documents({})
    docs_with_category_id = law_documents.count_documents({'doc_category_id': {'$exists': True, '$ne': None}})
    category_entries = law_doc_category.count_documents({})
    
    logger.info(action="verify_migration", event="total_documents_count", count=total_docs)
    logger.info(action="verify_migration", event="documents_with_category_count", count=docs_with_category_id)
    logger.info(action="verify_migration", event="category_entries_count", count=category_entries)
    
    if category_entries != 2:
        logger.warning(action="verify_migration", event="unexpected_category_entries_count", count=category_entries)
    
    categories = list(law_doc_category.find({}))
    logger.info(action="verify_migration", event="category_entries_list")
    for cat in categories:
        count = law_documents.count_documents({'doc_category_id': cat['doc_category_id']})
        logger.info(action="verify_migration", event="category_entry_details", category_id=cat['doc_category_id'], category=cat['doc_category'], count=count)
    
    sample_docs = list(law_documents.aggregate([
        {'$match': {'doc_category_id': {'$exists': True}}},
        {'$sample': {'size': 5}}
    ]))
    
    for doc in sample_docs:
        category_entry = law_doc_category.find_one({'doc_category_id': doc.get('doc_category_id')})
        if category_entry:
            match = category_entry['doc_category'] == doc.get('doc_category', '')
            logger.info(action="verify_migration", event="sample_verification", doc_id=doc['doc_id'], category_id=doc.get('doc_category_id'), doc_category=doc.get('doc_category', ''), match=match)
        else:
            logger.error(action="verify_migration", event="category_entry_not_found", **{"error.code": "DB", "error.message": "Category entry not found"}, doc_id=doc['doc_id'], category_id=doc.get('doc_category_id'))
    
    client.close()


def rollback_migration() -> None:
    logger.warning(action="rollback_migration", event="rollback_started")
    client, core_db = connect_to_databases()

    law_documents = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
    law_doc_category = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_CATEGORY_COLLECTION_NAME]
    
    result = law_documents.update_many(
        {'doc_category_id': {'$exists': True}},
        {'$unset': {'doc_category_id': ''}}
    )
    logger.info(action="rollback_migration", event="documents_unset", count=result.modified_count)
    
    law_doc_category.drop()
    logger.info(action="rollback_migration", event="collection_dropped", collection=NEW_COLLECTION_NAME)
    
    client.close()
    logger.info(action="rollback_migration", event="rollback_completed")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate doc_category to new collection (v2 - 2 entries only)')
    parser.add_argument('--dry-run', action='store_true', help='Run without making changes')
    parser.add_argument('--verify', action='store_true', help='Verify migration')
    parser.add_argument('--rollback', action='store_true', help='Rollback migration')
    
    args = parser.parse_args()
    
    if args.verify:
        verify_migration()
    elif args.rollback:
        confirm = input("Are you sure you want to rollback? This will remove all migrated data. (yes/no): ")
        if confirm.lower() == 'yes':
            rollback_migration()
        else:
            logger.info(action="rollback_migration", event="rollback_cancelled")
    else:
        if args.dry_run:
            logger.info(action="migrate_doc_category", event="dry_run_mode_enabled")
        migrate_doc_category(dry_run=args.dry_run)
