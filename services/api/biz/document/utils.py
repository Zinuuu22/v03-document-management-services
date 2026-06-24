from core.common.mongo.client import get_mongo_client
import structlog
import os
import sys
import json
from typing import Dict, List
from pymongo import MongoClient
from pymongo.collection import Collection
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from services.api.utils.search import stream
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

# Khởi tạo kết nối MongoDB
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
law_references_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_COLLECTION_NAME]
law_doc_type_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_TYPE_COLLECTION_NAME]

def get_doc_type_map():
    return {
        item["type_id"]: item.get("doc_type_name", "")
        for item in law_doc_type_collection.find({})
    }

def enrich_stream(gen, total_count):
    doc_type_map = get_doc_type_map()
    for item in stream(gen, total_count):
        # logger.debug("stream_raw_item", raw=repr(item), type=type(item).__name__)
        try:
            item_decoded = item.decode("utf-8") if isinstance(item, bytes) else item
            
            # Nếu string có thể load thành JSON dictionary (tức là 1 hit của model)
            data = json.loads(item_decoded)
            
            if isinstance(data, dict) and "documentTypeCode" in data:
                doc_type_code = data.get("documentTypeCode")
                data["documentTypeName"] = doc_type_map.get(doc_type_code, "")
                enriched_item = json.dumps(data, ensure_ascii=False)
                yield enriched_item.encode("utf-8") if isinstance(item, bytes) else enriched_item
            else:
                yield item

        except json.JSONDecodeError:
            # Nếu nó là `b','` hoặc `b']}}'` hoặc `b'{"code": 0 ...'`, json.loads sẽ chết
            # Chúng ta KHÔNG LÀM GÌ, chỉ cần yield nó qua!
            yield item
            
        except Exception as e:
            logger.error("enrich_stream_failed", action="enrich_stream", **{"error.code": "STREAM", "error.message": str(e), "raw": repr(item)}, exc_info=True)
            yield item


def get_document_relationship(id_or_code: str, collection: Collection = law_references_collection) -> Dict[str, List[str]]:
    """
    Retrieve document relationships based on ID or code.

    Args:
        id_or_code (str): Document ID or code.
        collection (Collection, optional): MongoDB collection to query. Defaults to law_references_collection.

    Returns:
        Dict[str, List[str]]: Dictionary containing lists of related document IDs for each relationship type.
    """
    if not isinstance(id_or_code, str) or not id_or_code.strip():
        logger.warning("get_document_relationship_failed", action="get_document_relationship", **{"error.code": "VAL", "error.message": "Invalid input: id_or_code must be a non-empty string"}, id_or_code=id_or_code)
        return {}

    # Define relationship types as a tuple for immutability and slight memory optimization
    REFERENCE_TYPES = (
        "GUIDED", "CONSOLIDATING", "CORRECTED", "REPLACE",
        "REFERENTIAL", "BASIS", "CONTENT_CONNECTION",
        "AVOID", "AMENDED"
    )

    # Initialize result dictionary using dict comprehension
    result = {f"{ref_type.lower()}_documents": [] for ref_type in REFERENCE_TYPES}

    try:
        # Use aggregation pipeline for single query instead of multiple find().distinct() calls
        pipeline = [
            {"$match": {"source_id": id_or_code}},
            {"$group": {
                "_id": "$reference_type",
                "target_ids": {"$addToSet": "$target_id"}
            }}
        ]
        
        # Execute aggregation and populate results
        for doc in collection.aggregate(pipeline):
            ref_type = doc["_id"]
            if ref_type in REFERENCE_TYPES:
                result[f"{ref_type.lower()}_documents"] = doc["target_ids"]
                logger.info("get_document_relationship_matches_found", action="get_document_relationship", ref_type=ref_type, count=len(doc["target_ids"]), id_or_code=id_or_code)

        return result

    except Exception as e:
        logger.error("get_document_relationship_failed", action="get_document_relationship", **{"error.code": "DB", "error.message": str(e)}, id_or_code=id_or_code, exc_info=True)
        return {}

if __name__ == "__main__":
    result = get_doc_type_map()
    logger.debug("get_doc_type_map_success", action="get_doc_type_map", result=result)