from core.common.mongo.client import get_mongo_client
import structlog
import sys
import os
import re
from flask_restful import Resource, reqparse
from flask import request
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
from structlog.contextvars import bind_contextvars
import time

logger = structlog.get_logger()



client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_doc_category_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_CATEGORY_COLLECTION_NAME]


def _format_doc_category(dc: dict) -> dict:
    """Format a document category document for API response."""
    def format_datetime(dt_value):
        """Convert datetime to ISO format string, or return string as-is"""
        if isinstance(dt_value, datetime):
            return dt_value.isoformat()
        return dt_value if dt_value else ''
    
    return {
        'code': dc.get('category_id', ''),
        'name': dc.get('doc_category', ''),
        'status': dc.get('status', ''),
        'documentCount': 0,
        'createdBy': dc.get('created_by', ''),
        'createdAt': format_datetime(dc.get('created_at')),
        'updatedBy': dc.get('last_modified_by', ''),
        'updatedAt': format_datetime(dc.get('last_modified_at'))
    }


class DocumentCategoryListAPI(Resource):
    def get(self):
        page_str = request.args.get('page', '1')
        limit_str = request.args.get('limit', '10')
        search_term = request.args.get('search', '')
        sort_field = request.args.get('sort', 'name')
        type = request.args.get('type', '')

        bind_contextvars(task="DocumentCategoryListAPI")
        start_t = time.time()
        try:
            page = int(page_str)
        except (ValueError, TypeError):
            return make_response(data=None, code=1000, message=f"Invalid value for 'page': '{page_str}'. Must be a valid integer."), 400

        try:
            limit = int(limit_str)
        except (ValueError, TypeError):
            return make_response(data=None, code=1000, message=f"Invalid value for 'limit': '{limit_str}'. Must be a valid integer."), 400

        page = max(1, page)
        limit = min(100, max(1, limit))

        try:
            query = {}
            if search_term:
                query['$or'] = [
                    {'category_id': {'$regex': search_term, '$options': 'i'}},
                    {'doc_category': {'$regex': search_term, '$options': 'i'}}
                ]

            total = law_doc_category_collection.count_documents(query)

            sort_key = 'doc_category'
            sort_direction = 1

            if sort_field:
                if sort_field.startswith('-'):
                    sort_direction = -1
                    field = sort_field[1:]
                else:
                    sort_direction = 1
                    field = sort_field

                if field in ['name', 'docCategory', 'doc_category']:
                    sort_key = 'doc_category'
                elif field in ['code', 'docCategoryId', 'doc_category_id']:
                    sort_key = 'category_id'
                elif field in ['createdAt', 'created_at', 'createdDate', 'created_date']:
                    sort_key = 'created_at'
                elif field in ['updatedAt', 'updated_at', 'updatedDate', 'updated_date', 'lastModified', 'last_modified']:
                    sort_key = 'last_modified_at'

            skip = (page - 1) * limit
            cursor = (law_doc_category_collection.find(query)
                    .sort(sort_key, sort_direction)
                    .skip(skip)
                    .limit(limit))
            items = []
            for dc in cursor:
                if type != "REPORT":
                    items.append(_format_doc_category(dc))
                else:
                    item = _format_doc_category(dc)
                    item['documentCount'] = law_documents_collection.count_documents({'category_id': dc['category_id']})
                    items.append(item)
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

            logger.info("get_document_categories_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(items), page=page, limit=limit, search=search_term, sort=sort_field)
            return make_response(data=response_data, code=0, message="Success"), 200

        except PyMongoError as e:
            logger.error("get_document_categories_failed", action="get", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("get_document_categories_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetByIdDocumentCategoryAPI(Resource):
    """API for getting document category by ObjectId or doc_category_id"""
    
    def get(self, idOrCode):
        bind_contextvars(task="GetByIdDocumentCategoryAPI")
        start_t = time.time()
        try:
            if ObjectId.is_valid(idOrCode):
                query = {'_id': ObjectId(idOrCode)}
            else:
                query = {'category_id': idOrCode}

            doc_category = law_doc_category_collection.find_one(query)

            if not doc_category:
                logger.error("get_document_category_by_id_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": f"Document category with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=2000, message=f"Document category with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            response_data = _format_doc_category(doc_category)
            logger.info("get_document_category_by_id_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, idOrCode=idOrCode)
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("get_document_category_by_id_failed", action="get", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("get_document_category_by_id_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetByDocIdDocumentCategoryAPI(Resource):
    """API for getting document category by doc_id (looks up the document's doc_category_id)"""
    
    def get(self, docId):
        bind_contextvars(task="GetByDocIdDocumentCategoryAPI")
        start_t = time.time()
        try:
            doc = law_documents_collection.find_one({'doc_id': docId})
            if not doc:
                logger.error("get_document_category_by_doc_id_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": f"Document with doc_id {docId} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, doc_id=docId)
                response = make_response(data=None, code=2000, message=f"Document with doc_id {docId} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            doc_category_id = doc.get('category_id')
            if not doc_category_id:
                logger.error("get_document_category_by_doc_id_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": f"Document {docId} has no category assigned", "event.duration": time.time()-start_t, "event.status": "failure"}, doc_id=docId)
                response = make_response(data=None, code=2000, message=f"Document {docId} has no category assigned")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            doc_category = law_doc_category_collection.find_one({'category_id': doc_category_id})
            if not doc_category:
                logger.error("get_document_category_by_doc_id_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": f"Document category {doc_category_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, doc_category_id=doc_category_id)
                response = make_response(data=None, code=2000, message=f"Document category {doc_category_id} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            response_data = _format_doc_category(doc_category)
            logger.info("get_document_category_by_doc_id_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, doc_id=docId)
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("get_document_category_by_doc_id_failed", action="get", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("get_document_category_by_doc_id_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class CreateDocumentCategoryAPI(Resource):
    """API for creating a new document category (should only have 2 categories total)"""
    
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str, required=True, location='json', help="Name is required")
        parser.add_argument('status', type=str, required=False, choices=('ACTIVE', 'INACTIVE'), location='json', default='ACTIVE', help="Status is optional (ACTIVE or INACTIVE), defaults to ACTIVE")
        args = parser.parse_args()

        doc_category_name = args['name']
        status = args['status']

        if doc_category_name:
            doc_category_name = doc_category_name.strip()
        
        bind_contextvars(task="CreateDocumentCategoryAPI")
        start_t = time.time()
        try:
            # Check for existing document category (case-insensitive)
            existing = law_doc_category_collection.find_one({'doc_category': {'$regex': f'^{re.escape(doc_category_name)}$', '$options': 'i'}})

            if existing:
                logger.error("create_document_category_failed", action="post", **{"error.code": "400-VAL", "error.message": f"Document category '{doc_category_name}' already exists", "event.duration": time.time()-start_t, "event.status": "failure"}, name=doc_category_name)
                response = make_response(data=None, code=2000, message=f"Document category '{doc_category_name}' already exists")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            max_entry = law_doc_category_collection.find_one(
                {},
                sort=[('category_id', -1)]
            )
            if max_entry and max_entry.get('category_id'):
                last_id = max_entry['category_id']
                seq_part = last_id[6:-2]
                next_seq = int(seq_part) + 1
            else:
                next_seq = 1
            
            now = datetime.now()
            year_month = now.strftime("%Y%m")
            doc_category_id = f"{year_month}{str(next_seq).zfill(6)}QP"

            current_time = now.strftime("%Y-%m-%d %H:%M:%S")
            current_user = "system"
            
            doc_category = {
                "category_id": doc_category_id,
                "doc_category": doc_category_name,
                "status": status,
                "created_by": current_user,
                "created_at": current_time,
                "last_modified_by": current_user,
                "last_modified_at": current_time
            }
            
            result = law_doc_category_collection.insert_one(doc_category)
            logger.info("create_document_category_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, id=doc_category_id, inserted_id=str(result.inserted_id))
            
            response_data = _format_doc_category(doc_category)
            return make_response(data=response_data, code=0, message="Success"), 201
            
        except PyMongoError as e:
            logger.error("create_document_category_failed", action="post", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("create_document_category_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UpdateDocumentCategoryAPI(Resource):
    """API for updating an existing document category record"""
    
    def put(self, idOrCode):
        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str, required=True, location='json', help="Name is required")
        args = parser.parse_args()

        doc_category_name = args['name']
        
        if doc_category_name:
            doc_category_name = doc_category_name.strip()

        bind_contextvars(task="UpdateDocumentCategoryAPI")
        start_t = time.time()
        try:
            if ObjectId.is_valid(idOrCode):
                query = {'_id': ObjectId(idOrCode)}
            else:
                query = {'category_id': idOrCode}

            doc_category = law_doc_category_collection.find_one(query)
            if not doc_category:
                logger.error("update_document_category_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Document category with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=2000, message=f"Document category with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            name_conflict = law_doc_category_collection.find_one({
                'doc_category': {
                    '$regex': f'^{re.escape(doc_category_name)}$',
                    '$options': 'i'
                },
                '_id': {'$ne': doc_category['_id']}
            })
            if name_conflict:
                logger.error("update_document_category_failed", action="put", **{"error.code": "400-VAL", "error.message": f"Document category '{doc_category_name}' already exists", "event.duration": time.time()-start_t, "event.status": "failure"}, name=doc_category_name)
                response = make_response(data=None, code=2000, message=f"Document category '{doc_category_name}' already exists")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            old_category_name = doc_category.get('doc_category')
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = "system"
            
            update_fields = {
                "doc_category": doc_category_name,
                "last_modified_by": current_user,
                "last_modified_at": current_time
            }
            
            update_data = {"$set": update_fields}
            
            result = law_doc_category_collection.update_one(query, update_data)
            if result.modified_count == 0 and result.matched_count == 0:
                logger.error("update_document_category_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to update document category", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=2000, message="Failed to update document category")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            if old_category_name != doc_category_name:
                law_documents_collection.update_many(
                    {'category_id': doc_category['category_id']},
                    {'$set': {'doc_category': doc_category_name}}
                )
                logger.info("update_document_category_success", action="put", old_name=old_category_name, new_name=doc_category_name)
                
            updated_doc_category = law_doc_category_collection.find_one(query)
            response_data = _format_doc_category(updated_doc_category)
            logger.info("update_document_category_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, idOrCode=idOrCode)
            
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("update_document_category_failed", action="put", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("update_document_category_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DeleteDocumentCategoryAPI(Resource):
    """API for deleting a document category record"""
    
    def delete(self, idOrCode):
        bind_contextvars(task="DeleteDocumentCategoryAPI")
        start_t = time.time()
        try:
            if ObjectId.is_valid(idOrCode):
                query = {'_id': ObjectId(idOrCode)}
            else:
                query = {'category_id': idOrCode}

            doc_category = law_doc_category_collection.find_one(query)
            if not doc_category:
                logger.error("delete_document_category_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": f"Document category with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=2000, message=f"Document category with idOrCode {idOrCode} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            doc_category_id = doc_category.get('category_id')
            
            docs_using_category = law_documents_collection.count_documents({'category_id': doc_category_id})
            if docs_using_category > 0:
                logger.error("delete_document_category_failed", action="delete", **{"error.code": "400-VAL", "error.message": f"Cannot delete: {docs_using_category} documents are using this category", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode, docs_count=docs_using_category)
                response = make_response(data=None, code=2000, message=f"Cannot delete: {docs_using_category} documents are using this category")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400
            
            result = law_doc_category_collection.delete_one(query)
            if result.deleted_count == 0:
                logger.error("delete_document_category_failed", action="delete", **{"error.code": "500-DB", "error.message": "Failed to delete document category", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=2000, message="Failed to delete document category")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            logger.info("delete_document_category_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"}, idOrCode=idOrCode)
            return make_response(data=None, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("delete_document_category_failed", action="delete", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("delete_document_category_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class PublishDocumentCategoryAPI(Resource):
    """API for publishing a document category by setting status to active"""
    
    def put(self, idOrCode):
        bind_contextvars(task="PublishDocumentCategoryAPI")
        start_t = time.time()
        try:
            if ObjectId.is_valid(idOrCode):
                query = {'_id': ObjectId(idOrCode)}
            else:
                query = {'category_id': idOrCode}

            doc_category = law_doc_category_collection.find_one(query)
            if not doc_category:
                logger.error("publish_document_category_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Document category with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=2000, message=f"Document category with idOrCode {idOrCode} not found")
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
            
            result = law_doc_category_collection.update_one(query, update_data)
            if result.modified_count == 0 and doc_category.get('status') != "ACTIVE":
                logger.error("publish_document_category_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to publish document category", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=2000, message="Failed to publish document category")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            updated_doc_category = law_doc_category_collection.find_one(query)
            response_data = _format_doc_category(updated_doc_category)
            
            logger.info("publish_document_category_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, idOrCode=idOrCode)
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("publish_document_category_failed", action="put", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("publish_document_category_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UnpublishDocumentCategoryAPI(Resource):
    """API for unpublishing a document category by setting status to inactive"""
    
    def put(self, idOrCode):
        bind_contextvars(task="UnpublishDocumentCategoryAPI")
        start_t = time.time()
        try:
            if ObjectId.is_valid(idOrCode):
                query = {'_id': ObjectId(idOrCode)}
            else:
                query = {'category_id': idOrCode}

            doc_category = law_doc_category_collection.find_one(query)
            if not doc_category:
                logger.error("unpublish_document_category_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Document category with idOrCode {idOrCode} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=2000, message=f"Document category with idOrCode {idOrCode} not found")
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
            
            result = law_doc_category_collection.update_one(query, update_data)
            if result.modified_count == 0 and doc_category.get('status') != "INACTIVE":
                logger.error("unpublish_document_category_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to unpublish document category", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=2000, message="Failed to unpublish document category")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            updated_doc_category = law_doc_category_collection.find_one(query)
            response_data = _format_doc_category(updated_doc_category)
            
            logger.info("unpublish_document_category_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, idOrCode=idOrCode)
            return make_response(data=response_data, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("unpublish_document_category_failed", action="put", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("unpublish_document_category_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class AssignDocumentCategoryAPI(Resource):
    """API for assigning a category to a document"""
    
    def put(self, docId):
        parser = reqparse.RequestParser()
        parser.add_argument('categoryId', type=str, required=True, location='json', help="categoryId is required")
        args = parser.parse_args()

        category_id = args['categoryId']
        
        bind_contextvars(task="AssignDocumentCategoryAPI")
        start_t = time.time()
        try:
            doc = law_documents_collection.find_one({'doc_id': docId})
            if not doc:
                logger.error("assign_document_category_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Document with doc_id {docId} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, doc_id=docId)
                response = make_response(data=None, code=2000, message=f"Document with doc_id {docId} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            doc_category = law_doc_category_collection.find_one({'category_id': category_id})
            if not doc_category:
                logger.error("assign_document_category_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Document category with id {category_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, category_id=category_id)
                response = make_response(data=None, code=2000, message=f"Document category with id {category_id} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            if doc_category.get('status') != 'ACTIVE':
                logger.error("assign_document_category_failed", action="put", **{"error.code": "400-VAL", "error.message": f"Document category {category_id} is not active", "event.duration": time.time()-start_t, "event.status": "failure"}, category_id=category_id)
                response = make_response(data=None, code=2000, message=f"Document category {category_id} is not active")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            result = law_documents_collection.update_one(
                {'doc_id': docId},
                {'$set': {
                    'category_id': category_id,
                    'doc_category': doc_category.get('doc_category')
                }}
            )
            
            if result.modified_count == 0 and result.matched_count == 0:
                logger.error("assign_document_category_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to assign category", "event.duration": time.time()-start_t, "event.status": "failure"}, doc_id=docId)
                response = make_response(data=None, code=2000, message="Failed to assign category")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            logger.info("assign_document_category_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, category_id=category_id, doc_id=docId)
            return make_response(data={'docId': docId, 'categoryId': category_id, 'categoryName': doc_category.get('doc_category')}, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("assign_document_category_failed", action="put", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("assign_document_category_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UnassignDocumentCategoryAPI(Resource):
    """API for removing category assignment from a document"""
    
    def put(self, docId):
        bind_contextvars(task="UnassignDocumentCategoryAPI")
        start_t = time.time()
        try:
            doc = law_documents_collection.find_one({'doc_id': docId})
            if not doc:
                logger.error("unassign_document_category_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Document with doc_id {docId} not found", "event.duration": time.time()-start_t, "event.status": "failure"}, doc_id=docId)
                response = make_response(data=None, code=2000, message=f"Document with doc_id {docId} not found")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            result = law_documents_collection.update_one(
                {'doc_id': docId},
                {'$unset': {'category_id': ''}}
            )
            
            if result.modified_count == 0 and result.matched_count == 0:
                logger.error("unassign_document_category_failed", action="put", **{"error.code": "500-DB", "error.message": "Failed to unassign category", "event.duration": time.time()-start_t, "event.status": "failure"}, doc_id=docId)
                response = make_response(data=None, code=2000, message="Failed to unassign category")
                response["error_code"] = "500-DB"
                response["status"] = False
                return response, 500

            logger.info("unassign_document_category_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, doc_id=docId)
            return make_response(data={'docId': docId}, code=0, message="Success"), 200
            
        except PyMongoError as e:
            logger.error("unassign_document_category_failed", action="put", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2001, message="Database error")
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("unassign_document_category_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


api.add_resource(DocumentCategoryListAPI, '/document_category/list')
api.add_resource(GetByIdDocumentCategoryAPI, '/document_category/get/<idOrCode>')
api.add_resource(GetByDocIdDocumentCategoryAPI, '/document_category/get_by_doc/<docId>')
api.add_resource(CreateDocumentCategoryAPI, '/document_category/create')
api.add_resource(UpdateDocumentCategoryAPI, '/document_category/update/<idOrCode>')
api.add_resource(DeleteDocumentCategoryAPI, '/document_category/delete/<idOrCode>')
api.add_resource(PublishDocumentCategoryAPI, '/document_category/published/<idOrCode>')
api.add_resource(UnpublishDocumentCategoryAPI, '/document_category/unpublished/<idOrCode>')
api.add_resource(AssignDocumentCategoryAPI, '/document_category/assign/<docId>')
api.add_resource(UnassignDocumentCategoryAPI, '/document_category/unassign/<docId>')