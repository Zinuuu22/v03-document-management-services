from core.common.mongo.client import get_mongo_client
import structlog
from structlog.contextvars import bind_contextvars
import time
import sys
from typing_extensions import dataclass_transform
import uuid
import os
from flask_restful import Resource, reqparse
from bson import ObjectId
from pymongo import MongoClient
from datetime import datetime
from typing import Dict, Any
from pymongo.errors import PyMongoError
from flask import request
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)
from services.api.utils.response import make_response
from services.api import api
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.v03.tree_classifier import predict, get_summary
from services.api.biz.tree_classifier.utils import send_message_to_kafka
logger = structlog.get_logger()

# Connect MongoDB
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
document_industry_sector_collection = db[MongoDBCollectionConfig.LAW_INDUSTRY_SECTORS_COLLECTION_NAME]
training_process_collection = db[MongoDBCollectionConfig.BIZ_TRAINING_PROCESS_COLLECTION_NAME]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
subject_tree_collection = db[MongoDBCollectionConfig.LAW_TREE_COMPONENT_COLLECTION_NAME]


class TrainingTreeAPI(Resource):
    def post(self):
        """
        Huấn luyện mô hình phân loại theo cây chuyên đề.
        """
        bind_contextvars(task="TrainingTreeAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument("train_id", type=str, required=True, help="train_id là bắt buộc")
        args = parser.parse_args()
        train_id = args["train_id"]
        
        # try:
        train_process = training_process_collection.find_one({"train_id": train_id})    
        if not train_process:
            return make_response(code=400, message="Tiến trình training chưa được khởi tạo", data=None), 400            
        model_id = str(uuid.uuid4())                        
        # Gửi message xuống kafka service để huấn luyện mô hình
        logger.info("training_tree_started", action="post", tree_id=train_process['tree_id'], model_id=model_id, **{"event.status": "success", "event.duration": time.time() - start_t})            
        
        data = {
                    "request_id": train_id,
                    "train_id": train_id,                        
                    "tree_id": train_process['tree_id'],
                    "train_name": train_process['train_name'],
                    "model_id": model_id,
                    "config": train_process['config'],
                    "dataset_ratio": train_process['dataset_ratio']
                }                
        status = send_message_to_kafka(data)            
        if status:
            return make_response(code=200, 
                                message=f"Huấn luyện thành công cây {train_process['tree_id']}", 
                                data=data), 200
        else:
            return make_response(code=500, 
                                message=f"Lỗi huấn luyện mô hình", 
                                data=None), 500


class PredictTreeAPI(Resource):
    def post(self):
        """
        Dự đoán chuyên đề cho văn bản đầu vào.
        """
        bind_contextvars(task="PredictTreeAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument("tree_id", type=str, required=True, help="ID của cây chuyên đề là bắt buộc")
        parser.add_argument("doc_id", type=str, required=True, help="Văn bản cần dự đoán là bắt buộc")
        args = parser.parse_args()

        tree_id = args["tree_id"]
        doc_id = args["doc_id"]

        try:
            model = training_process_collection.find_one(
                                                {"tree_id": tree_id, "status": "COMPLETED", "use_status": "ACTIVE"},
                                                sort=[("created_at", -1)]
                                            )
            if not model:
                logger.error("predict_tree_failed", action="post", tree_id=tree_id, **{"error.code": "404-NOTFOUND", "error.message": "Không tồn tại model tương ứng với cây chuyên đề", "event.status": "failure", "event.duration": time.time() - start_t})
                return make_response(code=404, message="Không tồn tại model tương ứng với cây chuyên đề", data=None), 404
            model_id = model.get("model_id")        
            
            # Step 1: Load model            
            db_model_path = model.get("model_path")
            local_model_dir = os.path.join(os.path.dirname(__file__), "models")
            local_model_path = os.path.join(local_model_dir, "model.bin")
            if os.path.exists(local_model_path):
                model_path = local_model_path
            else:
                model_path = db_model_path

            # Step 2: Load document
            document = law_documents_collection.find_one({"doc_id": doc_id})
            if not document:
                logger.error("predict_tree_failed", action="post", doc_id=doc_id, **{"error.code": "404-NOTFOUND", "error.message": f"Không tìm thấy văn bản với doc_id = {doc_id}", "event.status": "failure", "event.duration": time.time() - start_t})
                return make_response(code=404, message=f"Không tìm thấy văn bản với doc_id = {doc_id}", data=None), 404
            
            _, summary = get_summary(doc_id)

            # Step 3: Inference
            label, prob = predict(model_path, summary)

            # Step 4: Get subject_tree
            subject = subject_tree_collection.find_one({"subject_id": label})
            if not subject:
                logger.error("predict_tree_failed", action="post", label=label, **{"error.code": "404-NOTFOUND", "error.message": "Subject tree không tồn tại", "event.status": "failure", "event.duration": time.time() - start_t})
                return make_response(code=404, message="Subject tree không tồn tại", data=None), 404
            
            subject_id = subject.get("subject_id")
            subject_parent_id = subject.get("subject_parent_id")

            subject_parent = subject_tree_collection.find_one({"subject_id": subject_parent_id})
            if not subject_parent:
                logger.error("predict_tree_failed", action="post", subject_parent_id=subject_parent_id, **{"error.code": "404-NOTFOUND", "error.message": "Subject parent không tồn tại", "event.status": "failure", "event.duration": time.time() - start_t})
                return make_response(code=404, message="Subject parent không tồn tại", data=None), 404

            response = [{
                "confidence": round(prob, 4) * 100,
                "model_id": model_id,
                "subject_id": subject_id,
                "subject_name": subject.get("subject_name"),
                "subject_parent_id": subject_parent_id,
                "subject_parent_name": subject_parent.get("subject_name")
            }]
            
            logger.info("predict_tree_success", action="post", model_id=model_id, doc_id=doc_id, subject_id=subject_id, prob=prob, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(code=200, message="Dự đoán thành công", data=response), 200

        except Exception as e:
            logger.error("predict_tree_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(code=500, message=f"Lỗi dự đoán chuyên đề: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class AddTrainingProcessAPI(Resource):
    def post(self):
        """
        Thêm mới một tiến trình huấn luyện (manual entry).
        """
        bind_contextvars(task="AddTrainingProcessAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument("train_name", type=str, required=True, help="train_name là bắt buộc")
        parser.add_argument("tree_id", type=str, required=True, help="tree_id là bắt buộc")
        parser.add_argument("model_path", type=str, required=False, default="")
        parser.add_argument("description", type=str, required=False, default="")
        parser.add_argument("config", type=dict, required=False, default={})
        parser.add_argument("created_by", type=str, required=False, default="ROOT") 
        parser.add_argument("dataset_ratio", type=float, required=False, default=0.2)
        args = parser.parse_args()

        try:
            train_id = str(uuid.uuid4())
            record = {
                "train_id": train_id,
                "train_name": args["train_name"],
                "tree_id": args["tree_id"],
                "model_id": train_id,
                "model_path": "",
                "metrics": None,
                "description": args["description"],
                "status": "INIT",
                "config": args["config"],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "created_by": args["created_by"],
                "last_modified_by": args["created_by"],
                "training_duration": None,
                "use_status": "INACTIVE",
                "dataset_ratio": args.get("dataset_ratio", 0.2)
            }
            training_process_collection.insert_one(record)
            logger.info("add_training_process_success", action="post", train_id=train_id, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(code=200, message="Thêm tiến trình huấn luyện thành công", data=record), 200
        except Exception as e:
            logger.error("add_training_process_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(code=500, message=f"Lỗi thêm tiến trình huấn luyện: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class UpdateTrainingProcessAPI(Resource):
    def post(self, train_id):
        """
        Cập nhật thông tin tiến trình huấn luyện theo train_id.
        """
        bind_contextvars(task="UpdateTrainingProcessAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument("train_name", type=str, required=False)
        parser.add_argument("tree_id", type=str, required=False)
        parser.add_argument("model_path", type=str, required=False)
        parser.add_argument("description", type=str, required=False)
        parser.add_argument("use_status", type=str, required=False)
        parser.add_argument("last_modified_by", type=str, required=False, default="ROOT")
        parser.add_argument("config", type=dict, required=False, default={})
        parser.add_argument("dataset_ratio", type=float, required=False, default=0.2)
        args = parser.parse_args()

        try:
            update_fields = {k: v for k, v in args.items() if v is not None}
            update_fields["last_modified_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            result = training_process_collection.update_one(
                {"train_id": train_id},
                {"$set": update_fields}
            )

            if result.matched_count == 0:
                logger.error("update_training_process_failed", action="post", train_id=train_id, **{"error.code": "404-NOTFOUND", "error.message": "Không tìm thấy tiến trình huấn luyện", "event.status": "failure", "event.duration": time.time() - start_t})
                return make_response(code=404, message="Không tìm thấy tiến trình huấn luyện", data=None), 404

            logger.info("update_training_process_success", action="post", train_id=train_id, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(code=200, message="Cập nhật thành công", data={"train_id": train_id}), 200
        except Exception as e:
            logger.error("update_training_process_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(code=500, message=f"Lỗi cập nhật tiến trình huấn luyện: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DeleteTrainingProcessAPI(Resource):
    def delete(self, train_id):
        """
        Xóa tiến trình huấn luyện theo train_id.
        """
        bind_contextvars(task="DeleteTrainingProcessAPI")
        start_t = time.time()
        try:
            result = training_process_collection.delete_one({"train_id": train_id})
            if result.deleted_count == 0:
                logger.error("delete_training_process_failed", action="delete", train_id=train_id, **{"error.code": "404-NOTFOUND", "error.message": "Không tìm thấy tiến trình huấn luyện để xóa", "event.status": "failure", "event.duration": time.time() - start_t})
                return make_response(code=404, message="Không tìm thấy tiến trình huấn luyện để xóa", data=None), 404

            logger.info("delete_training_process_success", action="delete", train_id=train_id, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(code=200, message="Xóa tiến trình huấn luyện thành công", data={"train_id": train_id}), 200
        except Exception as e:
            logger.error("delete_training_process_failed", action="delete", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(code=500, message=f"Lỗi xóa tiến trình huấn luyện: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class ListTrainingProcessAPI(Resource):
    def get(self):
        """
        Lấy danh sách tiến trình huấn luyện (có phân trang và bộ lọc).
        Query params hỗ trợ:
        - status: lọc theo trạng thái tiến trình
        - page: số trang (mặc định = 1)
        - limit: số bản ghi mỗi trang (mặc định = 10)
        """
        bind_contextvars(task="ListTrainingProcessAPI")
        start_t = time.time()
        # Lấy tham số từ query string
        status = request.args.get("status")
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))

        # Đảm bảo giới hạn hợp lý
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 10

        # Tạo điều kiện truy vấn
        query = {}
        if status:
            query["status"] = status
        
        try:
            # Đếm tổng số bản ghi
            total_records = training_process_collection.count_documents(query)
            total_pages = (total_records + limit - 1) // limit  # làm tròn lên

            # Tính toán skip và lấy dữ liệu theo phân trang
            skip = (page - 1) * limit
            records = list(
                training_process_collection.find(query, {"_id": 0})
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )

            # Trả kết quả có metadata
            response_data = {
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total_records": total_records,
                    "total_pages": total_pages,
                },
                "records": records
            }

            logger.info("list_training_process_success", action="get", page=page, limit=limit, total_records=total_records, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(code=200, message="Lấy danh sách tiến trình thành công", data=response_data), 200

        except Exception as e:
            logger.error("list_training_process_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(code=500, message=f"Lỗi lấy danh sách tiến trình: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class GetTrainingProcessAPI(Resource):
    def get(self, train_id):
        """
        Lấy chi tiết một tiến trình huấn luyện theo train_id.
        """
        bind_contextvars(task="GetTrainingProcessAPI")
        start_t = time.time()
        try:
            record = training_process_collection.find_one({"train_id": train_id}, {"_id": 0})
            if not record:
                logger.error("get_training_process_failed", action="get", train_id=train_id, **{"error.code": "404-NOTFOUND", "error.message": "Không tìm thấy tiến trình huấn luyện", "event.status": "failure", "event.duration": time.time() - start_t})
                return make_response(code=404, message="Không tìm thấy tiến trình huấn luyện", data=None), 404

            logger.info("get_training_process_success", action="get", train_id=train_id, **{"event.status": "success", "event.duration": time.time() - start_t})
            return make_response(code=200, message="Lấy chi tiết tiến trình thành công", data=record), 200
        except Exception as e:
            logger.error("get_training_process_failed", action="get", **{"error.code": "500-SYS", "error.message": str(e), "event.status": "failure", "event.duration": time.time() - start_t}, exc_info=True)
            response = make_response(code=500, message=f"Lỗi lấy chi tiết tiến trình: {str(e)}", data=None)
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500



api.add_resource(TrainingTreeAPI, '/tree/training/start')
api.add_resource(PredictTreeAPI, '/tree/training/classify')

api.add_resource(AddTrainingProcessAPI, '/tree/training/add')
api.add_resource(UpdateTrainingProcessAPI, '/tree/training/update/<string:train_id>')
api.add_resource(DeleteTrainingProcessAPI, '/tree/training/delete/<string:train_id>')
api.add_resource(ListTrainingProcessAPI, '/tree/training/list')
api.add_resource(GetTrainingProcessAPI, '/tree/training/detail/<string:train_id>')
