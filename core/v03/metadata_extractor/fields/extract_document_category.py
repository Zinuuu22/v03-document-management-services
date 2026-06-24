import re
from typing import Optional, Dict
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()
sys.path.append(PROJECT_ROOT)
from core.v03.metadata_extractor.utils.regex_pattern import LEGAL_DOCUMENT_TYPES, LEGAL_DOCUMENT_PATTERN


def extract_document_category(document_code: Optional[str], document_type: Optional[str]) -> Dict[str, str]:
    response = {"document_category": "Văn bản Hành Chính"}
    
    # Kiểm tra đầu vào
    if not document_code or not isinstance(document_code, str):
        logger.warning("invalid_document_code", action="extract_document_category", document_code=document_code)
        return response
    
    if not document_type or not isinstance(document_type, str):
        logger.warning("invalid_document_type", action="extract_document_category", document_type=document_type)
        return response

    if document_type.lower() not in LEGAL_DOCUMENT_TYPES:
        logger.warning("document_type_not_in_list", action="extract_document_category", document_type=document_type)
        return response

    if document_type.lower() in {'nghị quyết', 'quyết định'} and not re.match(LEGAL_DOCUMENT_PATTERN, document_code):
        logger.warning("invalid_document_code_pattern", action="extract_document_category", document_type=document_type, document_code=document_code)
        return response
    else:
        logger.debug("valid_document_code", action="extract_document_category", document_code=document_code)
        response["document_category"] = "Văn bản Pháp Luật"        
        return response

if __name__ == '__main__':
    logger.info("extract_result", result=extract_document_category('129/2015/NQ-HĐND', 'Nghị quyết'))
