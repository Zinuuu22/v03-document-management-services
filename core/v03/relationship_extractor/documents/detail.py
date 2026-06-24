from core.common.mongo.client import get_mongo_client
import json
from pymongo import MongoClient
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
from constants import LLMsConfigExtractRelationship, MongoDBConfig

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

EXTRACT_RELATIONSHIP_DETAIL_PROMPT = load_prompt_by_title(
    r"# Prompt 3: Trích xuất mối quan hệ hướng dẫn chi tiết từ văn bản"
)


# "Cổng" quyết định có gọi LLM trích xuất quan hệ "quy định chi tiết / hướng dẫn"
# cho một điều luật hay không.
#
# Quan hệ này là MỘT CHIỀU và do CHÍNH văn bản đầu vào khai báo về bản thân nó
# (thường ở Điều "Phạm vi điều chỉnh"). Trong văn bản pháp luật VN, văn bản tự
# khai báo bằng cấu trúc tự tham chiếu:
#       "<Loại văn bản> NÀY quy định ..."
# với phần phía sau "quy định" rất đa dạng, KHÔNG chỉ là "chi tiết / cụ thể":
#   - "Thông tư này quy định chi tiết một số điều của Luật Nhà ở..."
#   - "Thông tư này quy định về trách nhiệm ... trong việc thực hiện các quy định
#      của Bộ luật Tố tụng hình sự năm 2015..."            (Thông tư 46/2019/TT-BCA)
#   - "Thông tư liên tịch này quy định việc phối hợp trong thực hiện một số quy
#      định của Luật Thi hành án hình sự..."               (TTLT 01/2023)
# Vì vậy cổng chỉ cần nhận diện dấu hiệu tự tham chiếu "<Loại văn bản> này quy định"
# (ưu tiên recall); việc xác định CHÍNH XÁC văn bản cấp trên được quy định chi tiết
# do LLM (Prompt 3) đảm nhiệm.
#
# Điểm mấu chốt xử lý issue #2: khi cụm "quy định chi tiết / hướng dẫn thi hành"
# nằm trong TÊN/TRÍCH YẾU của MỘT VĂN BẢN KHÁC thì đứng ngay trước nó là số hiệu /
# "của <cơ quan>", KHÔNG phải "<Loại văn bản> này", ví dụ:
#       "...Nghị định số 145/2020/NĐ-CP ... của Chính phủ quy định chi tiết và
#        hướng dẫn thi hành một số điều của Bộ luật Lao động..."
# Những điều luật chỉ dẫn chiếu kiểu này sẽ KHÔNG khớp "<Loại văn bản> này quy định"
# nên không trở thành candidate -> không bị trích nhầm.
DETAIL_DOCUMENT_TYPE_ALT = (
    r"(?:thông tư liên tịch|thông tư|nghị định|nghị quyết|quyết định|pháp lệnh"
    r"|bộ luật|luật|văn bản hợp nhất|văn bản|quy chế|điều lệ|hiến pháp|sắc lệnh"
    r"|chỉ thị)"
)
DETAIL_CANDIDATE_PATTERN = re.compile(DETAIL_DOCUMENT_TYPE_ALT + r"\s+này\s+quy định")


def __is_detail_document_candidate(article_title, article_content):
    full_content = f"{article_title}\n{article_content}".lower()
    return DETAIL_CANDIDATE_PATTERN.search(full_content) is not None


# Cụm dẫn chiếu/áp dụng MẠNH: một văn bản nêu ngay sau các cụm này (để áp dụng cho
# một nội dung/thủ tục cụ thể) là quan hệ DẪN CHIẾU (referential), không phải "quy
# định chi tiết". Chỉ dùng cụm mạnh "thực hiện theo / áp dụng theo" -- KHÔNG dùng
# "theo quy định của/tại" vì các cụm này cũng hay đi kèm chính LUẬT cấp trên đang
# được quy định chi tiết.
__DETAIL_REFERENTIAL_SIGNALS = (
    "thực hiện theo", "được thực hiện theo", "áp dụng theo",
)
# Loại văn bản "ngang cấp" (không phải văn bản cấp trên được quy định chi tiết). Quan
# hệ "quy định chi tiết" hướng tới văn bản CẤP TRÊN (Luật/Bộ luật/Pháp lệnh/Nghị định),
# nên một Thông tư/Quyết định ngang cấp được nêu kèm "thực hiện theo" gần như chắc chắn
# là dẫn chiếu, không phải đối tượng được quy định chi tiết.
__DETAIL_PEER_TYPES = ("thông tư liên tịch", "thông tư", "quyết định", "chỉ thị")


def __is_referential_governed(law_document, full_content_list, window=50):
    """True nếu văn bản NGANG CẤP (Thông tư/Quyết định...) xuất hiện ngay sau một cụm
    áp dụng mạnh ("thực hiện theo"...) -> là dẫn chiếu, không phải quy định chi tiết.
    KHÔNG áp cho Luật/Bộ luật/Nghị định cấp trên (đối tượng được quy định chi tiết)."""
    if not law_document.strip().lower().startswith(__DETAIL_PEER_TYPES):
        return False
    for content in full_content_list:
        idx = content.find(law_document)
        while idx != -1:
            pre = content[max(0, idx - window): idx].lower()
            if any(sig in pre for sig in __DETAIL_REFERENTIAL_SIGNALS):
                return True
            idx = content.find(law_document, idx + 1)
    return False


async def extract_relationship_detail(segments, document_name, client: httpx.AsyncClient, semaphore: asyncio.Semaphore):        
    relationships = {
        'detail': []     
    }    
    full_content_list = []
    
    for segment in segments:
        article_title = segment['article_title']
        article_content = remove_reference(segment['article_content'])
        full_content = f"{article_title}\n{article_content}"
        full_content_list.append(full_content)  # Lưu lại nội dung điều khoản

    async def process_seg(segment):
        article_title = segment['article_title']
        article_content = remove_reference(segment['article_content'])

        if not __is_detail_document_candidate(article_title, article_content):
            return None       
        
        prompt = EXTRACT_RELATIONSHIP_DETAIL_PROMPT.format(
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
            logger.error("extract_detail_relationship_failed", action="extract_relationship_detail", **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
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
        
    seen = set()
    for relationship_rs in results:
        if relationship_rs is not None and 'detail' in relationship_rs:
            for law_document in relationship_rs['detail']:
                if law_document in seen:
                    continue
                # Guard chống hallucination: tên văn bản phải thực sự xuất hiện
                # trong nội dung điều luật nguồn.
                if not any(law_document in content for content in full_content_list):
                    continue
                # Văn bản được nêu sau cụm dẫn chiếu/áp dụng ("thực hiện theo"...) là
                # quan hệ referential, không phải detail -> bỏ để không lấn module khác.
                if __is_referential_governed(law_document, full_content_list):
                    logger.info("skip_referential_governed_detail", action="extract_relationship_detail", law_document=law_document)
                    continue
                seen.add(law_document)
                relationships['detail'].append(law_document)

    return relationships


if __name__ == '__main__':    
    from pymongo import MongoClient
    from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig

    client = get_mongo_client()

    db = client[MigrateConfig.MIGRATE_CORE_DB]

    documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
    segment_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
    
    document_id = '559392'
    
    document = documents_collection.find_one({'doc_id': document_id})
    segments = list(segment_collection.find({'doc_id': document['doc_id']}))  