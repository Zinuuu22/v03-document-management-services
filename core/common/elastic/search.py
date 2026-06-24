from typing import Any, Dict, List, Optional

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from .client import ElasticClient, execute_elastic_with_logging


# ---------------------------------------------------------------------------
# ElasticSearcher class
# ---------------------------------------------------------------------------

class ElasticSearcher(ElasticClient):
    """Quản lý các truy vấn tìm kiếm trên Elasticsearch."""

    # ------------------------------------------------------------------
    # Lấy doc_content theo doc_id
    # ------------------------------------------------------------------

    def get_document_content(self, doc_id: str) -> str:
        """
        Lấy nội dung toàn văn (doc_content) của một document theo doc_id.

        Args:
            doc_id: ID của document cần lấy nội dung.

        Returns:
            Chuỗi nội dung văn bản, hoặc chuỗi rỗng nếu không tìm thấy.
        """
        def do_get():
            result = self.client.get(
                index=self.index,
                id=doc_id,
                _source=["doc_content"],
                ignore=[404],
            )

            if not result.get("found"):
                logger.info("document_not_found", action="get_document_content", doc_id=doc_id)
                return ""

            content = result["_source"].get("doc_content", "")
            return content.strip().replace(".-", ".") if content else ""
            
        try:
            return execute_elastic_with_logging(
                do_get,
                action="get_document_content",
                operation="get_document_content",
                meta={"index": self.index, "doc_id": doc_id}
            )
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Full-text search + filter
    # ------------------------------------------------------------------

    def search_documents(
        self,
        keyword: Optional[str] = None,
        # --- filters ---
        category_id: Optional[str] = None,
        type_id: Optional[str] = None,
        effective_status_id: Optional[str] = None,
        agency_ids: Optional[List[str]] = None,
        issuing_level_id: Optional[str] = None,
        doc_issue_date_from: Optional[str] = None,   # "YYYY-MM-DD"
        doc_issue_date_to: Optional[str] = None,     # "YYYY-MM-DD"
        # --- pagination ---
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """
        Full-text search trên doc_content và doc_title, kết hợp với các filter.

        Args:
            keyword: Từ khoá tìm kiếm (tìm trên doc_title và doc_content).
            category_id: Filter theo hình thức văn bản.
            type_id: Filter theo loại văn bản.
            effective_status_id: Filter theo trạng thái hiệu lực.
            agency_ids: Filter theo danh sách cơ quan ban hành (OR giữa các phần tử).
            issuing_level_id: Filter theo cấp ban hành.
            doc_issue_date_from: Ngày ban hành từ (inclusive).
            doc_issue_date_to: Ngày ban hành đến (inclusive).
            page: Trang hiện tại (bắt đầu từ 1).
            page_size: Số kết quả mỗi trang.

        Returns:
            Dict gồm total, page, page_size, và hits (danh sách _source).
        """
        must: List[Dict] = []
        filters: List[Dict] = []

        # --- Full-text search ---
        if keyword:
            must.append({
                "multi_match": {
                    "query": keyword,
                    "fields": ["doc_title^2", "doc_content"],
                    "type": "best_fields",
                }
            })

        # --- Filters ---
        if category_id:
            filters.append({"term": {"category_id": category_id}})

        if type_id:
            filters.append({"term": {"type_id": type_id}})

        if effective_status_id:
            filters.append({"term": {"effective_status_id": effective_status_id}})

        if issuing_level_id:
            filters.append({"term": {"issuing_level_id": issuing_level_id}})

        if agency_ids:
            filters.append({"terms": {"agency_ids": agency_ids}})

        if doc_issue_date_from or doc_issue_date_to:
            date_range: Dict[str, str] = {}
            if doc_issue_date_from:
                date_range["gte"] = doc_issue_date_from
            if doc_issue_date_to:
                date_range["lte"] = doc_issue_date_to
            filters.append({"range": {"doc_issue_date": date_range}})

        # --- Assemble query ---
        if must or filters:
            query = {
                "bool": {
                    **({"must": must} if must else {"must": [{"match_all": {}}]}),
                    **({"filter": filters} if filters else {}),
                }
            }
        else:
            query = {"match_all": {}}

        body = {
            "query": query,
            "from": (page - 1) * page_size,
            "size": page_size,
            "_source": {
                "excludes": ["doc_content"]   # không trả content trong listing
            },
        }

        def do_search():
            response = self.client.search(index=self.index, body=body)
            hits = response["hits"]["hits"]
            total = response["hits"]["total"]["value"]

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "hits": [hit["_source"] for hit in hits],
            }
            
        try:
            return execute_elastic_with_logging(
                do_search,
                action="search_documents",
                operation="search_documents",
                meta={"index": self.index, "keyword": keyword, "page": page, "page_size": page_size}
            )
        except Exception:
            return {"total": 0, "page": page, "page_size": page_size, "hits": []}

    # ------------------------------------------------------------------
    # Tìm document theo doc_id (tương thích ngược với code cũ)
    # ------------------------------------------------------------------

    def search_document(self, doc_id: str) -> Optional[Dict]:
        """
        Tìm document theo trường 'code' (doc_id).
        Tương thích ngược với hàm search_document() standalone cũ.

        Args:
            doc_id: Giá trị cần tìm trong trường 'code'.

        Returns:
            Dict _source của document đầu tiên tìm thấy, hoặc None nếu không có.
        """
        query = {
            "query": {
                "match": {
                    "doc_id": doc_id
                }
            }
        }

        def do_search():
            response = self.client.search(index=self.index, body=query)
            hits = response["hits"]["hits"]

            if not hits:
                logger.info("document_not_found", action="search_document", doc_id=doc_id)
                return None

            return hits[0]
            
        try:
            return execute_elastic_with_logging(
                do_search,
                action="search_document",
                operation="search_document",
                meta={"index": self.index, "doc_id": doc_id}
            )
        except Exception:
            return None