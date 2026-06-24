from core.common.mongo.client import get_mongo_client
import json
import sys
import os
import re
import asyncio
import httpx

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
llm_instance = LLMs(llms_config=LLMsConfigExtractRelationship)
MD_FILE_PATH = f"{PROJECT_ROOT}/core/v03/relationship_extractor/utils/prompts_relationship_document.md"

def load_prompt_by_title(title_pattern: str):
    with open(MD_FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = rf"({title_pattern}.*?)(?=\n# Prompt|\Z)"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(1).strip()
    return None

EXTRACT_RELATIONSHIP_REPLACE_PROMPT = load_prompt_by_title(
    r"# Prompt 5: Trích xuất mối quan hệ thay thế từ văn bản"
)


def __is_replace_document_candidate(article_title, article_content):
    if (article_title.lower().find('hiệu lực thi hành') != -1 or article_title.find('. Hiệu lực') != -1 or article_title.lower().find('điều khoản thi hành') != -1 or article_title.lower().find('tổ chức thực hiện') != -1\
        or article_title.lower().find('và thay thế') != -1 or article_title.lower().find('trách nhiệm thi hành') != -1 or article_title.lower().find('có hiệu lực kể từ') != -1)\
    and (article_title.lower().find('thay thế') != -1 or article_content.lower().find('thay thế') != -1\
        or article_content.lower().find('hết hiệu lực') != -1 or article_content.lower().find('chấm dứt hiệu lực') != -1):
        return True
    return False


async def extract_relationship_replace(segments, document_name, client: httpx.AsyncClient, semaphore: asyncio.Semaphore):        
    relationships = {
        'replace_full': [],
        'replace_apart': []     
    }    
    
    async def process_seg(segment):
        article_title = segment['article_title']
        article_content = remove_reference(segment['article_content'])
        
        if not __is_replace_document_candidate(article_title, article_content):
            return None       
        
        prompt = EXTRACT_RELATIONSHIP_REPLACE_PROMPT.format(
            document_name=document_name,
            article_title=remove_article(article_title),
            article_content=remove_multi_underline(article_content)
        )
        
        try:
            async with semaphore:
                answer = await llm_instance.llms_async(prompt, client=client)    
            relationship_rs = llm_instance.llms_post_process(answer)                                
            return relationship_rs
        except Exception as e:
            logger.error("extract_replace_relationship_failed", action="extract_relationship_replace", **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
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
        if relationship_rs is not None and 'replace_full' in relationship_rs:
            relationships['replace_full'].extend(relationship_rs['replace_full']) 
        if relationship_rs is not None and 'replace_apart' in relationship_rs:
            relationships['replace_apart'].extend(relationship_rs['replace_apart']) 
                                                       
    return relationships


async def main():
    import asyncio
    from pymongo import MongoClient
    from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig

    client = get_mongo_client()

    db = client[MigrateConfig.MIGRATE_CORE_DB]

    documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
    segment_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]  

    document_id = '2463'    
    document = documents_collection.find_one({'doc_id': document_id})
    from core.v03.content_extractor import extract_components
    segments = extract_components(document['doc_content'])

    logger.info("process_document_started", action="__main__", doc_title=document['doc_title'], segment_count=len(segments))  

    http_client = httpx.AsyncClient()
    semaphore = asyncio.Semaphore(10)

    result = await extract_relationship_replace(
        segments=segments,
        document_name=document['doc_title'],
        client=http_client,
        semaphore=semaphore
    )
    logger.info("extract_relationship_replace_successful", action="__main__", result=result)
    for idx, doc in enumerate(result.get('replace_full', []), 1):
        logger.info("show_replace_full_document_successful", action="__main__", index=idx, doc_name=doc)

    for idx, doc in enumerate(result.get('replace_apart', []), 1):
        logger.info("show_replace_apart_document_successful", action="__main__", index=idx, doc_name=doc)

    await http_client.aclose()  
    
if __name__ == '__main__':
    asyncio.run(main())
    