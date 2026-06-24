from core.common.mongo.client import get_mongo_client
import structlog
import sys
import os
import json
import uuid
from flask_restful import Resource, reqparse
from datetime import datetime
from flask import Response, request
from typing import Dict, Any
from pymongo.errors import PyMongoError
from werkzeug.utils import secure_filename
from pyvi import ViUtils

# Set up project root and append to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from pymongo import MongoClient
from constants import ImportTreeConfig, MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from services.api import api
from services.api.utils import send_kafka_message, make_response
from core.v03.tree_processor.processor import LawTreeManager
logger = structlog.get_logger()

# Initialize LawTreeManager
law_tree_manager = LawTreeManager()

# MongoDB connection for IndexDocumentTreeStaticAPI
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
law_tree_collection = db[MongoDBCollectionConfig.LAW_TREE_COLLECTION_NAME]
law_tree_component_collection = db[MongoDBCollectionConfig.LAW_TREE_COMPONENT_COLLECTION_NAME]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]


def vi_sort_key(text):
    text = text.lower()
    text = ViUtils.remove_accents(text)
    return text

class CreateSubjectTreeAPI(Resource):
    """API for creating a new subject tree, parent subject, or child subject."""

    def post(self) -> Dict[str, Any]:
        """Handle POST request to create a subject tree or subject.

        Returns:
            Response with created object details or error message.
        """
        structlog.contextvars.bind_contextvars(task="CreateSubjectTreeAPI")
        start_time = datetime.now()
        parser = reqparse.RequestParser()
        parser.add_argument("name", type=str, required=True, nullable=False, location="json")
        parser.add_argument("parentCode", type=str, nullable=True, location="json")
        parser.add_argument("filterType", type=str, nullable=True, location="json", default="CHILD")
        parser.add_argument("keywordCodes", type=list, nullable=True, location="json")
        parser.add_argument("documentCategoryCodes", type=list, nullable=True, location="json")
        parser.add_argument("issuedLevelCodes", type=list, nullable=True, location="json")
        parser.add_argument("industrySectorCodes", type=list, nullable=True, location="json")
        parser.add_argument("agencyIssuedCodes", type=list, nullable=True, location="json")
        parser.add_argument("decreeIssuedCodes", type=list, nullable=True, location="json")
        parser.add_argument("decreeIssuedFrom", type=str, nullable=True, location="json")
        parser.add_argument("decreeIssuedTo", type=str, nullable=True, location="json")
        parser.add_argument("dateExpiredFrom", type=str, nullable=True, location="json")
        parser.add_argument("dateExpiredTo", type=str, nullable=True, location="json")
        parser.add_argument("decreeEffectFrom", type=str, nullable=True, location="json")
        parser.add_argument("decreeEffectTo", type=str, nullable=True, location="json")
        parser.add_argument("decreeStatusCode", type=str, nullable=True, location="json")
        parser.add_argument("created_by", type=str, default="System", location="json")

        args = parser.parse_args()

        try:
            # Convert date strings to datetime objects
            date_fields = [
                "decreeIssuedFrom", "decreeIssuedTo", "dateExpiredFrom", 
                "dateExpiredTo", "decreeEffectFrom", "decreeEffectTo"
            ]
            for field in date_fields:
                if args[field]:
                    try:
                        args[field] = datetime.fromisoformat(args[field])
                    except ValueError:
                        duration = (datetime.now() - start_time).total_seconds()
                        logger.error("create_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": f"Invalid date format for {field}"})
                        return make_response(
                            data=None, code=2000, 
                            message=f"Invalid date format for {field}. Use ISO format (e.g., 2023-10-01T00:00:00)"
                        ), 400

            # Prepare rules for child subject
            rules = {
                "keywordCodes": args["keywordCodes"],
                "documentCategoryCodes": args["documentCategoryCodes"],
                "issuedLevelCodes": args["issuedLevelCodes"],
                "industrySectorCodes": args["industrySectorCodes"],
                "agencyIssuedCodes": args["agencyIssuedCodes"],
                "decreeIssuedCodes": args["decreeIssuedCodes"],
                "decreeIssuedFrom": args["decreeIssuedFrom"],
                "decreeIssuedTo": args["decreeIssuedTo"],
                "dateExpiredFrom": args["dateExpiredFrom"],
                "dateExpiredTo": args["dateExpiredTo"],
                "decreeEffectFrom": args["decreeEffectFrom"],
                "decreeEffectTo": args["decreeEffectTo"],
                "decreeStatusCode": args["decreeStatusCode"]
            }

            subject_level = args["filterType"]
            logger.debug("create_subject_tree_started", action="post", name=args["name"], subject_level=subject_level, parent_subject_id=args["parentCode"], rules=rules, created_by=args["created_by"])
            # Call LawTreeManager to create tree or subject
            obj_type, status, obj_id, message = law_tree_manager.create_subject_tree_with_rule(
                name=args["name"],
                subject_level=subject_level,
                parent_subject_id=args["parentCode"],
                rules=rules,
                created_by=args["created_by"]
            )

            if not status:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("create_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": message})
                return make_response(data=None, code=1000, message=message), 400

            # Retrieve the created object
            if obj_type == "TREE":
                obj = law_tree_manager.tree_collection.find_one({"tree_id": obj_id})
            else:
                obj = law_tree_manager.subject_tree_collection.find_one({"subject_id": obj_id})

            if not obj:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("create_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "404-NOT_FOUND", "error.message": "Created object not found"})
                return make_response(data=None, code=1000, message="Created object not found"), 404

            # Format response
            response_data = {
                "id": obj_id,
                "code": obj_id,  # Assume code is same as id
                "name": obj["tree_name"] if obj_type == "TREE" else obj["subject_name"],
                "createdBy": obj["created_by"],
                "createdDate": obj["created_at"],
                "lastModifiedBy": obj.get("last_modified_by", obj["created_by"]),
                "lastModified": obj["last_modified_at"],
                "status": obj.get("status", "ACTIVE"),
                "parentCode": obj.get("subject_parent_id", "") if obj_type != "TREE" else None,
                "state": obj.get("state", "PENDING"),
                "filterType": obj.get("subject_level", "") if obj_type != "TREE" else "TREE",
                "category": obj.get("category", "LAW"),
                "keywordCodes": obj.get("rules", {}).get("keywordCodes", []) if obj_type == "CHILD" else [],
                "documentCategoryCodes": obj.get("rules", {}).get("documentCategoryCodes", "") if obj_type == "CHILD" else "",
                "issuedLevelCodes": obj.get("rules", {}).get("issuedLevelCodes", "") if obj_type == "CHILD" else "",
                "industrySectorCodes": obj.get("rules", {}).get("industrySectorCodes", "") if obj_type == "CHILD" else "",
                "agencyIssuedCodes": obj.get("rules", {}).get("agencyIssuedCodes", "") if obj_type == "CHILD" else "",
                "decreeIssuedCodes": obj.get("rules", {}).get("decreeIssuedCodes", "") if obj_type == "CHILD" else "",
                "decreeIssuedFrom": obj.get("rules", {}).get("decreeIssuedFrom", None) if obj_type == "CHILD" else None,
                "decreeIssuedTo": obj.get("rules", {}).get("decreeIssuedTo", None) if obj_type == "CHILD" else None,
                "dateExpiredFrom": obj.get("rules", {}).get("dateExpiredFrom", None) if obj_type == "CHILD" else None,
                "dateExpiredTo": obj.get("rules", {}).get("dateExpiredTo", None) if obj_type == "CHILD" else None,
                "decreeEffectFrom": obj.get("rules", {}).get("decreeEffectFrom", None) if obj_type == "CHILD" else None,
                "decreeEffectTo": obj.get("rules", {}).get("decreeEffectTo", None) if obj_type == "CHILD" else None,
                "decreeStatusCode": obj.get("rules", {}).get("decreeStatusCode", "") if obj_type == "CHILD" else "",
                "count": obj.get("count", 0)
            }

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("create_subject_tree_success", action="post", **{"event.duration": duration, "event.status": "success"}, obj_id=obj_id, obj_type=obj_type)
            return make_response(data=response_data, code=0, message=f"{obj_type.capitalize()} created successfully"), 201

        except PyMongoError as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("create_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-DB", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("create_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class DeleteSubjectTreeAPI(Resource):
    """API for deleting a subject tree or subject by ID or code."""

    def post(self, idOrCode: str):
        """Handle POST request to delete a subject tree or subject.

        Args:
            idOrCode: ID or code of the tree or subject to delete.

        Returns:
            Response with success status and message.
        """
        structlog.contextvars.bind_contextvars(task="DeleteSubjectTreeAPI")
        start_time = datetime.now()
        try:
            if not idOrCode:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("delete_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "ID or code cannot be empty"})
                return make_response(data=None, code=1000, message="ID or code cannot be empty"), 400

            logger.debug("delete_subject_tree_started", action="post", idOrCode=idOrCode)

            # Call LawTreeManager to delete tree or subject
            status, message = law_tree_manager.delete_subject(subject_id=idOrCode)

            if not status:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("delete_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "404-NOT_FOUND", "error.message": message}, idOrCode=idOrCode)
                return make_response(data={"success": False}, code=1000, message=message), 404

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("delete_subject_tree_success", action="post", **{"event.duration": duration, "event.status": "success"}, idOrCode=idOrCode)
            return make_response(data={"success": True}, code=0, message=message), 200

        except PyMongoError as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("delete_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-DB", "error.message": str(e)}, idOrCode=idOrCode, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("delete_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500

class SubjectTreeDocumentAPI(Resource):
    """API for retrieving subject tree information and its subjects with pagination."""

    def get(self) -> Dict[str, Any]:
        """Handle GET request to retrieve subject tree details and its children with pagination.

        Query Parameters:
            skip (int): Number of trees to skip (default: 0).
            limit (int): Maximum number of trees to return (default: 10).
            tree_id (str, optional): Specific tree ID to retrieve.

        Returns:
            Response with tree details, including children subjects, or error message.
        """
        parser = reqparse.RequestParser()
        parser.add_argument("skip", type=int, default=0, location="args")
        parser.add_argument("limit", type=int, default=10, location="args")
        parser.add_argument("tree_id", type=str, required=False, location="args")
        args = parser.parse_args()

        structlog.contextvars.bind_contextvars(task="SubjectTreeDocumentAPI")
        start_time = datetime.now()

        try:
            logger.debug("get_subject_tree_started", action="get", tree_id=args.get("tree_id"), skip=args.get("skip"), limit=args.get("limit"))
            responses = []
            query = {"tree_id": args["tree_id"]} if args["tree_id"] else {}
            total_trees = law_tree_manager.tree_collection.count_documents(query)

            # Fetch trees with pagination
            trees = law_tree_manager.tree_collection.find(query).skip(args["skip"]).limit(args["limit"])
            
            for tree in trees:
                try:
                    # Fetch subjects with projection
                    subjects = list(law_tree_manager.subject_tree_collection.find(
                        {"tree_id": tree["tree_id"]},
                        {"subject_id": 1, "subject_name": 1, "subject_level": 1, "subject_parent_id": 1, 
                        "count": 1, "status": 1, "category": 1, "doc_id_includes": 1, "_id": 0}
                    ))

                    # Build children hierarchy
                    parent_subjects = [s for s in subjects if s["subject_level"] == "PARENT"]
                    child_subjects = [s for s in subjects if s["subject_level"] == "CHILD"]
                    parent_subjects = sorted(parent_subjects, key=lambda x: vi_sort_key(x.get("subject_name", "")))
                    child_subjects = sorted(child_subjects, key=lambda x: vi_sort_key(x.get("subject_name", "")))
                    children = []
                    for parent in parent_subjects:
                        parent_data = {
                            "code": parent["subject_id"],
                            "name": parent["subject_name"],
                            "parentCode": tree["tree_id"],
                            "count": len(set([doc_id for child in child_subjects if child["subject_parent_id"] == parent["subject_id"] for doc_id in child.get("doc_id_includes", [])])),
                            "filterType": parent["subject_level"],
                            "status": parent.get("status", "ACTIVE"),
                            "category": parent.get("category", "LAW"),
                            "childrens": []
                        }
                        for child in child_subjects:
                            if child["subject_parent_id"] == parent["subject_id"]:
                                child_data = {
                                    "code": child["subject_id"],
                                    "name": child["subject_name"],
                                    "parentCode": child["subject_parent_id"],
                                    "count": child.get("count", 0),
                                    "filterType": child["subject_level"],
                                    "status": child.get("status", "ACTIVE"),
                                    "category": child.get("category", "LAW"),
                                    "doc_id_includes": child.get("doc_id_includes", []),
                                    "childrens": []
                                }
                                parent_data["childrens"].append(child_data)
                        children.append(parent_data)

                    # Calculate unique document count for the tree
                    total_count = len(set([doc_id for subject in subjects for doc_id in subject.get("doc_id_includes", [])]))

                    response_data = {
                        "code": tree["tree_id"],
                        "name": tree["tree_name"],
                        "parentCode": None,
                        "count": total_count,
                        "filterType": "TREE",
                        "status": tree.get("status", "ACTIVE"),
                        "category": tree.get("category", "LAW"),
                        "childrens": children
                    }
                    responses.append(response_data)
                except PyMongoError as e:
                    logger.error("process_tree_failed", action="get", **{"error.code": "500-DB", "error.message": str(e)}, tree_id=tree['tree_id'], exc_info=True)
                    continue

            if not responses:
                duration = (datetime.now() - start_time).total_seconds()
                logger.info("get_subject_tree_success", action="get", **{"event.duration": duration, "event.status": "success"}, total=total_trees, found=0)
                return make_response(
                    data={"trees": [], "total": total_trees, "skip": args["skip"], "limit": args["limit"]},
                    code=0,
                    message="No trees found"
                ), 200

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("get_subject_tree_success", action="get", **{"event.duration": duration, "event.status": "success"}, total=total_trees, found=len(responses))
            return make_response(
                data={"trees": responses, "total": total_trees, "skip": args["skip"], "limit": args["limit"]},
                code=0,
                message="Trees retrieved successfully"
            ), 200

        except PyMongoError as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_subject_tree_failed", action="get", **{"event.duration": duration, "event.status": "failed", "error.code": "500-DB", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_subject_tree_failed", action="get", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500

    def stream(self):
        """Handle GET request to stream subject tree details and its children.

        Query Parameters:
            tree_id (str, optional): Specific tree ID to stream.

        Returns:
            Streamed JSON response with tree details.
        """
        parser = reqparse.RequestParser()
        parser.add_argument("tree_id", type=str, required=False, location="args")
        args = parser.parse_args()

        structlog.contextvars.bind_contextvars(task="SubjectTreeDocumentAPI")
        start_time = datetime.now()

        def generate_stream():
            try:
                logger.debug("stream_subject_tree_started", action="stream", tree_id=args.get("tree_id"))
                query = {"tree_id": args["tree_id"]} if args["tree_id"] else {}
                trees = law_tree_manager.tree_collection.find(query)
                
                yield '['
                first_tree = True
                for tree in trees:
                    if not first_tree:
                        yield ','
                    first_tree = False
                    
                    subjects = list(law_tree_manager.subject_tree_collection.find(
                        {"tree_id": tree["tree_id"]},
                        {"subject_id": 1, "subject_name": 1, "subject_level": 1, "subject_parent_id": 1, 
                         "count": 1, "status": 1, "category": 1, "doc_id_includes": 1, "_id": 0}
                    ))

                    parent_subjects = [s for s in subjects if s["subject_level"] == "PARENT"]
                    child_subjects = [s for s in subjects if s["subject_level"] == "CHILD"]

                    children = []
                    for parent in parent_subjects:
                        parent_data = {
                            "code": parent["subject_id"],
                            "name": parent["subject_name"],
                            "parentCode": tree["tree_id"],
                            "count": len(set([doc_id for child in child_subjects if child["subject_parent_id"] == parent["subject_id"] for doc_id in child.get("doc_id_includes", [])])),
                            "filterType": parent["subject_level"],
                            "status": parent.get("status", "ACTIVE"),
                            "category": parent.get("category", "LAW"),
                            "childrens": []
                        }
                        for child in child_subjects:
                            if child["subject_parent_id"] == parent["subject_id"]:
                                child_data = {
                                    "code": child["subject_id"],
                                    "name": child["subject_name"],
                                    "parentCode": child["subject_parent_id"],
                                    "count": child.get("count", 0),
                                    "filterType": child["subject_level"],
                                    "status": child.get("status", "ACTIVE"),
                                    "category": child.get("category", "LAW"),
                                    "doc_id_includes": child.get("doc_id_includes", []),
                                    "childrens": []
                                }
                                parent_data["childrens"].append(child_data)
                        children.append(parent_data)

                    # Calculate unique document count for the tree
                    total_count = len(set([doc_id for subject in subjects for doc_id in subject.get("doc_id_includes", [])]))

                    response_data = {
                        "code": tree["tree_id"],
                        "name": tree["tree_name"],
                        "parentCode": None,
                        "count": total_count,
                        "filterType": "TREE",
                        "status": tree.get("status", "ACTIVE"),
                        "category": tree.get("category", "LAW"),
                        "childrens": children
                    }
                    yield json.dumps(response_data)
                duration = (datetime.now() - start_time).total_seconds()
                logger.info("stream_subject_tree_success", action="stream", **{"event.duration": duration, "event.status": "success"})
                yield ']'
            except PyMongoError as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("stream_subject_tree_failed", action="stream", **{"event.duration": duration, "event.status": "failed", "error.code": "500-DB", "error.message": str(e)}, exc_info=True)
                yield json.dumps({"error": str(e)})
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("stream_subject_tree_failed", action="stream", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
                yield json.dumps({"error": str(e)})

        return Response(generate_stream(), mimetype='application/json')
        

class UpdateSubjectTreeAPI(Resource):
    """API for updating a subject tree, parent subject, or child subject by ID or code."""

    def post(self, idOrCode: str) -> Dict[str, Any]:
        """Handle POST request to update a subject tree or subject.

        Args:
            idOrCode: ID or code of the tree or subject to update.

        Returns:
            Response with updated object details or error message.
        """
        structlog.contextvars.bind_contextvars(task="UpdateSubjectTreeAPI")
        start_time = datetime.now()
        parser = reqparse.RequestParser()
        parser.add_argument("name", type=str, required=True, nullable=False, location="json")
        parser.add_argument("parentCode", type=str, nullable=True, location="json")
        parser.add_argument("filterType", type=str, nullable=True, location="json", default="CHILD")
        parser.add_argument("keywordCodes", type=list, nullable=True, location="json")
        parser.add_argument("documentCategoryCodes", type=list, nullable=True, location="json")
        parser.add_argument("issuedLevelCodes", type=list, nullable=True, location="json")
        parser.add_argument("industrySectorCodes", type=list, nullable=True, location="json")
        parser.add_argument("agencyIssuedCodes", type=list, nullable=True, location="json")
        parser.add_argument("decreeIssuedCodes", type=list, nullable=True, location="json")
        parser.add_argument("decreeIssuedFrom", type=str, nullable=True, location="json")
        parser.add_argument("decreeIssuedTo", type=str, nullable=True, location="json")
        parser.add_argument("dateExpiredFrom", type=str, nullable=True, location="json")
        parser.add_argument("dateExpiredTo", type=str, nullable=True, location="json")
        parser.add_argument("decreeEffectFrom", type=str, nullable=True, location="json")
        parser.add_argument("decreeEffectTo", type=str, nullable=True, location="json")
        parser.add_argument("decreeStatusCode", type=str, nullable=True, location="json")
        parser.add_argument("created_by", type=str, default="System", location="json")

        args = parser.parse_args()

        try:
            logger.debug("update_subject_tree_started", action="post", idOrCode=idOrCode, name=args.get("name"))
            if not idOrCode:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("update_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "ID or code cannot be empty"})
                return make_response(data=None, code=1000, message="ID or code cannot be empty"), 400

            # Convert date strings to datetime objects
            date_fields = [
                "decreeIssuedFrom", "decreeIssuedTo", "dateExpiredFrom", 
                "dateExpiredTo", "decreeEffectFrom", "decreeEffectTo"
            ]
            for field in date_fields:
                if args[field]:
                    try:
                        args[field] = datetime.fromisoformat(args[field])
                    except ValueError:
                        duration = (datetime.now() - start_time).total_seconds()
                        logger.error("update_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": f"Invalid date format for {field}"})
                        return make_response(
                            data=None, code=2000, 
                            message=f"Invalid date format for {field}. Use ISO format (e.g., 2023-10-01T00:00:00)"
                        ), 400

            # Prepare rules for child subject
            rules = {
                "keywordCodes": args["keywordCodes"] or [],
                "documentCategoryCodes": args["documentCategoryCodes"],
                "issuedLevelCodes": args["issuedLevelCodes"],
                "industrySectorCodes": args["industrySectorCodes"],
                "agencyIssuedCodes": args["agencyIssuedCodes"],
                "decreeIssuedCodes": args["decreeIssuedCodes"],
                "decreeIssuedFrom": args["decreeIssuedFrom"],
                "decreeIssuedTo": args["decreeIssuedTo"],
                "dateExpiredFrom": args["dateExpiredFrom"],
                "dateExpiredTo": args["dateExpiredTo"],
                "decreeEffectFrom": args["decreeEffectFrom"],
                "decreeEffectTo": args["decreeEffectTo"],
                "decreeStatusCode": args["decreeStatusCode"]
            }

            # Validate parentCode and filterType
            obj = law_tree_manager.tree_collection.find_one({"tree_id": idOrCode})
            if obj:
                obj_type = "TREE"
            else:
                obj = law_tree_manager.subject_tree_collection.find_one({"subject_id": idOrCode})
                obj_type = obj["subject_level"] if obj else "TREE"
            
            if obj_type == "TREE" and args["parentCode"]:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("update_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Cannot set parentCode for a tree"})
                return make_response(data=None, code=2000, message="Cannot set parentCode for a tree"), 400

            if obj_type == "PARENT" and args["filterType"] != "PARENT":
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("update_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Cannot change filterType of a parent subject"})
                return make_response(data=None, code=2000, message="Cannot change filterType of a parent subject"), 400

            if obj_type == "CHILD" and args["filterType"] != "CHILD":
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("update_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Cannot change filterType of a child subject"})
                return make_response(data=None, code=2000, message="Cannot change filterType of a child subject"), 400

            # Call LawTreeManager to update tree or subject
            type_result, status = law_tree_manager.update_subject(
                subject_id=idOrCode,
                subject_name=args.get("name", ""),
                rules=rules if args.get("filterType") == "CHILD" else {},
                last_modified_by=args.get("last_modified_by", "System")
            )

            if not status:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("update_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "404-NOT_FOUND", "error.message": "Tree or subject not found"}, idOrCode=idOrCode)
                return make_response(data=None, code=1000, message="Tree or subject not found"), 404

            # Retrieve the updated object
            if type_result == "TREE":
                obj = law_tree_manager.tree_collection.find_one({"tree_id": idOrCode})
            else:
                obj = law_tree_manager.subject_tree_collection.find_one({"subject_id": idOrCode})

            if not obj:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("update_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "404-NOT_FOUND", "error.message": "Updated object not found"})
                return make_response(data=None, code=1000, message="Updated object not found"), 404

            # Format response
            response_data = {
                "id": idOrCode,
                "code": idOrCode,  # Assume code is same as id
                "name": obj["tree_name"] if type_result == "TREE" else obj["subject_name"],
                "createdBy": obj["created_by"],
                "createdDate": obj["created_at"],
                "lastModifiedBy": obj.get("last_modified_by", obj["created_by"]),
                "lastModified": obj["last_modified_at"],
                "status": obj.get("status", "ACTIVE"),
                "parentCode": obj.get("subject_parent_id", "") if type_result != "TREE" else None,
                "state": obj.get("state", "PENDING"),
                "filterType": obj.get("subject_level", "") if type_result != "TREE" else "TREE",
                "category": obj.get("category", "LAW"),
                "keywordCodes": obj.get("rules", {}).get("keywordCodes", []) if type_result == "CHILD" else [],
                "documentCategoryCodes": obj.get("rules", {}).get("documentCategoryCodes", []) if type_result == "CHILD" else [],
                "issuedLevelCodes": obj.get("rules", {}).get("issuedLevelCodes", []) if type_result == "CHILD" else [],
                "industrySectorCodes": obj.get("rules", {}).get("industrySectorCodes", []) if type_result == "CHILD" else [],
                "agencyIssuedCodes": obj.get("rules", {}).get("agencyIssuedCodes", []) if type_result == "CHILD" else [],
                "decreeIssuedCodes": obj.get("rules", {}).get("decreeIssuedCodes", []) if type_result == "CHILD" else [],
                "decreeIssuedFrom": obj.get("rules", {}).get("decreeIssuedFrom", None) if type_result == "CHILD" else None,
                "decreeIssuedTo": obj.get("rules", {}).get("decreeIssuedTo", None) if type_result == "CHILD" else None,
                "dateExpiredFrom": obj.get("rules", {}).get("dateExpiredFrom", None) if type_result == "CHILD" else None,
                "dateExpiredTo": obj.get("rules", {}).get("dateExpiredTo", None) if type_result == "CHILD" else None,
                "decreeEffectFrom": obj.get("rules", {}).get("decreeEffectFrom", None) if type_result == "CHILD" else None,
                "decreeEffectTo": obj.get("rules", {}).get("decreeEffectTo", None) if type_result == "CHILD" else None,
                "decreeStatusCode": obj.get("rules", {}).get("decreeStatusCode", "") if type_result == "CHILD" else "",
                "count": obj.get("count", 0)
            }

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("update_subject_tree_success", action="post", **{"event.duration": duration, "event.status": "success"}, idOrCode=idOrCode, type_result=type_result)
            return make_response(data=response_data, code=0, message=f"{type_result.capitalize()} updated successfully"), 200

        except PyMongoError as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("update_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-DB", "error.message": str(e)}, idOrCode=idOrCode, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("update_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class SubjectTreeGetAPI(Resource):
    """API for retrieving subject tree information and its subjects with pagination."""
    def post(self, idOrCode: str) -> Dict[str, Any]:
        """Handle GET request to retrieve subject tree details and its children with pagination.

        Query Parameters:
            skip (int): Number of trees to skip (default: 0).
            limit (int): Maximum number of trees to return (default: 10).
            tree_id (str, optional): Specific tree ID to retrieve.

        Returns:
            Response with tree details, including children subjects, or error message.
        """
        parser = reqparse.RequestParser()
        parser.add_argument("skip", type=int, default=0, location="args")
        parser.add_argument("limit", type=int, default=10, location="args")
        args = parser.parse_args()

        structlog.contextvars.bind_contextvars(task="SubjectTreeGetAPI")
        start_time = datetime.now()

        try:
            logger.debug("get_subject_tree_started", action="post", idOrCode=idOrCode)
            response = None
            query = {"tree_id": idOrCode}                        
            tree = law_tree_manager.tree_collection.find_one(query)            
            if tree:
                # Fetch subjects with projection
                subjects = list(law_tree_manager.subject_tree_collection.find(
                    {"tree_id": idOrCode},
                    {"subject_id": 1, "subject_name": 1, "subject_level": 1, "subject_parent_id": 1, 
                        "count": 1, "status": 1, "category": 1, "doc_id_includes": 1, "_id": 0}
                ))

                # Build children hierarchy
                parent_subjects = [s for s in subjects if s["subject_level"] == "PARENT"]
                child_subjects = [s for s in subjects if s["subject_level"] == "CHILD"]
                parent_subjects = sorted(parent_subjects, key=lambda x: vi_sort_key(x.get("subject_name", "")))
                child_subjects = sorted(child_subjects, key=lambda x: vi_sort_key(x.get("subject_name", "")))
                children = []
                for parent in parent_subjects:
                    parent_data = {
                        "code": parent["subject_id"],
                        "name": parent["subject_name"],
                        "parentCode": tree["tree_id"],
                        "count": len(set([doc_id for child in child_subjects if child["subject_parent_id"] == parent["subject_id"] for doc_id in child.get("doc_id_includes", [])])),
                        "filterType": parent["subject_level"],
                        "status": parent.get("status", "ACTIVE"),
                        "category": parent.get("category", "LAW"),
                        "childrens": []
                    }
                    for child in child_subjects:
                        if child["subject_parent_id"] == parent["subject_id"]:
                            child_data = {
                                "code": child["subject_id"],
                                "name": child["subject_name"],
                                "parentCode": child["subject_parent_id"],
                                "count": child.get("count", 0),
                                "filterType": child["subject_level"],
                                "status": child.get("status", "ACTIVE"),
                                "category": child.get("category", "LAW"),
                                "doc_id_includes": child.get("doc_id_includes", []),
                                "childrens": []
                            }
                            parent_data["childrens"].append(child_data)
                    children.append(parent_data)

                total_count = len(set([doc_id for subject in subjects for doc_id in subject.get("doc_id_includes", [])]))

                response = {
                    "code": tree["tree_id"],
                    "name": tree["tree_name"],
                    "parentCode": None,
                    "count": total_count,
                    "filterType": "TREE",
                    "status": tree.get("status", "ACTIVE"),
                    "category": tree.get("category", "LAW"),
                    "childrens": children
                }
            else:
                subject = law_tree_manager.subject_tree_collection.find_one({'subject_id': idOrCode}) 
                if subject:
                    if subject["subject_level"] == "CHILD":
                        response = {
                            "code": subject["subject_id"],
                            "name": subject["subject_name"],
                            "parentCode": subject["subject_parent_id"],
                            "count": len(subject.get("doc_id_includes", [])),
                            "filterType": subject["subject_level"],
                            "status": subject.get("status", "ACTIVE"),
                            "category": subject.get("category", "LAW"),
                            "doc_id_includes": subject.get("doc_id_includes", []),
                            "childrens": []                        
                        }
                        for key, value in subject.get("rules", {}).items():
                            response[key] = value
                    else:
                        child_subjects = list(law_tree_manager.subject_tree_collection.find({'subject_parent_id': subject["subject_id"]}))
                        children = []
                        for child_subject in child_subjects:
                            child_data = {
                                "code": child_subject["subject_id"],
                                "name": child_subject["subject_name"],
                                "parentCode": child_subject["subject_parent_id"],
                                "count": child_subject.get("count", 0),
                                "filterType": child_subject["subject_level"],
                                "status": child_subject.get("status", "ACTIVE"),
                                "category": child_subject.get("category", "LAW"),
                                "doc_id_includes": child_subject.get("doc_id_includes", []),
                                "childrens": [],                                                        
                            }
                            for key, value in child_subject.get("rules", {}).items():
                                child_data[key] = value
                            children.append(child_data)
                        
                        response = {
                            "code": subject["subject_id"],
                            "name": subject["subject_name"],
                            "parentCode": subject["subject_parent_id"],
                            "count": len(set([doc_id for subject in subjects for doc_id in subject.get("doc_id_includes", [])])),
                            "filterType": subject["subject_level"],
                            "status": subject.get("status", "ACTIVE"),
                            "category": subject.get("category", "LAW"),
                            "doc_id_includes": subject.get("doc_id_includes", []),
                            "childrens": children
                        }

            if not response:
                duration = (datetime.now() - start_time).total_seconds()
                logger.info("get_subject_tree_success", action="post", **{"event.duration": duration, "event.status": "success"}, found=0)
                return make_response(
                    data=response,
                    code=0,
                    message="No trees found"
                ), 200

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("get_subject_tree_success", action="post", **{"event.duration": duration, "event.status": "success"}, found=1)
            return make_response(
                data=response,
                code=0,
                message="Trees retrieved successfully"
            ), 200

        except PyMongoError as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-DB", "error.message": str(e)}, idOrCode=idOrCode, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("get_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, idOrCode=idOrCode, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500

    
    def stream(self):
        """Handle GET request to stream subject tree details and its children.

        Query Parameters:
            tree_id (str, optional): Specific tree ID to stream.

        Returns:
            Streamed JSON response with tree details.
        """
        parser = reqparse.RequestParser()
        parser.add_argument("tree_id", type=str, required=False, location="args")
        args = parser.parse_args()

        structlog.contextvars.bind_contextvars(task="SubjectTreeGetAPI")
        start_time = datetime.now()

        def generate_stream():
            try:
                logger.debug("stream_subject_tree_started", action="stream", tree_id=args.get("tree_id"))
                query = {"tree_id": args["tree_id"]} if args["tree_id"] else {}
                tree = law_tree_manager.tree_collection.find_one(query)
                
                yield '['
                
                subjects = list(law_tree_manager.subject_tree_collection.find(
                        {"tree_id": tree["tree_id"]},
                        {"subject_id": 1, "subject_name": 1, "subject_level": 1, "subject_parent_id": 1, 
                         "count": 1, "status": 1, "category": 1, "doc_id_includes": 1, "_id": 0}
                    ))

                parent_subjects = [s for s in subjects if s["subject_level"] == "PARENT"]
                child_subjects = [s for s in subjects if s["subject_level"] == "CHILD"]

                children = []
                for parent in parent_subjects:
                    parent_data = {
                        "code": parent["subject_id"],
                        "name": parent["subject_name"],
                        "parentCode": tree["tree_id"],
                        "count": parent.get("count", 0),
                        "filterType": parent["subject_level"],
                        "status": parent.get("status", "ACTIVE"),
                        "category": parent.get("category", "LAW"),
                        "childrens": []
                    }
                    for child in child_subjects:
                        if child["subject_parent_id"] == parent["subject_id"]:
                            child_data = {
                                "code": child["subject_id"],
                                "name": child["subject_name"],
                                "parentCode": child["subject_parent_id"],
                                "count": child.get("count", 0),
                                "filterType": child["subject_level"],
                                "status": child.get("status", "ACTIVE"),
                                "category": child.get("category", "LAW"),
                                "doc_id_includes": child.get("doc_id_includes", []),
                                "childrens": []
                            }
                            parent_data["childrens"].append(child_data)
                    children.append(parent_data)

                total_count = sum(subject.get("count", 0) for subject in subjects)

                response_data = {
                    "code": tree["tree_id"],
                    "name": tree["tree_name"],
                    "parentCode": None,
                    "count": total_count,
                    "filterType": "TREE",
                    "status": tree.get("status", "ACTIVE"),
                    "category": tree.get("category", "LAW"),
                    "childrens": children
                }
                yield json.dumps(response_data)
                duration = (datetime.now() - start_time).total_seconds()
                logger.info("stream_subject_tree_success", action="stream", **{"event.duration": duration, "event.status": "success"})
                yield ']'
            except PyMongoError as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("stream_subject_tree_failed", action="stream", **{"event.duration": duration, "event.status": "failed", "error.code": "500-DB", "error.message": str(e)}, exc_info=True)
                yield json.dumps({"error": str(e)})
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("stream_subject_tree_failed", action="stream", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
                yield json.dumps({"error": str(e)})

        return Response(generate_stream(), mimetype='application/json')
            

class SubjectTreeMappingDocumentAPI(Resource):
    """API for streaming document mapping information for a subject tree by its code."""

    def post(self, code: str) -> Response:
        """Handle POST request to stream document mapping for a subject tree.

        Args:
            code: Code of the subject tree.

        Returns:
            Streamed JSON response with document mapping details or error message.
        """
        structlog.contextvars.bind_contextvars(task="SubjectTreeMappingDocumentAPI")
        start_time = datetime.now()

        def generate_stream():
            try:
                logger.debug("stream_subject_tree_mapping_started", action="post", code=code)
                if not code:
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.error("stream_subject_tree_mapping_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Subject tree code cannot be empty"})
                    yield json.dumps(make_response(data=None, code=1000, message="Subject tree code cannot be empty")["data"])
                    return
                                    
                # Find the tree
                tree = law_tree_manager.tree_collection.find_one(
                    {"tree_id": code},
                    {"tree_id": 1, "tree_name": 1, "created_by": 1, "created_at": 1, 
                     "last_modified_by": 1, "last_modified_at": 1, "status": 1, "_id": 0}
                )
                if tree:                    
                    # Initialize response data
                    logger.debug("stream_subject_tree_mapping_found_tree", action="post", tree_id=tree.get("tree_id"))
                    subjects = law_tree_manager.subject_tree_collection.find(
                        {"tree_id": code},
                        {"subject_id": 1, "subject_name": 1, "subject_parent_id": 1, 
                         "count": 1, "status": 1, "category": 1, "doc_id_includes": 1, "_id": 0}
                    ).batch_size(100)

                    document_codes = []
                    for subject in subjects:
                        doc_ids = subject.get("doc_id_includes", [])
                        document_codes.extend(str(doc_id) for doc_id in doc_ids)
                    document_codes = list(dict.fromkeys(document_codes))
                    
                    response_data = {
                        "id": tree["tree_id"],
                        "code": tree["tree_id"],
                        "createdBy": tree.get("created_by", "System"),
                        "createdDate": tree["created_at"],
                        "lastModifiedBy": tree.get("last_modified_by", tree.get("created_by", "System")),
                        "lastModified": tree["last_modified_at"],
                        "status": tree.get("status", "ACTIVE"),
                        "text": tree.get("tree_name", ""),
                        "subjectTreeCode": tree["tree_id"],
                        "documentCodes": document_codes,
                        "count": len(document_codes)
                    }
                else:
                    logger.debug("stream_subject_tree_mapping_not_found_tree", action="post", code=code)
                    subject = law_tree_manager.subject_tree_collection.find_one({'subject_id': code},
                        {"tree_id": 1, "subject_id": 1, "created_by": 1, "created_at": 1, "subject_name": 1,
                        "last_modified_by": 1, "last_modified_at": 1, "status": 1, "doc_id_includes": 1, "subject_level": 1, "_id": 0})
                    
                    if not subject:
                        duration = (datetime.now() - start_time).total_seconds()
                        logger.error("stream_subject_tree_mapping_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "404-NOT_FOUND", "error.message": "Subject tree or subject not found"}, code=code)
                        yield json.dumps(make_response(data=None, code=1001, message=f"Subject tree or subject not found with code: {code}")["data"])
                        return
                
                    if subject['subject_level'] == 'PARENT':
                        logger.debug("stream_subject_tree_mapping_parent_subject", action="post", subject_id=subject.get("subject_id"))
                        subjects = list(law_tree_manager.subject_tree_collection.find(
                            {"subject_parent_id": subject['subject_id'], "subject_level": "CHILD"},
                            {"doc_id_includes": 1, "_id": 0}
                        ))
                        logger.debug("stream_subject_tree_mapping_subjects_retrieved", action="post", count=len(subjects))
                        document_codes = []
                        for _subject in subjects:
                            doc_ids = _subject.get("doc_id_includes", [])
                            document_codes.extend(str(doc_id) for doc_id in doc_ids)
                        document_codes = list(dict.fromkeys(document_codes))
                    else:
                        document_codes = list(dict.fromkeys(subject.get("doc_id_includes", [])))
                        
                    response_data = {
                            "id": subject["subject_id"],
                            "code": subject["subject_id"],
                            "createdBy": subject.get("created_by", "System"),
                            "createdDate": subject["created_at"],
                            "lastModifiedBy": subject.get("last_modified_by", subject.get("created_by", "System")),
                            "lastModified": subject["last_modified_at"],
                            "status": subject.get("status", "ACTIVE"),
                            "text": subject.get("subject_name", ""),
                            "subjectTreeCode": subject["tree_id"],
                            "documentCodes": document_codes,
                            "count": len(document_codes)
                        }
                        
                duration = (datetime.now() - start_time).total_seconds()
                logger.info("stream_subject_tree_mapping_success", action="post", **{"event.duration": duration, "event.status": "success"}, found=len(document_codes))
                yield json.dumps(make_response(
                    data=response_data,
                    code=0,
                    message="Subject tree mapping retrieved successfully"
                )["data"])

            except PyMongoError as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("stream_subject_tree_mapping_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-DB", "error.message": str(e)}, code=code, exc_info=True)
                yield json.dumps(make_response(data=None, code=2000, message=str(e))["data"])
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("stream_subject_tree_mapping_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
                yield json.dumps(make_response(data=None, code=2000, message=str(e))["data"])

        return Response(generate_stream(), mimetype='application/json')


class DocumentSegmentTreeElasticAPI(Resource):
    """API for searching document segments with pagination."""

    def post(self, page: int, quantity: int) -> Dict[str, Any]:
        """Handle POST request to search document segments with pagination.

        Args:
            page: Page number (1-based).
            quantity: Number of records per page.

        Returns:
            Response with search results, total count, or error message.
        """
        parser = reqparse.RequestParser()
        parser.add_argument("documentCodes", type=list, nullable=True, location="json")        
        args = parser.parse_args()

        structlog.contextvars.bind_contextvars(task="DocumentSegmentTreeElasticAPI")
        start_time = datetime.now()

        if not args["documentCodes"]:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("search_document_segment_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Document codes are required"})
            return make_response(
                data=None, code=1000, message="Document codes are required"
            ), 400
        logger.debug("search_document_segment_started", action="post", count=len(args['documentCodes']), page=page, quantity=quantity)

        try:
            # Validate pagination parameters
            if page < 1 or quantity < 1:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("search_document_segment_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Invalid pagination parameters"})
                return make_response(
                    data=None, code=1000, message="Page and quantity must be positive integers"
                ), 400

            query = {"doc_id": {"$in": args["documentCodes"]}}
            # Calculate skip for pagination (page is 1-based)
            skip = (page - 1) * quantity

            # Count total documents
            total_count = law_tree_manager.law_document_collection.count_documents(query)
            logger.debug("search_document_segment_total_found", action="post", count=total_count)

            # Fetch documents with pagination
            documents = list(law_tree_manager.law_document_collection.find(query).skip(skip).limit(quantity))
            logger.debug("search_document_segment_retrieved", action="post", count=len(documents))

            # Format response
            models = []
            for doc in documents:
                # Ensure datetime fields are converted to ISO strings or None
                created_at = doc.get("created_at")
                last_modified_at = doc.get("last_modified_at")
                decree_issued = doc.get("decree_issued")
                decree_effect = doc.get("decree_effect")

                model = {
                    "storageCode": doc.get("storage_id", ""),
                    "code": doc.get("doc_id", ""),
                    "name": doc.get("doc_title", ""),
                    "description": doc.get("doc_content", ""),
                    "createdBy": doc.get("created_by", "System"),
                    "createdDate": created_at if isinstance(created_at, datetime) else None,
                    "lastModifiedBy": doc.get("last_modified_by", doc.get("created_by", "System")),
                    "lastModified": last_modified_at if isinstance(last_modified_at, datetime) else None,
                    "status": doc.get("status", "ACTIVE"),
                    "documentCategoryCode": doc.get("category_id", ""),
                    "documentCode": doc.get("doc_code", ""),
                    "agencySymbol": doc.get("agency_symbol", ""),
                    "keywordCodes": doc.get("keyword_ids", []),
                    "industrySectorCodes": doc.get("industry_sector_ids", []),
                    "issuedLevelCode": doc.get("issuing_level_id", ""),
                    "properties": doc.get("properties", []),
                    "documentReferences": doc.get("doc_references", []),
                    "documentFormCode": doc.get("document_form_code", ""),
                    "signerCodes": doc.get("signer_ids", []),
                    "positionCodes": doc.get("position_ids", []),
                    "agencyIssuedCodes": doc.get("agency_ids", []),
                    "decreeIssued": doc.get("doc_issue_date", None),
                    "decreeEffect": doc.get("doc_effective_date", None),
                    "decreeStatus": doc.get("decree_status", ""),
                    "decreeStatusCode": doc.get("effective_status_id", ""),
                    "guidedDocuments": doc.get("guided_documents", []),
                    "consolidatingDocuments": doc.get("consolidating_documents", []),
                    "correctedDocuments": doc.get("corrected_documents", []),
                    "replaceDocuments": doc.get("replace_documents", []),
                    "referentialDocuments": doc.get("referential_documents", []),
                    "basisDocuments": doc.get("basis_documents", []),
                    "contentConnectionDocuments": doc.get("content_connection_documents", []),
                    "avoidDocuments": doc.get("avoid_documents", []),
                    "amendedDocuments": doc.get("amended_documents", []),
                    "source": doc.get("source", ""),
                    "referenceStorageCodes": doc.get("reference_storage_codes", []),
                    "templateMappingCode": doc.get("template_mapping_code", ""),
                    "dataSource": doc.get("data_source", ""),
                    "embeddingStatus": doc.get("embedding_status", ""),
                    "finetuneClassifyCode": doc.get("finetune_classify_code", ""),
                    "shortDescription": doc.get("doc_short_description", "")
                }
                models.append(model)

            response_data = {
                "count": total_count,
                "models": models
            }

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("search_document_segment_success", action="post", **{"event.duration": duration, "event.status": "success"}, total=total_count, returned=len(models))
            return make_response(
                data=response_data,
                code=0,
                message="Documents retrieved successfully"
            ), 200

        except PyMongoError as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("search_document_segment_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-DB", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("search_document_segment_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# Temporary directory for uploaded files
UPLOAD_FOLDER = "/tmp/law_tree_uploads"

class ImportSubjectTreeAPI(Resource):
    """API for importing a subject tree from an Excel file."""

    def post(self) -> Dict[str, Any]:
        """Handle POST request to import a subject tree from an Excel file.

        Form Data:
            file: Excel file (.xlsx or .xls) containing tree data.
            tree_name: Name of the tree to create.
            created_by: User who initiated the import (default: System).

        Returns:
            Response with import status, message, and failed imports (if any).
        """
        parser = reqparse.RequestParser()
        parser.add_argument("tree_name", type=str, required=True, nullable=False, location="form")
        parser.add_argument("created_by", type=str, default="System", location="form")
        args = parser.parse_args()

        tree_name = args["tree_name"]
        created_by = args["created_by"]        
        
        structlog.contextvars.bind_contextvars(task="ImportSubjectTreeAPI")
        start_time = datetime.now()

        try:
            logger.debug("import_subject_tree_started", action="post", tree_name=tree_name, created_by=created_by)
            # Check if upload directory is accessible
            try:
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                if not os.access(UPLOAD_FOLDER, os.W_OK):
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.error("import_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": "No write permission for upload directory"}, directory=UPLOAD_FOLDER)
                    response = make_response(data=None, code=2000, message="Server error: No write permission for upload directory")
                    response["error_code"] = "500-SYS"
                    response["status"] = False
                    return response, 500
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("import_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, directory=UPLOAD_FOLDER, exc_info=True)
                response = make_response(data=None, code=2000, message="Server error: Failed to access upload directory")
                response["error_code"] = "500-SYS"
                response["status"] = False
                return response, 500

            # Check if file is present
            if "file" not in request.files:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("import_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "No file provided"})
                return make_response(
                    data=None, code=1000, message="No file provided"
                ), 400

            file = request.files["file"]
            if not file or file.filename == "":
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("import_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "No file selected"})
                return make_response(
                    data=None, code=1000, message="No file selected"
                ), 400

            # Validate file extension
            if not law_tree_manager.allowed_file(file.filename):
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("import_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": "Invalid file extension"})
                return make_response(
                    data=None, code=1000,
                    message=f"Invalid file extension. Allowed: .xlsx, .xls"
                ), 400

            # Securely save the file temporarily
            filename = secure_filename(file.filename)
            temp_file_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{filename}")
            logger.debug("import_subject_tree_saving", action="post", path=temp_file_path)
            file.save(temp_file_path)

            # Verify file was saved correctly
            if not os.path.exists(temp_file_path):
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("import_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": "Failed to save uploaded file"}, path=temp_file_path)
                response = make_response(data=None, code=2000, message="Server error: Failed to save uploaded file")
                response["error_code"] = "500-SYS"
                response["status"] = False
                return response, 500
            
            status, tree_id, message = law_tree_manager.check_valid_file(
                tree_name=tree_name,
                path_file_excel=temp_file_path,
                created_by=created_by
            )            
            
            # Send Kafka message ImportTreeQuery
            send_kafka_message(
                message={
                    "request_id": tree_id,
                    "tree_id": tree_id,
                    "excel_file_path": temp_file_path,
                    "created_by": created_by
                },
                topic=ImportTreeConfig.IMPORT_TREE_QUERY_TOPIC                
            )
                                    
            # Format response
            response_data = {
                "status": status,
                "message": message,
                "tree_id": tree_id,
                "created_by": created_by
            }

            if not status:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("import_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": message})
                return make_response(
                    data=response_data, code=1000, message=message
                ), 400

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("import_subject_tree_success", action="post", **{"event.duration": duration, "event.status": "success"}, tree_id=tree_id)
            return make_response(
                data=response_data, code=0, message=message
            ), 200

        except PyMongoError as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("import_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-DB", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("import_subject_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500
        


class SuggestTreeAPI(Resource):
    """API for classifying a document into child subjects based on defined rules."""
    
    def post(self):
        """Handle POST request to classify a document into child subjects."""
        parser = reqparse.RequestParser()
        parser.add_argument("docContent", type=str, required=True, nullable=False, location="json")
        parser.add_argument("documentCategoryCode", type=str, required=True, nullable=False, location="json")
        parser.add_argument("keywordCodes", type=list, nullable=True, location="json")
        parser.add_argument("issuedLevelCode", type=str, nullable=True, location="json")
        parser.add_argument("industrySectorCodes", type=list, nullable=True, location="json")
        parser.add_argument("agencyIssuedCodes", type=list, nullable=True, location="json")
        parser.add_argument("decreeIssuedCode", type=str, nullable=True, location="json")
        parser.add_argument("decreeIssuedDate", type=str, nullable=True, location="json")
        parser.add_argument("dateExpiredDate", type=str, nullable=True, location="json")
        parser.add_argument("decreeEffectDate", type=str, nullable=True, location="json")
        parser.add_argument("decreeStatusCode", type=str, nullable=True, location="json")
        parser.add_argument("tree_id", type=str, nullable=True, location="json")
        args = parser.parse_args()

        structlog.contextvars.bind_contextvars(task="SuggestTreeAPI")
        start_time = datetime.now()

        try:
            logger.debug("suggest_tree_started", action="post", documentCategoryCode=args["documentCategoryCode"])
            # Step 1: Standardize metadata
            metadata = {
                "docContent": args["docContent"],
                "documentCategoryCode": args["documentCategoryCode"],
                "keywordCodes": args.get("keywordCodes", []),
                "issuedLevelCode": args.get("issuedLevelCode"),
                "industrySectorCodes": args.get("industrySectorCodes"),
                "agencyIssuedCodes": args.get("agencyIssuedCodes"),
                "decreeIssuedCode": args.get("decreeIssuedCode"),
                "decreeIssuedDate": None,
                "dateExpiredDate": None,
                "decreeEffectDate": None,
                "decreeStatusCode": args.get("decreeStatusCode")                
            }
            
            date_fields = ["decreeIssuedDate", "dateExpiredDate", "decreeEffectDate"]
            for field in date_fields:
                if args[field]:
                    try:
                        metadata[field] = datetime.fromisoformat(args[field])
                    except ValueError:
                        duration = (datetime.now() - start_time).total_seconds()
                        logger.error("suggest_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "400-VAL", "error.message": f"Invalid date format for {field}"})
                        return make_response(
                            data=None, code=1000,
                            message=f"Invalid date format for {field}. Use ISO format (e.g., 2023-10-01T00:00:00)"
                        ), 400
            

            # Step 2: Query CHILD components
            query = {"subject_level": "CHILD"}
            if args["tree_id"]:
                query["tree_id"] = args["tree_id"]
            child_subjects = list(law_tree_manager.subject_tree_collection.find(query))
            logger.debug("suggest_tree_child_subjects_found", action="post", count=len(child_subjects))


            if not child_subjects:
                duration = (datetime.now() - start_time).total_seconds()
                logger.info("suggest_tree_success", action="post", **{"event.duration": duration, "event.status": "success"}, found=0)
                return make_response(data=None, code=1000, message="No child subjects found"), 404

            # Step 3: Match rules and count matches
            matched_subjects = []
            for subject in child_subjects:
                rules = subject.get("rules", {})
                match_count = 0

                # Compare each rule
                if rules.get("documentCategoryCodes", None) and metadata["documentCategoryCode"]:
                    if metadata["documentCategoryCode"] in rules.get("documentCategoryCodes"):
                        match_count += 1
                
                if rules.get("issuedLevelCodes", None) and metadata["issuedLevelCode"]:
                    if metadata["issuedLevelCode"] in rules.get("issuedLevelCodes"):
                        match_count += 1

                if rules.get("industrySectorCodes", None) and metadata["industrySectorCodes"]:
                    common_industry_sectors = len(set(rules.get("industrySectorCodes", [])).intersection(set(metadata["industrySectorCodes"])))
                    match_count += common_industry_sectors                        

                if rules.get("agencyIssuedCodes", None) and metadata["agencyIssuedCodes"]:
                    common_agencies = len(set(rules.get("agencyIssuedCodes", [])).intersection(set(metadata["agencyIssuedCodes"])))
                    match_count += common_agencies

                if rules.get("decreeIssuedCodes", None) and metadata["decreeIssuedCode"]:
                    if metadata["decreeIssuedCode"] in rules.get("decreeIssuedCodes"):
                        match_count += 1
                
                if rules.get("decreeStatusCode", None) and metadata["decreeStatusCode"]:
                    if metadata["decreeStatusCode"] in rules.get("decreeStatusCode"):
                        match_count += 1
                
                if rules.get("decreeIssuedFrom", None) and metadata["decreeIssuedDate"]:
                    if rules.get("decreeIssuedFrom") <= metadata["decreeIssuedDate"] <= rules.get("decreeIssuedTo", metadata["decreeIssuedDate"]):
                        match_count += 1
                
                if rules.get("dateExpiredFrom", None) and metadata["dateExpiredDate"]:
                    if rules.get("dateExpiredFrom") <= metadata["dateExpiredDate"] <= rules.get("dateExpiredTo", metadata["dateExpiredDate"]):
                        match_count += 1
                
                if rules.get("decreeEffectFrom", None) and metadata["decreeEffectDate"]:
                    if rules.get("decreeEffectFrom") <= metadata["decreeEffectDate"] <= rules.get("decreeEffectTo", metadata["decreeEffectDate"]):
                        match_count += 1

                if metadata["keywordCodes"] and rules.get("keywordCodes", []):
                    common_keywords = len(set(rules.get("keywordCodes", [])).intersection(set(metadata["keywordCodes"])))
                    match_count += common_keywords                        

                if match_count > 0:
                    tree = law_tree_manager.tree_collection.find_one({"tree_id": subject["tree_id"]})
                    tree_name = tree["tree_name"]
                                        
                    matched_subjects.append({
                        "subject_id": subject["subject_id"],
                        "subject_name": subject["subject_name"],
                        "tree_id": subject["tree_id"],
                        "tree_name": tree_name,
                        "parent_subject_id": subject.get("subject_parent_id", ""),
                        "match_count": match_count
                    })

            # Step 4: Sort by match_count
            matched_subjects.sort(key=lambda x: x["match_count"], reverse=True)

            if not matched_subjects:
                duration = (datetime.now() - start_time).total_seconds()
                logger.info("suggest_tree_success", action="post", **{"event.duration": duration, "event.status": "success"}, found=0)
                return make_response(data=None, code=1000, message="No matching child subjects found"), 404

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("suggest_tree_success", action="post", **{"event.duration": duration, "event.status": "success"}, found=len(matched_subjects[:10]))
            return make_response(
                data=matched_subjects[:10],  # Top 10 matches
                code=0,
                message="Document classified successfully"
            ), 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("suggest_tree_failed", action="post", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class IndexDocumentTreeStaticAPI(Resource):
    def get(self):
        """
        API thống kê số lượng văn bản được lập chỉ mục theo từng cây chủ đề (tree).
        - num_documents: tổng số văn bản thuộc cây đó
        - index_success: số văn bản có bản ghi trong document_collection
        Hỗ trợ filter theo tree_id.
        """
        try:
            req_parser = reqparse.RequestParser()
            req_parser.add_argument("tree_id", type=str, location="args", default=None)
            args = req_parser.parse_args()
            tree_id_filter = args["tree_id"]

            structlog.contextvars.bind_contextvars(task="IndexDocumentTreeStaticAPI")
            start_time = datetime.now()

            # ---- Step 1. Lấy tất cả cây chủ đề (hoặc theo tree_id nếu có) ----
            tree_query = {"tree_id": tree_id_filter} if tree_id_filter else {}
            trees = list(law_tree_manager.tree_collection.find(tree_query, {"_id": 0, "tree_id": 1, "tree_name": 1}))
            if not trees:
                duration = (datetime.now() - start_time).total_seconds()
                logger.info("index_document_tree_static_success", action="get", **{"event.duration": duration, "event.status": "success"}, found=0)
                return make_response(data={}, code=0, message="No trees found"), 200

            # ---- Step 2. Lấy toàn bộ tree_id -> doc_id mapping ----
            component_match = {"tree_id": tree_id_filter} if tree_id_filter else {}
            pipeline = []
            if component_match:
                pipeline.append({"$match": component_match})
            pipeline.extend([
                {"$unwind": "$doc_id_includes"},
                {
                    "$group": {
                        "_id": "$tree_id",
                        "doc_ids": {"$addToSet": "$doc_id_includes"}
                    }
                }
            ])
            tree_docs = list(law_tree_manager.subject_tree_collection.aggregate(pipeline))

            tree_docs_map = {t["_id"]: t["doc_ids"] for t in tree_docs}

            # ---- Step 3. Lấy toàn bộ doc_id đang tồn tại ----
            all_doc_ids = set(doc_id for doc_ids in tree_docs_map.values() for doc_id in doc_ids)
            existing_docs = set(
                d["doc_id"] for d in law_tree_manager.law_document_collection.find(
                    {"doc_id": {"$in": list(all_doc_ids)}}, {"_id": 0, "doc_id": 1}
                )
            )

            # ---- Step 4. Tổng hợp kết quả ----
            result = []
            for tree in trees:
                tree_id = tree["tree_id"]
                doc_ids = set(tree_docs_map.get(tree_id, []))
                num_documents = len(doc_ids)
                index_success = len(doc_ids & existing_docs)

                result.append({
                    "tree_id": tree_id,
                    "tree_name": tree["tree_name"],
                    "num_documents": num_documents,
                    "index_success": index_success
                })

            duration = (datetime.now() - start_time).total_seconds()
            logger.info("index_document_tree_static_success", action="get", **{"event.duration": duration, "event.status": "success"}, count=len(result))
            return make_response(data=result, code=0, message="Index document tree successfully"), 200

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error("index_document_tree_static_failed", action="get", **{"event.duration": duration, "event.status": "failed", "error.code": "500-SYS", "error.message": str(e)}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


# Register API resource
api.add_resource(ImportSubjectTreeAPI, "/subject-tree/import")
api.add_resource(SubjectTreeMappingDocumentAPI, "/subject-tree/get-documents/<string:code>")
api.add_resource(SubjectTreeGetAPI, "/subject-tree/<string:idOrCode>")
api.add_resource(SubjectTreeDocumentAPI, "/subject-tree/subject-document")
api.add_resource(UpdateSubjectTreeAPI, "/subject-tree/update/<string:idOrCode>")
api.add_resource(CreateSubjectTreeAPI, "/subject-tree/create")
api.add_resource(DeleteSubjectTreeAPI, "/subject-tree/delete/<string:idOrCode>")
api.add_resource(DocumentSegmentTreeElasticAPI, "/document-segment-tree/elastic/<int:page>/<int:quantity>")
api.add_resource(SuggestTreeAPI, "/subject-tree/suggest-tree")
api.add_resource(IndexDocumentTreeStaticAPI, "/subject-tree/index/static")
