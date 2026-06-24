import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.common.elastic import ElasticSearcher
from core.v03.content_extractor.components.extract_clauds import extract_clauds
from core.v03.content_extractor.components.extract_segments import extract_segments


def extract_components(content, document_code=None):
    segments = []
    try:
        segments = extract_segments(content, document_code)
        for segment in segments:
                segment_code = segment['code']
                clauds_rs = []
                try:
                    segment_content = segment['article_content']        
                    clauds = extract_clauds(segment_content)                
                    clauds_rs = clauds['clauds']
                except Exception as e:
                    logger.error("extract_claud_failed", action="extract_components", **{"error.code": "PARSE", "error.message": str(e)}, segment_code=segment_code, exc_info=True)                
                segment['clauds'] = clauds_rs                            
    except Exception as e:
        logger.error("extract_segment_failed", action="extract_components", **{"error.code": "PARSE", "error.message": str(e)}, exc_info=True)  
    return segments


if __name__ == '__main__':
        
    import time
    start_time = time.time()    
    elastic_searcher = ElasticSearcher()
    content = elastic_searcher.get_document_content(doc_id='52491')
    segments = extract_components(content=content)
    logger.info("extract_completed", action="extract_components", segment_count=len(segments))  
    logger.debug("extract_result", action="extract_components", segments=segments)  
    logger.debug("extract_timing", action="extract_components", elapsed_seconds=time.time() - start_time)