from core.common.mongo.client import get_mongo_client
import json
import sys
import os
import re
import asyncio
import httpx
from typing import Dict, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from constants import LLMsConfigExtractRelationship
from core.common.llms import LLMs
from core.v03.relationship_extractor.utils import remove_reference, remove_article, remove_multi_underline, extract_doc_number

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

EXTRACT_RELATIONSHIP_AMEND_PROMPT = load_prompt_by_title(
    r"# Prompt 1: Trích xuất mối quan hệ sửa đổi, bổ sung"
)

    
def __is_amend_document_candidate(article_title, article_content):
    if (article_title.lower().find('. sửa đổi') != -1 \
        or article_content.lower().find('. sửa đổi') != -1 \
        or article_title.lower().find('sửa đổi') != -1 \
        or article_content.lower().find('sửa đổi') != -1\
        or article_title.lower().find('. hiệu lực thi hành') != -1) \
        and article_title.lower().find('phụ lục') == -1:
        return True
    return False

def __is_add_document_candidate(article_title, article_content):
    if (article_title.lower().find('. bổ sung') != -1 \
        or article_content.lower().find('. bổ sung') != -1 \
        or article_title.lower().find('bổ sung') != -1 \
        or article_content.lower().find('bổ sung') != -1):
        return True
    return False

def __clean_article_content(article_content: str) -> str:
    """
    Xóa toàn bộ nội dung kể từ từ 'PHỤ LỤC' trở đi.
    Nếu không tìm thấy 'PHỤ LỤC' thì giữ nguyên nội dung.
    """
    parts = article_content.split("PHỤ LỤC", 1)

    if len(parts) > 1:
        keep_len = len(parts[0])
        return article_content[:keep_len].rstrip()
    return article_content


def filter_relationship_results(relationships: Dict[str, List[str]], document_name: str) -> Dict[str, List[str]]:
    """
    - Loại bỏ chính văn bản đầu vào
    - Loại bỏ các văn bản trùng số hiệu
    """

    source_doc_number = extract_doc_number(document_name)

    unique_amend = {}
    for doc in relationships.get('amend', []):
        doc_number = extract_doc_number(doc)

        # Bỏ nếu là chính văn bản gốc
        if doc_number == source_doc_number:
            logger.warning("remove_self_reference_invalid", action="filter_relationship_results", doc=doc, doc_type="amend")
            continue

        # Chống trùng: giữ lại tên ĐẦY ĐỦ hơn (dài hơn) khi LLM trả cùng văn bản
        # ở nhiều dạng (ngắn vs đầy đủ) -> tránh giữ bản rút gọn.
        if doc_number in unique_amend:
            if len(doc) > len(unique_amend[doc_number]):
                logger.warning("remove_duplicate_document_invalid", action="filter_relationship_results", doc=unique_amend[doc_number], doc_type="amend")
                unique_amend[doc_number] = doc
            else:
                logger.warning("remove_duplicate_document_invalid", action="filter_relationship_results", doc=doc, doc_type="amend")
            continue

        unique_amend[doc_number] = doc

    unique_add = {}
    for doc in relationships.get('add', []):
        doc_number = extract_doc_number(doc)

        if doc_number == source_doc_number:
            logger.warning("remove_self_reference_invalid", action="filter_relationship_results", doc=doc, doc_type="add")
            continue

        if doc_number in unique_add:
            if len(doc) > len(unique_add[doc_number]):
                logger.warning("remove_duplicate_document_invalid", action="filter_relationship_results", doc=unique_add[doc_number], doc_type="add")
                unique_add[doc_number] = doc
            else:
                logger.warning("remove_duplicate_document_invalid", action="filter_relationship_results", doc=doc, doc_type="add")
            continue

        unique_add[doc_number] = doc

    return {
        'amend': list(unique_amend.values()),
        'add': list(unique_add.values())
    }


async def extract_relationship_amend(segments, document_name, client: httpx.AsyncClient, semaphore: asyncio.Semaphore): 
    '''
        Trích xuất mối quan hệ sửa đổi, bổ sung
    '''       
    relationships = {
        'amend': [],
        'add': []        
    }    
    
    async def process_seg(segment):
        article_title = segment['article_title']
        article_content = remove_reference(segment['article_content'])
        article_content = __clean_article_content(article_content)
        
        if not __is_amend_document_candidate(article_title, article_content)\
            and not __is_add_document_candidate(article_title, article_content):
            return None
        
        logger.debug("process_article_started", action="extract_relationship_amend", article_title=article_title, content_len=len(article_content))

        prompt = EXTRACT_RELATIONSHIP_AMEND_PROMPT.format(
            document_name=document_name,
            article_title=remove_article(article_title),
            article_content=remove_multi_underline(article_content)
        )
        try:
            async with semaphore:
                answer = await LLMs.llms_async(prompt, client=client)    
            relationship_rs = LLMs.llms_post_process(answer)                                
            logger.info("extract_relationship_completed", action="extract_relationship_amend", relationship_rs=relationship_rs)        
            return relationship_rs
        except Exception as e:
            logger.error("extract_relationship_failed", action="extract_relationship_amend", **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
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
        if relationship_rs is not None and 'amend' in relationship_rs:
            relationships['amend'].extend(relationship_rs['amend'])
        if relationship_rs is not None and 'add' in relationship_rs:
            relationships['add'].extend(relationship_rs['add'])
    relationships = filter_relationship_results(relationships, document_name)

    return relationships

    
async def main():
    import asyncio
    from pymongo import MongoClient
    from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig

    client = get_mongo_client()

    db = client[MigrateConfig.MIGRATE_CORE_DB]

    documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]

    document_id = '633116'    
    document = documents_collection.find_one({'doc_id': document_id})
    from core.v03.content_extractor import extract_components
    segments = extract_components(document['doc_content'])

    logger.info("process_document_started", action="__main__", doc_title=document['doc_title'], segment_count=len(segments))  

    http_client = httpx.AsyncClient()
    semaphore = asyncio.Semaphore(10)

    result = await extract_relationship_amend(
        segments=segments,
        document_name=document['doc_title'],
        client=http_client,
        semaphore=semaphore
    )
    logger.info("extract_relationship_amend_successful", action="__main__", result=result)
    for idx, doc in enumerate(result.get('amend', []), 1):
        logger.info("show_amend_document_successful", action="__main__", index=idx, doc_name=doc)

    for idx, doc in enumerate(result.get('add', []), 1):
        logger.info("show_add_document_successful", action="__main__", index=idx, doc_name=doc)

    await http_client.aclose() 
        
if __name__ == '__main__':
    asyncio.run(main())
    