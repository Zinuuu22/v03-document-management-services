from core.common.mongo.client import get_mongo_client
import structlog
import sys
import os
from pymongo import MongoClient, UpdateOne
from datasets import load_dataset
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

mongo_client = get_mongo_client()
test_db = mongo_client['hunghv'] #test db to insert data into
test_articles = test_db['law_articles_v1']#database to store articles

from core.v03.content_extractor.components.extract_segments import extract_segments

def extract_articles():
    """
    insert articles into test_articles
    """
    logger.info("Resetting collection: dropping law_articles...")
    test_articles.drop()
    
    logger.info("Starting extract_articles...")
    
    articles_to_insert = []
    
    for doc in test_db['raw_document_new_v1'].find():
        raw_text = doc.get("content", {}).get("raw_text", "")
        doc_id = str(doc.get("doc_id", ""))
        
        if not raw_text:
            continue
            
        # Call the existing API to get parsed segments
        segments = extract_segments(content=raw_text, document_code=doc_id)
        
        for segment in segments:
            article = {
                "article_id": segment["code"],
                "article_content": segment["article_content"],
                "article_effective_date": doc.get("effective_date", ""),
                "article_expiry_date": doc.get("updated_at", ""),
                "article_index": segment["index"],
                "article_title": segment["article_title"],
                "chapter": segment["chapter"],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "created_by": "system",
                "doc_id": segment["document_code"],
                "effective_status_id": doc.get("effective_status", "ACTIVE"),
                "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_by": "system",
                "part": segment["part"],
                "section": segment["section"],
                "start_article_index": segment["segment_index"],
                "sub_section": segment["sub_section"]
            }
            articles_to_insert.append(article)
            
        # Insert in batches to save memory
        if len(articles_to_insert) >= 1000:
            test_articles.insert_many(articles_to_insert)
            articles_to_insert = []
            
    # Insert remaining documents
    if articles_to_insert:
        test_articles.insert_many(articles_to_insert)
        
    logger.info("Finished extract_articles.")

def main():
    logger.info("Starting full migration process.")
    extract_articles()
    logger.info("Migration completed successfully.")

if __name__ == "__main__":
    main()

