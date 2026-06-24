from core.common.mongo.client import get_mongo_client
import structlog
import sys
import os
import uuid
from flask_restful import Resource, reqparse
from flask import request
from bson import ObjectId
from pymongo import MongoClient
from datetime import datetime
from typing import Dict, Any
from pymongo.errors import PyMongoError
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from services.api import api
from services.api.utils import make_response
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from structlog.contextvars import bind_contextvars
import time

logger = structlog.get_logger()



# Connect MongoDB
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_effective_status_collection = db[MongoDBCollectionConfig.LAW_EFFECTIVE_STATUS_COLLECTION_NAME]


def _format_decree_status(ds: dict) -> dict:
    """Format a decree status document for API response."""
    def format_datetime(dt_value):
        """Convert datetime to ISO format string, or return string as-is"""
        if isinstance(dt_value, datetime):
            return dt_value.isoformat()
        return dt_value if dt_value else ''
    
    return {
        'code': ds.get('effective_status_id', ''),
        'name': ds.get('effective_status_name', ''),
        'description': ds.get('description', ''),
        'status': ds.get('status', ''),
        'createdBy': ds.get('created_by', ''),
        'createdAt': format_datetime(ds.get('created_at')),
        'updatedBy': ds.get('last_modified_by', ''),
        'updatedAt': format_datetime(ds.get('last_modified_at'))
    }


class DecreeStatusDocumentAPI(Resource):    
    def get(self):
        page_str = request.args.get('page', '1')
        limit_str = request.args.get('limit', '10')
        search_term = request.args.get('search', '')
        sort_field = request.args.get('sort', '-createdDate')

        bind_contextvars(task="DecreeStatusDocumentAPI")
        start_t = time.time()
        try:
            page = int(page_str)
        except (ValueError, TypeError):
            logger.error("get_decree_statuses_failed", action="get", **{"error.code": "400-VAL", "error.message": f"Invalid value for 'page': '{page_str}'. Must be a valid integer.", "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(data=None, code=1000, message=f"Invalid value for 'page': '{page_str}'. Must be a valid integer."), 400

        try:
            limit = int(limit_str)
        except (ValueError, TypeError):
            logger.error("get_decree_statuses_failed", action="get", **{"error.code": "400-VAL", "error.message": f"Invalid value for 'limit': '{limit_str}'. Must be a valid integer.", "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(data=None, code=1000, message=f"Invalid value for 'limit': '{limit_str}'. Must be a valid integer."), 400

        page = max(1, page)
        limit = min(100, max(1, limit))

        try:
            query = {}
            if search_term:
                query['$or'] = [
                    {'effective_status_id': {'$regex': search_term, '$options': 'i'}},
                    {'effective_status_name': {'$regex': search_term, '$options': 'i'}}
                ]

            total = law_effective_status_collection.count_documents(query)

            sort_key = 'created_at'
            sort_direction = -1
            if sort_field:
                if sort_field.startswith('-'):
                    sort_direction = -1
                    field = sort_field[1:]
                else:
                    sort_direction = 1
                    field = sort_field

                if field == 'name':
                    sort_key = 'effective_status_name'
                elif field == 'code':
                    sort_key = 'effective_status_id'
                elif field in ['createdAt', 'created_at']:
                    sort_key = 'created_at'
                elif field in ['updatedAt', 'updated_at']:
                    sort_key = 'last_modified_at'

            skip = (page - 1) * limit
            cursor = (law_effective_status_collection.find(query)
                      .sort(sort_key, sort_direction)
                      .skip(skip)
                      .limit(limit))

            items = []
            for ds in cursor:
                items.append({
                    'code': ds.get('effective_status_id', ''),
                    'name': ds.get('effective_status_name', ''),
                    'description': ds.get('description', ''),
                    'status': ds.get('status', ''),
                    'createdBy': ds.get('created_by', ''),
                    'createdAt': ds.get('created_at', '').isoformat() if isinstance(ds.get('created_at'), datetime) else ds.get('created_at', ''),
                    'updatedBy': ds.get('last_modified_by', ''),
                    'updatedAt': ds.get('last_modified_at', '').isoformat() if isinstance(ds.get('last_modified_at'), datetime) else ds.get('last_modified_at', '')
                })

            total_pages = (total + limit - 1) // limit if total > 0 else 1
            response_data = {
                'items': items,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'totalPages': total_pages,
                    'hasNext': page < total_pages,
                    'hasPrev': page > 1
                }
            }

            logger.info("get_decree_statuses_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(items), page=page, limit=limit, search=search_term)
            logger.debug("get_decree_statuses", action="get", response_data=response_data, **{"event.duration": time.time()-start_t})
            return make_response(data=response_data, code=0, message="Success"), 200

        except PyMongoError as e:
            logger.error("get_decree_statuses_failed", action="get", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("get_decree_statuses_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetByIdDecreeStatusAPI(Resource):
    """API for getting decree status by ObjectId or decree_status_id"""
    
    def get(self, idOrCode):
        bind_contextvars(task="GetByIdDecreeStatusAPI")
        start_t = time.time()
        try:
            if ObjectId.is_valid(idOrCode):
                query = {'_id': ObjectId(idOrCode)}
            else:
                query = {'effective_status_id': idOrCode}

            decree_status = law_effective_status_collection.find_one(query)

            if not decree_status:
                logger.error("get_decree_status_by_id_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": f"Decree status with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message=f"Decree status with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            response_data = _format_decree_status(decree_status)
            logger.info("get_decree_status_by_id_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, id_or_code=idOrCode)
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("get_decree_status_by_id_failed", action="get", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("get_decree_status_by_id_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class CreateDecreeStatusAPI(Resource):
    """API for creating a new decree status record"""
    
    def post(self):
        bind_contextvars(task="CreateDecreeStatusAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str, required=True, location='json', help="Name is required")
        parser.add_argument('description', type=str, required=False, location='json', default='', help="Description is optional")
        parser.add_argument('status', type=str, required=False, choices=('ACTIVE', 'INACTIVE'), location='json', default='ACTIVE', help="Status is optional (ACTIVE or INACTIVE), defaults to ACTIVE")
        args = parser.parse_args()

        decree_status_name = args['name']
        description = args['description']
        status = args['status']

        if decree_status_name:
            decree_status_name = decree_status_name.strip()
            
        if description:
            description = description.strip()
        
        try:
            decree_status_id = str(uuid.uuid4())
            
            # Check for duplicate name (case-insensitive)
            existing = law_effective_status_collection.find_one({'effective_status_name': {
                '$regex': f'^{re.escape(decree_status_name)}$',
                '$options': 'i'
            }})

            if existing:
                logger.error("create_decree_status_failed", action="post", **{"error.code": "400-VAL", "error.message": f"Decree status with name {decree_status_name} already exists", "event.duration": time.time()-start_t, "event.status": "failure"}, decree_status_name=decree_status_name)
                response = make_response(data=None, code=2000, message=f"Decree status with name {decree_status_name} already exists")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = "system"
            
            decree_status = {
                "effective_status_id": decree_status_id,
                "effective_status_name": decree_status_name,
                "description": description,
                "status": status,
                "created_by": current_user,
                "created_at": current_time,
                "last_modified_by": current_user,
                "last_modified_at": current_time
            }
            
            result = law_effective_status_collection.insert_one(decree_status)
            logger.info("create_decree_status_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, decree_status_id=decree_status_id, inserted_id=str(result.inserted_id))
            
            response_data = _format_decree_status(decree_status)
            return make_response(data=response_data, code=0, message="Success"), 201
            
        except PyMongoError as e:
            logger.error("create_decree_status_failed", action="post", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("create_decree_status_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UpdateDecreeStatusAPI(Resource):
    """API for updating an existing decree status record"""
    
    def put(self, idOrCode):
        bind_contextvars(task="UpdateDecreeStatusAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('code', type=str, required=False, location='json', help="Code is optional")
        parser.add_argument('name', type=str, required=True, location='json', help="Name is required")
        parser.add_argument('description', type=str, required=False, location='json', help="Description is optional")
        args = parser.parse_args()

        decree_status_id = args['code']
        decree_status_name = args['name']
        description = args.get('description')

        if decree_status_id:
            decree_status_id = decree_status_id.strip()

        if decree_status_name:
            decree_status_name = decree_status_name.strip()
            
        if description:
            description = description.strip()
        
        try:
            if ObjectId.is_valid(idOrCode):
                query = {'_id': ObjectId(idOrCode)}
            else:
                query = {'effective_status_id': idOrCode}

            decree_status = law_effective_status_collection.find_one(query)
            if not decree_status:
                logger.error("update_decree_status_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Decree status with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message=f"Decree status with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            if decree_status_id and decree_status_id != decree_status['effective_status_id']:
                logger.error("update_decree_status_failed", action="put", **{"error.code": "400-VAL", "error.message": f"Provided code {decree_status_id} does not match existing code {decree_status['effective_status_id']}", "event.duration": time.time()-start_t, "event.status": "failure"}, provided_code=decree_status_id, actual_code=decree_status['effective_status_id'])
                response = make_response(data=None, code=2000, message=f"Provided code {decree_status_id} does not match existing code")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            name_conflict = law_effective_status_collection.find_one({
                'effective_status_name': {
                    '$regex': f'^{re.escape(decree_status_name)}$',
                    '$options': 'i'
                },
                '_id': {'$ne': decree_status['_id']}
            })
            if name_conflict:
                logger.error("update_decree_status_failed", action="put", **{"error.code": "400-VAL", "error.message": f"Decree status with name {decree_status_name} already exists", "event.duration": time.time()-start_t, "event.status": "failure"}, decree_status_name=decree_status_name)
                response = make_response(data=None, code=2000, message=f"Decree status with name {decree_status_name} already exists")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = "system"
            
            update_fields = {
                "effective_status_name": decree_status_name,
                "last_modified_by": current_user,
                "last_modified_at": current_time
            }
            
            if description is not None:
                update_fields["description"] = description
            
            update_data = {"$set": update_fields}
            
            result = law_effective_status_collection.update_one(query, update_data)
            if result.modified_count == 0 and result.matched_count == 0:
                logger.error("update_decree_status_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to update decree status", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message="Failed to update decree status")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500
                
            updated_decree_status = law_effective_status_collection.find_one(query)
            response_data = _format_decree_status(updated_decree_status)
            logger.info("update_decree_status_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, id_or_code=idOrCode)
            
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("update_decree_status_failed", action="put", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("update_decree_status_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DeleteDecreeStatusAPI(Resource):
    """API for deleting a decree status record"""
    
    def delete(self, idOrCode):
        bind_contextvars(task="DeleteDecreeStatusAPI")
        start_t = time.time()
        try:
            if ObjectId.is_valid(idOrCode):
                query = {'_id': ObjectId(idOrCode)}
            else:
                query = {'effective_status_id': idOrCode}

            decree_status = law_effective_status_collection.find_one(query)
            if not decree_status:
                logger.error("delete_decree_status_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": f"Decree status with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message=f"Decree status with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            result = law_effective_status_collection.delete_one(query)
            if result.deleted_count == 0:
                logger.error("delete_decree_status_failed", action="delete", **{"error.code": "500-DB", "error.message": "Failed to delete decree status", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message="Failed to delete decree status")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            logger.info("delete_decree_status_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"}, id_or_code=idOrCode)
            return make_response(data=None, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("delete_decree_status_failed", action="delete", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("delete_decree_status_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class PublishDecreeStatusAPI(Resource):
    """API for publishing a decree status by setting status to active"""
    
    def put(self, idOrCode):
        bind_contextvars(task="PublishDecreeStatusAPI")
        start_t = time.time()
        try:
            if ObjectId.is_valid(idOrCode):
                query = {'_id': ObjectId(idOrCode)}
            else:
                query = {'effective_status_id': idOrCode}

            decree_status = law_effective_status_collection.find_one(query)
            if not decree_status:
                logger.error("publish_decree_status_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Decree status with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message=f"Decree status with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = "admin"
            
            update_data = {
                "$set": {
                    "status": "ACTIVE",
                    "last_modified_by": current_user,
                    "last_modified_at": current_time
                }
            }
            
            result = law_effective_status_collection.update_one(query, update_data)
            if result.modified_count == 0 and decree_status.get('status') != "ACTIVE":
                logger.error("publish_decree_status_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to publish decree status", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message="Failed to publish decree status")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            updated_decree_status = law_effective_status_collection.find_one(query)
            response_data = _format_decree_status(updated_decree_status)
            
            logger.info("publish_decree_status_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, id_or_code=idOrCode)
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("publish_decree_status_failed", action="put", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("publish_decree_status_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UnpublishDecreeStatusAPI(Resource):
    """API for unpublishing a decree status by setting status to inactive"""
    
    def put(self, idOrCode):
        bind_contextvars(task="UnpublishDecreeStatusAPI")
        start_t = time.time()
        try:
            if ObjectId.is_valid(idOrCode):
                query = {'_id': ObjectId(idOrCode)}
            else:
                query = {'effective_status_id': idOrCode}

            decree_status = law_effective_status_collection.find_one(query)
            if not decree_status:
                logger.error("unpublish_decree_status_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Decree status with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message=f"Decree status with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = "admin"
            
            update_data = {
                "$set": {
                    "status": "INACTIVE",
                    "last_modified_by": current_user,
                    "last_modified_at": current_time
                }
            }
            
            result = law_effective_status_collection.update_one(query, update_data)
            if result.modified_count == 0 and decree_status.get('status') != "INACTIVE":
                logger.error("unpublish_decree_status_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to unpublish decree status", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message="Failed to unpublish decree status")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            updated_decree_status = law_effective_status_collection.find_one(query)
            response_data = _format_decree_status(updated_decree_status)
            
            logger.info("unpublish_decree_status_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, id_or_code=idOrCode)
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("unpublish_decree_status_failed", action="put", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("unpublish_decree_status_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class SearchDecreeStatusAPI(Resource):
    """API for searching decree status records with pagination"""
    
    def post(self, page: int, quantity: int) -> Dict[str, Any]:
        parser = reqparse.RequestParser()
        parser.add_argument('filterText', type=str, required=False, location='json', default="")
        parser.add_argument('Status', type=str, required=False, location='json', default="")
        args = parser.parse_args()

        bind_contextvars(task="SearchDecreeStatusAPI")
        start_t = time.time()
        try:
            page = int(page)
            quantity = int(quantity)
            
            if page < 1 or quantity < 1:
                logger.error("search_decree_statuses_failed", action="post", **{"error.code": "400-VAL", "error.message": "Page and quantity must be positive integers", "event.duration": time.time()-start_t, "event.status": "failure"}, page=page, quantity=quantity)
                response = make_response(data=None, code=1000, message="Page and quantity must be positive integers")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            query = {}
            if args['filterText']:
                query['$or'] = [
                    {'effective_status_id': {'$regex': args['filterText'], '$options': 'i'}},
                    {'effective_status_name': {'$regex': args['filterText'], '$options': 'i'}}
                ]
            if args['Status']:
                query['status'] = args['Status']
          
            skip = (page - 1) * quantity

            total_count = law_effective_status_collection.count_documents(query)
            decree_statuses = list(law_effective_status_collection.find(query).skip(skip).limit(quantity))

            models = [_format_decree_status(ds) for ds in decree_statuses]

            response_data = {
                "count": total_count,
                "models": models
            }

            logger.info("search_decree_statuses_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, page=page, quantity=quantity, total=total_count, count=len(models))
            return make_response(data=response_data, code=0, message="Decree statuses retrieved successfully"), 200

        except PyMongoError as e:
            logger.error("search_decree_statuses_failed", action="post", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("search_decree_statuses_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# Register API
api.add_resource(DecreeStatusDocumentAPI, '/decree_status/list')
api.add_resource(GetByIdDecreeStatusAPI, '/decree_status/get/<idOrCode>')
api.add_resource(CreateDecreeStatusAPI, '/decree_status/create')
api.add_resource(UpdateDecreeStatusAPI, '/decree_status/update/<idOrCode>')
api.add_resource(DeleteDecreeStatusAPI, '/decree_status/delete/<idOrCode>')
api.add_resource(PublishDecreeStatusAPI, '/decree_status/published/<idOrCode>')
api.add_resource(UnpublishDecreeStatusAPI, '/decree_status/unpublished/<idOrCode>')
api.add_resource(SearchDecreeStatusAPI, '/decree_status/search/<page>/<quantity>')
