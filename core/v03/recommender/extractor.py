from core.common.elastic.client import get_elastic_client
from core.common.mongo.client import get_mongo_client

import re
import sys
import os
import structlog
from pymongo import MongoClient
from io import BufferedReader, BytesIO
from elasticsearch import Elasticsearch
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

# Import các cấu hình và module cần thiết
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig, \
    RecommendDocumentConfig, ElasticConfig
from core.common.reader import DocumentProcessor
from core.v03.metadata_extractor import extract_metadata  
from core.v03.content_extractor import extract_components
from core.v03.relationship_extractor.utils import extract_brief, mapping_document
from core.common.minio import MinIOClient
from logs.logger_conf import setup_logging
setup_logging()
logger = structlog.get_logger()
        
minio_client = MinIOClient()
documentProcessor = DocumentProcessor()

# Kết nối MongoDB
client = get_mongo_client()
elastic_client = get_elastic_client()


db = client[MigrateConfig.MIGRATE_CORE_DB]
documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
reference_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_COLLECTION_NAME]
law_doc_type_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_TYPE_COLLECTION_NAME]


def parse_datetime(value: str) -> str | None:
    """Chuyển '2021-09-15 00:00:00' -> '2021-09-15T00:00:00', bỏ qua nếu rỗng."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return value


def map_document_to_output(doc: dict) -> dict:
    """
    Map document từ Elasticsearch sang output schema chuẩn.
    """
    doc_type_name = law_doc_type_collection.find_one({"type_id": doc.get("type_id")}).get("doc_type_name",'')
    return {
        # ✅ Map trực tiếp
        "code":                 doc.get("doc_id"),
        "name":                 doc.get("doc_title"),
        "description":          doc.get("doc_content"),
        "shortDescription":     doc.get("doc_short_description"),
        "documentCode":         doc.get("doc_code"),
        "storageCode":          doc.get("storage_id"),
        "documentCategoryCode": doc.get("type_id"),
        "issuedLevelCode":      doc.get("issuing_level_id"),
        "decreeStatusCode":     doc.get("effective_status_id"),
        "dataSource":           doc.get("data_source"),
        "keywordCodes":         [x for x in doc.get("keyword_ids", []) if x],
        "industrySectorCodes":  [x for x in doc.get("industry_sector_ids", []) if x],
        "agencyIssuedCodes":    [x for x in doc.get("agency_ids", []) if x],
        "signerCodes":          [x for x in doc.get("signer_ids", []) if x],
        "positionCodes":        [x for x in doc.get("position_ids", []) if x],
        "decreeIssued":         parse_datetime(doc.get("doc_issue_date")),
        "decreeEffect":         parse_datetime(doc.get("doc_effective_date")),
        "documentTypeName":     doc_type_name
    }


def get_upload_record_by_storage_id(storage_id):
    upload_record = upload_record_collection.find_one({"storage_id": storage_id})
    return upload_record


def get_document_info_by_id(doc_id):
    """
    Lấy thông tin cơ bản của văn bản từ database dựa trên doc_id.
    
    Args:
        doc_id (str): ID của văn bản.
    
    Returns:
        list: Danh sách chứa thông tin doc_code và doc_title.
    """
    documents = documents_collection.find({"doc_id": doc_id})
    return list(documents)


def search_document_from_ids(doc_ids):
    """
    Tìm kiếm văn bản từ elastic dựa trên doc_id.
    
    Args:
        doc_ids (list): ID của văn bản.
    
    Returns:
        list: Danh sách chứa thông tin doc_code và doc_title.
    """
    # Define the search query
    query = {
        "query": {
            "terms": {
                "doc_id": doc_ids
            }
        }
    }    
    try:
        # Execute the search
        responses = elastic_client.search(index=ElasticConfig.ELASTIC_INDEX, body=query)        
        documents = []
        for hit in responses["hits"]["hits"]:
            documents.append(map_document_to_output(hit['_source']))        
    except Exception as e:
        logger.error("search_document_failed", action="search_document_from_ids", **{"error.code": "ES", "error.message": str(e)}, exc_info=True)
        return None
    return documents


def merge_related_documents(related_docs):
    """
    Gộp tất cả doc_ids từ các nhóm quan hệ thành một tập hợp duy nhất.
    
    Args:
        related_docs (dict): Dictionary chứa các nhóm văn bản theo quan hệ.
    
    Returns:
        set: Tập hợp tất cả doc_ids duy nhất.
    """
    final_doc_ids =     set()
    for _, doc_ids in related_docs.items():
        final_doc_ids.update(doc_ids)
    return final_doc_ids        


def get_related_documents_from_db(doc_id, recommend_types=None):
    """
    Lấy danh sách văn bản liên quan từ database dựa vào doc_id và loại quan hệ recommend_type.
    Quan hệ có thể bao gồm: AMENDED, REPLACED, BASIS, DETAIL, CONTENT_CONNECTION.
    
    Args:
        doc_id (str): ID văn bản gốc.
        recommend_type (str): Loại quan hệ (phải thuộc RecommendDocumentConfig.RECOMMEND_TYPE).
    
    Returns:
        dict: Các nhóm văn bản liên quan được phân loại theo quan hệ.
    """
    if recommend_types is None:
        return None, "recommend_types is invalid"    
    
    related_docs = {}
    for recommend_type in recommend_types:
        if recommend_type not in RecommendDocumentConfig.RECOMMEND_TYPE:
            return None, "recommend_type is invalid"    
    
    
    amended_doc_ids= set()
    replaced_doc_ids= set()
    B_doc_ids = set()
    
    # Lấy các văn bản được sửa đổi hoặc thay thế bởi doc_id
    references = reference_collection.find(
        {"source_id": doc_id, "reference_type": {"$in": ["AMENDED", "REPLACED"]}}
    )
    for reference in list(references):
        if reference['reference_type'] == "AMENDED":
            amended_doc_ids.add(reference['target_id'])
        elif reference['reference_type'] == "REPLACED":
            replaced_doc_ids.add(reference['target_id'])
        B_doc_ids.add(reference['target_id'])

    A_doc_ids = set()
    C_doc_ids = set() 
    if B_doc_ids:
        for doc_id in list(B_doc_ids):            
            references = reference_collection.find(
                {"source_id": doc_id, 
                "reference_type": {"$in": ["BASIS", "AMEND", "REPLACE", "DETAIL", "CONTENT_CONNECTION"]}}
            )
            for reference in list(references):
                if reference['reference_type'] == "BASIS":
                    C_doc_ids.add(reference['target_id'])
                elif reference['target_id'] not in C_doc_ids not in B_doc_ids:
                    A_doc_ids.add(reference['target_id'])
    
    # Lấy văn bản chi tiết
    D_doc_ids = set()
    references = reference_collection.find({"source_id": doc_id, "reference_type": "DETAIL"})
    for reference in list(references):
        D_doc_ids.add(reference['target_id'])

    # Lấy văn bản có kết nối nội dung
    E_doc_ids = set()
    references = reference_collection.find({"source_id": doc_id, "reference_type": "CONTENT_CONNECTION"})
    for reference in list(references):
        E_doc_ids.add(reference['target_id'])

    
    if "TYPE_1" in recommend_types:
        related_docs["TYPE_1"] = list(amended_doc_ids)
    if "TYPE_2" in recommend_types:
        related_docs["TYPE_2"] = list(replaced_doc_ids)
    if "TYPE_3" in recommend_types:
        related_docs["TYPE_3"] = list(C_doc_ids)    
    if "TYPE_4" in recommend_types:
        related_docs["TYPE_4"] = list(A_doc_ids)
    if "TYPE_5" in recommend_types:
        related_docs["TYPE_5"] = list(D_doc_ids | E_doc_ids)        
    return related_docs, None


def extract_laws(content):
    pattern = re.compile(
    r"(Luật(?: số)? [^;,.]+?\d+/\d{4}/[A-Z0-9\-]+|"
    r"Nghị định(?: số)? [^;,.]+?\d+/\d{4}/[A-Z0-9\-]+|"
    r"Thông tư(?: số)? [^;,.]+?\d+/\d{4}/[A-Z0-9\-]+|"
    r"Quyết định(?: số)? [^;,.]+?\d+/\d{4}/[A-Z0-9\-]+)",
    re.UNICODE)
    matches = pattern.findall(content)
    return matches


def get_related_documents_from_upload(storage_id=None, doc_content=None, recommend_types =None):
    """
    Lấy danh sách văn bản liên quan dựa trên file upload hoặc nội dung doc_content.
    
    Args:
        storage_id (str): Mã lưu trữ của văn bản (tùy chọn).
        doc_content (str): Nội dung văn bản (tùy chọn).
        recommend_type (str): Loại quan hệ cần phân tích.
    
    Returns:
        dict: Các văn bản liên quan không nằm trong DB.
    """
    
    if recommend_types is None:
        return None, "recommend_types is invalid"    
    
    related_docs = {}
    for recommend_type in recommend_types:
        if recommend_type not in RecommendDocumentConfig.RECOMMEND_TYPE:
            return None, "recommend_type is invalid"    
        related_docs[recommend_type] = set()
    
    
    # Download file từ storage_id
    if storage_id is not None:
        upload_record = get_upload_record_by_storage_id(storage_id)
        if upload_record is None:
            return None, "upload_record is invalid"            
        object_name = upload_record['__text']
        file_stream = minio_client.download_file(object_name)        
        buffered_stream = BufferedReader(file_stream)
        byte_stream = BytesIO(buffered_stream.read())
        path_file = documentProcessor.convert_doc_to_docx(byte_stream)
        logger.info("convert_path_file", action="get_related_documents_from_upload", path=path_file)
        doc_content = documentProcessor.read_docx_v2(path_file)
    else:
        doc_content = None

    if doc_content is None:
        return None, "doc_content is invalid"
    logger.info("load_doc_content", action="get_related_documents_from_upload", content_len=len(doc_content))

    # Trích xuất Metadata    
    metadata = extract_metadata(
        content=doc_content, 
        metadata_names=['document_code', 'document_type', 'document_name']
    )
    logger.info("extract_metadata", action="get_related_documents_from_upload", metadata=metadata)

    # Trích xuất các thành phần (segments)
    segments = extract_components(
        content=doc_content, 
        document_code=metadata['document_code']
    )
    logger.info("extract_segments", action="get_related_documents_from_upload", count=len(segments))
    
    error = None
    document = documents_collection.find_one({"doc_code": metadata['document_code']})
    if not document:
        brief_content = extract_brief(doc_content)
        logger.info("extract_brief_content", action="get_related_documents_from_upload", content_len=len(brief_content) if brief_content else 0)
        
        matches = extract_laws(brief_content)
        logger.info("extract_law_matches", action="get_related_documents_from_upload", count=len(matches))
        
        for match in matches:
            document = mapping_document(match)
            logger.info("document_mapped", action="get_related_documents_from_upload", document=document)
            if document:
                related_docs['TYPE_5'].add(document[0]['_id'])
    else:
        doc_id = document['doc_id']
        related_docs, error = get_related_documents_from_db(doc_id, recommend_types)
    
    return related_docs, error


if __name__ == "__main__":
    import time    
    start_time = time.time()

    status = "NOT_IN_DB"
    if status == "IN_DB":
        doc_id = "296661"    
        related_docs = get_related_documents_from_db(doc_id=doc_id, recommend_types=["TYPE_1", "TYPE_2", "TYPE_3", "TYPE_4", "TYPE_5"])    
    else:
        storage_id = "f6c1eaa4-5398-4a4e-ade3-2f85852e2dd5"                
        related_docs, error = get_related_documents_from_upload(storage_id=storage_id, 
                                                                doc_content=None, 
                                                                recommend_types=["TYPE_1", "TYPE_2", "TYPE_3", "TYPE_4", "TYPE_5"])
    
    
    logger.info("related_documents_found", related_docs=related_docs)
    for type_relationship, doc_ids in related_docs.items():
        logger.info(type_relationship)
        for doc_id in doc_ids:
            doc_info = get_document_info_by_id(doc_id)
            logger.info(doc_info)    
    
    for type_relationship, doc_ids in related_docs.items():
        logger.info("relationship_type_count", type=type_relationship, count=len(doc_ids))
    filtered_doc_ids = merge_related_documents(related_docs=related_docs)
    logger.info("filtered_documents", count=len(filtered_doc_ids))    
    end_time = time.time()
    logger.info("time_elapsed", time = end_time - start_time)    
