from core.common.mongo.client import get_mongo_client
import structlog
import os
import sys
import json
from datetime import datetime
from typing import Dict, Generator
from flask import request, Response
from flask_restful import Resource
from pymongo import MongoClient
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig
from services.api import api
from services.api.utils import make_response
from structlog.contextvars import bind_contextvars
import time
logger = structlog.get_logger()


# ======================= MongoDB =======================
client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
law_process_manage_collection = db[MongoDBCollectionConfig.LAW_PROCESS_MANAGE_COLLECTION_NAME]

VALID_STATUS = ["DO", "STOP"]

# =====================================================
# API 1: UPSERT (CREATE / UPDATE)
# =====================================================
class LawProcessManageUpsertAPI(Resource):
    """
    Create or update law process manage record
    """

    def post(self):
        bind_contextvars(task="LawProcessManageUpsertAPI")
        start_t = time.time()
        try:
            body = request.get_json()
            if not body:
                logger.error("upsert_law_process_manage_failed", action="post", **{"error.code": "400-VAL", "error.message": "No JSON body provided", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(None, '400', 'No JSON body provided'), 400

            app_request_id = body.get('appRequestId')
            status = body.get('status')

            if not app_request_id or not status:
                logger.error("upsert_law_process_manage_failed", action="post", **{"error.code": "400-VAL", "error.message": "appRequestId and status are required", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    None, '400',
                    'appRequestId and status are required'
                ), 400
            if status not in VALID_STATUS:
                logger.error("upsert_law_process_manage_failed", action="post", **{"error.code": "400-VAL", "error.message": "status is invalid", "event.duration": time.time()-start_t, "event.status": "failure"}, status=status)
                return make_response(
                    None, '400',
                    'status is invalid'
                ), 400

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = ""

            law_process_manage_collection.update_one(
                {'app_request_id': app_request_id},
                {
                    '$set': {
                        'app_request_id': app_request_id,
                        'status': status,
                        'last_modified_at': now,
                        'last_modified_by': current_user
                    },
                    '$setOnInsert': {
                        'created_at': now,
                        'created_by': current_user
                    }
                },
                upsert=True
            )

            logger.info("upsert_law_process_manage_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, app_request_id=app_request_id, status=status)

            return make_response(
                None, '200',
                'Upsert law process manage successfully'
            ), 200

        except Exception as e:
            logger.error("upsert_law_process_manage_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(None, '500', f'Internal server error: {str(e)}')
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# =====================================================
# API 2: GET BY app_request_id
# =====================================================
class LawProcessManageGetAPI(Resource):
    """
    Get law process manage record by app_request_id
    """

    def get(self, appRequestId: str):
        bind_contextvars(task="LawProcessManageGetAPI")
        start_t = time.time()
        try:
            if not appRequestId:
                logger.error("get_law_process_manage_failed", action="get", **{"error.code": "400-VAL", "error.message": "appRequestId is required", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    None, '400',
                    'appRequestId is required'
                ), 400

            record = law_process_manage_collection.find_one(
                {'app_request_id': appRequestId},
                {'_id': 0}
            )

            if not record:
                logger.error("get_law_process_manage_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": "Record not found", "event.duration": time.time()-start_t, "event.status": "failure"}, appRequestId=appRequestId)
                return make_response(
                    None, '404',
                    'Record not found'
                ), 404

            logger.info("get_law_process_manage_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, appRequestId=appRequestId)
            return make_response(
                record, '200',
                'Get law process manage successfully'
            ), 200

        except Exception as e:
            logger.error("get_law_process_manage_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(None, '500', f'Internal server error: {str(e)}')
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500



# =====================================================
# REGISTER ROUTES
# =====================================================
api.add_resource(LawProcessManageUpsertAPI,"/law-process-manage/upsert")
api.add_resource(LawProcessManageGetAPI,"/law-process-manage/get/<string:appRequestId>")