from core.common.mongo.client import get_mongo_client
import re
import json
import time
import os
import sys
import structlog
from pymongo import MongoClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.v03.metadata_extractor.extractor import extract_metadata
from core.v03.relationship_extractor.utils import extract_brief, mapping_document
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

# ===========================================================
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
document_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
tree_collection = db[MongoDBCollectionConfig.LAW_TREE_COLLECTION_NAME]
tree_component_collection = db[MongoDBCollectionConfig.LAW_TREE_COMPONENT_COLLECTION_NAME]
keywords_collection = db[MongoDBCollectionConfig.LAW_KEYWORD_COLLECTION_NAME]


def extract_laws(content):
    # Regex đơn giản: khớp từ "Luật" đến dấu chấm phẩy
    pattern = re.compile(r"Luật[^;]+", re.UNICODE)
    matches = pattern.findall(content)
    return matches


def get_keywords_from_base(content):    
    # Bước 1: Trích xuất metadata
    metadata_names = ['document_name', 
                    'document_code', 
                    'document_type',]

    metadata = extract_metadata(content=content, metadata_names=metadata_names)
    logger.info("get_keywords_from_base", metadata=metadata)


    # Bước 2: Trích xuất các keywords
    brief_content = extract_brief(content)
    matches = extract_laws(brief_content)
    logger.info("get_keywords_from_base", match_count=len(matches))    

    keywords = set()
    for match in matches:
        document = mapping_document(match)
        if document:
            # logger.info(f"Document: {document[0]['_source']}")
            doc_id = document[0]['_source']['code']

            document_in_db = document_collection.find_one({"doc_id": doc_id})
            if document_in_db:
                # logger.info(f"Document in DB: {document_in_db}")
                for keyword_id in document_in_db['keyword_ids']:
                    keyword = keywords_collection.find_one({'keyword_id': keyword_id})
                    if keyword:
                        keywords.add(keyword['keyword_name'])
    return keywords
