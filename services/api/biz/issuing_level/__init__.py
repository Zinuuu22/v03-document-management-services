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
issuing_level_collection = db[MongoDBCollectionConfig.LAW_ISSUING_LEVEL_COLLECTION_NAME]


class GetIssuingLevelAPI(Resource):
    def get(self):
        bind_contextvars(task="GetIssuingLevelAPI")
        start_t = time.time()
        try:
            issuing_levels = list(issuing_level_collection.find())
            final_issuing_levels = []
            for issuing_level in issuing_levels:
                final_issuing_levels.append({
                    "code": issuing_level["issuing_level_id"],
                    "name": issuing_level["issuing_level_name"],
                    "created_by": issuing_level["created_by"],
                    "created_date": issuing_level["created_at"],
                    "last_modified": issuing_level["last_modified_at"],
                    "status": issuing_level["status"],
                    "text": issuing_level.get("__text", "")
                })
            
            logger.info("get_issuing_level_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(final_issuing_levels))
            return make_response(data=final_issuing_levels, code=0, message="Success"), 200
        except Exception as e:
            logger.error("get_issuing_level_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


api.add_resource(GetIssuingLevelAPI, '/issuing-level/get')


