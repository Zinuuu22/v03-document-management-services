from core.common.mongo.client import get_mongo_client
import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

import pandas as pd
from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig
from pymongo import MongoClient


client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
# db1 = client['khiemdx']
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
law_agencies_collection = db[MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME]

from core.v03.law_authority_verifier.verify_authority import validate_agency_authority

def combine_title_content(title, content):
    return f"{title}\n{content}"


def check_authority():
    data = list(
        db1['test_cases_5_2'].aggregate([
            {"$match": {"agency_name": {"$ne": 'Chính phủ'}}},
            {"$project": {"_id": 0}}
        ])
    )
    for item in data:
        title = item.get('article_title', '')
        agency_name = item.get('expect_agency', '')
        content = item.get('article_content', '')
        combined_text = combine_title_content(title, content)
        result = validate_agency_authority(agency_name, combined_text)
        item['llm_result'] = result.get('result', '')
        item['reason'] = result.get('reason', '')
        db1['test_cases_5_2_result'].insert_one(item)

if __name__ == '__main__':
    check_authority()