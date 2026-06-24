from core.common.mongo.client import get_mongo_client

import os
from dotenv import load_dotenv
load_dotenv() # MUST be loaded before importing anything else

import structlog
import sys
from pymongo import MongoClient, UpdateOne
from datasets import load_dataset
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MinioConfig, MigrateConfig, MongoDBCollectionConfig
from logs.logger_conf import setup_logging
from core.v03.metadata_extractor.fields.extract_document_category import extract_document_category
from jobs.law.migrate_from_huggingface.utils.search_existing_records import search_record

setup_logging()
logger = structlog.get_logger()

mongo_client = get_mongo_client()
db = mongo_client['hunghv']
raw_documents = db['raw_document_new_v1']
law_documents = db['law_documents_v1']

core_db = mongo_client['v03_core_11032026']


raw_schema = {
    "doc_id": "str",  # Unique document identifier

    "content": {  # Nested object containing file + raw content
        "doc_file_path": "str",  # File name/path in MinIO (e.g., 08_2026_QD-UBND_m_695018.doc)
        "raw_text": "str",       # Extracted raw text content of the document
        "html": "str",           # HTML version of the document (empty if not available)
    },

    "created_at": "str",  # Document creation date (YYYY-MM-DD)

    "doc_code": "str",  # Official document code (e.g., 08/2026/QĐ-UBND)

    "doc_title": "str",  # Title of the legal document

    "doc_type": "str",  # Type of document (e.g., Quyết định)

    "effective_date": "str",  # Date the document becomes effective

    "effective_status": "str",  # Legal status (e.g., Còn hiệu lực)

    "industry_sectors": [  # List of industry/domain classifications
        "str"  # Example: "Thể thao - Y tế"
    ],

    "issue_agencies": [  # List of issuing agencies
        {
            "name": "str",  # Name of the agency (e.g., Thành phố Hồ Chí Minh)
            "id": "str",    # Internal agency identifier
        }
    ],

    "issued_date": "str",  # Date the document was issued

    "issued_level": {  # Administrative level of issuing authority
        "name": "str",  # Level name (e.g., Địa Phương)
        "id": "str",    # Internal level identifier
    },

    "keywords": [  # Extracted keywords (can be empty)
        "str"
    ],

    "relationships": [  # Relationships to other documents (currently empty)
        "Any"
    ],

    "signers": [  # People who signed the document
        {
            "name": "str",  # Signer's name
            "id": "str",    # Internal signer identifier
        }
    ],

    "source": {  # Source system information
        "name": "str",  # Source name (e.g., tvpl-01042026)
        "id": "str",    # Source ID (empty in this case)
    },

    "updated_at": "str",  # Last update timestamp (empty if not updated)
}
new_doc_schema = {
    "doc_id": {
        "dtype": "str",  # Unique identifier of the document
    },
    "agency_ids": {
        "dtype": "list[str]",  # List of issuing agency IDs
    },
    "category_id": {
        "dtype": "str",  # Category classification ID of the document
    },
    "created_at": {
        "dtype": "str",  # Timestamp when the document was created (string format), make a now() function
    },
    "created_by": {
        "dtype": "str",  # User/system that created the document, default SYSTEM
    },
    "data_source": {
        "dtype": "str",  # Source of the data, make all tvpl-01042026
    },
    "doc_code": {
        "dtype": "str",  # Official legal document code (e.g., 48/2024/QĐ-UBND)
    },
    "doc_content": {
        "dtype": "str",  # Full textual content of the document
    },
    "doc_effective_date": {
        "dtype": "str",  # Effective date of the document (string format)
    },
    "doc_expiry_date": {
        "dtype": "str",  # Expiry date of the document (if any)
    },
    "doc_issue_date": {
        "dtype": "str",  # Date the document was officially issued
    },
    "doc_short_description": {
        "dtype": "str",  # Short summary/description of the document
    },
    "doc_title": {
        "dtype": "str",  # Title of the document
    },
    "effective_status_id": {
        "dtype": "str",  # Status ID indicating legal effectiveness
    },
    "industry_sector_ids": {
        "dtype": "list[str]",  # List of industry/sector classification IDs
    },
    "issuing_level_id": {
        "dtype": "str",  # Administrative level of issuing authority
    },
    "keyword_ids": {
        "dtype": "list[str]",  # List of keyword IDs associated with the document
    },
    "last_modified_at": {
        "dtype": "str",  # Last modification timestamp
    },
    "last_modified_by": {
        "dtype": "str",  # User who last modified the document
    },
    "position_ids": {
        "dtype": "list[str]",  # List of positions related to the document (e.g., roles) leave blank for now
    },
    "signer_ids": {
        "dtype": "list[str]",  # List of signer IDs of the document
    },
    "status_in_system": {
        "dtype": "str",  # Internal system status (e.g., IN, OUT), make all IN
    },
    "storage_id": {
        "dtype": "str",  # Reference ID to object stored in MinIO (file storage) get_storage_id
    },
    "tree_ids": {
        "dtype": "list[str]",  # Hierarchical classification IDs
    },
    "type_id": {
        "dtype": "str",  # Document type identifier
    },
}
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

def _transform_doc(doc: dict) -> dict:
    """Transform huggingface raw_document_new_v1 schema to law_documents schema."""
    
    # Extract agency_ids
    agency_ids = []
    for a in doc.get("issue_agencies", []):
        if isinstance(a, dict) and a.get("id"):
            agency_ids.append(a.get("id"))
            
    # Extract signer_ids
    signer_ids = []
    for s in doc.get("signers", []):
        if isinstance(s, dict) and s.get("id"):
            signer_ids.append(s.get("id"))
            
    # Extract storage_id via doc_id (more reliable than filename)
    doc_id = str(doc.get("doc_id", ""))
    storage_id = search_record(db['law_document_storage_v1'], "doc_id", doc_id, "storage_id") if doc_id else ""

    # Extract category via extract_document_category API
    doc_code = doc.get("doc_code", "")
    doc_type = doc.get("doc_type", "")
    category_res = extract_document_category(document_code=doc_code, document_type=doc_type)
    doc_category = category_res.get("document_category", "Văn bản Hành Chính")
    category_id = search_record(core_db['law_doc_category'], "doc_category", doc_category, "category_id")
    
    now_str = _now()

    return {
        "doc_id": str(doc.get("doc_id", "")),
        "agency_ids": agency_ids,
        "category_id": category_id,
        "doc_category": doc_category,
        "created_at": now_str,
        "created_by": "SYSTEM",
        "data_source": "tvpl-01042026",
        "doc_code": doc.get("doc_code", ""),
        "doc_content": doc.get("content", {}).get("raw_text", ""),
        "doc_effective_date": doc.get("effective_date", "") + " 00:00:00",
        "doc_expiry_date": doc.get("updated_at", ""), # Assuming updated_at represents expiry/effectless date as per step_1
        "doc_issue_date": doc.get("issued_date", "") + " 00:00:00",
        "doc_short_description": doc.get("doc_title", ""), # Fallback to title
        "doc_title": doc.get("doc_title", ""),
        "effective_status_id": search_record(core_db['law_effective_status'], "effective_status_name", doc.get("effective_status", "Không xác định"), "effective_status_id"),
        "industry_sector_ids": [
            search_record(core_db['law_industry_sectors'], "industry_sector_name", sector, "industry_sector_id")
            for sector in doc.get("industry_sectors", [])
        ],
        "issuing_level_id": doc.get("issued_level", {}).get("id", "") if isinstance(doc.get("issued_level"), dict) else "",
        "keyword_ids": doc.get("keywords", []),
        "last_modified_at": now_str,
        "last_modified_by": "SYSTEM",
        "position_ids": [],
        "signer_ids": signer_ids,
        "status_in_system": "OUT" if storage_id == "" else "IN",
        "storage_id": storage_id,
        "tree_ids": [], # Hierarchical classification IDs
        "type_id": search_record(core_db['law_doc_types'], "doc_type_name", doc.get("doc_type", ""), "type_id"),
    }

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process():
    # 0. Drop existing law documents collection to ensure a clean slate
    logger.info("Resetting collection: dropping law_documents...")
    law_documents.drop()
    
    BATCH_SIZE = 50
    
    # Query only documents that have an id
    query = {"doc_id": {"$exists": True}}
    total_docs = raw_documents.count_documents(query)
    
    logger.info("migration_started", total_docs=total_docs, batch_size=BATCH_SIZE)
    
    success_count = 0
    error_count = 0
    batch = []
    
    try:
        cursor = raw_documents.find(query, no_cursor_timeout=True)
        
        for doc in cursor:
            try:
                transformed_doc = _transform_doc(doc)
                
                # We use UpdateOne with upsert=True based on doc_id
                operation = UpdateOne(
                    {"doc_id": transformed_doc["doc_id"]},
                    {
                        "$set": {
                            k: v for k, v in transformed_doc.items()
                            if k not in ["created_at", "created_by"]
                        },                    
                        "$setOnInsert": {
                            "created_at": transformed_doc["created_at"],
                            "created_by": transformed_doc["created_by"]
                        }
                    },
                    upsert=True
                )
                batch.append(operation)
                
                if len(batch) >= BATCH_SIZE:
                    result = law_documents.bulk_write(batch, ordered=False)
                    success_count += result.upserted_count + result.modified_count
                    if result.upserted_count + result.modified_count < len(batch):
                        # Some docs might have been identical, no modification needed.
                        # We just count it as success for simplicity if no error was raised
                        success_count += len(batch) - (result.upserted_count + result.modified_count)
                        
                    logger.info("batch_indexed", success_count=success_count, remaining=total_docs - success_count)
                    batch = []
            except Exception as e:
                logger.error("doc_transform_failed", doc_id=doc.get("doc_id"), error=str(e))
                error_count += 1
                
        # Flush remaining
        if batch:
            try:
                 result = law_documents.bulk_write(batch, ordered=False)
                 success_count += result.upserted_count + result.modified_count
                 if result.upserted_count + result.modified_count < len(batch):
                        success_count += len(batch) - (result.upserted_count + result.modified_count)
            except Exception as e:
                 logger.error("final_batch_failed", error=str(e))
                 error_count += len(batch)
                 
    finally:
        cursor.close()
        
    logger.info("migration_completed", total_docs=total_docs, success_count=success_count, error_count=error_count)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate raw documents to law documents.")
    args = parser.parse_args()
    process()
