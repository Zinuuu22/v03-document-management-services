from core.common.mongo.client import get_mongo_client
import structlog
import sys
import uuid
import os
import re
from flask_restful import Resource, reqparse
from pymongo import MongoClient
from datetime import datetime
from typing import Dict, Any
from pymongo.errors import PyMongoError
from pyvi import ViUtils
from structlog.contextvars import clear_contextvars, bind_contextvars
import time


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from services.api import api
from services.api.utils import make_response
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig

logger = structlog.get_logger()


# Connect MongoDB
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
document_agency_collection = db[MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME]


def vi_sort_key(text):
    text = text.lower()
    text = ViUtils.remove_accents(text)
    return text


class ListAgencyAPI(Resource):
    """API for listing all agency records"""
    def get(self):
        
        bind_contextvars(**{"task": "ListAgencyAPI"})
        start_t = time.time()
        try:
            document_agencies = list(document_agency_collection.find())
            document_agencies = sorted(document_agencies, key=lambda x: vi_sort_key(x.get("agency_name", "")))
            result = []
            for doc_agency in document_agencies:
                result.append({
                    "code": doc_agency.get("agency_id", ""),
                    "name": doc_agency.get("agency_name", ""),
                    "createdBy": doc_agency.get("created_by", "system"),
                    "createdDate": doc_agency.get("created_at", "").isoformat() if isinstance(doc_agency.get("created_at"), datetime) else doc_agency.get("created_at", ""),
                    "lastModifiedBy": doc_agency.get("last_modified_by", "system"),
                    "lastModified": doc_agency.get("last_modified_at", "").isoformat() if isinstance(doc_agency.get("last_modified_at"), datetime) else doc_agency.get("last_modified_at", ""),
                    "status": doc_agency.get("status", "")
                })
            
            logger.info("get_list_agency_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(result))
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("get_list_agency_failed", action="get", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=500, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500


class GetByCodeAgencyAPI(Resource):
    """API for getting agency by code"""
    def get(self, idOrCode):
        
        bind_contextvars(**{"task": "GetByCodeAgencyAPI"})
        start_t = time.time()
        try:
            query = {'agency_id': idOrCode}
            
            document_agencies = list(document_agency_collection.find(query).sort("agency_name", 1))
            
            result = []
            for doc_agency in document_agencies:
                result.append({
                    "code": doc_agency.get("agency_id", ""),
                    "name": doc_agency.get("agency_name", ""),
                    "description": doc_agency.get("description", ""),
                    "createdBy": doc_agency.get("created_by", "system"),
                    "createdDate": doc_agency.get("created_at", "").isoformat() if isinstance(doc_agency.get("created_at"), datetime) else doc_agency.get("created_at", ""),
                    "lastModifiedBy": doc_agency.get("last_modified_by", "system"),
                    "lastModified": doc_agency.get("last_modified_at", "").isoformat() if isinstance(doc_agency.get("last_modified_at"), datetime) else doc_agency.get("last_modified_at", ""),
                    "status": doc_agency.get("status", ""),
                    "text": ""
                })
            
            logger.info("get_agency_by_code_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(result))
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("get_agency_by_code_failed", action="get", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=500, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500


class CreateAgencyAPI(Resource):
    """API for creating a new agency record"""  
    def post(self):  
        bind_contextvars(**{"task": "CreateAgencyAPI"})
        start_t = time.time()
        
        parser = reqparse.RequestParser()
        parser.add_argument('code', type=str, required=False, nullable=False, help="Code is optional")
        parser.add_argument('name', type=str, required=True, nullable=False, help="Name is required")
        parser.add_argument('description', type=str, required=False, nullable=False, help="Description is optional")
        args = parser.parse_args()

        agency_id = args['code']
        agency_name = args['name']
        description = args['description']

        if agency_id:
            agency_id = agency_id.strip()

        if agency_name:
            agency_name = agency_name.strip()
            
        if description:
            description = description.strip()
        else:
            description = ""
        
        try:
            if not agency_id:
                agency_id = str(uuid.uuid4())
            
            # Check if agency_id exists
            id_exists = document_agency_collection.find_one({'agency_id': agency_id})
            
            # Check if agency_name exists (case-insensitive)
            name_exists = document_agency_collection.find_one({'agency_name': {
                '$regex': f'^{re.escape(agency_name)}$',
                '$options': 'i'
            }})

            if id_exists or name_exists:
                msg_detail = ""
                if id_exists:
                    msg_detail = f"Agency with agency_id {agency_id} already exists. "
                if name_exists:
                    msg_detail += f"Agency with agency_name {agency_name} already exists."
                
                logger.error("create_agency_failed", action="post", **{"error.code": "400-VAL", "error.message": msg_detail.strip(), "event.duration": time.time()-start_t, "event.status": "failure"}, agency_id=agency_id, agency_name=agency_name)
                response = make_response(data=None, code=400, message=msg_detail.strip())
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = "system" 
            
            document_agency = {
                "agency_id": agency_id,
                "agency_name": agency_name,
                "description": description,
                "created_by": current_user,
                "created_at": current_time,
                "last_modified_by": current_user,
                "last_modified_at": current_time,
                "status": "ACTIVE"
            }
            
            result = document_agency_collection.insert_one(document_agency)
            logger.info("create_agency_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, agency_id=agency_id, inserted_id=str(result.inserted_id))
            
            document_agency['_id'] = str(result.inserted_id)

            response_data = {
                "code": document_agency.get("agency_id", ""),
                "name": document_agency.get("agency_name", ""),
                "description": document_agency.get("description", ""),
                "createdBy": document_agency.get("created_by", ""),
                "createdDate": document_agency.get("created_at", "").isoformat() if isinstance(document_agency.get("created_at"), datetime) else document_agency.get("created_at", ""),
                "lastModifiedBy": document_agency.get("last_modified_by", ""),
                "lastModified": document_agency.get("last_modified_at", "").isoformat() if isinstance(document_agency.get("last_modified_at"), datetime) else document_agency.get("last_modified_at", ""),
                "status": document_agency.get("status", "")
            }
            return make_response(data=response_data, code=0, message="Success"), 201
            
        except Exception as e:
            logger.error("create_agency_failed", action="post", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=500, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500


class UpdateAgencyAPI(Resource):
    """API for updating an existing agency record"""
    
    def put(self, idOrCode): 
        bind_contextvars(**{"task": "UpdateAgencyAPI"})
        start_t = time.time()
        
        parser = reqparse.RequestParser()
        parser.add_argument('code', type=str, required=False, nullable=False, help="Agency ID is optional")
        parser.add_argument('name', type=str, required=True, nullable=False, help="Agency name is required")
        parser.add_argument('description', type=str, required=False, nullable=False, help="Description is optional")
        args = parser.parse_args()

        agency_id = args['code']
        agency_name = args['name']
        description = args['description']

        if agency_id:
            agency_id = agency_id.strip()

        if agency_name:
            agency_name = agency_name.strip()
            
        if description:
            description = description.strip()
        else:
            description = ""
        
        try:
            query = {'agency_id': idOrCode}

            document_agency = document_agency_collection.find_one(query)
            if not document_agency:
                logger.error("update_agency_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Agency with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=404, message=f"Agency with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            if agency_id and agency_id != document_agency['agency_id']:
                logger.error("update_agency_failed", action="put", **{"error.code": "400-VAL", "error.message": f"Provided agency_id {agency_id} does not match agency code", "event.duration": time.time()-start_t, "event.status": "failure"}, provided_agency_id=agency_id, actual_agency_id=document_agency['agency_id'])
                response = make_response(data=None, code=400, message=f"Provided agency_id {agency_id} does not match agency code")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            # Check for duplicate name (case-insensitive) excluding current record
            existing_name = document_agency_collection.find_one({
                'agency_name': {
                    '$regex': f'^{re.escape(agency_name)}$',
                    '$options': 'i'
                },
                'agency_id': {'$ne': document_agency['agency_id']}
            })
            existing_name = existing_name is not None
            if existing_name:
                logger.error("update_agency_failed", action="put", **{"error.code": "400-VAL", "error.message": f"Agency with agency_name {agency_name} already exists", "event.duration": time.time()-start_t, "event.status": "failure"}, agency_name=agency_name)
                response = make_response(data=None, code=400, message=f"Agency with agency_name {agency_name} already exists")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = "system"
            
            update_data = {
                "$set": {
                    "agency_name": agency_name,
                    "description": description,
                    "last_modified_by": current_user,
                    "last_modified_at": current_time
                }
            }
            
            result = document_agency_collection.update_one(query, update_data)
            if result.modified_count == 0:
                logger.error("update_agency_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to update agency", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=500, message="Failed to update agency")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500
                
            updated_document_agency = document_agency_collection.find_one(query)
            response_data = {
                "code": updated_document_agency.get("agency_id", ""),
                "name": updated_document_agency.get("agency_name", ""),
                "description": updated_document_agency.get("description", ""),
                "createdBy": updated_document_agency.get("created_by", ""),
                "createdDate": updated_document_agency.get("created_at", "").isoformat() if isinstance(updated_document_agency.get("created_at"), datetime) else updated_document_agency.get("created_at", ""),
                "lastModifiedBy": updated_document_agency.get("last_modified_by", ""),
                "lastModified": updated_document_agency.get("last_modified_at", "").isoformat() if isinstance(updated_document_agency.get("last_modified_at"), datetime) else updated_document_agency.get("last_modified_at", ""),
                "status": updated_document_agency.get("status", "")
            }
            logger.info("update_agency_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, idOrCode=idOrCode)
            
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("update_agency_failed", action="put", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=500, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500


class DeleteAgencyAPI(Resource):
    """API for deleting an agency record"""
    
    def delete(self, idOrCode):
        bind_contextvars(**{"task": "DeleteAgencyAPI"})
        start_t = time.time()
        try:
            query = {'agency_id': idOrCode}

            document_agency = document_agency_collection.find_one(query)
            if not document_agency:
                logger.error("delete_agency_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": f"Agency with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=404, message=f"Agency with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            result = document_agency_collection.delete_one(query)
            if result.deleted_count == 0:
                logger.error("delete_agency_failed", action="delete", **{"error.code": "500-DB", "error.message": "Failed to delete agency", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=500, message="Failed to delete agency")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            logger.info("delete_agency_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"}, idOrCode=idOrCode)
            return make_response(data=None, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("delete_agency_failed", action="delete", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=500, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500


class PublishAgencyAPI(Resource):
    """API for publishing an agency by setting status to active"""
    
    def put(self, idOrCode):
        bind_contextvars(**{"task": "PublishAgencyAPI"})
        start_t = time.time()
        try:
            query = {'agency_id': idOrCode}

            document_agency = document_agency_collection.find_one(query)
            if not document_agency:
                logger.error("publish_agency_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Agency with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=404, message=f"Agency with idOrCode {idOrCode} not found")
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
            
            result = document_agency_collection.update_one(query, update_data)
            if result.modified_count == 0 and document_agency['status'] != "ACTIVE":
                logger.error("publish_agency_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to publish agency", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=500, message="Failed to publish agency")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            updated_document_agency = document_agency_collection.find_one(query)
            
            response_data = {
                "code": updated_document_agency.get("agency_id", ""),
                "name": updated_document_agency.get("agency_name", ""),
                "description": updated_document_agency.get("description", ""),
                "createdBy": updated_document_agency.get("created_by", ""),
                "createdDate": updated_document_agency.get("created_at", "").isoformat() if isinstance(updated_document_agency.get("created_at"), datetime) else updated_document_agency.get("created_at", ""),
                "lastModifiedBy": updated_document_agency.get("last_modified_by", ""),
                "lastModified": updated_document_agency.get("last_modified_at", "").isoformat() if isinstance(updated_document_agency.get("last_modified_at"), datetime) else updated_document_agency.get("last_modified_at", ""),
                "status": updated_document_agency.get("status", "")
            }
            
            logger.info("publish_agency_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, idOrCode=idOrCode)
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("publish_agency_failed", action="put", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=500, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500


class UnpublishAgencyAPI(Resource):
    """API for unpublishing an agency by setting status to inactive"""
    def put(self, idOrCode):
        bind_contextvars(**{"task": "UnpublishAgencyAPI"})
        start_t = time.time()
        try:
            query = {'agency_id': idOrCode}

            document_agency = document_agency_collection.find_one(query)
            if not document_agency:
                logger.error("unpublish_agency_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Agency with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=404, message=f"Agency with idOrCode {idOrCode} not found")
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
            
            result = document_agency_collection.update_one(query, update_data)
            if result.modified_count == 0 and document_agency['status'] != "INACTIVE":
                logger.error("unpublish_agency_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to unpublish agency", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=500, message="Failed to unpublish agency")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            updated_document_agency = document_agency_collection.find_one(query)
            
            response_data = {
                "code": updated_document_agency.get("agency_id", ""),
                "name": updated_document_agency.get("agency_name", ""),
                "description": updated_document_agency.get("description", ""),
                "createdBy": updated_document_agency.get("created_by", ""),
                "createdDate": updated_document_agency.get("created_at", "").isoformat() if isinstance(updated_document_agency.get("created_at"), datetime) else updated_document_agency.get("created_at", ""),
                "lastModifiedBy": updated_document_agency.get("last_modified_by", ""),
                "lastModified": updated_document_agency.get("last_modified_at", "").isoformat() if isinstance(updated_document_agency.get("last_modified_at"), datetime) else updated_document_agency.get("last_modified_at", ""),
                "status": updated_document_agency.get("status", "")
            }
            
            logger.info("unpublish_agency_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, idOrCode=idOrCode)
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("unpublish_agency_failed", action="put", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=500, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500


class SearchAgencyAPI(Resource):
    """API for searching agency records with pagination"""
    
    def post(self, page: int, quantity: int) -> Dict[str, Any]:
        """Handle POST request to search agency records with pagination.

        Args:
            page: Page number (1-based).
            quantity: Number of records per page.

        Returns:
            Response with search results, total count, or error message.
        """
        
        bind_contextvars(**{"task": "SearchAgencyAPI"})
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('text', type=str, required=False, nullable=True, location='json', help="Search text")
        parser.add_argument('status', type=str, required=False, nullable=True, location='json', help="Agency status")
        args = parser.parse_args()

        text = args['text']
        status = args['status']
        
        logger.debug("search_agency_received", action="post", text=text, status=status, page=page, quantity=quantity)

        try:
            page = int(page)
            quantity = int(quantity)
            
            if page < 1 or quantity < 1:
                logger.error("search_agency_failed", action="post", **{"error.code": "400-VAL", "error.message": "Page and quantity must be positive integers", "event.duration": time.time()-start_t, "event.status": "failure"}, page=page, quantity=quantity)
                response = make_response(data=None, code=400, message="Page and quantity must be positive integers")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            query = {}
            if text:
                query['$or'] = [
                    {'agency_id': {'$regex': text, '$options': 'i'}},
                    {'agency_name': {'$regex': text, '$options': 'i'}},
                    {'description': {'$regex': text, '$options': 'i'}}
                ]
            if status:
                query['status'] = status

            skip = (page - 1) * quantity

            total_count = document_agency_collection.count_documents(query)
            document_agencies = list(document_agency_collection.find(query))
            document_agencies.sort(key=lambda x: vi_sort_key(x.get("agency_name", "")))
            document_agencies = document_agencies[skip:skip + quantity]

            models = []
            for doc_agency in document_agencies:
                model = {
                    "code": doc_agency.get("agency_id", ""),
                    "name": doc_agency.get("agency_name", ""),
                    "description": doc_agency.get("description", ""),
                    "createdBy": doc_agency.get("created_by", "admin"),
                    "createdDate": doc_agency.get("created_at", "").isoformat() if isinstance(doc_agency.get("created_at"), datetime) else doc_agency.get("created_at", ""),
                    "lastModifiedBy": doc_agency.get("last_modified_by", "admin"),
                    "lastModified": doc_agency.get("last_modified_at", "").isoformat() if isinstance(doc_agency.get("last_modified_at"), datetime) else doc_agency.get("last_modified_at", ""),
                    "status": doc_agency.get("status", ""),
                    "text": text if text else ""
                }
                models.append(model)

            response_data = {
                "count": total_count,
                "models": models
            }

            logger.info("search_agency_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(models), page=page, quantity=quantity, total=total_count)
            return make_response(
                data=response_data,
                code=0,
                message="Agencies retrieved successfully"
            ), 200

        except PyMongoError as e:
            logger.error("search_agency_failed", action="post", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=500, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("search_agency_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=500, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class AgencyInUseAPI(Resource):
    """API for checking if an agency is referenced by any documents"""
    
    def get(self):
        bind_contextvars(**{"task": "AgencyInUseAPI"})
        start_t = time.time()
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('code', type=str, required=True, location='args', help='Agency code is required')
            args = parser.parse_args()
            
            code = args['code']
            
            law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
            
            query = {"agency_ids": code}
            
            total = law_documents_collection.count_documents(query)
            in_use = total > 0
            
            result = {
                "in_use": in_use,
                "total": total
            }
            
            logger.info("agency_in_use_check_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, code=code, in_use=in_use, total=total)
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("agency_in_use_check_failed", action="get", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=500, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500


api.add_resource(ListAgencyAPI, '/agency-issued/get')
api.add_resource(GetByCodeAgencyAPI, '/agency-issued/<idOrCode>')
api.add_resource(CreateAgencyAPI, '/agency-issued/create')
api.add_resource(UpdateAgencyAPI, '/agency-issued/update/<idOrCode>')
api.add_resource(DeleteAgencyAPI, '/agency-issued/delete/<idOrCode>')
api.add_resource(PublishAgencyAPI, '/agency-issued/published/<idOrCode>')
api.add_resource(UnpublishAgencyAPI, '/agency-issued/unpublished/<idOrCode>')
api.add_resource(SearchAgencyAPI, '/agency-issued/<page>/<quantity>')
api.add_resource(AgencyInUseAPI, '/agency-issued/in-use')

