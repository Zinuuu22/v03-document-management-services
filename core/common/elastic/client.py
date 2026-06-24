import os
import sys
from datetime import datetime
import structlog
from elasticsearch import Elasticsearch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

from logs.logger_conf import setup_logging
from constants import ElasticConfig
from core.common.external_logging import execute_external_with_logging

setup_logging()
logger = structlog.get_logger()

def classify_elastic_error(e):
    e_str = str(e).lower()
    e_type = type(e).__name__.lower()
    if "timeout" in e_type or "timeout" in e_str:
        return "timeout"
    if "connection" in e_type or "connection error" in e_str:
        return "network"
    if "unavailable" in e_str or "503" in e_str or "502" in e_str:
        return "service_unavailable"
    if "circuit_breaking" in e_str or "too_many_requests" in e_str or "429" in e_str:
        return "resource_limitation"
    return "unknown"

def execute_elastic_with_logging(func, action, operation, meta=None):
    return execute_external_with_logging(
        func=func,
        action=action,
        service_name="elasticsearch",
        operation=operation,
        error_classifier=classify_elastic_error,
        meta=meta,
        error_code="ES",
        slow_threshold_ms=1000
    )

def map_mongo_to_elasticsearch(document: dict) -> dict:
    """
    Map document từ MongoDB sang schema Elasticsearch chuẩn hoá.

    Quy tắc:
    - Trường đơn thiếu → chuỗi rỗng "".
    - Trường mảng thiếu → mảng rỗng [].
    - Các field metadata admin (created_at, created_by, …) KHÔNG được đưa vào ES.
    - Date fields: Convert string dates to ISO format for ES compatibility.

    Args:
        document: Document gốc từ MongoDB.

    Returns:
        Dict sẵn sàng để index vào Elasticsearch.
    """
    
    def normalize_date(date_value):
        """Convert date to ES-compatible format (ISO or None)."""
        if not date_value:
            return None
        if isinstance(date_value, datetime):
            return date_value.isoformat()
        if isinstance(date_value, str):
            # Convert "YYYY-MM-DD HH:MM:SS" to "YYYY-MM-DDTHH:MM:SS"
            return date_value.replace(' ', 'T') if ' ' in date_value else date_value
        return date_value
    
    doc_id = document.get("doc_id", "")
    if not doc_id:
        raise ValueError("document phải có trường 'doc_id'")

    return {
        # --- Định danh ---
        "doc_id":               document.get("doc_id", ""),
        "doc_code":             document.get("doc_code", ""),

        # --- Nội dung văn bản (full-text search) ---
        "doc_title":            document.get("doc_title", ""),
        "doc_short_description":document.get("doc_short_description", ""),
        "doc_content":          document.get("doc_content", ""),

        # --- Ngày tháng ---
        "doc_issue_date":       normalize_date(document.get("doc_issue_date")),
        "doc_effective_date":   normalize_date(document.get("doc_effective_date")),
        "doc_expiry_date":      normalize_date(document.get("doc_expiry_date")),

        # --- Nguồn dữ liệu ---
        "data_source":          document.get("data_source", "SYSTEM"),

        # --- Phân loại / trạng thái ---
        "category_id":          document.get("category_id", ""),
        "effective_status_id":  document.get("effective_status_id", ""),
        "type_id":              document.get("type_id", ""),
        "issuing_level_id":     document.get("issuing_level_id", ""),

        # --- Lưu trữ ---
        "storage_id":           document.get("storage_id", ""),

        # --- Danh sách ID (array fields) ---
        "agency_ids":           document.get("agency_ids", []),
        "industry_sector_ids":  document.get("industry_sector_ids", []),
        "keyword_ids":          document.get("keyword_ids", []),
        "signer_ids":           document.get("signer_ids", []),
        "position_ids":         document.get("position_ids", []),
        "tree_ids":             document.get("tree_ids", []),
    }


# ---------------------------------------------------------------------------
# ElasticClient class
# ---------------------------------------------------------------------------

_elastic_client_instance = None

def get_elastic_client() -> Elasticsearch:
    """Trả về client Elasticsearch nguyên bản đã định cấu hình với basic auth (Singleton)"""
    global _elastic_client_instance
    if _elastic_client_instance is None:
        kwargs = {}
        if ElasticConfig.ELASTIC_USERNAME and ElasticConfig.ELASTIC_PASSWORD:
            kwargs["basic_auth"] = (ElasticConfig.ELASTIC_USERNAME, ElasticConfig.ELASTIC_PASSWORD)
        _elastic_client_instance = Elasticsearch([ElasticConfig.ELASTIC_HOST], **kwargs)
    return _elastic_client_instance

class ElasticClient:
    """Wrapper khởi tạo và giữ kết nối tới Elasticsearch."""

    def __init__(self):
        try:
            kwargs = {}
            if ElasticConfig.ELASTIC_USERNAME and ElasticConfig.ELASTIC_PASSWORD:
                kwargs["basic_auth"] = (ElasticConfig.ELASTIC_USERNAME, ElasticConfig.ELASTIC_PASSWORD)
            
            self.client = Elasticsearch([ElasticConfig.ELASTIC_HOST], **kwargs)
            
            def do_ping():
                if not self.client.ping():
                    raise ConnectionError(f"Failed to connect to Elasticsearch at {ElasticConfig.ELASTIC_HOST}")
                return True
                
            execute_elastic_with_logging(
                do_ping, 
                action="__init__", 
                operation="ping", 
                meta={"host": ElasticConfig.ELASTIC_HOST}
            )
            self.index = ElasticConfig.ELASTIC_INDEX
        except Exception as e:
            raise