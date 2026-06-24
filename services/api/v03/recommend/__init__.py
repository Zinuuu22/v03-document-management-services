import os
import sys
from typing import List, Dict, Any, Optional
from flask_restful import Resource, reqparse
import structlog
from structlog.contextvars import bind_contextvars
import time
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from services.api import api
from services.api.utils import make_response
from core.v03.recommender import get_related_documents_from_db, get_related_documents_from_upload, search_document_from_ids, get_tree_by_keywords
class RecommendDocumentsAPI(Resource):
    """API for recommend API."""

    def post(self) -> Dict[str, List[str]]:
        parser = reqparse.RequestParser()   
        parser.add_argument("doc_id", type=str, required=False, nullable=False, location="json")
        parser.add_argument("types", type=str, required=False, nullable=False, location="json")
        parser.add_argument("storage_code", type=str, required=False, nullable=False, location="json")
                
        args = parser.parse_args()
        doc_id = args.get("doc_id", None)
        recommend_types = args.get("types", None)
        storage_code = args.get("storage_code", None)

        bind_contextvars(task="RecommendDocumentsAPI")
        start_time = time.time()
        logger.debug("recommend_documents_started", action="RecommendDocumentsAPI", doc_id=doc_id, recommend_types=recommend_types, storage_code=storage_code)

        if storage_code is None and doc_id is None:
            return make_response(data=None, code=2000, message="storage_code or doc_id is required"), 400        
        
        try:
            if doc_id is not None:
                related_docs, error = get_related_documents_from_db(doc_id=doc_id, recommend_types=recommend_types)
            else:
                related_docs, error = get_related_documents_from_upload(storage_code=storage_code, recommend_types=recommend_types)
            if error:
                return make_response(data=None, code=2000, message=error), 400            
            logger.debug("recommend_documents_related_found", action="RecommendDocumentsAPI", count=len(related_docs))

            for key, value in related_docs.items():
                if isinstance(value, set):
                    related_docs[key] = list(value)
                # Tìm kiếm văn bản từ elastic
                doc_ids = value
                related_docs[key] = search_document_from_ids(doc_ids)
            logger.debug("recommend_documents_search_success", action="RecommendDocumentsAPI")

            duration = time.time() - start_time
            logger.info("recommend_documents_success", action="RecommendDocumentsAPI", **{"event.status": "success", "event.duration": duration})

            return make_response(data=related_docs, code=0, message="Success"), 200
        except Exception as e:
            duration = time.time() - start_time
            logger.error("recommend_documents_failed", action="RecommendDocumentsAPI", **{"event.status": "failure", "event.duration": duration, "error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return make_response(data=None, code=2000, message=str(e)), 500


class GetTreeByKeywordsAPI(Resource):
    """API for get tree by keywords."""

    def post(self) -> Dict[str, List[str]]:
        parser = reqparse.RequestParser()   
        parser.add_argument("keywords", type=list[str], required=False, nullable=False, location="json")
        parser.add_argument("valid_tree_ids", type=list[str], required=False, nullable=False, location="json")
                
        args = parser.parse_args()
        keywords = args.get("keywords", None)
        valid_tree_ids = args.get("valid_tree_ids", None)

        bind_contextvars(task="GetTreeByKeywordsAPI")
        start_time = time.time()
        logger.debug("get_tree_by_keywords_started", action="GetTreeByKeywordsAPI", keywords=keywords, valid_tree_ids=valid_tree_ids)

        if keywords is None:
            return make_response(data=None, code=2000, message="keywords is required"), 400        
        
        try:
            tree_components = get_tree_by_keywords(keywords=keywords, valid_tree_ids=valid_tree_ids)
            duration = time.time() - start_time
            logger.info("get_tree_by_keywords_success", action="GetTreeByKeywordsAPI", **{"event.status": "success", "event.duration": duration})
            return make_response(data=tree_components, code=0, message="Success"), 200
        except Exception as e:
            duration = time.time() - start_time
            logger.error("get_tree_by_keywords_failed", action="GetTreeByKeywordsAPI", **{"event.status": "failure", "event.duration": duration, "error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return make_response(data=None, code=2000, message=str(e)), 500


# Register API resources
api.add_resource(RecommendDocumentsAPI, "/recommender/related_documents")
api.add_resource(GetTreeByKeywordsAPI, "/recommender/get_tree_by_keywords")