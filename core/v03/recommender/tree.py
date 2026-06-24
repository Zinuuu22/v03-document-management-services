from core.common.elastic.client import get_elastic_client
from core.common.mongo.client import get_mongo_client
import re
import sys
import os
from pymongo import MongoClient
from elasticsearch import Elasticsearch
from datetime import datetime

# Xác định thư mục gốc dự án
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig, ElasticConfig

# Kết nối MongoDB
client = get_mongo_client()
elastic_client = get_elastic_client()


db = client[MigrateConfig.MIGRATE_CORE_DB]
documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
tree_collection = db[MongoDBCollectionConfig.LAW_TREE_COLLECTION_NAME]
tree_component_collection = db[MongoDBCollectionConfig.LAW_TREE_COMPONENT_COLLECTION_NAME]



def convert_datetime_to_iso(obj):
    """Recursively convert datetime objects to ISO format strings."""
    if isinstance(obj, dict):
        return {k: convert_datetime_to_iso(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_to_iso(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def get_tree_by_keywords(keywords: list[str], valid_tree_ids: list[str] = []):
    # Find all tree components that match the keywords without lower/upper case
    cursor = tree_component_collection.find({
        "subject_name": {
            "$in": [re.compile(keyword, re.IGNORECASE) for keyword in keywords]
        }
    })
    
    # Filter tree_components by valid_tree_ids
    tree_components = []
    if len(valid_tree_ids) > 0:
        for tree_component in cursor:
            tree_component.pop("_id", None)
            if tree_component["tree_id"] not in valid_tree_ids:
                tree_components.append(convert_datetime_to_iso(tree_component))
    else:
        for tree_component in cursor:
            tree_component.pop("_id", None)
            tree_components.append(convert_datetime_to_iso(tree_component))      
    logger.debug("filter_tree_components", action="get_tree_by_keywords", count=len(tree_components))
    return tree_components


if __name__ == "__main__":
    keywords = ['giao thông đường thuỷ nội địa',
 'Giao thông - Vận tải',
 'Cục Hàng hải Việt Nam',
 'Vận tải hành khách cố định',
 'Giấy chứng nhận đăng ký kinh doanh',
 'Hồ sơ',
 'Hệ thống dịch vụ công trực tuyến',
 'Chủ tàu',
 'Đại lý đại diện cho chủ tàu',
 'Bộ Giao thông vận tải',
 'Nghị định số 61/2018/NĐ-CP',
 'Bộ Tài chính']
    valid_tree_ids = []
    tree_components = get_tree_by_keywords(keywords=keywords, valid_tree_ids=valid_tree_ids)
    logger.info("tree_components_result", count=len(tree_components))