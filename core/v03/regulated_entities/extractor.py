from core.common.mongo.client import get_mongo_client
import unicodedata
import uuid
import json
from datetime import datetime
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname((__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging
import httpx
import asyncio

setup_logging()
logger = structlog.get_logger()

from pymongo import MongoClient
from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig
from core.common.llms import LLMs
from constants import LLMsConfigExtractRelationship

llm_instance = LLMs(llms_config=LLMsConfigExtractRelationship)

CREATED_BY = "System"
CREATED_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
law_regulated_entities_collection = db[MongoDBCollectionConfig.LAW_REGULATED_OBJECT_COLLECTION_NAME]
law_regulated_object_mapping_collection = db[MongoDBCollectionConfig.LAW_REGULATED_OBJECT_MAPPING_COLLECTION_NAME]

PATH_FILE_PROMPT = os.path.join(PROJECT_ROOT, "core/v03/regulated_entities/utils/prompts.md")
logger.debug("prompt_path_configured", action="module", path=PATH_FILE_PROMPT)


def load_prompt_template(file_path: str) -> str:
    """
    Load the prompt template from a .md file.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error("found_no_prompt_file", action="load_prompt_template", **{"error.code": "IO", "error.message": f"File not found: {file_path}"}, exc_info=True)
        raise
    except Exception as e:
        logger.error("found_no_prompt_file", action="load_prompt_template", **{"error.code": "IO", "error.message": str(e)}, file_path=file_path, exc_info=True)
        raise


def generate_regulated_entities(content: str):
    prompt_template = load_prompt_template(PATH_FILE_PROMPT)
    prompt = prompt_template.format(content=content)
    logger.debug("prepare_llm_prompt", action="generate_regulated_entities", prompt_length=len(prompt))
    response = llm_instance.llms(prompt)    
    return response

async def generate_regulated_entities_async(content: str, client: httpx.AsyncClient, semaphore: asyncio.Semaphore):
    prompt_template = load_prompt_template(PATH_FILE_PROMPT)
    prompt = prompt_template.format(content=content)
    logger.debug("prepare_llm_prompt", action="generate_regulated_entities_async", prompt_length=len(prompt))
    async with semaphore:
        response = await llm_instance.llms_async(prompt, client=client)
    return response



def normalize_text(content: str) -> str:
    if not content:
        return ""

    text = unicodedata.normalize('NFD', content)

    text = ''.join(
        ch for ch in text
        if unicodedata.category(ch) != 'Mn'
    )
    return text.lower()

def convert_to_data_model(data):        
    final_results = []
    final_results_mapping = []    
    
    content = data.get('content', '')
    doc_id = data.get('doc_id', '')
    results = data.get('results', {}).get('doi_tuong_dieu_chinh', [])
    for result in results:
        if len(result) == 0:
            continue
        data_raw = {
            "regulated_object_id": str(uuid.uuid4()),
            "regulated_object_name": result,
            "regulated_object_name_norm": normalize_text(result),
            "status": "ACTIVE",
            "created_at": CREATED_AT,
            "created_by": CREATED_BY,
            "last_modified_at": CREATED_AT,
            "last_modified_by": CREATED_BY
        }

        data_mapping = {
            'doc_id': doc_id,
            'regulated_object_id': data_raw.get('regulated_object_id',''),
            'relation_type': "PRIMARY",
            "created_at": CREATED_AT,
            "created_by": CREATED_BY,
            "last_modified_at": CREATED_AT,
            "last_modified_by": CREATED_BY

        }

        final_results.append(data_raw)
        final_results_mapping.append(data_mapping)

    return final_results, final_results_mapping


if __name__ == '__main__':
    query = {
        "$and": [
            {
                "category_id": "20250300001ABC"
            },
            {
                "issuing_level_id": "1d583b10-0d3e-4a63-b77a-e5c2a23c24cb"
            },
            {
                "effective_status_id": "20250300001HLU"
            },
            {
                "doc_code": { "$not": { "$regex": "QĐ-UB" } }
            },
            {
                "$or": [
                    {
                        "type_id": {
                            "$in": [
                                "20250300003WEH",
                                "20250300008DM1",
                                "20250300006DGT",
                                "20250300014KJG",
                                "20250300015YPU",
                                "20250300016FBN",
                                "202503000202MJ",
                                "20250300026AZT",
                                "20250300029L2A",
                                "20250300031WBA",
                                "20240700001LBV"
                            ]
                        }
                    },
                    {
                        "$and": [
                            {
                                "type_id": {
                                    "$in": ["20250300023QVD", "20250300025AOK"]
                                }
                            },
                            {
                                "doc_code": {
                                    "$regex": "^\\d+/\\d{4}/.*$",
                                    "$options": "i"
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    }

    documents = list(law_documents_collection.find(query,{"_id":0, 'doc_id':1}))
    doc_ids = [doc.get('doc_id') for doc in documents]
    articles = list(law_articles_collection.find({'doc_id': {"$in": doc_ids}, "article_title": {"$regex": "Phạm vi điều chỉnh"}}))

    results = []
    for article in articles[:2]:
        article_id = article.get('article_id','')
        doc_id = article.get('doc_id','')
        article_title = article['article_title']
        article_content = article['article_content']
        content = article_title + '\n' + article_content
        result = generate_regulated_entities(content)
        if result:
            data = {
                'doc_id': doc_id,
                'article_id': article_id,
                'content': content,
                'results': result
            }
            results.append(data)
            
    for result in results:
        converted_results, converted_mappings = convert_to_data_model(result)
        law_regulated_entities_collection.insert_many(converted_results)
        law_regulated_object_mapping_collection.insert_many(converted_mappings)
        logger.info("regulated_entities_inserted", action="main", article_id=result['article_id'], entity_count=len(converted_results))

    