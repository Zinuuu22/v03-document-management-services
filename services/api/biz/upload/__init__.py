from core.common.mongo.client import get_mongo_client
import structlog
import os
import sys
import uuid
import json
import shutil
from datetime import datetime
from typing import Dict, Any, Generator, Optional
from core.common import elastic
from flask_restful import Resource
from flask import request, Response
from structlog.contextvars import bind_contextvars
from pymongo import MongoClient
from constants import MongoDBConfig, MigrateConfig, AppConfig
from docx import Document
import tempfile


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from constants import MinioConfig, MongoDBCollectionConfig
from services.api import api
from services.api.utils import make_response
from services.api.biz.upload.utils import send_requests_to_kafka_extract, send_requests_to_kafka_index, add_relationship_to_db
from core.common.minio import MinIOClient
from core.common.reader import DocumentProcessor
from core.common.elastic import ElasticIndexer
logger = structlog.get_logger()


minioClient = MinIOClient()
elasticIndexer = ElasticIndexer()
documentProcessor = DocumentProcessor()

client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
biz_upload_record_collection = db[MongoDBCollectionConfig.BIZ_UPLOAD_RECORD_COLLECTION_NAME]
biz_upload_documents_collection = db[MongoDBCollectionConfig.BIZ_UPLOAD_DOCUMENTS_COLLECTION_NAME]
biz_upload_articles_collection = db[MongoDBCollectionConfig.BIZ_UPLOAD_ARTICLES_COLLECTION_NAME]

pipeline_document_state_collection = db[MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME]

law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_document_storage_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_STORAGE_COLLECTION_NAME]
law_documents_category_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_TYPE_COLLECTION_NAME]
law_keywords_collection = db[MongoDBCollectionConfig.LAW_KEYWORD_COLLECTION_NAME]
law_issued_levels_collection = db[MongoDBCollectionConfig.LAW_ISSUING_LEVEL_COLLECTION_NAME]
law_signers_collection = db[MongoDBCollectionConfig.LAW_SIGNERS_COLLECTION_NAME]
law_positions_collection = db[MongoDBCollectionConfig.LAW_POSITIONS_COLLECTION_NAME]
law_agencies_collection = db[MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME]
law_industry_sectors_collection = db[MongoDBCollectionConfig.LAW_INDUSTRY_SECTORS_COLLECTION_NAME]

law_social_relation_draft_collection = db[MongoDBCollectionConfig.LAW_SOCIAL_RELATION_DRAFT_COLLECTION_NAME]
law_social_relation_collection = db[MongoDBCollectionConfig.LAW_SOCIAL_RELATION_COLLECTION_NAME]
law_social_relation_mapping_draft_collection = db[MongoDBCollectionConfig.LAW_SOCIAL_RELATION_MAPPING_DRAFT_COLLECTION_NAME]
law_social_relation_mapping_collection = db[MongoDBCollectionConfig.LAW_SOCIAL_RELATION_MAPPING_COLLECTION_NAME]

law_authority_draft_collection = db[MongoDBCollectionConfig.LAW_AUTHORITY_DRAFT_COLLECTION_NAME]
law_authority_collection = db[MongoDBCollectionConfig.LAW_AUTHORITY_COLLECTION_NAME]
law_authority_mapping_draft_collection = db[MongoDBCollectionConfig.LAW_AUTHORITY_MAPPING_DRAFT_COLLECTION_NAME]
law_authority_mapping_collection = db[MongoDBCollectionConfig.LAW_AUTHORITY_MAPPING_COLLECTION_NAME]

law_reference_draft_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_DRAFT_COLLECTION_NAME]
law_reference_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_COLLECTION_NAME]

law_regulated_entities_draft_collection = db[MongoDBCollectionConfig.LAW_REGULATED_OBJECT_DRAFT_COLLECTION_NAME]
law_regulated_entities_collection = db[MongoDBCollectionConfig.LAW_REGULATED_OBJECT_COLLECTION_NAME]
law_regulated_object_mapping_draft_collection = db[MongoDBCollectionConfig.LAW_REGULATED_OBJECT_MAPPING_DRAFT_COLLECTION_NAME]
law_regulated_object_mapping_collection = db[MongoDBCollectionConfig.LAW_REGULATED_OBJECT_MAPPING_COLLECTION_NAME]

law_references_article_draft_collection = db[MongoDBCollectionConfig.LAW_REFERENCES_ARTICLE_DRAFT_COLLECTION_NAME]
law_references_article_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_ARTICLE_COLLECTION_NAME]

law_articles_draft_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_DRAFT_COLLECTION_NAME]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]

# Validate date functions
def validate_date(date_str: Optional[str]) -> Optional[str]:
    """Validate date string in format DD/MM/YYYY."""
    if not date_str:
        return None
    try:
        datetime.strptime(date_str, "%d/%m/%Y")
        return date_str
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected DD/MM/YYYY")

def parse_date(date_str: str) -> str:
    """Convert date from DD/MM/YYYY to YYYY-MM-DD HH:MM:SS format.

    Args:
        date_str: Date string in DD/MM/YYYY format (e.g., '19/06/2015').

    Returns:
        Date string in YYYY-MM-DD HH:MM:SS format (e.g., '2015-06-19 00:00:00').

    Raises:
        ValueError: If the input date string is invalid.
    """
    try:
        if date_str:            
            parsed_date = datetime.strptime(date_str, "%d/%m/%Y")
            return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
        return ""
    except ValueError as e:
        raise ValueError(f"Invalid date format: {date_str}. Expected DD/MM/YYYY.") from e

# Validate code functions
def validate_code(collection, field: str, code: str, error_message: str) -> Dict:
    """Validate code in a collection with case-insensitive query."""
    if not code:
        return None
    result = collection.find_one({field: {'$regex': f'^{code}$', '$options': 'i'}})
    if not result:
        raise ValueError(error_message)
    return result

# Validate and create keyword functions
def validate_and_create_keyword(keyword: Dict, collection) -> Dict:
    """Validate or create a keyword in law_keywords."""
    if not isinstance(keyword, dict) or 'code' not in keyword or 'name' not in keyword:
        raise ValueError("Invalid keyword format")
    law_keyword = collection.find_one({'keyword_id': {'$regex': f'^{keyword["code"]}$', '$options': 'i'}})
    if not law_keyword:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        keyword_obj = {
            "keyword_id": keyword['code'],
            "keyword_name": keyword['name'],
            "created_by": "System",
            "created_at": current_time,
            "last_modified_at": current_time,
            "last_modified_by": "System",
            "status": "ACTIVE"
        }
        collection.insert_one(keyword_obj)
    return {
        'code': keyword['code'],
        'name': keyword['name'],
        'score': keyword.get('score', 0.0),
        'duplicate': keyword.get('duplicate', 0.0)
    }


class DocumentUploadRecordUploadAPI(Resource):
    """API for creating document upload records."""

    def post(self) -> Dict[str, Any]:
        bind_contextvars(task="DocumentUploadRecordUploadAPI")
        start_time = datetime.now()

        files = request.files.getlist('files')
        if not files or all(file.filename == '' for file in files):
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("upload_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "No files uploaded"})
            response = make_response(data=None, code='400', message='No files uploaded')
            response["error_code"] = "400-VAL"
            response["status"] = False
            return response, 400

        logger.debug("upload_document_started", action="post", file_count=len(files))
        uploaded_records = []
        for file in files:
            try:
                documentProcessor.validate_file(file)
            except ValueError as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("upload_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": str(e)}, filename=file.filename, exc_info=True)
                response = make_response(data=None, code='400', message=str(e))
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400
            
            filename = file.filename
            created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            temp_file_path = None
            try:
                suffix = os.path.splitext(filename)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    file.save(tmp)
                    temp_file_path = tmp.name
                logger.debug("upload_file_saved_temp", action="post", path=temp_file_path, filename=filename)
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("upload_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, filename=filename, exc_info=True)
                response = make_response(data=None, code='500', message="Failed to process uploaded file")
                response["error_code"] = "500-SYS"
                response["status"] = False
                return response, 500
            
                        
            # Step 1: Extract Segments
            path_file_docx = None
            try:
                upload_path = temp_file_path + ".upload"
                shutil.copy(temp_file_path, upload_path)
                path_file_docx = documentProcessor.convert_doc_to_docx(temp_file_path)
                logger.debug("upload_doc_converted_to_docx", action="post", path_file_docx=path_file_docx, filename=filename)
                doc_content = documentProcessor.read_docx(path_file_docx)
            except Exception as e:
                doc_content = ""
                logger.error("upload_doc_read_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e)}, filename=filename, exc_info=True)
            finally:
                if path_file_docx and os.path.exists(path_file_docx):
                    os.remove(path_file_docx)
                    logger.debug("upload_docx_temp_cleaned", action="post", filename=filename)
            
            try:
                unique_id = str(uuid.uuid4())
                bind_contextvars(**{"request.id": unique_id})
                from core.v03.content_extractor import extract_components
                logger.info("upload_segment_extraction_started", action="post", filename=filename, doc_id=unique_id)
                
                article_extraction_start = datetime.now()
                segments = extract_components(doc_content, document_code=unique_id)

                norm_segments = []
                for segment in segments:
                    norm_segment = {
                            "article_id"              : segment['code'],
                            "doc_id"                  : segment['document_code'],
                            "article_title"           : segment['article_title'],
                            "article_content"         : segment['article_content'],
                            "article_index"           : segment['index'],
                            "start_article_index"     : segment['segment_index'],
                            "article_effective_date"  : segment.get('article_effective_date', ""),
                            "article_expiry_date"     : segment.get('article_expiry_date', ""),
                            "effective_status_id"     : "3969bc0a-a285-4a6d-9865-5b549cf88d20",
                            "part"                    : segment.get('part', ""),
                            "chapter"                 : segment.get('chapter', ""),
                            "section"                 : segment.get('section', ""),
                            "sub_section"             : segment.get('sub_section', ""),
                            "created_at"              : created_date,
                            "created_by"              : "System",
                            "last_modified_at"        : created_date,
                            "last_modified_by"        : "System",
                        }
                    norm_segments.append(norm_segment)

                law_articles_collection.insert_many(norm_segments)
                article_extraction_duration = (datetime.now() - article_extraction_start).total_seconds()
                logger.info("upload_segment_extraction_success", action="post", filename=filename, doc_id=unique_id, count=len(norm_segments), **{"event.duration": article_extraction_duration})
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("upload_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, filename=filename, exc_info=True)
                response = make_response(data=None, code=2000, message='Failed to extract segments')
                response["error_code"] = "500-SYS"
                response["status"] = False
                return response, 415
            
            # Step 2: Upload to MinIO            
            try:                
                with open(upload_path, 'rb') as f:
                    object_name = minioClient.upload_file(file=f, bucket_name=MinioConfig.UPLOAD_BUCKET_NAME, file_name=filename)
                logger.info("upload_file_to_minio_success", action="post", filename=filename, bucket=MinioConfig.UPLOAD_BUCKET_NAME, object_name=object_name)
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("upload_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, filename=filename, exc_info=True)
                response = make_response(data=None, code=2000, message="Failed to upload file to MinIO")
                response["error_code"] = "500-SYS"
                response["status"] = False
                return response, 500
            finally:
                for p in [temp_file_path, upload_path]:
                    if p and os.path.exists(p):
                        os.remove(p)
                logger.debug("upload_temp_files_cleaned", action="post", filename=filename)
            
            
            # Step 2b: Create law_document_storage record
            try:
                storage_record = {
                    "storage_id": unique_id,
                    "bucket": MinioConfig.UPLOAD_BUCKET_NAME,
                    "name": filename,
                    "path": object_name,
                    "created_at": created_date,
                    "created_by": "System",
                    "last_modified_at": created_date,
                    "last_modified_by": "System"
                }
                law_document_storage_collection.insert_one(storage_record)
                logger.info("upload_storage_record_created", action="post", storage_id=unique_id, filename=filename)
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("upload_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, filename=filename, exc_info=True)
                response = make_response(data=None, code=2000, message="Failed to create storage record")
                response["error_code"] = "500-SYS"
                response["status"] = False
                return response, 500

            # Step 3: Create pipeline document state record with nested step objects
            try:
                extracting_step = {"status": "EXTRACTING", "start_at": created_date, "finish_at": None, "duration_time": None}
                success_step = {"status": "PROCESSED", "start_at": None, "finish_at": None, "duration_time": None}
                                
                record = {
                    "doc_id"                      : unique_id,
                    "request_id"                  : unique_id,
                    "file_name"                   : filename,
                    "status"                      : "EXTRACTING",
                    "articles_extraction"         : success_step.copy(),                    
                    "metadata_extraction"         : extracting_step.copy(),
                    "keyword_extraction"          : extracting_step.copy(),
                    "relationship_extraction"     : extracting_step.copy(),
                    "regulated_entity_extraction" : extracting_step.copy(),
                    "social_relation_extraction"  : extracting_step.copy(),
                    "authority_extraction"        : extracting_step.copy(),
                    "article_relationship_extraction" : extracting_step.copy(),                    
                    "articles_classification"     : success_step.copy(),
                    "elastic_indexing"            : extracting_step.copy(),                    
                    "article_embedding"           : extracting_step.copy(),
                    "content_embedding"           : extracting_step.copy(),                    
                    "title_embedding"             : extracting_step.copy(),
                    "created_at"                  : created_date,
                    "created_by"                  : "System",
                    "last_modified_at"            : created_date,
                    "last_modified_by"            : "System",
                }
                pipeline_document_state_collection.insert_one(record)                
                logger.debug("upload_pipeline_state_created", action="post", doc_id=unique_id, filename=filename)
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("upload_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, filename=filename, exc_info=True)
                response = make_response(data=None, code=2000, message="Failed to create pipeline document state")
                response["error_code"] = "500-SYS"
                response["status"] = False
                return response, 500

            
            # Step 4: Create draft document in law_documents with status_in_system=OUT
            try:                
                document = {
                    "doc_id": unique_id,
                    "storage_id" : unique_id,
                    "doc_code" : "",
                    "doc_title" : "",
                    "doc_short_description" : "",
                    "doc_content": doc_content,
                    "doc_issue_date": None,
                    "doc_effective_date": None,
                    "doc_expiry_date": None,
                    "data_source": "UPLOAD",
                    "category_id": None,
                    "effective_status_id": None,
                    "type_id": None,
                    "issuing_level_id": None,
                    "agency_ids": [],
                    "industry_sector_ids": [],
                    "keyword_ids": [],
                    "position_ids": [],
                    "signer_ids": [],
                    "tree_ids": [],
                    "reference_storage_ids": [],
                    "status_in_system": "OUT",
                    "created_at" : created_date,
                    "created_by" : "System",
                    "last_modified_at" : created_date,
                    "last_modified_by" : "System"
                    }
                law_documents_collection.insert_one(document)   
                logger.debug("upload_draft_document_created", action="post", doc_id=unique_id, filename=filename)
                                           
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("upload_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, filename=filename, exc_info=True)
                response = make_response(data=None, code='500', message=str(e))
                response["error_code"] = "500-SYS"
                response["status"] = False
                return response, 500
        
                        
            # Step 5: Send message to Kafka
            try:
                logger.debug("send_upload_kafka_started", action="post", filename=filename, doc_id=unique_id)
                status = send_requests_to_kafka_extract(request_id=unique_id, doc_id=unique_id, doc_content=doc_content)
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("send_upload_kafka_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, filename=filename, exc_info=True)
                response = make_response(data=None, code='500', message='Failed to send message to Kafka')
                response["error_code"] = "500-SYS"
                response["status"] = False
                return response, 500

            if not status:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("send_upload_kafka_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": "One or more Kafka topic sends returned status=False"}, filename=filename)
                response = make_response(data=None, code='500', message='Failed to send message to Kafka')
                response["error_code"] = "500-SYS"
                response["status"] = False
                return response, 500

            logger.debug("send_upload_kafka_success", action="post", filename=filename, doc_id=unique_id)
            uploaded_records.append({
                "record_id": unique_id,
                "doc_id": unique_id,
                "file_name": filename,
                "bucket": MinioConfig.UPLOAD_BUCKET_NAME,
                "storage_id": unique_id,
                "status": "EXTRACTING"
            })
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info("upload_document_success", action="post", **{"event.duration": duration, "event.status": "success"}, file_count=len(uploaded_records))
        return make_response(data=uploaded_records, code='200', message='Files uploaded successfully'), 200



# class DocumentUploadRecordSearchAPI(Resource):
#     """API for searching document upload records with pagination and streaming."""

#     def _stream_records(self, query: Dict, skip: int, quantity: int) -> Generator[str, None, None]:
#         """Generator function to stream records as JSON chunks."""
#         try:
#             total_count = pipeline_document_state_collection.count_documents(query)            
#             records = pipeline_document_state_collection.find(query).sort('created_at', -1).skip(skip).limit(quantity)
                        
#             yield '{"count": ' + str(total_count) + ', "models": ['
#             first = True
#             for record in records:
#                 try:
                                                            
#                     document = law_documents_collection.find_one({'doc_id': record.get('doc_id', ''), 'status_in_system': 'OUT'})
#                     if document is None:
#                         continue
                    
#                     if not first:
#                         yield ','                    
                                        
#                     metadata_extraction_status = record.get('metadata_extraction', {}).get('status', '')
#                     keyword_extraction_status = record.get('keyword_extraction', {}).get('status', '')
#                     relationship_extraction_status = record.get('relationship_extraction', {}).get('status', '')
#                     regulated_entity_extraction_status = record.get('regulated_entity_extraction', {}).get('status', '')
#                     social_relation_extraction_status = record.get('social_relation_extraction', {}).get('status', '')                    
#                     authority_extraction_status = record.get('authority_extraction', {}).get('status', '')
#                     article_relationship_extraction_status = record.get('article_relationship_extraction', {}).get('status', '')

#                     model = {
#                         'storageCode'                      : document.get('storage_id', ''),
#                         'code'                             : record.get('doc_id', ''),
#                         'name'                             : record.get('file_name', ''),
#                         'description'                      : '',
#                         'createdBy'                        : record.get('created_by', ''),
#                         'createdDate'                      : record.get('created_at', ''),
#                         'lastModifiedBy'                   : record.get('last_modified_by', ''),
#                         'lastModified'                     : record.get('last_modified_at', ''),
#                         'status'                           : record.get('status', ''),
#                         'text'                             : '',
#                         'fileName'                         : record.get('file_name', ''),
#                         'extractMetadataStatus'            : "DONE" if metadata_extraction_status == "PROCESSED" else metadata_extraction_status,
#                         'extractKeywordStatus'             : "DONE" if keyword_extraction_status == "PROCESSED" else keyword_extraction_status,
#                         'extractRelationshipStatus'        : "DONE" if relationship_extraction_status == "PROCESSED" else relationship_extraction_status,
#                         'extractRegulatedEntitiesStatus'   : "DONE" if regulated_entity_extraction_status == "PROCESSED" else regulated_entity_extraction_status,
#                         'extractSocialRelationStatus'      : "DONE" if social_relation_extraction_status == "PROCESSED" else social_relation_extraction_status,
#                         'extractAuthorityStatus'           : "DONE" if authority_extraction_status == "PROCESSED" else authority_extraction_status,
#                         'extractArticleRelationshipStatus' : "DONE" if article_relationship_extraction_status == "PROCESSED" else article_relationship_extraction_status,
#                     }
#                     yield json.dumps(model)                    
#                     first = False
#                     logger.debug("DocumentUploadRecordSearchAPI", msg="Streaming record", doc_id=record.get('doc_id', 'unknown'))
#                 except Exception:
#                     logger.debug("DocumentUploadRecordSearchAPI", exc_info=True, msg="Error streaming record", doc_id=record.get('doc_id', 'unknown'))
#                     pass
#             yield ']}'
#         except Exception as e:
#             logger.error("DocumentUploadRecordSearchAPI", **{"error.code": "500-SYS", "error.message": str(e)}, msg="Error during streaming", exc_info=True)
#             yield json.dumps({"code": "500", "message": f"Internal server error during streaming: {str(e)}"})

#     def post(self, page: int, quantity: int):
                
#         body = request.get_json()        
        
#         # query status not COMPLETED
#         query = {"status": {"$ne": "COMPLETED"}}          
#         if body:
#             text = body.get('text', None)
#             if text:
#                 query['file_name'] = {'$regex': text, '$options': 'i'}
            
#             status = body.get('status', None)
#             if status:
#                 query['status'] = {'$regex': status, '$options': 'i'}

#         logger.debug("DocumentUploadRecordSearchAPI", query=query)

#         # Validate input parameters
#         if not isinstance(page, int) or page < 1:
#             logger.error("DocumentUploadRecordSearchAPI", **{"error.code": "400-VAL", "error.message": "Invalid page number"}, msg="Invalid page number", page=page)
#             response = make_response(data=None, code='400', message='Page number must be a positive integer')
#             response["error_code"] = "400-VAL"
#             response["status"] = False
#             return response, 400

#         if not isinstance(quantity, int) or quantity < 1 or quantity > 100:
#             logger.error("DocumentUploadRecordSearchAPI", **{"error.code": "400-VAL", "error.message": "Invalid quantity"}, msg="Invalid quantity", quantity=quantity)
#             response = make_response(data=None, code='400', message='Quantity must be between 1 and 100')
#             response["error_code"] = "400-VAL"
#             response["status"] = False
#             return response, 400

#         # TODO: Add authentication check
#         skip = (page - 1) * quantity
                
#         return Response(
#             self._stream_records(query, skip, quantity),
#             mimetype='application/json'
#         )


class DocumentUploadRecordSearchAPI(Resource):
    """API for searching document upload records with pagination and streaming."""

    STATUS_MAP = {
        "PROCESSED": "DONE"
    }

    def _map_status(self, status: str) -> str:
        return self.STATUS_MAP.get(status, status)

    def _build_aggregation_pipeline(self, query: Dict, skip: int, quantity: int) -> list:
        return [
                {'$match': query },
                {
                    '$lookup': {
                    'from': "law_documents",
                    'localField': "doc_id",
                    'foreignField': "doc_id",
                    'as': "law_doc",
                    'pipeline': [
                        {'$match': {'status_in_system': "OUT"}},
                        {'$project': {'_id': 0, 'storage_id': 1}},
                        {'$limit': 1}
                    ]
                    }
                },
                {'$match': {'law_doc': { '$ne': [] }}},
                {
                    '$facet': {
                    'total': [{ '$count': "count" }],
                    'records': [
                        { '$sort': { 'created_at': -1 } },
                        { '$skip': skip },
                        { '$limit': quantity }
                    ]
                    }
                }
                ]

    def _stream_records(self, query: Dict, skip: int, quantity: int) -> Generator[str, None, None]:
        """Generator function to stream records as JSON chunks."""
        try:
            pipeline = self._build_aggregation_pipeline(query, skip, quantity)
            result   = list(pipeline_document_state_collection.aggregate(pipeline))

            if not result:
                yield '{"count": 0, "models": []}'
                return

            facet     = result[0]
            total_count = facet["total"][0]["count"] if facet.get("total") else 0
            records     = facet.get("records", [])

            yield '{"count": ' + str(total_count) + ', "models": ['

            first = True
            for record in records:
                try:
                    law_doc_list = record.get("law_doc", [])
                    if not law_doc_list:
                        continue

                    law_doc = law_doc_list[0]

                    if not first:
                        yield ','

                    model = {
                        'storageCode'                      : law_doc.get('storage_id', ''),
                        'code'                             : record.get('doc_id', ''),
                        'name'                             : record.get('file_name', ''),
                        'description'                      : '',
                        'createdBy'                        : record.get('created_by', ''),
                        'createdDate'                      : record.get('created_at', ''),
                        'lastModifiedBy'                   : record.get('last_modified_by', ''),
                        'lastModified'                     : record.get('last_modified_at', ''),
                        'status'                           : record.get('status', ''),
                        'text'                             : '',
                        'fileName'                         : record.get('file_name', ''),
                        'extractMetadataStatus'            : self._map_status(record.get('metadata_extraction',            {}).get('status', '')),
                        'extractKeywordStatus'             : self._map_status(record.get('keyword_extraction',             {}).get('status', '')),
                        'extractRelationshipStatus'        : self._map_status(record.get('relationship_extraction',        {}).get('status', '')),
                        'extractRegulatedEntitiesStatus'   : self._map_status(record.get('regulated_entity_extraction',   {}).get('status', '')),
                        'extractSocialRelationStatus'      : self._map_status(record.get('social_relation_extraction',    {}).get('status', '')),
                        'extractAuthorityStatus'           : self._map_status(record.get('authority_extraction',          {}).get('status', '')),
                        'extractArticleRelationshipStatus' : self._map_status(record.get('article_relationship_extraction',{}).get('status', '')),
                    }

                    yield json.dumps(model)
                    first = False
                    logger.debug("stream_upload_record", action="_stream_records", doc_id=record.get('doc_id', 'unknown'))

                except Exception:
                    logger.debug("stream_upload_record_failed", action="_stream_records", exc_info=True, doc_id=record.get('doc_id', 'unknown'))
                    continue

            yield ']}'

        except Exception as e:
            logger.error("search_upload_records_failed", action="_stream_records", **{"error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            yield json.dumps({"code": "500", "message": f"Internal server error during streaming: {str(e)}"})

    def post(self, page: int, quantity: int):
        bind_contextvars(task="DocumentUploadRecordSearchAPI")
        start_time = datetime.now()

        # Validate input parameters
        if not isinstance(page, int) or page < 1:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("search_upload_records_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Page number must be a positive integer"}, page=page)
            response = make_response(data=None, code='400', message='Page number must be a positive integer')
            response["error_code"] = "400-VAL"
            response["status"]     = False
            return response, 400

        if not isinstance(quantity, int) or quantity < 1 or quantity > 100:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("search_upload_records_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Quantity must be between 1 and 100"}, quantity=quantity)
            response = make_response(data=None, code='400', message='Quantity must be between 1 and 100')
            response["error_code"] = "400-VAL"
            response["status"]     = False
            return response, 400

        body = request.get_json()

        query = {"status": {"$ne": "COMPLETED"}}

        if body:
            text = body.get('text', None)
            if text:
                query['file_name'] = {'$regex': text, '$options': 'i'}

            status = body.get('status', None)
            if status:
                query['status'] = {'$regex': status, '$options': 'i'}

        logger.debug("search_upload_records_started", action="post", page=page, quantity=quantity, query=query)

        skip = (page - 1) * quantity

        return Response(
            self._stream_records(query, skip, quantity),
            mimetype='application/json'
        )

        

class DocumentUploadRecordByIdAPI(Resource):
    """API for retrieving a document segment record by record_id with details from biz_upload_documents."""

    def post(self, idOrCode: str) -> Dict[str, Any]:
        bind_contextvars(task="DocumentUploadRecordByIdAPI")
        start_time = datetime.now()

        # Validate input parameter
        if not idOrCode or not isinstance(idOrCode, str):
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_upload_record_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Invalid idOrCode"}, id_or_code=idOrCode)
            response = make_response(data=None, code='400', message='idOrCode must be a non-empty string')
            response["error_code"] = "400-VAL"
            response["status"] = False
            return response, 400

        logger.debug("get_upload_record_started", action="post", id_or_code=idOrCode)

        try:
            # Query pipeline_document_state
            pipeline_state = pipeline_document_state_collection.find_one({'doc_id': idOrCode})
            if not pipeline_state:
                duration = (datetime.now() - start_time).total_seconds()
                logger.warning("get_upload_record_not_found", action="post", **{"event.duration": duration, "event.status": "failed"}, id_or_code=idOrCode)
                return make_response(data=None, code='404', message='Record not found'), 404

            # Query law_documents with status_in_system='OUT' (draft/uploaded documents)
            document = law_documents_collection.find_one({'doc_id': idOrCode})
            if not document:
                duration = (datetime.now() - start_time).total_seconds()
                logger.warning("get_upload_record_not_found", action="post", **{"event.duration": duration, "event.status": "failed"}, id_or_code=idOrCode)
                return make_response(data=None, code='404', message='Document not found'), 404

            
            metadata_extraction = pipeline_state.get('metadata_extraction', {}).get('status', '')
            relationship_extraction = pipeline_state.get('relationship_extraction', {}).get('status', '')
            keyword_extraction = pipeline_state.get('keyword_extraction', {}).get('status', '')
            
            response_data = {
                'code': document.get('doc_id', ''),
                'name': document.get('doc_title', ''),
                'description': document.get('doc_content', ''),
                'shortDescription': document.get('doc_short_description', ''),
                'documentCode': document.get('doc_code', ''),
                'storageCode': document.get('storage_id', ''),
                'dataSource': document.get('data_source', 'UPLOAD'),
                'extractMetadataStatus': "DONE" if metadata_extraction == "PROCESSED" else metadata_extraction,
                'extractRelationshipStatus': "DONE" if relationship_extraction == "PROCESSED" else relationship_extraction,
                'extractKeywordStatus': "DONE" if keyword_extraction == "PROCESSED" else keyword_extraction,
                'decreeIssued': document.get('doc_issue_date', None),
                'decreeEffect': document.get('doc_effective_date', None),
                'dateExpired': document.get('doc_expiry_date', None),    
                'decreeStatusCode': document.get('effective_status_id', None),
                'treeCodes': [c for c in document.get('tree_ids', []) if c],
                'source': document.get('data_source', 'UPLOAD')                
            }

            # Get referenceStorages
            reference_storage_ids = document.get('reference_storage_ids', [])
            reference_storages = []
            for storage_id in reference_storage_ids:
                document_storage = law_document_storage_collection.find_one({"storage_id": storage_id})                
                if document_storage:
                    reference_storages.append({
                        'code': storage_id,
                        'name': document_storage.get('name', '')
                    })

            response_data['referenceStorages'] = reference_storages
            response_data['referenceStorageCodes'] = [c for c in reference_storage_ids if c]
            
            # Get document category code
            document_category_code = document.get('category_id', None)
            if document_category_code is None:
                document_type = document.get('document_type', '')
                law_document_type = law_documents_category_collection.find_one({
                    'doc_type_name': {'$regex': f'^{document_type}$', '$options': 'i'}
                })
                document_category_code = law_document_type.get('type_id', '') if law_document_type else ''
            response_data['documentCategoryCode'] = document_category_code
    
            
            # Get keywords code
            keyword_ids = document.get('keyword_ids', [])
            if not keyword_ids:
                keywords = document.get('keywords', [])
                keyword_ids = []
                document_keywords = []
                for keyword in keywords:
                    keyword_obj = law_keywords_collection.find_one({
                        'keyword_name': {'$regex': f'^{keyword}$', '$options': 'i'}
                    })
                    if not keyword_obj:
                        keyword_obj = {
                            "keyword_id": str(uuid.uuid4()),
                            "keyword_name": keyword,
                            "created_by": "System",
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "last_modified_by": "System",
                            "status": "ACTIVE"
                        }
                        law_keywords_collection.insert_one(keyword_obj)
                    keyword_ids.append(keyword_obj.get('keyword_id', ''))
                    document_keywords.append({
                        'code': keyword_obj.get('keyword_id', ''),
                        'name': keyword_obj.get('keyword_name', '')
                    })
            else:
                document_keywords = []
                for keyword_id in keyword_ids:
                    keyword_obj = law_keywords_collection.find_one({'keyword_id': keyword_id})
                    if keyword_obj:
                        document_keywords.append({
                            'code': keyword_obj.get('keyword_id', ''),
                            'name': keyword_obj.get('keyword_name', '')
                        })
            response_data['keywordCodes'] = [c for c in keyword_ids if c]
            response_data['keywords'] = document_keywords
            
            # Get issuing level code
            issued_level_id = document.get('issuing_level_id', None)
            if issued_level_id is None:
                issued_level_code = document.get('document_level', '')            
                law_issued_level = law_issued_levels_collection.find_one({
                    'issuing_level_name': {'$regex': f'^{issued_level_code}$', '$options': 'i'}
                })
                issued_level_id = law_issued_level.get('issuing_level_id', '') if law_issued_level else ''
            response_data['issuedLevelCode'] = issued_level_id

            # Get document form code
            type_id = document.get('type_id', '')
            response_data['documentTypeCode'] = type_id

            # Get signers
            signer_ids = document.get('signer_ids', [])
            if not signer_ids:
                human_signers = document.get('human_sign', [])
                signer_ids = []
                signers = []
                for human_signer in human_signers:
                    human_name = human_signer.get('human_name', None)
                    if human_name is None or len(human_name.strip()) == 0:
                        continue                    
                    signer_obj = law_signers_collection.find_one({
                        'signer_name': {'$regex': f'^{human_name}$', '$options': 'i'}
                    })
                    if not signer_obj:
                        signer_obj = {
                            "signer_id": str(uuid.uuid4()),
                            "signer_name": human_name,
                            "created_by": "System",
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "last_modified_by": "System",
                            "status": "ACTIVE"
                        }
                        law_signers_collection.insert_one(signer_obj)
                    signer_ids.append(signer_obj.get('signer_id', ''))
                    signers.append({
                        'code': signer_obj.get('signer_id', ''),
                        'name': signer_obj.get('signer_name', '')
                    })
            else:
                signers = []
                for signer_id in signer_ids:
                    signer_obj = law_signers_collection.find_one({'signer_id': signer_id})
                    if signer_obj:
                        signers.append({
                            'code': signer_obj.get('signer_id', ''),
                            'name': signer_obj.get('signer_name', '')
                        })
            response_data['signerCodes'] = [c for c in signer_ids if c]
            response_data['signers'] = signers

            # Get positions
            position_ids = document.get('position_ids', [])
            if not position_ids:
                human_signers = document.get('human_sign', [])
                position_ids = []
                positions = []
                for human_signer in human_signers:
                    human_title = human_signer.get('human_title', None)
                    if human_title is None or len(human_title.strip()) == 0:
                        continue
                    position_obj = law_positions_collection.find_one({
                        'position_name': {'$regex': f'^{human_title}$', '$options': 'i'}
                    })
                    if not position_obj:
                        position_obj = {
                            "position_id": str(uuid.uuid4()),
                            "position_name": human_title,
                            "created_by": "System",
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "last_modified_by": "System",
                            "status": "ACTIVE"
                        }
                        law_positions_collection.insert_one(position_obj)
                    position_ids.append(position_obj.get('position_id', ''))
                    positions.append({
                        'code': position_obj.get('position_id', ''),
                        'name': position_obj.get('position_name', '')
                    })
            else:
                positions = []
                for position_id in position_ids:
                    position_obj = law_positions_collection.find_one({'position_id': position_id})
                    if position_obj:
                        positions.append({
                            'code': position_obj.get('position_id', ''),
                            'name': position_obj.get('position_name', '')
                        })
            response_data['positionCodes'] = [c for c in position_ids if c]
            response_data['positions'] = positions


            # Get agencies
            agency_ids = document.get('agency_ids', [])
            if not agency_ids:
                agencies = document.get('agency', [])            
                agency_ids = []
                document_agencies = []
                for agency in agencies:
                    agency_obj = law_agencies_collection.find_one({'agency_name': {'$regex': f'^{agency}$', '$options': 'i'}})
                    if not agency_obj:                        
                        agency_obj = {
                            "agency_id": str(uuid.uuid4()),
                            "agency_name": agency,
                            "created_by": "System",
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                            "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "last_modified_by": "System",
                            "status": "ACTIVE"
                        }
                        law_agencies_collection.insert_one(agency_obj)
                    agency_ids.append(agency_obj.get('agency_id', ''))
                    document_agencies.append({
                        'code': agency_obj.get('agency_id', ''),
                        'name': agency_obj.get('agency_name', '')
                    })    
            else:
                document_agencies = []
                for agency_id in agency_ids:
                    agency_obj = law_agencies_collection.find_one({'agency_id': agency_id})
                    if agency_obj:
                        document_agencies.append({
                            'code': agency_obj.get('agency_id', ''),
                            'name': agency_obj.get('agency_name', '')
                        })
            response_data['agencyIssuedCodes'] = [c for c in agency_ids if c]
            response_data['agencies'] = document_agencies

            # Get industry_sector form code
            industry_sector_ids = document.get('industry_sector_ids', [])
            industry_sectors = []
            for industry_sector_id in industry_sector_ids:
                industry_sector_obj = law_industry_sectors_collection.find_one({'industry_sector_id': industry_sector_id})
                if industry_sector_obj:
                    industry_sectors.append({
                        'code': industry_sector_obj.get('industry_sector_id', ''),
                        'name': industry_sector_obj.get('industry_sector_name', '')
                    })
            response_data['industry_sectors'] = industry_sectors
            response_data['industrySectorCodes'] = [c for c in industry_sector_ids if c]

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("get_upload_record_success", action="post", **{"event.duration": duration, "event.status": "success"}, id_or_code=idOrCode)
            return make_response(data=response_data, code='200', message='Record retrieved successfully'), 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_upload_record_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code='500', message=f'Internal server error: {str(e)}')
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DocumentUploadRecordSaveDraftAPI(Resource):
    """API for saving draft document segment records."""

    def post(self) -> Dict[str, Any]:
        bind_contextvars(task="DocumentUploadRecordSaveDraftAPI")
        start_time = datetime.now()

        try:
            body = request.get_json()
            if not body:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("save_upload_draft_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "No JSON body provided"})
                response = make_response(data=None, code='400', message='No JSON body provided')
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            record_id = body.get('code')
            if not record_id:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("save_upload_draft_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Missing mandatory field: code"})
                response = make_response(data=None, code='400', message='Missing mandatory field: code')
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            mandatory_fields = [
                'name', 'documentCode', 'storageCode',
                'keywordCodes', 'industrySectorCodes', 'issuedLevelCode', 'documentTypeCode',
                'signerCodes', 'agencyIssuedCodes', 'decreeStatusCode', 'decreeEffect', 'dateExpired',
                'decreeIssued', 'treeCodes', 'referenceStorageCodes', 'shortDescription', 'source', 'positionCodes'
            ]
            for field in mandatory_fields:
                if field not in body:
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.error("save_upload_draft_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": f"Missing mandatory field: {field}"}, field=field)
                    response = make_response(data=None, code='400', message=f'Missing mandatory field: {field}')
                    response["error_code"] = "400-VAL"
                    response["status"] = False
                    return response, 400

            logger.debug("save_upload_draft_started", action="post", doc_id=record_id)
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            set_fields = {
                'doc_title':              body.get('name'),
                'doc_code':               body.get('documentCode'),
                'doc_short_description':  body.get('shortDescription', None),
                'keyword_ids':            body.get('keywordCodes', []),
                'storage_id':             body.get('storageCode'),
                'issuing_level_id':       body.get('issuedLevelCode', None),
                'type_id':                body.get('documentTypeCode', None),
                'agency_ids':             body.get('agencyIssuedCodes', []),
                'signer_ids':             body.get('signerCodes', []),
                'position_ids':           body.get('positionCodes', []),
                'doc_issue_date':         body.get('decreeIssued', None),
                'doc_effective_date':     body.get('decreeEffect', None),
                'doc_expiry_date':        body.get('dateExpired', None),
                'tree_ids':               body.get('treeCodes', []),
                'effective_status_id':    body.get('decreeStatusCode', None),
                'reference_storage_ids':  body.get('referenceStorageCodes', []),
                'industry_sector_ids':    body.get('industrySectorCodes', []),
                'data_source':            body.get('source', 'UPLOAD'),
                'last_modified_at':       current_time,
                'last_modified_by':       'System',
            }

            result = law_documents_collection.update_one(
                {'doc_id': record_id, 'status_in_system': 'OUT'},
                {'$set': set_fields}
            )

            if result.matched_count == 0:
                existing = law_documents_collection.find_one({'doc_id': record_id})

                if existing and existing.get('status_in_system') == 'IN':
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.error("save_upload_draft_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Document already published, cannot save draft"}, doc_id=record_id)
                    response = make_response(data=None, code='400',
                                             message='Document already published, cannot edit draft')
                    response["error_code"] = "400-VAL"
                    response["status"] = False
                    return response, 400

                elif not existing:
                    # Chưa tồn tại → insert mới
                    new_doc = {
                        **set_fields,
                        'doc_id':          record_id,
                        'status_in_system': 'OUT',
                        'created_at':       current_time,
                        'created_by':       'System',
                    }
                    law_documents_collection.insert_one(new_doc)
                    logger.info("save_upload_draft_inserted", action="post", doc_id=record_id)
                else:
                    law_documents_collection.update_one(
                        {'doc_id': record_id},
                        {'$set': set_fields}
                    )
                    logger.debug("save_upload_draft_updated", action="post", doc_id=record_id)
            else:
                logger.debug("save_upload_draft_updated", action="post", doc_id=record_id)

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("save_upload_draft_success", action="post", **{"event.duration": duration, "event.status": "success"}, doc_id=record_id)
            return make_response(data=None, code='200', message='Draft saved successfully'), 200

        except ValueError as ve:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("save_upload_draft_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": str(ve)}, exc_info=True)
            response = make_response(data=None, code='400', message=str(ve))
            response["error_code"] = "400-VAL"
            response["status"] = False
            return response, 400
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("save_upload_draft_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code='500', message=f'Internal server error: {str(e)}')
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DocumentUploadRecordSaveDocumentAPI(Resource):
    """API for saving document segment records to law_documents collection."""

    def post(self) -> Dict[str, Any]:
        bind_contextvars(task="DocumentUploadRecordSaveDocumentAPI")
        start_time = datetime.now()

        try:
            # Get request body
            body = request.get_json()
            if not body:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("save_upload_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "No JSON body provided"})
                response = make_response(data=None, code='400', message='No JSON body provided')
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            # Validate mandatory fields
            mandatory_fields = [                
                'code', 'name', 'documentCategoryCode', 'documentCode', 'storageCode',
                'keywordCodes', 'industrySectorCodes', 'issuedLevelCode', 'documentTypeCode',
                'signerCodes', 'agencyIssuedCodes', 'decreeStatusCode', 'decreeEffect', 'dateExpired', 
                'decreeIssued', 'treeCodes', 'referenceStorageCodes', 'shortDescription', 'source', 'positionCodes'
            ]
            for field in mandatory_fields:
                if field not in body:
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.error("save_upload_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": f"Missing mandatory field: {field}"}, field=field)
                    response = make_response(data=None, code='400', message=f'Missing mandatory field: {field}')
                    response["error_code"] = "400-VAL"
                    response["status"] = False
                    return response, 400

            # Read existing draft document from law_documents with status_in_system='OUT'
            draft_document = law_documents_collection.find_one({'doc_id': body.get('code'), 'status_in_system': 'OUT'})
            if not draft_document:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("save_upload_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "404-NOTFOUND", "error.message": "Draft document not found"}, code=body.get('code'))
                response = make_response(data=None, code='404', message='Draft document not found')
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404

            logger.debug("save_upload_document_started", action="post", doc_id=body.get('code'))
            
            # Step 1 Update document in law_documents - flip status_in_system from OUT to IN
            document = {
                'doc_id': body.get('code'),
                'doc_code': body.get('documentCode'),
                'doc_title': body.get('name'),                
                'doc_short_description': body.get('shortDescription', ''),
                'doc_content': draft_document.get('doc_content', ''),
                'doc_issue_date': body.get('decreeIssued', None),
                'doc_effective_date': body.get('decreeEffect', None), 
                'doc_expiry_date': body.get('dateExpired', None), 
                'data_source': body.get('source'),
                'created_at': draft_document.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                'created_by': draft_document.get('created_by', "SYSTEM"),
                'last_modified_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'last_modified_by': "System",
                'effective_status_id': body.get('decreeStatusCode'),
                'category_id': body.get('documentCategoryCode'),
                'type_id': body.get('documentTypeCode'),
                'industry_sector_ids': body.get('industrySectorCodes'),
                'storage_id': body.get('storageCode'),
                'keyword_ids': body.get('keywordCodes', []),
                'position_ids': body.get('positionCodes', []),
                'reference_storage_ids': body.get('referenceStorageCodes', []),
                'tree_ids': body.get('treeCodes', []),
                'signer_ids': body.get('signerCodes', []),
                'agency_ids': body.get('agencyIssuedCodes', []),
                'issuing_level_id': body.get('issuedLevelCode'),
                'status_in_system': 'IN'
            }

            # Step 2 Update document in law_documents (flip status_in_system from OUT to IN)
            filter_query = {'doc_id': body.get('code'), 'status_in_system': 'OUT'}
            law_documents_collection.update_one(
                filter_query,
                {'$set': document}
            )
            logger.debug("save_upload_document_finalized", action="post", doc_id=body.get('code'))

            # Step 3: Send Kafka index request
            request_id = str(uuid.uuid4())
            logger.debug("send_index_kafka_started", action="post", doc_id=body.get('code'), request_id=request_id)
            send_requests_to_kafka_index(request_id=request_id, doc_id=body.get('code'))
            logger.debug("send_index_kafka_success", action="post", doc_id=body.get('code'), request_id=request_id)

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("save_upload_document_success", action="post", **{"event.duration": duration, "event.status": "success"}, doc_id=body.get('code'))
            return make_response(data=None, code='200', message='Document saved successfully'), 200

        except ValueError as ve:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("save_upload_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": str(ve)}, exc_info=True)
            response = make_response(data=None, code='400', message=str(ve))
            response["error_code"] = "400-VAL"
            response["status"] = False
            return response, 400
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("save_upload_document_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code='500', message=f'Internal server error: {str(e)}')
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# Register resource
api.add_resource(DocumentUploadRecordUploadAPI, "/document-upload-record/create")
api.add_resource(DocumentUploadRecordSearchAPI, "/document-upload-record/search/<int:page>/<int:quantity>")
api.add_resource(DocumentUploadRecordByIdAPI, "/document-upload-record/get/<string:idOrCode>")
api.add_resource(DocumentUploadRecordSaveDraftAPI, "/document-upload-record/save-draft")
api.add_resource(DocumentUploadRecordSaveDocumentAPI, "/document-upload-record/save-document")
