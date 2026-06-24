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

effective_status_map = {
    "Không xác định": "b04750de-31f5-4266-b5c7-ac56c2bac946",
    "Hết hiệu lực": "a2e5eb7f-140b-43e9-9a9e-0b351466ae05",
    "Còn hiệu lực": "3969bc0a-a285-4a6d-9865-5b549cf88d20"
}
unknown_effective_status_id = "b04750de-31f5-4266-b5c7-ac56c2bac946"


client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
law_references_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_COLLECTION_NAME]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]

# ---------------------------------------------------------------------
# 1️⃣ API: Lấy danh sách reference theo doc_id và reference_type
# ---------------------------------------------------------------------
class LawReferenceListAPI(Resource):
    def get(self) -> Dict[str, Any]:
        """
        Lấy danh sách reference theo doc_id và reference_type
        Query params:
            - doc_id: ID của document
            - reference_type: loại tham chiếu (VD: AMENDED, REPEALED, ...)
        """
        bind_contextvars(task="LawReferenceListAPI")
        start_t = time.time()
        try:
            doc_id = request.args.get("doc_id")
            reference_type = request.args.get("reference_type")
            logger.debug("get_law_reference_list", action="get", **{"event.duration": time.time()-start_t}, doc_id=doc_id, reference_type=reference_type)

            query = {}
            if doc_id:
                query["source_id"] = doc_id
            if reference_type:
                query["reference_type"] = reference_type
            refs = list(law_references_collection.find(query, {"_id": 0}))
            if not refs:
                logger.error("get_law_reference_list_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": "References not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code="404", message="References not found"), 404
            
            logger.info("get_law_reference_list_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(refs))
            return make_response(data=refs, code="200", message="Success"), 200

        except ValueError as ve:
            logger.error("get_law_reference_list_failed", action="get", **{"error.code": "400-VAL", "error.message": str(ve), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(data=None, code="400", message=str(ve)), 400
        except Exception as e:
            logger.error("get_law_reference_list_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code="500", message="Internal server error")
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500



# ---------------------------------------------------------------------
# 2️⃣ API: Thêm mới reference
# ---------------------------------------------------------------------
class LawReferenceAddAPI(Resource):
    def post(self) -> Dict[str, Any]:
        """
        Thêm mới một bản ghi reference
        Body JSON:
        {
            "source_id": "635289",
            "source_type": "DOCUMENT",
            "target_id": "524363",
            "target_type": "DOCUMENT",
            "reference_type": "AMENDED",
            "reference_status": "Còn hiệu lực",
            "last_modified_by": "admin"
        }
        """
        bind_contextvars(task="LawReferenceAddAPI")
        start_t = time.time()
        try:
            body = request.get_json() or {}
            # Check exist source_id or target_id in document collection
            if not law_documents_collection.find_one({"doc_id": body.get("source_id")}):
                logger.error("add_law_reference_failed", action="post", **{"error.code": "404-NOTFOUND", "error.message": "Source document not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code="404", message="Source document not found"), 404
            if not law_documents_collection.find_one({"doc_id": body.get("target_id")}):
                logger.error("add_law_reference_failed", action="post", **{"error.code": "404-NOTFOUND", "error.message": "Target document not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code="404", message="Target document not found"), 404
            required_fields = ["source_id", "target_id", "reference_type"]
            missing_fields = []
            for field in required_fields:
                if field not in body:
                    missing_fields.append(field)
            if missing_fields:
                logger.error("add_law_reference_failed", action="post", **{"error.code": "400-VAL", "error.message": f"Missing required fields: {', '.join(missing_fields)}", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    data=None, code="400", message=f"Missing required fields: {', '.join(missing_fields)}"
                ), 400
            
            # Translate reference_status to effective_status_id
            reference_status_name = body.get("reference_status", "Còn hiệu lực").strip()
            effective_status_id = effective_status_map.get(reference_status_name, unknown_effective_status_id)
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_user = body.get("last_modified_by", "system")
            
            ref_doc = {
                "reference_id": str(uuid.uuid4()),
                "source_id": validate_id(body["source_id"]),
                "target_id": validate_id(body["target_id"]),
                "effective_status_id": effective_status_id,
                "reference_type": body["reference_type"],
                "created_at": current_time,
                "created_by": current_user,
                "last_modified_at": current_time,
                "last_modified_by": current_user
            }

            result = law_references_collection.insert_one(ref_doc)
            if not result.inserted_id:
                logger.error("add_law_reference_failed", action="post", **{"error.code": "500-DB", "error.message": "Failed to insert reference", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code="500", message="Failed to insert reference"), 500

            logger.info("add_law_reference_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, reference_id=ref_doc["reference_id"])
            return make_response(data=ref_doc, code="201", message="Reference added successfully"), 201

        except ValueError as ve:
            logger.error("add_law_reference_failed", action="post", **{"error.code": "400-VAL", "error.message": str(ve), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(data=None, code="400", message=str(ve)), 400
        except Exception as e:
            logger.error("add_law_reference_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code="500", message="Internal server error")
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# ---------------------------------------------------------------------
# 3️⃣ API: Cập nhật reference theo reference_id
# ---------------------------------------------------------------------
class LawReferenceUpdateAPI(Resource):
    def post(self, reference_id: str) -> Dict[str, Any]:
        """
        Cập nhật thông tin reference theo reference_id
        Body JSON chứa các trường cần cập nhật
        """
        bind_contextvars(task="LawReferenceUpdateAPI")
        start_t = time.time()
        try:
            ref_id = validate_id(reference_id)
            body = request.get_json() or {}

            if not body:
                logger.error("update_law_reference_failed", action="post", **{"error.code": "400-VAL", "error.message": "Empty update body", "event.duration": time.time()-start_t, "event.status": "failure"}, reference_id=reference_id)
                return make_response(data=None, code="400", message="Empty update body"), 400

            if "reference_status" in body:
                reference_status_name = body.pop("reference_status").strip()
                body["effective_status_id"] = effective_status_map.get(reference_status_name, unknown_effective_status_id)
            
            # Xoá trường deprecated (nếu có)
            body.pop("source_type", None)
            body.pop("target_type", None)
            
            body["last_modified_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            result = law_references_collection.update_one(
                {"reference_id": ref_id},
                {"$set": body}
            )

            if result.matched_count == 0:
                logger.error("update_law_reference_failed", action="post", **{"error.code": "404-NOTFOUND", "error.message": "Reference not found", "event.duration": time.time()-start_t, "event.status": "failure"}, reference_id=reference_id)
                return make_response(data=None, code="404", message="Reference not found"), 404

            logger.info("update_law_reference_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, reference_id=reference_id)
            return make_response(data=None, code="200", message="Reference updated successfully"), 200

        except ValueError as ve:
            logger.error("update_law_reference_failed", action="post", **{"error.code": "400-VAL", "error.message": str(ve), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(data=None, code="400", message=str(ve)), 400
        except Exception as e:
            logger.error("update_law_reference_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code="500", message="Internal server error")
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# ---------------------------------------------------------------------
# 4️⃣ API: Xóa reference theo reference_id
# ---------------------------------------------------------------------
class LawReferenceDeleteAPI(Resource):
    def delete(self, reference_id: str) -> Dict[str, Any]:
        """
        Xóa reference theo reference_id
        """
        bind_contextvars(task="LawReferenceDeleteAPI")
        start_t = time.time()
        try:
            ref_id = validate_id(reference_id)

            result = law_references_collection.delete_one({"reference_id": ref_id})

            if result.deleted_count == 0:
                logger.error("delete_law_reference_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": "Reference not found", "event.duration": time.time()-start_t, "event.status": "failure"}, reference_id=reference_id)
                return make_response(data=None, code="404", message="Reference not found"), 404

            logger.info("delete_law_reference_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"}, reference_id=reference_id)
            return make_response(data=None, code="200", message="Reference deleted successfully"), 200

        except ValueError as ve:
            logger.error("delete_law_reference_failed", action="delete", **{"error.code": "400-VAL", "error.message": str(ve), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(data=None, code="400", message=str(ve)), 400
        except Exception as e:
            logger.error("delete_law_reference_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code="500", message="Internal server error")
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500

# ---------------------------------------------------------------------
# Register API routes
# ---------------------------------------------------------------------
api.add_resource(LawReferenceListAPI, '/law-reference/list')
api.add_resource(LawReferenceAddAPI, '/law-reference/add')
api.add_resource(LawReferenceUpdateAPI, '/law-reference/update/<string:reference_id>')
api.add_resource(LawReferenceDeleteAPI, '/law-reference/delete/<string:reference_id>')

