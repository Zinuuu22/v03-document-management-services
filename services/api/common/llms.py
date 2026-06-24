import os
import sys
from flask_restful import Resource, reqparse
from flask import Response
import structlog
import json
from typing import Dict, Any, Optional

# Project setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from services.api import api
from core.common.llms import LLMs
from constants import LLMsConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

# Initialize LLMs instance (lowercase for Python convention)
llms = LLMs()

def dict_to_json(data: Dict[Any, Any], indent: Optional[int] = None, ensure_ascii: bool = False) -> str:
    try:
        return json.dumps(
            data,
            indent=indent,
            ensure_ascii=ensure_ascii,
            default=str
        )
    except TypeError as e:
        logger.error("dict_to_json_failed", action="dict_to_json", **{"error.code": "PARSE", "error.message": str(e)}, exc_info=True)
        raise ValueError(f"Failed to convert dictionary to JSON: {str(e)}")


class LLMsAnswerAPI(Resource):        
    def post(self):
        # Define parser once to avoid redefinition per request
        parser = reqparse.RequestParser()
        parser.add_argument('prompt', type=str, required=True, help="Prompt is required", location='json')
        parser.add_argument('llms_base_url', type=str, required=False, location='json')
        parser.add_argument('llms_model_name', type=str, required=False, location='json')
        parser.add_argument('content', type=str, required=False, location='json')
        parser.add_argument('temperature', type=float, required=False, location='json')
        parser.add_argument('max_new_tokens', type=int, required=False, location='json')
        parser.add_argument('top_k', type=int, required=False, location='json')
        parser.add_argument('top_p', type=float, required=False, location='json')  # Fixed type to float
        parser.add_argument('do_sample', type=bool, required=False, location='json')  # Fixed type to bool
        parser.add_argument('repetition_penalty', type=float, required=False, location='json')
        

        logger.debug("llms_answer_parse_args", action="post")
        args = parser.parse_args()
        prompt = args['prompt']

        # Create a new LLMsConfig instance to avoid modifying the global config
        logger.debug("llms_answer_load_config", action="post")
        config = LLMsConfig()

        # Override config parameters if provided        
        if args.get('llms_base_url') is not None:
            config.LLMS_BASE_URL = args['llms_base_url']
        if args.get('llms_model_name') is not None:
            config.LLMS_MODEL_NAME = args['llms_model_name']
        if args.get('content') is not None:
            config.PARAM_CONTENT = args['content']
        if args.get('temperature') is not None:
            if not 0.0 <= args['temperature'] <= 2.0:
                return {'status': False, 'message': 'Temperature must be between 0.0 and 2.0'}, 400
            config.PARAM_TEMPERATURE = args['temperature']
        if args.get('max_new_tokens') is not None:
            if args['max_new_tokens'] < 1 or args['max_new_tokens'] > 2048:
                return {'status': False, 'message': 'max_new_tokens must be between 1 and 2048'}, 400                
            config.PARAM_MAX_NEW_TOKENS = args['max_new_tokens']
        if args.get('top_k') is not None:
            if args['top_k'] < 1 or args['top_k'] > 100:
                return {'status': False, 'message': 'top_k must be between 1 and 100'}, 400
            config.PARAM_TOP_K = args['top_k']
        if args.get('top_p') is not None:
            if not 0.0 <= args['top_p'] <= 1.0:
                return {'status': False, 'message': 'top_p must be between 0.0 and 1.0'}, 400                
            config.PARAM_TOP_P = args['top_p']
        if args.get('do_sample') is not None:
            config.PARAM_DO_SAMPLE = str(args['do_sample'])
        if args.get('repetition_penalty') is not None:
            if not 1.0 <= args['repetition_penalty'] <= 2.0:
                return {'status': False, 'message': 'repetition_penalty must be between 1.0 and 2.0'}, 400                                
            config.PARAM_REPETITION_PENALTY = args['repetition_penalty']

        try:
            # Call LLMs with the updated config
            logger.debug("llms_answer_call_started", action="post", prompt_len=len(prompt))
            answer = llms.llms(prompt=prompt, llms_config=config)
            response = {
                'status': True,
                'message': None,
                'answer': answer
            }
            return Response(
                response=dict_to_json(response, indent=2, ensure_ascii=False),
                status=200,
                mimetype='application/json'
            )
        except Exception as e:
            logger.error("llms_answer_failed", action="post", **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
            response = {
                'status': False,
                'message': f"LLMs answer failed: {str(e)}"
            }
            return Response(
                response=dict_to_json(response, indent=2, ensure_ascii=False),
                status=400,
                mimetype='application/json'
            )

# Register API resources
api.add_resource(LLMsAnswerAPI, '/llms/answer')