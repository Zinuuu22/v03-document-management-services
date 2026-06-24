import os
import sys
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.common.textspliter import FixedRecursiveCharacterTextSplitter
from core.common.llms import LLMs
from constants import EmbeddingConfig, LLMsConfigExtractKeywords
import httpx
import asyncio

TEXT_SPLITTER = FixedRecursiveCharacterTextSplitter(chunk_size=EmbeddingConfig.MAX_CHUNK_SIZE)
LLMs = LLMs(llms_config=LLMsConfigExtractKeywords)
PATH_PROMPT_JSON = os.path.join(PROJECT_ROOT, 'core/v03/keywords_extractor/utils/prompts.json')
try:
    if os.path.exists(PATH_PROMPT_JSON):
        with open(PATH_PROMPT_JSON, "r", encoding="utf-8") as file:
            PROMPTS = json.load(file)
except Exception as e:        
    logger.error("load_prompts_failed", **{"error.code": "IO", "error.message": str(e)}, exc_info=True)


def __prepocess(content):
    content = content.replace('\"', '\'')
    content = content.replace('\”', '\'')
    content = content.replace('\;', '\,')    
    contents = TEXT_SPLITTER.split_text(content)     
    return contents[:5]
    

def get_prompts_extract_keywords(content, version='version_1'):    
    preprocessed_contents = __prepocess(content)
    logger.debug("content_preprocessed", action="get_prompts_extract_keywords", content_count=len(preprocessed_contents))
    
    prompts = []
    for content in preprocessed_contents:
        prompt = PROMPTS[version]["prompt"].format(content=content)
        prompts.append(prompt)
    return prompts


def extract_keywords_wrapper(prompt, responses):
    """Thread-safe wrapper for keyword extraction"""
    try:
        response = LLMs.llms(prompt=prompt)    
        responses.append(response)
    except Exception as e:
        logger.error("extract_keyword_failed", action="extract_keywords_wrapper", **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
        responses.append(None)  

async def extract_keywords_wrapper_async(prompt, responses, client: httpx.AsyncClient, semaphore: asyncio.Semaphore):
    """Async wrapper for keyword extraction"""
    try:
        async with semaphore:
            response = await LLMs.llms_async(prompt=prompt, client=client)    
        responses.append(response)
    except Exception as e:
        logger.error("extract_keyword_failed", action="extract_keywords_wrapper_async", **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
        responses.append(None)
    

def format_response(responses):    
    keywords = set()    
    result = []        
    for response in responses:
        response = response.split("</think>")[-1].strip()     
        try:
            lines = response.strip().split('\n')
            for line in lines:
                if len(line.strip()) == 0:
                    continue
                try:
                    remain, li_do = line.split('Lý do:')                
                    remain, do_tin_cay = remain.split('Độ tin cậy:')
                    tu_khoa = remain.split('###Từ khóa:')[1]
                    item = {
                        'key': tu_khoa[:-2].strip(),
                        'value': do_tin_cay.strip().split('%')[0],
                        'reason': li_do[:-2].strip()
                    }        
                    
                    if item['key'] not in keywords and int(item['value']) > 90:
                        result.append(item)
                        keywords.add(item['key'])
                except:
                    pass        
        except:
            pass
    return result
