import io
import os
import sys
from flask import jsonify
from flask_restful import Resource, reqparse, request
import structlog
from structlog.contextvars import bind_contextvars
import time
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)  # Use insert for better path precedence
from services.api import api
from services.api.utils import preprocess_document_from_storage_code, preprocess_document_from_stream, make_response
from core.v03.content_extractor import extract_components
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()


class ExtractSegmentsFromStorageCodeAPI(Resource):
    """API for extracting segments from storage code"""
    
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('storage_code', type=str, required=True, nullable=False)
        parser.add_argument('document_code', type=str, required=False, nullable=False)
        args = parser.parse_args()
        
        storage_code = args['storage_code']
        document_code = args['document_code']     
        bind_contextvars(task="ExtractSegmentsFromStorageCodeAPI")
        start_time = time.time()
        logger.debug("extract_segments_from_storage_code_started", action="ExtractSegmentsFromStorageCodeAPI", storage_code=storage_code)

        try:    
            content = preprocess_document_from_storage_code(storage_code)        
            segments = extract_components(content=content, document_code=document_code)            
            logger.debug("extract_segments_from_storage_code_processing_success", action="ExtractSegmentsFromStorageCodeAPI", segment_count=len(segments))                

            duration = time.time() - start_time
            logger.info("extract_segments_from_storage_code_success", action="ExtractSegmentsFromStorageCodeAPI", **{"event.status": "success", "event.duration": duration})
            return make_response(data=segments, code=0, message="Success"), 200
        except Exception as e:
            duration = time.time() - start_time
            logger.error("extract_segments_from_storage_code_failed", action="ExtractSegmentsFromStorageCodeAPI", **{"event.status": "failure", "event.duration": duration, "error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return make_response(data=None, code=2000, message=str(e)), 500


class ExtractSegmentsFromContentAPI(Resource):
    """API for extracting segments from content"""
    
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('content', type=str, required=True, nullable=False)
        parser.add_argument('document_code', type=str, required=False, nullable=False)
        args = parser.parse_args()

        content = args['content']        
        document_code = args['document_code']        
        bind_contextvars(task="ExtractSegmentsFromContentAPI")
        start_time = time.time()
        logger.debug("extract_segments_from_content_started", action="ExtractSegmentsFromContentAPI")

        try:                        
            segments = extract_components(content=content, document_code=document_code)            
            logger.debug("extract_segments_from_content_processing_success", action="ExtractSegmentsFromContentAPI", segment_count=len(segments))
            
            duration = time.time() - start_time
            logger.info("extract_segments_from_content_success", action="ExtractSegmentsFromContentAPI", **{"event.status": "success", "event.duration": duration})
            return make_response(data=segments, code=0, message="Success"), 200
        except Exception as e:
            duration = time.time() - start_time
            logger.error("extract_segments_from_content_failed", action="ExtractSegmentsFromContentAPI", **{"event.status": "failure", "event.duration": duration, "error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return make_response(data=None, code=2000, message=str(e)), 500


class ExtractSegmentsFromFileAPI(Resource):
    """API for extracting segments from uploaded file"""
    
    def post(self):
        bind_contextvars(task="ExtractSegmentsFromFileAPI")
        start_time = time.time()
        logger.debug("extract_segments_from_file_started", action="ExtractSegmentsFromFileAPI")

        try:
            uploaded_file = request.files.get('file')
            if not uploaded_file:
                logger.error("extract_segments_from_file_failed", action="ExtractSegmentsFromFileAPI", **{"event.status": "failure", "error.code": "EXT", "error.message": "No file provided"})
                return make_response(data=[], code=0, message="No file provided"), 200
                
            logger.debug("extract_segments_from_file_processing_started", action="ExtractSegmentsFromFileAPI")
            with io.BytesIO(uploaded_file.read()) as file_stream:
                content = preprocess_document_from_stream(file_stream)
                
            segments = extract_components(content=content)
            logger.debug("extract_segments_from_file_processing_success", action="ExtractSegmentsFromFileAPI", segment_count=len(segments))
            
            duration = time.time() - start_time
            logger.info("extract_segments_from_file_success", action="ExtractSegmentsFromFileAPI", **{"event.status": "success", "event.duration": duration})
            return make_response(data=segments, code=0, message="Success"), 200
        except Exception as e:
            duration = time.time() - start_time
            logger.error("extract_segments_from_file_failed", action="ExtractSegmentsFromFileAPI", **{"event.status": "failure", "event.duration": duration, "error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return make_response(data=None, code=2000, message=str(e)), 500


# Register API resources
api.add_resource(ExtractSegmentsFromStorageCodeAPI, '/mirgate/extract_segments_from_storage_code')
api.add_resource(ExtractSegmentsFromContentAPI, '/mirgate/extract_segments_from_content')
api.add_resource(ExtractSegmentsFromFileAPI, '/mirgate/extract_segments_from_file')