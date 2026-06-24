from core.common.mongo.client import get_mongo_client
import structlog
import sys
import uuid
import os
from flask_restful import Resource, reqparse
from bson import ObjectId
from pymongo import MongoClient
from datetime import datetime
from typing import Dict, Any
from pymongo.errors import PyMongoError
from pyvi import ViUtils

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from services.api.utils.response import make_response
from services.api import api
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from structlog.contextvars import bind_contextvars
import time
logger = structlog.get_logger()



# Connect MongoDB
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
document_industry_sector_collection = db[MongoDBCollectionConfig.LAW_INDUSTRY_SECTORS_COLLECTION_NAME]


def vi_sort_key(text):
    text = text.lower()
    text = ViUtils.remove_accents(text)
    return text

class ListIndustrySectorAPI(Resource):
    """API for listing all industry sector records"""
    
    def get(self):
        bind_contextvars(task="ListIndustrySectorAPI")
        start_t = time.time()
        try:
            industry_sectors = list(document_industry_sector_collection.find())
            industry_sectors = sorted(industry_sectors, key=lambda x: vi_sort_key(x.get("industry_sector_name", "")))
            result = []
            for doc_industry_sector in industry_sectors:
                doc_industry_sector['_id'] = str(doc_industry_sector['_id'])
                result.append({
                    "code": doc_industry_sector.get("industry_sector_id", ""),
                    "name": doc_industry_sector.get("industry_sector_name", ""),
                    "createdBy": doc_industry_sector.get("created_by", "system"),
                    "createdDate": doc_industry_sector.get("created_at", "").isoformat() if isinstance(doc_industry_sector.get("created_at"), datetime) else doc_industry_sector.get("created_at", ""),
                    "lastModifiedBy": doc_industry_sector.get("last_modified_by", "system"),
                    "lastModified": doc_industry_sector.get("last_modified_at", "").isoformat() if isinstance(doc_industry_sector.get("last_modified_at"), datetime) else doc_industry_sector.get("last_modified_at", ""),
                    "status": doc_industry_sector.get("status", "")
                })
            
            logger.info("get_list_industry_sector_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(result))
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("get_list_industry_sector_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


api.add_resource(ListIndustrySectorAPI, '/industry-sector/get')