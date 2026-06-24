from core.common.mongo.client import get_mongo_client
import structlog
from structlog.contextvars import bind_contextvars
import time
import sys
import uuid
import os
import re

from flask_restful import Resource, reqparse
from bson import ObjectId
from pymongo import MongoClient
from datetime import datetime
from typing import Dict, Any
from pymongo.errors import PyMongoError
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from services.api import api
from services.api.utils import make_response
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
logger = structlog.get_logger()


# Connect MongoDB
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
position_collection = db[MongoDBCollectionConfig.LAW_POSITIONS_COLLECTION_NAME]


class ListPositionAPI(Resource):
    """API for listing all position records"""
    
    def get(self):
        bind_contextvars(task="ListPositionAPI")
        start_t = time.time()
        try:
            positions = list(position_collection.find().sort('position_name', 1))
            
            result = []
            for pos in positions:
                pos['_id'] = str(pos['_id'])
                result.append({
                    "code": pos.get("position_id", ""),
                    "name": pos.get("position_name", ""),
                    "description": pos.get("description", ""),
                    "createdBy": pos.get("created_by", ""),
                    "createdDate": pos.get("created_at", "").isoformat() if isinstance(pos.get("created_at"), datetime) else pos.get("created_at", ""),
                    "lastModifiedBy": pos.get("last_modified_by", ""),
                    "lastModified": pos.get("last_modified_at", "").isoformat() if isinstance(pos.get("last_modified_at"), datetime) else pos.get("last_modified_at", ""),
                    "status": pos.get("status", "")
                })
            
            logger.info("list_position_success", action="get", count=len(result), **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("list_position_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetByCodePositionAPI(Resource):
    """API for getting position by code"""
    
    def get(self, idOrCode):
        bind_contextvars(task="GetByCodePositionAPI")
        start_t = time.time()
        try:
            if ObjectId.is_valid(idOrCode):
                query = {'_id': ObjectId(idOrCode)}
            else:
                query = {'position_id': idOrCode}
            
            positions = list(position_collection.find(query).sort('position_name', 1))
            
            result = []
            for pos in positions:
                pos['_id'] = str(pos['_id'])
                result.append({
                    "code": pos.get("position_id", ""),
                    "name": pos.get("position_name", ""),
                    "description": pos.get("description", ""),
                    "createdBy": pos.get("created_by", ""),
                    "createdDate": pos.get("created_at", "").isoformat() if isinstance(pos.get("created_at"), datetime) else pos.get("created_at", ""),
                    "lastModifiedBy": pos.get("last_modified_by", ""),
                    "lastModified": pos.get("last_modified_at", "").isoformat() if isinstance(pos.get("last_modified_at"), datetime) else pos.get("last_modified_at", ""),
                    "status": pos.get("status", "")
                })
            
            logger.info("get_by_code_position_success", action="get", count=len(result), **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("get_by_code_position_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class CreatePositionAPI(Resource):
    """API for creating a new position record"""
    
    def post(self):
        bind_contextvars(task="CreatePositionAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('code', type=str, required=False, nullable=False, help="Code is optional")
        parser.add_argument('name', type=str, required=True, nullable=False, help="Name is required")
        parser.add_argument('description', type=str, required=False, nullable=False, help="Description is optional")
        args = parser.parse_args()

        position_id = args['code']
        position_name = args['name']
        description = args['description']

        if position_id:
            position_id = position_id.strip()
        
        if position_name:
            position_name = position_name.strip()
            
        if description:
            description = description.strip()
        else:
            description = ""
        
        try:
            if not position_id:
                position_id = str(uuid.uuid4())
            
            # Check if position_id exists
            id_exists = position_collection.find_one({'position_id': position_id})
            
            # Check if position_name exists (case-insensitive)
            name_exists = position_collection.find_one({
                'position_name': {
                    '$regex': f'^{re.escape(position_name)}$',
                    '$options': 'i'
                }
            })
            
            if id_exists or name_exists:
                msg_detail = ""
                if id_exists:
                    msg_detail = f"Position with position_id {position_id} already exists. "
                if name_exists:
                    msg_detail += f"Position with position_name {position_name} already exists."
                
                logger.error("create_position_failed", action="post", position_id=position_id, position_name=position_name, **{"error.code": "400-VAL", "error.message": msg_detail.strip(), "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=msg_detail.strip())
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = "admin" 
            
            position = {
                "position_id": position_id,
                "position_name": position_name,
                "description": description,
                "created_by": current_user,
                "created_at": current_time,
                "last_modified_by": current_user,
                "last_modified_at": current_time,
                "status": "ACTIVE"
            }
            
            result = position_collection.insert_one(position)
            logger.info("create_position_success", action="post", position_id=position_id, inserted_id=str(result.inserted_id), **{"event.status": "success", "event.duration": time.time() - start_t})
            
            position['_id'] = str(result.inserted_id)

            response_data = {
                "code": position.get("position_id", ""),
                "name": position.get("position_name", ""),
                "description": position.get("description", ""),
                "createdBy": position.get("created_by", ""),
                "createdDate": position.get("created_at", "").isoformat() if isinstance(position.get("created_at"), datetime) else position.get("created_at", ""),
                "lastModifiedBy": position.get("last_modified_by", ""),
                "lastModified": position.get("last_modified_at", "").isoformat() if isinstance(position.get("last_modified_at"), datetime) else position.get("last_modified_at", ""),
                "status": position.get("status", "")
            }
            return make_response(data=response_data, code=0, message="Success"), 201
            
        except Exception as e:
            logger.error("create_position_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UpdatePositionAPI(Resource):
    """API for updating an existing position record"""
    
    def put(self, idOrCode):
        bind_contextvars(task="UpdatePositionAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('code', type=str, required=False, nullable=False, help="Position ID is optional")
        parser.add_argument('name', type=str, required=True, nullable=False, help="Position name is required")
        parser.add_argument('description', type=str, required=False, nullable=False, help="Description is optional")
        args = parser.parse_args()

        position_id = args['code']
        position_name = args['name']
        description = args['description']

        if position_id:
            position_id = position_id.strip()
            
        if position_name:
            position_name = position_name.strip()
            
        if description:
            description = description.strip()
        else:
            description = ""
        
        try:
            query = {}
            if ObjectId.is_valid(idOrCode):
                query['_id'] = ObjectId(idOrCode)
            else:
                query['position_id'] = idOrCode

            position = position_collection.find_one(query)
            if not position:
                logger.error("update_position_failed", action="put", idOrCode=idOrCode, **{"error.code": "404-NOTFOUND", "error.message": f"Position with idOrCode {idOrCode} not found", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=f"Position with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            if position_id and position_id != position['position_id']:
                logger.error("update_position_failed", action="put", provided_id=position_id, actual_id=position['position_id'], **{"error.code": "400-VAL", "error.message": f"Provided position_id {position_id} does not match position code", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=f"Provided position_id {position_id} does not match position code")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            # Check for duplicate name excluding current record
            existing_name = position_collection.find_one({
                'position_name': {
                    '$regex': f'^{re.escape(position_name)}$',
                    '$options': 'i'
                },
                'position_id': {'$ne': position['position_id']}
            })
            
            if existing_name:
                logger.error("update_position_failed", action="put", position_name=position_name, **{"error.code": "400-VAL", "error.message": f"Position with position_name {position_name} already exists", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=f"Position with position_name {position_name} already exists")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = "admin"
            
            update_data = {
                "$set": {
                    "position_name": position_name,
                    "description": description,
                    "last_modified_by": current_user,
                    "last_modified_at": current_time
                }
            }
            
            result = position_collection.update_one(query, update_data)
            if result.modified_count == 0:
                logger.error("update_position_failed", action="put", idOrCode=idOrCode, **{"error.code": "500-DB", "error.message": "Failed to update position", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message="Failed to update position")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500
                
            updated_position = position_collection.find_one(query)
            response_data = {
                "code": updated_position.get("position_id", ""),
                "name": updated_position.get("position_name", ""),
                "description": updated_position.get("description", ""),
                "createdBy": updated_position.get("created_by", ""),
                "createdDate": updated_position.get("created_at", "").isoformat() if isinstance(updated_position.get("created_at"), datetime) else updated_position.get("created_at", ""),
                "lastModifiedBy": updated_position.get("last_modified_by", ""),
                "lastModified": updated_position.get("last_modified_at", "").isoformat() if isinstance(updated_position.get("last_modified_at"), datetime) else updated_position.get("last_modified_at", ""),
                "status": updated_position.get("status", "")
            }
            logger.info("update_position_success", action="put", idOrCode=idOrCode, **{"event.status": "success", "event.duration": time.time() - start_t})
            
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("update_position_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DeletePositionAPI(Resource):
    """API for deleting a position record"""
    
    def delete(self, idOrCode):
        bind_contextvars(task="DeletePositionAPI")
        start_t = time.time()
        try:
            query = {}
            if ObjectId.is_valid(idOrCode):
                query['_id'] = ObjectId(idOrCode)
            else:
                query['position_id'] = idOrCode

            position = position_collection.find_one(query)
            if not position:
                logger.error("delete_position_failed", action="delete", idOrCode=idOrCode, **{"error.code": "404-NOTFOUND", "error.message": f"Position with idOrCode {idOrCode} not found", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=f"Position with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            result = position_collection.delete_one(query)
            if result.deleted_count == 0:
                logger.error("delete_position_failed", action="delete", idOrCode=idOrCode, **{"error.code": "500-DB", "error.message": "Failed to delete position", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message="Failed to delete position")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            logger.info("delete_position_success", action="delete", idOrCode=idOrCode, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(data=None, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("delete_position_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class PublishPositionAPI(Resource):
    """API for publishing a position by setting status to active"""
    
    def put(self, idOrCode):
        bind_contextvars(task="PublishPositionAPI")
        start_t = time.time()
        try:
            query = {}
            if ObjectId.is_valid(idOrCode):
                query['_id'] = ObjectId(idOrCode)
            else:
                query['position_id'] = idOrCode

            position = position_collection.find_one(query)
            if not position:
                logger.error("publish_position_failed", action="put", idOrCode=idOrCode, **{"error.code": "404-NOTFOUND", "error.message": f"Position with idOrCode {idOrCode} not found", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=f"Position with idOrCode {idOrCode} not found")
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
            
            result = position_collection.update_one(query, update_data)
            if result.modified_count == 0 and position['status'] != "ACTIVE":
                logger.error("publish_position_failed", action="put", idOrCode=idOrCode, **{"error.code": "500-DB", "error.message": "Failed to publish position", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message="Failed to publish position")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            updated_position = position_collection.find_one(query)
            updated_position['_id'] = str(updated_position['_id'])
            
            response_data = {
                "code": updated_position.get("position_id", ""),
                "name": updated_position.get("position_name", ""),
                "description": updated_position.get("description", ""),
                "createdBy": updated_position.get("created_by", ""),
                "createdDate": updated_position.get("created_at", "").isoformat() if isinstance(updated_position.get("created_at"), datetime) else updated_position.get("created_at", ""),
                "lastModifiedBy": updated_position.get("last_modified_by", ""),
                "lastModified": updated_position.get("last_modified_at", "").isoformat() if isinstance(updated_position.get("last_modified_at"), datetime) else updated_position.get("last_modified_at", ""),
                "status": updated_position.get("status", "")
            }
            
            logger.info("publish_position_success", action="put", idOrCode=idOrCode, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("publish_position_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UnpublishPositionAPI(Resource):
    """API for unpublishing a position by setting status to inactive"""
    
    def put(self, idOrCode):
        bind_contextvars(task="UnpublishPositionAPI")
        start_t = time.time()
        try:
            query = {}
            if ObjectId.is_valid(idOrCode):
                query['_id'] = ObjectId(idOrCode)
            else:
                query['position_id'] = idOrCode

            position = position_collection.find_one(query)
            if not position:
                logger.error("unpublish_position_failed", action="put", idOrCode=idOrCode, **{"error.code": "404-NOTFOUND", "error.message": f"Position with idOrCode {idOrCode} not found", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=f"Position with idOrCode {idOrCode} not found")
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
            
            result = position_collection.update_one(query, update_data)
            if result.modified_count == 0 and position['status'] != "INACTIVE":
                logger.error("unpublish_position_failed", action="put", idOrCode=idOrCode, **{"error.code": "500-DB", "error.message": "Failed to unpublish position", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message="Failed to unpublish position")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            updated_position = position_collection.find_one(query)
            updated_position['_id'] = str(updated_position['_id'])
            
            response_data = {
                "code": updated_position.get("position_id", ""),
                "name": updated_position.get("position_name", ""),
                "description": updated_position.get("description", ""),
                "createdBy": updated_position.get("created_by", ""),
                "createdDate": updated_position.get("created_at", "").isoformat() if isinstance(updated_position.get("created_at"), datetime) else updated_position.get("created_at", ""),
                "lastModifiedBy": updated_position.get("last_modified_by", ""),
                "lastModified": updated_position.get("last_modified_at", "").isoformat() if isinstance(updated_position.get("last_modified_at"), datetime) else updated_position.get("last_modified_at", ""),
                "status": updated_position.get("status", "")
            }
            
            logger.info("unpublish_position_success", action="put", idOrCode=idOrCode, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("unpublish_position_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class SearchPositionAPI(Resource):
    """API for searching position records with pagination"""
    
    def post(self, page: int, quantity: int) -> Dict[str, Any]:
        """Handle POST request to search position records with pagination.

        Args:
            page: Page number (1-based).
            quantity: Number of records per page.

        Returns:
            Response with search results, total count, or error message.
        """
        bind_contextvars(task="SearchPositionAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('text', type=str, required=False, nullable=True, location='json', help="Search text")
        parser.add_argument('status', type=str, required=False, nullable=True, location='json', help="Position status")
        args = parser.parse_args()

        text = args['text']
        status = args['status']
        
        try:
            page = int(page)
            quantity = int(quantity)
            
            if page < 1 or quantity < 1:
                logger.error("search_position_failed", action="post", page=page, quantity=quantity, **{"error.code": "400-VAL", "error.message": "Page and quantity must be positive integers", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=1000, message="Page and quantity must be positive integers")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            query = {}
            if text:
                query['$or'] = [
                    {'position_id': {'$regex': text, '$options': 'i'}},
                    {'position_name': {'$regex': text, '$options': 'i'}},
                    {'description': {'$regex': text, '$options': 'i'}}
                ]
            if status:
                query['status'] = status

            skip = (page - 1) * quantity

            total_count = position_collection.count_documents(query)
            positions = list(position_collection.find(query).sort('position_name', 1).skip(skip).limit(quantity))

            models = []
            for pos in positions:
                model = {
                    "code": pos.get("position_id", ""),
                    "name": pos.get("position_name", ""),
                    "description": pos.get("description", ""),
                    "createdBy": pos.get("created_by", "admin"),
                    "createdDate": pos.get("created_at", "").isoformat() if isinstance(pos.get("created_at"), datetime) else pos.get("created_at", ""),
                    "lastModifiedBy": pos.get("last_modified_by", "admin"),
                    "lastModified": pos.get("last_modified_at", "").isoformat() if isinstance(pos.get("last_modified_at"), datetime) else pos.get("last_modified_at", ""),
                    "status": pos.get("status", ""),
                    "text": text if text else ""
                }
                models.append(model)

            response_data = {
                "count": total_count,
                "models": models
            }

            logger.info("search_position_success", action="post", count=len(models), page=page, quantity=quantity, total=total_count, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(
                data=response_data,
                code=0,
                message="Positions retrieved successfully"
            ), 200

        except PyMongoError as e:
            logger.error("search_position_failed", action="post", **{"error.code": "500-DB", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("search_position_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class PositionInUseAPI(Resource):
    """API for checking if a position is referenced by any documents"""
    
    def get(self):
        bind_contextvars(task="PositionInUseAPI")
        start_t = time.time()
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('position_id', type=str, required=True, location='args', help='Position ID is required')
            args = parser.parse_args()
            
            position_id = args['position_id']
            
            law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
            
            query = {"position_ids": position_id}
            
            total = law_documents_collection.count_documents(query)
            in_use = total > 0
            
            result = {
                "in_use": in_use,
                "total": total
            }
            
            logger.info("position_in_use_success", action="get", position_id=position_id, in_use=in_use, total_documents=total, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("position_in_use_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


api.add_resource(ListPositionAPI, '/position/get')
api.add_resource(GetByCodePositionAPI, '/position/<idOrCode>')
api.add_resource(CreatePositionAPI, '/position/create')
api.add_resource(UpdatePositionAPI, '/position/update/<idOrCode>')
api.add_resource(DeletePositionAPI, '/position/delete/<idOrCode>')
api.add_resource(PublishPositionAPI, '/position/published/<idOrCode>')
api.add_resource(UnpublishPositionAPI, '/position/unpublished/<idOrCode>')
api.add_resource(SearchPositionAPI, '/position/<page>/<quantity>')
api.add_resource(PositionInUseAPI, '/position/in-use')

