from core.common.mongo.client import get_mongo_client
import os
import sys
import re

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )
)
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig
from pymongo import MongoClient
import time


client = get_mongo_client()

db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
law_agencies_collection = db[MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME]

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
    "Bộ Văn hóa, Thể thao và Du lịch",
    "Bộ Dân tộc và Tôn giáo",
    "Bộ Giáo dục và Đào tạo",
    "Bộ Nông nghiệp và Môi trường",
    "Ngân hàng Nhà nước Việt Nam",
    "Thanh tra Chính phủ",
    "Bộ Quốc phòng",
    "Bộ Công an",
    "Viện trưởng Viện kiểm sát nhân dân tối cao"
]

def get_agency_id(agency_name: str):
    try:
        return law_agencies_collection.find_one({"agency_name": agency_name})["agency_id"]
    except Exception as e:
        return None

def split_clause_content(full_text):
    if not isinstance(full_text, str):
        return []

    # Split tại vị trí bắt đầu của một khoản: optional whitespace + số[.số...]. + space
    clauses = re.split(r"(?=(?:^|\n)\s*\d+(?:\.\d+)*\.\s)", full_text.strip(), flags=re.UNICODE)


    results = []
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue

        # Bắt: 1) numbering dạng 1. hoặc 1.2. hoặc 1.2.3.
        #       2) phần tiêu đề ngắn (non-greedy) trước dấu ':' hoặc newline hoặc hết chuỗi
        #       3) phần thân còn lại (có thể multiline)
        m = re.match(
            r"^\s*(\d+(?:\.\d+)*\.)\s*(.*?)(?:[:\n]|$)\s*(.*)$",
            clause,
            flags=re.DOTALL | re.UNICODE
        )
        if not m:
            # nếu không match theo kiểu trên, cố gắng một match đơn giản (toàn bộ clause là header)
            m2 = re.match(r"^\s*(\d+(?:\.\d+)*\.\s*.*)$", clause, flags=re.UNICODE)
            if m2:
                header = m2.group(1).strip()
                results.append({
                    "clause_content_title": header,
                    "clause_content_detail": None
                })
            continue

        numbering = m.group(1).strip()              # ví dụ: "1.2."
        header_text = m.group(2).strip()            # tiêu đề ngay sau số (có thể rỗng)
        clause_body = m.group(3).strip()            # phần thân

        # hợp nhất phần tiêu đề (numbering + header_text nếu có)
        if header_text:
            clause_header = f"{numbering} {header_text}"
        else:
            clause_header = numbering

        # tách các mục con (a) b) ...) nếu có xuống dòng
        if clause_body and "\n" in clause_body:
            # lookahead: sau newline có kí tự a-z (có dấu tiếng Việt) + ) 
            split_pattern = (
                r"(?<=\n)(?=[a-zàáâãèéêìíòóôõùúăđĩũơư"
                r"ạảấầẩẫậắằẳẵặẹẻẽềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]\))"
            )
            items = re.split(split_pattern, clause_body, flags=re.UNICODE | re.IGNORECASE)
            items = [it.strip() for it in items if it.strip()]
        else:
            # Nếu body không có xuống dòng nhưng chứa nội dung (ví dụ: "Tiêu đề: nội dung"),
            # có thể tách thành một item duy nhất
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
    # pattern chính
    pattern = re.compile(
        r"(?<!\d)([2-9]|\d{2,})\. " + r"(?P<agency>" + "|".join(AGENCY_LIST) + r") quy định chi tiết (?P<clause>.+?)(?P<article>Điều [\w\d]+|Điều này)",
        flags=re.IGNORECASE | re.UNICODE
    )
    match = pattern.search(text)

    if not match:
        # pattern ngắn (chỉ "Điều này")
        pattern_short = re.compile(
            r"(?<!\d)([2-9]|\d{2,})\. " + r"(?P<agency>" + "|".join(AGENCY_LIST) + r") quy định chi tiết (?P<article>Điều [\w\d]+|Điều này)",
            flags=re.IGNORECASE | re.UNICODE
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

        # Nếu có “khoản” → lấy các khoản tương ứng
        if result["clause"] and "khoản" in result["clause"]:
            clause_pattern = re.compile(r"((\d+\..+?)(?=(\n\d+\.|\Z)))", re.DOTALL)
            clauses = clause_pattern.findall(text)
            matched_clauses = []
            for num, clause_text, _ in clauses:
                if re.search(rf"\b{num}\b", result["clause"]):
                    matched_clauses.append(clause_text.strip())
            if matched_clauses:
                result["clause_content"] = "\n".join(matched_clauses)

        # Nếu không có "khoản" → lấy phần TRƯỚC đoạn "quy định chi tiết..."
        else:
            # tìm vị trí dòng chứa câu quy định chi tiết
            lines = text.strip().splitlines()
            for i, line in enumerate(lines):
                if re.search(rf"{result['agency']} quy định chi tiết", line, re.IGNORECASE):
                    # nối các dòng trước đó thành nội dung
                    content_before = "\n".join(lines[:i]).rstrip()
                    # loại bỏ dòng đánh số khoản 2. ở cuối nếu có
                    content_before = re.sub(r"\n?\s*\d+\.\s*$", "", content_before)
                    result["clause_content"] = content_before.strip()
                    break

        return result

    return {"has_pattern": False}

def get_law_articles(article_id=None):
    pipeline = []

    # Thêm điều kiện match nếu có article_id
    if article_id:
        pipeline.append({'$match': {'article_id': article_id}})

    # Tiếp tục các stage sau
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

# Case1 Giao quyền trực tiếp    
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

if __name__ == "__main__":
    # case 1:
    records = []
    for k, v in data.items():
        for article_id in v:
            articles = get_law_articles(article_id)
            if not articles:
                continue
            article = articles[0]
            for item in split_clause_content(article['article_content']):
                record = {
                    'doc_id': article['doc_id'],
                    'doc_title': article['doc_title'],
                    'article_id': article['article_id'],
                    'article_title': article['article_title'],
                    'article_content': article['article_content'],
                    'agency_id': get_agency_id(k),
                    'agency_name':k,
                    'authority_content':item['clause_content_title'],
                    'authority_content_detail': item['clause_content_detail'],
                    'status': article.get('status'),
                    'doc_effective_date': article['doc_effective_date'],
                    'doc_expiry_date': article['doc_expiry_date'],
                    'effective_status_id': article['effective_status_id'],
                }
                print(record)