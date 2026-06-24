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
from pyvi import ViUtils

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from services.api import api
from services.api.utils import make_response
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
logger = structlog.get_logger()



# Connect MongoDB
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
document_type_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_TYPE_COLLECTION_NAME]
documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]

def vi_sort_key(text):
    text = text.lower()
    text = ViUtils.remove_accents(text)
    return text

class ListDocumentTypeAPI(Resource):
    """API for listing all document type records"""
    
    def get(self):
        bind_contextvars(task="ListDocumentTypeAPI")
        start_t = time.time()
        try:
            document_types = list(document_type_collection.find())
            doc_type_name_asc = sorted(document_types, key=lambda x: vi_sort_key(x.get("doc_type_name", "")))
            
            result = []
            for doc_type in doc_type_name_asc:                
                result.append({
                    "code": doc_type.get("type_id", ""),
                    "name": doc_type.get("doc_type_name", ""),
                    "createdBy": doc_type.get("created_by", ""),
                    "createdDate": doc_type.get("created_at", "").isoformat() if isinstance(doc_type.get("created_at"), datetime) else doc_type.get("created_at", ""),
                    "lastModifiedBy": doc_type.get("last_modified_by", ""),
                    "lastModified": doc_type.get("last_modified_at", "").isoformat() if isinstance(doc_type.get("last_modified_at"), datetime) else doc_type.get("last_modified_at", ""),
                    "status": doc_type.get("status", "")
                })
            
            logger.info("list_document_type_success", action="get", count=len(result), **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("list_document_type_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetByCodeDocumentTypeAPI(Resource):
    """API for getting document type by code"""
    
    def get(self, idOrCode):
        bind_contextvars(task="GetByCodeDocumentTypeAPI")
        start_t = time.time()
        try:
            if ObjectId.is_valid(idOrCode):
                query = {'_id': ObjectId(idOrCode)}
            else:
                query = {'type_id': idOrCode}
            
            document_types = list(document_type_collection.find(query).sort("doc_type_name", 1))
            
            result = []
            for doc_type in document_types:
                doc_type['_id'] = str(doc_type['_id'])
                result.append({
                    "code": doc_type.get("type_id", ""),
                    "name": doc_type.get("doc_type_name", ""),
                    "createdBy": doc_type.get("created_by", ""),
                    "createdDate": doc_type.get("created_at", "").isoformat() if isinstance(doc_type.get("created_at"), datetime) else doc_type.get("created_at", ""),
                    "lastModifiedBy": doc_type.get("last_modified_by", ""),
                    "lastModified": doc_type.get("last_modified_at", "").isoformat() if isinstance(doc_type.get("last_modified_at"), datetime) else doc_type.get("last_modified_at", ""),
                    "status": doc_type.get("status", ""),
                    "description": doc_type.get("description", "")
                })
            
            logger.info("get_by_code_document_type_success", action="get", count=len(result), **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("get_by_code_document_type_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class CreateDocumentTypeAPI(Resource):
    """API for creating a new document type record"""
    
    def post(self):
        bind_contextvars(task="CreateDocumentTypeAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('code', type=str, required=False, nullable=False, help="Code is optional")
        parser.add_argument('name', type=str, required=True, nullable=False, help="Name is required")
        parser.add_argument('description', type=str, required=False, nullable=False, help="Description is optional")
        args = parser.parse_args()

        type_id = args['code']
        doc_type_name = args['name']
        description = args['description']

        if type_id:
            type_id = type_id.strip()
        
        if doc_type_name:
            doc_type_name = doc_type_name.strip()
            
        if description:
            description = description.strip()
        else:
            description = ""
        
        try:
            if not type_id:
                type_id = str(uuid.uuid4())
            
            # Check if type_id exists
            id_exists = document_type_collection.find_one({'type_id': type_id})
            
            # Check if doc_type_name exists (case-insensitive)
            name_exists = document_type_collection.find_one({'doc_type_name': {
                '$regex': f'^{re.escape(doc_type_name)}$',
                '$options': 'i'
            }})

            if id_exists or name_exists:
                msg_detail = ""
                if id_exists:
                    msg_detail = f"Document type with type_id {type_id} already exists. "
                if name_exists:
                    msg_detail += f"Document type with doc_type_name {doc_type_name} already exists."

                logger.error("create_document_type_failed", action="post", type_id=type_id, doc_type_name=doc_type_name, **{"error.code": "400-VAL", "error.message": msg_detail.strip(), "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=msg_detail.strip())
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = "system" 
            
            document_type = {
                "type_id": type_id,
                "doc_type_name": doc_type_name,
                "description": description,
                "created_by": current_user,
                "created_at": current_time,
                "last_modified_by": current_user,
                "last_modified_at": current_time,
                "status": "ACTIVE"
            }
            
            result = document_type_collection.insert_one(document_type)
            logger.info("create_document_type_success", action="post", type_id=type_id, inserted_id=str(result.inserted_id), **{"event.status": "success", "event.duration": time.time() - start_t})
            
            document_type['_id'] = str(result.inserted_id)

            response_data = {
                "code": document_type.get("type_id", ""),
                "name": document_type.get("doc_type_name", ""),
                "description": document_type.get("description", ""),
                "createdBy": document_type.get("created_by", ""),
                "createdDate": document_type.get("created_at", "").isoformat() if isinstance(document_type.get("created_at"), datetime) else document_type.get("created_at", ""),
                "lastModifiedBy": document_type.get("last_modified_by", ""),
                "lastModified": document_type.get("last_modified_at", "").isoformat() if isinstance(document_type.get("last_modified_at"), datetime) else document_type.get("last_modified_at", ""),
                "status": document_type.get("status", "")
            }
            return make_response(data=response_data, code=0, message="Success"), 201
            
        except Exception as e:
            logger.error("create_document_type_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UpdateDocumentTypeAPI(Resource):
    """API for updating an existing document type record"""
    
    def put(self, idOrCode):
        bind_contextvars(task="UpdateDocumentTypeAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('code', type=str, required=False, nullable=False, help="Document type ID is optional")
        parser.add_argument('name', type=str, required=True, nullable=False, help="Document type name is required")
        parser.add_argument('description', type=str, required=False, nullable=False, help="Description is optional")
        args = parser.parse_args()

        type_id = args['code']
        doc_type_name = args['name']
        description = args['description']

        if type_id:
            type_id = type_id.strip()
        
        if doc_type_name:
            doc_type_name = doc_type_name.strip()
            
        if description:
            description = description.strip()
        else:
            description = ""
        
        try:
            query = {}
            if ObjectId.is_valid(idOrCode):
                query['_id'] = ObjectId(idOrCode)
            else:
                query['type_id'] = idOrCode

            document_type = document_type_collection.find_one(query)
            if not document_type:
                logger.error("update_document_type_failed", action="put", idOrCode=idOrCode, **{"error.code": "404-NOTFOUND", "error.message": f"Document type with idOrCode {idOrCode} not found", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=f"Document type with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            if type_id and type_id != document_type['type_id']:
                logger.error("update_document_type_failed", action="put", provided_id=type_id, actual_id=document_type['type_id'], **{"error.code": "400-VAL", "error.message": f"Provided type_id {type_id} does not match document type code", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=f"Provided type_id {type_id} does not match document type code")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            # Check for duplicate name (case-insensitive) excluding current record
            existing_name = document_type_collection.find_one({
                'doc_type_name': {
                    '$regex': f'^{re.escape(doc_type_name)}$',
                    '$options': 'i'
                },
                'type_id': {'$ne': document_type['type_id']}
            })
            
            if existing_name:
                logger.error("update_document_type_failed", action="put", doc_type_name=doc_type_name, **{"error.code": "400-VAL", "error.message": f"Document type with doc_type_name {doc_type_name} already exists", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=f"Document type with doc_type_name {doc_type_name} already exists")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = "system"
            
            update_data = {
                "$set": {
                    "doc_type_name": doc_type_name,
                    "description": description,
                    "last_modified_by": current_user,
                    "last_modified_at": current_time
                }
            }
            
            result = document_type_collection.update_one(query, update_data)
            if result.modified_count == 0:
                logger.error("update_document_type_failed", action="put", idOrCode=idOrCode, **{"error.code": "500-DB", "error.message": "Failed to update document type", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message="Failed to update document type")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500
                
            updated_document_type = document_type_collection.find_one(query)
            response_data = {
                "code": updated_document_type.get("type_id", ""),
                "name": updated_document_type.get("doc_type_name", ""),
                "description": updated_document_type.get("description", ""),
                "createdBy": updated_document_type.get("created_by", ""),
                "createdDate": updated_document_type.get("created_at", "").isoformat() if isinstance(updated_document_type.get("created_at"), datetime) else updated_document_type.get("created_at", ""),
                "lastModifiedBy": updated_document_type.get("last_modified_by", ""),
                "lastModified": updated_document_type.get("last_modified_at", "").isoformat() if isinstance(updated_document_type.get("last_modified_at"), datetime) else updated_document_type.get("last_modified_at", ""),
                "status": updated_document_type.get("status", "")
            }
            logger.info("update_document_type_success", action="put", idOrCode=idOrCode, **{"event.status": "success", "event.duration": time.time() - start_t})
            
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("update_document_type_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DeleteDocumentTypeAPI(Resource):
    """API for deleting a document type record"""
    
    def delete(self, idOrCode):
        bind_contextvars(task="DeleteDocumentTypeAPI")
        start_t = time.time()
        try:
            query = {}
            if ObjectId.is_valid(idOrCode):
                query['_id'] = ObjectId(idOrCode)
            else:
                query['type_id'] = idOrCode

            document_type = document_type_collection.find_one(query)
            if not document_type:
                logger.error("delete_document_type_failed", action="delete", idOrCode=idOrCode, **{"error.code": "404-NOTFOUND", "error.message": f"Document type with idOrCode {idOrCode} not found", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=f"Document type with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            result = document_type_collection.delete_one(query)
            if result.deleted_count == 0:
                logger.error("delete_document_type_failed", action="delete", idOrCode=idOrCode, **{"error.code": "500-DB", "error.message": "Failed to delete document type", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message="Failed to delete document type")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            logger.info("delete_document_type_success", action="delete", idOrCode=idOrCode, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(data=None, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("delete_document_type_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class PublishDocumentTypeAPI(Resource):
    """API for publishing a document type by setting status to active"""
    
    def put(self, idOrCode):
        bind_contextvars(task="PublishDocumentTypeAPI")
        start_t = time.time()
        try:
            query = {}
            if ObjectId.is_valid(idOrCode):
                query['_id'] = ObjectId(idOrCode)
            else:
                query['type_id'] = idOrCode

            document_type = document_type_collection.find_one(query)
            if not document_type:
                logger.error("publish_document_type_failed", action="put", idOrCode=idOrCode, **{"error.code": "404-NOTFOUND", "error.message": f"Document type with idOrCode {idOrCode} not found", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=f"Document type with idOrCode {idOrCode} not found")
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
            
            result = document_type_collection.update_one(query, update_data)
            if result.modified_count == 0 and document_type['status'] != "ACTIVE":
                logger.error("publish_document_type_failed", action="put", idOrCode=idOrCode, **{"error.code": "500-DB", "error.message": "Failed to publish document type", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message="Failed to publish document type")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            updated_document_type = document_type_collection.find_one(query)
            updated_document_type['_id'] = str(updated_document_type['_id'])
            
            response_data = {
                "code": updated_document_type.get("type_id", ""),
                "name": updated_document_type.get("doc_type_name", ""),
                "description": updated_document_type.get("description", ""),
                "createdBy": updated_document_type.get("created_by", ""),
                "createdDate": updated_document_type.get("created_at", "").isoformat() if isinstance(updated_document_type.get("created_at"), datetime) else updated_document_type.get("created_at", ""),
                "lastModifiedBy": updated_document_type.get("last_modified_by", ""),
                "lastModified": updated_document_type.get("last_modified_at", "").isoformat() if isinstance(updated_document_type.get("last_modified_at"), datetime) else updated_document_type.get("last_modified_at", ""),
                "status": updated_document_type.get("status", "")
            }
            
            logger.info("publish_document_type_success", action="put", idOrCode=idOrCode, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("publish_document_type_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UnpublishDocumentTypeAPI(Resource):
    """API for unpublishing a document type by setting status to inactive"""
    
    def put(self, idOrCode):
        bind_contextvars(task="UnpublishDocumentTypeAPI")
        start_t = time.time()
        try:
            query = {}
            if ObjectId.is_valid(idOrCode):
                query['_id'] = ObjectId(idOrCode)
            else:
                query['type_id'] = idOrCode

            document_type = document_type_collection.find_one(query)
            if not document_type:
                logger.error("unpublish_document_type_failed", action="put", idOrCode=idOrCode, **{"error.code": "404-NOTFOUND", "error.message": f"Document type with idOrCode {idOrCode} not found", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message=f"Document type with idOrCode {idOrCode} not found")
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
            
            result = document_type_collection.update_one(query, update_data)
            if result.modified_count == 0 and document_type['status'] != "INACTIVE":
                logger.error("unpublish_document_type_failed", action="put", idOrCode=idOrCode, **{"error.code": "500-DB", "error.message": "Failed to unpublish document type", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=2000, message="Failed to unpublish document type")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            updated_document_type = document_type_collection.find_one(query)
            updated_document_type['_id'] = str(updated_document_type['_id'])
            
            response_data = {
                "code": updated_document_type.get("type_id", ""),
                "name": updated_document_type.get("doc_type_name", ""),
                "description": updated_document_type.get("description", ""),
                "createdBy": updated_document_type.get("created_by", ""),
                "createdDate": updated_document_type.get("created_at", "").isoformat() if isinstance(updated_document_type.get("created_at"), datetime) else updated_document_type.get("created_at", ""),
                "lastModifiedBy": updated_document_type.get("last_modified_by", ""),
                "lastModified": updated_document_type.get("last_modified_at", "").isoformat() if isinstance(updated_document_type.get("last_modified_at"), datetime) else updated_document_type.get("last_modified_at", ""),
                "status": updated_document_type.get("status", "")
            }
            
            logger.info("unpublish_document_type_success", action="put", idOrCode=idOrCode, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("unpublish_document_type_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class SearchDocumentTypeAPI(Resource):
    """API for searching document type records with pagination"""
    
    def post(self, page: int, quantity: int) -> Dict[str, Any]:
        """Handle POST request to search document type records with pagination.

        Args:
            page: Page number (1-based).
            quantity: Number of records per page.

        Returns:
            Response with search results, total count, or error message.
        """
        bind_contextvars(task="SearchDocumentTypeAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('text', type=str, required=False, nullable=True, location='json', help="Search text")
        parser.add_argument('status', type=str, required=False, nullable=True, location='json', help="Document type status")
        args = parser.parse_args()

        text = args['text']
        status = args['status']
        
        try:
            page = int(page)
            quantity = int(quantity)
            
            if page < 1 or quantity < 1:
                logger.error("search_document_type_failed", action="post", page=page, quantity=quantity, **{"error.code": "400-VAL", "error.message": "Page and quantity must be positive integers", "event.status": "failure", "event.duration": time.time() - start_t})
                response = make_response(data=None, code=1000, message="Page and quantity must be positive integers")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            query = {}
            if text:
                query['$or'] = [
                    {'type_id': {'$regex': text, '$options': 'i'}},
                    {'doc_type_name': {'$regex': text, '$options': 'i'}},
                    {'description': {'$regex': text, '$options': 'i'}}
                ]
            if status:
                query['status'] = status

            skip = (page - 1) * quantity

            total_count = document_type_collection.count_documents(query)
            document_types = list(document_type_collection.find(query))
            document_types.sort(key=lambda x: vi_sort_key(x.get("doc_type_name", "")))
            document_types = document_types[skip:skip + quantity]

            models = []
            for doc_type in document_types:
                model = {
                    "code": doc_type.get("type_id", ""),
                    "name": doc_type.get("doc_type_name", ""),
                    "description": doc_type.get("description", ""),
                    "createdBy": doc_type.get("created_by", "admin"),
                    "createdDate": doc_type.get("created_at", "").isoformat() if isinstance(doc_type.get("created_at"), datetime) else doc_type.get("created_at", ""),
                    "lastModifiedBy": doc_type.get("last_modified_by", "admin"),
                    "lastModified": doc_type.get("last_modified_at", "").isoformat() if isinstance(doc_type.get("last_modified_at"), datetime) else doc_type.get("last_modified_at", ""),
                    "status": doc_type.get("status", ""),
                    "text": text if text else ""
                }
                models.append(model)

            response_data = {
                "count": total_count,
                "models": models
            }

            logger.info("search_document_type_success", action="post", count=len(models), page=page, quantity=quantity, total=total_count, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(
                data=response_data,
                code=0,
                message="Document types retrieved successfully"
            ), 200

        except PyMongoError as e:
            logger.error("search_document_type_failed", action="post", **{"error.code": "500-DB", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("search_document_type_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class StaticDocumentTypeAPI(Resource):
    def get(self):
        bind_contextvars(task="StaticDocumentTypeAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('code', type=str, required=False, location='args', help="Filter by document type code")
        args = parser.parse_args()
        code_filter = args.get('code')
        
        try:
            # Lấy tất cả loại văn bản hợp lệ (luôn lấy tất cả để tính %)
            all_document_types = list(document_type_collection.find({
                "doc_type_name": {"$exists": True, "$ne": ""}
            }).sort("doc_type_name", 1))
            
            # Ánh xạ theo type_id (KHÔNG phải _id)
            all_doc_type_map = {
                doc_type["type_id"]: doc_type
                for doc_type in all_document_types
                if "type_id" in doc_type
            }
            
            if not all_doc_type_map:
                logger.debug("static_document_type_success", action="get", **{"event.status": "success", "event.duration": time.time() - start_t})
                return make_response(data=[], code=0, message="No document types found"), 200
            
            # Pipeline đếm số lượng văn bản theo loại
            pipeline = [
                {
                    "$match": {
                        "type_id": {
                            "$exists": True, 
                            "$ne": None, 
                            "$in": list(all_doc_type_map.keys())
                        }
                    }
                },
                {
                    "$group": {
                        "_id": "$type_id",
                        "document_count": {"$sum": 1}
                    }
                }
            ]
            
            # Thực thi pipeline
            doc_counts = {}
            total_documents = 0
            
            for doc in documents_collection.aggregate(pipeline):
                doc_id = doc['_id']
                doc_counts[doc_id] = doc['document_count']
                total_documents += doc['document_count']
            
            if code_filter:
                doc_type_map = {k: v for k, v in all_doc_type_map.items() if k == code_filter}
            else:
                doc_type_map = all_doc_type_map
            
            if not doc_type_map:
                logger.debug("static_document_type_success", action="get", **{"event.status": "success", "event.duration": time.time() - start_t})
                return make_response(data=[], code=0, message=f"No document type found with code: {code_filter}"), 200
            
            # Chuẩn bị kết quả trả về
            result = []
            for type_id, doc_type in doc_type_map.items():
                count = doc_counts.get(type_id, 0)
                percentage = (count / total_documents * 100) if total_documents > 0 else 0
                
                result.append({
                    "code": type_id,
                    "name": doc_type.get("doc_type_name", ""),
                    "documentCount": count,
                    "documentCountPercent": round(percentage, 2),
                    "createdBy": doc_type.get("created_by", "system"),
                    "createdDate": doc_type.get("created_at", ""),
                    "lastModifiedBy": doc_type.get("last_modified_by", "system"),
                    "lastModified": doc_type.get("last_modified_at", ""),
                    "status": doc_type.get("status", "")
                })
            
            # Sắp xếp theo số lượng giảm dần
            result.sort(key=lambda x: x["documentCount"], reverse=True)
            
            logger.info("static_document_type_success", action="get", count=len(result), total_docs=total_documents, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(data=result, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("static_document_type_failed", action="get", **{"error.code": "500-DB", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("static_document_type_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DocumentTypeInUseAPI(Resource):
    """API for checking if a document type is referenced by any documents"""
    
    def get(self):
        bind_contextvars(task="DocumentTypeInUseAPI")
        start_t = time.time()
        try:
            parser = reqparse.RequestParser()
            parser.add_argument('doc_type_id', type=str, required=True, location='args', help='Document type ID is required')
            args = parser.parse_args()
            
            type_id = args['doc_type_id']
            
            query = {"type_id": type_id}
            
            total = documents_collection.count_documents(query)
            in_use = total > 0
            
            result = {
                "in_use": in_use,
                "total": total
            }
            
            logger.info("document_type_in_use_success", action="get", type_id=type_id, in_use=in_use, total_documents=total, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("document_type_in_use_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


api.add_resource(ListDocumentTypeAPI, '/document-type/get')
api.add_resource(GetByCodeDocumentTypeAPI, '/document-type/<idOrCode>')
api.add_resource(CreateDocumentTypeAPI, '/document-type/create')
api.add_resource(UpdateDocumentTypeAPI, '/document-type/update/<idOrCode>')
api.add_resource(DeleteDocumentTypeAPI, '/document-type/delete/<idOrCode>')
api.add_resource(PublishDocumentTypeAPI, '/document-type/published/<idOrCode>')
api.add_resource(UnpublishDocumentTypeAPI, '/document-type/unpublished/<idOrCode>')
api.add_resource(SearchDocumentTypeAPI, '/document-type/<page>/<quantity>')
api.add_resource(StaticDocumentTypeAPI, '/document-type/static')
api.add_resource(DocumentTypeInUseAPI, '/document-type/in-use')
