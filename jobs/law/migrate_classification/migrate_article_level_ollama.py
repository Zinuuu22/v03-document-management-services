from core.common.mongo.client import get_mongo_client
import os
import sys
import time
from datetime import datetime
import structlog
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.v03.segments_classifier import classify_segment
from jobs.law.migrate_classification import post_process_classify
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

MAX_WORKERS = 3

client = get_mongo_client()

core_db = client[MigrateConfig.MIGRATE_CORE_DB]
document_collection = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]                
articles_collection = core_db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
articles_class_collection = core_db[MongoDBCollectionConfig.LAW_ARTICLE_CLASS_COLLECTION_NAME]


def process_article(article: dict, articles_class_collection) -> None:
    """Process and classify a single article.

    Args:
        article (dict): Article document from MongoDB.
        articles_class_collection: MongoDB collection for articles classification.
        articles_collection: MongoDB collection for articles.

    Raises:
        Exception: If classification fails.
    """
    article_id = article.get('article_id', 'Unknown')
    is_classification = article.get("is_classification", "FAIL")
    if is_classification != "FAIL":
        return
    try:          
        article_title = article.get('article_title', '').strip()
        article_content = article.get('article_content', '').strip()
        content = f"{article_title}\n{article_content}".strip().replace('\n\n', '\n')
        if not content:
            logger.warning(action="process_article", event="article_empty_content", article_id=article_id)
            articles_collection.update_one(
                {"_id": article["_id"]},
                {"$set": {"is_classification": "FAIL"}}
            )
            return

        # Classify article
        logger.debug(action="process_article", event="article_classification_started", article_id=article_id)
        classification = classify_segment(segment=content)
        pp_classification = post_process_classify(classification)
        
        articles_class_collection.insert_one({
            'article_id': article_id,
            'article_title': article_title,
            'article_content': article_content,
            'doc_id': article.get('doc_id', 'Unknown'),
            'content': content,             
            'class': pp_classification,             
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'version': MigrateConfig.MIGRATE_CLASSIFY_ARTICLE_LEVEL_OLLAMA
        })
        
        articles_collection.update_one(
            {"_id": article["_id"]},
            {"$set": {"is_classification": "SUCCESS"}}
        )        
        logger.info(action="process_article", event="article_classified", article_id=article_id)
    except Exception as e:
        logger.error(action="process_article", event="article_classification_failed", **{"error.code": "LLM", "error.message": str(e)}, article_id=article_id, exc_info=True)
        articles_collection.update_one(
            {"_id": article["_id"]},
            {"$set": {"is_classification": "FAIL"}}
        )
        raise


def migrate_classification(document_codes: list[str] = []) -> None:
    """Migrate classification for articles in law_articles using multi-threading."""
    processed_count = 0
    error_count = 0
    try:
        logger.info(action="migrate_classification", event="migration_started")
        if document_codes:
            doc_ids = []
            for document_code in document_codes:
                documents = list(document_collection.find({'doc_code': document_code, 'doc_effective_status': "Còn hiệu lực"}, 
                                                            {'_id': 1, 'doc_id': 1}))
                if documents:
                    for document in documents:
                        doc_ids.append(document['doc_id'])
                        logger.info(action="migrate_classification", event="document_found", document_code=document_code, doc_id=document['doc_id'])
                else:
                    logger.error(action="migrate_classification", event="document_not_found", **{"error.code": "DB", "error.message": "Document not found"}, document_code=document_code)                    
            articles = list(articles_collection.find({'doc_id': {'$in': doc_ids}}))     
        else:
            articles = list(articles_collection.find({}))
        logger.info(action="migrate_classification", event="articles_to_classify_found", count=len(articles))
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(process_article, article, articles_class_collection)
                for article in articles
            ]
            for future in futures:
                try:
                    future.result()
                    processed_count += 1
                except Exception as e:
                    error_count += 1
                    continue
        logger.info(action="migrate_classification", event="migration_completed", processed=processed_count, errors=error_count)
    except Exception as e:
        logger.error(action="migrate_classification", event="migration_failed", **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
        raise
        

if __name__ == "__main__":
    """Run the article classification migration process."""
    try:
        logger.info(action="main", event="article_classification_migration_started")
        start_time = time.time()
        migrate_classification()
        logger.info(action="main", event="article_classification_migration_completed", duration=time.time() - start_time)
    except Exception as e:
        logger.error(action="main", event="article_classification_migration_failed", **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
        raise
