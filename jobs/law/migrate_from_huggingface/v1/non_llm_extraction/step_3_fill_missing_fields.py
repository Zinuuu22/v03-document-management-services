from core.common.mongo.client import get_mongo_client
import os
from dotenv import load_dotenv
load_dotenv() 

import structlog
import sys
import uuid
import random
import string
import re
from pymongo import MongoClient, UpdateOne
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

# --- Connection ---
mongo_client = get_mongo_client()
db = mongo_client['hunghv']

# Collections
law_docs_coll = db['law_documents_v1']
raw_docs_coll = db['raw_document_new_v1']
storage_coll = db['law_document_storage_v1']
local_doc_types = db['law_doc_types']
local_categories = db['law_doc_category']
local_agencies = db['law_agencies']

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_custom_id(prefix="202503", seq=1):
    """Generates an ID in the format YYYYMMNNNNNXXX (e.g., 20250300001VOQ)"""
    suffix = ''.join(random.choices(string.ascii_uppercase, k=3))
    return f"{prefix}{seq:05d}{suffix}"

def resolve_id(collection, match_field, match_value, id_field, prefix="202503"):
    """Find-or-create lookup for local catalogs."""
    if not match_value:
        return ""
    
    # Try case-insensitive exact match
    existing = collection.find_one({
        match_field: {"$regex": f"^{re.escape(match_value.strip())}$", "$options": "i"}
    })
    
    if existing:
        return existing[id_field]
    
    # Seed new entry
    logger.info("seeding_new_catalog_entry", collection=collection.name, value=match_value)
    count = collection.count_documents({})
    new_id = generate_custom_id(prefix=prefix, seq=count + 1)
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    collection.insert_one({
        id_field: new_id,
        match_field: match_value,
        "status": "ACTIVE",
        "created_at": now_str,
        "created_by": "SYSTEM",
        "last_modified_at": now_str,
        "last_modified_by": "admin"
    })
    return new_id

def get_raw_doc(doc_id):
    """Fetch raw doc with flexible ID typing (supports string or int)."""
    # 1. Try as is (usually string in processed)
    res = raw_docs_coll.find_one({"doc_id": doc_id})
    if res: return res
    # 2. Try as int
    try:
        res = raw_docs_coll.find_one({"doc_id": int(doc_id)})
        if res: return res
    except: pass
    # 3. Try as str
    return raw_docs_coll.find_one({"doc_id": str(doc_id)})

# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def replenish_ids():
    # --- PHASE 1: Replenish raw_document_new_v1 ---
    logger.info("starting_replenishment", target="raw_document_new_v1")
    
    raw_agency_query = {"$or": [{"issue_agencies.id": {"$exists": False}}, {"issue_agencies.id": {"$in": ["", None]}}]}
    raw_missing_agency = list(raw_docs_coll.find(raw_agency_query, {"doc_id": 1, "issue_agencies": 1}))
    
    if raw_missing_agency:
        logger.info("target_found", count=len(raw_missing_agency), target="raw_document_new_v1_agencies")
        raw_ops = []
        for doc in raw_missing_agency:
            updated_agencies = []
            changed = False
            for agency in doc.get("issue_agencies", []):
                if not agency.get("id"):
                    aid = resolve_id(local_agencies, "agency_id", "agency_name", agency.get("name")) # Fixed resolve_id params if needed
                    # Wait, resolve_id(collection, match_field, match_value, id_field)
                    aid = resolve_id(local_agencies, "agency_name", agency.get("name"), "agency_id")
                    agency["id"] = aid
                    changed = True
                updated_agencies.append(agency)
            
            if changed:
                raw_ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"issue_agencies": updated_agencies}}))
        
        if raw_ops:
            res = raw_docs_coll.bulk_write(raw_ops)
            logger.info("replenished_agency_ids", count=res.modified_count, target="raw_document_new_v1")

    # --- PHASE 2: Replenish law_documents_v1 ---
    logger.info("starting_replenishment", target="law_documents_v1")
    
    # 1. Fill missing category_id
    cat_query = {"$or": [{"category_id": {"$exists": False}}, {"category_id": {"$in": ["", None]}}]}
    docs_missing_cat = list(law_docs_coll.find(cat_query, {"doc_id": 1, "doc_category": 1}))
    if docs_missing_cat:
        logger.info("target_found", count=len(docs_missing_cat), target="law_documents_v1_categories")
        cat_ops = []
        for doc in docs_missing_cat:
            cid = resolve_id(local_categories, "doc_category", doc.get("doc_category"), "category_id")
            if cid:
                cat_ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"category_id": cid}}))
        if cat_ops:
            res = law_docs_coll.bulk_write(cat_ops)
            logger.info("replenished_category_ids", count=res.modified_count, target="law_documents_v1")

    # 2. Fill missing type_id
    type_query = {"$or": [{"type_id": {"$exists": False}}, {"type_id": {"$in": ["", None]}}]}
    docs_missing_type = list(law_docs_coll.find(type_query, {"doc_id": 1}))
    if docs_missing_type:
        logger.info("target_found", count=len(docs_missing_type), target="law_documents_v1_types")
        type_ops = []
        for doc in docs_missing_type:
            raw_doc = get_raw_doc(doc["doc_id"])
            if raw_doc and raw_doc.get("doc_type"):
                tid = resolve_id(local_doc_types, "doc_type_name", raw_doc["doc_type"], "type_id")
                if tid:
                    type_ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"type_id": tid}}))
        if type_ops:
            res = law_docs_coll.bulk_write(type_ops)
            logger.info("replenished_type_ids", count=res.modified_count, target="law_documents_v1")

    # 3. Fill missing agency_ids
    agency_query = {"$or": [{"agency_ids": {"$exists": False}}, {"agency_ids": []}, {"agency_ids": None}, {"agency_ids": [""]}]}
    docs_missing_agency = list(law_docs_coll.find(agency_query, {"doc_id": 1}))
    if docs_missing_agency:
        logger.info("target_found", count=len(docs_missing_agency), target="law_documents_v1_agencies")
        agency_ops = []
        for doc in docs_missing_agency:
            raw_doc = get_raw_doc(doc["doc_id"])
            if raw_doc:
                flat_ids = [a["id"] for a in raw_doc.get("issue_agencies", []) if a.get("id")]
                if flat_ids:
                    agency_ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"agency_ids": flat_ids}}))
        if agency_ops:
            res = law_docs_coll.bulk_write(agency_ops)
            logger.info("replenished_agency_ids", count=res.modified_count, target="law_documents_v1")

    # 4. Fill missing storage_id
    storage_query = {"$or": [{"storage_id": {"$exists": False}}, {"storage_id": {"$in": ["", None]}}]}
    docs_missing_storage = list(law_docs_coll.find(storage_query, {"doc_id": 1}))
    if docs_missing_storage:
        logger.info("target_found", count=len(docs_missing_storage), target="law_documents_v1_storage")
        storage_ops = []
        for doc in docs_missing_storage:
            s_record = storage_coll.find_one({"doc_id": str(doc["doc_id"])}, {"storage_id": 1})
            if s_record:
                storage_ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"storage_id": s_record["storage_id"]}}))
        if storage_ops:
            res = law_docs_coll.bulk_write(storage_ops)
            logger.info("replenished_storage_ids", count=res.modified_count, target="law_documents_v1")

    # 5. Flip status_in_system to "IN" for docs that now have a storage_id
    status_ops = []
    docs_with_storage = list(law_docs_coll.find(
        {"storage_id": {"$exists": True, "$nin": ["", None]}, "status_in_system": {"$ne": "IN"}},
        {"_id": 1}
    ))
    for doc in docs_with_storage:
        status_ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"status_in_system": "IN"}}))
    if status_ops:
        res = law_docs_coll.bulk_write(status_ops)
        logger.info("updated_status_in_system", count=res.modified_count, target="law_documents_v1")
    else:
        logger.info("no_status_updates_needed", target="law_documents_v1")

if __name__ == "__main__":
    replenish_ids()
    logger.info("replenishment_completed")
