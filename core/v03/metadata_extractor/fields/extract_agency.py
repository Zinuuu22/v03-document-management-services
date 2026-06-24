import re
import sys
import os
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.common.llms import LLMs
from core.v03.metadata_extractor.utils import get_brief_content
from core.v03.metadata_extractor.utils.regex_pattern import REGEX_PATTERNS_AGENCY
from constants import LLMsConfigExtractMetadata

#Call LLMs
LLms = LLMs(llms_config=LLMsConfigExtractMetadata)

# Load the prompt from JSON file once at module level
JSON_FILE_PATH = f"{PROJECT_ROOT}/core/v03/metadata_extractor/utils/prompts.json"
try:
    with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
        prompt_data = json.load(f)
        EXTRACT_AGENCY_PROMPT = prompt_data["extract_agency_prompt"]
except Exception as e:
    logger.error("load_prompt_failed", **{"error.code": "IO", "error.message": str(e)}, json_path=JSON_FILE_PATH, exc_info=True)


def __llms_extract_agency(txt):
    '''
        Extract agency from content by llms
    '''
    content = get_brief_content(txt)
    logger.debug("prepare_content", action="__llms_extract_agency", content_len=len(content) if content else 0)

    prompt = EXTRACT_AGENCY_PROMPT.format(content=content)

    response = LLms.llms(prompt)
    logger.debug("receive_llm_response", action="__llms_extract_agency", response_len=len(response) if response else 0)
    dictionary = LLms.llms_post_process(response)
    logger.debug("parse_llm_response", action="__llms_extract_agency", dictionary=dictionary)
    return dictionary

def extract_agency(content, document_code):
    '''
        Extract agency from content by llms and document code by regex
    '''
    agencies = []
    llms_agencies = __llms_extract_agency(content)            
    if llms_agencies is not None:
        agencies = [value for _, value in llms_agencies.items()]
        if len(agencies) == 0:
            agencies = __regex_extract_agency(document_code)        
    return agencies


async def __llms_extract_agency_async(txt, client, semaphore):
    '''
        Extract agency from content by llms
    '''
    content = get_brief_content(txt)
    logger.debug("prepare_content", action="__llms_extract_agency", content_len=len(content) if content else 0)

    prompt = EXTRACT_AGENCY_PROMPT.format(content=content)

    async with semaphore:
        response = await LLms.llms_async(prompt, client=client)
    logger.debug("receive_llm_response", action="__llms_extract_agency", response_len=len(response) if response else 0)
    dictionary = LLms.llms_post_process(response)
    logger.debug("parse_llm_response", action="__llms_extract_agency", dictionary=dictionary)
    return dictionary


def __regex_extract_agency(document_code):
    '''
        Extract agency from document code by regex
    '''
    agencies = []
    code_parts = document_code.split('-')
    
    for part in code_parts:
        for key, info in REGEX_PATTERNS_AGENCY.items():
            if re.search(info["pattern"], part, re.IGNORECASE):
                agencies.append(info["agency"])
                break  
    
    return agencies if agencies else []
    return agencies


async def extract_agency_async(content, document_code, client, semaphore):
    '''
        Extract agency from content by llms and document code by regex
    '''
    agencies = []
    llms_agencies = await __llms_extract_agency_async(content, client, semaphore)
    if llms_agencies is not None:
        agencies = [value for _, value in llms_agencies.items()]
        if len(agencies) == 0:
            agencies = __regex_extract_agency(document_code)        
    
    return agencies

if __name__ == "__main__":
    txt = """
BỘ CÔNG AN - VIỆN KIỂM SÁT NHÂN DÂN TỐI CAO - TÒA ÁN NHÂN DÂN TỐI CAO
-------

CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
---------------

Số: 03/2025/TTLT-BCA-VKSNDTC-TANDTC

Hà Nội, ngày 01 tháng 3 năm 2025


THÔNG TƯ LIÊN TỊCH

QUY ĐỊNH VỀ XỬ LÝ MỘT SỐ VẤN ĐỀ LIÊN QUAN ĐẾN ÁP DỤNG CÁC BIỆN PHÁP XỬ LÝ HÀNH CHÍNH ĐƯA VÀO TRƯỜNG GIÁO DƯỠNG, CƠ SỞ GIÁO DỤC BẮT BUỘC, CƠ SỞ CAI NGHIỆN BẮT BUỘC VÀ BIỆN PHÁP ĐƯA VÀO CƠ SỞ CAI NGHIỆN BẮT BUỘC ĐỐI VỚI NGƯỜI NGHIỆN MA TÚY TỪ ĐỦ 12 TUỔI ĐẾN DƯỚI 18 TUỔI KHI SẮP XẾP TỔ CHỨC BỘ MÁY NHÀ NƯỚC

Căn cứ Nghị quyết số 190/2025/QH15 ngày 19 tháng 02 năm 2025 của Quốc hội quy định về xử lý một số vấn đề liên quan đến sắp xếp tổ chức bộ máy nhà nước;

Bộ trưởng Bộ Công an, Viện trưởng Viện kiểm sát nhân dân tối cao, Chánh án Tòa án nhân dân tối cao ban hành Thông tư liên tịch quy định về xử lý một số vấn đề liên quan đến áp dụng các biện pháp xử lý hành chính đưa vào trường giáo dưỡng, cơ sở giáo dục bắt buộc, cơ sở cai nghiện bắt buộc và biện pháp đưa vào cơ sở cai nghiện bắt buộc đối với người nghiện ma túy từ đủ 12 tuổi đến dưới 18 tuổi khi sắp xếp tổ chức bộ máy nhà nước.
    """
    import asyncio
    import httpx
    async def main():
        async with httpx.AsyncClient() as client:
            semaphore = asyncio.Semaphore(10)
            result = await extract_agency_async(txt, '03/2025/TTLT-BCA-VKSNDTC-TANDTC', client, semaphore)
            print("result:", result)
    
    asyncio.run(main())
