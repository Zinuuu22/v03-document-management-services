from core.common.mongo.client import get_mongo_client
import structlog
import os
import sys
from datetime import datetime
from typing import Dict, Any
from flask_restful import Resource
from flask import request
from dateutil import parser 
from pymongo import MongoClient
import uuid
from structlog.contextvars import bind_contextvars
import time

logger = structlog.get_logger()


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from services.api import api
from services.api.utils import make_response, validate_id
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig, RelationshipConfig
            


client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
law_references_article_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_ARTICLE_COLLECTION_NAME]
law_references_article_draft_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_ARTICLE_DRAFT_COLLECTION_NAME]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]


# ---------------------------------------------------------------------
# Article Relationship APIs
# ---------------------------------------------------------------------
class ArticleRelationshipGetAPI(Resource):
    def get(self, relationship_id: str) -> Dict[str, Any]:
        bind_contextvars(task="ArticleRelationshipGetAPI")
        start_t = time.time()
        try:
            relationship = law_references_article_collection.find_one({'relationship_id': relationship_id})
            if not relationship:
                logger.error("get_article_relationship_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": "Article relationship not found", "event.duration": time.time()-start_t, "event.status": "failure"}, relationship_id=relationship_id)
                return make_response(data=None, code='404', message='Article relationship not found'), 404
            
            # Convert ObjectId to string for JSON serialization
            relationship['_id'] = str(relationship['_id'])            
            if 'created_at' in relationship:
                val = relationship['created_at']
                if isinstance(val, str):
                    dt = parser.isoparse(val)
                    relationship['created_at'] = dt.isoformat()
                elif isinstance(val, datetime):
                    relationship['created_at'] = val.isoformat()
        
            logger.info("get_article_relationship_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, relationship_id=relationship_id)
            return make_response(data=relationship, code='200', message='Success'), 200
        except Exception as e:
            logger.error("get_article_relationship_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code='500', message='Internal server error')
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class ArticleRelationshipCreateAPI(Resource):
    def post(self) -> Dict[str, Any]:
        bind_contextvars(task="ArticleRelationshipCreateAPI")
        start_t = time.time()
        try:
            body = request.get_json() or {}
            
            # Validate required fields
            required_fields = [
                'source_doc_id', 'source_article_id',
                'source_clause', 'source_point', 'target_doc_id', 'target_article_id',
                'target_article', 'target_clause', 'target_point', 'relationship_type', 'created_by'
            ]
            
            for field in required_fields:
                if field not in body:
                    logger.error("create_article_relationship_failed", action="post", **{"error.code": "400-VAL", "error.message": f"Missing required field: {field}", "event.duration": time.time()-start_t, "event.status": "failure"})
                    return make_response(data=None, code='400', message=f'Missing required field: {field}'), 400
            
            # Validate relationship_type enum
            valid_relationship_types = [
                "AMEND", "AMENDED", "BASIS", "CONSOLIDATED", "CONTENT_CONNECTION",
                "CORRECT", "DETAIL", "REFERENTIAL", "REPLACE", "REPLACED"
            ]
            if body['relationship_type'] not in valid_relationship_types:
                logger.error("create_article_relationship_failed", action="post", **{"error.code": "400-VAL", "error.message": "Invalid relationship_type", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code='400', message='Invalid relationship_type'), 400
            
            # Prepare document
            document = {
                'relationship_id': str(uuid.uuid4()),
                'source_doc_id': body['source_doc_id'],
                'source_article_id': body['source_article_id'],
                'source_clause': body['source_clause'],
                'source_point': body['source_point'],
                'target_doc_id': body['target_doc_id'],
                'target_article_id': body['target_article_id'],
                'target_article': body['target_article'],
                'target_clause': body['target_clause'],
                'target_point': body['target_point'],
                'relationship_type': body['relationship_type'],
                'created_by': body['created_by'],
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'last_modified_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'last_modified_by': body.get('last_modified_by', body['created_by'])
            }
            
            # Insert document
            result = law_references_article_collection.insert_one(document)
            
            logger.info("create_article_relationship_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, relationship_id=document['relationship_id'])
            return make_response(data={
                'relationship_id': document['relationship_id']
            }, code='200', message='Article relationship created successfully'), 200
            
        except ValueError as ve:
            logger.error("create_article_relationship_failed", action="post", **{"error.code": "400-VAL", "error.message": str(ve), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(data=None, code='400', message=str(ve)), 400
        except Exception as e:
            logger.error("create_article_relationship_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code='500', message='Internal server error')
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class ArticleRelationshipUpdateAPI(Resource):
    def put(self, relationship_id: str) -> Dict[str, Any]:
        bind_contextvars(task="ArticleRelationshipUpdateAPI")
        start_t = time.time()
        try:
            body = request.get_json() or {}
            
            # Validate relationship_type if provided
            if 'relationship_type' in body:
                valid_relationship_types = [
                    "AMEND", "AMENDED", "BASIS", "CONSOLIDATED", "CONTENT_CONNECTION",
                    "CORRECT", "DETAIL", "REFERENTIAL", "REPLACE", "REPLACED"
                ]
                if body['relationship_type'] not in valid_relationship_types:
                    logger.error("update_article_relationship_failed", action="put", **{"error.code": "400-VAL", "error.message": "Invalid relationship_type", "event.duration": time.time()-start_t, "event.status": "failure"})
                    return make_response(data=None, code='400', message='Invalid relationship_type'), 400
            
            # Prepare update data
            update_data = {}
            allowed_fields = [
                'source_doc_id', 'source_article_id', 'source_clause', 'source_point',
                'target_doc_id', 'target_article_id', 'target_article', 'target_clause',
                'target_point', 'relationship_type', 'last_modified_by'
            ]
            
            for field in allowed_fields:
                if field in body:
                    update_data[field] = body[field]
            
            if update_data:
                update_data['last_modified_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                result = law_references_article_collection.update_one(
                    {'relationship_id': relationship_id},
                    {'$set': update_data}
                )
                
                if result.matched_count == 0:
                    logger.error("update_article_relationship_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": "Article relationship not found", "event.duration": time.time()-start_t, "event.status": "failure"}, relationship_id=relationship_id)
                    return make_response(data=None, code='404', message='Article relationship not found'), 404
                
                logger.info("update_article_relationship_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"}, relationship_id=relationship_id)
                return make_response(data={'relationship_id': relationship_id}, code='200', message='Article relationship updated successfully'), 200
            else:
                logger.error("update_article_relationship_failed", action="put", **{"error.code": "400-VAL", "error.message": "No valid fields to update", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code='400', message='No valid fields to update'), 400
                
        except ValueError as ve:
            logger.error("update_article_relationship_failed", action="put", **{"error.code": "400-VAL", "error.message": str(ve), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(data=None, code='400', message=str(ve)), 400
        except Exception as e:
            logger.error("update_article_relationship_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code='500', message='Internal server error')
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class ArticleRelationshipDeleteAPI(Resource):
    def delete(self, relationship_id: str) -> Dict[str, Any]:
        bind_contextvars(task="ArticleRelationshipDeleteAPI")
        start_t = time.time()
        try:
            result = law_references_article_collection.delete_one({'relationship_id': relationship_id})
            
            if result.deleted_count == 0:
                logger.error("delete_article_relationship_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": "Article relationship not found", "event.duration": time.time()-start_t, "event.status": "failure"}, relationship_id=relationship_id)
                return make_response(data=None, code='404', message='Article relationship not found'), 404
            
            logger.info("delete_article_relationship_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"}, relationship_id=relationship_id)
            return make_response(data={'relationship_id': relationship_id}, code='200', message='Article relationship deleted successfully'), 200
            
        except Exception as e:
            logger.error("delete_article_relationship_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code='500', message='Internal server error')
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class ArticleRelationshipSearchAPI(Resource):
    def post(self) -> Dict[str, Any]:
        bind_contextvars(task="ArticleRelationshipSearchAPI")
        start_t = time.time()
        try:
            body = request.get_json() or {}
            
            # Build query from filters
            query = {}
            allowed_filters = [
                'source_doc_id', 'target_doc_id', 'relationship_type', 'created_by',
                'source_article_id', 'target_article_id', 'source_clause', 'target_article'
            ]
            
            for field in allowed_filters:
                if field in body and body[field]:
                    if field in ['source_doc_id', 'target_doc_id', 'relationship_type', 'created_by']:
                        query[field] = body[field]
                    else:
                        # For other fields, use regex for partial matching
                        query[field] = {'$regex': body[field], '$options': 'i'}
            
            # Pagination
            page = body.get('page', 1)
            limit = body.get('limit', 10)
            skip = (page - 1) * limit
            
            # Execute query
            total_count = law_references_article_collection.count_documents(query)
            relationships = list(law_references_article_collection.find(query).skip(skip).limit(limit))
            
            # Convert ObjectIds to strings    
            for rel in relationships:
                rel['_id'] = str(rel['_id'])
                if 'created_at' in rel:
                    val = rel['created_at']
                    if isinstance(val, str):
                        dt = parser.isoparse(val)
                        rel['created_at'] = dt.isoformat()
                    elif isinstance(val, datetime):
                        rel['created_at'] = val.isoformat()

                target_article_id = rel.get('target_article_id', '')
                logger.debug("search_article_relationships", action="post", target_article_id=target_article_id, **{"event.duration": time.time()-start_t})
                if target_article_id:
                    target_article = law_articles_collection.find_one({'article_id': target_article_id})
                    if target_article:
                        rel['target_article_title'] = target_article.get('article_title', '')
                else:
                    rel['target_article_title'] = ''

            logger.info("search_article_relationships_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=total_count)
            return make_response(data={
                'relationships': relationships,
                'total_count': total_count,
                'page': page,
                'limit': limit
            }, code='200', message='Search completed successfully'), 200
            
        except Exception as e:
            logger.error("search_article_relationships_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code='500', message='Internal server error')
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# ---------------------------------------------------------------------
# Draft Article Relationship APIs
# ---------------------------------------------------------------------
# Drafts are cross-document references whose TARGET document is not in the DB,
# so they have no target_doc_id to resolve. Instead they carry the raw display
# fields (target_doc_name, target_doc_code, target_article, relationship_type)
# extracted from the source document, ready for the FE to render directly.
class ArticleRelationshipDraftGetAPI(Resource):
    def get(self, relationship_id: str) -> Dict[str, Any]:
        bind_contextvars(task="ArticleRelationshipDraftGetAPI")
        start_t = time.time()
        try:
            relationship = law_references_article_draft_collection.find_one({'relationship_id': relationship_id})
            if not relationship:
                logger.error("get_article_relationship_draft_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": "Draft article relationship not found", "event.duration": time.time()-start_t, "event.status": "failure"}, relationship_id=relationship_id)
                return make_response(data=None, code='404', message='Draft article relationship not found'), 404

            relationship['_id'] = str(relationship['_id'])
            if 'created_at' in relationship:
                val = relationship['created_at']
                if isinstance(val, str):
                    relationship['created_at'] = parser.isoparse(val).isoformat()
                elif isinstance(val, datetime):
                    relationship['created_at'] = val.isoformat()

            logger.info("get_article_relationship_draft_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, relationship_id=relationship_id)
            return make_response(data=relationship, code='200', message='Success'), 200
        except Exception as e:
            logger.error("get_article_relationship_draft_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code='500', message='Internal server error')
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class ArticleRelationshipDraftSearchAPI(Resource):
    def post(self) -> Dict[str, Any]:
        bind_contextvars(task="ArticleRelationshipDraftSearchAPI")
        start_t = time.time()
        try:
            body = request.get_json() or {}

            query = {}
            # Exact-match keys vs. partial-match (regex) keys, mirroring the
            # resolved search API. target_doc_name/target_doc_code are draft-only.
            exact_filters = ['source_doc_id', 'relationship_type', 'created_by', 'target_doc_code']
            regex_filters = ['source_article_id', 'source_clause', 'target_article', 'target_doc_name']
            for field in exact_filters:
                if body.get(field):
                    query[field] = body[field]
            for field in regex_filters:
                if body.get(field):
                    query[field] = {'$regex': body[field], '$options': 'i'}

            page = body.get('page', 1)
            limit = body.get('limit', 10)
            skip = (page - 1) * limit

            total_count = law_references_article_draft_collection.count_documents(query)
            relationships = list(law_references_article_draft_collection.find(query).skip(skip).limit(limit))

            for rel in relationships:
                rel['_id'] = str(rel['_id'])
                if 'created_at' in rel:
                    val = rel['created_at']
                    if isinstance(val, str):
                        rel['created_at'] = parser.isoparse(val).isoformat()
                    elif isinstance(val, datetime):
                        rel['created_at'] = val.isoformat()

            logger.info("search_article_relationship_drafts_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=total_count)
            return make_response(data={
                'relationships': relationships,
                'total_count': total_count,
                'page': page,
                'limit': limit
            }, code='200', message='Search completed successfully'), 200
        except Exception as e:
            logger.error("search_article_relationship_drafts_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code='500', message='Internal server error')
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class ArticleRelationshipDraftDeleteAPI(Resource):
    def delete(self, relationship_id: str) -> Dict[str, Any]:
        bind_contextvars(task="ArticleRelationshipDraftDeleteAPI")
        start_t = time.time()
        try:
            result = law_references_article_draft_collection.delete_one({'relationship_id': relationship_id})

            if result.deleted_count == 0:
                logger.error("delete_article_relationship_draft_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": "Draft article relationship not found", "event.duration": time.time()-start_t, "event.status": "failure"}, relationship_id=relationship_id)
                return make_response(data=None, code='404', message='Draft article relationship not found'), 404

            logger.info("delete_article_relationship_draft_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"}, relationship_id=relationship_id)
            return make_response(data={'relationship_id': relationship_id}, code='200', message='Draft article relationship deleted successfully'), 200

        except Exception as e:
            logger.error("delete_article_relationship_draft_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code='500', message='Internal server error')
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# Article Relationship routes
api.add_resource(ArticleRelationshipGetAPI, '/article-relationship/get/<string:relationship_id>')
api.add_resource(ArticleRelationshipCreateAPI, '/article-relationship/create')
api.add_resource(ArticleRelationshipUpdateAPI, '/article-relationship/update/<string:relationship_id>')
api.add_resource(ArticleRelationshipDeleteAPI, '/article-relationship/delete/<string:relationship_id>')
api.add_resource(ArticleRelationshipSearchAPI, '/article-relationship/search')

# Draft article relationship routes (target document not in DB)
api.add_resource(ArticleRelationshipDraftGetAPI, '/article-relationship-draft/get/<string:relationship_id>')
api.add_resource(ArticleRelationshipDraftSearchAPI, '/article-relationship-draft/search')
api.add_resource(ArticleRelationshipDraftDeleteAPI, '/article-relationship-draft/delete/<string:relationship_id>')


