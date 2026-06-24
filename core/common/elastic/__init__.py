from .client import ElasticClient
from .index import ElasticIndexer
from .search import ElasticSearcher
from typing import Dict, Optional

__all__ = ["ElasticClient", "ElasticIndexer", "ElasticSearcher", "search_document", "search_document_content"]


def search_document(doc_id: str) -> Optional[Dict]:
    """
    Tìm document theo trường 'code'.
    Tương thích ngược với: from core.common.elastic import search_document
    """
    return ElasticSearcher().search_document(doc_id)


def search_document_content(doc_id: str) -> str:
    """
    Lấy doc_content theo doc_id.
    Tương thích ngược với: from core.common.elastic import search_document_content
    """
    return ElasticSearcher().get_document_content(doc_id)