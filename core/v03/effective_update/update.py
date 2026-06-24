from core.common.mongo.client import get_mongo_client
import os
import sys
import time
from datetime import datetime
from typing import List, Dict
from pymongo import MongoClient
from pymongo import UpdateOne


# Constants and Configuration
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig

# Status mapping from Vietnamese labels to UUIDs
EFFECTIVE_STATUS_MAP = {
    "Không xác định": "b04750de-31f5-4266-b5c7-ac56c2bac946",
    "Hết hiệu lực": "a2e5eb7f-140b-43e9-9a9e-0b351466ae05",
    "Còn hiệu lực": "3969bc0a-a285-4a6d-9865-5b549cf88d20"
}

# Kết nối MongoDB
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
law_references_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_COLLECTION_NAME]


def update_effective_status_daily(status: str = "Hết hiệu lực") -> List[Dict]:
    """
    Update the effective status of law documents based on their effective date.
    Also cascades the status to all articles belonging to expired documents.
    
    Args:
        status (str): The status label (e.g., "Hết hiệu lực") - will be converted to UUID
    
    Returns:
        List[Dict]: List of results containing document IDs, article IDs, effective dates, and update status
    """
    # Convert status label to UUID
    status_id = EFFECTIVE_STATUS_MAP.get(status, status)
    results = []
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(hour=0, minute=0, second=0, microsecond=0)
    updated_doc_ids = []  # Track which documents were updated
    
    try:
        logger.info("update_status_started", action="update_effective_status_daily", date=str(today.date()))

        # Step 1: Find documents to update
        start_time = time.time()
        query = {
            "effective_status_id": {"$ne": status_id},
            "doc_expiry_date": {"$ne": ""}
        }
        docs = law_documents_collection.find(query)
        logger.debug("execute_query", action="update_effective_status_daily", elapsed_seconds=round(time.time() - start_time, 2))

        # Step 2: Update document effective status
        start_time = time.time()
        update_count = 0

        for doc in list(docs):            
            doc_id = doc["doc_id"]
            doc_expiry_date = doc.get("doc_expiry_date", "")
            result = {
                "doc_id": doc_id,
                "doc_expiry_date": doc_expiry_date,
                "status": "No Update"
            }

            logger.debug("process_document", action="update_effective_status_daily", doc_id=doc_id, expiry_date=doc_expiry_date)
            if doc_expiry_date:
                try:
                    expiry_date = datetime.strptime(doc_expiry_date, "%Y-%m-%d %H:%M:%S")
                    if expiry_date.date() < today.date():
                        logger.info("update_document_status", action="update_effective_status_daily", doc_id=doc_id)
                        result["status"] = "Update"
                        # Uncomment to enable actual updates
                        law_documents_collection.update_one(
                            {"_id": doc["_id"]},
                            {"$set": {"effective_status_id": status_id}}
                        )
                        update_count += 1
                        updated_doc_ids.append(doc_id)  # Track updated doc_id
                except ValueError as e:
                    result["status"] = f"Error: Invalid date format - {str(e)}"
                    logger.error("invalid_date_format", action="update_effective_status_daily", **{"error.code": "PARSE", "error.message": str(e)}, doc_id=doc_id, expiry_date=doc_expiry_date, exc_info=True)

            results.append(result)

        logger.info("update_documents", action="update_effective_status_daily", count=update_count, status=status)
        logger.debug("update_timing", action="update_effective_status_daily", elapsed_seconds=round(time.time() - start_time, 2))

        # Step 3: Cascade update articles from newly expired documents
        if updated_doc_ids:
            logger.info("update_cascade_started", action="update_effective_status_daily", expired_doc_count=len(updated_doc_ids))
            start_time = time.time()
            cascade_update_count = 0

            # Find articles that belong to newly expired documents
            articles_from_expired_docs_query = {
                "doc_id": {"$in": updated_doc_ids},
                "effective_status_id": {"$ne": status_id}
            }
            articles_from_expired_docs = law_articles_collection.find(articles_from_expired_docs_query)

            for article in list(articles_from_expired_docs):
                article_id = article["article_id"]
                doc_id = article.get("doc_id", "")
                result = {
                    "article_id": article_id,
                    "doc_id": doc_id,
                    "reason": "Document expired",
                    "status": "Inactive"
                }

                logger.debug("update_article_cascade", action="update_effective_status_daily", article_id=article_id, doc_id=doc_id)
                law_articles_collection.update_one(
                    {"_id": article["_id"]},
                    {"$set": {"effective_status_id": status_id}}
                )
                cascade_update_count += 1
                results.append(result)

            logger.info("update_cascade_completed", action="update_effective_status_daily", article_count=cascade_update_count, status=status)
            logger.debug("cascade_timing", action="update_effective_status_daily", elapsed_seconds=round(time.time() - start_time, 2))
        else:
            logger.info("no_cascade_update_needed", action="update_effective_status_daily")

    except Exception as e:
        logger.error("update_failed", action="update_effective_status_daily", **{"error.code": "DB", "error.message": str(e)}, exc_info=True)

    return results


def get_relationship_documents(doc_id: str) -> Dict:
    # Get the relationship documents from law references collection doc_id can be source_id or target_id
    relationship_documents = law_references_collection.find({"$or": [{"source_id": doc_id}, {"target_id": doc_id}]}, 
                                                                {"source_id": 1, "target_id": 1, "reference_type": 1})
    return list(relationship_documents)


def update_effective_status_now(doc_id: str, status: str = "Hết hiệu lực", debug: bool = False) -> List[Dict]:
    """
    Update the effective status of a law document now.
    
    Args:
        doc_id (str): The ID of the law document to update
        status (str): The status label (e.g., "Hết hiệu lực") - will be converted to UUID
    
    Returns:
        List[Dict]: List of results containing document IDs, effective dates, and update status
    """
    # Convert status label to UUID
    status_id = EFFECTIVE_STATUS_MAP.get(status, status)

    # Get the relationship documents from law references collection
    relationship_documents = get_relationship_documents(doc_id)
    logger.info("found_relationship_documents", action="update_effective_status_now", count=len(relationship_documents))

    
    update_doc_ids = set()
    commands = []
    # Update the effective status of the relationship documents
    for relationship_document in relationship_documents:
        logger.debug("process_relationship_document", action="update_effective_status_now", relationship=relationship_document)
        source_id = relationship_document["source_id"]
        target_id = relationship_document["target_id"]
        reference_type = relationship_document["reference_type"]
        logger.debug("relationship_ids", action="update_effective_status_now", source_id=source_id, target_id=target_id, ref_type=reference_type)        
        
        # Find source and target document        
        source_document = law_documents_collection.find_one({"doc_id": source_id})
        target_document = law_documents_collection.find_one({"doc_id": target_id})

        
        command = None
        # If current doc replaces another, update the counterpart
        if str(source_id) == doc_id and reference_type == "REPLACED":
            source_effective_date = source_document.get("doc_effective_date", None)
            target_expire_date = target_document.get("doc_expiry_date", None)
            if source_effective_date:
                if target_expire_date is None :
                    target_expire_date = source_effective_date 
                    
            filter_query = {"doc_id": target_id}
            update_doc = {"$set": {"effective_status_id": status_id, "doc_expiry_date": target_expire_date}}
            if target_id not in update_doc_ids:             
                update_doc_ids.add(target_id)
                command = UpdateOne(filter_query, update_doc, upsert=False)

        # If current doc is replaced by another, update the counterpart
        elif str(target_id) == doc_id and reference_type == "REPLACE":
            target_effective_date = target_document.get("doc_effective_date", None)
            source_expire_date = source_document.get("doc_expiry_date", None)
            if target_effective_date:
                if source_expire_date is None :
                    source_expire_date = target_effective_date  
            
            filter_query = {"doc_id": source_id}
            update_doc = {"$set": {"effective_status_id": status_id, "doc_expiry_date": source_expire_date}}            
            if source_id not in update_doc_ids:             
                update_doc_ids.add(source_id)            
                command = UpdateOne(filter_query, update_doc, upsert=False)
            
        if command is not None:
            commands.append(command)
            logger.debug("create_command", action="update_effective_status_now", command_type="UpdateOne")

    if len(commands) > 0:
        if not debug:
            law_documents_collection.bulk_write(commands, ordered=False)
        logger.info("documents_status", action="update_effective_status_now", count=len(commands), status=status)
    else:
        logger.info("no_documents_to_update", action="update_effective_status_now", status=status)
    return commands



if __name__ == "__main__":    
    # import csv    
    # # Update the effective status of law documents based on their effective date.
    # results = update_effective_status_daily()    
    # # Save the results to a CSV file
    # with open("update_effective_status.csv", "w", newline="", encoding="utf-8") as csvfile:
    #     fieldnames = results[0].keys()
    #     writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    #     writer.writeheader()
    #     writer.writerows(results)


    # Update the effective status of law documents now.
    import csv
    doc_id = "587691"
    commands = update_effective_status_now(doc_id, debug=True)
    logger.info("update_completed", command_count=len(commands))

    # Save commands to csv file
    for command in commands:
        doc_id = command._filter["doc_id"]
        status = command._doc["$set"]["effective_status_id"]
        with open("update_effective_status_now.csv", "a", encoding="utf-8") as textfile:
            textfile.write(f"doc_id: {doc_id}, status: {status}\n")
    logger.info("commands_saved", filename="update_effective_status_now.txt")