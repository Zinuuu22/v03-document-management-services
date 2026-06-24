from core.common.mongo.client import get_mongo_client
import os
import sys
import re
import uuid
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
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
    DETAIL_REGULATION_PATTERN,
    DETAIL_REGULATION_SHORT_PATTERN,
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

from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig
from pymongo import MongoClient
import time


client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
law_article_classified_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_CLASS_COLLECTION_NAME]
law_agencies_collection = db[MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME]
law_authority_collection = db[MongoDBCollectionConfig.LAW_AUTHORITY_COLLECTION_NAME]
law_authority_mapping_collection = db[MongoDBCollectionConfig.LAW_AUTHORITY_MAPPING_COLLECTION_NAME]


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
    doc_expiry_date = data.get('doc_expiry_date','')
    doc_id = data.get('doc_id','')
    doc_title = data.get('doc_title','')
    article_id = data.get('article_id','')
    article_title = data.get('article_title','')
    article_content = data.get('article_content','')
    agency_id = data.get('agency_id','')
    agency_name = data.get('agency_name','')

    record_raw = {
        'authority_id': str(uuid.uuid4()),
        'authority_content': authority_content,
        'doc_effective_date': doc_effective_date,
        'doc_expiry_date': doc_expiry_date,
        'effective_status_id': data.get('effective_status_id', ''),
        'status': "ACTIVE",
        "created_at": CREATED_DATE,
        "created_by": CREATED_BY,
        "last_modified_at": CREATED_DATE,
        "last_modified_by": CREATED_BY
    }

    record_mapping = {
        'authority_id': record_raw.get('authority_id',''),
        'doc_id': doc_id,
        'article_id': article_id,
        'agency_id': agency_id,
        "created_at": CREATED_DATE,
        "created_by": CREATED_BY,
        "last_modified_at": CREATED_DATE,
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
            
            # Strip whitespace từ clause
            clause_clean = result["clause"].strip()
            
            for clause_full_match in clauses:
                clause_text = clause_full_match[0]
                
                # Tìm số khoản từ đầu clause_text
                clause_num_match = re.match(r"(\d+)", clause_text)
                if clause_num_match:
                    clause_num = clause_num_match.group(1)
                    # Tìm số này trong clause_clean
                    if re.search(rf"\bkhoản\s+{re.escape(clause_num)}\b", clause_clean, re.IGNORECASE):
                        matched_clauses.append(clause_text.strip())
            
            if matched_clauses:
                result["clause_content"] = "\n".join(matched_clauses)
            else:
                # Fallback: lấy nội dung trước dòng
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
        if check_pattern(law_article['article_content']):
            continue
        try:
            check_result = detect_detail_regulation(law_article['article_content'])
        except Exception as e:
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
                'doc_effective_date': law_article.get('doc_effective_date',''),
                'doc_expiry_date': law_article.get('doc_expiry_date',''),
                'effective_status_id': law_article.get('effective_status_id', ''),
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'last_modified_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            result_raw, result_mapping = convert_to_data_model(record)
            law_authority_collection.insert_one(result_raw)
            law_authority_mapping_collection.insert_one(result_mapping)
        else:
            continue
    return list_result

def get_law_articles(article_id=None):
    pipeline = []
    if article_id:
        pipeline.append({'$match': {'article_id': article_id}})
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
        },
        {
            '$project': {
                '_id': 0,
                'doc_id': 1,
                'doc_title': '$doc_info.doc_title',
                'article_id': 1,
                'article_title': 1,
                'article_content': 1,
                'status': 1,
                'doc_effective_date': '$doc_info.doc_effective_date',
                'doc_expiry_date': '$doc_info.doc_expiry_date',
                'effective_status_id': '$doc_info.effective_status_id',
            }
        }
    ]
    result = list(law_articles_collection.aggregate(pipeline))
    return result

def extract_authority_other():
    '''
    Hàm này để quét nội dung giao quyền của các cơ quan quản lý nhà nước đã xác định trước
    '''
    # law_articles_09062025
    # data = {
    #     "Quốc hội": [
    #         "163c22d5-7b5a-4779-8f92-e61e6c0ea445",
    #         "65826bff-26e9-4108-b8ba-9e4eb11c0c87",
    #         "3d8b13db-e30f-4877-ae84-42c2a66e9b12",
    #         "e4c24e2a-5824-4f99-befc-8298032ef353",
    #         "d4b0a752-32f7-47c4-aeaf-21d35fb9ae98",
    #         "fe408017-0a82-45cb-8a8a-4acca65d1b49"
    #     ],
    #     "Chủ tịch nước": [
    #         "6f9c61fe-1f0f-43f3-b269-d5d764c16e89"
    #     ],
    #     "Chính phủ": [
    #         "199f7b79-9654-4b81-8d85-7eb8fe0c1a77",
    #         "499176b2-01d3-4cc9-a7a9-6ac96eafeb27"
    #     ],
    #     "Thủ tướng Chính phủ": [
    #         "0152f073-81a1-4712-be76-4d522001b09b",
    #         "0610de00-2b45-4463-8439-e3b950b24e6d"
    #     ],
    #     "Bộ Y tế": ["9724b8be-c9e3-45a2-a88c-fa47d67caa9d"],
    #     "Bộ Tư pháp": ["8fa5c8ab-10b0-44c7-921f-65c0fa683349"],
    #     "Bộ Công thương": ["54f8af5b-a7e1-4338-aa63-d3a8471d7430"],
    #     "Bộ Xây dựng": ["9418c69d-5df6-4a16-a89b-0b243d50b7da"],
    #     "Bộ Nội vụ": ["fb33fea4-15f5-45cf-8851-87d28e62d3ed"],
    #     "Bộ Tài chính": ["9b040451-e148-490e-9a84-76fe6dac50e7"],
    #     "Bộ Ngoại giao": ["a3d7a96f-0201-41a7-bc3f-9a423980d5a0"],
    #     "Bộ Khoa học và Công nghệ": ["3c3e1b99-0eae-4d19-911d-675cfca118b8"],
    #     "Bộ Văn hóa, Thể thao và Du lịch": ["be902921-b58d-4e9c-9f4b-2f561e620e64"],
    #     "Bộ Dân tộc và Tôn giáo": ["9503faa2-a2e8-4a39-981c-f230fd055eea"],
    #     "Bộ Giáo dục và Đào tạo": ["a1ad2953-5dc1-4278-9d22-fa1f09ff107c"],
    #     "Bộ Nông nghiệp và Môi trường": ["ff2336b0-1d07-49c9-a0c0-fc70f4039ef4"],
    #     "Ngân hàng Nhà nước Việt Nam": ["c164cddc-4606-40cf-8712-ffac1f5d7c04"],
    #     "Thanh tra Chính phủ": ["f8c49735-814e-4837-be1d-0ee19add9eeb"],
    #     "Bộ Quốc phòng": ["ca9e5ca9-234f-47e9-ba32-02b5235ee254"],
    #     "Bộ Công an": ["4128f8ee-7d99-4b38-a684-b2d99f36ab38"],
    #     "Viện trưởng Viện kiểm sát nhân dân tối cao": ["eb58765e-8082-4009-b8dc-cdd3dc6685a5"]
    # }
    
    # law_articles_26102025
    data = {
        "Quốc hội": [
            "a1d8889e-026e-4c22-8e5c-933acfeae3d1",
            "254fc385-7db6-4d3f-8743-adb14d16153a",
            "c9fb03eb-bff4-47ed-b6db-6bcbf6064fea",
            "ceea86f3-2c06-42b6-b424-0cbfc0e7c459",
            "6c570086-4ae7-4d7c-b35b-5a6163439851",
            "649ddf1e-0f6b-481e-84db-26426ff44c4c"
        ],
        "Chủ tịch nước": [
            "e528fdc8-0cea-4679-912f-dc63ab0a25e9"
        ],
        "Chính phủ": [
            "19c4488f-6720-47a6-96e2-da7bddb772ba",
            "32a067ab-ee25-49a1-8a21-473e4731f755"
        ],
        "Thủ tướng Chính phủ": [
            "24bcd465-dc29-4881-9bbb-a4ed2d678893",
            "939dae58-9eca-40e8-ab8d-5e712596f8df"
        ],
        "Bộ Y tế": [
            "89341e49-601f-468a-823a-f21b9e0c071b"
        ],
        "Bộ Tư pháp": [
            "273812ba-a90a-4ab7-a7e0-2e08d1481268"
        ],
        "Bộ Công thương": [
            "e0773e9c-446b-452b-bc6d-f3ecb8124cf8"
        ],
        "Bộ Xây dựng": [
            "073afd6b-4890-4b28-913f-a598d37ebcb0"
        ],
        "Bộ Nội vụ": [
            "402e8928-0ac2-470a-8237-81e2fb4c7882"
        ],
        "Bộ Tài chính": [
            "33d18a19-1163-4369-8829-4e50ad6379dc"
        ],
        "Bộ Ngoại giao": [
            "3ec52b17-8c3f-493c-9262-19960a52df54"
        ],
        "Bộ Khoa học và Công nghệ": [
            "ea997f3c-1d18-47f0-b31c-63160ce816e2"
        ],
        "Bộ Văn hóa, Thể thao và Du lịch": [
            "d71df502-c758-438a-9cdd-cacbf0f60426"
        ],
        "Bộ Dân tộc và Tôn giáo": [
            "81f8ce77-d41f-487a-a614-d1e9dc51f315"
        ],
        "Bộ Giáo dục và Đào tạo": [
            "1a7cd9f7-b8e3-4744-abee-1628ba90baa9"
        ],
        "Bộ Nông nghiệp và Môi trường": [
            "2dff85e1-ee3b-4832-afb3-525f05dc05e7"
        ],
        "Ngân hàng Nhà nước Việt Nam": [
            "980cf140-e9e6-4865-a9f2-d2e654e5599b"
        ],
        "Thanh tra Chính phủ": [
            "d726a0e6-f938-4a60-99fb-09c634c5c731"
        ],
        "Bộ Quốc phòng": [
            "10ac5f10-9ade-4207-bdb5-2a6b8f7d50ba"
        ],
        "Bộ Công an": [
            "7b309ac1-0402-4326-abf2-9d1b9fa2981e"
        ],
        "Viện trưởng Viện kiểm sát nhân dân tối cao": [
            "22e86416-bdc4-43ba-8b3e-553070183a33"
        ]
    }
    records = []
    for k, v in data.items():
        for article_id in v:
            law_article = get_law_articles(article_id)[0]
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
                'doc_effective_date': law_article.get('doc_effective_date',''),
                'doc_expiry_date': law_article.get('doc_expiry_date',''),
                'effective_status_id': law_article.get('effective_status_id', ''),
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'last_modified_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            records.append(record)
            result_raw, result_mapping = convert_to_data_model(record)
            law_authority_collection.insert_one(result_raw)
            law_authority_mapping_collection.insert_one(result_mapping)
    return records


if __name__ == "__main__":
    get_authority(get_law_articles())

    # Quét tất cả các article đã xác nhận là nội dung giao quyền
    extract_authority_other()
