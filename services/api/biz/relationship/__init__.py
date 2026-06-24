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
law_reference_draft_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_DRAFT_COLLECTION_NAME]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]


# ---------------------------------------------------------------------
# 1️⃣ API: Lấy danh sách reference theo doc_id và reference_type
# ---------------------------------------------------------------------


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

            # Bổ sung thông tin văn bản đích (số hiệu/tên/cơ quan) để GUI hiển thị đúng theo
            # output extractor — bản ghi reference chỉ lưu target_id nên cần join sang law_documents.
            target_ids = [str(r["target_id"]) for r in refs if r.get("target_id")]
            doc_map = {
                str(d["doc_id"]): d
                for d in law_documents_collection.find(
                    {"doc_id": {"$in": target_ids}},
                    {"_id": 0, "doc_id": 1, "doc_code": 1, "doc_title": 1, "agency_ids": 1},
                )
            }

            # Khử trùng theo (target_id, reference_type): chống các bản ghi lặp do ghi đồng thời.
            seen = set()
            enriched = []
            for r in refs:
                tid = str(r.get("target_id") or "")
                key = (tid, r.get("reference_type"))
                if key in seen:
                    continue
                seen.add(key)
                doc = doc_map.get(tid)
                if doc:
                    r["code"] = tid
                    r["document_code"] = doc.get("doc_code", "")
                    r["name"] = doc.get("doc_title", "")
                    r["agency"] = doc.get("agency_ids", "")
                enriched.append(r)

            logger.info("get_law_reference_list_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(enriched), raw_count=len(refs))
            return make_response(data=enriched, code="200", message="Success"), 200

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
# 1️⃣.b API: Lấy danh sách reference draft (quan hệ chưa map được target doc_id)
# ---------------------------------------------------------------------
class LawReferenceDraftListAPI(Resource):
    def get(self) -> Dict[str, Any]:
        """
        Lấy danh sách reference draft theo doc_id và reference_type.
        Đây là các quan hệ trích xuất được nhưng chưa resolve được sang văn bản
        trong DB (chỉ có target_doc_title + target_doc_code).
        Gọi song song với /law-reference/list.
        Query params:
            - doc_id: ID của document đầu vào (source_id)
            - reference_type: loại tham chiếu (AMENDED, BASIS, DETAIL, REPLACED, ...)
        """
        bind_contextvars(task="LawReferenceDraftListAPI")
        start_t = time.time()
        try:
            doc_id = request.args.get("doc_id")
            reference_type = request.args.get("reference_type")
            logger.debug("get_law_reference_draft_list", action="get", **{"event.duration": time.time()-start_t}, doc_id=doc_id, reference_type=reference_type)

            query = {}
            if doc_id:
                query["source_id"] = doc_id
            if reference_type:
                query["reference_type"] = reference_type
            refs = list(law_reference_draft_collection.find(query, {"_id": 0}))
            if not refs:
                logger.error("get_law_reference_draft_list_failed", action="get", **{"error.code": "404-NOTFOUND", "error.message": "Draft references not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code="404", message="Draft references not found"), 404

            # Khử trùng theo (target_doc_title, reference_type) và thêm các field hiển thị đồng nhất
            # với /law-reference/list (code rỗng vì chưa map được target doc_id).
            seen = set()
            deduped = []
            for r in refs:
                key = ((r.get("target_doc_title") or "").strip(), r.get("reference_type"))
                if key in seen:
                    continue
                seen.add(key)
                r["code"] = ""
                r["document_code"] = r.get("target_doc_code", "")
                r["name"] = r.get("target_doc_title", "")
                deduped.append(r)

            logger.info("get_law_reference_draft_list_success", action="get", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(deduped), raw_count=len(refs))
            return make_response(data=deduped, code="200", message="Success"), 200

        except ValueError as ve:
            logger.error("get_law_reference_draft_list_failed", action="get", **{"error.code": "400-VAL", "error.message": str(ve), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(data=None, code="400", message=str(ve)), 400
        except Exception as e:
            logger.error("get_law_reference_draft_list_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code="500", message="Internal server error")
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# ---------------------------------------------------------------------
# 1️⃣.c API: Thêm mới reference draft
# ---------------------------------------------------------------------
class LawReferenceDraftAddAPI(Resource):
    def post(self) -> Dict[str, Any]:
        """
        Thêm mới một bản ghi reference draft (quan hệ chưa resolve được target doc_id).
        Body JSON:
        {
            "source_id": "635289",
            "source_type": "DOCUMENT",
            "target_doc_title": "Nghị định số 10/2023/NĐ-CP",
            "target_doc_code": "10/2023/NĐ-CP",
            "reference_type": "AMENDED",
            "reference_status": "Còn hiệu lực",
            "last_modified_by": "admin"
        }
        """
        bind_contextvars(task="LawReferenceDraftAddAPI")
        start_t = time.time()
        try:
            body = request.get_json() or {}

            # Kiểm tra source_id tồn tại trong document collection
            if not law_documents_collection.find_one({"doc_id": body.get("source_id")}):
                logger.error("add_law_reference_draft_failed", action="post", **{"error.code": "404-NOTFOUND", "error.message": "Source document not found", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code="404", message="Source document not found"), 404

            required_fields = ["source_id", "source_type", "reference_type"]
            missing_fields = [field for field in required_fields if field not in body]
            if missing_fields:
                logger.error("add_law_reference_draft_failed", action="post", **{"error.code": "400-VAL", "error.message": f"Missing required fields: {', '.join(missing_fields)}", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    data=None, code="400", message=f"Missing required fields: {', '.join(missing_fields)}"
                ), 400

            draft_doc = {
                "reference_draft_id": str(uuid.uuid4()),
                "source_id": validate_id(body["source_id"]),
                "source_type": body["source_type"],
                "target_doc_title": body.get("target_doc_title", ""),
                "target_doc_code": body.get("target_doc_code", ""),
                "reference_type": body["reference_type"],
                "reference_status": body.get("reference_status", "Còn hiệu lực"),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_by": body.get("last_modified_by", "")
            }

            result = law_reference_draft_collection.insert_one(draft_doc)
            if not result.inserted_id:
                logger.error("add_law_reference_draft_failed", action="post", **{"error.code": "500-DB", "error.message": "Failed to insert reference draft", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code="500", message="Failed to insert reference draft"), 500

            logger.info("add_law_reference_draft_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, reference_draft_id=draft_doc["reference_draft_id"])
            return make_response(data=draft_doc, code="201", message="Reference draft added successfully"), 201

        except ValueError as ve:
            logger.error("add_law_reference_draft_failed", action="post", **{"error.code": "400-VAL", "error.message": str(ve), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(data=None, code="400", message=str(ve)), 400
        except Exception as e:
            logger.error("add_law_reference_draft_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code="500", message="Internal server error")
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# ---------------------------------------------------------------------
# 1️⃣.d API: Xóa reference draft theo reference_draft_id
# ---------------------------------------------------------------------
class LawReferenceDraftDeleteAPI(Resource):
    def delete(self, reference_draft_id: str) -> Dict[str, Any]:
        """
        Xóa reference draft theo reference_draft_id
        """
        bind_contextvars(task="LawReferenceDraftDeleteAPI")
        start_t = time.time()
        try:
            draft_id = validate_id(reference_draft_id)

            result = law_reference_draft_collection.delete_one({"reference_draft_id": draft_id})

            if result.deleted_count == 0:
                logger.error("delete_law_reference_draft_failed", action="delete", **{"error.code": "404-NOTFOUND", "error.message": "Reference draft not found", "event.duration": time.time()-start_t, "event.status": "failure"}, reference_draft_id=reference_draft_id)
                return make_response(data=None, code="404", message="Reference draft not found"), 404

            logger.info("delete_law_reference_draft_success", action="delete", **{"event.duration": time.time()-start_t, "event.status": "success"}, reference_draft_id=reference_draft_id)
            return make_response(data=None, code="200", message="Reference draft deleted successfully"), 200

        except ValueError as ve:
            logger.error("delete_law_reference_draft_failed", action="delete", **{"error.code": "400-VAL", "error.message": str(ve), "event.duration": time.time()-start_t, "event.status": "failure"})
            return make_response(data=None, code="400", message=str(ve)), 400
        except Exception as e:
            logger.error("delete_law_reference_draft_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
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
            required_fields = ["source_id", "source_type", "target_id", "target_type", "reference_type"]
            missing_fields = []
            for field in required_fields:
                if field not in body:
                    missing_fields.append(field)
            if missing_fields:
                logger.error("add_law_reference_failed", action="post", **{"error.code": "400-VAL", "error.message": f"Missing required fields: {', '.join(missing_fields)}", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(
                    data=None, code="400", message=f"Missing required fields: {', '.join(missing_fields)}"
                ), 400
            
            ref_doc = {
                "reference_id": str(uuid.uuid4()),
                "source_id": validate_id(body["source_id"]),
                "source_type": body["source_type"],
                "target_id": validate_id(body["target_id"]),
                "target_type": body["target_type"],
                "reference_status": body.get("reference_status", "Còn hiệu lực"),
                "reference_type": body["reference_type"],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_by": body.get("last_modified_by", "")
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
api.add_resource(LawReferenceDraftListAPI, '/law-reference/draft/list')
api.add_resource(LawReferenceDraftAddAPI, '/law-reference/draft/add')
api.add_resource(LawReferenceDraftDeleteAPI, '/law-reference/draft/delete/<string:reference_draft_id>')
api.add_resource(LawReferenceAddAPI, '/law-reference/add')
api.add_resource(LawReferenceUpdateAPI, '/law-reference/update/<string:reference_id>')
api.add_resource(LawReferenceDeleteAPI, '/law-reference/delete/<string:reference_id>')

