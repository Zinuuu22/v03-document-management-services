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
from services.api.biz.regulated_object.regulated_object_models import RegulatedObjectModel
logger = structlog.get_logger()

# Initialize model
regulated_object_model = RegulatedObjectModel()
# ==================== REGULATED OBJECT APIs ====================

class ListRegulatedObjectsAPI(Resource):
    """API for listing regulated objects with filters and pagination"""
    
    def get(self):
        """
        GET /api/regulated-objects
        Query parameters:
        - regulated_object_name: Filter by name (partial match)
        - status: Filter by status (Active/Inactive)
        - regulated_object_id: Filter by specific ID
        - created_date_from: Start date filter (ISO format)
        - created_date_to: End date filter (ISO format)
        - page: Page number (default: 1)
        - limit: Items per page (default: 10, max: 100)
        """
        bind_contextvars(task="ListRegulatedObjectsAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('regulated_object_name', type=str, required=False, default='', location='args')
        parser.add_argument('status', type=str, required=False, default='', location='args')
        parser.add_argument('regulated_object_id', type=str, required=False, default='', location='args')
        parser.add_argument('created_date_from', type=str, required=False, default='', location='args')
        parser.add_argument('created_date_to', type=str, required=False, default='', location='args')
        parser.add_argument('page', type=int, required=False, default=1, location='args')
        parser.add_argument('limit', type=int, required=False, default=10, location='args')
        args = parser.parse_args()
        
        try:
            # Validate pagination
            page = max(1, args['page'])
            limit = min(100, max(1, args['limit']))
            
            # Prepare filters
            filters = {}
            if args['regulated_object_name']:
                filters['regulated_object_name'] = args['regulated_object_name']
            if args['status']:
                filters['status'] = args['status']
            if args['regulated_object_id']:
                filters['regulated_object_id'] = args['regulated_object_id']
            if args['created_date_from']:
                filters['created_date_from'] = args['created_date_from']
            if args['created_date_to']:
                filters['created_date_to'] = args['created_date_to']
            
            # Get paginated results
            result = regulated_object_model.list_regulated_objects(
                filters=filters,
                page=page,
                limit=limit
            )
            
            logger.info("get_regulated_objects_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Successfully retrieved regulated objects",
                data=result), 200
            
        except Exception as e:
            logger.error("get_regulated_objects_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to retrieve regulated objects: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class CreateRegulatedObjectAPI(Resource):
    """API for creating a new regulated object"""
    
    def _normalize_name_norm(self, value):
        if value is None:
            return None
        if isinstance(value, (str, list)):
            return value
        raise ValueError("regulated_object_name_norm must be a string or list of strings")
    
    def post(self):
        """
        POST /api/regulated-objects
        Body:
        - regulated_object_id: Unique identifier (required)
        - regulated_object_name: Name of the regulated object (required)
        - regulated_object_name_norm: Normalized names for search (string or list of strings, optional)
        - description: Description (optional)
        - status: Status (Active/Inactive, default: Active)
        - metadata: Additional metadata (dict, optional)
        - created_by: User ID who created this record (optional)
        """
        bind_contextvars(task="CreateRegulatedObjectAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('regulated_object_name', type=str, required=True, 
                          help='Regulated object name is required', location='json')        
        parser.add_argument('regulated_object_name_norm', type=self._normalize_name_norm, required=False, 
                            location='json')
        parser.add_argument('description', type=str, required=False, location='json')
        parser.add_argument('status', type=str, required=False, default='Active', 
                          choices=('Active', 'Inactive'), location='json')
        parser.add_argument('metadata', type=dict, required=False, location='json')
        parser.add_argument('created_by', type=str, required=False, location='json')
        args = parser.parse_args()
        
        try:
            # Prepare data for creation
            data = {
                'regulated_object_id': str(uuid.uuid4()),
                'regulated_object_name': args['regulated_object_name'],
                'status': args['status']
            }
            
            # Add optional fields if provided
            if args['regulated_object_name_norm'] is not None:
                data['regulated_object_name_norm'] = args['regulated_object_name_norm']
            if args['description'] is not None:
                data['description'] = args['description']
            if args['metadata'] is not None:
                data['metadata'] = args['metadata']
            if args['created_by'] is not None:
                data['created_by'] = args['created_by']
            
            # Create the regulated object
            result = regulated_object_model.create_regulated_object(data)
            
            logger.info("create_regulated_object_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=201,
                message="Regulated object created successfully",
                data=result
            ), 201
            
        except ValueError as e:
            logger.error("create_regulated_object_failed", action="post", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(
                code=400,
                message=str(e),
                data=None
            ), 400
            
        except Exception as e:
            logger.error("create_regulated_object_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message="Failed to create regulated object", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UpdateRegulatedObjectAPI(Resource):
    """API for updating an existing regulated object"""
    
    def put(self, regulated_object_id):
        """
        PUT /api/regulated-objects/<regulated_object_id>/update
        
        Path parameters:
        - regulated_object_id: The ID of the regulated object to update
        
        Body:
        - regulated_object_name: Updated name (optional)
        - regulated_object_name_norm: Updated normalized names (string or list, optional)
        - description: Updated description (optional)
        - status: Updated status (Active/Inactive, optional)
        - metadata: Updated metadata (dict, optional)
        - last_modified_by: User ID who is making the update (required)
        """
        bind_contextvars(task="UpdateRegulatedObjectAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('regulated_object_name', type=str, required=False, location='json')
        parser.add_argument('regulated_object_name_norm', type=(str, list), required=False, location='json')
        parser.add_argument('description', type=str, required=False, location='json')
        parser.add_argument('status', type=str, required=False, choices=('Active', 'Inactive'), location='json')
        parser.add_argument('metadata', type=dict, required=False, location='json')
        parser.add_argument('last_modified_by', type=str, required=True, 
                          help='User ID who is making the update is required', 
                          location='json')
        args = parser.parse_args()
        
        try:
            # Check if the regulated object exists
            existing = regulated_object_model.get_regulated_object_by_id(regulated_object_id)
            if not existing:
                return make_response(
                    code=404,
                    message=f"Regulated object with ID {regulated_object_id} not found",
                    data=None
                ), 404
            
            # Prepare update data
            update_data = {}
            if args['regulated_object_name'] is not None:
                update_data['regulated_object_name'] = args['regulated_object_name']
            if args['regulated_object_name_norm'] is not None:
                update_data['regulated_object_name_norm'] = args['regulated_object_name_norm']
            if args['description'] is not None:
                update_data['description'] = args['description']
            if args['status'] is not None:
                update_data['status'] = args['status']
            if args['metadata'] is not None:
                update_data['metadata'] = args['metadata']
            
            # Add last modified info
            update_data['last_modified_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            update_data['last_modified_by'] = args['last_modified_by']
            
            # Update the regulated object
            result = regulated_object_model.update_regulated_object(regulated_object_id, update_data)
            
            if not result:
                logger.error("update_regulated_object_failed", action="put", **{"error.code": "500-SYS", "error.message": "Failed to update regulated object", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=500,
                    message="Failed to update regulated object",
                    data=None
                ), 500
            
            logger.info("update_regulated_object_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Regulated object updated successfully",
                data=result
            )
            
        except ValueError as e:
            logger.error("update_regulated_object_failed", action="put", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(
                code=400,
                message=str(e),
                data=None
            ), 400
            
        except Exception as e:
            logger.error("update_regulated_object_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to update regulated object: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetRegulatedObjectAPI(Resource):
    """API for retrieving a single regulated object by ID"""
    
    def get(self, regulated_object_id):
        """
        GET /api/regulated-objects/<regulated_object_id>
        
        Path parameters:
        - regulated_object_id: The ID of the regulated object to retrieve
        """
        bind_contextvars(task="GetRegulatedObjectAPI")
        start_t = time.time()
        try:
            # Get the regulated object
            regulated_object = regulated_object_model.get_regulated_object_by_id(regulated_object_id)
            
            if not regulated_object:
                logger.error("get_regulated_object_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": f"Regulated object with ID {regulated_object_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=404,
                    message=f"Regulated object with ID {regulated_object_id} not found",
                    data=None
                ), 404
            
            logger.info("get_regulated_object_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Successfully retrieved regulated object",
                data=regulated_object
            )
            
        except Exception as e:
            logger.error("get_regulated_object_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to retrieve regulated object: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500



class DeleteRegulatedObjectAPI(Resource):
    """API for deleting a regulated object"""
    
    def delete(self, regulated_object_id):
        """
        DELETE /api/regulated-objects/<regulated_object_id>/delete
        
        Query parameters:
        - delete_mappings: Whether to delete related mappings (default: true)
        """
        bind_contextvars(task="DeleteRegulatedObjectAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('delete_mappings', type=bool, required=False, default=True, 
                          location='args',
                          help='Whether to delete related mappings')
        args = parser.parse_args()
        
        try:
            # Check if the regulated object exists
            existing = regulated_object_model.get_regulated_object_by_id(regulated_object_id)
            if not existing:
                logger.error("delete_regulated_object_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": f"Regulated object with ID {regulated_object_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=404,
                    message=f"Regulated object with ID {regulated_object_id} not found",
                    data=None
                ), 404
            
            # Delete the regulated object
            result = regulated_object_model.delete_regulated_object(
                regulated_object_id=regulated_object_id,
                delete_mappings=args['delete_mappings']
            )
            
            logger.info("delete_regulated_object_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message=f"Regulated object {regulated_object_id} deleted successfully",
                data=result
            )
            
        except ValueError as e:
            logger.error("delete_regulated_object_failed", action="delete", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(
                code=400,
                message=str(e),
                data=None
            ), 400
            
        except Exception as e:
            logger.error("delete_regulated_object_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to delete regulated object: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# ==================== REGULATED OBJECT MAPPING APIs ====================

class ListRegulatedObjectMappingsAPI(Resource):
    """API for listing regulated object mappings with filters and pagination"""
    
    def get(self):
        """
        GET /api/regulated-object-mappings
        Query parameters:
        - doc_id: Filter by document ID
        - regulated_object_id: Filter by regulated object ID
        - relation_type: Filter by relation type (Primary/Secondary)
        - page: Page number (default: 1)
        - limit: Items per page (default: 10, max: 100)
        """
        bind_contextvars(task="ListRegulatedObjectMappingsAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('doc_id', type=str, required=False, location='args')
        parser.add_argument('regulated_object_id', type=str, required=False, location='args')
        parser.add_argument('relation_type', type=str, required=False, location='args')
        parser.add_argument('page', type=int, required=False, default=1, location='args')
        parser.add_argument('limit', type=int, required=False, default=10, location='args')
        args = parser.parse_args()
        
        try:
            # Prepare filters
            filters = {}
            if args['doc_id']:
                filters['doc_id'] = args['doc_id']
            if args['regulated_object_id']:
                filters['regulated_object_id'] = args['regulated_object_id']
            if args['relation_type']:
                filters['relation_type'] = args['relation_type']
            
            # Get paginated results
            result = regulated_object_model.list_mappings(
                filters=filters,
                page=args['page'],
                limit=min(100, max(1, args['limit']))
            )
            
            logger.info("get_regulated_object_mappings_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Successfully retrieved regulated object mappings",
                data=result
            ), 200
            
        except Exception as e:
            logger.error("get_regulated_object_mappings_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to retrieve regulated object mappings: {str(e)}", data=[])
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class CreateRegulatedObjectMappingAPI(Resource):
    """API for creating a new regulated object mapping"""
    
    def post(self):
        """
        POST /api/regulated-object-mappings/create
        Body:
        - doc_id: Document ID (required)
        - regulated_object_id: Regulated object ID (required)
        - relation_type: Relation type (Primary/Secondary, default: Primary)
        - metadata: Additional metadata (optional)
        - created_by: User ID who created this mapping (required)
        """
        bind_contextvars(task="CreateRegulatedObjectMappingAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('doc_id', type=str, required=True, 
                          help='Document ID is required', location='json')
        parser.add_argument('regulated_object_id', type=str, required=True,
                          help='Regulated object ID is required', location='json')
        parser.add_argument('relation_type', type=str, required=False, 
                          default='PRIMARY', choices=('PRIMARY', 'SECONDARY', 'REFERENCE'),
                          location='json')
        parser.add_argument('metadata', type=dict, required=False, location='json')
        parser.add_argument('created_by', type=str, required=True,
                          help='Created by user ID is required', location='json')
        args = parser.parse_args()
        
        try:
            # Check if regulated object exists
            if not regulated_object_model.get_regulated_object_by_id(args['regulated_object_id']):
                raise ValueError(f"Regulated object with ID {args['regulated_object_id']} not found")
                
            # Check if document exists
            existing_doc = regulated_object_model.check_document_exists(args['doc_id'])
            if not existing_doc:
                raise ValueError(f"Document with ID {args['doc_id']} not found")

            # Check if mapping already exists
            existing = regulated_object_model.get_mapping_by_doc_and_object(
                args['doc_id'], 
                args['regulated_object_id']
            )
            if existing:
                raise ValueError(f"Mapping already exists for document {args['doc_id']} and regulated object {args['regulated_object_id']}")
            
            # Prepare mapping data
            mapping_data = {
                'doc_id': args['doc_id'],
                'regulated_object_id': args['regulated_object_id'],
                'relation_type': args['relation_type'],
                'created_by': args['created_by'],
                'created_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            if args['metadata']:
                mapping_data['metadata'] = args['metadata']
            
            # Create the mapping
            result = regulated_object_model.create_mapping(mapping_data)
            
            logger.info("create_regulated_object_mapping_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=201,
                message="Regulated object mapping created successfully",
                data=result
            ), 201
            
        except ValueError as e:
            logger.error("create_regulated_object_mapping_failed", action="post", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(
                code=400,
                message=str(e),
                data=None
            ), 400
            
        except Exception as e:
            logger.error("create_regulated_object_mapping_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to create regulated object mapping: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UpdateRegulatedObjectMappingAPI(Resource):
    def put(self, mapping_id):
        bind_contextvars(task="UpdateRegulatedObjectMappingAPI")
        start_t = time.time()
        try:            
            # Parse request arguments
            parser = reqparse.RequestParser()
            parser.add_argument('relation_type', type=str, required=False)
            parser.add_argument('last_modified_by', type=str, required=True)
            parser.add_argument('metadata', type=dict, required=False)
            args = parser.parse_args()

            # Get the existing mapping
            mapping = regulated_object_model.get_mapping_by_id(mapping_id)
            if not mapping:
                logger.error("update_regulated_object_mapping_failed", action="put", **{"error.code": "404-NOTFOUND", "error.message": f"Mapping with ID {mapping_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=404,
                    message=f"Mapping with ID {mapping_id} not found",
                    data=None
                ), 404

            # Prepare update data
            update_data = {
                'last_modified_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'last_modified_by': args['last_modified_by']
            }
            
            if args.get('relation_type') is not None:
                update_data['relation_type'] = args['relation_type']
            if args.get('metadata') is not None:
                update_data['metadata'] = args['metadata']
            
            # Update the mapping
            result = regulated_object_model.update_mapping(mapping_id, update_data)
            
            # Convert result to dictionary if it's not already one
            if hasattr(result, 'to_dict'):
                result_data = result.to_dict()
            elif hasattr(result, '__dict__'):
                result_data = result.__dict__
                # Remove any private attributes (starting with _)
                result_data = {k: v for k, v in result_data.items() if not k.startswith('_')}
            else:
                result_data = dict(result) if result is not None else {}

            logger.info("update_regulated_object_mapping_success", action="put", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Regulated object mapping updated successfully",
                data=result_data
            ), 200
            
        except ValueError as e:
            logger.error("update_regulated_object_mapping_failed", action="put", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=400, message=str(e), data=None)
            response["error_code"] = "400-VAL"
            response["status"] = False
            return response, 400
        except Exception as e:
            logger.error("update_regulated_object_mapping_failed", action="put", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to update regulated object mapping: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DeleteRegulatedObjectMappingAPI(Resource):
    """API for deleting a regulated object mapping"""
    
    def delete(self, mapping_id):
        """
        DELETE /api/regulated-object-mappings/<mapping_id>/delete
        
        Path parameters:
        - mapping_id: The ID of the mapping to delete
        """
        bind_contextvars(task="DeleteRegulatedObjectMappingAPI")
        start_t = time.time()
        try:
            # Check if mapping exists
            existing = regulated_object_model.get_mapping_by_id(mapping_id)
            if not existing:
                logger.error("delete_regulated_object_mapping_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": f"Mapping with ID {mapping_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=404,
                    message=f"Mapping with ID {mapping_id} not found",
                    data=None
                ), 404
            
            # Delete the mapping
            result = regulated_object_model.delete_mapping(mapping_id)
            
            if not result:
                logger.error("delete_regulated_object_mapping_failed", action="delete", **{"error.code": "500-SYS", "error.message": "Failed to delete regulated object mapping", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=500,
                    message="Failed to delete regulated object mapping",
                    data=None
                ), 500
            
            logger.info("delete_regulated_object_mapping_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message=f'Regulated object mapping {mapping_id} deleted successfully',
                data={"deleted_count": 1}
            )
            
        except Exception as e:
            logger.error("delete_regulated_object_mapping_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to delete regulated object mapping: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetRegulatedObjectMappingAPI(Resource):
    """API for getting a single regulated object mapping by ID"""
    
    def get(self, mapping_id):
        """
        GET /api/regulated-object-mappings/<mapping_id>
        
        Path parameters:
        - mapping_id: The ID of the mapping to retrieve
        """
        bind_contextvars(task="GetRegulatedObjectMappingAPI")
        start_t = time.time()
        try:
            # Get the mapping
            mapping = regulated_object_model.get_mapping_by_id(mapping_id)
            
            if not mapping:
                logger.error("get_regulated_object_mapping_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": f"Mapping with ID {mapping_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=404,
                    message=f"Mapping with ID {mapping_id} not found",
                    data=None
                ), 404
            
            logger.info("get_regulated_object_mapping_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Successfully retrieved regulated object mapping",
                data=mapping
            )
            
        except Exception as e:
            logger.error("get_regulated_object_mapping_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to retrieve regulated object mapping: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500
        
class CheckRegulatedObjectMappingAPI(Resource):
    """API for checking if a regulated object has mappings"""
    
    def get(self, id_or_regulated_object_id):
        """
        GET /api/regulated-objects/<id_or_regulated_object_id>/check-mapping
        
        Path parameters:
        - id_or_regulated_object_id: Either MongoDB ObjectId (_id) or regulated_object_id
        
        Returns:
        - has_mapping: True if mappings exist, False otherwise
        - mappings: List of mapping documents
        """
        bind_contextvars(task="CheckRegulatedObjectMappingAPI")
        start_t = time.time()
        try:
            regulated_object = regulated_object_model.get_regulated_object_by_id(id_or_regulated_object_id)
            
            if not regulated_object:
                try:
                    obj_id = ObjectId(id_or_regulated_object_id)
                    regulated_object = regulated_object_model.collection.find_one({"_id": obj_id})
                    if regulated_object:
                        regulated_object['_id'] = str(regulated_object['_id'])
                except:
                    pass
            
            if not regulated_object:
                logger.error("check_regulated_object_mapping_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": f"Regulated object with ID {id_or_regulated_object_id} not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    code=404,
                    message=f"Regulated object with ID {id_or_regulated_object_id} not found",
                    data=None
                ), 404
            
            regulated_object_id = regulated_object.get('regulated_object_id')
            
            mappings_cursor = regulated_object_model.mapping_collection.find(
                {"regulated_object_id": regulated_object_id}
            )
            mappings = []
            for mapping in mappings_cursor:
                mapping['_id'] = str(mapping['_id'])
                mappings.append(mapping)
            
            has_mapping = len(mappings) > 0
            
            logger.info("check_regulated_object_mapping_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
            return make_response(
                code=200,
                message="Successfully checked regulated object mappings",
                data={
                    "has_mapping": has_mapping,
                    "mapping_count": len(mappings),
                    "mappings": mappings
                }
            ), 200
            
        except Exception as e:
            logger.error("check_regulated_object_mapping_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(code=500, message=f"Failed to check regulated object mapping: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# ==================== API ENDPOINTS ====================

# Regulated Objects
api.add_resource(ListRegulatedObjectsAPI, '/regulated-objects')
api.add_resource(CreateRegulatedObjectAPI, '/regulated-objects/create')
api.add_resource(GetRegulatedObjectAPI, '/regulated-objects/<string:regulated_object_id>')
api.add_resource(UpdateRegulatedObjectAPI, '/regulated-objects/<string:regulated_object_id>/update')
api.add_resource(DeleteRegulatedObjectAPI, '/regulated-objects/<string:regulated_object_id>/delete')
api.add_resource(CheckRegulatedObjectMappingAPI, '/regulated-objects/<string:id_or_regulated_object_id>/check-mapping')

# Regulated Object Mappings
api.add_resource(ListRegulatedObjectMappingsAPI, '/regulated-object-mappings')
api.add_resource(CreateRegulatedObjectMappingAPI, '/regulated-object-mappings/create')
api.add_resource(UpdateRegulatedObjectMappingAPI, '/regulated-object-mappings/<string:mapping_id>/update')
api.add_resource(GetRegulatedObjectMappingAPI, '/regulated-object-mappings/<string:mapping_id>')
api.add_resource(DeleteRegulatedObjectMappingAPI, '/regulated-object-mappings/<string:mapping_id>/delete')

