from core.common.mongo.client import get_mongo_client
import structlog
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from typing import Dict, Any, Optional, List
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()


class RegulatedObjectModel:
    """Model for managing regulated objects in law documents"""
    
    def __init__(self):
        self.client = get_mongo_client()
        self.db = self.client[MigrateConfig.MIGRATE_CORE_DB]
        self.collection = self.db[MongoDBCollectionConfig.LAW_REGULATED_OBJECT_COLLECTION_NAME]
        self.mapping_collection = self.db[MongoDBCollectionConfig.LAW_REGULATED_OBJECT_MAPPING_COLLECTION_NAME]
        self.document_collection = self.db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
        
        # Create indexes
        self._create_indexes()
    
    def _create_indexes(self):
        """Create necessary indexes for collections"""
        try:
            # Indexes for regulated_object collection
            self.collection.create_index("regulated_object_id", unique=True)
            self.collection.create_index("regulated_object_name")
            self.collection.create_index("status")
            self.collection.create_index("created_at")
            
            # Indexes for mapping collection
            self.mapping_collection.create_index("doc_id")
            self.mapping_collection.create_index("regulated_object_id")
            self.mapping_collection.create_index([("doc_id", 1), ("regulated_object_id", 1)])
            
            logger.info("create_indexes_success", action="_create_indexes", **{"event.status": "success"})
        except Exception as e:
            logger.error("create_indexes_failed", action="_create_indexes", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
    
    def check_document_exists(self, doc_id: str) -> bool:
        """Check if a document exists by its ID"""
        return self.document_collection.find_one({"doc_id": doc_id}) is not None
    
    # ==================== REGULATED OBJECT METHODS ====================
    
    def create_regulated_object(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new regulated object"""
        try:
            # Check if regulated_object_id already exists
            if self.collection.find_one({"regulated_object_id": data.get("regulated_object_id")}):
                raise ValueError(f"Regulated object with ID {data.get('regulated_object_id')} already exists")
            
            # Set timestamps
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data['created_at'] = current_time
            data['last_modified_at'] = current_time
            
            # Set default status if not provided
            if 'status' not in data:
                data['status'] = 'Active'
                
            # Ensure regulated_object_name_norm is a list
            if 'regulated_object_name_norm' in data and isinstance(data['regulated_object_name_norm'], str):
                data['regulated_object_name_norm'] = [data['regulated_object_name_norm']]
            
            result = self.collection.insert_one(data)
            created_object = self.get_regulated_object_by_id(data['regulated_object_id'])
            
            logger.info("create_regulated_object_success", action="create_regulated_object", regulated_object_id=data['regulated_object_id'], **{"event.status": "success"})
            return created_object
        except Exception as e:
            logger.error("create_regulated_object_failed", action="create_regulated_object", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def get_regulated_object_by_id(self, regulated_object_id: str) -> Optional[Dict[str, Any]]:
        """Get a regulated object by its ID"""
        obj = self.collection.find_one({"regulated_object_id": regulated_object_id})
        if obj and '_id' in obj:
            obj['_id'] = str(obj['_id'])
        return obj
    
    def update_regulated_object(self, regulated_object_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing regulated object"""
        try:
            # Check if object exists
            existing = self.get_regulated_object_by_id(regulated_object_id)
            if not existing:
                raise ValueError(f"Regulated object with ID {regulated_object_id} not found")
            
            # Update timestamp
            update_data['last_modified_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Remove fields that shouldn't be updated
            update_data.pop('regulated_object_id', None)
            update_data.pop('created_at', None)
            update_data.pop('created_by', None)
            update_data.pop('_id', None)
            
            # Ensure regulated_object_name_norm is a list
            if 'regulated_object_name_norm' in update_data and isinstance(update_data['regulated_object_name_norm'], str):
                update_data['regulated_object_name_norm'] = [update_data['regulated_object_name_norm']]
            
            result = self.collection.update_one(
                {"regulated_object_id": regulated_object_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info("update_regulated_object_success", action="update_regulated_object", regulated_object_id=regulated_object_id, **{"event.status": "success"})
            
            return self.get_regulated_object_by_id(regulated_object_id)
        except Exception as e:
            logger.error("update_regulated_object_failed", action="update_regulated_object", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def delete_regulated_object(self, regulated_object_id: str, delete_mappings: bool = True) -> Dict[str, Any]:
        """Delete a regulated object and optionally its mappings"""
        try:
            # Check if object exists
            existing = self.get_regulated_object_by_id(regulated_object_id)
            if not existing:
                raise ValueError(f"Regulated object with ID {regulated_object_id} not found")
            
            # Delete related mappings if requested
            deleted_mappings = 0
            if delete_mappings:
                mapping_result = self.mapping_collection.delete_many({"regulated_object_id": regulated_object_id})
                deleted_mappings = mapping_result.deleted_count
            
            # Delete the regulated object
            result = self.collection.delete_one({"regulated_object_id": regulated_object_id})
            
            logger.info("delete_regulated_object_success", action="delete_regulated_object", regulated_object_id=regulated_object_id, deleted_mappings=deleted_mappings, **{"event.status": "success"})
            
            return {
                "regulated_object_id": regulated_object_id,
                "deleted": True,
                "deleted_mappings": deleted_mappings
            }
        except Exception as e:
            logger.error("delete_regulated_object_failed", action="delete_regulated_object", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def list_regulated_objects(self, filters: Dict[str, Any] = None, 
                             page: int = 1, 
                             limit: int = 10) -> Dict[str, Any]:
        """List regulated objects with filtering and pagination"""
        try:
            query = {}
            
            if filters:
                # Filter by name (partial match)
                if 'regulated_object_name' in filters and filters['regulated_object_name']:
                    query['regulated_object_name'] = {
                        '$regex': filters['regulated_object_name'], 
                        '$options': 'i'
                    }
                
                # Filter by status
                if 'status' in filters and filters['status']:
                    query['status'] = filters['status']
                
                # Filter by regulated_object_id
                if 'regulated_object_id' in filters and filters['regulated_object_id']:
                    query['regulated_object_id'] = filters['regulated_object_id']
                
                # Filter by date range
                if 'created_date_from' in filters or 'created_date_to' in filters:
                    date_query = {}
                    if 'created_date_from' in filters and filters['created_date_from']:
                        date_query['$gte'] = datetime.fromisoformat(filters['created_date_from'].rstrip('Z'))
                    if 'created_date_to' in filters and filters['created_date_to']:
                        date_query['$lte'] = datetime.fromisoformat(filters['created_date_to'].rstrip('Z'))
                    if date_query:
                        query['created_at'] = date_query
            
            # Calculate pagination
            total = self.collection.count_documents(query)
            skip = (page - 1) * limit
            
            # Execute query
            cursor = self.collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
            
            objects = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                objects.append(doc)
            
            logger.debug("list_regulated_objects_success", action="list_regulated_objects", count=len(objects), page=page, limit=limit, total=total, **{"event.status": "success"})
            
            return {
                'status': 'success',
                'data': objects,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total
                }
            }
        except Exception as e:
            logger.error("list_regulated_objects_failed", action="list_regulated_objects", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    # ==================== MAPPING METHODS ====================
    
    def create_mapping(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new mapping between document and regulated object"""
        try:
            # Check if mapping already exists
            existing = self.mapping_collection.find_one({
                "doc_id": data['doc_id'],
                "regulated_object_id": data['regulated_object_id'],
                "relation_type": data.get('relation_type', 'PRIMARY')
            })
            
            if existing:
                raise ValueError("Mapping already exists")
            
            # Set timestamps
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data['created_at'] = current_time
            data['last_modified_at'] = current_time
            
            # Set default relation_type if not provided
            if 'relation_type' not in data:
                data['relation_type'] = 'PRIMARY'
            
            result = self.mapping_collection.insert_one(data)
            mapping = self.get_mapping_by_id(str(result.inserted_id))
            
            logger.info("create_mapping_success", action="create_mapping", doc_id=data['doc_id'], regulated_object_id=data['regulated_object_id'], **{"event.status": "success"})
            return mapping
        except Exception as e:
            logger.error("create_mapping_failed", action="create_mapping", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def _find_mapping_doc(self, mapping_id: str) -> Optional[Dict[str, Any]]:
        """Resolve a mapping by its regulated_object_id (business key, preferred)
        first, falling back to Mongo's internal _id for callers that already
        have it (e.g. from list/check-mapping responses)."""
        mapping = self.mapping_collection.find_one({"regulated_object_id": mapping_id})
        if not mapping and ObjectId.is_valid(mapping_id):
            mapping = self.mapping_collection.find_one({"_id": ObjectId(mapping_id)})
        return mapping

    def get_mapping_by_id(self, mapping_id: str) -> Optional[Dict[str, Any]]:
        """Get a mapping by its regulated_object_id (preferred) or Mongo _id"""
        try:
            mapping = self._find_mapping_doc(mapping_id)
            if mapping:
                mapping['_id'] = str(mapping['_id'])
                if 'doc_id' in mapping:
                    document = self.document_collection.find_one({"doc_id": mapping['doc_id']})
                    if document:
                        mapping['doc_title'] = document.get('doc_title', '')
            return mapping
        except Exception as e:
            logger.error("get_mapping_by_id_failed", action="get_mapping_by_id", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            return None

    def update_mapping(self, mapping_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing mapping"""
        try:
            # Check if mapping exists
            existing = self._find_mapping_doc(mapping_id)
            if not existing:
                raise ValueError(f"Mapping with ID {mapping_id} not found")

            # Update timestamp
            update_data['last_modified_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Remove fields that shouldn't be updated
            update_data.pop('_id', None)
            update_data.pop('doc_id', None)
            update_data.pop('regulated_object_id', None)
            update_data.pop('created_at', None)
            update_data.pop('created_date', None)
            update_data.pop('created_by', None)

            result = self.mapping_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": update_data}
            )

            if result.modified_count > 0:
                logger.info("update_mapping_success", action="update_mapping", mapping_id=mapping_id, **{"event.status": "success"})

            return self.get_mapping_by_id(mapping_id)
        except Exception as e:
            logger.error("update_mapping_failed", action="update_mapping", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise

    def delete_mapping(self, mapping_id: str) -> Dict[str, Any]:
        """Delete a mapping"""
        try:
            # Check if mapping exists
            existing = self._find_mapping_doc(mapping_id)
            if not existing:
                raise ValueError(f"Mapping with ID {mapping_id} not found")

            result = self.mapping_collection.delete_one({"_id": existing["_id"]})
            
            if result.deleted_count > 0:
                logger.info("delete_mapping_success", action="delete_mapping", mapping_id=mapping_id, **{"event.status": "success"})
                return {"mapping_id": mapping_id, "deleted": True}
            else:
                raise Exception("Failed to delete mapping")
        except Exception as e:
            logger.error("delete_mapping_failed", action="delete_mapping", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def list_mappings(self, filters: Dict[str, Any] = None, 
                     page: int = 1, 
                     limit: int = 10) -> Dict[str, Any]:
        """List mappings with filtering and pagination"""
        try:
            query = {}
            
            if filters:
                # Filter by doc_id
                if 'doc_id' in filters and filters['doc_id']:
                    query['doc_id'] = filters['doc_id']
                
                # Filter by regulated_object_id
                if 'regulated_object_id' in filters and filters['regulated_object_id']:
                    query['regulated_object_id'] = filters['regulated_object_id']
                
                # Filter by relation_type
                if 'relation_type' in filters and filters['relation_type']:
                    query['relation_type'] = filters['relation_type']
                
                # Filter by date range
                if 'created_date_from' in filters or 'created_date_to' in filters:
                    date_query = {}
                    if 'created_date_from' in filters and filters['created_date_from']:
                        date_query['$gte'] = datetime.fromisoformat(filters['created_date_from'].rstrip('Z'))
                    if 'created_date_to' in filters and filters['created_date_to']:
                        date_query['$lte'] = datetime.fromisoformat(filters['created_date_to'].rstrip('Z'))
                    if date_query:
                        query['created_at'] = date_query
            
            # Calculate pagination
            total = self.mapping_collection.count_documents(query)
            skip = (page - 1) * limit
            
            # Execute query
            cursor = self.mapping_collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
            
            mappings = []
            for doc in cursor:
                regulated_object = self.get_regulated_object_by_id(doc['regulated_object_id'] )
                doc['_id'] = str(doc['_id'])
                doc['regulated_object_name'] = regulated_object.get('regulated_object_name', '')
                if 'doc_id' in doc:
                    document = self.document_collection.find_one({"doc_id": doc['doc_id']})
                    if document:
                        doc['doc_title'] = document.get('doc_title', '')
                mappings.append(doc)
            
            logger.debug("list_mappings_success", action="list_mappings", count=len(mappings), page=page, limit=limit, total=total, **{"event.status": "success"})
            
            return {
                'status': 'success',
                'data': mappings,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total
                }
            }
        except Exception as e:
            logger.error("list_mappings_failed", action="list_mappings", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def get_mappings_by_doc_id(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all mappings for a specific document"""
        try:
            cursor = self.mapping_collection.find({"doc_id": doc_id})
            mappings = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                mappings.append(doc)
            return mappings
        except Exception as e:
            logger.error("get_mappings_by_doc_id_failed", action="get_mappings_by_doc_id", doc_id=doc_id, **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            return []
    
    def get_mappings_by_regulated_object_id(self, regulated_object_id: str) -> List[Dict[str, Any]]:
        """Get all mappings for a specific regulated object"""
        try:
            cursor = self.mapping_collection.find({"regulated_object_id": regulated_object_id})
            mappings = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                mappings.append(doc)
            return mappings
        except Exception as e:
            logger.error("get_mappings_by_regulated_object_id_failed", action="get_mappings_by_regulated_object_id", regulated_object_id=regulated_object_id, **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            return []
    
    # ==================== SOCIAL RELATION MAPPING METHODS ====================
    
    def create_social_relation_mapping(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new social relation mapping"""
        try:
            # Validate that social_relation exists
            if not self.get_social_relation_by_id(data.get('social_relation_id')):
                raise ValueError(f"Social relation {data.get('social_relation_id')} does not exist")
            
            # Check for duplicate mapping
            existing = self.mapping_collection.find_one({
                "doc_id": data.get('doc_id'),
                "article_id": data.get('article_id'),
                "social_relation_id": data.get('social_relation_id')
            })
            if existing:
                raise ValueError("This mapping already exists")
            
            # Set timestamps
            data['created_date'] = datetime.utcnow()
            data['last_modified'] = datetime.utcnow()
            
            # Set default relation_type if not provided
            if 'relation_type' not in data:
                data['relation_type'] = 'PRIMARY'
            
            result = self.mapping_collection.insert_one(data)
            created_mapping = self.mapping_collection.find_one({"_id": result.inserted_id})
            created_mapping['_id'] = str(created_mapping['_id'])
            
            logger.info("create_social_relation_mapping_success", action="create_social_relation_mapping", inserted_id=str(result.inserted_id), **{"event.status": "success"})
            return created_mapping
        except Exception as e:
            logger.error("create_social_relation_mapping_failed", action="create_social_relation_mapping", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def get_social_relation_mapping_by_id(self, mapping_id: str) -> Optional[Dict[str, Any]]:
        """Get a social relation mapping by its ObjectId"""
        try:
            if not ObjectId.is_valid(mapping_id):
                return None
            
            mapping = self.mapping_collection.find_one({"_id": ObjectId(mapping_id)})
            if mapping:
                mapping['_id'] = str(mapping['_id'])
            return mapping
        except Exception as e:
            logger.error("get_social_relation_mapping_by_id_failed", action="get_social_relation_mapping_by_id", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            return None

    def get_mapping_by_doc_and_object(self, doc_id: str, regulated_object_id: str) -> Optional[Dict[str, Any]]:
        """Get a mapping by document ID and regulated object ID"""
        try:
            mapping = self.mapping_collection.find_one({
                "doc_id": doc_id,
                "regulated_object_id": regulated_object_id
            })
            if mapping:
                mapping['_id'] = str(mapping['_id'])
            return mapping
        except Exception as e:
            logger.error("get_mapping_by_doc_and_object_failed", action="get_mapping_by_doc_and_object", doc_id=doc_id, regulated_object_id=regulated_object_id, **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            return None
    
    def update_social_relation_mapping(self, mapping_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing social relation mapping"""
        try:
            if not ObjectId.is_valid(mapping_id):
                raise ValueError(f"Invalid mapping ID: {mapping_id}")
            
            # Check if mapping exists
            existing = self.get_social_relation_mapping_by_id(mapping_id)
            if not existing:
                raise ValueError(f"Social relation mapping with ID {mapping_id} not found")
            
            # Update timestamp
            update_data['last_modified'] = datetime.utcnow()
            
            # Remove fields that shouldn't be updated
            update_data.pop('_id', None)
            update_data.pop('created_date', None)
            update_data.pop('created_by', None)
            
            result = self.mapping_collection.update_one(
                {"_id": ObjectId(mapping_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info("update_social_relation_mapping_success", action="update_social_relation_mapping", mapping_id=mapping_id, **{"event.status": "success"})
            
            return self.get_social_relation_mapping_by_id(mapping_id)
        except Exception as e:
            logger.error("update_social_relation_mapping_failed", action="update_social_relation_mapping", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def delete_social_relation_mapping(self, mapping_id: str) -> Dict[str, Any]:
        """Delete a social relation mapping"""
        try:
            if not ObjectId.is_valid(mapping_id):
                raise ValueError(f"Invalid mapping ID: {mapping_id}")
            
            # Check if mapping exists
            existing = self.get_social_relation_mapping_by_id(mapping_id)
            if not existing:
                raise ValueError(f"Social relation mapping with ID {mapping_id} not found")
            
            # Delete the mapping
            result = self.mapping_collection.delete_one({"_id": ObjectId(mapping_id)})
            
            logger.info("delete_social_relation_mapping_success", action="delete_social_relation_mapping", mapping_id=mapping_id, **{"event.status": "success"})
            
            return {
                "mapping_id": mapping_id,
                "deleted": True
            }
        except Exception as e:
            logger.error("delete_social_relation_mapping_failed", action="delete_social_relation_mapping", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def list_social_relation_mappings(self, filters: Dict[str, Any] = None,
                                     page: int = 1,
                                     limit: int = 10) -> Dict[str, Any]:
        """List social relation mappings with filtering and pagination"""
        try:
            query = {}
            
            if filters:
                # Filter by doc_id
                if 'doc_id' in filters and filters['doc_id']:
                    query['doc_id'] = filters['doc_id']
                
                # Filter by article_id
                if 'article_id' in filters and filters['article_id']:
                    query['article_id'] = filters['article_id']
                
                # Filter by social_relation_id
                if 'social_relation_id' in filters and filters['social_relation_id']:
                    query['social_relation_id'] = filters['social_relation_id']
                
                # Filter by relation_type
                if 'relation_type' in filters and filters['relation_type']:
                    query['relation_type'] = filters['relation_type']
            
            # Calculate pagination
            total = self.mapping_collection.count_documents(query)
            skip = (page - 1) * limit
            
            # Execute query
            cursor = self.mapping_collection.find(query).skip(skip).limit(limit).sort("created_date", -1)
            
            mappings = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                mappings.append(doc)
            
            logger.debug("list_social_relation_mappings_success", action="list_social_relation_mappings", count=len(mappings), page=page, limit=limit, total=total, **{"event.status": "success"})
            
            return {
                'status': 'success',
                'data': mappings,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total
                }
            }
        except Exception as e:
            logger.error("list_social_relation_mappings_failed", action="list_social_relation_mappings", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
# Draft model removed - no longer needed