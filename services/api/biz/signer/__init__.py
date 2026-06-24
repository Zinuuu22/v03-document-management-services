from core.common.mongo.client import get_mongo_client
import structlog
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
document_signer_collection = db[MongoDBCollectionConfig.LAW_SIGNERS_COLLECTION_NAME]

def vi_sort_key(text):
    text = text.lower()
    text = ViUtils.remove_accents(text)
    return text


class ListSignerAPI(Resource):
    """API for listing all signer records"""
    
    def get(self):
        bind_contextvars(task="ListSignerAPI")
        start_t = time.time()
        try:
            document_signers = list(document_signer_collection.find())
            document_signers = sorted(document_signers, key=lambda x: vi_sort_key(x.get("signer_name", "")))
            
            result = []
            for doc_signer in document_signers:
                doc_signer['_id'] = str(doc_signer['_id'])
                result.append({
                    "code": doc_signer.get("signer_id", ""),
                    "name": doc_signer.get("signer_name", ""),
                    "createdBy": doc_signer.get("created_by", "system"),
                    "createdDate": doc_signer.get("created_at", "").isoformat() if isinstance(doc_signer.get("created_at"), datetime) else doc_signer.get("created_at", ""),
                    "lastModifiedBy": doc_signer.get("last_modified_by", "system"),
                    "lastModified": doc_signer.get("last_modified_at", "").isoformat() if isinstance(doc_signer.get("last_modified_at"), datetime) else doc_signer.get("last_modified_at", ""),
                    "status": doc_signer.get("status", "")
                })
            
            logger.info("get_signers_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, signer_count=len(result))
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("get_signers_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetByCodeSignerAPI(Resource):
    """API for getting signer by code"""
    
    def get(self, idOrCode):
        bind_contextvars(task="GetByCodeSignerAPI")
        start_t = time.time()
        try:
            if ObjectId.is_valid(idOrCode):
                query = {'_id': ObjectId(idOrCode)}
            else:
                query = {'signer_id': idOrCode}
            
            document_signers = list(document_signer_collection.find(query).sort("signer_name", 1))
            
            result = []
            for doc_signer in document_signers:
                doc_signer['_id'] = str(doc_signer['_id'])
                result.append({
                    "code": doc_signer.get("signer_id", ""),
                    "name": doc_signer.get("signer_name", ""),
                    "description": doc_signer.get("description", ""),
                    "createdBy": doc_signer.get("created_by", "system"),
                    "createdDate": doc_signer.get("created_at", "").isoformat() if isinstance(doc_signer.get("created_at"), datetime) else doc_signer.get("created_at", ""),
                    "lastModifiedBy": doc_signer.get("last_modified_by", "system"),
                    "lastModified": doc_signer.get("last_modified_at", "").isoformat() if isinstance(doc_signer.get("last_modified_at"), datetime) else doc_signer.get("last_modified_at", ""),
                    "status": doc_signer.get("status", ""),
                    "text": ""
                })
            
            logger.info("get_signer_by_code_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, signer_count=len(result), id_or_code=idOrCode)
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("get_signer_by_code_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True, id_or_code=idOrCode)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class CreateSignerAPI(Resource):
    """API for creating a new signer record"""
    
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('code', type=str, required=False, nullable=False, help="Code is optional")
        parser.add_argument('name', type=str, required=True, nullable=False, help="Name is required")
        parser.add_argument('description', type=str, required=False, nullable=False, help="Description is optional")
        args = parser.parse_args()

        signer_id = args['code']
        signer_name = args['name']
        description = args['description']

        if signer_id:
            signer_id = signer_id.strip()
        if signer_name:
            signer_name = signer_name.strip()
        if description:
            description = description.strip()
        else:
            description = ""
        
        bind_contextvars(task="CreateSignerAPI")
        start_t = time.time()
        try:
            if not signer_id:
                signer_id = str(uuid.uuid4())
            
            # Check if signer_id exists
            id_exists = document_signer_collection.find_one({'signer_id': signer_id})
            
            # Check if signer_name exists (case-insensitive)
            name_exists = document_signer_collection.find_one({'signer_name': {
                '$regex': f'^{re.escape(signer_name)}$',
                '$options': 'i'
            }})

            if id_exists or name_exists:
                msg_detail = ""
                if id_exists:
                    msg_detail = f"Signer with signer_id {signer_id} already exists. "
                if name_exists:
                    msg_detail += f"Signer with signer_name {signer_name} already exists."
                
                logger.error("create_signer_failed", action="post", **{"error.code": "400-VAL", "error.message": msg_detail.strip(), "event.duration": time.time()-start_t, "event.status": "failure"}, signer_id=signer_id, signer_name=signer_name)
                response = make_response(data=None, code=2000, message=msg_detail.strip())
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = "system" 
            
            document_signer = {
                "signer_id": signer_id,
                "signer_name": signer_name,
                "description": description,
                "created_by": current_user,
                "created_at": current_time,
                "last_modified_by": current_user,
                "last_modified_at": current_time,
                "status": "ACTIVE"
            }
            
            result = document_signer_collection.insert_one(document_signer)
            logger.info("create_signer_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, signer_id=signer_id, mongo_id=str(result.inserted_id))
            
            document_signer['_id'] = str(result.inserted_id)

            response_data = {
                "code": document_signer.get("signer_id", ""),
                "name": document_signer.get("signer_name", ""),
                "description": document_signer.get("description", ""),
                "createdBy": document_signer.get("created_by", ""),
                "createdDate": document_signer.get("created_at", "").isoformat() if isinstance(document_signer.get("created_at"), datetime) else document_signer.get("created_at", ""),
                "lastModifiedBy": document_signer.get("last_modified_by", ""),
                "lastModified": document_signer.get("last_modified_at", "").isoformat() if isinstance(document_signer.get("last_modified_at"), datetime) else document_signer.get("last_modified_at", ""),
                "status": document_signer.get("status", "")
            }
            return make_response(data=response_data, code=0, message="Success"), 201
            
        except Exception as e:
            logger.error("create_signer_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UpdateSignerAPI(Resource):
    """API for updating an existing signer record"""
    
    def put(self, idOrCode):
        parser = reqparse.RequestParser()
        parser.add_argument('code', type=str, required=False, nullable=False, help="Signer ID is optional")
        parser.add_argument('name', type=str, required=True, nullable=False, help="Signer name is required")
        parser.add_argument('description', type=str, required=False, nullable=False, help="Description is optional")
        args = parser.parse_args()

        signer_id = args['code']
        signer_name = args['name']
        description = args['description']

        if signer_id:
            signer_id = signer_id.strip()

        if signer_name:
            signer_name = signer_name.strip()
            
        if description:
            description = description.strip()
        else:
            description = ""
        
        bind_contextvars(task="UpdateSignerAPI")
        start_t = time.time()
        try:
            query = {}
            if ObjectId.is_valid(idOrCode):
                query['_id'] = ObjectId(idOrCode)
            else:
                query['signer_id'] = idOrCode

            document_signer = document_signer_collection.find_one(query)
            if not document_signer:
                logger.error("update_signer_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Signer with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message=f"Signer with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            if signer_id and signer_id != document_signer['signer_id']:
                logger.error("update_signer_failed", action="put", **{"error.code": "400-VAL", "error.message": f"Provided signer_id {signer_id} does not match signer code", "event.duration": time.time()-start_t, "event.status": "failure"}, provided_id=signer_id, actual_id=document_signer['signer_id'])
                response = make_response(data=None, code=2000, message=f"Provided signer_id {signer_id} does not match signer code")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            # Check for duplicate name (case-insensitive) excluding current record
            existing_name = document_signer_collection.find_one({
                'signer_name': {
                    '$regex': f'^{re.escape(signer_name)}$',
                    '$options': 'i'
                },
                'signer_id': {'$ne': document_signer['signer_id']}
            })
            
            if existing_name:
                logger.error("update_signer_failed", action="put", **{"error.code": "400-VAL", "error.message": f"Signer with signer_name {signer_name} already exists", "event.duration": time.time()-start_t, "event.status": "failure"}, signer_name=signer_name)
                response = make_response(data=None, code=2000, message=f"Signer with signer_name {signer_name} already exists")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = "system"
            
            update_data = {
                "$set": {
                    "signer_name": signer_name,
                    "description": description,
                    "last_modified_by": current_user,
                    "last_modified_at": current_time
                }
            }
            
            result = document_signer_collection.update_one(query, update_data)
            if result.modified_count == 0:
                logger.error("update_signer_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to update document signer", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message="Failed to update document signer")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500
                
            updated_document_signer = document_signer_collection.find_one(query)
            response_data = {
                "code": updated_document_signer.get("signer_id", ""),
                "name": updated_document_signer.get("signer_name", ""),
                "description": updated_document_signer.get("description", ""),
                "createdBy": updated_document_signer.get("created_by", ""),
                "createdDate": updated_document_signer.get("created_at", "").isoformat() if isinstance(updated_document_signer.get("created_at"), datetime) else updated_document_signer.get("created_at", ""),
                "lastModifiedBy": updated_document_signer.get("last_modified_by", ""),
                "lastModified": updated_document_signer.get("last_modified_at", "").isoformat() if isinstance(updated_document_signer.get("last_modified_at"), datetime) else updated_document_signer.get("last_modified_at", ""),
                "status": updated_document_signer.get("status", "")
            }
            logger.info("update_signer_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, id_or_code=idOrCode)
            
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("update_signer_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True, id_or_code=idOrCode)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DeleteSignerAPI(Resource):
    """API for deleting a signer record"""
    
    def delete(self, idOrCode):
        bind_contextvars(task="DeleteSignerAPI")
        start_t = time.time()
        try:
            query = {}
            if ObjectId.is_valid(idOrCode):
                query['_id'] = ObjectId(idOrCode)
            else:
                query['signer_id'] = idOrCode

            document_signer = document_signer_collection.find_one(query)
            if not document_signer:
                logger.error("delete_signer_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": f"Signer with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message=f"Signer with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            result = document_signer_collection.delete_one(query)
            if result.deleted_count == 0:
                logger.error("delete_signer_failed", action="delete", **{"error.code": "500-DB", "error.message": "Failed to delete document signer", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message="Failed to delete document signer")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            logger.info("delete_signer_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"}, id_or_code=idOrCode)
            return make_response(data=None, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("delete_signer_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True, id_or_code=idOrCode)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class PublishSignerAPI(Resource):
    """API for publishing a signer by setting status to active"""
    
    def put(self, idOrCode):
        bind_contextvars(task="PublishSignerAPI")
        start_t = time.time()
        try:
            query = {}
            if ObjectId.is_valid(idOrCode):
                query['_id'] = ObjectId(idOrCode)
            else:
                query['signer_id'] = idOrCode

            document_signer = document_signer_collection.find_one(query)
            if not document_signer:
                logger.error("publish_signer_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Signer with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message=f"Signer with idOrCode {idOrCode} not found")
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
            
            result = document_signer_collection.update_one(query, update_data)
            if result.modified_count == 0 and document_signer['status'] != "ACTIVE":
                logger.error("publish_signer_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to publish document signer", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message="Failed to publish document signer")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            updated_document_signer = document_signer_collection.find_one(query)
            updated_document_signer['_id'] = str(updated_document_signer['_id'])
            
            response_data = {
                "code": updated_document_signer.get("signer_id", ""),
                "name": updated_document_signer.get("signer_name", ""),
                "description": updated_document_signer.get("description", ""),
                "createdBy": updated_document_signer.get("created_by", ""),
                "createdDate": updated_document_signer.get("created_at", "").isoformat() if isinstance(updated_document_signer.get("created_at"), datetime) else updated_document_signer.get("created_at", ""),
                "lastModifiedBy": updated_document_signer.get("last_modified_by", ""),
                "lastModified": updated_document_signer.get("last_modified_at", "").isoformat() if isinstance(updated_document_signer.get("last_modified_at"), datetime) else updated_document_signer.get("last_modified_at", ""),
                "status": updated_document_signer.get("status", "")
            }
            
            logger.info("publish_signer_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, id_or_code=idOrCode)
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("publish_signer_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True, id_or_code=idOrCode)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UnpublishSignerAPI(Resource):
    """API for unpublishing a signer by setting status to inactive"""
    
    def put(self, idOrCode):
        bind_contextvars(task="UnpublishSignerAPI")
        start_t = time.time()
        try:
            query = {}
            if ObjectId.is_valid(idOrCode):
                query['_id'] = ObjectId(idOrCode)
            else:
                query['signer_id'] = idOrCode

            document_signer = document_signer_collection.find_one(query)
            if not document_signer:
                logger.error("unpublish_signer_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Signer with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message=f"Signer with idOrCode {idOrCode} not found")
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
            
            result = document_signer_collection.update_one(query, update_data)
            if result.modified_count == 0 and document_signer['status'] != "INACTIVE":
                logger.error("unpublish_signer_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to unpublish document signer", "event.duration": time.time()-start_t, "event.status": "failure"}, id_or_code=idOrCode)
                response = make_response(data=None, code=2000, message="Failed to unpublish document signer")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            updated_document_signer = document_signer_collection.find_one(query)
            updated_document_signer['_id'] = str(updated_document_signer['_id'])
            
            response_data = {
                "code": updated_document_signer.get("signer_id", ""),
                "name": updated_document_signer.get("signer_name", ""),
                "description": updated_document_signer.get("description", ""),
                "createdBy": updated_document_signer.get("created_by", ""),
                "createdDate": updated_document_signer.get("created_at", "").isoformat() if isinstance(updated_document_signer.get("created_at"), datetime) else updated_document_signer.get("created_at", ""),
                "lastModifiedBy": updated_document_signer.get("last_modified_by", ""),
                "lastModified": updated_document_signer.get("last_modified_at", "").isoformat() if isinstance(updated_document_signer.get("last_modified_at"), datetime) else updated_document_signer.get("last_modified_at", ""),
                "status": updated_document_signer.get("status", "")
            }
            
            logger.info("unpublish_signer_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, id_or_code=idOrCode)
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("unpublish_signer_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True, id_or_code=idOrCode)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class SearchSignerAPI(Resource):
    """API for searching signer records with pagination"""
    
    def post(self, page: int, quantity: int) -> Dict[str, Any]:
        """Handle POST request to search signer records with pagination.

        Args:
            page: Page number (1-based).
            quantity: Number of records per page.

        Returns:
            Response with search results, total count, or error message.
        """
        parser = reqparse.RequestParser()
        parser.add_argument('filterText', type=str, required=False, default="")
        parser.add_argument('Status', type=str, required=False, default="")
        args = parser.parse_args()

        bind_contextvars(task="SearchSignerAPI")
        start_t = time.time()
        try:
            page = int(page)
            quantity = int(quantity)
            
            if page < 1 or quantity < 1:
                logger.error("search_signers_failed", action="post", **{"error.code": "400-VAL", "error.message": "Page and quantity must be positive integers", "event.duration": time.time()-start_t, "event.status": "failure"}, page=page, quantity=quantity)
                response = make_response(data=None, code=1000, message="Page and quantity must be positive integers")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            query = {}            
            if args['filterText']:
                query['$or'] = [
                    {'signer_id': {'$regex': args['filterText'], '$options': 'i'}},
                    {'signer_name': {'$regex': args['filterText'], '$options': 'i'}},
                    {'description': {'$regex': args['filterText'], '$options': 'i'}}
                ]
            if args['Status']:
                query['status'] = args['Status']
          
            skip = (page - 1) * quantity

            total_count = document_signer_collection.count_documents(query)
            logger.debug("search_signers", action="post", total_count=total_count, **{"event.duration": time.time()-start_t})
            document_signers = list(document_signer_collection.find(query))
            document_signers.sort(key=lambda x: vi_sort_key(x.get("signer_name", "")))
            document_signers = document_signers[skip:skip + quantity]
            logger.debug("search_signers", action="post", found_count=len(document_signers), **{"event.duration": time.time()-start_t})

            models = []
            for doc_signer in document_signers:
                model = {
                    "code": doc_signer.get("signer_id", ""),
                    "name": doc_signer.get("signer_name", ""),
                    "description": doc_signer.get("description", ""),
                    "createdBy": doc_signer.get("created_by", "admin"),
                    "createdDate": doc_signer.get("created_at", "").isoformat() if isinstance(doc_signer.get("created_at"), datetime) else doc_signer.get("created_at", ""),
                    "lastModifiedBy": doc_signer.get("last_modified_by", "admin"),
                    "lastModified": doc_signer.get("last_modified_at", "").isoformat() if isinstance(doc_signer.get("last_modified_at"), datetime) else doc_signer.get("last_modified_at", ""),
                    "status": doc_signer.get("status", "")                    
                }
                models.append(model)

            response_data = {
                "count": total_count,
                "models": models
            }

            logger.info("search_signers_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(models), page=page, quantity=quantity, total=total_count)
            return make_response(
                data=response_data,
                code=0,
                message="Document signers retrieved successfully"
            ), 200

        except PyMongoError as e:
            logger.error("search_signers_failed", action="post", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("search_signers_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class SignerInUseAPI(Resource):
    """API for checking if a signer is referenced by any documents"""
    
    def get(self):
        bind_contextvars(task="SignerInUseAPI")
        start_t = time.time()
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('signer_id', type=str, required=True, location='args', help='Signer ID is required')
            args = parser.parse_args()
            
            signer_id = args['signer_id']
            
            law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
            
            query = {"signer_ids": signer_id}
            
            total = law_documents_collection.count_documents(query)
            in_use = total > 0
            
            result = {
                "in_use": in_use,
                "total": total
            }
            
            logger.info("check_signer_in_use_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, signer_id=signer_id, in_use=in_use, total_documents=total)
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("check_signer_in_use_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


api.add_resource(ListSignerAPI, '/signer/get')
api.add_resource(GetByCodeSignerAPI, '/signer/<idOrCode>')
api.add_resource(CreateSignerAPI, '/signer/create')
api.add_resource(UpdateSignerAPI, '/signer/update/<idOrCode>')
api.add_resource(DeleteSignerAPI, '/signer/delete/<idOrCode>')
api.add_resource(PublishSignerAPI, '/signer/published/<idOrCode>')
api.add_resource(UnpublishSignerAPI, '/signer/unpublished/<idOrCode>')
api.add_resource(SearchSignerAPI, '/signer/<page>/<quantity>')
api.add_resource(SignerInUseAPI, '/signer/in-use')

