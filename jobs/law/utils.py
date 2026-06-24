from core.common.mongo.client import get_mongo_client
import os
import sys
import structlog
from datetime import datetime
from pymongo import MongoClient
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from core.v03.metadata_extractor.fields.extract_document_category import extract_document_category
from constants import MongoDBConfig, MigrateConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()


def connect_to_databases():
    """Kết nối tới raw_db và core_db."""
    try:
        client = get_mongo_client()

        raw_db = client[MigrateConfig.MIGRATE_RAW_DB]
        core_db = client[MigrateConfig.MIGRATE_CORE_DB]
        return raw_db, core_db
    except Exception as e:
        logger.error(action="connect_to_databases", event="connect_to_databases_failed", **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
        raise


def parse_datetime(date_str):
    """Chuyển đổi chuỗi ngày giờ sang định dạng datetime."""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return None


def parse_date(date_str):
    """Chuyển đổi chuỗi ngày sang chuỗi datetime %Y-%m-%d %H:%M:%S"""
    logger.info(action="parse_date", event="parse_date_started", date=date_str)

    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    logger.info(action="parse_date", event="date_stripped", date=date_str)

    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%d/%m/%Y',
        '%Y-%m-%d',
        '%d-%m-%Y',
        '%Y/%m/%d'
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue

    return None



def get_last_modified_by(doc):
    val = doc.get('last_modified_by', None)
    if val is None or val == '':
        # Trả về thời gian hiện tại theo định dạng yêu cầu
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return val

def get_doc_type(doc):
    properties = doc.get('properties', [])
    for prop in properties:
        if prop['key'] == 'Loại văn bản':
            return prop['value']
    return None


def check_document_category(doc):
    document_code = doc.get('document_code', None)
    document_type = get_doc_type(doc)  
    response = extract_document_category(document_code=document_code, document_type=document_type)
    return response.get('document_category', '')

def check_document_level(document_code):
    response = {"document_level": "Địa Phương"}

    if document_code.find('UBND') != -1 or document_code.find('HDND') != -1 or document_code.find('HĐND') != -1:
        response["document_level"] = "Địa Phương" 
    else:
        response["document_level"] = "Trung Ương"

    return response
if __name__ == "__main__":
    pass