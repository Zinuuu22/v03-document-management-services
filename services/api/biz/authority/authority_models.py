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

effective_status_map = {
    "Không xác định": "b04750de-31f5-4266-b5c7-ac56c2bac946",
    "Hết hiệu lực": "a2e5eb7f-140b-43e9-9a9e-0b351466ae05",
    "Còn hiệu lực": "3969bc0a-a285-4a6d-9865-5b549cf88d20"
}
unknown_effective_status_id = "b04750de-31f5-4266-b5c7-ac56c2bac946"



class AuthorityModel:
    """Model for managing authority information in law documents"""
    
    def __init__(self):
        self.client = get_mongo_client()
        self.db = self.client[MigrateConfig.MIGRATE_CORE_DB]
        self.collection = self.db[MongoDBCollectionConfig.LAW_AUTHORITY_COLLECTION_NAME]
        self.mapping_collection = self.db[MongoDBCollectionConfig.LAW_AUTHORITY_MAPPING_COLLECTION_NAME]
        self.article_collection = self.db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
        self.document_collection = self.db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
        self.agencies_collection = self.db[MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME]
        
        # Create indexes
        self._create_indexes()
    
    def _create_indexes(self):
        """Create necessary indexes for collections"""
        try:
            # Indexes for authority collection
            self.collection.create_index("authority_id", unique=True)
            self.collection.create_index("status")
            self.collection.create_index("created_at")
            
            # Indexes for mapping collection
            self.mapping_collection.create_index("doc_id")
            self.mapping_collection.create_index("article_id")
            self.mapping_collection.create_index("authority_id")
            self.mapping_collection.create_index("agency_id")
            self.mapping_collection.create_index([("doc_id", 1), ("authority_id", 1)])
            
            logger.info("create_indexes_success", action="_create_indexes", **{"event.status": "success"})
        except Exception as e:
            logger.error("create_indexes_failed", action="_create_indexes", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
    
    def check_document_exists(self, doc_id: str) -> bool:
        """Check if a document exists by its ID"""
        return self.document_collection.find_one({"doc_id": doc_id}) is not None
    
    # ==================== AUTHORITY METHODS ====================
    
    def create_authority(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new authority definition"""
        try:
            # Check if authority_id already exists
            if self.collection.find_one({"authority_id": data.get("authority_id")}):
                raise ValueError(f"Authority with ID {data.get('authority_id')} already exists")
            
            # Set timestamps
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data['created_at'] = current_time
            data['last_modified_at'] = current_time
            
            # Set default status if not provided
            if 'status' not in data:
                data['status'] = 'ACTIVE'
            
            # Normalize status to uppercase
            if 'status' in data:
                data['status'] = data['status'].upper()
            
            # Translate doc_effective_status to effective_status_id if provided
            if 'doc_effective_status' in data:
                status_name = data.pop('doc_effective_status', '').strip()
                data['effective_status_id'] = effective_status_map.get(status_name, unknown_effective_status_id)
            
            # Normalize doc_expire_date to doc_expiry_date
            if 'doc_expire_date' in data:
                data['doc_expiry_date'] = data.pop('doc_expire_date')
            
            result = self.collection.insert_one(data)
            created_authority = self.get_authority_by_id(data['authority_id'])
            
            logger.info("create_authority_success", action="create_authority", authority_id=data['authority_id'], **{"event.status": "success"})
            return created_authority
        except Exception as e:
            logger.error("create_authority_failed", action="create_authority", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def get_authority_by_id(self, authority_id: str) -> Optional[Dict[str, Any]]:
        """Get an authority by its ID"""
        authority = self.collection.find_one({"authority_id": authority_id})
        if authority and '_id' in authority:
            authority['_id'] = str(authority['_id'])
        return authority
    
    def update_authority(self, authority_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing authority"""
        try:
            # Check if authority exists
            existing = self.get_authority_by_id(authority_id)
            if not existing:
                raise ValueError(f"Authority with ID {authority_id} not found")
            
            # Update timestamp
            update_data['last_modified_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if 'doc_effective_status' in update_data:
                status_name = update_data.pop('doc_effective_status', '').strip()
                update_data['effective_status_id'] = effective_status_map.get(status_name, unknown_effective_status_id)
            
            # Normalize doc_expire_date to doc_expiry_date
            if 'doc_expire_date' in update_data:
                update_data['doc_expiry_date'] = update_data.pop('doc_expire_date')
            
            # Normalize status to uppercase
            if 'status' in update_data:
                update_data['status'] = update_data['status'].upper()
            
            # Remove fields that shouldn't be updated
            update_data.pop('authority_id', None)
            update_data.pop('created_at', None)
            update_data.pop('created_date', None)
            update_data.pop('created_by', None)
            update_data.pop('_id', None)
            
            result = self.collection.update_one(
                {"authority_id": authority_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info("update_authority_success", action="update_authority", authority_id=authority_id, **{"event.status": "success"})
            
            return self.get_authority_by_id(authority_id)
        except Exception as e:
            logger.error("update_authority_failed", action="update_authority", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def delete_authority(self, authority_id: str, delete_mappings: bool = True) -> Dict[str, Any]:
        """Delete an authority and optionally its mappings (cascade)"""
        try:
            # Check if authority exists
            existing = self.get_authority_by_id(authority_id)
            if not existing:
                raise ValueError(f"Authority with ID {authority_id} not found")
            
            # Delete related mappings if requested
            deleted_mappings = 0
            if delete_mappings:
                mapping_result = self.mapping_collection.delete_many({"authority_id": authority_id})
                deleted_mappings = mapping_result.deleted_count
            
            # Delete the authority
            result = self.collection.delete_one({"authority_id": authority_id})
            
            logger.info("delete_authority_success", action="delete_authority", authority_id=authority_id, deleted_mappings=deleted_mappings, **{"event.status": "success"})
            
            return {
                "authority_id": authority_id,
                "deleted": True,
                "deleted_mappings": deleted_mappings
            }
        except Exception as e:
            logger.error("delete_authority_failed", action="delete_authority", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def list_authorities(self, filters: Dict[str, Any] = None, 
                        page: int = 1, 
                        limit: int = 10) -> Dict[str, Any]:
        """List authorities with filtering and pagination"""
        try:
            query = {}
            
            if filters:
                # Filter by agency_id
                if 'agency_id' in filters and filters['agency_id']:
                    # Query mappings to get authority_ids for this agency
                    mapping_query = {"agency_id": filters['agency_id']}
                    authority_ids = self.mapping_collection.distinct("authority_id", mapping_query)
                    query['authority_id'] = {'$in': authority_ids}
                
                # Filter by status
                if 'status' in filters and filters['status']:
                    query['status'] = filters['status']
                
                # Filter by keyword (search in authority_content)
                if 'keyword' in filters and filters['keyword']:
                    query['authority_content'] = {
                        '$regex': filters['keyword'], 
                        '$options': 'i'
                    }
                
                # Filter by doc_id (via mappings)
                if 'doc_id' in filters and filters['doc_id']:
                    mapping_query = {"doc_id": filters['doc_id']}
                    authority_ids = self.mapping_collection.distinct("authority_id", mapping_query)
                    # Combine with existing authority_id filter if present
                    if 'authority_id' in query:
                        # Intersection of both sets
                        existing_ids = set(query['authority_id']['$in'])
                        new_ids = set(authority_ids)
                        query['authority_id'] = {'$in': list(existing_ids & new_ids)}
                    else:
                        query['authority_id'] = {'$in': authority_ids}
            
            # Calculate pagination
            total = self.collection.count_documents(query)
            skip = (page - 1) * limit
            
            # Execute query
            cursor = self.collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
            
            authorities = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                authorities.append(doc)
            
            logger.debug("list_authorities_success", action="list_authorities", count=len(authorities), page=page, limit=limit, total=total, **{"event.status": "success"})
            
            return {
                'status': 'success',
                'data': authorities,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total
                }
            }
        except Exception as e:
            logger.error("list_authorities_failed", action="list_authorities", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    # ==================== MAPPING METHODS ====================
    
    def create_mapping(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new mapping between document/article and authority"""
        try:
            # Check if mapping already exists
            existing = self.mapping_collection.find_one({
                "doc_id": data['doc_id'],
                "article_id": data.get('article_id'),
                "authority_id": data['authority_id'],
                "agency_id": data.get('agency_id')
            })
            
            if existing:
                raise ValueError("Mapping already exists")
            
            # Set timestamps
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data['created_at'] = current_time
            data['last_modified_at'] = current_time
            
            result = self.mapping_collection.insert_one(data)
            mapping = self.get_mapping_by_id(str(result.inserted_id))
            
            logger.info("create_mapping_success", action="create_mapping", doc_id=data['doc_id'], authority_id=data['authority_id'], **{"event.status": "success"})
            return mapping
        except Exception as e:
            logger.error("create_mapping_failed", action="create_mapping", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def _find_mapping_doc(self, mapping_id: str) -> Optional[Dict[str, Any]]:
        """Resolve a mapping by its authority_id (business key, preferred) first,
        falling back to Mongo's internal _id for callers that already have it
        (e.g. from list/check-mapping responses)."""
        mapping = self.mapping_collection.find_one({"authority_id": mapping_id})
        if not mapping and ObjectId.is_valid(mapping_id):
            mapping = self.mapping_collection.find_one({"_id": ObjectId(mapping_id)})
        return mapping

    def get_mapping_by_id(self, mapping_id: str) -> Optional[Dict[str, Any]]:
        """Get a mapping by its authority_id (preferred) or Mongo _id"""
        try:
            mapping = self._find_mapping_doc(mapping_id)
            if mapping:
                mapping['_id'] = str(mapping['_id'])
                
                # Enrich with document title if available
                if 'doc_id' in mapping:
                    doc = self.document_collection.find_one({"doc_id": mapping['doc_id']})
                    if doc:
                        mapping['doc_title'] = doc.get('doc_title', '')
                if 'article_id' in mapping:
                    article = self.article_collection.find_one({"article_id": mapping['article_id']})
                    if article:
                        mapping['article_title'] = article.get('article_title', '')
                if 'agency_id' in mapping:
                    agency = self.agencies_collection.find_one({"agency_id": mapping['agency_id']})
                    if agency:
                        mapping['agency_name'] = agency.get('agency_name', '')                
                # Enrich with authority content if available
                if 'authority_id' in mapping:
                    authority = self.get_authority_by_id(mapping['authority_id'])
                    if authority:
                        mapping['authority_content'] = authority.get('authority_content', '')
                        mapping['authority_quotation'] = authority.get('authority_quotation', '')
                
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
                
                # Filter by article_id
                if 'article_id' in filters and filters['article_id']:
                    query['article_id'] = filters['article_id']
                
                # Filter by authority_id
                if 'authority_id' in filters and filters['authority_id']:
                    query['authority_id'] = filters['authority_id']
                
                # Filter by agency_id
                if 'agency_id' in filters and filters['agency_id']:
                    query['agency_id'] = filters['agency_id']
            
            # Calculate pagination
            total = self.mapping_collection.count_documents(query)
            skip = (page - 1) * limit
            
            # Execute query
            cursor = self.mapping_collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
            
            mappings = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                
                # Enrich with document title, article_content, agency_name, authority content
                if 'doc_id' in doc:
                    document = self.document_collection.find_one({"doc_id": doc['doc_id']})
                    if document:
                        doc['doc_title'] = document.get('doc_title', '')
                if 'article_id' in doc:
                    article = self.article_collection.find_one({"article_id": doc['article_id']})
                    if article:
                        doc['article_title'] = article.get('article_title', '')
                        doc['article_content'] = article.get('article_content', '')
                if 'agency_id' in doc:
                    agency = self.agencies_collection.find_one({"agency_id": doc['agency_id']})
                    if agency:
                        doc['agency_name'] = agency.get('agency_name', '')
                if 'authority_id' in doc:
                    authority = self.get_authority_by_id(doc['authority_id'])
                    if authority:
                        doc['authority_content'] = authority.get('authority_content', '')
                        doc['authority_quotation'] = authority.get('authority_quotation', '')
                
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
    
    def get_mapping_by_doc_and_authority(self, doc_id: str, authority_id: str) -> Optional[Dict[str, Any]]:
        """Get a mapping by document ID and authority ID"""
        try:
            mapping = self.mapping_collection.find_one({
                "doc_id": doc_id,
                "authority_id": authority_id
            })
            if mapping:
                mapping['_id'] = str(mapping['_id'])
            return mapping
        except Exception as e:
            logger.error("get_mapping_by_doc_and_authority_failed", action="get_mapping_by_doc_and_authority", doc_id=doc_id, authority_id=authority_id, **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            return None
    
    # ==================== LEGACY METHODS (for backward compatibility) ====================
    
    def list_agencies(self, search: str = '', page: int = 1, limit: int = 20) -> Dict[str, Any]:
        """List all agencies with optional search"""
        query = {"status": "ACTIVE"}
        
        if search:
            query["$or"] = [
                {"agency_name": {"$regex": search, "$options": "i"}},
                {"agency_id": {"$regex": search, "$options": "i"}}
            ]
        
        total = self.agencies_collection.count_documents(query)
        skip = (page - 1) * limit
        
        cursor = self.agencies_collection.find(query).skip(skip).limit(limit)
        
        agencies = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            agencies.append({
                'id': doc['agency_id'],
                'name': doc['agency_name'],
                'status': doc['status']
            })
        
        return {
            'total': total,
            'page': page,
            'limit': limit,
            'items': agencies
        }
# Draft model removed - no longer needed