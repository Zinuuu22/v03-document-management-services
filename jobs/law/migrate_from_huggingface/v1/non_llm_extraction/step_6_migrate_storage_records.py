from core.common.mongo.client import get_mongo_client
import os
from dotenv import load_dotenv
load_dotenv() # MUST be loaded before importing anything else

import structlog
import sys
import uuid
from pymongo import MongoClient, UpdateOne
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MinioConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

mongo_client = get_mongo_client()
db = mongo_client['hunghv']
raw_documents = db['raw_document_new_v1']
storage_collection = db['law_document_storage_v1']

def get_minio_objects():
    from minio import Minio
    # --- connect ---
    endpoint = MinioConfig.ENDPOINT.replace("http://", "").replace("https://", "")
    client = Minio(
        endpoint,
        access_key=MinioConfig.ACCESS_KEY,
        secret_key=MinioConfig.SECRET_KEY,
        secure=False
    )
    crawl_bucket = "v03.vbpl-crawl"
    
    file_map = {} # doc_id -> (object_name, bucket)
    try:
        logger.info("listing_minio_objects", bucket=crawl_bucket)
        objects = client.list_objects(crawl_bucket, recursive=True)
        for obj in objects:
            name = obj.object_name
            if "_m_" not in name:
                continue
            
            try:
                suffix = name.split("_m_")[-1]
                doc_id_part = suffix.split(".")[0]
                file_map[doc_id_part] = {
                    "name": name,
                    "bucket": crawl_bucket,
                    "path": name # Path is same as name in this context
                }
            except Exception:
                continue
        logger.info("minio_objects_listed", count=len(file_map))
    except Exception as e:
        logger.error("minio_listing_failed", error=str(e))
        
    return file_map

def migrate_storage_records():
    # 0. Drop existing storage collection to ensure a clean slate
    logger.info("Resetting collection: dropping law_document_storage...")
    storage_collection.drop()
    
    # 1. Get all objects from MinIO
    minio_files = get_minio_objects()
    
    # 2. Get all raw documents that have a file path
    # Even if they don't have doc_file_path, we might want to check doc_id
    cursor = raw_documents.find({}, {"doc_id": 1, "content.doc_file_path": 1})
    
    records_to_upsert = []
    created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for doc in cursor:
        doc_id = str(doc.get("doc_id"))
        
        # Check if we have a match in MinIO
        if doc_id in minio_files:
            file_info = minio_files[doc_id]
            
            storage_record = {
                "storage_id": str(uuid.uuid4()),
                "doc_id": doc_id,  # Explicitly store doc_id for reliable linking
                "bucket": file_info["bucket"],
                "name": file_info["name"],
                "path": file_info["path"],
                "created_at": created_date,
                "created_by": "SYSTEM",
            }
            
            records_to_upsert.append(
                UpdateOne(
                    {"storage_id": storage_record["storage_id"]},
                    {"$set": storage_record},
                    upsert=True
                )
            )
            
    if records_to_upsert:
        logger.info("upserting_storage_records", count=len(records_to_upsert))
        result = storage_collection.bulk_write(records_to_upsert)
        logger.info("upsert_done", matched=result.matched_count, upserted=result.upserted_count, modified=result.modified_count)
    else:
        logger.info("no_records_to_migrate")

if __name__ == "__main__":
    migrate_storage_records()
