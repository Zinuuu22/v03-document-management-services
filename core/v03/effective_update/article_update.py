from core.common.mongo.client import get_mongo_client
import os
import sys
import time
import re
import unicodedata
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
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
law_references_article_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_ARTICLE_COLLECTION_NAME]


def update_article_effective_status_daily(status: str = "Hết hiệu lực") -> List[Dict]:
    """
    Update article-level effective status by date based on article_expiry_date.
    
    Note: Articles from expired documents are handled by update_effective_status_daily().
    This function only updates articles with their own expiry date.
    
    Args:
        status (str): The status label (e.g., "Hết hiệu lực") - will be converted to UUID
    
    Returns:
        List[Dict]: List of results containing article IDs, expiry dates, and update status
    """
    # Convert status label to UUID
    status_id = EFFECTIVE_STATUS_MAP.get(status, status)
    results = []
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(hour=0, minute=0, second=0, microsecond=0)
    
    try:
        logger.info("update_article_status_started", action="update_article_effective_status_daily", date=str(today.date()))

        # Step 1: Find articles to update based on their own expiry date
        start_time = time.time()
        query = {
            "effective_status_id": {"$ne": status_id},
            "article_expiry_date": {"$ne": "", "$ne": None}
        }
        articles = law_articles_collection.find(query)
        logger.debug("executed_query", action="update_article_effective_status_daily", elapsed_seconds=round(time.time() - start_time, 2))

        # Step 2: Update article effective status by article_expiry_date
        start_time = time.time()
        update_count = 0

        for article in list(articles):
            article_id = article["article_id"]
            article_expiry_date = article.get("article_expiry_date", "")
            result = {
                "article_id": article_id,
                "article_expiry_date": article_expiry_date,
                "status": "No Update"
            }

            logger.debug("process_article", action="update_article_effective_status_daily", article_id=article_id, expiry_date=article_expiry_date)
            if article_expiry_date:
                try:
                    expiry_date = datetime.strptime(article_expiry_date, "%Y-%m-%d %H:%M:%S")
                    if expiry_date.date() < today.date():
                        logger.info("update_article_status", action="update_article_effective_status_daily", article_id=article_id)
                        result["status"] = "Update"
                        law_articles_collection.update_one(
                            {"_id": article["_id"]},
                            {"$set": {"effective_status_id": status_id}}
                        )
                        update_count += 1
                except ValueError as e:
                    result["status"] = f"Error: Invalid date format - {str(e)}"
                    logger.error("parse_date_failed", action="update_article_effective_status_daily", **{"error.code": "PARSE", "error.message": str(e)}, article_id=article_id, expiry_date=article_expiry_date, exc_info=True)

            results.append(result)

        logger.info("update_articles", action="update_article_effective_status_daily", count=update_count, status=status)
        logger.debug("update_timing", action="update_article_effective_status_daily", elapsed_seconds=round(time.time() - start_time, 2))

    except Exception as e:
        logger.error("update_article_failed", action="update_article_effective_status_daily", **{"error.code": "DB", "error.message": str(e)}, exc_info=True)

    return results


def normalize_relationship_type(relationship_type: str) -> str:
    """
    Chuẩn hóa relationship_type để xử lý các biến thể tiếng Việt có dấu/không dấu và tiếng Anh
    """
    if not relationship_type:
        return ""
    
    # Chuyển về lowercase và loại bỏ dấu tiếng Việt
    normalized = unicodedata.normalize('NFD', relationship_type.lower())
    normalized = re.sub(r'[\u0300-\u036f]', '', normalized)
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Map variants
    if normalized in ['sua doi', 'sua đoi', 'amend', 'amended', 'sửa đổi', "sửa đổi"]:
        return 'AMEND'
    elif normalized in ['thay the', 'thay the toan phan', 'replace', 'replaced', 'thay thế']:
        return 'REPLACE'
    elif normalized in ['huy bo', 'bai bo', 'repeal', 'repealed', 'huỷ bỏ', 'bãi bỏ']:
        return 'REPEAL'
    elif normalized in ['bo sung', 'supplement', 'supplemented', 'bổ sung']:
        return 'SUPPLEMENT'
    
    return relationship_type.upper()


def get_relationship_articles(art_id: str) -> Dict:
    # Get the relationship articles from law references collection art_id can be source_article_id or target_article_id
    relationship_articles = law_references_article_collection.find({"$or": [{"source_article_id": art_id}, {"target_article_id": art_id}]}, 
                                                                {"source_article_id": 1, "target_article_id": 1, "relationship_type": 1, "source_clause": 1, "source_point": 1,
                                                                 "target_clause": 1, "target_point": 1, "_id": 0})
    return list(relationship_articles)


def update_effective_status_now(art_id: str, status: str = "Hết hiệu lực", debug: bool = False) -> List[Dict]:
    """
    Update the effective status of a law article now.
    
    Args:
        art_id (str): The ID of the law article to update
        status (str): The status label (e.g., "Hết hiệu lực") - will be converted to UUID
    
    Returns:
        List[Dict]: List of results containing article IDs, effective dates, and update status
    """
    # Convert status label to UUID
    status_id = EFFECTIVE_STATUS_MAP.get(status, status)

    # Get the relationship articles from law references collection
    relationship_articles = get_relationship_articles(art_id)
    logger.info("found_relationships", action="update_effective_status_now", count=len(relationship_articles))

    commands = []
    updated_article_ids = set()

    for relationship_article in relationship_articles:
        logger.debug("process_relationship", action="update_effective_status_now", relationship=relationship_article)
        source_article_id = relationship_article["source_article_id"]
        target_article_id = relationship_article["target_article_id"]
        relationship_type = relationship_article["relationship_type"]
        logger.debug("relationship_ids", action="update_effective_status_now", source_id=source_article_id, target_id=target_article_id, ref_type=relationship_type)        
        source_article = law_articles_collection.find_one({"article_id": source_article_id})
        target_article = law_articles_collection.find_one({"article_id": target_article_id})

        normalized_ref_type = normalize_relationship_type(relationship_type)
        clause = relationship_article.get("source_clause") or relationship_article.get("target_clause")
        point = relationship_article.get("source_point") or relationship_article.get("target_point")
        
        logger.debug("relationship_fields", action="update_effective_status_now", ref_type=normalized_ref_type, clause=clause, point=point, source_id=source_article_id, target_id=target_article_id) 

        command = None
        
        # Xử lý logic theo relationship_type đã chuẩn hóa
        if str(source_article_id) == art_id:
            # Article hiện tại là source
            if normalized_ref_type == "AMEND":
                # Sửa đổi - set to expired status
                new_status = status_id
                logger.info("detected_amend", action="update_effective_status_now", article_id=target_article_id, clause=clause, point=point, status=status)
                
            elif normalized_ref_type == "REPLACE":
                # Thay thế (toàn phần) - Hết hiệu lực toàn bộ
                new_status = status_id
                logger.info("detect_replace", action="update_effective_status_now", article_id=target_article_id, status=status)
                
            elif normalized_ref_type == "REPEAL":
                # Hủy bỏ - Hết hiệu lực toàn bộ
                new_status = status_id
                logger.info("detect_repeal", action="update_effective_status_now", article_id=target_article_id, status=status)
                
            elif normalized_ref_type == "SUPPLEMENT":
                logger.info("detect_supplement", action="update_effective_status_now", article_id=target_article_id)
                continue
            else:
                logger.debug("unknown_relationship_type", action="update_effective_status_now", original=relationship_type, normalized=normalized_ref_type)
                continue
                
            # Cập nhật target article
            source_effective_date = source_article.get("article_effective_date") if source_article else None
            target_expire_date = target_article.get("article_expiry_date") if target_article else None

            logger.debug("compare_date", action="update_effective_status_now", target_expire=target_expire_date, source_effective=source_effective_date)
            if source_effective_date and target_expire_date is None:
                target_expire_date = source_effective_date
            
            filter_query = {"article_id": target_article_id}
            if target_article_id not in updated_article_ids:  # Kiểm tra trùng lặp
                update_article = {"$set": {"effective_status_id": new_status, "article_expiry_date": target_expire_date, "source_effective_date": source_effective_date}}
                command = UpdateOne(filter_query, update_article, upsert=False)
                updated_article_ids.add(target_article_id)

        elif str(target_article_id) == art_id:
            if normalized_ref_type == "AMEND":
                # Sửa đổi - set to expired status
                new_status = status_id
                logger.info("detect_target_amend", action="update_effective_status_now", article_id=target_article_id, clause=clause, point=point, status=status)
                
            elif normalized_ref_type == "REPLACE":
                new_status = status_id
                logger.info("detect_target_replace", action="update_effective_status_now", article_id=target_article_id, status=status)
                
            elif normalized_ref_type == "REPEAL":
                new_status = status_id
                logger.info("detect_target_repeal", action="update_effective_status_now", article_id=target_article_id, status=status)
                
            elif normalized_ref_type == "SUPPLEMENT":
                logger.info("detect_target_supplement", action="update_effective_status_now", article_id=target_article_id)
                continue
            else:
                logger.debug("unknown_relationship_type", action="update_effective_status_now", original=relationship_type, normalized=normalized_ref_type)
                continue
            
            source_effective_date = source_article.get("article_effective_date") if source_article else None
            target_expire_date = target_article.get("article_expiry_date") if target_article else None
            logger.debug("compare_target_date", action="update_effective_status_now", target_expire=target_expire_date, source_effective=source_effective_date)
            if source_effective_date and target_expire_date is None:
                target_expire_date = source_effective_date

            logger.debug("set_target_expire_date", action="update_effective_status_now", target_expire=target_expire_date)        
            filter_query = {"article_id": target_article_id}
            if target_article_id not in updated_article_ids:
                update_article = {"$set": {"effective_status_id": new_status, "article_expiry_date": target_expire_date, "source_effective_date": source_effective_date}}
                command = UpdateOne(filter_query, update_article, upsert=False)
                updated_article_ids.add(target_article_id)

        if command is not None:
            commands.append(command)
            logger.debug("create_command", action="update_effective_status_now", command_type="UpdateOne")

    logger.debug("prepare_commands", action="update_effective_status_now", command_count=len(commands))
    if len(commands) > 0:
        if not debug:
            law_articles_collection.bulk_write(commands, ordered=False)
        logger.info("update_articles_status", action="update_effective_status_now", count=len(commands), status=status)
    else:
        logger.info("update_no_article", action="update_effective_status_now")
    return commands



if __name__ == "__main__":    
    # Update the effective status of law articles now.
    import csv
    art_id = "9c2d7b55-0c8e-4d7e-9a1b-4a3f2e1b0003"
    commands = update_effective_status_now(art_id, debug=True)
    
    # Save commands to csv file
    final_commands = []    
    for command in commands:        
        # Get status from command (now uses UUID)
        status_id = command._doc.get('$set', {}).get('effective_status_id', '')
            
        # Extract filter and update from UpdateOne object
        final_commands.append({
            'filter': command._filter, 
            'update': command._doc,
            'article_id': command._filter.get('article_id', ''),
            'effective_status_id': status_id,
            'expiry_date': command._doc.get('$set', {}).get('article_expiry_date', '')
        })
    
    logger.info("article_update_count", total=len(final_commands))
    
    if final_commands:
        # Write to file        
        with open("update_effective_status.csv", "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = final_commands[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(final_commands)
        logger.info("results_saved", filename="update_effective_status.csv")
    else:
        logger.info("no_commands_to_save")
