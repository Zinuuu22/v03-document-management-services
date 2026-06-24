import structlog
import sys
import os
import uuid
from flask_restful import Resource, reqparse
from datetime import datetime
from typing import Dict, Any
import time
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from services.api.utils.response import make_response
from services.api import api
from services.api.biz.social_relation.social_relation_models import SocialRelationModel, DuplicateSocialRelationGroupItemError
logger = structlog.get_logger()

# Initialize model
social_relation_model = SocialRelationModel()


class ListSocialRelationsAPI(Resource):
    """API for listing social relations with filters and pagination"""
    
    def get(self):
        """
        GET /api/social-relations
        Query parameters:
        - social_relation_name: Filter by name (partial match)
        - status: Filter by status (Active/Inactive)
        - social_relation_id: Filter by specific ID
        - created_date_from: Start date filter
        - created_date_to: End date filter
        - page: Page number (default: 1)
        - limit: Items per page (default: 10)
        """
        bind_contextvars(task="ListSocialRelationsAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('social_relation_name', type=str, required=False, default='', location='args')
        parser.add_argument('status', type=str, required=False, default='', location='args')
        parser.add_argument('social_relation_id', type=str, required=False, default='', location='args')
        parser.add_argument('created_date_from', type=str, required=False, default='', location='args')
        parser.add_argument('created_date_to', type=str, required=False, default='', location='args')
        parser.add_argument('page', type=int, required=False, default=1, location='args')
        parser.add_argument('limit', type=int, required=False, default=10, location='args')
        args = parser.parse_args()
        
        try:
            filters = {}
            if args['social_relation_name']:
                filters['social_relation_name'] = args['social_relation_name']
            if args['status']:
                filters['status'] = args['status']
            if args['social_relation_id']:
                filters['social_relation_id'] = args['social_relation_id']
            if args['created_date_from']:
                filters['created_date_from'] = datetime.fromisoformat(args['created_date_from'])
            if args['created_date_to']:
                filters['created_date_to'] = datetime.fromisoformat(args['created_date_to'])
            
            result = social_relation_model.list_social_relations(
                filters=filters,
                page=args['page'],
                limit=args['limit']
            )
            
            logger.info("get_social_relations_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("get_social_relations_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class CreateSocialRelationAPI(Resource):
    """API for creating a new social relation"""
    
    def post(self):
        """
        POST /api/social-relations
        Body:
        - social_relation_name: Name of the relation (required)
        - description: Description (optional)
        - social_relation_name_norm: Normalized name (required)
        - status: Status (optional, default: Active)
        - created_by: Creator username (required)
        """
        bind_contextvars(task="CreateSocialRelationAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('social_relation_name', type=str, required=True, help='Social relation name is required', location='json')
        parser.add_argument('description', type=str, required=False, default='', location='json')
        parser.add_argument('social_relation_name_norm', type=str, required=True, help='Normalized name is required', location='json')
        parser.add_argument('status', type=str, required=False, default='ACTIVE', location='json')
        parser.add_argument('created_by', type=str, required=True, help='Created by is required', location='json')
        args = parser.parse_args()
        
        try:
            data = {
                'social_relation_id': str(uuid.uuid4()),
                'social_relation_name': args['social_relation_name'],
                'description': args['description'],
                'social_relation_name_norm': args['social_relation_name_norm'],
                'status': args['status'],
                'created_by': args['created_by']
            }
            
            result = social_relation_model.create_social_relation(data)
            
            logger.info("create_social_relation_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message="Social relation created successfully"), 201
            
        except ValueError as e:
            logger.error("create_social_relation_failed", action="post", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            response = make_response(data=None, code=1000, message=str(e))
            response["error_code"] = "400-VAL"
            response["status"] = False
            return response, 400
        except Exception as e:
            logger.error("create_social_relation_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UpdateSocialRelationAPI(Resource):
    """API for updating an existing social relation"""
    
    def put(self, social_relation_id):
        """
        PUT /api/social-relations/<social_relation_id>
        Body:
        - social_relation_name: Updated name (optional)
        - description: Updated description (optional)
        - social_relation_name_norm: Updated normalized name (optional)
        - status: Updated status (optional)
        - last_modified_by: Username (required)
        """
        bind_contextvars(task="UpdateSocialRelationAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('social_relation_name', type=str, required=False, location='json')
        parser.add_argument('description', type=str, required=False, location='json')
        parser.add_argument('social_relation_name_norm', type=str, required=False, location='json')
        parser.add_argument('status', type=str, required=False, location='json')
        parser.add_argument('last_modified_by', type=str, required=True, help='Last modified by is required', location='json')
        args = parser.parse_args()
        
        try:
            update_data = {'last_modified_by': args['last_modified_by']}
            
            if args['social_relation_name']:
                update_data['social_relation_name'] = args['social_relation_name']
            if args['description'] is not None:
                update_data['description'] = args['description']
            if args['social_relation_name_norm']:
                update_data['social_relation_name_norm'] = args['social_relation_name_norm']
            if args['status']:
                update_data['status'] = args['status']
            
            result = social_relation_model.update_social_relation(social_relation_id, update_data)
            
            logger.info("update_social_relation_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message="Social relation updated successfully"), 200
            
        except ValueError as e:
            logger.error("update_social_relation_failed", action="put", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            response = make_response(data=None, code=1000, message=str(e))
            response["error_code"] = "400-VAL"
            response["status"] = False
            return response, 400
        except Exception as e:
            logger.error("update_social_relation_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DeleteSocialRelationAPI(Resource):
    """API for deleting a social relation"""
    
    def delete(self, social_relation_id):
        """
        DELETE /api/social-relations/<social_relation_id>/delete
        Deletes the social relation and all its related mappings
        """
        bind_contextvars(task="DeleteSocialRelationAPI")
        start_t = time.time()
        try:
            result = social_relation_model.delete_social_relation(social_relation_id, delete_mappings=True)
            
            message = f"Social relation {social_relation_id} deleted successfully"
            logger.info("delete_social_relation_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message=message), 200
            
        except ValueError as e:
            logger.error("delete_social_relation_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            response = make_response(data=None, code=1000, message=str(e))
            response["error_code"] = "404-NOTFOUND"
            response["status"] = False
            return response, 404
        except Exception as e:
            logger.error("delete_social_relation_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetSocialRelationAPI(Resource):
    """API for getting a single social relation by ID"""
    
    def get(self, social_relation_id):
        """
        GET /api/social-relations/<social_relation_id>
        Get a specific social relation by its ID
        """
        bind_contextvars(task="GetSocialRelationAPI")
        start_t = time.time()
        try:
            result = social_relation_model.get_social_relation_by_id(social_relation_id)
            
            if not result:
                logger.error("get_social_relation_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": "Social relation not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code=1000, message="Social relation not found"), 404
            
            logger.info("get_social_relation_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("get_social_relation_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# ==================== SOCIAL RELATION MAPPING APIs ====================

class ListSocialRelationMappingsAPI(Resource):
    """API for listing social relation mappings with filters and pagination"""
    
    def get(self):
        """
        GET /api/social-relation-mappings
        Query parameters:
        - doc_id: Filter by document ID
        - article_id: Filter by article ID
        - social_relation_id: Filter by social relation ID
        - relation_type: Filter by relation type (PRIMARY/Secondary)
        - page: Page number (default: 1)
        - limit: Items per page (default: 10)
        """
        bind_contextvars(task="ListSocialRelationMappingsAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('doc_id', type=str, required=False, default='', location='args')
        parser.add_argument('article_id', type=str, required=False, default='', location='args')
        parser.add_argument('social_relation_id', type=str, required=False, default='', location='args')
        parser.add_argument('relation_type', type=str, required=False, default='', location='args')
        parser.add_argument('page', type=int, required=False, default=1, location='args')
        parser.add_argument('limit', type=int, required=False, default=10, location='args')
        args = parser.parse_args()
        
        try:
            filters = {}
            if args['doc_id']:
                filters['doc_id'] = args['doc_id']
            if args['article_id']:
                filters['article_id'] = args['article_id']
            if args['social_relation_id']:
                filters['social_relation_id'] = args['social_relation_id']
            if args['relation_type']:
                filters['relation_type'] = args['relation_type']
            
            result = social_relation_model.list_social_relation_mappings(
                filters=filters,
                page=args['page'],
                limit=args['limit']
            )
            
            logger.info("get_social_relation_mappings_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("get_social_relation_mappings_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class CreateSocialRelationMappingAPI(Resource):
    """API for creating a new social relation mapping"""
    
    def post(self):
        """
        POST /api/social-relation-mappings
        Body:
        - doc_id: Document ID (required)
        - article_id: Article ID (optional)
        - social_relation_id: Social relation ID (required)
        - relation_type: Relation type (optional, default: PRIMARY)
        - created_by: Creator username (required)
        """
        bind_contextvars(task="CreateSocialRelationMappingAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('doc_id', type=str, required=True, help='Document ID is required', location='json')
        parser.add_argument('article_id', type=str, required=False, location='json')
        parser.add_argument('social_relation_id', type=str, required=True, help='Social relation ID is required', location='json')
        parser.add_argument('relation_type', type=str, required=False, default='PRIMARY', location='json')
        parser.add_argument('created_by', type=str, required=True, help='Created by is required', location='json')
        args = parser.parse_args()
        
        try:
            existing_doc = social_relation_model.check_document_exists(args['doc_id'])
            if not existing_doc:
                raise ValueError(f"Document with ID {args['doc_id']} not found")
            
            if args['article_id']:
                existing_article = social_relation_model.check_article_exists(args['article_id'])
                if not existing_article:
                    raise ValueError(f"Article with ID {args['article_id']} not found")
            
            existing_social_relation = social_relation_model.check_social_relation_exists(args['social_relation_id'])
            if not existing_social_relation:
                raise ValueError(f"Social relation with ID {args['social_relation_id']} not found")
            
            data = {
                'doc_id': args['doc_id'],
                'social_relation_id': args['social_relation_id'],
                'relation_type': args['relation_type'],
                'created_by': args['created_by']
            }

            if args['article_id']:
                data['article_id'] = args['article_id']
            
            result = social_relation_model.create_social_relation_mapping(data)
            
            logger.info("create_social_relation_mapping_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message="Social relation mapping created successfully"), 201
            
        except ValueError as e:
            logger.error("create_social_relation_mapping_failed", action="post", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            response = make_response(data=None, code=1000, message=str(e))
            response["error_code"] = "400-VAL"
            response["status"] = False
            return response, 400
        except Exception as e:
            logger.error("create_social_relation_mapping_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UpdateSocialRelationMappingAPI(Resource):
    """API for updating an existing social relation mapping"""
    
    def put(self, mapping_id):
        """
        PUT /api/social-relation-mappings/<mapping_id>
        Body:
        - relation_type: Updated relation type (optional)
        - last_modified_by: Username (required)
        """
        bind_contextvars(task="UpdateSocialRelationMappingAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('relation_type', type=str, required=False, location='json')
        parser.add_argument('last_modified_by', type=str, required=True, help='Last modified by is required', location='json')
        args = parser.parse_args()
        
        try:
            update_data = {'last_modified_by': args['last_modified_by']}
            
            if args['relation_type']:
                update_data['relation_type'] = args['relation_type']
            
            result = social_relation_model.update_social_relation_mapping(mapping_id, update_data)
            
            logger.info("update_social_relation_mapping_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message="Social relation mapping updated successfully"), 200
            
        except ValueError as e:
            logger.error("update_social_relation_mapping_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            response = make_response(data=None, code=1000, message=str(e))
            response["error_code"] = "404-NOTFOUND"
            response["status"] = False
            return response, 404
        except Exception as e:
            logger.error("update_social_relation_mapping_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DeleteSocialRelationMappingAPI(Resource):
    """API for deleting a social relation mapping"""
    
    def delete(self, mapping_id):
        """
        DELETE /api/social-relation-mappings/<mapping_id>
        Deletes a specific social relation mapping
        """
        bind_contextvars(task="DeleteSocialRelationMappingAPI")
        start_t = time.time()
        try:
            result = social_relation_model.delete_social_relation_mapping(mapping_id)
            
            logger.info("delete_social_relation_mapping_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message="Liên kết đã được xóa."), 200
            
        except ValueError as e:
            logger.error("delete_social_relation_mapping_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            response = make_response(data=None, code=1000, message=str(e))
            response["error_code"] = "404-NOTFOUND"
            response["status"] = False
            return response, 404
        except Exception as e:
            logger.error("delete_social_relation_mapping_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetSocialRelationMappingAPI(Resource):
    """API for getting a single social relation mapping by ID"""
    
    def get(self, mapping_id):
        """
        GET /api/social-relation-mappings/<mapping_id>
        Get a specific social relation mapping by its ID
        """
        bind_contextvars(task="GetSocialRelationMappingAPI")
        start_t = time.time()
        try:
            result = social_relation_model.get_social_relation_mapping_by_id(mapping_id)
            
            if not result:
                logger.error("get_social_relation_mapping_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": "Social relation mapping not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code=1000, message="Social relation mapping not found"), 404

            # Enrich with the referenced article's title/content from law_articles.
            article_id = result.get('article_id')
            result['article_title'] = ''
            result['article_content'] = ''
            if article_id:
                article = social_relation_model.article_collection.find_one({'article_id': article_id})
                if article:
                    result['article_title'] = article.get('article_title', '')
                    result['article_content'] = article.get('article_content', '')

            logger.info("get_social_relation_mapping_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("get_social_relation_mapping_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetSocialRelationDetailAPI(Resource):
    """API for getting social relation mapping details with enriched data"""
    
    def get(self, idOrSocialRelationId):
        """
        GET /api/social-relation-mappings/detail/<idOrSocialRelationId>
        Get social relation mapping details by ObjectId or social_relation_id
        Returns a list of mappings with article_title and social_relation_name
        """
        bind_contextvars(task="GetSocialRelationDetailAPI")
        start_t = time.time()
        try:
            result = social_relation_model.get_social_relation_detail(idOrSocialRelationId)
            
            if not result:
                logger.error("get_social_relation_detail_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": "No social relation mappings found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code=1000, message="No social relation mappings found"), 404
            
            logger.info("get_social_relation_detail_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message="Success"), 200
            
        except Exception as e:
            logger.error("get_social_relation_detail_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500

class CheckSocialRelationMappingAPI(Resource):
    """API for checking if a social relation has mappings"""
    
    def get(self, id_or_social_relation_id):
        """
        GET /api/social-relations/<id_or_social_relation_id>/check-mapping
        
        Path parameters:
        - id_or_social_relation_id: Either MongoDB ObjectId (_id) or social_relation_id
        
        Returns:
        - has_mapping: True if mappings exist, False otherwise
        - mappings: List of mapping documents
        """
        bind_contextvars(task="CheckSocialRelationMappingAPI")
        start_t = time.time()
        try:
            from bson import ObjectId
            
            social_relation = social_relation_model.get_social_relation_by_id(id_or_social_relation_id)
            
            if not social_relation:
                try:
                    obj_id = ObjectId(id_or_social_relation_id)
                    social_relation = social_relation_model.collection.find_one({"_id": obj_id})
                    if social_relation:
                        social_relation['_id'] = str(social_relation['_id'])
                except:
                    pass
            
            if not social_relation:
                logger.error("check_social_relation_mapping_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": f"Social relation with ID {id_or_social_relation_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    data=None,
                    code=1000,
                    message=f"Social relation with ID {id_or_social_relation_id} not found"
                ), 404
            
            social_relation_id = social_relation.get('social_relation_id')
            
            mappings_cursor = social_relation_model.mapping_collection.find(
                {"social_relation_id": social_relation_id}
            )
            mappings = []
            for mapping in mappings_cursor:
                mapping['_id'] = str(mapping['_id'])
                mappings.append(mapping)
            
            has_mapping = len(mappings) > 0
            
            logger.info("check_social_relation_mapping_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                data={
                    "has_mapping": has_mapping,
                    "mapping_count": len(mappings),
                    "mappings": mappings
                },
                code=0,
                message="Successfully checked social relation mappings"
            ), 200
            
        except Exception as e:
            logger.error("check_social_relation_mapping_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=f"Failed to check social relation mapping: {str(e)}")
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# ==================== SOCIAL RELATION GROUP APIs ====================

class ListSocialRelationGroupsAPI(Resource):
    """API for listing social relation groups, each with its social relations"""

    def get(self):
        """
        GET /api/social-relation-groups
        Query parameters:
        - keyword: Search on social_relation_group_name / social_relation_group_name_norm
        - status: Filter by status
        - doc_id: Filter by document ID
        - page: Page number (default: 1)
        - limit: Items per page (default: 10)
        """
        bind_contextvars(task="ListSocialRelationGroupsAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('keyword', type=str, required=False, default='', location='args')
        parser.add_argument('status', type=str, required=False, default='', location='args')
        parser.add_argument('doc_id', type=str, required=False, default='', location='args')
        parser.add_argument('page', type=int, required=False, default=1, location='args')
        parser.add_argument('limit', type=int, required=False, default=10, location='args')
        args = parser.parse_args()

        try:
            filters = {}
            if args['keyword']:
                filters['keyword'] = args['keyword']
            if args['status']:
                filters['status'] = args['status']
            if args['doc_id']:
                filters['doc_id'] = args['doc_id']

            result = social_relation_model.list_social_relation_groups(
                filters=filters,
                page=args['page'],
                limit=args['limit']
            )

            logger.info("get_social_relation_groups_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message="Success"), 200

        except Exception as e:
            logger.error("get_social_relation_groups_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class AddSocialRelationToGroupAPI(Resource):
    """API for adding (assigning) an existing social relation (danh mục) into
    an existing social relation group, in the context of a document"""

    def post(self):
        """
        POST /api/social-relation-groups/add-relation
        Body:
        - social_relation_id: ID of the existing social relation catalog entry (required)
        - social_relation_group_id: ID of the existing social relation group (required)
        - doc_id: ID of the current document (required)
        - created_by: Username performing the action (optional)
        """
        bind_contextvars(task="AddSocialRelationToGroupAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('social_relation_id', type=str, required=True, help='Social relation ID is required', location='json')
        parser.add_argument('social_relation_group_id', type=str, required=True, help='Social relation group ID is required', location='json')
        parser.add_argument('doc_id', type=str, required=True, help='Document ID is required', location='json')
        parser.add_argument('created_by', type=str, required=False, default='', location='json')
        args = parser.parse_args()

        try:
            data = {
                'social_relation_id': args['social_relation_id'],
                'social_relation_group_id': args['social_relation_group_id'],
                'doc_id': args['doc_id'],
                'created_by': args['created_by'],
            }

            result = social_relation_model.add_social_relation_to_group(data)

            logger.info("add_social_relation_to_group_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message="Đã thêm quan hệ xã hội vào nhóm thành công"), 201

        except DuplicateSocialRelationGroupItemError as e:
            logger.error("add_social_relation_to_group_failed", action="post", **{"error.code": "409-DUP", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "409-DUP"
            response["status"] = False
            return response, 409

        except ValueError as e:
            logger.error("add_social_relation_to_group_failed", action="post", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            response = make_response(data=None, code=1000, message=str(e))
            response["error_code"] = "400-VAL"
            response["status"] = False
            return response, 400

        except Exception as e:
            logger.error("add_social_relation_to_group_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DeleteSocialRelationGroupAPI(Resource):
    """API for deleting a social relation group, cascading to its relations and mappings"""

    def delete(self, social_relation_group_id):
        """
        DELETE /api/social-relation-groups/<social_relation_group_id>/delete
        Deletes the group and all social relations belonging to it, plus all
        mappings pointing at those relations.
        """
        bind_contextvars(task="DeleteSocialRelationGroupAPI")
        start_t = time.time()
        try:
            result = social_relation_model.delete_social_relation_group(social_relation_group_id)

            message = "Deleted social relation group successfully"
            logger.info("delete_social_relation_group_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(data=result, code=0, message=message), 200

        except ValueError as e:
            logger.error("delete_social_relation_group_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            response = make_response(data=None, code=1000, message=str(e))
            response["error_code"] = "404-NOTFOUND"
            response["status"] = False
            return response, 404
        except Exception as e:
            logger.error("delete_social_relation_group_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# Register API endpoints
api.add_resource(ListSocialRelationsAPI, '/social-relations')
api.add_resource(CreateSocialRelationAPI, '/social-relations/create')
api.add_resource(GetSocialRelationAPI, '/social-relations/<string:social_relation_id>')
api.add_resource(UpdateSocialRelationAPI, '/social-relations/<string:social_relation_id>/update')
api.add_resource(DeleteSocialRelationAPI, '/social-relations/<string:social_relation_id>/delete')
api.add_resource(CheckSocialRelationMappingAPI, '/social-relations/<string:id_or_social_relation_id>/check-mapping')

api.add_resource(ListSocialRelationMappingsAPI, '/social-relation-mappings')
api.add_resource(CreateSocialRelationMappingAPI, '/social-relation-mappings/create')
api.add_resource(GetSocialRelationMappingAPI, '/social-relation-mappings/<string:mapping_id>')
api.add_resource(UpdateSocialRelationMappingAPI, '/social-relation-mappings/<string:mapping_id>/update')
api.add_resource(DeleteSocialRelationMappingAPI, '/social-relation-mappings/<string:mapping_id>/delete')
api.add_resource(GetSocialRelationDetailAPI, '/social-relation-mappings/detail/<string:idOrSocialRelationId>')

api.add_resource(ListSocialRelationGroupsAPI, '/social-relation-groups')
api.add_resource(AddSocialRelationToGroupAPI, '/social-relation-groups/add-relation')
api.add_resource(DeleteSocialRelationGroupAPI, '/social-relation-groups/<string:social_relation_group_id>/delete')

