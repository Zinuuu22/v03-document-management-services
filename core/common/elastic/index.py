from typing import Any, Dict, List

from elasticsearch import helpers

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from constants import ElasticConfig
from .client import ElasticClient, map_mongo_to_elasticsearch, execute_elastic_with_logging


# ---------------------------------------------------------------------------
# ElasticIndexer class
# ---------------------------------------------------------------------------

class ElasticIndexer(ElasticClient):
    """Quản lý việc index / update law_documents lên Elasticsearch."""

    # ------------------------------------------------------------------
    # Index một document
    # ------------------------------------------------------------------

    def index_document(self, document: Dict[str, Any]) -> bool:
        """
        Index một document vào Elasticsearch.

        Args:
            document: Document từ MongoDB.

        Returns:
            True nếu thành công, False nếu thất bại.
        """
        doc_id = document.get("doc_id", "unknown")
        
        def do_op():
            es_doc = map_mongo_to_elasticsearch(document)
            self.client.index(
                index=self.index,
                id=es_doc["doc_id"],
                body=es_doc,
            )
            return True
            
        try:
            return execute_elastic_with_logging(
                do_op,
                action="index_document",
                operation="index_document",
                meta={"index": self.index, "doc_id": doc_id}
            )
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Index nhiều document (bulk)
    # ------------------------------------------------------------------

    def index_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Bulk index danh sách document vào Elasticsearch.

        Args:
            documents: Danh sách document từ MongoDB.

        Returns:
            Dict với success_count và error_count.
        """
        actions = []
        error_count = 0

        for doc in documents:
            try:
                es_doc = map_mongo_to_elasticsearch(doc)
                actions.append({
                    "_index": self.index,
                    "_id": es_doc["doc_id"],
                    "_source": es_doc,
                })
            except Exception as e:
                logger.error("mapping_skipped", action="index_documents",
                    **{"error.code": "MAP", "error.message": str(e)},
                    doc_id=doc.get("doc_id", "unknown"),
                )
                error_count += 1

        if not actions:
            return {"success_count": 0, "error_count": error_count}

        def do_bulk():
            success, failed = helpers.bulk(self.client, actions, raise_on_error=False, stats_only=False)
            return success, failed

        try:
            success, failed = execute_elastic_with_logging(
                do_bulk,
                action="index_documents",
                operation="bulk_index_documents",
                meta={"index": self.index, "batch_size": len(actions)}
            )
            errs = error_count + len(failed)
            if failed:
                logger.error("bulk_partial_failure", action="index_documents", failed_count=len(failed), **{"error.code": "ES"})
            return {"success_count": success, "error_count": errs}
        except Exception:
            return {"success_count": 0, "error_count": len(actions) + error_count}

    # ------------------------------------------------------------------
    # Update toàn bộ document (upsert)
    # ------------------------------------------------------------------

    def update_document(self, document: Dict[str, Any]) -> bool:
        """
        Update (hoặc upsert) toàn bộ document trong Elasticsearch.

        Args:
            document: Document từ MongoDB.

        Returns:
            True nếu thành công, False nếu thất bại.
        """
        doc_id = document.get("doc_id", "unknown")
        
        def do_op():
            es_doc = map_mongo_to_elasticsearch(document)
            self.client.update(
                index=self.index,
                id=es_doc["doc_id"],
                body={"doc": es_doc, "doc_as_upsert": True},
            )
            return True
            
        try:
            return execute_elastic_with_logging(
                do_op,
                action="update_document",
                operation="update_document",
                meta={"index": self.index, "doc_id": doc_id}
            )
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Update một số trường cụ thể
    # ------------------------------------------------------------------

    def update_document_fields(self, doc_id: str, fields: Dict[str, Any]) -> bool:
        """
        Update một số trường cụ thể của document, giữ nguyên các trường còn lại.

        Args:
            doc_id: ID của document cần update.
            fields: Dict chứa các trường cần update.

        Returns:
            True nếu thành công, False nếu thất bại.
        """
        def do_op():
            self.client.update(
                index=self.index,
                id=doc_id,
                body={"doc": fields},
            )
            return True
            
        try:
            return execute_elastic_with_logging(
                do_op,
                action="update_document_fields",
                operation="update_document_fields",
                meta={"index": self.index, "doc_id": doc_id, "fields_updated": list(fields.keys())}
            )
        except Exception:
            return False