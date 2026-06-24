from core.common.mongo.client import get_mongo_client
import structlog
import sys
import uuid
import os
from flask_restful import Resource, reqparse
from pymongo import MongoClient
from datetime import datetime, date
from services.api import api
from typing import Dict, Any
from pymongo.errors import PyMongoError

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

from services.api.utils.response import make_response
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from structlog.contextvars import bind_contextvars
import time
logger = structlog.get_logger()



# Connect MongoDB
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]
law_signers_collection = db[MongoDBCollectionConfig.LAW_SIGNERS_COLLECTION_NAME]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_agencies_collection = db[MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME]


def parse_date(value: str) -> date:
    """Parse string to datetime.date, expecting YYYY-MM-DD format."""
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        logger.error("parse_date_failed", action="parse_date", **{"error.code": "400-VAL", "error.message": "Date must be in YYYY-MM-DD format (e.g., 2024-01-01)", "event.status": "failure"}, exc_info=True)
        return None

class LawStatisticsBySignerAPI(Resource):
    """API for statistics of law documents by signer"""
    
    def post(self) -> Dict[str, Any]:
        """Handle POST request to get statistics of law documents by signer.

        Returns:
            Response with statistics (code, name, count) or error message.
        """
        bind_contextvars(task="LawStatisticsBySignerAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('decreeIssuedFrom', type=str, required=False, nullable=True, location='json', help="Issue date from (YYYY-MM-DD)")
        parser.add_argument('decreeIssuedTo', type=str, required=False, nullable=True, location='json', help="Issue date to (YYYY-MM-DD)")
        parser.add_argument('decreeEffectFrom', type=str, required=False, nullable=True, location='json', help="Effective date from (YYYY-MM-DD)")
        parser.add_argument('decreeEffectTo', type=str, required=False, nullable=True, location='json', help="Effective date to (YYYY-MM-DD)")
        args = parser.parse_args()

        decree_issued_from = args.get('decreeIssuedFrom', None)
        decree_issued_to = args.get('decreeIssuedTo', None)
        decree_effect_from = args.get('decreeEffectFrom', None)
        decree_effect_to = args.get('decreeEffectTo', None)

        if decree_issued_from:
            decree_issued_from = parse_date(decree_issued_from)
        if decree_issued_to:
            decree_issued_to = parse_date(decree_issued_to)
        if decree_effect_from:
            decree_effect_from = parse_date(decree_effect_from)
        if decree_effect_to:
            decree_effect_to = parse_date(decree_effect_to)
        
        logger.debug("get_law_statistics_by_signer", action="post", **{"event.duration": time.time()-start_t}, decreeIssuedFrom=decree_issued_from, decreeIssuedTo=decree_issued_to, decreeEffectFrom=decree_effect_from, decreeEffectTo=decree_effect_to)

        try:
            # Validate date ranges
            if decree_issued_from and decree_issued_to and decree_issued_from > decree_issued_to:
                logger.error("get_law_statistics_by_signer_failed", action="post", **{"error.code": "400-VAL", "error.message": "decreeIssuedFrom must be before decreeIssuedTo", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code=1000, message="decreeIssuedFrom must be before decreeIssuedTo"), 400
            if decree_effect_from and decree_effect_to and decree_effect_from > decree_effect_to:
                logger.error("get_law_statistics_by_signer_failed", action="post", **{"error.code": "400-VAL", "error.message": "decreeEffectFrom must be before decreeEffectTo", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code=1000, message="decreeEffectFrom must be before decreeEffectTo"), 400

            issue_from_dt = datetime.combine(decree_issued_from, datetime.min.time()) if decree_issued_from else None
            issue_to_dt = datetime.combine(decree_issued_to, datetime.max.time()) if decree_issued_to else None
            effect_from_dt = datetime.combine(decree_effect_from, datetime.min.time()) if decree_effect_from else None
            effect_to_dt = datetime.combine(decree_effect_to, datetime.max.time()) if decree_effect_to else None

            logger.debug("get_law_statistics_by_signer", action="post", **{"event.duration": time.time()-start_t}, issue_from=issue_from_dt, issue_to=issue_to_dt, effect_from=effect_from_dt, effect_to=effect_to_dt, data_source="MongoDB")

            # Handler for both string and datetime
            pipeline = [{
                "$addFields": {
                    "doc_issue_date_converted": {
                        "$cond": {
                            "if": {"$eq": [{"$type": "$doc_issue_date"}, "string"]},
                            "then": {"$dateFromString": {"dateString": "$doc_issue_date", "onError": None}},
                            "else": "$doc_issue_date"
                        }
                    },
                    "doc_effective_date_converted": {
                        "$cond": {
                            "if": {"$eq": [{"$type": "$doc_effective_date"}, "string"]},
                            "then": {"$dateFromString": {"dateString": "$doc_effective_date", "onError": None}},
                            "else": "$doc_effective_date"
                        }
                    }
                }
            }]

            match_stage = {}
            if issue_from_dt or issue_to_dt:
                match_stage['doc_issue_date_converted'] = {}
                if issue_from_dt:
                    match_stage['doc_issue_date_converted']['$gte'] = issue_from_dt
                if issue_to_dt:
                    match_stage['doc_issue_date_converted']['$lte'] = issue_to_dt
            if effect_from_dt or effect_to_dt:
                match_stage['doc_effective_date_converted'] = {}
                if effect_from_dt:
                    match_stage['doc_effective_date_converted']['$gte'] = effect_from_dt
                if effect_to_dt:
                    match_stage['doc_effective_date_converted']['$lte'] = effect_to_dt
                match_stage['doc_effective_date_converted']['$ne'] = None

            if match_stage:
                pipeline.append({"$match": match_stage})

            pipeline.extend([
                {"$unwind": "$signer_ids"},
                {
                    "$group": {
                        "_id": "$signer_ids",
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$lookup": {
                        "from": "law_signers",
                        "localField": "_id",
                        "foreignField": "signer_id",
                        "as": "signer"
                    }
                },
                {"$unwind": "$signer"},
                {
                    "$project": {
                        "_id": 0,
                        "code": "$_id",
                        "name": "$signer.signer_name",
                        "count": 1
                    }
                }
            ])

            logger.debug("get_law_statistics_by_signer", action="post", **{"event.duration": time.time()-start_t}, pipeline_stages=len(pipeline), has_date_filters=bool(match_stage))
            results = list(law_documents_collection.aggregate(pipeline))
            logger.debug("get_law_statistics_by_signer", action="post", **{"event.duration": time.time()-start_t}, signer_count=len(results))

            response_data = results if results else []

            logger.info("get_law_statistics_by_signer_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(response_data))
            return make_response(
                data=response_data,
                code=0,
                message="Statistics retrieved successfully"
            ), 200

        except PyMongoError as e:
            logger.error("get_law_statistics_by_signer_failed", action="post", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("get_law_statistics_by_signer_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500


class LawStatisticsByAgencyIssuedAPI(Resource):
    """API for statistics of law documents by agency issued"""
    
    def post(self) -> Dict[str, Any]:
        """Handle POST request to get statistics of law documents by agency issued.

        Returns:
            Response with statistics (code, name, count) or error message.
        """
        bind_contextvars(task="LawStatisticsByAgencyIssuedAPI")
        start_t = time.time()
        parser = reqparse.RequestParser()
        parser.add_argument('decreeIssuedFrom', type=str, required=False, nullable=True, location='json', help="Issue date from (YYYY-MM-DD)")
        parser.add_argument('decreeIssuedTo', type=str, required=False, nullable=True, location='json', help="Issue date to (YYYY-MM-DD)")
        parser.add_argument('decreeEffectFrom', type=str, required=False, nullable=True, location='json', help="Effective date from (YYYY-MM-DD)")
        parser.add_argument('decreeEffectTo', type=str, required=False, nullable=True, location='json', help="Effective date to (YYYY-MM-DD)")
        args = parser.parse_args()

        decree_issued_from = args.get('decreeIssuedFrom', None)
        decree_issued_to = args.get('decreeIssuedTo', None)
        decree_effect_from = args.get('decreeEffectFrom', None)
        decree_effect_to = args.get('decreeEffectTo', None)

        if decree_issued_from:
            decree_issued_from = parse_date(decree_issued_from)
        if decree_issued_to:
            decree_issued_to = parse_date(decree_issued_to)
        if decree_effect_from:
            decree_effect_from = parse_date(decree_effect_from)
        if decree_effect_to:
            decree_effect_to = parse_date(decree_effect_to)

        logger.debug("get_law_statistics_by_agency_issued", action="post", **{"event.duration": time.time()-start_t}, decreeIssuedFrom=decree_issued_from, decreeIssuedTo=decree_issued_to, decreeEffectFrom=decree_effect_from, decreeEffectTo=decree_effect_to)

        try:
            # Validate date ranges
            if decree_issued_from and decree_issued_to and decree_issued_from > decree_issued_to:
                logger.error("get_law_statistics_by_agency_issued_failed", action="post", **{"error.code": "400-VAL", "error.message": "decreeIssuedFrom must be before decreeIssuedTo", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code=1000, message="decreeIssuedFrom must be before decreeIssuedTo"), 400
            if decree_effect_from and decree_effect_to and decree_effect_from > decree_effect_to:
                logger.error("get_law_statistics_by_agency_issued_failed", action="post", **{"error.code": "400-VAL", "error.message": "decreeEffectFrom must be before decreeEffectTo", "event.duration": time.time()-start_t, "event.status": "failure"})
                return make_response(data=None, code=1000, message="decreeEffectFrom must be before decreeEffectTo"), 400

            issue_from_dt = datetime.combine(decree_issued_from, datetime.min.time()) if decree_issued_from else None
            issue_to_dt = datetime.combine(decree_issued_to, datetime.max.time()) if decree_issued_to else None
            effect_from_dt = datetime.combine(decree_effect_from, datetime.min.time()) if decree_effect_from else None
            effect_to_dt = datetime.combine(decree_effect_to, datetime.max.time()) if decree_effect_to else None

            logger.debug("get_law_statistics_by_agency_issued", action="post", **{"event.duration": time.time()-start_t}, issue_from=issue_from_dt, issue_to=issue_to_dt, effect_from=effect_from_dt, effect_to=effect_to_dt, data_source="MongoDB")

            # Handler for both string and datetime
            pipeline = [{
                "$addFields": {
                    "doc_issue_date_converted": {
                        "$cond": {
                            "if": {"$eq": [{"$type": "$doc_issue_date"}, "string"]},
                            "then": {"$dateFromString": {"dateString": "$doc_issue_date", "onError": None}},
                            "else": "$doc_issue_date"
                        }
                    },
                    "doc_effective_date_converted": {
                        "$cond": {
                            "if": {"$eq": [{"$type": "$doc_effective_date"}, "string"]},
                            "then": {"$dateFromString": {"dateString": "$doc_effective_date", "onError": None}},
                            "else": "$doc_effective_date"
                        }
                    }
                }
            }]

            match_stage = {}
            if issue_from_dt or issue_to_dt:
                match_stage['doc_issue_date_converted'] = {}
                if issue_from_dt:
                    match_stage['doc_issue_date_converted']['$gte'] = issue_from_dt
                if issue_to_dt:
                    match_stage['doc_issue_date_converted']['$lte'] = issue_to_dt
            if effect_from_dt or effect_to_dt:
                match_stage['doc_effective_date_converted'] = {}
                if effect_from_dt:
                    match_stage['doc_effective_date_converted']['$gte'] = effect_from_dt
                if effect_to_dt:
                    match_stage['doc_effective_date_converted']['$lte'] = effect_to_dt
                match_stage['doc_effective_date_converted']['$ne'] = None

            if match_stage:
                pipeline.append({"$match": match_stage})

            pipeline.extend([
                {"$unwind": "$agency_ids"},
                {
                    "$group": {
                        "_id": "$agency_ids",
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$lookup": {
                        "from": "law_agencies",
                        "localField": "_id",
                        "foreignField": "agency_id",
                        "as": "agency"
                    }
                },
                {"$unwind": "$agency"},
                {
                    "$project": {
                        "_id": 0,
                        "code": "$_id",
                        "name": "$agency.agency_name",
                        "count": 1
                    }
                }
            ])

            logger.debug("get_law_statistics_by_agency_issued", action="post", **{"event.duration": time.time()-start_t}, pipeline_stages=len(pipeline), has_date_filters=bool(match_stage))
            results = list(law_documents_collection.aggregate(pipeline))
            logger.debug("get_law_statistics_by_agency_issued", action="post", **{"event.duration": time.time()-start_t}, agency_count=len(results))

            response_data = results if results else []

            logger.info("get_law_statistics_by_agency_issued_success", action="post", **{"event.duration": time.time()-start_t, "event.status": "success"}, count=len(response_data))
            return make_response(
                data=response_data,
                code=0,
                message="Statistics retrieved successfully"
            ), 200

        except PyMongoError as e:
            logger.error("get_law_statistics_by_agency_issued_failed", action="post", **{"error.code": "500-DB", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-DB"
            response["status"] = False
            return response, 500
        except Exception as e:
            logger.error("get_law_statistics_by_agency_issued_failed", action="post", **{"error.code": "500-SYS", "error.message": str(e), "event.duration": time.time()-start_t, "event.status": "failure"}, exc_info=True)
            response = make_response(data=None, code=2000, message=str(e))
            response["error_code"] = "500-SYS"
            response["status"] = False
            return response, 500

# Register API
api.add_resource(LawStatisticsByAgencyIssuedAPI, '/document-report/agency-issued')
api.add_resource(LawStatisticsBySignerAPI, '/document-report/signer')
