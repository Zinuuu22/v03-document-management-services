from core.common.mongo.client import get_mongo_client
import json
import sys
import os
import asyncio
import httpx
from typing import Dict, List
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.common.llms import LLMs
from core.v03.relationship_extractor.utils import remove_reference, remove_article, remove_multi_underline
from constants import LLMsConfigExtractRelationship

#Call LLMs
LLMs = LLMs(llms_config=LLMsConfigExtractRelationship)
MD_FILE_PATH = f"{PROJECT_ROOT}/core/v03/relationship_extractor/utils/prompts_relationship_document.md"

def load_prompt_by_title(title_pattern: str):
    with open(MD_FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = rf"({title_pattern}.*?)(?=\n# Prompt|\Z)"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(1).strip()
    return None

EXTRACT_RELATIONSHIP_REPEAL_PROMPT = load_prompt_by_title(
    r"# Prompt 4: Trích xuất mối quan hệ bãi bỏ từ văn bản"
)

def clean_text(text: str) -> str:
    """
    Remove everything from 'Nơi nhận:' (case-insensitive) to the end of the text.
    Returns cleaned text.
    """
    # Regex tìm 'Nơi nhận:' và tất cả phía sau nó
    cleaned = re.sub(r"Nơi nhận:.*$", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    return cleaned

def __is_repeal_document_candidate(article_title, article_content):
    if article_content.lower().find("bãi bỏ") == -1 \
        and article_content.lower().find("chấm dứt hiệu lực") == -1\
        and article_title.lower().find('bãi bỏ') == -1\
        and article_title.lower().find("chấm dứt hiệu lực") == -1\
        and article_title.lower().find("hiệu lực thi hành") == -1\
        and article_title.lower().find("điều khoản thi hành") == -1:
            return False
    return True

async def extract_relationship_repeal(segments, document_name, client: httpx.AsyncClient, semaphore: asyncio.Semaphore):        
    relationships = {
        'repeal_full': [],
        'repeal_apart': []
    }  
    
    async def process_seg(segment):
        article_title = segment['article_title']
        article_content = remove_reference(segment['article_content'])
        article_content = clean_text(article_content)
        
        if not __is_repeal_document_candidate(article_title, article_content):
            return None       
        
        prompt = EXTRACT_RELATIONSHIP_REPEAL_PROMPT.format(
            document_name=document_name,
            article_title=remove_article(article_title),
            article_content=remove_multi_underline(article_content)
        )      

        try:
            async with semaphore:
                answer = await LLMs.llms_async(prompt, client=client)    
            relationship_rs = LLMs.llms_post_process(answer)                                
            return relationship_rs
        except Exception as e:
            logger.error("extract_relationship_failed", action="extract_relationship_repeal", **{"error.code": "LLM", "error.message": str(e)}, article_title=article_title[:50], exc_info=True)
            return None      

    results = []
    batch_size = 20
    for i in range(0, len(segments), batch_size):
        chunk = segments[i : i + batch_size]
        logger.info("processing_batch", 
                    start_index=i, 
                    end_index=i + len(chunk), 
                    total=len(segments))
        tasks = [process_seg(seg) for seg in chunk]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        results.extend(batch_results)
        
    for relationship_rs in results:
        if relationship_rs is not None and 'repeal_full' in relationship_rs:
            relationships['repeal_full'].extend(relationship_rs['repeal_full']) 
        if relationship_rs is not None and 'repeal_apart' in relationship_rs:
            relationships['repeal_apart'].extend(relationship_rs['repeal_apart']) 
            
    return relationships

if __name__ == '__main__':
    from pymongo import MongoClient
    from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig

    client = get_mongo_client()

    db = client[MigrateConfig.MIGRATE_CORE_DB]

    documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
    segment_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
    
    document_id = '672076'
    
    document = documents_collection.find_one({'doc_id': document_id})
    segments = list(segment_collection.find({'doc_id': document_id}))      
    result = extract_relationship_repeal(segments=segments, document_name=document['doc_title'])
    logger.info("extract_repeal_relationships_successful", action="__main__", result=result)