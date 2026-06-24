import structlog
import sys
import os
from flask_restful import Resource, reqparse
from datetime import datetime
import uuid
from typing import Dict, Any, List
from bson import ObjectId
import time
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from services.api.utils.response import make_response
from services.api import api
from services.api.biz.authority.authority_models import AuthorityModel

logger = structlog.get_logger()

# Initialize model
authority_model = AuthorityModel()

# ==================== AUTHORITY APIs ====================
class ListAuthoritiesAPI(Resource):
    """API for listing authorities with filters and pagination"""
    
    def get(self):
        """
        GET /api/authorities
        Query parameters:
        - agency_id: Filter by agency ID
        - keyword: Filter by keyword in authority content
        - status: Filter by status (ACTIVE/INACTIVE)
        - doc_id: Filter by document ID
        - page: Page number (default: 1)
        - limit: Items per page (default: 10, max: 100)
        """
        bind_contextvars(task="ListAuthoritiesAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('agency_id', type=str, required=False, default='', location='args')
        parser.add_argument('keyword', type=str, required=False, default='', location='args')
        parser.add_argument('status', type=str, required=False, default='', location='args')
        parser.add_argument('doc_id', type=str, required=False, default='', location='args')
        parser.add_argument('page', type=int, required=False, default=1, location='args')
        parser.add_argument('limit', type=int, required=False, default=10, location='args')
        args = parser.parse_args()
        
        try:
            # Validate pagination
            page = max(1, args['page'])
            limit = min(100, max(1, args['limit']))
            
            # Prepare filters
            filters = {}
            if args['agency_id']:
                filters['agency_id'] = args['agency_id']
            if args['keyword']:
                filters['keyword'] = args['keyword']
            if args['status']:
                filters['status'] = args['status']
            if args['doc_id']:
                filters['doc_id'] = args['doc_id']
            
            # Get paginated results
            result = authority_model.list_authorities(
                filters=filters,
                page=page,
                limit=limit
            )
            
            logger.info("get_authorities_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Successfully retrieved authorities",
                data=result), 200
            
        except Exception as e:
            logger.error("get_authorities_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to retrieve authorities: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class CreateAuthorityAPI(Resource):
    """API for creating a new authority"""
    
    def post(self):
        """
        POST /api/authorities/create
        Body:
        - authority_content: Authority content (required)
        - doc_effective_date: Document effective date (optional)
        - doc_expire_date: Document expiry date (optional)
        - doc_effective_status: Document effective status (optional)
        - status: Status (ACTIVE/INACTIVE, default: ACTIVE)
        - created_by: User ID who created this record (required)
        """
        bind_contextvars(task="CreateAuthorityAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('authority_content', type=str, required=True,
                          help='Authority content is required', location='json')
        parser.add_argument('authority_quotation', type=str, required=False, location='json')
        parser.add_argument('status', type=str, required=False, default='ACTIVE',
                          choices=('ACTIVE', 'INACTIVE'), location='json')
        parser.add_argument('created_by', type=str, required=True,
                          help='Created by user ID is required', location='json')
        args = parser.parse_args()

        try:
            # Prepare data for creation
            data = {
                'authority_id': str(uuid.uuid4()),
                'authority_content': args['authority_content'],
                'status': args['status'],
                'created_by': args['created_by']
            }
            if args.get('authority_quotation') is not None:
                data['authority_quotation'] = args['authority_quotation']
            
        
            
            # Create the authority
            result = authority_model.create_authority(data)
            
            logger.info("create_authority_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=201,
                message="Authority created successfully",
                data=result
            ), 201
            
        except ValueError as e:
            logger.error("create_authority_failed", action="post", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(
                code=400,
                message=str(e),
                data=None
            ), 400
            
        except Exception as e:
            logger.error("create_authority_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message="Failed to create authority", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetAuthorityAPI(Resource):
    """API for retrieving a single authority by ID"""
    
    def get(self, authority_id):
        """
        GET /api/authorities/<authority_id>
        
        Path parameters:
        - authority_id: The ID of the authority to retrieve
        """
        bind_contextvars(task="GetAuthorityAPI")
        start_t = time.time()
        try:
            # Get the authority
            authority = authority_model.get_authority_by_id(authority_id)
            
            if not authority:
                logger.error("get_authority_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": f"Authority with ID {authority_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=404,
                    message=f"Authority with ID {authority_id} not found",
                    data=None
                ), 404
            
            logger.info("get_authority_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Successfully retrieved authority",
                data=authority
            )
            
        except Exception as e:
            logger.error("get_authority_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to retrieve authority: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UpdateAuthorityAPI(Resource):
    """API for updating an existing authority"""
    
    def put(self, authority_id):
        """
        PUT /api/authorities/<authority_id>/update
        
        Path parameters:
        - authority_id: The ID of the authority to update
        
        Body:
        - authority_content: Updated authority content (optional)
        - doc_effective_date: Updated effective date (optional)
        - doc_expire_date: Updated expiry date (optional)
        - doc_effective_status: Updated effective status (optional)
        - status: Updated status (ACTIVE/INACTIVE, optional)
        - last_modified_by: User ID who is making the update (required)
        """
        bind_contextvars(task="UpdateAuthorityAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('authority_content', type=str, required=False, location='json')
        parser.add_argument('authority_quotation', type=str, required=False, location='json')
        parser.add_argument('doc_effective_date', type=str, required=False, location='json')
        parser.add_argument('doc_expire_date', type=str, required=False, location='json')
        parser.add_argument('doc_effective_status', type=str, required=False, location='json')
        parser.add_argument('status', type=str, required=False,
                          choices=('ACTIVE', 'INACTIVE'), location='json')
        parser.add_argument('last_modified_by', type=str, required=True,
                          help='User ID who is making the update is required',
                          location='json')
        args = parser.parse_args()

        try:
            # Check if the authority exists
            existing = authority_model.get_authority_by_id(authority_id)
            if not existing:
                return make_response(
                    code=404,
                    message=f"Authority with ID {authority_id} not found",
                    data=None
                ), 404

            # Prepare update data
            update_data = {}
            if args['authority_content'] is not None:
                update_data['authority_content'] = args['authority_content']
            if args.get('authority_quotation') is not None:
                update_data['authority_quotation'] = args['authority_quotation']
            if args['doc_effective_date'] is not None:
                update_data['doc_effective_date'] = args['doc_effective_date']
            if args['doc_expire_date'] is not None:
                update_data['doc_expire_date'] = args['doc_expire_date']
            if args['doc_effective_status'] is not None:
                update_data['doc_effective_status'] = args['doc_effective_status']
            if args['status'] is not None:
                update_data['status'] = args['status']
            
            # Add last modified info
            update_data['last_modified_by'] = args['last_modified_by']
            
            # Update the authority
            result = authority_model.update_authority(authority_id, update_data)
            
            if not result:
                logger.error("update_authority_failed", action="put", **{"error.code": "500-SYS", "error.message": "Failed to update authority", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=500,
                    message="Failed to update authority",
                    data=None
                ), 500
            
            logger.info("update_authority_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Authority updated successfully",
                data=result
            )
            
        except ValueError as e:
            logger.error("update_authority_failed", action="put", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(
                code=400,
                message=str(e),
                data=None
            ), 400
            
        except Exception as e:
            logger.error("update_authority_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to update authority: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DeleteAuthorityAPI(Resource):
    """API for deleting an authority"""
    
    def delete(self, authority_id):
        """
        DELETE /api/authorities/<authority_id>/delete
        
        Path parameters:
        - authority_id: The ID of the authority to delete
        
        Query parameters:
        - delete_mappings: Whether to delete related mappings (default: true)
        """
        bind_contextvars(task="DeleteAuthorityAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('delete_mappings', type=bool, required=False, default=True,
                          location='args',
                          help='Whether to delete related mappings')
        args = parser.parse_args()
        
        try:
            # Check if the authority exists
            existing = authority_model.get_authority_by_id(authority_id)
            if not existing:
                return make_response(
                    code=404,
                    message=f"Authority with ID {authority_id} not found",
                    data=None
                ), 404
            
            # Delete the authority
            result = authority_model.delete_authority(
                authority_id=authority_id,
                delete_mappings=args['delete_mappings']
            )
            
            logger.info("delete_authority_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message=f"Authority {authority_id} deleted successfully",
                data=result
            )
            
        except ValueError as e:
            logger.error("delete_authority_failed", action="delete", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(
                code=400,
                message=str(e),
                data=None
            ), 400
            
        except Exception as e:
            logger.error("delete_authority_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to delete authority: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# ==================== AUTHORITY MAPPING APIs ====================

class ListAuthorityMappingsAPI(Resource):
    """API for listing authority mappings with filters and pagination"""
    
    def get(self):
        """
        GET /api/authority-mappings
        Query parameters:
        - doc_id: Filter by document ID
        - article_id: Filter by article ID
        - authority_id: Filter by authority ID
        - agency_id: Filter by agency ID
        - page: Page number (default: 1)
        - limit: Items per page (default: 10, max: 100)
        """
        bind_contextvars(task="ListAuthorityMappingsAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('doc_id', type=str, required=False, location='args')
        parser.add_argument('article_id', type=str, required=False, location='args')
        parser.add_argument('authority_id', type=str, required=False, location='args')
        parser.add_argument('agency_id', type=str, required=False, location='args')
        parser.add_argument('page', type=int, required=False, default=1, location='args')
        parser.add_argument('limit', type=int, required=False, default=10, location='args')
        args = parser.parse_args()
        
        try:
            # Prepare filters
            filters = {}
            if args['doc_id']:
                filters['doc_id'] = args['doc_id']
            if args['article_id']:
                filters['article_id'] = args['article_id']
            if args['authority_id']:
                filters['authority_id'] = args['authority_id']
            if args['agency_id']:
                filters['agency_id'] = args['agency_id']
            
            # Get paginated results
            result = authority_model.list_mappings(
                filters=filters,
                page=args['page'],
                limit=min(100, max(1, args['limit']))
            )
            
            logger.info("get_authority_mappings_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Successfully retrieved authority mappings",
                data=result
            ), 200
            
        except Exception as e:
            logger.error("get_authority_mappings_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to retrieve authority mappings: {str(e)}", data=[])
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class CreateAuthorityMappingAPI(Resource):
    """API for creating a new authority mapping"""
    
    def post(self):
        """
        POST /api/authority-mappings/create
        Body:
        - doc_id: Document ID (required)
        - article_id: Article ID (optional)
        - authority_id: Authority ID (required)
        - agency_id: Agency ID (optional)
        - created_by: User ID who created this mapping (required)
        """
        bind_contextvars(task="CreateAuthorityMappingAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('doc_id', type=str, required=True,
                          help='Document ID is required', location='json')
        parser.add_argument('article_id', type=str, required=False, location='json')
        parser.add_argument('authority_id', type=str, required=True,
                          help='Authority ID is required', location='json')
        parser.add_argument('agency_id', type=str, required=True, location='json')
        parser.add_argument('created_by', type=str, required=True,
                          help='Created by user ID is required', location='json')
        args = parser.parse_args()
        
        try:
            # Check if authority exists
            if not authority_model.get_authority_by_id(args['authority_id']):
                raise ValueError(f"Authority with ID {args['authority_id']} not found")
            
            # Check if document exists
            existing_doc = authority_model.check_document_exists(args['doc_id'])
            if not existing_doc:
                raise ValueError(f"Document with ID {args['doc_id']} not found")
            
            # Check if mapping already exists
            existing = authority_model.get_mapping_by_doc_and_authority(
                args['doc_id'],
                args['authority_id']
            )
            
            if existing:
                raise ValueError(f"Mapping already exists for document {args['doc_id']} and authority {args['authority_id']}")
            
            # Prepare mapping data
            mapping_data = {
                'doc_id': args['doc_id'],
                'authority_id': args['authority_id'],
                'created_by': args['created_by']
            }
            
            if args['article_id']:
                mapping_data['article_id'] = args['article_id']
            if args['agency_id']:
                mapping_data['agency_id'] = args['agency_id']
            
            # Create the mapping
            result = authority_model.create_mapping(mapping_data)
            
            logger.info("create_authority_mapping_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=201,
                message="Authority mapping created successfully",
                data=result
            ), 201
            
        except ValueError as e:
            logger.error("create_authority_mapping_failed", action="post", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(
                code=400,
                message=str(e),
                data=None
            ), 400
            
        except Exception as e:
            logger.error("create_authority_mapping_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to create authority mapping: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetAuthorityMappingAPI(Resource):
    """API for getting a single authority mapping by ID"""
    
    def get(self, mapping_id):
        """
        GET /api/authority-mappings/<mapping_id>
        
        Path parameters:
        - mapping_id: The ID of the mapping to retrieve
        """
        bind_contextvars(task="GetAuthorityMappingAPI")
        start_t = time.time()
        try:
            # Get the mapping
            mapping = authority_model.get_mapping_by_id(mapping_id)
            
            if not mapping:
                logger.error("get_authority_mapping_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": f"Mapping with ID {mapping_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=404,
                    message=f"Mapping with ID {mapping_id} not found",
                    data=None
                ), 404

            # Enrich with the referenced article's title/content from law_articles.
            article_id = mapping.get('article_id')
            mapping['article_title'] = ''
            mapping['article_content'] = ''
            if article_id:
                article = authority_model.article_collection.find_one({'article_id': article_id})
                if article:
                    mapping['article_title'] = article.get('article_title', '')
                    mapping['article_content'] = article.get('article_content', '')

            logger.info("get_authority_mapping_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Successfully retrieved authority mapping",
                data=mapping
            )
            
        except Exception as e:
            logger.error("get_authority_mapping_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to retrieve authority mapping: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UpdateAuthorityMappingAPI(Resource):
    """API for updating an existing authority mapping"""
    
    def put(self, mapping_id):
        """
        PUT /api/authority-mappings/<mapping_id>/update
        
        Path parameters:
        - mapping_id: The ID of the mapping to update
        
        Body:
        - doc_id: Updated document ID (optional)
        - article_id: Updated article ID (optional)
        - authority_id: Updated authority ID (optional)
        - agency_id: Updated agency ID (optional)
        - last_modified_by: User ID who is making the update (required)
        """
        bind_contextvars(task="UpdateAuthorityMappingAPI")
        start_t = time.time()
        try:
            # Parse request arguments
            parser = reqparse.RequestParser()
            # parser.add_argument('doc_id', type=str, required=False, location='json')
            parser.add_argument('article_id', type=str, required=False, location='json')
            # parser.add_argument('authority_id', type=str, required=False, location='json')
            parser.add_argument('agency_id', type=str, required=False, location='json')
            parser.add_argument('last_modified_by', type=str, required=True,
                              help='User ID who is making the update is required',
                              location='json')
            args = parser.parse_args()
            
            # Get the existing mapping
            mapping = authority_model.get_mapping_by_id(mapping_id)
            if not mapping:
                logger.error("update_authority_mapping_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Mapping with ID {mapping_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=404,
                    message=f"Mapping with ID {mapping_id} not found",
                    data=None
                ), 404
            
            # Prepare update data
            update_data = {
                'last_modified_by': args['last_modified_by']
            }
            
            if args.get('doc_id') is not None:
                update_data['doc_id'] = args['doc_id']
            if args.get('article_id') is not None:
                update_data['article_id'] = args['article_id']
            if args.get('authority_id') is not None:
                update_data['authority_id'] = args['authority_id']
            if args.get('agency_id') is not None:
                update_data['agency_id'] = args['agency_id']
            
            # Update the mapping
            result = authority_model.update_mapping(mapping_id, update_data)
            
            logger.info("update_authority_mapping_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Authority mapping updated successfully",
                data=result
            ), 200
            
        except ValueError as e:
            logger.error("update_authority_mapping_failed", action="put", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=400, message=str(e), data=None)
            response["error_code"] = "400-VAL"
            response["status"] = False
            return response, 400
        except Exception as e:
            logger.error("update_authority_mapping_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to update authority mapping: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DeleteAuthorityMappingAPI(Resource):
    """API for deleting an authority mapping"""
    
    def delete(self, mapping_id):
        """
        DELETE /api/authority-mappings/<mapping_id>/delete
        
        Path parameters:
        - mapping_id: The ID of the mapping to delete
        """
        bind_contextvars(task="DeleteAuthorityMappingAPI")
        start_t = time.time()
        try:
            # Check if mapping exists
            existing = authority_model.get_mapping_by_id(mapping_id)
            if not existing:
                logger.error("delete_authority_mapping_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": f"Mapping with ID {mapping_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=404,
                    message=f"Mapping with ID {mapping_id} not found",
                    data=None
                ), 404
            
            # Delete the mapping
            result = authority_model.delete_mapping(mapping_id)
            
            if not result:
                logger.error("delete_authority_mapping_failed", action="delete", **{"error.code": "500-SYS", "error.message": "Failed to delete authority mapping", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=500,
                    message="Failed to delete authority mapping",
                    data=None
                ), 500
            
            logger.info("delete_authority_mapping_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message=f'Authority mapping {mapping_id} deleted successfully',
                data={"deleted_count": 1}
            )
            
        except Exception as e:
            logger.error("delete_authority_mapping_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to delete authority mapping: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class CheckAuthorityMappingAPI(Resource):
    """API for checking if an authority has mappings"""
    
    def get(self, id_or_authority_id):
        """
        GET /api/authority/<id_or_authority_id>/check-mapping
        
        Path parameters:
        - id_or_authority_id: Either MongoDB ObjectId (_id) or authority_id
        
        Returns:
        - has_mapping: True if mappings exist, False otherwise
        - mappings: List of mapping documents
        """
        bind_contextvars(task="CheckAuthorityMappingAPI")
        start_t = time.time()
        try:
            authority = authority_model.get_authority_by_id(id_or_authority_id)
            
            if not authority:
                try:
                    obj_id = ObjectId(id_or_authority_id)
                    authority = authority_model.collection.find_one({"_id": obj_id})
                    if authority:
                        authority['_id'] = str(authority['_id'])
                except Exception as e:
                    logger.error("check_authority_mapping_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
                    pass
            
            if not authority:
                logger.error("check_authority_mapping_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": f"Authority with ID {id_or_authority_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=404,
                    message=f"Authority with ID {id_or_authority_id} not found",
                    data=None
                ), 404
            
            authority_id = authority.get('authority_id')
            
            mappings_cursor = authority_model.mapping_collection.find(
                {"authority_id": authority_id}
            )
            mappings = []
            for mapping in mappings_cursor:
                mapping['_id'] = str(mapping['_id'])
                mappings.append(mapping)
            
            has_mapping = len(mappings) > 0
            
            logger.info("check_authority_mapping_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Successfully checked authority mappings",
                data={
                    "has_mapping": has_mapping,
                    "mapping_count": len(mappings),
                    "mappings": mappings
                }
            ), 200
            
        except Exception as e:
            logger.error("check_authority_mapping_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to check authority mapping: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500

# Draft endpoints removed - no longer needed


# ==================== ROUTE REGISTRATIONS ====================

# Authorities
api.add_resource(ListAuthoritiesAPI, '/authority')
api.add_resource(CreateAuthorityAPI, '/authority/create')
api.add_resource(GetAuthorityAPI, '/authority/<string:authority_id>')
api.add_resource(UpdateAuthorityAPI, '/authority/<string:authority_id>/update')
api.add_resource(DeleteAuthorityAPI, '/authority/<string:authority_id>/delete')
api.add_resource(CheckAuthorityMappingAPI, '/authority/<string:id_or_authority_id>/check-mapping')


# Authority Mappings
api.add_resource(ListAuthorityMappingsAPI, '/authority-mappings')
api.add_resource(CreateAuthorityMappingAPI, '/authority-mappings/create')
api.add_resource(GetAuthorityMappingAPI, '/authority-mappings/<string:mapping_id>')
api.add_resource(UpdateAuthorityMappingAPI, '/authority-mappings/<string:mapping_id>/update')
api.add_resource(DeleteAuthorityMappingAPI, '/authority-mappings/<string:mapping_id>/delete')
