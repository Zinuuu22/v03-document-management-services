from core.common.mongo.client import get_mongo_client
import structlog
import sys
import os
import uuid
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.common.elastic import ElasticIndexer
from core.common.minio import MinIOClient
from jobs.law.migrate_from_domino.utils import get_view_all_unid, get_all_document_unids, extract_domino_metadata, map_to_target_schema
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

mongo_client = get_mongo_client()
db = mongo_client[MigrateConfig.MIGRATE_RAW_DB]
document_segment_colection = db[MongoDBCollectionConfig.RAW_DOCUMENTS_SEGMENTS_COLLECTION_NAME]
resources_col = db[MongoDBCollectionConfig.RAW_RESOURCE_COLLECTION_NAME]

minio_client = MinIOClient()
elastic_client = ElasticIndexer()
error_lock = threading.Lock()


def process_single_unid(unid, existed_codes):
    """
    Hàm xử lý cho một UNID đơn lẻ
    """
    local_errors = {
        "NOT_FOUND_FILE_URL_ERROR": None,
        "DOWNLOAD_FILE_ERROR": None,
    }

    try:
        if unid in existed_codes:
            return None

        # 1. Trích xuất metadata
        doc = extract_domino_metadata(unid)
        logger.warning(action="process_single_unid", event="unid_processing_started", unid=unid, so_ky_hieu=doc.get('so_ky_hieu'))

        file_urls = doc.get("file_dinh_kem", [])
        if len(file_urls) == 0:
            logger.error(action="process_single_unid", event="file_url_not_found", **{"error.code": "EXT", "error.message": "NOT_FOUND_FILE_URL_ERROR"}, unid=unid)
            local_errors["NOT_FOUND_FILE_URL_ERROR"] = unid
            return local_errors

        # 2. Mapping dữ liệu theo schema yêu cầu
        document_segment = map_to_target_schema(doc)
        
        # 3. Thao tác với Database
        # Lưu ý: Pymongo thread-safe nên có thể dùng chung client trong thread
        data = document_segment_colection.find_one({"code": unid})        
        
        if data is not None:
            logger.info(action="process_single_unid", event="unid_found_updating", unid=unid)
            document_segment["code"] = data["code"]
            document_segment["storage_code"] = data["storage_code"]
            document_segment_colection.update_one({"code": unid}, {"$set": document_segment})
        else:
            logger.info(action="process_single_unid", event="unid_not_found_inserting", unid=unid)
            document_segment["code"] = unid
            document_segment["storage_code"] = str(uuid.uuid4())
            document_segment_colection.insert_one(document_segment)            
        return None

    except Exception as e:
        logger.error(action="process_single_unid", event="unid_processing_failed", **{"error.code": "EXT", "error.message": str(e)}, unid=unid, exc_info=True)
        return None


def crawl_documents_multithreaded(unids: list[str], max_workers: int = 10):
    existed_codes = {
        d["code"]
        for d in document_segment_colection.find({}, {"code": 1, "_id": 0})
    }
    
    final_errors = {
        "NOT_FOUND_FILE_URL_ERROR": [],
        "DOWNLOAD_FILE_ERROR": [],
    }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_unid = {executor.submit(process_single_unid, unid, existed_codes): unid for unid in unids}
        
        for future in as_completed(future_to_unid):
            result = future.result()
            if result:
                with error_lock:
                    if result["NOT_FOUND_FILE_URL_ERROR"]:
                        final_errors["NOT_FOUND_FILE_URL_ERROR"].append(result["NOT_FOUND_FILE_URL_ERROR"])
                    if result["DOWNLOAD_FILE_ERROR"]:
                        final_errors["DOWNLOAD_FILE_ERROR"].append(result["DOWNLOAD_FILE_ERROR"])
    return final_errors
    

def process():
    view_unid = get_view_all_unid()
    if not view_unid:
        logger.error(action="process", event="view_not_found", **{"error.code": "EXT", "error.message": "View Van ban ALL not found"})
        return
    unids = get_all_document_unids(view_unid)
    errors = crawl_documents_multithreaded(unids)
    logger.info(action="process", event="migration_errors_summary", errors=errors)
    return errors

if __name__ == "__main__":
    errors = process()
    logger.info(action="main", event="migration_errors_summary", errors=errors)