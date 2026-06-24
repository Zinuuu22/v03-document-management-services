from core.common.mongo.client import get_mongo_client
import structlog
import os
import sys
import uuid
from datetime import datetime
from typing import Dict, Any
from flask_restful import Resource
from flask import request
from pymongo import MongoClient
from pyvi import ViUtils

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from services.api import api
from services.api.utils import make_response
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from structlog.contextvars import bind_contextvars
import time
logger = structlog.get_logger()


client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
keywords_collection = db[MongoDBCollectionConfig.LAW_KEYWORD_COLLECTION_NAME]


def vi_sort_key(text):
    if not isinstance(text, str):  # xử lý None, float NaN, int, ...
        text = "" if not text else str(text)
    text = text.lower()
    text = ViUtils.remove_accents(text)
    return text


class GetKeywordsAPI(Resource):
    def get(self):
        bind_contextvars(task="GetKeywordsAPI")
        start_t = time.time()
        try:
            keywords = list(keywords_collection.find())
            keywords = sorted(keywords, key=lambda x: vi_sort_key(x.get("keyword_name", "")))
            final_keywords = []
            for keyword in keywords:
                final_keywords.append({
                    "code": keyword["keyword_id"],
                    "name": keyword["keyword_name"],
                    "created_by": keyword["created_by"],
                    "created_date": keyword.get("created_at", ""),
                    "last_modified": keyword.get("last_modified_at", ""),
                    "status": keyword["status"],
                    "text": keyword.get("__text", "")
                })
            
            logger.info("get_keywords_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(final_keywords))
            return make_response(data=final_keywords, code=0, message="Success"), 200
        except Exception as e:
            logger.error("get_keywords_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


api.add_resource(GetKeywordsAPI, '/keywords/get')

