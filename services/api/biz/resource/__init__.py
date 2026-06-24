from core.common.mongo.client import get_mongo_client
import structlog
import uuid
import os
import sys
from datetime import datetime
from typing import Dict, Any
from flask_restful import Resource
from flask import request, Response, send_file
from pymongo import MongoClient
from bson import ObjectId
import tempfile
import subprocess
from docx import Document
from io import BytesIO
import re
from html import escape

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from services.api import api
from services.api.utils import make_response
from constants import MongoDBConfig, MigrateConfig, MinioConfig, MongoDBCollectionConfig
from core.common.minio import MinIOClient
from core.common.reader import DocumentProcessor
from structlog.contextvars import bind_contextvars
import time
logger = structlog.get_logger()

# from services.api.utils.minio import download_from_minio, upload_to_minio
# from services.api.utils.reader import convert_doc_to_docx, convert_docx_to_html, HTML_TEMPLATE

minioClient = MinIOClient()
documentProcessor = DocumentProcessor()


# Khởi tạo kết nối MongoDB
client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_document_storage_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_STORAGE_COLLECTION_NAME]

ALLOWED_EXTENSIONS = ['.doc', '.docx', '.pdf']


class DownloadDocumentAPI(Resource):
    """API for downloading a document file from MinIO based on doc_id"""
    
    def get(self, idOrCode: str) -> Response:
        """
        Download a document file from MinIO.

        Args:
            idOrCode (str): The document ID or code.

        Returns:
            Response: File stream if successful, or JSON error response.
        """
        bind_contextvars(task="DownloadDocumentAPI")
        start_t = time.time()
        try:
            # Validate input
            if not idOrCode or not isinstance(idOrCode, str):
                logger.error("download_document_failed", action="get", **{"error.code": "400-VAL", "error.message": "Invalid idOrCode", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=1000, message="Invalid idOrCode")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            # Query document in MongoDB
            document = law_documents_collection.find_one({"doc_id": idOrCode})
            if document:
                storage_id = document.get("storage_id")
            else:
                storage_id = idOrCode
            
            # Query law_document_storage for file metadata
            storage_record = law_document_storage_collection.find_one({"storage_id": storage_id})
            if not storage_record:
                logger.error("download_document_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": "Storage record not found", "event.duration": time.time()-start_t, "event.status": "failure"}, storage_id=storage_id)
                response = make_response(data=None, code=2000, message="No file associated with this document")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404
            
            stored_bucket = storage_record.get("bucket", "")
            stored_path = storage_record.get("path", "")
            
            if "." in stored_bucket:
                bucket_name = MinioConfig.DEFAULT_BUCKET_NAME
                object_name = f"{stored_bucket}/{stored_path}" if stored_bucket else stored_path
                fallback_object_name = stored_path
            else:
                bucket_name = stored_bucket if stored_bucket else MinioConfig.DEFAULT_BUCKET_NAME
                object_name = stored_path
                fallback_object_name = None
                
            logger.debug("resolve_minio_location_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, bucket_name=bucket_name, object_name=object_name)
                
            if not object_name:
                logger.error("download_document_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": "No object_name found", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
                response = make_response(data=None, code=2000, message="No file associated with this document")
                response["error_code"] = "404-NOTFOUND"
                response["status"] = False
                return response, 404
                

            # Download file from MinIO
            try:
                file_stream = minioClient.download_file(object_name, bucket_name)
                file_name = os.path.basename(object_name)
                content_type = 'application/octet-stream'

                logger.info("download_document_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, object_name=object_name)
                return send_file(
                    file_stream,
                    as_attachment=True,
                    download_name=file_name,
                    mimetype=content_type
                )
            except Exception as e:
                
                if fallback_object_name and fallback_object_name != object_name:
                    try:
                        file_stream = minioClient.download_file(fallback_object_name, bucket_name)
                        file_name = os.path.basename(fallback_object_name)
                        content_type = 'application/octet-stream'

                        logger.info("download_document_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, fallback_path=fallback_object_name)
                        return send_file(
                            file_stream,
                            as_attachment=True,
                            download_name=file_name,
                            mimetype=content_type
                        )
                    except Exception as fallback_error:
                        logger.error("download_document_failed", action="get", **{"error.code": "500-SYS", "error.message": str(fallback_error), "event.duration": time.time()-start_t, "event.status": "failure"}, fallback_path=fallback_object_name, exc_info=True)
                        pass
                else:
                    logger.error("download_document_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, object_name=object_name, exc_info=True)
                
                return make_response(data=None, code=2000, message="File not found in MinIO"), 404

        except Exception as e:
            logger.error("download_document_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode, exc_info=True)
            response = make_response(data=None, code=2000, message="Internal server error")
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DisplayDocumentAPI(Resource):
    """API for retrieving a document file from MinIO and returning it as HTML for web display"""

    def get(self, idOrCode: str) -> Response:
        """
        Retrieve a document file from MinIO and return its content as HTML.

        Args:
            idOrCode (str): The document ID or code.

        Returns:
            Response: JSON response with HTML content or error details.
        """
        bind_contextvars(task="DisplayDocumentAPI")
        start_t = time.time()
        # try:
        # Validate input
        if not idOrCode or not isinstance(idOrCode, str) or not re.match(r'^[\w-]+$', idOrCode):
            logger.error("display_document_failed", action="get", **{"error.code": "400-VAL", "error.message": "Invalid idOrCode: Must be a non-empty string with alphanumeric characters or hyphens", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
            response = make_response(data=None, code=1000, message="Invalid idOrCode: Must be a non-empty string with alphanumeric characters or hyphens")
            response["error_code"] = "400-VAL"
            response["status"] = False
            return response, 400

        # Query document in MongoDB
        document = law_documents_collection.find_one({"doc_id": idOrCode})
        if document:
            storage_id = document.get("storage_id")
        else:
            storage_id = idOrCode

        logger.debug("resolve_storage_started", action="get", storage_id=storage_id)

        # Query law_document_storage for file metadata
        storage_record = law_document_storage_collection.find_one({"storage_id": storage_id})
        if not storage_record:
            logger.error("display_document_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": "Storage record not found", "event.duration": time.time()-start_t, "event.status": "failure"}, storage_id=storage_id)
            response = make_response(data=None, code=2000, message="No file associated with this document")
            response["error_code"] = "404-NOTFOUND"
            response["status"] = False
            return response, 404
        
        stored_bucket = storage_record.get("bucket", "")
        stored_path = storage_record.get("path", "")
        
        if "." in stored_bucket:
            bucket_name = MinioConfig.DEFAULT_BUCKET_NAME
            object_name = f"{stored_bucket}/{stored_path}" if stored_bucket else stored_path
            fallback_object_name = stored_path
        else:
            bucket_name = stored_bucket if stored_bucket else MinioConfig.DEFAULT_BUCKET_NAME
            object_name = stored_path
            fallback_object_name = None

        if not object_name:
            logger.error("display_document_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": "No object_name found", "event.duration": time.time()-start_t, "event.status": "failure"}, idOrCode=idOrCode)
            response = make_response(data=None, code=2000, message="No file associated with this document")
            response["error_code"] = "404-NOTFOUND"
            response["status"] = False
            return response, 404

        # Download file from MinIO
        try:
            file_stream = minioClient.download_file(object_name, bucket_name)
            file_name = os.path.basename(object_name)
        except Exception as e:
            logger.error("display_document_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            
            if fallback_object_name and fallback_object_name != object_name:
                try:
                    file_stream = minioClient.download_file(fallback_object_name, bucket_name)
                    file_name = os.path.basename(fallback_object_name)
                except Exception as fallback_error:
                    logger.error("display_document_failed", action="get", **{"error.code": "500-SYS", "error.message": str(fallback_error), "event.duration": time.time()-start_t, "event.status": "failure"}, fallback_path=fallback_object_name, exc_info=True)
                    return make_response(data=None, code=2000, message="File not found in MinIO"), 404
            else:
                logger.error("display_document_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
                return make_response(data=None, code=2000, message="File not found in MinIO"), 404

        # Process file content based on extension
        file_data = file_stream.read()
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.doc') as temp_file:
                temp_file.write(file_data)
                temp_file_path = temp_file.name
        except Exception as e:
            logger.error("display_document_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message="Error processing .doc file")
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500    
        
        if file_name.lower().endswith('.doc'):
            docx_file_path = documentProcessor.convert_doc_to_docx(file_input=temp_file_path)
            if not docx_file_path:
                logger.error("display_document_failed", action="get", **{"error.code": "500-SYS", "error.message": "Failed to convert .doc to .docx", "event.duration": time.time()-start_t, "event.status": "failure"}, temp_file=temp_file_path)
                response = make_response(data=None, code=2000, message="Server cannot process .doc files")
                response["error_code"] = "500-SYS"
                response["status"] = False
                return response, 500
        else:
            docx_file_path = temp_file_path
        
        # Convert docx to html
        html_content = documentProcessor.docx_to_html_mammoth(docx_input=docx_file_path)

        # Remove temp files
        try:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        except Exception as e:
            logger.error("display_document_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, temp_file=temp_file_path, exc_info=True)
        
        try:
            if docx_file_path and docx_file_path != temp_file_path and os.path.exists(docx_file_path):
                os.remove(docx_file_path)
        except Exception as e:
            logger.error("display_document_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, docx_file=docx_file_path, exc_info=True)

        logger.info("display_document_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"})
        return make_response(data={"html": html_content}, code=0, message="Success"), 200


class ResourceUploadAPI(Resource):
    """API for uploading legal document attachments to MinIO and recording metadata."""
    def post(self) -> Response:
        """
        Handle POST request to upload a file to MinIO and record metadata in MongoDB.

        Returns:
            Response: JSON with file metadata or error message.
        """
        bind_contextvars(task="ResourceUploadAPI")
        start_t = time.time()
        try:                        
            # Validate file
            if 'file' not in request.files:
                logger.error("upload_resource_failed", action="post", **{"error.code": "400-VAL", "error.message": "No file provided in request", "event.duration": time.time()-start_t, "event.status": "failure"})
                response = make_response(data=None, code=1000, message="File is required")
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            file = request.files['file']
            try:
                documentProcessor.validate_file(file)
            except ValueError as e:
                logger.error("upload_resource_failed", action="post", **{"error.code": "400-VAL", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
                response = make_response(data=None, code=1000, message=str(e))
                response["error_code"] = "400-VAL"
                response["status"] = False
                return response, 400

            # Upload to MinIO            
            filename = file.filename
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:                
                object_name = minioClient.upload_file(file=file, bucket_name=MinioConfig.UPLOAD_BUCKET_NAME)                
            except Exception as e:
                logger.error("upload_resource_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, filename=filename, exc_info=True)
                response = make_response(data=None, code=2000, message="Failed to upload file to MinIO")
                response["error_code"] = "500-SYS"
                response["status"] = False
                return response, 500

            # Create record in law_document_storage
            storage_id = str(uuid.uuid4())
            record = {
                "storage_id": storage_id,
                "bucket": MinioConfig.UPLOAD_BUCKET_NAME,
                "name": filename,
                "path": object_name,
                "created_at": created_at,
                "created_by": "SYSTEM"
            }

            try:
                law_document_storage_collection.insert_one(record)
            except Exception as e:
                logger.error("mongodb_insert_failed", action="post", **{"error.code": "500-DB", "error.message": str(e)}, filename=filename, exc_info=True)
            
            # Prepare response
            response = {
                'path': object_name,        
                'size': file.content_length,
                'bucket': MinioConfig.UPLOAD_BUCKET_NAME,
                'code': storage_id,
                'name': filename,
                'createdBy': 'SYSTEM',
                'createdDate': created_at,
                'lastModifiedBy': 'SYSTEM',
                'lastModified': created_at,
                'status': 'ACTIVE'
            }            
            logger.info("upload_resource_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, filename=filename, storage_id=storage_id)
            return make_response(data=response, code=0, message="File uploaded successfully"), 200
                
        except Exception as e:
            logger.error("upload_resource_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message="Internal server error")
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# Register API resource
api.add_resource(DownloadDocumentAPI, '/resource/download/<idOrCode>')
api.add_resource(DisplayDocumentAPI, '/resource/display/<idOrCode>')
api.add_resource(ResourceUploadAPI, '/resource/upload')
