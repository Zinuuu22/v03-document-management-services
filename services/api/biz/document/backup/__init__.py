from core.common.elastic.client import get_elastic_client
from core.common.mongo.client import get_mongo_client
import structlog
import structlog.contextvars
from structlog.contextvars import bind_contextvars
import requests
import os
import sys
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Dict, Any
from flask_restful import Resource, reqparse
from flask import request, Response, send_file
from pymongo import MongoClient
from docx import Document
from elasticsearch import Elasticsearch

from services.api.biz.upload import law_document_storage_collection

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from services.api import api
from services.api.utils import make_response
from constants import MongoDBConfig, MigrateConfig, MinioConfig, ElasticConfig, AppConfig, APIEndpoints, MongoDBCollectionConfig
from services.api.biz.document.utils import get_document_relationship, enrich_stream, get_doc_type_map
from services.api.utils.minio import download_from_minio, upload_to_minio, delete_minio_object
from services.api.utils.reader import convert_doc_to_docx
from services.api.utils.search import build_query, search, stream, build_query_semantic_search, parse_date
from core.v03.tree_processor.processor import LawTreeManager
from core.common.elastic import ElasticIndexer
from core.v03.effective_update.update import update_effective_status_now
from core.v03.effective_update.article_update import update_effective_status_now as update_effective_status_now_article
logger = structlog.get_logger()

            
            
# Khởi tạo kết nối MongoDB
client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_industry_sector_collection = db[MongoDBCollectionConfig.LAW_INDUSTRY_SECTORS_COLLECTION_NAME]
law_agencies_collection = db[MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME]
law_keywords_collection = db[MongoDBCollectionConfig.LAW_KEYWORD_COLLECTION_NAME]
law_references_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_COLLECTION_NAME]
law_doc_type_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_TYPE_COLLECTION_NAME]
law_issuing_level_collection = db[MongoDBCollectionConfig.LAW_ISSUING_LEVEL_COLLECTION_NAME]
law_decree_status_collection = db[MongoDBCollectionConfig.LAW_DECREE_STATUS_COLLECTION_NAME]
law_signer_collection = db[MongoDBCollectionConfig.LAW_SIGNERS_COLLECTION_NAME]
law_position_collection = db[MongoDBCollectionConfig.LAW_POSITIONS_COLLECTION_NAME]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]

raw_resource_collection = client[MongoDBCollectionConfig.LAW_DOCUMENT_STORAGE_COLLECTION_NAME]


# Init Elasticsearch client
es_client = get_elastic_client()
es_indexer = ElasticIndexer()

# Init LawTreeManager
law_tree_manager = LawTreeManager()

class GetDocumentDetailAPI(Resource):
    def get(self, idOrCode: str) -> Dict[str, Any]:
        bind_contextvars(task="GetDocumentDetailAPI")
        start_time = datetime.now()
        try:
            query    = {"doc_id": idOrCode}
            document = law_documents_collection.find_one(query)

            if not document:
                duration = (datetime.now() - start_time).total_seconds()
                logger.warning("get_document_detail_not_found", action="get", **{"event.duration": duration, "event.status": "failed"}, id_or_code=idOrCode)
                return make_response(data=None, code=2000, message="Document not found"), 404

            # --- Flatten keyword_ids nếu là list of list ---
            raw_keyword_ids = document.get("keyword_ids", [])
            flat_keyword_ids = [
                i for item in raw_keyword_ids
                for i in (item if isinstance(item, list) else [item])
            ]

            # --- Industries ---
            industries = [
                {"code": i["industry_sector_id"], "name": i["industry_sector_name"]}
                for i in law_industry_sector_collection.find(
                    {"industry_sector_id": {"$in": document.get("industry_sector_ids", [])}}
                )
            ]

            # --- Agencies ---
            agencies = [
                {"code": a["agency_id"], "name": a["agency_name"]}
                for a in law_agencies_collection.find(
                    {"agency_id": {"$in": document.get("agency_ids", [])}}
                )
            ]

            # --- Keywords (dùng flat_keyword_ids) ---
            keywords = [
                {"code": k["keyword_id"], "name": k["keyword_name"]}
                for k in law_keywords_collection.find(
                    {"keyword_id": {"$in": flat_keyword_ids}}
                )
            ]

            # --- Doc type ---
            doc_type      = law_doc_type_collection.find_one({"type_id": document.get("type_id", "")})
            doc_type_name = doc_type["doc_type_name"] if doc_type else ""

            # --- Issuing level ---
            issue_level      = law_issuing_level_collection.find_one({"issuing_level_id": document.get("issuing_level_id", "")})
            issue_level_name = issue_level["issuing_level_name"] if issue_level else ""

            # --- Signers ---
            signers = [
                {"code": s["signer_id"], "name": s["signer_name"]}
                for s in law_signer_collection.find(
                    {"signer_id": {"$in": document.get("signer_ids", [])}}
                )
            ]

            # --- Positions ---
            positions = [
                {"code": p["position_id"], "name": p["position_name"]}
                for p in law_position_collection.find(
                    {"position_id": {"$in": document.get("position_ids", [])}}
                )
            ]

            # --- Reference storages (safe: skip nếu không tìm thấy) ---
            referenceStorages = []
            for storage_id in document.get("reference_storage_ids", []):
                document_storage = law_document_storage_collection.find_one({"storage_id": storage_id})
                referenceStorages.append({
                    "code": storage_id,
                    "name": document_storage["name"] if document_storage else ""
                })

            # --- Trees ---
            trees = [
                {"code": s["subject_id"], "name": s["subject_name"]}
                for s in law_tree_manager.subject_tree_collection.find(
                    {"subject_id": {"$in": document.get("tree_ids", [])}}
                )
            ]

            # --- Relationships ---
            try:
                relationships = get_document_relationship(idOrCode)
            except Exception as e:
                logger.warning("get_relationships_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e)}, exc_info=True)

                relationships = {}

            # --- Build response ---
            def _isoformat(value):
                if isinstance(value, datetime):
                    return value.isoformat()
                return value or None

            final_document = {
                "code":                         document.get("doc_id", ""),
                "name":                         document.get("doc_title", ""),
                "documentCode":                 document.get("doc_code", ""),
                "createdBy":                    document.get("created_by", ""),
                "createdDate":                  _isoformat(document.get("created_at")),
                "lastModifiedBy":               document.get("last_modified_by", ""),
                "lastModified":                 document.get("last_modified_at", None),
                "referenceStorages":            referenceStorages,
                "shortDescription":             document.get("doc_short_description", ""),
                "keywords":                     keywords,
                "keywordCodes":                 flat_keyword_ids,
                "industries":                   industries,
                "industrySectorCodes":          document.get("industry_sector_ids", []),
                "documentType":                 doc_type_name,
                "documentTypeCode":             document.get("type_id", ""),
                "storageCode":                  document.get("storage_id", ""),
                "agencySymbol":                 agencies,
                "agencyIssuedCodes":             document.get("agency_ids", []),
                "issuedLevel":                  issue_level_name,
                "issuedLevelCode":              document.get("issuing_level_id", ""),
                "signerCodes":                  document.get("signer_ids", []),
                "trees":                        trees,
                "treeCodes":                    document.get("tree_ids", []),
                "signers":                      signers,
                "positionCodes":                document.get("position_ids", []),
                "positions":                    positions,
                "decreeIssued":                 _isoformat(document.get("doc_issue_date")),
                "decreeEffect":                 _isoformat(document.get("doc_effective_date")),
                "dateExpired":                  _isoformat(document.get("doc_expiry_date")),
                "decreeStatus":                 document.get("doc_effective_status", ""),
                "decreeStatusCode":             document.get("effective_status_id", ""),
                "referenceStorageCodes":        document.get("reference_storage_ids", []),
                "dataSource":                   document.get("data_source", ""),
                "guidedDocuments":              relationships.get("guided_documents", []),
                "consolidatingDocuments":       relationships.get("consolidating_documents", []),
                "correctedDocuments":           relationships.get("corrected_documents", []),
                "replaceDocuments":             relationships.get("replace_documents", []),
                "referentialDocuments":         relationships.get("referential_documents", []),
                "basisDocuments":               relationships.get("basis_documents", []),
                "contentConnectionDocuments":   relationships.get("content_connection_documents", []),
                "avoidDocuments":               relationships.get("avoid_documents", []),
                "amendedDocuments":             relationships.get("amended_documents", []),
            }

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("get_document_detail_success", action="get", **{"event.duration": duration, "event.status": "success"}, doc_id=idOrCode)
            return make_response(data=final_document, code=0, message="Success"), 200

        except ValueError as ve:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_document_detail_failed", action="get", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": str(ve)}, exc_info=True)
            response = make_response(data=None, code=2000, message="Invalid ID")
            response["error_code"] = "400-VAL"
            response["status"] = False
            return response, 400
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_document_detail_failed", action="get", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DocumentTextSearchAPI(Resource):
    """API for searching documents in Elasticsearch with pagination and streaming."""
    
    def _validate_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and parse filter parameters from request body.

        Args:
            filters (Dict[str, Any]): Filter parameters from request body.

        Returns:
            Dict[str, Any]: Validated filter parameters.

        Raises:
            ValueError: If date format is invalid.
        """
        validated_filters = {}

        # Text search parameters
        if 'text' in filters:
            validated_filters['text'] = str(filters['text'])
        if 'searchFields' in filters and isinstance(filters['searchFields'], list):
            validated_filters['searchFields'] = [str(f) for f in filters['searchFields']]
        if 'searchMethod' in filters and filters['searchMethod'] in ['normal', 'exact']:
            validated_filters['searchMethod'] = filters['searchMethod']
        if 'filterType' in filters and filters['filterType'] == 'fuzzy':
            validated_filters['filterType'] = 'fuzzy'    

        # Status filter
        if 'status' in filters:
            validated_filters['status'] = str(filters['status'])
        
        # Code filters
        code_fields = [
            'documentCategoryCodes', 'keywordCodes', 'industrySectorCodes',
            'issuedLevelCodes', 'agencyIssuedCodes', 'decreeStatusCodes', 'codes', 'positionCodes', 'signerCodes', 'documentTypeCodes'
        ]
        for field in code_fields:
            if field in filters and isinstance(filters[field], list):
                validated_filters[field] = [str(v) for v in filters[field]]

        # Date range filters
        date_fields = [
            ('decreeIssuedFrom', 'decreeIssuedTo'), 
            ('dateExpiredFrom', 'dateExpiredTo'),
            ('decreeEffectFrom', 'decreeEffectTo')
        ]
        for start_field, end_field in date_fields:
            if start_field in filters and filters[start_field]:
                validated_filters[start_field] = parse_date(filters[start_field])
            if end_field in filters and filters[end_field]:
                validated_filters[end_field] = parse_date(filters[end_field])

        return validated_filters


    def post(self, page: int, quantity: int):
        """Handle POST request to search documents.

        Args:
            page (int): Page number (1-based).
            quantity (int): Number of records per page (1-100).

        Returns:
            Response: Streaming JSON response with search results.
        """
        bind_contextvars(task="DocumentTextSearchAPI")
        start_time = datetime.now()
        # Validate input parameters
        if not isinstance(page, int) or page < 1:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("search_documents_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Page number must be a positive integer"}, page=page)
            return {"code": "400", "message": "Page number must be a positive integer", "data": None, "error_code": "400-VAL", "status": False}, 400

        if not isinstance(quantity, int) or quantity < 1 or quantity > 100:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("search_documents_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Quantity must be between 1 and 100"}, quantity=quantity)
            return {"code": "400", "message": "Quantity must be between 1 and 100", "data": None, "error_code": "400-VAL", "status": False}, 400

        try:
            # Get filters from request body
            filters = request.get_json() or {}
            validated_filters = self._validate_filters(filters)
            logger.debug("validate_filters_success", action="post", validated_filters=validated_filters)

            # Build Elasticsearch query
            query = build_query(validated_filters)

            # Get total count
            count_result = es_client.count(index=ElasticConfig.ELASTIC_INDEX, body={"query": query})
            total_count = count_result['count']
            logger.debug("get_total_count_success", action="post", total_matching_documents=total_count)

            # Create search generator with pagination
            skip = (page - 1) * quantity
            logger.debug("search_elasticsearch_started", action="post", search_query=query, page=page, quantity=quantity, skip=skip)
            search_gen = search(es_client, index=ElasticConfig.ELASTIC_INDEX, 
                                query=query, 
                                batch_size=1000,
                                max_records=quantity,
                                skip= skip)
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info("search_documents_success", action="post", **{"event.duration": duration, "event.status": "success"})
            # Stream response
            return Response(
                enrich_stream(search_gen, total_count),
                mimetype='application/json'
            )

        except ValueError as ve:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("search_documents_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": str(ve)}, exc_info=True)
            return {"code": "400", "message": f"Invalid input: {str(ve)}", "data": None, "error_code": "400-VAL", "status": False}, 400
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("search_documents_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            return {"code": "500", "message": f"Internal server error: {str(e)}", "data": None, "error_code": "500-SYS", "status": False}, 500


class DocumentDeleteAPI(Resource):

    def _delete_from_mongo(self, idOrCode: str):
        try:
            document = law_documents_collection.find_one({"doc_id": idOrCode})
            if not document:
                return False, None, None

            law_documents_collection.delete_one({"doc_id": idOrCode})

            storage_id  = document.get("storage_id")
            object_name = None
            bucket_name = None

            if storage_id:
                record = law_document_storage_collection.find_one({"storage_id": storage_id})
                if record:
                    file_name = record.get("name")
                    if file_name:
                        object_name = f"uploads/{file_name}"
                    bucket_name = record.get("bucket")
                    law_document_storage_collection.delete_one({"storage_id": storage_id})

            # Xóa law_articles liên quan
            articles_result = law_articles_collection.delete_many({"doc_id": idOrCode})
            logger.debug("deleted_articles_from_mongo", action="_delete_from_mongo", doc_id=idOrCode, deleted_count=articles_result.deleted_count)

            return True, object_name, bucket_name

        except Exception as e:
            logger.error("delete_from_mongo_failed", action="_delete_from_mongo", **{"error.code": "500-DB", "error.message": str(e)}, exc_info=True)
            raise

    def _delete_from_elasticsearch(self, idOrCode: str) -> bool:
        try:
            result = es_client.delete(
                index=ElasticConfig.ELASTIC_INDEX,
                id=str(idOrCode),
                ignore=[404]
            )
            deleted = result.get("result") in ["deleted", "not_found"]
            logger.debug("deleted_from_elasticsearch", action="_delete_from_elasticsearch", id=idOrCode, es_delete_result=result.get("result"))
            return deleted
        except Exception as e:
            logger.error("delete_from_elasticsearch_failed", action="_delete_from_elasticsearch", **{"error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            raise

    def delete(self, idOrCode: str):
        bind_contextvars(task="DocumentDeleteAPI")
        start_time = datetime.now()
        try:
            logger.debug("delete_document_started", action="delete", id=idOrCode)

            # Step 1: Kiểm tra document tồn tại trước
            document = law_documents_collection.find_one({"doc_id": idOrCode})
            if not document:
                duration = (datetime.now() - start_time).total_seconds()
                logger.warning("delete_document_not_found", action="delete", **{"event.duration": duration, "event.status": "failed"}, id_or_code=idOrCode)
                return make_response(
                    data=None, code=2000,
                    message=f"Document with ID {idOrCode} not found"
                ), 404

            # Step 2: Xóa từ Elasticsearch
            es_deleted = False
            try:
                es_deleted = self._delete_from_elasticsearch(idOrCode)
                logger.debug("delete_from_elasticsearch_success", action="delete", es_deleted=es_deleted)
            except Exception as e:
                logger.error("delete_from_elasticsearch_failed_ignoring", action="delete", **{"error.code": "500-SYS", "error.message": str(e)}, exc_info=True)

            # Step 3: Xóa từ MongoDB
            mongo_deleted, object_name, bucket_name = self._delete_from_mongo(idOrCode)
            logger.debug("delete_from_mongo_success", action="delete", mongo_deleted=mongo_deleted, object_name=object_name, bucket_name=bucket_name)

            # Step 4: Xóa từ MinIO
            minio_deleted = False
            try:
                if object_name and bucket_name:
                    delete_minio_object(object_name, bucket_name)
                    minio_deleted = True
                    logger.debug("delete_from_minio_success", action="delete", object_name=object_name)
            except Exception as e:
                logger.error("delete_from_minio_failed_ignoring", action="delete", **{"error.code": "500-SYS", "error.message": str(e)}, exc_info=True)

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("delete_document_success", action="delete", **{"event.duration": duration, "event.status": "success"}, doc_id=idOrCode, es_deleted=es_deleted, mongo_deleted=mongo_deleted, minio_deleted=minio_deleted)

            return make_response(
                data={
                    "law_documents_deleted": mongo_deleted,
                    "elasticsearch_deleted": es_deleted,
                    "minio_deleted":         minio_deleted
                },
                code=0,
                message="Document deleted successfully"
            ), 200

        except ValueError as ve:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("delete_document_failed", action="delete", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": str(ve)}, exc_info=True)
            return {"code": "400", "message": f"Invalid input: {str(ve)}", "data": None,
                    "error_code": "400-VAL", "status": False}, 400
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("delete_document_failed", action="delete", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            return {"code": "500", "message": f"Internal server error: {str(e)}", "data": None,
                    "error_code": "500-SYS", "status": False}, 500

                    
class DocumentUpdateAPI(Resource):        
    def _validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        update_data = {
            "last_modified_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "last_modified_by": "system"
        }

        date_fields = [
            ('documentCode', 'doc_code'),
            ('name', 'doc_title'),
            ('description', 'doc_content'),
            ('documentCategoryCode', 'category_id'),
            ('documentTypeCode', 'type_id'),
            ('industrySectorCodes', 'industry_sector_ids'),
            ('agencyIssuedCodes', 'agency_ids'),
            ('signerCodes', 'signer_ids'),
            ('source', 'data_source'),
            ('positionCodes', 'position_ids'),
            ('decreeIssued', 'doc_issue_date'),
            ('decreeEffect', 'doc_effective_date'),
            ('dateExpired', 'doc_expiry_date'),
            ('decreeStatusCode', 'effective_status_id'),
            ('issuedLevelCode', 'issuing_level_id'),
            ('keywordCodes', 'keyword_ids'),
            ('referenceStorageCodes', 'reference_storage_ids'),
            ('treeCodes', 'tree_ids'),
            ('shortDescription', 'doc_short_description'),
            ('storageCode', 'storage_id')
        ]

        date_value_fields = ['decreeIssued', 'decreeEffect', 'dateExpired']

        for (input_field, mongo_field) in date_fields:
            if input_field not in data:
                continue
            
            if input_field in ['keywordCodes', 'industrySectorCodes', 'agencyIssuedCodes', 'signerCodes', 'positionCodes', 'referenceStorageCodes', 'treeCodes']:
                update_data[mongo_field] = data[input_field]
                continue
            
            if input_field in date_value_fields:
                value = data[input_field]
                if value is None or value == "":
                    update_data[mongo_field] = None
                else:
                    update_data[mongo_field] = value
            else:
                if data[input_field]:
                    update_data[mongo_field] = data[input_field]
        
        return update_data


    def post(self, idOrCode: str) -> Dict[str, Any]:
        """
        Update document information in law_documents collection.

        Returns:
            Dict[str, Any]: Response with updated document data or error message.
        """
        bind_contextvars(task="DocumentUpdateAPI")
        start_time = datetime.now()
        data = request.get_json() or {}

        update_data = self._validate_input(data)
        keyword_ids = update_data.get("keyword_ids", [])
        
        try:
            law_tree_manager.update_subject_ids_with_doc_id(doc_id=idOrCode, keyword_ids = keyword_ids)
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("update_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500
            
        update_data.pop("tree_ids", None)
        result = law_documents_collection.find_one_and_update(
            {"doc_id": idOrCode},
            {"$set": update_data},
            return_document=True
        )        
        
        if not result:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("update_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "404-NOTFOUND", "error.message": f"Document not found for id {idOrCode}"}, id_or_code=idOrCode)
            response = make_response(data=None, code=2000, message="Document not found")
            response["error_code"] = "404-NOTFOUND"
            response["status"] = False
            return response, 404

        # Update in Elastic
        try:
            document = law_documents_collection.find_one({"doc_id": idOrCode})
            update_es_status = es_indexer.update_document(document)
            if not update_es_status:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("update_document_failed", action="post", **{"event.status": "failed", "event.duration": duration, "error.code": "500-SYS", "error.message": "Error updating document in Elasticsearch"})
                response = make_response(data=None, code=2000, message="Error updating document in Elasticsearch")
                response["error_code"] = "500-SYS"
                response["status"] = False
                return response, 500
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("update_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500

        response_data = {
            "code": result.get("doc_id", ""),
            "documentCode": result.get("doc_code", ""),
            "name": result.get("doc_title", "")
        }

        duration = (datetime.now() - start_time).total_seconds()
        logger.info("update_document_success", action="post", **{"event.duration": duration, "event.status": "success"}, document_updated=response_data)
        return make_response(data=response_data, code=0, message="Success"), 200


class DocumentSemanticSearchAPI(Resource):
    """API for searching documents in Elasticsearch with pagination and streaming."""

    def _validate_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and parse filter parameters from request body.

        Args:
            filters (Dict[str, Any]): Filter parameters from request body.

        Returns:
            Dict[str, Any]: Validated filter parameters.

        Raises:
            ValueError: If date format is invalid.
        """
        validated_filters = {}
        # Text search parameters
        if 'text' in filters:
            validated_filters['text'] = str(filters['text'])
        if 'top_k' in filters:
            validated_filters['top_k'] = int(filters['top_k'])

        if 'searchFields' in filters and isinstance(filters['searchFields'], list):
            validated_filters['searchFields'] = [str(f) for f in filters['searchFields']]
        
        # Status filter
        if 'status' in filters:
            validated_filters['status'] = str(filters['status'])

        # Code filters
        code_fields = [
            'documentCategoryCodes', 'keywordCodes', 'industrySectorCodes',
            'issuedLevelCodes', 'agencyIssuedCodes', 'decreeStatusCodes', 'codes', 'positionCodes', 'signerCodes', 'documentTypeCodes'
        ]
        for field in code_fields:
            if field in filters and isinstance(filters[field], list):
                validated_filters[field] = [str(v) for v in filters[field]]        

        # Date range filters
        date_fields = [
            ('decreeIssuedFrom', 'decreeIssuedTo'),
            ('dateExpiredFrom', 'dateExpiredTo'),
            ('decreeEffectFrom', 'decreeEffectTo')
        ]
        for start_field, end_field in date_fields:
            if start_field in filters and filters[start_field]:
                validated_filters[start_field] = parse_date(filters[start_field])
            if end_field in filters and filters[end_field]:
                validated_filters[end_field] = parse_date(filters[end_field])

        return validated_filters


    def _semantic_search(self, validated_filters):
        """Semantic search using API."""
        text = validated_filters.get("text", "")      
        field = validated_filters.get("searchFields", ["name", "content"])
        top_k = validated_filters.get("top_k", 200)

        if field == ['name']:
            payload = {
            "query": text,
            "knowledge_name": AppConfig.SEMANTIC_SEARCH_KNOWLEDGE_NAME,
            "model_type": AppConfig.SEMANTIC_SEARCH_KNOWLEDGE_NAME_MODEL,
            "top_k": top_k
            }
        elif field == ['content']:
            payload = {
            "query": text,
            "knowledge_name": AppConfig.SEMANTIC_SEARCH_KNOWLEDGE_CONTENT,
            "model_type": AppConfig.SEMANTIC_SEARCH_KNOWLEDGE_CONTENT_MODEL,
            "top_k": top_k
        }
        else:
            return None
        logger.debug("semantic_search_payload", action="_semantic_search", payload=payload)
        logger.debug("semantic_search_endpoint", action="_semantic_search", endpoint=APIEndpoints.SEMANTIC_SEARCH)
        response = requests.post(APIEndpoints.SEMANTIC_SEARCH, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            return None


    def post(self, page: int, quantity: int):
        """Handle POST request to search documents.

        Args:
            page (int): Page number (1-based).
            quantity (int): Number of records per page (1-100).

        Returns:
            Response: Streaming JSON response with search results.
        """
        bind_contextvars(task="DocumentSemanticSearchAPI")
        start_time = datetime.now()
        # Validate input parameters
        if not isinstance(page, int) or page < 1:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("search_documents_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Page number must be a positive integer"}, page=page)
            return {"code": "400", "message": "Page number must be a positive integer", "data": None, "error_code": "400-VAL", "status": False}, 400

        if not isinstance(quantity, int) or quantity < 1 or quantity > 100:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("search_documents_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Quantity must be between 1 and 100"}, quantity=quantity)
            return {"code": "400", "message": "Quantity must be between 1 and 100", "data": None, "error_code": "400-VAL", "status": False}, 400

        try:
            # Get filters from request body and validate it
            filters = request.get_json() or {}
            validated_filters = self._validate_filters(filters)
            logger.debug("validate_filters_success", action="post", validated_filters=validated_filters)
            
            if validated_filters['text']:
                # Semantic search using API
                semantic_search_result = self._semantic_search(validated_filters)
                if not semantic_search_result:
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.error("semantic_search_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Semantic search failed"})
                    return {
                        "code": "400",
                        "message": "Semantic search failed",
                        "data": None
                    }, 400
                
                # Get document codes from semantic search result and Update codes in validated filters 
                codes = [result['document_id'] for result in semantic_search_result['result']]                        
                validated_filters['codes'] = codes
                logger.debug("semantic_search_success", action="post", codes=validated_filters['codes'])
                
            # Build Elasticsearch query
            query = build_query_semantic_search(validated_filters)
            logger.debug("create_search_query_success", action="post", search_query=query)

            # Get total count
            count_result = es_client.count(index=ElasticConfig.ELASTIC_INDEX, body={"query": query})
            total_count = count_result['count']
            logger.debug("get_total_count_success", action="post", total_matching_documents=total_count)

            # Create search generator with pagination
            skip = (page - 1) * quantity
            logger.debug("search_elasticsearch_started", action="post", page=page, quantity=quantity, skip=skip)
            search_gen = search(es_client, index=ElasticConfig.ELASTIC_INDEX, 
                                query=query, 
                                batch_size=1000,
                                max_records=quantity,
                                skip=skip)
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info("search_documents_success", action="post", **{"event.duration": duration, "event.status": "success"})
            # Stream response
            return Response(
                enrich_stream(search_gen, total_count),
                mimetype='application/json'
            )

        except ValueError as ve:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("search_documents_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": str(ve)}, exc_info=True)
            return {"code": "400", "message": f"Invalid input: {str(ve)}", "data": None, "error_code": "400-VAL", "status": False}, 400
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("search_documents_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            return {"code": "500", "message": f"Internal server error: {str(e)}", "data": None, "error_code": "500-SYS", "status": False}, 500


class UpdateEffectiveStatusAPI(Resource):
    def post(self, idOrCode: str):
        """
        Cập nhật hiệu lực cho các văn bản bị ảnh hưởng bởi văn bản đầu vào (idOrCode).

        Request body (JSON):
            - status (str, optional): Trạng thái hiệu lực muốn đặt. Mặc định: "Hết hiệu lực".
            - debug (bool, optional): Nếu true, không ghi DB, chỉ trả về các lệnh dự kiến. Mặc định: false.

        Response:
            - countUpdated: số lượng văn bản ảnh hưởng
            - updated: danh sách đối tượng gồm doc_id, status, expiry_date (nếu có)
        """
        bind_contextvars(task="UpdateEffectiveStatusAPI")
        start_time = datetime.now()
        try:
            body = request.get_json() or {}
            status_to_set = body.get('status', 'Hết hiệu lực')
            debug = bool(body.get('debug', False))
            logger.debug("update_effective_status_started", action="post", idOrCode=idOrCode, status=status_to_set, debug=debug)

            commands = update_effective_status_now(doc_id=idOrCode, status=status_to_set, debug=debug)

            # commands is a list of UpdateOne operations; extract filter/update for response readability
            updated_docs = []
            for cmd in commands:
                try:
                    # Preferred for UpdateOne
                    filter_part = getattr(cmd, '_filter', {})
                    update_part = getattr(cmd, '_doc', {})
                    updated_docs.append({
                        'doc_id': filter_part.get('doc_id'),
                        'status': update_part.get('$set', {}).get('doc_effective_status'),
                        'expiry_date': update_part.get('$set', {}).get('doc_expiry_date')
                    })
                except Exception:
                    # Fallback: if the command isn't UpdateOne (future-proof)
                    try:
                        filter_part = cmd[0] if isinstance(cmd, (list, tuple)) and len(cmd) > 0 else {}
                        update_part = cmd[1] if isinstance(cmd, (list, tuple)) and len(cmd) > 1 else {}
                        updated_docs.append({
                            'doc_id': filter_part.get('doc_id'),
                            'status': update_part.get('$set', {}).get('doc_effective_status'),
                            'expiry_date': update_part.get('$set', {}).get('doc_expiry_date')
                        })
                    except Exception:
                        updated_docs.append({'doc_id': None, 'status': None, 'expiry_date': None})

            response = {
                'countUpdated': len(commands),
                'debug': debug,
                'updated': updated_docs
            }
            duration = (datetime.now() - start_time).total_seconds()
            logger.info("update_effective_status_success", action="post", **{"event.duration": duration, "event.status": "success"}, count_updated=len(commands))
            return make_response(data=response, code=0, message='Success'), 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("update_effective_status_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500

class UpdateArticleEffectiveStatusAPI(Resource):
    def post(self, idOrCode: str):
        """
        Cập nhật hiệu lực cho các điều luật bị ảnh hưởng bởi điều luật đầu vào (idOrCode).

        Request body (JSON):
            - status (str, optional): Trạng thái hiệu lực muốn đặt. Mặc định: "Hết hiệu lực".
            - debug (bool, optional): Nếu true, không ghi DB, chỉ trả về các lệnh dự kiến. Mặc định: false.

        Response:
            - partial_effect_count: số lượng điều luật ảnh hưởng một phần
            - full_effect_count: số lượng điều luật ảnh hưởng toàn phần
            - updated: danh sách đối tượng tác động gồm article_id, article_expiry_date (nếu có)
        """
        bind_contextvars(task="UpdateArticleEffectiveStatusAPI")
        start_time = datetime.now()
        try:
            body = request.get_json() or {}
            status_to_set = body.get('status', 'Hết hiệu lực')
            debug = bool(body.get('debug', False))
            logger.debug("update_article_effective_status_started", action="post", idOrCode=idOrCode, status=status_to_set, debug=debug)

            # Gọi hàm update_effective_status_now_article từ module article_update
            commands = update_effective_status_now_article(art_id=idOrCode, status=status_to_set, debug=debug)

            # Đếm số lượng điều luật theo loại hiệu lực
            partial_effect_count = 0
            full_effect_count = 0
            updated_articles = []
            for cmd in commands:
                try:
                    # Lấy thông tin từ UpdateOne object
                    filter_part = getattr(cmd, '_filter', {})
                    update_part = getattr(cmd, '_doc', {})

                    # Lấy thông tin chi tiết từ update command
                    article_id = filter_part.get('article_id')
                    article_status = update_part.get('$set', {}).get('article_effective_status')
                    article_expiry_date = update_part.get('$set', {}).get('article_expiry_date')

                    # Đếm theo loại status
                    if article_status == "Hết hiệu lực một phần":
                        partial_effect_count += 1
                    elif article_status == "Hết hiệu lực":
                        full_effect_count += 1

                    updated_articles.append({
                        'article_id': article_id,
                        'article_status': article_status,
                        'article_expiry_date': article_expiry_date
                    })
                except Exception as e:
                    logger.error("process_article_command_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
                    updated_articles.append({
                        'article_id': None, 
                        'article_status': None, 
                        'article_expiry_date': None
                    })

            response = {
                'partial_effect_count': partial_effect_count,
                'full_effect_count': full_effect_count,
                'total_effect_count': len(commands),
                'debug': debug,
                'updated': updated_articles,
            }
            duration = (datetime.now() - start_time).total_seconds()
            logger.info("update_article_effective_status_success", action="post", **{"event.duration": duration, "event.status": "success"}, total_effect_count=len(commands))
            return make_response(data=response, code=0, message='Success'), 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("update_article_effective_status_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500

class UpdateEffectiveStatusManualAPI(Resource):
    def post(self):
        """
        Cập nhật hiệu lực của một văn bản hoặc một điều luật 
        """
        bind_contextvars(task="UpdateEffectiveStatusManualAPI")
        start_time = datetime.now()
        parser = reqparse.RequestParser()
        parser.add_argument('doc_id', type=str, required=True)
        parser.add_argument('doc_expiry_date', type=str, required=False)
        parser.add_argument('doc_effective_status_id', type=str, required=False)

        parser.add_argument('article_id', type=str, required=False)
        parser.add_argument('article_expiry_date', type=str, required=False)
        parser.add_argument('article_effective_status_id', type=str, required=False)
        parser.add_argument('debug', type=str, required=False, default=False)
        args = parser.parse_args()
        
        # Parse dữ liệu đầu vào
        doc_id = args.get('doc_id')
        doc_expiry_date = args.get('doc_expiry_date', None)
        doc_effective_status_id = args.get('doc_effective_status_id', None)
        # doc_effective_status = args.get('doc_effective_status', None)
        
        article_id = args.get('article_id', None)
        article_expiry_date = args.get('article_expiry_date', None)
        article_effective_status_id = args.get('article_effective_status_id', None)
        # article_effective_status = args.get('article_effective_status', None)
        
        # Xử lý biến debug (chuyển string "true"/"false" sang boolean)
        debug = args.get('debug', False)

        result_log = {
            "debug_mode": debug,
            "document_updated": None,
            "article_updated": None
        } 
        try:
            logger.debug("update_effective_status_manual_started", action="post", doc_id=doc_id, article_id=article_id, debug=debug)
            # ---------------------------------------------------------
            # 1. CẬP NHẬT VĂN BẢN (LAW_DOCUMENTS)
            # ---------------------------------------------------------
            if doc_id and (doc_effective_status_id is not None or doc_expiry_date is not None):
                update_fields = {}
                if doc_effective_status_id is not None:
                    update_fields["effective_status_id"] = doc_effective_status_id if doc_effective_status_id else None
                    if doc_effective_status_id:
                        doc = law_decree_status_collection.find_one({'effective_status_id': doc_effective_status_id})
                        doc_effective_status = doc.get("effective_status_name", "") if doc else ""
                    else:
                        doc_effective_status = ""
                    update_fields["doc_effective_status"] = doc_effective_status
                if doc_expiry_date is not None:
                    update_fields["doc_expiry_date"] = doc_expiry_date if doc_expiry_date else None
                # Logic update
                if update_fields:
                    query = {"doc_id": doc_id} 
                    if debug:
                        result_log["document_updated"] = {"query": str(query), "set": update_fields}
                    else:
                        update_res = law_documents_collection.update_one(query, {"$set": update_fields})
                        article_modified_count = 0
                        if "doc_effective_status" in update_fields:
                            update_article = law_articles_collection.update_many(query, {"$set": {"effective_status_id": update_fields.get("effective_status_id"), "article_effective_status": update_fields.get("doc_effective_status")}})
                            article_modified_count += update_article.modified_count
                        if "doc_expiry_date" in update_fields:
                            update_article = law_articles_collection.update_many(query, {"$set": {"article_expiry_date": update_fields.get("doc_expiry_date")}})
                            article_modified_count += update_article.modified_count
                        result_log["document_updated"] = {
                            "matched_count": update_res.matched_count,
                            "modified_count": update_res.modified_count,
                            "article_updated": article_modified_count
                        }

            # ---------------------------------------------------------
            # 2. CẬP NHẬT ĐIỀU LUẬT (LAW_ARTICLES)
            # ---------------------------------------------------------
            if article_id and (article_effective_status_id is not None or article_expiry_date is not None):
                update_fields = {}
                if article_effective_status_id is not None:
                    update_fields["effective_status_id"] = article_effective_status_id if article_effective_status_id else None
                    if article_effective_status_id:
                        doc = law_decree_status_collection.find_one({'effective_status_id': article_effective_status_id})
                        update_fields["article_effective_status"] = doc.get("effective_status_name", "") if doc else ""
                    else:
                        update_fields["article_effective_status"] = ""
                if article_expiry_date is not None:
                    update_fields["article_expiry_date"] = article_expiry_date if article_expiry_date else None
                
                # Logic update
                if update_fields:
                    query = {"article_id": article_id} 
                    if debug:
                        result_log["article_updated"] = {"query": str(query), "set": update_fields}
                    else:
                        update_res = law_articles_collection.update_one(query, {"$set": update_fields})
                        result_log["article_updated"] = {
                            "matched_count": update_res.matched_count,
                            "modified_count": update_res.modified_count
                        }

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("update_effective_status_manual_success", action="post", **{"event.duration": duration, "event.status": "success"}, data=result_log)
            return {
                "message": "Process completed",
                "data": result_log
            }, 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("update_effective_status_manual_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            return {"message": "Internal Server Error", "error": str(e)}, 500

class ListArticlesAPI(Resource):
    def get(self):
        """
        Lấy danh sách điều luật (article_title và article_content)
        - Hỗ trợ phân trang qua query params: ?page=1&limit=10&doc_id=...
        """
        bind_contextvars(task="ListArticlesAPI")
        start_time = datetime.now()
        try:
            # ---- Parse query params ----
            parser = reqparse.RequestParser()
            parser.add_argument("page", type=int, default=1, location="args")
            parser.add_argument("limit", type=int, default=10, location="args")
            parser.add_argument("doc_id", type=str, required=True, location="args")
            args = parser.parse_args()

            page = max(1, args["page"])
            limit = max(1, args["limit"])
            skip = (page - 1) * limit
            doc_id = args["doc_id"]

            logger.debug("list_articles_started", action="get", doc_id=doc_id)

            law_count = law_articles_collection.count_documents({"doc_id": doc_id})
            if law_count == 0:
                duration = (datetime.now() - start_time).total_seconds()
                logger.warning("list_articles_not_found", action="get", **{"event.duration": duration, "event.status": "failed"}, doc_id=doc_id)
                return make_response(code=2000, message="Document not found", data=None), 404

            total = law_count
            cursor = law_articles_collection.find(
                {"doc_id": doc_id},
                {"article_id": 1, "article_title": 1, "article_content": 1, "_id": 0}
            ).skip(skip).limit(limit)
            data = list(cursor)

            result = {
                "page": page,
                "limit": limit,
                "total": total,
                "data": data,
            }
            duration = (datetime.now() - start_time).total_seconds()
            logger.info("list_articles_success", action="get", **{"event.duration": duration, "event.status": "success"}, doc_id=doc_id, total=total)
            return make_response(code=0, message="Success", data=result), 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("list_articles_failed", action="get", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(code=2000, message=str(e), data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500

class DocumentEffectiveStatusStatisticsAPI(Resource):
    def get(self):
        bind_contextvars(task="DocumentEffectiveStatusStatisticsAPI")
        start_time = datetime.now()
        try:
            req_parser = reqparse.RequestParser()
            req_parser.add_argument("year", type=int, location="args", default=None)
            args = req_parser.parse_args()
            year = args["year"]

            match_stage = {}
            if year:
                match_stage["doc_issue_date"] = {
                    "$regex": f"^{year}-",
                    "$options": "i"
                }

            # Gom nhóm trạng thái văn bản
            pipeline = []
            if match_stage:
                pipeline.append({"$match": match_stage})
            
            pipeline.extend([
                {
                    "$lookup": {
                        "from": MongoDBCollectionConfig.LAW_EFFECTIVE_STATUS_COLLECTION_NAME,
                        "localField": "effective_status_id",
                        "foreignField": "effective_status_id",
                        "as": "status_info"
                    }
                },
                {
                    "$unwind": {
                        "path": "$status_info",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$switch": {
                                "branches": [
                                    {
                                        "case": {
                                            "$regexMatch": {
                                                "input": {"$ifNull": ["$status_info.effective_status_name", ""]},
                                                "regex": r"^Còn hiệu lực$",
                                                "options": "i"
                                            }
                                        },
                                        "then": "Còn hiệu lực"
                                    },
                                    {
                                        "case": {
                                            "$regexMatch": {
                                                "input": {"$ifNull": ["$status_info.effective_status_name", ""]},
                                                "regex": r"^Hết hiệu lực$",
                                                "options": "i"
                                            }
                                        },
                                        "then": "Hết hiệu lực"
                                    },
                                    {
                                        "case": {
                                            "$regexMatch": {
                                                "input": {"$ifNull": ["$status_info.effective_status_name", ""]},
                                                "regex": r"^Chưa có hiệu lực$",
                                                "options": "i"
                                            }
                                        },
                                        "then": "Chưa có hiệu lực"
                                    }
                                ],
                                "default": "Hiệu lực không xác định"
                            }
                        },
                        "count": {"$sum": 1}
                    }
                }
            ])

            # Thực thi pipeline
            doc_stats = list(law_documents_collection.aggregate(pipeline))
            total_docs = sum(d["count"] for d in doc_stats)

            # Đảm bảo có đủ 4 nhóm
            status_labels = [
                "Còn hiệu lực",
                "Hết hiệu lực",
                "Chưa có hiệu lực",
                "Hiệu lực không xác định"
            ]
            stats_map = {d["_id"]: d["count"] for d in doc_stats}

            result = []
            for label in status_labels:
                count = int(stats_map.get(label, 0))
                percent = round((count / total_docs * 100) if total_docs > 0 else 0.0, 2)
                result.append({
                    "status": label,
                    "documentCount": count,
                    "documentCountPercent": percent
                })

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("get_document_effective_status_statistics_success", action="get", **{"event.duration": duration, "event.status": "success"}, total_docs=total_docs)
            return make_response(data=result, code=0, message="Success"), 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_document_effective_status_statistics_failed", action="get", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DocumentExpiringAPI(Resource):
    def get(self):
        """
        Lấy danh sách các văn bản sắp hết hiệu lực trong vòng 3 tháng tới.
        Xử lý cả 2 định dạng datetime: ISO format và string format.
        Hỗ trợ filter theo tên văn bản (search) với kiểu include (chứa chuỗi).
        """
        bind_contextvars(task="DocumentExpiringAPI")
        start_time = datetime.now()
        try:
            req_parser = reqparse.RequestParser()
            req_parser.add_argument("page", type=int, location="args", default=1)
            req_parser.add_argument("limit", type=int, location="args", default=20)
            req_parser.add_argument("search", type=str, location="args", default="")
            args = req_parser.parse_args()
            page = max(1, args["page"])
            limit = min(100, max(1, args["limit"]))
            skip = (page - 1) * limit
            search_term = args["search"]

            now = datetime.utcnow()
            three_months_later = now + timedelta(days=90)

            # Initial match: only documents with non-null doc_expiry_date
            initial_match = {"doc_expiry_date": {"$ne": None}}
            if search_term:
                initial_match["$or"] = [
                    {"doc_title": {"$regex": search_term, "$options": "i"}},
                    {"doc_code": {"$regex": search_term, "$options": "i"}}
                ]

            # Aggregation pipeline: convert string dates, filter by date range, sort, paginate
            pipeline = [
                {"$match": initial_match},
                {
                    "$addFields": {
                        "expiry_date_parsed": {
                            "$cond": {
                                "if": {"$eq": [{"$type": "$doc_expiry_date"}, "date"]},
                                "then": "$doc_expiry_date",
                                "else": {
                                    "$cond": {
                                        "if": {"$eq": [{"$type": "$doc_expiry_date"}, "string"]},
                                        "then": {"$dateFromString": {"dateString": "$doc_expiry_date", "onError": None}},
                                        "else": None
                                    }
                                }
                            }
                        }
                    }
                },
                {
                    "$match": {
                        "expiry_date_parsed": {
                            "$ne": None,
                            "$gte": now,
                            "$lte": three_months_later
                        }
                    }
                },
                {
                    "$addFields": {
                        "days_until_expiry": {
                            "$divide": [
                                {"$subtract": ["$expiry_date_parsed", now]},
                                1000 * 60 * 60 * 24  # ms -> day
                            ]
                        }
                    }
                },
                {"$sort": {"days_until_expiry": 1}},
                {
                    "$facet": {
                        "metadata": [{"$count": "total"}],
                        "data": [
                            {"$skip": skip},
                            {"$limit": limit},
                            {
                                "$project": {
                                    "_id": {"$toString": "$_id"},
                                    "doc_id": 1,
                                    "doc_code": 1,
                                    "doc_title": 1,
                                    "doc_effective_status": 1,
                                    "doc_expiry_date": {
                                        "$dateToString": {
                                            "format": "%Y-%m-%d %H:%M:%S",
                                            "date": "$expiry_date_parsed"
                                        }
                                    },
                                    "days_until_expiry": {"$floor": "$days_until_expiry"}
                                }
                            }
                        ]
                    }
                }
            ]

            result_cursor = law_documents_collection.aggregate(pipeline)
            agg_result = list(result_cursor)

            if agg_result:
                facet_result = agg_result[0]
                total = facet_result["metadata"][0]["total"] if facet_result["metadata"] else 0
                paginated_docs = facet_result["data"]
            else:
                total = 0
                paginated_docs = []

            result = {
                "page": page,
                "limit": limit,
                "total": total,
                "data": paginated_docs
            }

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("get_expiring_documents_success", action="get", **{"event.duration": duration, "event.status": "success"}, total=total, months=3)
            return make_response(data=result, code=0, message="Success"), 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_expiring_documents_failed", action="get", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DocumentIndexedByDateAPI(Resource):
    def get(self):
        structlog.contextvars.bind_contextvars(task="DocumentIndexedByDateAPI")
        start_time = datetime.now()
        try:
            parser = reqparse.RequestParser()
            parser.add_argument("interval", type=str, location="args", default="day", choices=("day", "week", "month"))
            parser.add_argument("year", type=int, location="args", default=None)
            args = parser.parse_args()
            interval = args["interval"]
            year     = args["year"]

            now = datetime.utcnow()
            if year:
                date_from = f"{year}-01-01"
                date_to   = f"{year}-12-31"
            else:
                three_months_ago = now - relativedelta(months=3)
                date_from = three_months_ago.strftime("%Y-%m-%d")
                date_to   = now.strftime("%Y-%m-%d")

            query_body = {
                "size": 10000,
                "_source": ["doc_id", "doc_title", "doc_code", "status_in_system", "doc_issue_date"],
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "range": {
                                    "doc_issue_date.keyword": {  # ← .keyword, bỏ format
                                        "gte": date_from,
                                        "lte": date_to,
                                    }
                                }
                            }
                        ]
                    }
                },
                "aggs": {
                    "by_date": {
                        "terms": {                              # ← đổi date_histogram → terms
                            "field": "doc_issue_date.keyword",
                            "size":  10000,
                            "order": {"_key": "asc"}
                        }
                    }
                }
            }

            response = es_client.search(index=ElasticConfig.ELASTIC_INDEX, body=query_body)

            # ---- Group histogram theo interval trong Python ----
            from collections import defaultdict

            def truncate_date(date_str: str, interval: str) -> str:
                """Cắt ngắn date_str theo interval."""
                try:
                    # Normalize về yyyy-MM-dd
                    d = date_str[:10]
                    dt = datetime.strptime(d, "%Y-%m-%d")
                    if interval == "day":
                        return dt.strftime("%Y-%m-%d")
                    elif interval == "week":
                        # Lấy ngày đầu tuần (Monday)
                        return (dt - timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
                    elif interval == "month":
                        return dt.strftime("%Y-%m")
                except Exception:
                    return date_str[:10]

            histogram_map   = defaultdict(int)
            monthly_map     = defaultdict(int)

            for bucket in response["aggregations"]["by_date"]["buckets"]:
                date_str = bucket["key"]
                count    = bucket["doc_count"]
                try:
                    d = date_str[:10]
                    datetime.strptime(d, "%Y-%m-%d")  # validate
                except Exception:
                    continue

                histogram_map[truncate_date(date_str, interval)] += count
                monthly_map[date_str[:7]] += count  # yyyy-MM

            histogram = [
                {"date": date, "count": count}
                for date, count in sorted(histogram_map.items())
                if count > 0
            ]
            monthly_effective = [
                {"month": month, "count": count}
                for month, count in sorted(monthly_map.items())
            ]

            # ---- Parse document list ----
            def format_decree_effect(value):
                if not value:
                    return None
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(value, fmt).strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        continue
                return value

            hits = response.get("hits", {}).get("hits", [])
            documents = [
                {
                    "code":         src.get("doc_id"),
                    "name":         src.get("doc_title"),
                    "documentCode": src.get("doc_code"),
                    "status":       src.get("status_in_system"),
                    "decreeIssued": format_decree_effect(src.get("doc_issue_date"))
                }
                for hit in hits
                for src in [hit.get("_source", {})]
            ]

            data = {
                "histogram":        histogram,
                "monthlyEffective": monthly_effective,
                "documents":        documents,
                "total":            len(documents)
            }

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("get_document_indexed_by_date_success", action="get", **{"event.duration": duration, "event.status": "success"},
                        histogram_count=len(histogram), monthly_count=len(monthly_effective),
                        total_documents=len(documents))
            return make_response(data=data, code=0, message="Success"), 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_document_indexed_by_date_failed", action="get", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DocumenEffectByYearAPI(Resource):
    def get(self):
        structlog.contextvars.bind_contextvars(task="DocumenEffectByYearAPI")
        start_time = datetime.now()
        try:
            parser = reqparse.RequestParser()
            parser.add_argument("year", type=int, location="args", default=datetime.utcnow().year)
            args = parser.parse_args()
            year          = args["year"]
            previous_year = year - 1

            def get_monthly_counts(target_year: int) -> dict:
                """Query ES và group theo tháng trong Python."""
                date_from = f"{target_year}-01-01"
                date_to   = f"{target_year}-12-31"

                query_body = {
                    "size": 0,
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "range": {
                                        "doc_issue_date.keyword": {
                                            "gte": date_from,
                                            "lte": date_to,
                                        }
                                    }
                                }
                            ]
                        }
                    },
                    "aggs": {
                        "by_date": {
                            "terms": {
                                "field": "doc_issue_date.keyword",
                                "size":  10000,
                                "order": {"_key": "asc"}
                            }
                        }
                    }
                }

                response = es_client.search(index=ElasticConfig.ELASTIC_INDEX, body=query_body)

                from collections import defaultdict
                monthly_counts = defaultdict(int)

                for bucket in response["aggregations"]["by_date"]["buckets"]:
                    date_str = bucket["key"]
                    try:
                        # Lấy tháng từ yyyy-MM-dd hoặc yyyy-MM-dd HH:mm:ss
                        month = int(date_str[5:7])
                        if 1 <= month <= 12:
                            monthly_counts[month] += bucket["doc_count"]
                    except (ValueError, IndexError):
                        continue

                return monthly_counts

            current_counts  = get_monthly_counts(year)
            previous_counts = get_monthly_counts(previous_year)

            months              = []
            year_total          = 0
            previous_year_total = 0

            for month in range(1, 13):
                current_count  = current_counts.get(month, 0)
                previous_count = previous_counts.get(month, 0)
                difference     = current_count - previous_count

                year_total          += current_count
                previous_year_total += previous_count

                months.append({
                    "month":               month,
                    "monthName":           f"Tháng {month}",
                    "documentCount":       current_count,
                    "previousYearCount":   previous_count,
                    "difference":          difference
                })

            data = {
                "year":                year,
                "previousYear":        previous_year,
                "months":              months,
                "yearTotal":           year_total,
                "previousYearTotal":   previous_year_total,
                "yearDifference":      year_total - previous_year_total
            }

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("get_doc_effect_by_year_success", action="get", **{"event.duration": duration, "event.status": "success"},
                        year=year, total_current=year_total, total_previous=previous_year_total)

            return make_response(data=data, code=0, message="Success"), 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_doc_effect_by_year_failed", action="get", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DocumentYearRangeStatisticsAPI(Resource):
    def get(self):
        structlog.contextvars.bind_contextvars(task="DocumentYearRangeStatisticsAPI")
        start_time = datetime.now()
        try:
            """
            Thống kê số lượng văn bản theo khoảng năm (begin_year đến end_year).
            Trả về histogram theo năm và tổng số văn bản trong khoảng thời gian đó.
            """
            parser = reqparse.RequestParser()
            parser.add_argument(
                "begin_year",
                type=int,
                location="args",
                required=False,
                default=None,
                help="Begin year is required"
            )
            parser.add_argument(
                "end_year",
                type=int,
                location="args",
                required=False,
                default=None
            )
            args = parser.parse_args()
            begin_year = args["begin_year"]
            end_year   = args["end_year"] if args["end_year"] else datetime.utcnow().year

            if begin_year and end_year and begin_year > end_year:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("get_document_year_range_statistics_failed", action="get", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "begin_year must be less than or equal to end_year"})
                return make_response(data=None, code=2000, message="begin_year must be less than or equal to end_year"), 400

            # Build range filter chỉ khi có begin_year
            range_filter = []
            if begin_year:
                date_from = f"{begin_year}-01-01"
                date_to   = f"{end_year}-12-31"
                range_filter.append({
                    "range": {
                        "doc_issue_date.keyword": {
                            "gte": date_from,
                            "lte": date_to,
                        }
                    }
                })

            query_body = {
                "size": 0,
                "query": {
                    "bool": {
                        "filter": range_filter
                    }
                },
                "aggs": {
                    "yearly_histogram": {
                        "terms": {
                            "field": "doc_issue_date.keyword",
                            "size":  10000,
                            "order": {"_key": "asc"}
                        }
                    }
                }
            }

            response = es_client.search(index=ElasticConfig.ELASTIC_INDEX, body=query_body)

            # Group theo năm trong Python vì field là keyword, không phải date
            from collections import defaultdict
            year_counts = defaultdict(int)

            for bucket in response["aggregations"]["yearly_histogram"]["buckets"]:
                date_str = bucket["key"]
                try:
                    year = int(str(date_str)[:4])
                    year_counts[year] += bucket["doc_count"]
                except (ValueError, IndexError):
                    continue

            histogram = [
                {"year": year, "count": count}
                for year, count in sorted(year_counts.items())
            ]
            total = sum(b["count"] for b in histogram)

            data = {
                "histogram": histogram,
                "total":     total
            }

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("get_document_year_range_statistics_success", action="get", **{"event.duration": duration, "event.status": "success"}, begin_year=begin_year, end_year=end_year, total=total)
            return make_response(data=data, code=0, message="Success"), 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_document_year_range_statistics_failed", action="get", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DocumentStatusStaticAPI(Resource):
    def get(self):
        structlog.contextvars.bind_contextvars(task="DocumentStatusStaticAPI")
        start_time = datetime.now()
        try:
            current_year = datetime.utcnow().year

            # ✅ Lookup effective_status_name từ law_effective_status
            status_pipeline = [
                {
                    "$lookup": {
                        "from": "law_effective_status",
                        "localField": "effective_status_id",
                        "foreignField": "effective_status_id",
                        "as": "effective_status_info"
                    }
                },
                {
                    "$addFields": {
                        "effective_status_name": {
                            "$ifNull": [
                                {"$arrayElemAt": ["$effective_status_info.effective_status_name", 0]},
                                "Hiệu lực không xác định"
                            ]
                        }
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "$switch": {
                                "branches": [
                                    {
                                        "case": {
                                            "$regexMatch": {
                                                "input": "$effective_status_name",
                                                "regex": r"^Còn hiệu lực$",
                                                "options": "i"
                                            }
                                        },
                                        "then": "Còn hiệu lực"
                                    },
                                    {
                                        "case": {
                                            "$regexMatch": {
                                                "input": "$effective_status_name",
                                                "regex": r"^Hết hiệu lực$",
                                                "options": "i"
                                            }
                                        },
                                        "then": "Hết hiệu lực"
                                    },
                                    {
                                        "case": {
                                            "$regexMatch": {
                                                "input": "$effective_status_name",
                                                "regex": r"^Chưa có hiệu lực$",
                                                "options": "i"
                                            }
                                        },
                                        "then": "Chưa có hiệu lực"
                                    }
                                ],
                                "default": "Hiệu lực không xác định"
                            }
                        },
                        "count": {"$sum": 1}
                    }
                }
            ]

            status_stats = list(law_documents_collection.aggregate(status_pipeline))
            status_map = {d["_id"]: d["count"] for d in status_stats}

            total_documents = sum(status_map.values())
            active_documents = status_map.get("Còn hiệu lực", 0)
            expired_documents = status_map.get("Hết hiệu lực", 0)
            not_yet_effective_documents = status_map.get("Chưa có hiệu lực", 0)
            unknown_status_documents = status_map.get("Hiệu lực không xác định", 0)

            # ✅ Loại trừ doc_expiry_date = ""
            issued_this_year = law_documents_collection.count_documents({
                "doc_issue_date": {"$regex": f"^{current_year}-"}
            })

            expired_this_year = law_documents_collection.count_documents({
                "$and": [
                    {"doc_expiry_date": {"$ne": ""}},
                    {"doc_expiry_date": {"$regex": f"^{current_year}-"}}
                ]
            })

            data = {
                "totalDocuments": total_documents,
                "activeDocuments": active_documents,
                "expiredDocuments": expired_documents,
                "notYetEffectiveDocuments": not_yet_effective_documents,
                "unknownStatusDocuments": unknown_status_documents,
                "issuedThisYear": issued_this_year,
                "expiredThisYear": expired_this_year
            }

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("get_document_status_static_success", action="get", **{"event.duration": duration, "event.status": "success"}, data=data)
            return make_response(data=data, code=0, message="Success"), 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_document_status_static_failed", action="get", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500
        

class CheckDocumentExistsAPI(Resource):
    def post(self):
        structlog.contextvars.bind_contextvars(task="CheckDocumentExistsAPI")
        start_time = datetime.now()
        try:
            # --- Parse input ---
            body       = request.get_json(silent=True) or {}
            doc_code   = body.get("doc_code", "").strip()
            agency_ids = body.get("agency_ids", [])
            doc_id = body.get("doc_id", [])

            if not doc_code:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("check_document_exists_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "doc_code is required"})
                response = make_response(data=None, code=2000, message="doc_code is required")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            # --- Build query ---
            query = {"doc_code": doc_code, "status_in_system" : "IN"}
            if agency_ids:
                query["agency_ids"] = {"$all": agency_ids}  # ← $in → $all
            if doc_id:
                query["doc_id"] = {"$ne": doc_id}

            # --- Find duplicates ---
            documents = list(law_documents_collection.find(
                query,
                {"_id": 0, "doc_id": 1}
            ))

            doc_ids = [d["doc_id"] for d in documents]

            data = {
                "status": len(doc_ids) > 0,
                "doc_ids": doc_ids
            }

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("check_document_exists_success", action="post", **{"event.duration": duration, "event.status": "success"}, doc_code=doc_code, agency_ids=agency_ids, data=data)
            return make_response(data=data, code=0, message="Success"), 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("check_document_exists_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# Register API resource
api.add_resource(GetDocumentDetailAPI, '/document/<idOrCode>')
api.add_resource(DocumentTextSearchAPI, '/document/text-search/<int:page>/<int:quantity>')
api.add_resource(DocumentSemanticSearchAPI, '/document/semantic-search/<int:page>/<int:quantity>')
api.add_resource(DocumentDeleteAPI, '/document/delete/<idOrCode>')
api.add_resource(DocumentUpdateAPI, '/document/update/<idOrCode>')
api.add_resource(UpdateEffectiveStatusAPI, '/document/effective-status/update/<idOrCode>')
api.add_resource(UpdateArticleEffectiveStatusAPI, '/document/effective-status/update/article/<idOrCode>')
api.add_resource(UpdateEffectiveStatusManualAPI, '/document/effective-status/update/manual')
api.add_resource(ListArticlesAPI, '/document/segment')
api.add_resource(DocumentEffectiveStatusStatisticsAPI, '/document/effective-status/static')
api.add_resource(DocumentIndexedByDateAPI, '/document/effective-date/static')
api.add_resource(DocumenEffectByYearAPI, '/document/effective-date/get-by-year')
api.add_resource(DocumentExpiringAPI, '/document/expiring')
api.add_resource(DocumentYearRangeStatisticsAPI, '/document/effective-date/year-range-static')
api.add_resource(DocumentStatusStaticAPI, '/document/status/static')
api.add_resource(CheckDocumentExistsAPI, '/document/check-exists')
