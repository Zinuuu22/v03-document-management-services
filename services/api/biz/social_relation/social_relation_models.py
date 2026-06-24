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


class DuplicateSocialRelationGroupItemError(Exception):
    """Raised when a social relation is already assigned to the requested
    social relation group (distinct from ValueError so the API layer can map
    it to its own response code instead of the generic 400-VAL one)."""
    pass


class SocialRelationModel:
    """Model for managing social relations in law documents"""
    
    def __init__(self):
        self.client = get_mongo_client()
        self.db = self.client[MigrateConfig.MIGRATE_CORE_DB]
        self.collection = self.db[MongoDBCollectionConfig.LAW_SOCIAL_RELATION_COLLECTION_NAME]
        self.mapping_collection = self.db[MongoDBCollectionConfig.LAW_SOCIAL_RELATION_MAPPING_COLLECTION_NAME]
        self.group_collection = self.db[MongoDBCollectionConfig.LAW_SOCIAL_RELATION_GROUP_COLLECTION_NAME]
        self.document_collection = self.db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
        self.article_collection = self.db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]

        # Create indexes
        self._create_indexes()

    def _create_indexes(self):
        """Create necessary indexes for collections"""
        try:
            # Indexes for social_relation collection
            self.collection.create_index("social_relation_id", unique=True)
            self.collection.create_index("social_relation_name")
            self.collection.create_index("status")
            self.collection.create_index("created_at")
            self.collection.create_index("social_relation_group_id")

            # Indexes for mapping collection
            self.mapping_collection.create_index("doc_id")
            self.mapping_collection.create_index("article_id")
            self.mapping_collection.create_index("social_relation_id")
            self.mapping_collection.create_index([("doc_id", 1), ("article_id", 1), ("social_relation_id", 1)])

            # Indexes for social_relation_group collection
            self.group_collection.create_index("social_relation_group_id", unique=True)
            self.group_collection.create_index("social_relation_group_name_norm")
            self.group_collection.create_index("status")
            self.group_collection.create_index("created_at")
            self.group_collection.create_index("doc_id")

            logger.info("create_indexes_success", action="_create_indexes", **{"event.status": "success"})
        except Exception as e:
            logger.error("create_indexes_failed", action="_create_indexes", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
    
    def check_document_exists(self, doc_id: str) -> bool:
        """Check if a document exists by its ID"""
        return self.document_collection.find_one({"doc_id": doc_id}) is not None
    
    def check_article_exists(self, article_id: str) -> bool:
        """Check if an article exists by its ID"""
        return self.article_collection.find_one({"article_id": article_id}) is not None
    
    def check_social_relation_exists(self, social_relation_id: str) -> bool:
        """Check if a social relation exists by its ID"""
        return self.collection.find_one({"social_relation_id": social_relation_id}) is not None
    
    # ==================== SOCIAL RELATION METHODS ====================
    
    def create_social_relation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new social relation"""
        try:
            # Check if social_relation_id already exists
            if self.collection.find_one({"social_relation_id": data.get("social_relation_id")}):
                raise ValueError(f"Social relation with ID {data.get('social_relation_id')} already exists")
            
            # Set timestamps
            data['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data['last_modified_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Set default status if not provided
            if 'status' not in data:
                data['status'] = 'ACTIVE'
            
            result = self.collection.insert_one(data)
            created_relation = self.get_social_relation_by_id(data['social_relation_id'])
            
            logger.info("create_social_relation_success", action="create_social_relation", social_relation_id=data['social_relation_id'], **{"event.status": "success"})
            return created_relation
        except Exception as e:
            logger.error("create_social_relation_failed", action="create_social_relation", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def get_social_relation_by_id(self, social_relation_id: str) -> Optional[Dict[str, Any]]:
        """Get a social relation by its ID"""
        relation = self.collection.find_one({"social_relation_id": social_relation_id})
        if relation:
            relation['_id'] = str(relation['_id'])
        return relation
    
    def update_social_relation(self, social_relation_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing social relation"""
        try:
            # Check if relation exists
            existing = self.get_social_relation_by_id(social_relation_id)
            if not existing:
                raise ValueError(f"Social relation with ID {social_relation_id} not found")
            
            # Update timestamp
            update_data['last_modified_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Remove fields that shouldn't be updated
            update_data.pop('social_relation_id', None)
            update_data.pop('created_at', None)
            update_data.pop('created_date', None)
            update_data.pop('created_by', None)
            update_data.pop('_id', None)
            
            result = self.collection.update_one(
                {"social_relation_id": social_relation_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info("update_social_relation_success", action="update_social_relation", social_relation_id=social_relation_id, **{"event.status": "success"})
            
            return self.get_social_relation_by_id(social_relation_id)
        except Exception as e:
            logger.error("update_social_relation_failed", action="update_social_relation", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def delete_social_relation(self, social_relation_id: str, delete_mappings: bool = True) -> Dict[str, Any]:
        """Delete a social relation and optionally its mappings"""
        try:
            # Check if relation exists
            existing = self.get_social_relation_by_id(social_relation_id)
            if not existing:
                raise ValueError(f"Social relation with ID {social_relation_id} not found")
            
            # Delete related mappings if requested
            deleted_mappings = 0
            if delete_mappings:
                mapping_result = self.mapping_collection.delete_many({"social_relation_id": social_relation_id})
                deleted_mappings = mapping_result.deleted_count
            
            # Delete the social relation
            result = self.collection.delete_one({"social_relation_id": social_relation_id})
            
            logger.info("delete_social_relation_success", action="delete_social_relation", social_relation_id=social_relation_id, deleted_mappings=deleted_mappings, **{"event.status": "success"})
            
            return {
                "social_relation_id": social_relation_id,
                "deleted": True,
                "deleted_mappings": deleted_mappings
            }
        except Exception as e:
            logger.error("delete_social_relation_failed", action="delete_social_relation", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def list_social_relations(self, filters: Dict[str, Any] = None, 
                             page: int = 1, 
                             limit: int = 10) -> Dict[str, Any]:
        """List social relations with filtering and pagination"""
        try:
            query = {}
            
            if filters:
                # Filter by name (partial match)
                if 'social_relation_name' in filters and filters['social_relation_name']:
                    query['social_relation_name'] = {
                        '$regex': filters['social_relation_name'], 
                        '$options': 'i'
                    }
                
                # Filter by status
                if 'status' in filters and filters['status']:
                    status_val = filters['status']
                    if isinstance(status_val, str) and status_val.strip().lower() == 'active':
                        query['status'] = {'$in': ['ACTIVE', 'Active']}
                    else:
                        query['status'] = status_val
                
                # Filter by social_relation_id
                if 'social_relation_id' in filters and filters['social_relation_id']:
                    query['social_relation_id'] = filters['social_relation_id']
                
                # Filter by date range
                if 'created_date_from' in filters or 'created_date_to' in filters:
                    date_query = {}
                    if 'created_date_from' in filters:
                        date_query['$gte'] = filters['created_date_from']
                    if 'created_date_to' in filters:
                        date_query['$lte'] = filters['created_date_to']
                    if date_query:
                        query['created_at'] = date_query
            
            # Calculate pagination
            total = self.collection.count_documents(query)
            skip = (page - 1) * limit
            
            # Execute query
            cursor = self.collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
            
            relations = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                relations.append(doc)
            
            logger.debug("list_social_relations_success", action="list_social_relations", count=len(relations), page=page, limit=limit, total=total, **{"event.status": "success"})
            
            return {
                'status': 'success',
                'data': relations,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total
                }
            }
        except Exception as e:
            logger.error("list_social_relations_failed", action="list_social_relations", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
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
            data['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data['last_modified_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Set default relation_type if not provided
            if 'relation_type' not in data:
                data['relation_type'] = 'PRIMARY'
            
            result = self.mapping_collection.insert_one(data)
            created_mapping = self.mapping_collection.find_one({"_id": result.inserted_id})
            created_mapping['_id'] = str(created_mapping['_id'])
            if 'doc_id' in created_mapping:
                document = self.document_collection.find_one({"doc_id": created_mapping['doc_id']})
                if document:
                    created_mapping['doc_title'] = document.get('doc_title', '')

            logger.info("create_social_relation_mapping_success", action="create_social_relation_mapping", inserted_id=str(result.inserted_id), **{"event.status": "success"})
            return created_mapping
        except Exception as e:
            logger.error("create_social_relation_mapping_failed", action="create_social_relation_mapping", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def _find_mapping_doc(self, mapping_id: str) -> Optional[Dict[str, Any]]:
        """Resolve a mapping by its social_relation_id (business key, preferred)
        first, falling back to Mongo's internal _id for callers that already
        have it (e.g. from list/check-mapping responses)."""
        mapping = self.mapping_collection.find_one({"social_relation_id": mapping_id})
        if not mapping and ObjectId.is_valid(mapping_id):
            mapping = self.mapping_collection.find_one({"_id": ObjectId(mapping_id)})
        return mapping

    def get_social_relation_mapping_by_id(self, mapping_id: str) -> Optional[Dict[str, Any]]:
        """Get a social relation mapping by its social_relation_id (preferred) or Mongo _id"""
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
            logger.error("get_social_relation_mapping_by_id_failed", action="get_social_relation_mapping_by_id", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            return None

    def update_social_relation_mapping(self, mapping_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing social relation mapping"""
        try:
            # Check if mapping exists
            existing = self._find_mapping_doc(mapping_id)
            if not existing:
                raise ValueError(f"Social relation mapping with ID {mapping_id} not found")

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
                logger.info("update_social_relation_mapping_success", action="update_social_relation_mapping", mapping_id=mapping_id, **{"event.status": "success"})

            return self.get_social_relation_mapping_by_id(mapping_id)
        except Exception as e:
            logger.error("update_social_relation_mapping_failed", action="update_social_relation_mapping", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise

    def delete_social_relation_mapping(self, mapping_id: str) -> Dict[str, Any]:
        """Delete a social relation mapping"""
        try:
            # Check if mapping exists
            existing = self._find_mapping_doc(mapping_id)
            if not existing:
                raise ValueError(f"Social relation mapping with ID {mapping_id} not found")

            # Delete the mapping
            result = self.mapping_collection.delete_one({"_id": existing["_id"]})
            
            logger.info("delete_social_relation_mapping_success", action="delete_social_relation_mapping", mapping_id=mapping_id, **{"event.status": "success"})
            
            return {
                "mapping_id": mapping_id,
                "deleted": True
            }
        except Exception as e:
            logger.error("delete_social_relation_mapping_failed", action="delete_social_relation_mapping", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
    
    def get_social_relation_detail(self, id_or_social_relation_id: str) -> List[Dict[str, Any]]:
        """Get social relation mapping details by ObjectId or social_relation_id"""
        try:
            # Determine if input is ObjectId or social_relation_id
            if ObjectId.is_valid(id_or_social_relation_id):
                query = {"_id": ObjectId(id_or_social_relation_id)}
            else:
                query = {"social_relation_id": id_or_social_relation_id}
            
            # Find all mappings matching the query
            cursor = self.mapping_collection.find(query)
            
            results = []
            for doc in cursor:
                article_class_val = doc.get('article_class', [])
                result = {
                    "_id": str(doc['_id']),
                    "doc_id": doc.get('doc_id', ''),
                    "article_id": doc.get('article_id', ''),
                    "created_by": doc.get('created_by', ''),
                    "created_at": doc.get('created_at', ''),
                    "last_modified_at": doc.get('last_modified_at', ''),
                    "last_modified_by": doc.get('last_modified_by', ''),
                    "relation_type": doc.get('relation_type', ''),
                    "social_relation_id": doc.get('social_relation_id', ''),
                    "article_class": article_class_val if isinstance(article_class_val, list) else [],
                }

                # Fetch article_title from law_articles collection
                if 'article_id' in doc and doc['article_id']:
                    article = self.article_collection.find_one(
                        {"article_id": doc['article_id']},
                        {"article_title": 1}
                    )
                    if article:
                        result['article_title'] = article.get('article_title', '')
                    else:
                        result['article_title'] = ''
                else:
                    result['article_title'] = ''

                # Fetch social_relation_name + social_relation from law_social_relation collection
                if 'social_relation_id' in doc and doc['social_relation_id']:
                    social_relation = self.collection.find_one(
                        {"social_relation_id": doc['social_relation_id']},
                        {"social_relation_name": 1, "social_relation": 1}
                    )
                    if social_relation:
                        result['social_relation_name'] = social_relation.get('social_relation_name', '')
                        result['social_relation'] = social_relation.get('social_relation', '')
                    else:
                        result['social_relation_name'] = ''
                        result['social_relation'] = ''
                else:
                    result['social_relation_name'] = ''
                    result['social_relation'] = ''

                if doc.get('doc_id'):
                    document = self.document_collection.find_one({"doc_id": doc['doc_id']})
                    result['doc_title'] = document.get('doc_title', '') if document else ''
                else:
                    result['doc_title'] = ''

                results.append(result)
            
            logger.debug("get_social_relation_detail_success", action="get_social_relation_detail", count=len(results), id_or_social_relation_id=id_or_social_relation_id, **{"event.status": "success"})
            return results
            
        except Exception as e:
            logger.error("get_social_relation_detail_failed", action="get_social_relation_detail", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
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
            cursor = self.mapping_collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
            
            mappings = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])
                
                if 'social_relation_id' in doc:
                    social_relation = self.collection.find_one(
                        {"social_relation_id": doc['social_relation_id']},
                        {"social_relation_name": 1}
                    )
                    if social_relation:
                        doc['social_relation_name'] = social_relation.get('social_relation_name', '')
                    else:
                        doc['social_relation_name'] = ''
                
                # Fetch article_title + article_content from law_articles collection
                if 'article_id' in doc:
                    article = self.article_collection.find_one(
                        {"article_id": doc['article_id']},
                        {"article_title": 1, "article_content": 1}
                    )
                    if article:
                        doc['article_title'] = article.get('article_title', '')
                        doc['article_content'] = article.get('article_content', '')
                    else:
                        doc['article_title'] = ''
                        doc['article_content'] = ''
                else:
                    doc['article_title'] = ''
                    doc['article_content'] = ''

                if 'doc_id' in doc:
                    document = self.document_collection.find_one({"doc_id": doc['doc_id']})
                    if document:
                        doc['doc_title'] = document.get('doc_title', '')

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

    # ==================== SOCIAL RELATION GROUP METHODS ====================

    def get_social_relation_group_by_id(self, social_relation_group_id: str) -> Optional[Dict[str, Any]]:
        """Get a social relation group by its ID"""
        group = self.group_collection.find_one({"social_relation_group_id": social_relation_group_id})
        if group:
            group['_id'] = str(group['_id'])
        return group

    def add_social_relation_to_group(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Assign an existing social relation (danh mục) into an existing
        social relation group, in the context of a document.

        Sets relation.social_relation_group_id = group_id and
        group.doc_id = doc_id (same last-writer-wins policy as the v2
        extractor write path), so GET /social-relation-groups?doc_id=<doc_id>
        immediately returns this relation under the group's social_relations
        without any change needed on the read side."""
        try:
            doc_id = data.get('doc_id')
            social_relation_group_id = data.get('social_relation_group_id')
            social_relation_id = data.get('social_relation_id')

            if not self.check_document_exists(doc_id):
                raise ValueError(f"Document with ID {doc_id} not found")

            group = self.get_social_relation_group_by_id(social_relation_group_id)
            if not group:
                raise ValueError(f"Social relation group with ID {social_relation_group_id} not found")

            relation = self.get_social_relation_by_id(social_relation_id)
            if not relation:
                raise ValueError(f"Social relation with ID {social_relation_id} not found")

            if relation.get('social_relation_group_id') == social_relation_group_id:
                raise DuplicateSocialRelationGroupItemError(
                    f"Social relation {social_relation_id} is already in group {social_relation_group_id}"
                )

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            last_modified_by = data.get('created_by', '')

            self.collection.update_one(
                {"social_relation_id": social_relation_id},
                {"$set": {
                    "social_relation_group_id": social_relation_group_id,
                    "last_modified_at": now_str,
                    "last_modified_by": last_modified_by
                }}
            )

            self.group_collection.update_one(
                {"social_relation_group_id": social_relation_group_id},
                {"$set": {
                    "doc_id": doc_id,
                    "last_modified_at": now_str,
                    "last_modified_by": last_modified_by
                }}
            )

            updated_relation = self.get_social_relation_by_id(social_relation_id)

            logger.info("add_social_relation_to_group_success", action="add_social_relation_to_group",
                        social_relation_id=social_relation_id,
                        social_relation_group_id=social_relation_group_id,
                        doc_id=doc_id, **{"event.status": "success"})

            return updated_relation
        except Exception as e:
            logger.error("add_social_relation_to_group_failed", action="add_social_relation_to_group", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise

    def list_social_relation_groups(self, filters: Dict[str, Any] = None,
                                   page: int = 1,
                                   limit: int = 10) -> Dict[str, Any]:
        """List social relation groups with filtering and pagination, each
        enriched with the social relations that belong to it (no mappings)."""
        try:
            query = {}

            if filters:
                # Keyword search on name + normalized name
                if 'keyword' in filters and filters['keyword']:
                    keyword = filters['keyword']
                    query['$or'] = [
                        {'social_relation_group_name': {'$regex': keyword, '$options': 'i'}},
                        {'social_relation_group_name_norm': {'$regex': keyword, '$options': 'i'}},
                    ]

                # Filter by status
                if 'status' in filters and filters['status']:
                    status_val = filters['status']
                    if isinstance(status_val, str) and status_val.strip().lower() == 'active':
                        query['status'] = {'$in': ['ACTIVE', 'Active']}
                    else:
                        query['status'] = status_val

                # Filter by doc_id
                if 'doc_id' in filters and filters['doc_id']:
                    query['doc_id'] = filters['doc_id']

            # Calculate pagination
            total = self.group_collection.count_documents(query)
            skip = (page - 1) * limit

            # Execute query
            cursor = self.group_collection.find(query).skip(skip).limit(limit).sort("created_at", -1)

            groups = []
            for doc in cursor:
                doc['_id'] = str(doc['_id'])

                relations_cursor = self.collection.find(
                    {"social_relation_group_id": doc.get("social_relation_group_id")}
                )
                relations = []
                for rel in relations_cursor:
                    rel['_id'] = str(rel['_id'])
                    relations.append(rel)
                doc['social_relations'] = relations

                groups.append(doc)

            logger.debug("list_social_relation_groups_success", action="list_social_relation_groups", count=len(groups), page=page, limit=limit, total=total, **{"event.status": "success"})

            return {
                'status': 'success',
                'data': groups,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total
                }
            }
        except Exception as e:
            logger.error("list_social_relation_groups_failed", action="list_social_relation_groups", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise

    def delete_social_relation_group(self, social_relation_group_id: str) -> Dict[str, Any]:
        """Delete a social relation group and cascade-delete its social relations
        and their mappings. Hard delete, matching delete_social_relation's style.

        Order: mappings (by collected relation_ids) -> relations -> group, so a
        crash mid-way never leaves an orphan relation/mapping pointing at an
        already-deleted group."""
        try:
            existing = self.get_social_relation_group_by_id(social_relation_group_id)
            if not existing:
                raise ValueError(f"Social relation group with ID {social_relation_group_id} not found")

            relation_ids = self.collection.distinct(
                "social_relation_id", {"social_relation_group_id": social_relation_group_id}
            )

            deleted_mappings_count = 0
            if relation_ids:
                mapping_result = self.mapping_collection.delete_many(
                    {"social_relation_id": {"$in": relation_ids}}
                )
                deleted_mappings_count = mapping_result.deleted_count

            relations_result = self.collection.delete_many(
                {"social_relation_group_id": social_relation_group_id}
            )
            deleted_relations_count = relations_result.deleted_count

            group_result = self.group_collection.delete_one(
                {"social_relation_group_id": social_relation_group_id}
            )
            deleted_groups_count = group_result.deleted_count

            logger.info("delete_social_relation_group_success", action="delete_social_relation_group",
                        social_relation_group_id=social_relation_group_id,
                        deleted_groups_count=deleted_groups_count,
                        deleted_relations_count=deleted_relations_count,
                        deleted_mappings_count=deleted_mappings_count,
                        **{"event.status": "success"})

            return {
                "social_relation_group_id": social_relation_group_id,
                "deleted_groups_count": deleted_groups_count,
                "deleted_relations_count": deleted_relations_count,
                "deleted_mappings_count": deleted_mappings_count,
            }
        except Exception as e:
            logger.error("delete_social_relation_group_failed", action="delete_social_relation_group", **{"error.code": "DB", "error.message": str(e), "event.status": "failure"}, exc_info=True)
            raise
