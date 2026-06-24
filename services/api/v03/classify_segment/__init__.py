import os
import sys
from typing import List, Dict, Any, Optional
from flask_restful import Resource, reqparse
import structlog
from structlog.contextvars import bind_contextvars
import time
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from services.api import api
from services.api.utils import make_response
from core.v03.segments_classifier import classify_segment
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()


class ClassifySegmentAPI(Resource):
    """API for classify segment API."""

    def post(self) -> Dict[str, List[str]]:
        parser = reqparse.RequestParser()
        parser.add_argument("segment_text", type=str, required=True, nullable=False, location="json")
        
        args = parser.parse_args()
        bind_contextvars(task="ClassifySegmentAPI")
        start_time = time.time()
        logger.debug("classify_segments_started", action="ClassifySegmentAPI", segment_len=len(segment_text))

        segment_text = args["segment_text"].replace("\n \n", "\n\n")
        
        try:
            classification = classify_segment(segment=segment_text)
            
            duration = time.time() - start_time
            logger.info("classify_segments_success", action="ClassifySegmentAPI", **{"event.status": "success", "event.duration": duration})
            return make_response(data=classification, code=0, message="Success"), 200
        except Exception as e:
            duration = time.time() - start_time
            logger.error("classify_segments_failed", action="ClassifySegmentAPI", **{"event.status": "failure", "event.duration": duration, "error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return make_response(data=None, code=2000, message=str(e)), 500


# Register API resources
api.add_resource(ClassifySegmentAPI, "/classification/classify_segment")
