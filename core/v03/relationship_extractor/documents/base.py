from core.common.mongo.client import get_mongo_client
from pymongo import MongoClient
import json
import sys
import re
import os
import asyncio
import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.common.llms import LLMs
from core.v03.relationship_extractor.utils import extract_brief
from constants import LLMsConfigExtractRelationship
from core.common.elastic import ElasticSearcher

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

EXTRACT_RELATIONSHIP_DOCUMENT_LEVEL_FROM_BRIEF_PROMPT = load_prompt_by_title(
    r"# Prompt 2: Trích xuất mối quan hệ căn cứ từ văn bản"
)


async def __relationship_document_level_extract_from_brief(document_title, document_brief, client: httpx.AsyncClient):
    document_title = document_title.strip()
    document_brief = document_brief.strip()

    prompt = EXTRACT_RELATIONSHIP_DOCUMENT_LEVEL_FROM_BRIEF_PROMPT.format(
        document_title=document_title,
        document_brief=document_brief
    )

    response = await LLMs.llms_async(prompt, client=client)
    dictionary = LLMs.llms_post_process(response)
    return dictionary


async def extract_relationship_base(content, document_name, client: httpx.AsyncClient, semaphore: asyncio.Semaphore):
    
    brief = extract_brief(content)      
    try:
        async with semaphore:
            dictionary = await __relationship_document_level_extract_from_brief(document_brief=brief, document_title=document_name, client=client)
    except Exception as e:
        dictionary = None
        logger.error("extract_relationship_failed", action="extract_relationship_base", **{"error.code": "LLM", "error.message": str(e)}, document_name=document_name, exc_info=True)
    return dictionary
    

if __name__ == '__main__':
    from pymongo import MongoClient
    from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig

    client = get_mongo_client()

    db = client[MigrateConfig.MIGRATE_CORE_DB]

    documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
    segment_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
    
    document_id = '661349'   
    document = documents_collection.find_one({'doc_id': document_id})
    elastic_searcher = ElasticSearcher()
    content = elastic_searcher.get_document_content(document_id)
    logger.debug("retrieve_document_content_successful", action="__main__", document_id=document_id, content_len=len(content) if content else 0)
    # extract_relationship_base(content=content, document_name=document['doc_title'])

    result = extract_relationship_base(
        content=content,
        document_name=document['doc_title']
    )

    logger.info("list_base_documents_info", action="__main__")
    for idx, doc in enumerate(result.get('base', []), 1):
        logger.info("show_base_document_info", action="__main__", index=idx, document=doc)