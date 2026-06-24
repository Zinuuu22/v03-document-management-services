from core.common.mongo.client import get_mongo_client
import structlog
import os
import sys
import uuid
from datetime import datetime
from typing import Dict, Any
from flask_restful import Resource, reqparse
from flask import request
from pymongo import MongoClient
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from services.api import api
from services.api.utils import make_response, validate_id
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig         
from structlog.contextvars import bind_contextvars
import time
logger = structlog.get_logger()


client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
law_references_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_COLLECTION_NAME]
law_references_article_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_ARTICLE_COLLECTION_NAME]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]

# ---------------------------------------------------------------------
# 1️⃣ API: Lấy danh sách document theo doc_id và reference_type
# ---------------------------------------------------------------------
class EffectiveUpdateDocumentListAPI(Resource):
    def get(self) -> Dict[str, Any]:
        """
        Lấy danh sách document từ doc_id 
        Query params:
            - source_id: ID của doc_id của document       (law_references_collection)
        Response:
            - target_id: ID của document có relationship_type: AMEND, REPLACE
            - reference_type: loại relationship
            - doc_name: tên document
        """
        bind_contextvars(task="EffectiveUpdateDocumentListAPI")
        start_t = time.time()
        try:
            doc_id = request.args.get("doc_id")
            
            if not doc_id:
                logger.error("get_effective_update_document_list_failed", action="get", **{"error.code": "400-VAL", "error.message": "doc_id is required", "event.duration": time.time()-start_t, "event.status": "failure"}, doc_id=doc_id)
                return make_response(data=None, code="400", message="doc_id is required"), 400

            query = {
                "source_id": doc_id,
                "reference_type": {"$in": ["AMEND", "REPLACE"]}
            }
            refs = list(law_references_collection.find(query, {"_id": 0}))
            
            result = []
            for ref in refs:
                target_doc_id = ref.get("target_id")
                doc_name = ""
                if target_doc_id:
                    doc = law_documents_collection.find_one({"doc_id": target_doc_id})
                    if doc:
                        doc_name = doc.get("doc_title", "")
                
                result.append({
                    "target_id": target_doc_id,
                    "reference_type": ref.get("reference_type"),
                    "doc_name": doc_name
                })
            
            logger.info("get_effective_update_document_list_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(result))
            return make_response(data=result, code="200", message="Success"), 200

        except ValueError as ve:
            logger.error("get_effective_update_document_list_failed", action="get", **{"error.code": "400-VAL", "error.message": str(ve), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(data=None, code="400", message=str(ve)), 400
        except Exception as e:
            logger.error("get_effective_update_document_list_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code="500", message="Internal server error")
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500

# ---------------------------------------------------------------------
# 2️⃣ API: Lấy danh sách document theo doc_id và reference_type
# ---------------------------------------------------------------------
class EffectiveUpdateArticleListAPI(Resource):
    def get(self) -> Dict[str, Any]:
        """
        Lấy danh sách article, document từ article_id   (law_references_article_collection)
        Query params:
            - source_id: ID của article_id   
        Response:
            - target_id: ID của article
            - article_title: tên article
            - reference_type: loại relationship có low_case và include: bãi bỏ, thay thế, sửa đổi, bổ sung
            - doc_id: ID của document
            - doc_name: tên document
        """
        bind_contextvars(task="EffectiveUpdateArticleListAPI")
        start_t = time.time()
        try:
            article_id = request.args.get("article_id")
            
            if not article_id:
                logger.error("get_effective_update_article_list_failed", action="get", **{"error.code": "400-VAL", "error.message": "article_id is required", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code="400", message="article_id is required"), 400

            query = {
                "source_article_id": article_id,
            }
            
            # Fetch references
            refs = list(law_references_article_collection.find(query, {"_id": 0}))
            # Filter logic: reference_type lower case includes "bãi bỏ", "thay thế", "sửa đổi", "bổ sung"
            allowed_keywords = ["bãi bỏ", "thay thế", "sửa đổi", "bổ sung"]
            
            final_result = []
            for ref in refs:
                ref_type = ref.get("relationship_type", "")
                ref_type_lower = ref_type.lower()
                if any(keyword in ref_type_lower for keyword in allowed_keywords):
                    target_doc_id = ref.get("target_doc_id")
                    target_article_id = ref.get("target_article_id")
                    article_title = ""
                    doc_name = ""
                    doc_type = ""
                    doc_code = ""
                    doc_issue_date = ""
                    status = ""
                    expiry_date = ""
                    if target_article_id:
                        article = law_articles_collection.find_one({"article_id": target_article_id})
                        if article:
                            article_title = article.get("article_title", "")
                    if target_doc_id:
                        doc = law_documents_collection.find_one({"doc_id": target_doc_id})
                        art = law_articles_collection.find_one({"article_id": target_article_id})
                        if doc:
                            doc_name = doc.get("doc_title", "")
                            doc_type = doc.get("category_id", "")
                            doc_code = doc.get("doc_code", "")
                            doc_issue_date = doc.get("doc_issue_date", "")
                        if art:
                            status = art.get("effective_status_id", "")
                            expiry_date = art.get("article_expiry_date", "")
                        else:
                            status = doc.get("effective_status_id", "")
                            expiry_date = doc.get("doc_expiry_date", "")
                    final_result.append({
                        "article_id": target_article_id,
                        "article_title": article_title,
                        "reference_type": ref_type,
                        "doc_id": target_doc_id,
                        "doc_name": doc_name,
                        "doc_type": doc_type,
                        "doc_code": doc_code,
                        "doc_issue_date": doc_issue_date,
                        "status" : status,
                        "expiry_date" : expiry_date
                    })

            logger.info("get_effective_update_article_list_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(final_result))
            return make_response(data=final_result, code="200", message="Success"), 200

        except ValueError as ve:
            logger.error("get_effective_update_article_list_failed", action="get", **{"error.code": "400-VAL", "error.message": str(ve), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(data=None, code="400", message=str(ve)), 400
        except Exception as e:
            logger.error("get_effective_update_article_list_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code="500", message="Internal server error")
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500

# ---------------------------------------------------------------------
api.add_resource(EffectiveUpdateDocumentListAPI, '/effective-update/document/list')
api.add_resource(EffectiveUpdateArticleListAPI, '/effective-update/article/list')
