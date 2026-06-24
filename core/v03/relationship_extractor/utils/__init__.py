import re
import sys
import os
import requests
import unicodedata
import uuid
import json
from difflib import SequenceMatcher

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.common.mongo.client import get_mongo_client
from core.v03.relationship_extractor.utils.regex_pattern import DATE_PATTERN, ARTICLE_PATTERN, QUOTES_PATTERN, DOCUMENT_NUMBER_PATTERN_1, DOCUMENT_NUMBER_PATTERN_2
from core.v03.relationship_extractor.utils.regex_pattern import DOCUMENT_TYPE, DOCUMENT_PART
from constants import ElasticConfig, MigrateConfig, MongoDBConfig, MongoDBCollectionConfig
from pymongo import MongoClient
from datetime import datetime
from core.common.elastic import ElasticSearcher

elastic_searcher = ElasticSearcher()
def search_document(doc_id):
    try:
        doc = law_documents_collection.find_one({'doc_id': str(doc_id)})
        if doc:
            return {'_source': doc}
        return None
    except Exception as e:
        logger.error("search_document_failed", action="search_document", doc_id=doc_id, error=str(e))
        return None

from typing import List, Dict, Any
from datetime import datetime


client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_doc_type_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_TYPE_COLLECTION_NAME]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]

DOCUMENT_TYPE = sorted(DOCUMENT_TYPE, key=len, reverse=True)


def extract_date(line: str) -> str | None:
    """
    Extract date from a line in format 'ngày X tháng Y năm Z'.
    """
    date_match = DATE_PATTERN.search(line)
    if date_match:
        day, month, year = date_match.groups()
        date_str = f"{day.zfill(2)}/{month.zfill(2)}/{year}"
        try:
            date_obj = datetime.strptime(date_str, "%d/%m/%Y")
            return date_obj.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            logger.error("extract_date_failed", action="extract_date", **{"error.code": "VAL", "error.message": str(e)}, date_str=date_str, exc_info=True)
    return None


def extract_document_name(line: str, date_pos: int) -> str:
    """
    Extract document name from a line, considering date position.
    """
    if date_pos != -1:
        return line[:date_pos].strip()
    return line.strip()

def extract_document_code(words: list[str]) -> str:
    text = ' '.join(words)
    match = DOCUMENT_NUMBER_PATTERN_2.search(text)
    if match:
        return match.group(0)
    for word in words:
        if '/' in word:
            return word
    return ''

def extract_document_type(line: str) -> str:
    list_document_type = [
        'BỘ LUẬT', 'THÔNG TƯ LIÊN TỊCH', 'QUY NƯỚC VIỆT ĐỊNH', 'VĂN BẢN HỢP NHẤT', 
        'ĐIỀU ƯỚC QUỐC TẾ', 'WTO_CAM KẾT VN', 'NGHỊ ĐỊNH THƯ', 'CHƯƠNG TRÌNH', 
        'VĂN BẢN KHÁC', 'BÁO CÁO THẨM TRA', 'HƯỚNG DẪN TẠM THỜI', 'VĂN BẢN WTO', 
        'WTO_VĂN BẢN', 'NGHỊ QUYẾT', 'QUYẾT ĐỊNH', 'CÔNG ĐIỆN KHẨN', 'THỎA THUẬN', 
        'CÔNG ĐIỆN', 'HIẾN PHÁP', 'HIỆP ĐỊNH', 'HƯỚNG DẪN', 'NGHỊ ĐỊNH', 'PHÁP LỆNH', 
        'NGHỊ ĐỊNH LIÊN BỘ', 'QUY CHẾ PHỐI HỢP', 'PHƯƠNG ÁN', 'THÔNG BÁO', 'THÔNG TRI', 
        'ĐIỆN KHẨN', 'CÔNG ƯỚC', 'KẾ HOẠCH', 'HƯỚNG DẪN LIÊN NGÀNH', 'KẾT LUẬN THANH TRA', 
        'KẾT LUẬN KIỂM TRA', 'KẾT LUẬN', 'QUY ĐỊNH', 'SẮC LUẬT', 'SẮC LỆNH', 'THÔNG TƯ', 
        'TỜ TRÌNH', 'ĐIỀU ƯỚC', 'CHƯƠNG TRÌNH HÀNH ĐỘNG', 'HIỆP ĐỊNH KHUNG', 'BÁO CÁO', 
        'CHỈ THỊ', 'CÔNG BỐ', 'QUY CHẾ', 'ĐIỀU LỆ', 'LUẬT', 'LỆNH', 'QUYẾT ĐỊNH ĐÍNH CHÍNH', 
        'HƯỚNG DẪN BỔ SUNG'
    ]
    
    positions = []

    for doc_type in list_document_type:
        pos = line.lower().find(doc_type.lower())
        if pos != -1:
            positions.append((pos, doc_type))

    if positions:
        min_pos, min_doc_type = min(positions, key=lambda x: x[0])
        if min_doc_type == "BỘ LUẬT":
            return "Luật"
        return min_doc_type
    else:
        return None


def extract_document_info(text: str) -> dict:
    """
    Extract document names, issuance dates, and document codes from text.
    """
    if not isinstance(text, str) or not text.strip():
        logger.error("extract_document_info_failed", action="extract_document_info", **{"error.code": "VAL", "error.message": "Invalid or empty text input"}, text_len=len(text) if text else 0)
        return {'document_names': [], 'dates': [], 'document_codes': [], 'document_types': []}

    try:
        text = re.sub(r'\s*([/-])\s*', r'\1', text)
        lines = text.strip().split('\n')
        document_names = ""
        dates = ""
        document_codes = ""
        document_types = ""

        for line in lines:
            if not line.strip():
                continue 

            # Extract date
            date = extract_date(line)
            date_pos = line.find(' ngày') if date else -1

            # Extract document name
            doc_name = extract_document_name(line, date_pos)
            document_names += doc_name

            # Extract document code
            doc_code = extract_document_code(doc_name.split())
            document_codes += doc_code.replace('.', '').split('(')[0]

            # Append date if found
            if date:
                dates += date

            # Extract document type
            doc_type = extract_document_type(doc_name)
            if doc_type:
                document_types += doc_type

        return {
            'document_names': document_names,
            'dates': dates,
            'document_codes': document_codes,
            'document_types': document_types
        }

    except Exception as e:
        logger.error("extract_document_info_failed", action="extract_document_info", **{"error.code": "PARSE", "error.message": str(e)}, text_len=len(text) if text else 0, exc_info=True)
        return {'document_names': [], 'dates': [], 'document_codes': [], 'document_types': []}


def remove_ellipsis(text):
    return text.replace('/', '').replace('-', '').replace('Đ', 'D').replace('đ', 'd').replace(",", "")


def extract_doc_number(text: str) -> str:
    """
    Trích xuất số hiệu văn bản theo mẫu: 40/2025/TT-BTC, 111/2021/TT-BTC,...
    Dùng làm khóa khử trùng văn bản (bền với khác biệt độ chi tiết của tên).
    """
    if not isinstance(text, str):
        return ""
    pattern = r"\d+/\d{4}/[A-ZĐ\-]+"
    match = re.search(pattern, text.upper())
    return match.group(0) if match else ""


# Thứ tự ưu tiên khi một văn bản bị phân vào nhiều loại quan hệ.
# Hiệu lực toàn bộ/mạnh thắng hiệu lực một phần/yếu; loại đứng trước được giữ lại.
RELATIONSHIP_PRIORITY = [
    'replace',       # thay thế toàn bộ (= replace_full)
    'repeal_full',   # bãi bỏ toàn bộ
    'repeal_apart',  # bãi bỏ một phần
    'amend',         # sửa đổi (đã gộp cả replace_apart ở extractor.py)
    'add',           # bổ sung
    'detail',        # quy định chi tiết
    'referential',   # dẫn chiếu, áp dụng (ưu tiên thấp nhất)
]


def arbitrate_relationships(relationships: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Khử trùng CHÉO giữa các loại quan hệ theo SỐ HIỆU văn bản.

    Mỗi số hiệu chỉ được giữ ở loại có ưu tiên cao nhất (theo RELATIONSHIP_PRIORITY).
    - Văn bản không trích được số hiệu -> giữ nguyên (không dedup để tránh gộp
      nhầm hai văn bản khác nhau).
    - Cùng số hiệu nhưng tên khác độ chi tiết -> giữ lại tên dài/đầy đủ nhất.
    - Các key ngoài priority (vd 'base') được giữ nguyên trạng.
    """
    # 1) Chọn tên đầy đủ nhất cho mỗi số hiệu (vd "TT 68/2019/TT-BCA" vs
    #    "Thông tư số 68/2019/TT-BCA ngày ... của Bộ Công an ...").
    best_name: Dict[str, str] = {}
    for names in relationships.values():
        for name in names:
            num = extract_doc_number(name)
            if num and (num not in best_name or len(name) > len(best_name[num])):
                best_name[num] = name

    seen: Dict[str, str] = {}  # số hiệu -> loại đã giữ
    result: Dict[str, List[str]] = {k: [] for k in relationships}
    for rel_type in RELATIONSHIP_PRIORITY:
        for name in relationships.get(rel_type, []):
            num = extract_doc_number(name)
            if not num:
                result[rel_type].append(name)  # không có số hiệu -> giữ nguyên
                continue
            if num in seen:
                logger.info("drop_duplicate_relationship", action="arbitrate_relationships",
                            num=num, dropped_from=rel_type, kept_in=seen[num])
                continue  # đã thuộc loại ưu tiên cao hơn
            seen[num] = rel_type
            result[rel_type].append(best_name[num])

    # Giữ nguyên các key không tham gia phân xử ưu tiên (vd 'base').
    for k in relationships:
        if k not in RELATIONSHIP_PRIORITY:
            result[k] = relationships[k]
    return result


# Ngưỡng tương đồng tên văn bản tối thiểu khi đối chiếu kết quả map theo mã văn bản.
TITLE_MATCH_THRESHOLD = 0.8


def __normalize_title_for_compare(text: str) -> str:
    """Chuẩn hóa tên văn bản để so khớp mờ: bỏ dấu câu, tiền tố 'số', cụm ngày tháng."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", str(text)).lower()
    text = re.sub(r'\bsố\b', ' ', text)
    text = re.sub(r'ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}', ' ', text)
    text = re.sub(r'[^\w/]+', ' ', text, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', text).strip()


def __token_set_ratio(a: str, b: str) -> float:
    """Tỉ lệ tương đồng theo tập token (mô phỏng token_set_ratio), bền với thừa/thiếu từ."""
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    inter = sorted(ta & tb)
    s_inter = ' '.join(inter)
    s_a = ' '.join(inter + sorted(ta - tb)).strip()
    s_b = ' '.join(inter + sorted(tb - ta)).strip()
    if not s_inter:
        return SequenceMatcher(None, s_a, s_b).ratio()
    return max(
        SequenceMatcher(None, s_inter, s_a).ratio(),
        SequenceMatcher(None, s_inter, s_b).ratio(),
        SequenceMatcher(None, s_a, s_b).ratio(),
    )


def title_similarity(name_a: str, name_b: str) -> float:
    """Độ tương đồng tên hai văn bản trong khoảng [0, 1]."""
    return __token_set_ratio(__normalize_title_for_compare(name_a), __normalize_title_for_compare(name_b))


def __select_best_document_by_title(candidates: list, input_name: str, threshold: float = TITLE_MATCH_THRESHOLD):
    """Chọn văn bản có tên khớp nhất với input_name trong số các ứng viên cùng mã.

    Trả về văn bản tốt nhất nếu độ tương đồng >= threshold, ngược lại trả về None
    (không pass khi fuzzy dưới ngưỡng).
    """
    best_doc = None
    best_score = -1.0
    for candidate in candidates:
        score = title_similarity(input_name, candidate.get('doc_title', ''))
        if score > best_score:
            best_score = score
            best_doc = candidate

    if best_doc is not None and best_score >= threshold:
        logger.debug("map_document_by_code_title_matched", action="mapping_document", score=round(best_score, 3), doc_id=str(best_doc.get('doc_id')))
        return best_doc

    logger.info("map_document_by_code_title_rejected", action="mapping_document", best_score=round(best_score, 3) if best_score >= 0 else None, candidates=len(candidates), input_name=input_name)
    return None


def mapping_document(text, doc_effective_date=None):
    extracted_info = extract_document_info(text)
    document_name = extracted_info['document_names']
    document_code = extracted_info['document_codes']
    document_type = extracted_info['document_types']
    document_date = extracted_info['dates']
    if document_type:
        doc_type = law_doc_type_collection.find_one({'doc_type_name': {'$regex': document_type, '$options': 'i'}})
        if doc_type:
            document_type_id = doc_type['type_id']
        else:
            document_type_id = None
            logger.warning("document_type_not_found", action="mapping_document", document_type=document_type, **{"error.code": "VAL", "error.message": "Document type not found"})

    if doc_effective_date:
        doc_effective_date = datetime.strptime(doc_effective_date, "%Y-%m-%d %H:%M:%S")

    valid_documents = []

    if document_code:
        logger.debug("map_document_by_code_started", action="mapping_document", document_code=document_code)
        safe_code = re.escape(document_code)
        # Khớp CHÍNH XÁC số hiệu (neo ^...$) thay vì khớp chuỗi con. Tránh "26/2020/NĐ-CP"
        # dính nhầm sang "126/2020/NĐ-CP", "30/..." dính "130/...", "01/2018/..." dính "101/2018/...".
        candidates = list(law_documents_collection.find({'doc_code': {'$regex': f'^{safe_code}$', '$options': 'i'}}))

        if candidates:
            # Có thể nhiều (hoặc một) văn bản cùng số hiệu -> chọn bản có TÊN khớp nhất với input.
            # Nếu độ tương đồng dưới ngưỡng -> trả [] để quan hệ được giữ ở dạng unmapped (draft),
            # không map nhầm sang văn bản trùng số hiệu nhưng khác nội dung
            # (vd 01/2018/NĐ-CP "Bộ Công an" vs "Tổng công ty Lương thực miền Bắc").
            chosen = __select_best_document_by_title(candidates, text)
            if chosen is not None:
                valid_document = search_document(doc_id=str(chosen['doc_id']))
                if valid_document:
                    valid_documents.append(valid_document)

    elif document_name and document_date:
        logger.debug("map_document_by_name_and_date_started", action="mapping_document", document_name=document_name, document_date=document_date)
        valid_doc_id = law_documents_collection.find_one({ '$and': [ {'doc_title': {'$regex': f"^{document_name}", '$options': 'i'}}, {'doc_issue_date': {'$eq': document_date}} ] })
        if valid_doc_id:
            valid_document = search_document(doc_id=str(valid_doc_id['doc_id']))
            if valid_document:
                valid_documents.append(valid_document)

    elif document_name and re.search(r'(năm\b|\b(19|20|29)\d{2}\b)', document_name, flags=re.IGNORECASE) and 'sửa đổi' not in document_name.lower():
        logger.debug("map_document_by_name_and_year_started", action="mapping_document", document_name=document_name)
        document_name = document_name.replace(' năm ', ' ')
        valid_doc_id = law_documents_collection.find_one({ '$and': [ {'doc_title': {'$regex': f"^{document_name}", '$options': 'i'}}, {'doc_title': {'$not': {'$regex': 'sửa đổi', '$options': 'i'}}} ] })
        if valid_doc_id:
            valid_document = search_document(doc_id=str(valid_doc_id['doc_id']))
            if valid_document:
                valid_documents.append(valid_document)

    elif document_name and 'năm' not in document_name and 'sửa đổi' in document_name:
        logger.debug("map_document_with_amendment_started", action="mapping_document", document_name=document_name)
        valid_doc_id = law_documents_collection.find_one({'doc_title': {'$regex': f"^{document_name}", '$options': 'i'}})
        if valid_doc_id:
            valid_document = search_document(doc_id=str(valid_doc_id['doc_id']))
            if valid_document:
                valid_documents.append(valid_document)

    elif document_name and doc_effective_date and 'năm' not in document_name and 'sửa đổi' not in document_name:
        logger.debug("map_document_name_invalid", action="mapping_document", document_name=document_name)
        candidate_documents = list(law_documents_collection.find({ '$and': [ {'doc_title': {'$regex': f"^{document_name}", '$options': 'i'}}, {'doc_title': {'$not': {'$regex': 'sửa đổi', '$options': 'i'}}} ] }).sort('doc_effective_date', -1))
        if candidate_documents:
            for candidate_document in candidate_documents:
                if datetime.strptime(str(candidate_document['doc_effective_date']), "%Y-%m-%d %H:%M:%S") <= doc_effective_date:
                    valid_document = search_document(doc_id=str(candidate_document['doc_id']))
                    if valid_document:
                        valid_documents.append(valid_document)
                        break
    elif document_name and document_type and document_type_id and doc_effective_date:
        candidate_documents = list(law_documents_collection.find({ '$and': [ {'type_id': document_type_id}, {'doc_title': {'$regex': f"^{document_name}", '$options': 'i'}} ] }).sort('doc_effective_date', -1))
        if candidate_documents:
            for candidate_document in candidate_documents:
                if datetime.strptime(str(candidate_document['doc_effective_date']), "%Y-%m-%d %H:%M:%S") <= doc_effective_date:
                    valid_document = search_document(doc_id=str(candidate_document['doc_id']))
                    if valid_document:
                        valid_documents.append(valid_document)
                        break
    else:
        logger.debug("map_document_failed", action="mapping_document", document_name=document_name if document_name else "")
        return []
    
    if not valid_documents:
            return []

    return valid_documents

def remove_article(text):
    """Remove 'Điều X.' prefix from the text."""
    return re.sub(ARTICLE_PATTERN, "", text)


def remove_multi_underline(text):
    """Remove 'Điều X.' prefix from the text."""
    return text.replace('\n\n', '\n')


def extract_part(data):
    """Extract article numbers ('Điều X') from names."""
    try:
        return [{'name': item, 'Điều': re.findall(r"Điều\s\d+", item)} for item in data.get('Names', [])]
    except Exception as e:
        logger.error("extract_part_failed", action="extract_part", **{"error.code": "PARSE", "error.message": str(e)}, exc_info=True)
        return []


def __replace_nested_quotes(text):
    """Replace nested double quotes with single quotes."""
    stack = []
    text_list = list(text)

    for i, char in enumerate(text_list):
        if char == '“':
            if stack:
                text_list[i] = "'"
            stack.append(char)
        elif char == '”':
            if len(stack) > 1:
                text_list[i] = "'"
            if stack:
                stack.pop()
    
    return ''.join(text_list)


def remove_reference(content):
    """Clean and process content, removing nested quotes and excess spaces."""
    content = re.sub(r" {2,}", " ", content)
    content = content.replace('"\n', '”\n').replace('\n "', '\n “').replace('\n"', '\n“')
    content = __replace_nested_quotes(content)
    
    references = re.findall(QUOTES_PATTERN, content, re.DOTALL)    
    for ref in references:
        content = content.replace(ref, '')    
    return content


def call_map_document_api(name, results, index):
    mapping_result = mapping_document(name)
    results[index] = mapping_result    


def extract_brief(content):
    
    brief = None    
    content = unicodedata.normalize("NFC", content)
    text = content[:5000]
    text = text.replace("\xa0", " ")    
    text = text.replace("  ", " ")        
    text = '\n' + text            
    
    type_match = None        
    type_pattern = r"\n(" + "|".join(map(re.escape, DOCUMENT_TYPE)) + r")\b"            
    type_matches = list(re.finditer(type_pattern, text))
    if type_matches:            
        type_match = min(type_matches, key=lambda m: m.start())
        doc_type = type_match.group(1)
        
    part_match = None
    part_pattern = r"\n(" + "|".join(map(re.escape, DOCUMENT_PART)) + r")\b"                
    part_matches = list(re.finditer(part_pattern, text, re.IGNORECASE))
    if part_matches:            
        part_match = min(part_matches, key=lambda m: m.start())
        doc_part = part_match.group(1)
    
    type_index = None
    if type_match is not None:
        type_index = type_match.start()
    
    part_index = None    
    if part_match is not None:
        part_index = part_match.start()
        
    if type_index is not None and part_index is not None:
        if type_index < part_index:
            brief = content[type_index: part_index]
    elif part_index is not None:
        brief = content[:part_index]
                
    if brief is not None:
        brief = brief.strip()
        sentences = brief.split('\n')
        return '\n'.join(sent for sent in sentences[2:])
    else:
        brief = content[:2000]
        return brief


def _get_target_id(doc_id, target_article):
    article = law_articles_collection.find_one({'doc_id': str(doc_id), 'article_title': {"$regex": f"^{target_article}[\\.\\-/\\n:]"}})
    # logger.info("target_id_query", doc_id=doc_id, target_article=target_article, target_id=target_id)
    logger.debug("query_target_id_successful", action="_get_target_id", doc_id=doc_id, target_article=target_article, target_id=article.get('article_id') if article else None)
    if article:
        return article['article_id']
    return None


def convert_relationships_to_records(results: List[Dict[str, Any]], collect_drafts: bool = False):
    """Resolve extracted relationships to DB records.

    Returns the list of resolved records (target document + article both found in
    the DB), exactly as before.

    When `collect_drafts=True`, returns a tuple `(resolved, drafts)` where `drafts`
    are cross-document references whose **target document is not in the DB**
    (`mapping_document` returned nothing). Each draft carries the raw display
    fields (`target_doc_name`, `target_doc_code`) so the FE can render
    Số hiệu / Tên văn bản / Điều luật / Loại quan hệ directly, without a doc lookup.
    """
    final_results: List[Dict[str, Any]] = []
    drafts: List[Dict[str, Any]] = []
    current_datetime = datetime.now()
    created_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
    last_modified = current_datetime.strftime("%Y-%m-%d %H:%M:%S")

    doc_cache: Dict[str, str] = {}
    source_clause = None
    source_point = None

    logger.info("show_results_successful", action="convert_relationships_to_records", results_count=len(results))
    for result in results:
        source_doc_id = result.get("doc_id")
        doc_effective_date = law_documents_collection.find_one({'doc_id': str(source_doc_id)})['doc_effective_date']
        source_article_id = result.get("article_id")
        relationships = result.get("relationships", [])

        if not relationships:
            continue

        # normalize về list
        if isinstance(relationships, dict):
            relationships = [relationships]
        elif not isinstance(relationships, list):
            logger.warning("process_relationships_invalid", action="convert_relationships_to_records", format=relationships)
            continue

        for rel in relationships:
            details = rel.get("details", [])

            for detail in details:
                doc_title = detail.get("detail_name")
                if not doc_title:
                    continue

                if doc_title not in doc_cache:
                    try:
                        target_doc = mapping_document(doc_title, doc_effective_date)
                        if target_doc:
                            doc_cache[doc_title] = target_doc[0]['_source']['doc_id']
                        else:
                            doc_cache[doc_title] = None
                    except (IndexError, KeyError, Exception) as e:
                        logger.error("map_document_failed", action="convert_relationships_to_records", **{"error.code": "DB", "error.message": str(e)}, doc_title=doc_title, exc_info=True)
                        continue
                
                # Gate: does the referenced document exist in the DB?
                #   not found → DRAFT (raw display fields, no target_doc_id)
                #   found     → resolved record (existing flow below)
                if doc_cache[doc_title] is None:
                    if collect_drafts:
                        try:
                            target_doc_code = extract_document_info(doc_title).get("document_codes", "")
                        except Exception:
                            target_doc_code = ""
                        drafts.append({
                            "relationship_id": str(uuid.uuid4()),
                            "source_doc_id": source_doc_id,
                            "source_article_id": source_article_id,
                            "source_clause": source_clause,
                            "source_point": source_point,
                            "target_doc_id": "",
                            "target_article_id": "",
                            "target_article": detail.get("detail_article", ""),
                            "target_clause": detail.get("detail_clause", ""),
                            "target_point": detail.get("detail_point", ""),
                            "target_doc_name": doc_title,            # Tên văn bản
                            "target_doc_code": target_doc_code,      # Số hiệu văn bản
                            "relationship_type": detail.get("type_llm", ""),
                            "created_by": "SYSTEM",
                            "created_at": created_date,
                            "last_modified_at": last_modified,
                            "last_modified_by": "admin",
                        })
                    continue
                target_doc_id = doc_cache[doc_title]
                target_article = detail.get("detail_article", "")

                if not target_article:
                    continue

                try:
                    target_article_id = _get_target_id(target_doc_id, target_article)
                except Exception as e:
                    logger.error("resolve_target_id_failed", action="convert_relationships_to_records", **{"error.code": "DB", "error.message": str(e)}, target_doc_id=target_doc_id, target_article=target_article, exc_info=True)
                    target_article_id = None

                if not target_article_id:
                    continue

                record = {
                    "relationship_id": str(uuid.uuid4()),
                    "source_doc_id": source_doc_id,
                    "source_article_id": source_article_id,
                    "source_clause": source_clause,
                    "source_point": source_point,
                    "target_doc_id": target_doc_id,
                    "target_article_id": target_article_id,
                    "target_article": target_article,
                    "target_clause": detail.get("detail_clause", ""),
                    "target_point": detail.get("detail_point", ""),
                    "relationship_type": detail.get("type_llm", ""),
                    "created_by": "SYSTEM",
                    "created_at": created_date,
                    "last_modified_at": last_modified,
                    "last_modified_by": "admin"
                }
                final_results.append(record)

    if collect_drafts:
        return final_results, drafts
    return final_results
    

if __name__ == '__main__':
    result = mapping_document()
    print(result)