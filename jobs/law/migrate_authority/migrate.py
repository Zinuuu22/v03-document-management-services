from core.common.mongo.client import get_mongo_client
import os
import sys
import structlog
import re
import uuid
import tqdm
from datetime import datetime
from pymongo import MongoClient
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

CREATED_BY = "System"
CREATED_DATE = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

from core.v03.law_authority_extractor.utils.regex_pattern import (
    SPLIT_CLAUSE_PATTERN,
    CLAUSE_HEADER_BODY_PATTERN,
    CLAUSE_SIMPLE_PATTERN,
    SUBITEM_SPLIT_PATTERN,
    CLAUSE_CAPTURE_PATTERN,
    DETAIL_REGULATION_HEADER_PATTERN,
    RELATIONSHIP_PATTERNS
)

AGENCY_LIST = [
    "Quốc hội",
    "Chủ tịch nước",
    "Chính phủ",
    "Thủ tướng Chính phủ",
    "Bộ Y tế",
    "Bộ Tư pháp",
    "Bộ Công thương",
    "Bộ Xây dựng",
    "Bộ Nội vụ",
    "Bộ Tài chính",
    "Bộ Ngoại giao",
    "Bộ Khoa học và Công nghệ",
    "Bộ Văn hóa Thể thao và Du lịch",
    "Bộ Dân tộc và Tôn giáo",
    "Bộ Giáo dục và Đào tạo",
    "Bộ Nông nghiệp và Môi trường",
    "Ngân hàng Nhà nước Việt Nam",
    "Thanh tra Chính phủ",
    "Bộ Quốc phòng",
    "Bộ Công an",
    "Viện trưởng Viện kiểm sát nhân dân tối cao"
]

client = get_mongo_client()

# Raw Database (for scoping)
raw_db = client['hunghv']
new_law_docs_collection = raw_db['law_documents_v1']

# Core Database (for extraction and updates)
db = client[MigrateConfig.MIGRATE_CORE_DB]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
law_agencies_collection = db[MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME]
law_authority_collection = db[MongoDBCollectionConfig.LAW_AUTHORITY_COLLECTION_NAME]
law_authority_mapping_collection = db[MongoDBCollectionConfig.LAW_AUTHORITY_MAPPING_COLLECTION_NAME]


def get_scope_doc_ids():
    """
    Fetch all the doc_ids from the raw collection ('hunghv.law_documents_v1') 
    so we can limit our extraction scope.
    """
    cursor = new_law_docs_collection.find({"doc_id": {"$exists": True}}, {"doc_id": 1, "_id": 0})

    doc_ids = []
    for doc in cursor:
        did = str(doc.get("doc_id", ""))
        if did:
            doc_ids.append(did)
            if did.isdigit():
                doc_ids.append(int(did))
    return doc_ids


def check_pattern(text: str):
    """
    Kiểm tra xem đoạn text có thuộc nhóm 'Bãi bỏ', 'Sửa đổi, bổ sung', hay 'Thay thế' không.
    Trả về:
      - (type_name, matched_pattern) nếu khớp
      - (None, None) nếu không khớp
    """
    for type_name, patterns in RELATIONSHIP_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE | re.UNICODE):
                return True
    return False


def get_agency_id(agency_name: str):
    try:
        return law_agencies_collection.find_one({"agency_name": agency_name})["agency_id"]
    except Exception as e:
        return None


def convert_to_data_model(data):
    authority_content = data.get('authority_content', '')
    doc_effective_date = data.get('doc_effective_date','')
    doc_expire_date = data.get('doc_expire_date','')
    doc_effective_status = data.get('doc_effective_status','')
    doc_id = data.get('doc_id','')
    article_id = data.get('article_id','')
    agency_id = data.get('agency_id','')

    record_raw = {
        'authority_id': str(uuid.uuid4()),
        'authority_content': authority_content,
        'doc_effective_date': doc_effective_date,
        'doc_expire_date': doc_expire_date,
        'doc_effective_status': doc_effective_status,
        'status': "ACTIVE",
        "created_date": CREATED_DATE,
        "created_by": CREATED_BY,
        "last_modified": CREATED_DATE,
        "last_modified_by": CREATED_BY
    }

    record_mapping = {
        'authority_id': record_raw.get('authority_id',''),
        'doc_id': doc_id,
        'article_id': article_id,
        'agency_id': agency_id,
        "created_date": CREATED_DATE,
        "created_by": CREATED_BY,
        "last_modified": CREATED_DATE,
        "last_modified_by": CREATED_BY
    }

    return record_raw, record_mapping


def split_clause_content(full_text):
    if not isinstance(full_text, str):
        return []
    clauses = re.split(SPLIT_CLAUSE_PATTERN, full_text.strip(), flags=re.UNICODE)
    results = []
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        m = re.match(
            CLAUSE_HEADER_BODY_PATTERN,
            clause,
            flags=re.DOTALL | re.UNICODE
        )
        if not m:
            m2 = re.match(CLAUSE_SIMPLE_PATTERN, clause, flags=re.UNICODE)
            if m2:
                header = m2.group(1).strip()
                results.append({
                    "clause_content_title": header,
                    "clause_content_detail": None
                })
            continue
        numbering = m.group(1).strip()              
        header_text = m.group(2).strip()            
        clause_body = m.group(3).strip()            
        if header_text:
            clause_header = f"{numbering} {header_text}"
        else:
            clause_header = numbering

        if clause_body and "\n" in clause_body:
            items = re.split(SUBITEM_SPLIT_PATTERN, clause_body, flags=re.UNICODE | re.IGNORECASE)
            items = [it.strip() for it in items if it.strip()]
        else:
            if clause_body:
                items = [clause_body]
            else:
                items = []

        results.append({
            "clause_content_title": clause_header,
            "clause_content_detail": items if items else None
        })
    return results

def detect_detail_regulation(text: str):
    pattern = re.compile(
        DETAIL_REGULATION_HEADER_PATTERN + r"(?P<agency>" + "|".join(re.escape(agency) for agency in AGENCY_LIST) + r") quy định chi tiết (?P<clause>.+?)(?P<article>Điều [\w\d]+|Điều này)",
        flags=re.IGNORECASE | re.UNICODE | re.DOTALL
    )
    match = pattern.search(text)
    if not match:
        pattern_short = re.compile(
            DETAIL_REGULATION_HEADER_PATTERN + r"(?P<agency>" + "|".join(re.escape(agency) for agency in AGENCY_LIST) + r") quy định chi tiết (?P<article>Điều [\w\d]+|Điều này)",
            flags=re.IGNORECASE | re.UNICODE | re.DOTALL
        )
        match = pattern_short.search(text)
    if match:
        result = {
            "has_pattern": True,
            "agency": match.group("agency"),
            "clause": match.groupdict().get("clause"),
            "article": match.group("article"),
            "clause_content": None
        }
        
        if result["clause"] and "khoản" in result["clause"]:
            clause_pattern = re.compile(CLAUSE_CAPTURE_PATTERN, re.DOTALL)
            clauses = clause_pattern.findall(text)
            matched_clauses = []
            clause_clean = result["clause"].strip()
            
            for clause_full_match in clauses:
                clause_text = clause_full_match[0]
                clause_num_match = re.match(r"(\d+)", clause_text)
                if clause_num_match:
                    clause_num = clause_num_match.group(1)
                    if re.search(rf"\bkhoản\s+{re.escape(clause_num)}\b", clause_clean, re.IGNORECASE):
                        matched_clauses.append(clause_text.strip())
            
            if matched_clauses:
                result["clause_content"] = "\n".join(matched_clauses)
            else:
                lines = text.strip().splitlines()
                for i, line in enumerate(lines):
                    if re.search(rf"{re.escape(result['agency'])} quy định chi tiết", line, re.IGNORECASE):
                        if i > 0:
                            content_before = "\n".join(lines[:i]).rstrip()
                            result["clause_content"] = content_before.strip() if content_before else None
                        break
        else:
            lines = text.strip().splitlines()
            for i, line in enumerate(lines):
                if re.search(rf"{re.escape(result['agency'])} quy định chi tiết", line, re.IGNORECASE):
                    if i > 0:
                        content_before = "\n".join(lines[:i]).rstrip()
                        result["clause_content"] = content_before.strip() if content_before else None
                    break
        return result
    return {"has_pattern": False}


def get_authority(list_article):
    list_result = []
    for law_article in list_article:
        try:
            law_article["is_authority_extract"] = "SUCCESS"
            if check_pattern(law_article['article_content']):
                law_articles_collection.replace_one({"_id": law_article["_id"]}, law_article)
                continue
            try:
                check_result = detect_detail_regulation(law_article['article_content'])
            except Exception as e:
                law_articles_collection.replace_one({"_id": law_article["_id"]}, law_article)
                continue   
            if check_result['has_pattern'] == True:
                record = {
                    'authority_id': str(uuid.uuid4()),
                    'doc_id': law_article.get('doc_id',''),
                    'doc_title': law_article.get('doc_title',''),
                    'article_id': law_article.get('article_id',''),
                    'article_title': law_article.get('article_title',''),
                    'article_content': law_article.get('article_content',''),
                    'agency_id': get_agency_id(check_result['agency']),
                    'agency_name':check_result['agency'],
                    'authority_content': check_result['clause_content'],
                    'status': law_article.get('status',''),
                    'doc_effective_date': law_article.get('effective_date',''),
                    'doc_expire_date': law_article.get('expire_date',''),
                    'doc_effective_status': law_article.get('effective_status',''),
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
    
                result_raw, result_mapping = convert_to_data_model(record)
                law_authority_collection.insert_one(result_raw)
                law_authority_mapping_collection.insert_one(result_mapping)
                logger.info(action="get_authority", event="authority_extracted", article_id=record['article_id'])
                list_result.append(record)
            else:
                law_articles_collection.replace_one({"_id": law_article["_id"]}, law_article)
                continue
        except Exception as e:
            logger.error(action="get_authority", event="get_authority_failed", **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
            law_article["is_authority_extract"] = "FAIL"
        law_articles_collection.replace_one({"_id": law_article["_id"]}, law_article)
    return list_result


def get_law_articles(article_id=None):
    pipeline = []
    
    # Restrict to SCOPE fetching from raw incoming database
    logger.info(action="get_law_articles", event="fetching_scope_doc_ids")
    scoped_doc_ids = get_scope_doc_ids()
    
    if not scoped_doc_ids:
        logger.warning(action="get_law_articles", event="no_docs_in_scope")
        return []

    if article_id:
        pipeline.append({'$match': {'article_id': article_id}})
    else:
        pipeline.append({
            '$match': {
                'doc_id': {'$in': scoped_doc_ids},
                '$or': [
                    {"is_authority_extract": "FAIL"},
                    {"is_authority_extract": {"$exists": False}}
                ]
            }
        })
        
    pipeline += [
        {
            '$lookup': {
                'from': 'law_documents',
                'localField': 'doc_id',
                'foreignField': 'doc_id',
                'as': 'doc_info'
            }
        },
        {
            '$unwind': {
                'path': '$doc_info',
                'preserveNullAndEmptyArrays': False
            }
        }
    ]
    return law_articles_collection.aggregate(pipeline)


def extract_authority_other():
    '''
    Hàm này để quét nội dung giao quyền của các cơ quan quản lý nhà nước đã xác định trước
    '''
    data = {
        "Quốc hội": [
            "163c22d5-7b5a-4779-8f92-e61e6c0ea445",
            "65826bff-26e9-4108-b8ba-9e4eb11c0c87",
            "3d8b13db-e30f-4877-ae84-42c2a66e9b12",
            "e4c24e2a-5824-4f99-befc-8298032ef353",
            "d4b0a752-32f7-47c4-aeaf-21d35fb9ae98",
            "fe408017-0a82-45cb-8a8a-4acca65d1b49"
        ],
        "Chủ tịch nước": [
            "6f9c61fe-1f0f-43f3-b269-d5d764c16e89"
        ],
        "Chính phủ": [
            "199f7b79-9654-4b81-8d85-7eb8fe0c1a77",
            "499176b2-01d3-4cc9-a7a9-6ac96eafeb27"
        ],
        "Thủ tướng Chính phủ": [
            "0152f073-81a1-4712-be76-4d522001b09b",
            "0610de00-2b45-4463-8439-e3b950b24e6d"
        ],
        "Bộ Y tế": ["9724b8be-c9e3-45a2-a88c-fa47d67caa9d"],
        "Bộ Tư pháp": ["8fa5c8ab-10b0-44c7-921f-65c0fa683349"],
        "Bộ Công thương": ["54f8af5b-a7e1-4338-aa63-d3a8471d7430"],
        "Bộ Xây dựng": ["9418c69d-5df6-4a16-a89b-0b243d50b7da"],
        "Bộ Nội vụ": ["fb33fea4-15f5-45cf-8851-87d28e62d3ed"],
        "Bộ Tài chính": ["9b040451-e148-490e-9a84-76fe6dac50e7"],
        "Bộ Ngoại giao": ["a3d7a96f-0201-41a7-bc3f-9a423980d5a0"],
        "Bộ Khoa học và Công nghệ": ["3c3e1b99-0eae-4d19-911d-675cfca118b8"],
        "Bộ Văn hóa, Thể thao và Du lịch": ["be902921-b58d-4e9c-9f4b-2f561e620e64"],
        "Bộ Dân tộc và Tôn giáo": ["9503faa2-a2e8-4a39-981c-f230fd055eea"],
        "Bộ Giáo dục và Đào tạo": ["a1ad2953-5dc1-4278-9d22-fa1f09ff107c"],
        "Bộ Nông nghiệp và Môi trường": ["ff2336b0-1d07-49c9-a0c0-fc70f4039ef4"],
        "Ngân hàng Nhà nước Việt Nam": ["c164cddc-4606-40cf-8712-ffac1f5d7c04"],
        "Thanh tra Chính phủ": ["f8c49735-814e-4837-be1d-0ee19add9eeb"],
        "Bộ Quốc phòng": ["ca9e5ca9-234f-47e9-ba32-02b5235ee254"],
        "Bộ Công an": ["4128f8ee-7d99-4b38-a684-b2d99f36ab38"],
        "Viện trưởng Viện kiểm sát nhân dân tối cao": ["eb58765e-8082-4009-b8dc-cdd3dc6685a5"]
    }
    records = []
    for k, v in data.items():
        for article_id in v:
            law_article = get_law_articles(article_id)[0]
            if check_pattern(law_article['article_content']):
                continue
            record = {
                'authority_id': str(uuid.uuid4()),
                'doc_id': law_article.get('doc_id',''),
                'doc_title': law_article.get('doc_title',''),
                'article_id': law_article.get('article_id',''),
                'article_title': law_article.get('article_title',''),
                'article_content': law_article.get('article_content',''),
                'agency_id': get_agency_id(k),
                'agency_name':k,
                'authority_content': law_article['article_content'],
                'status': law_article.get('status',''),
                'doc_effective_date': law_article.get('effective_date',''),
                'doc_expire_date': law_article.get('expire_date',''),
                'doc_effective_status': law_article['effective_status'],
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            records.append(record)
            result_raw, result_mapping = convert_to_data_model(record)
            law_authority_collection.insert_one(result_raw)
            law_authority_mapping_collection.insert_one(result_mapping)
    return records


if __name__ == "__main__":
    logger.info(action="main", event="starting_authority_extraction", status="loading data...")
    cursor = get_law_articles()
    
    if cursor:
        results = get_authority(tqdm.tqdm(cursor, desc="Processing Articles"))
        logger.info(action="main", event="authority_extraction_results", success_count=len(results))
    else:
        logger.info(action="main", event="no_articles_to_process")
