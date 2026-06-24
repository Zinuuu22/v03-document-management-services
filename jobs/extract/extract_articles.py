import uuid
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import structlog
from pymongo import MongoClient, InsertOne, UpdateOne
from core.common.mongo.client import get_mongo_client


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)


from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.v03.content_extractor.extractor import extract_components
from core.common.elastic.search import ElasticSearcher
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

elastic_searcher = ElasticSearcher()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CREATED_BY  = "SYSTEM"
MAX_WORKERS = 10
BATCH_SIZE  = 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _duration(start: str, finish: str) -> float:
    fmt = "%Y-%m-%d %H:%M:%S"
    try:
        return (datetime.strptime(finish, fmt) - datetime.strptime(start, fmt)).total_seconds()
    except Exception:
        return 0.0


def _update_pipeline_state(pipeline_collection, doc_id: str, status: str, start_at: str):
    """Update trạng thái bước articles_extraction trong pipeline_document_state."""
    finish_at = _now()
    try:
        pipeline_collection.update_one(
            {"document_id": doc_id},
            {
                "$set": {
                    "articles_extraction": {
                        "status": status,
                        "start_at": start_at,
                        "finish_at": finish_at,
                        "duration_time": _duration(start_at, finish_at),
                    },
                    "last_modified_at": finish_at,
                    "last_modified_by": CREATED_BY,
                }
            },
        )
    except Exception as e:
        logger.error(
            action="_update_pipeline_state",
            event="pipeline_state_update_failed",
            **{"error.code": "MONGO", "error.message": str(e)},
            doc_id=doc_id,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Document processor
# ---------------------------------------------------------------------------

def process_document(doc: dict, collections: dict) -> tuple[str, bool]:
    """
    Xử lý một document: fetch content → extract articles/clauses → lưu vào MongoDB.

    Args:
        doc: Document từ law_documents collection.
        collections: Dict chứa các MongoDB collection cần dùng.

    Returns:
        Tuple (doc_id, success).
    """
    doc_id   = doc["doc_id"]
    doc_code = doc["doc_code"]
    start_at = _now()

    document_collection = collections["document"]
    article_collection  = collections["article"]
    clause_collection   = collections["clause"]
    pipeline_collection = collections["pipeline"]

    try:
        logger.info(action="process_document", event="process_document_started", doc_id=doc_id)

        # 1. Fetch content từ Elasticsearch
        content = elastic_searcher.get_document_content(doc_id)
        if not content:
            logger.warning(action="process_document", event="empty_content_warning", doc_id=doc_id)
            _mark_document(document_collection, doc["_id"], "FAIL")
            _update_pipeline_state(pipeline_collection, doc_id, "FAILED", start_at)
            return doc_id, False

        # 2. Extract articles và clauses
        articles = extract_components(content=content, document_code=doc_code)
        if not articles:
            logger.warning(action="process_document", event="no_articles_extracted_warning", doc_id=doc_id)
            _mark_document(document_collection, doc["_id"], "FAIL")
            _update_pipeline_state(pipeline_collection, doc_id, "FAILED", start_at)
            return doc_id, False

        # 3. Chuẩn bị bulk insert articles
        now = _now()
        article_docs = []
        clause_docs  = []

        for article in articles:
            article_docs.append(InsertOne({
                "article_id":          article["code"],
                "doc_id":              doc_id,
                "article_title":       article["article_title"],
                "article_content":     article["article_content"],
                "article_order_index": article["segment_index"],
                "created_date":        now,
                "created_by":          CREATED_BY,
                "last_modified":       now,
                "last_modified_by":    CREATED_BY,
                "part":                article.get("part"),
                "chapter":             article.get("chapter"),
                "section":             article.get("section"),
                "sub_section":         article.get("sub_section"),
            }))

            # 4. Chuẩn bị bulk insert clauses
            description = article["article_content"].split("1.")[0].strip()
            for idx, claud in enumerate(article.get("clauds", [])):
                clause_docs.append(InsertOne({
                    "claud_id":               str(uuid.uuid4()),
                    "article_id":             article["code"],
                    "claud_summary_content":  f"{article['article_title']}\n{description}\n{claud['claud']}".strip(),
                    "claud_content":          claud["claud"].strip(),
                    "claud_order_index":      idx,
                    "created_date":           now,
                    "created_by":             CREATED_BY,
                    "last_modified":          now,
                    "last_modified_by":       CREATED_BY,
                }))

        # 5. Bulk write
        if article_docs:
            article_collection.bulk_write(article_docs, ordered=False)
        if clause_docs:
            clause_collection.bulk_write(clause_docs, ordered=False)

        # 6. Đánh dấu thành công
        _mark_document(document_collection, doc["_id"], "SUCCESS")
        _update_pipeline_state(pipeline_collection, doc_id, "PROCESSED", start_at)
        logger.info(action="process_document", event="process_document_completed", doc_id=doc_id, articles=len(articles), clauses=len(clause_docs))
        return doc_id, True

    except Exception as e:
        logger.error(
            action="process_document",
            event="process_document_failed",
            **{"error.code": "DB", "error.message": str(e)},
            doc_id=doc_id,
            exc_info=True,
        )
        _mark_document(document_collection, doc["_id"], "FAIL")
        _update_pipeline_state(pipeline_collection, doc_id, "FAILED", start_at)
        return doc_id, False


def _mark_document(document_collection, mongo_id, status: str):
    """Cập nhật trạng thái is_extract_article trong law_documents."""
    try:
        document_collection.update_one(
            {"_id": mongo_id},
            {"$set": {"is_extract_article": status}},
        )
    except Exception as e:
        logger.error(action="_mark_document", event="mark_document_failed", **{"error.code": "MONGO", "error.message": str(e)}, exc_info=True)


# ---------------------------------------------------------------------------
# Main migrate
# ---------------------------------------------------------------------------
 
def migrate():
    """Migrate articles và clauses từ law_documents, dùng multithreading."""
 
    # --- Kết nối MongoDB ---
    mongo_client = get_mongo_client()
    core_db = mongo_client[MigrateConfig.MIGRATE_CORE_DB]
 
    collections = {
        "document": core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME],
        "article":  core_db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME],
        "clause":   core_db[MongoDBCollectionConfig.LAW_CLAUSE_COLLECTION_NAME],
        "pipeline": core_db[MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME],
    }
    logger.info(action="migrate", event="mongodb_connected")
 
    # Chỉ lấy document chưa xử lý thành công
    query = {"article_extraction": {"$nin": ["PROCESSED"]}}
    total = collections["pipeline"].count_documents(query)
    logger.info(action="migrate", event="migration_started", total_docs=total, max_workers=MAX_WORKERS)
 
    if total == 0:
        logger.info(action="migrate", event="migration_skipped")
        mongo_client.close()
        return
 
    # --- Thống kê thread-safe ---
    success_ids = []
    failed_ids  = []
    lock        = Lock()
 
    try:
        cursor = collections["document"].find(query, no_cursor_timeout=True)
 
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_document, doc, collections): doc["doc_id"]
                for doc in cursor
            }
 
            for future in as_completed(futures):
                doc_id = futures[future]
                try:
                    _, success = future.result()
                    with lock:
                        (success_ids if success else failed_ids).append(doc_id)
                except Exception as e:
                    logger.error(
                        action="migrate",
                        event="future_execution_failed",
                        **{"error.code": "THREAD", "error.message": str(e)},
                        doc_id=doc_id,
                        exc_info=True,
                    )
                    with lock:
                        failed_ids.append(doc_id)
 
    finally:
        cursor.close()
        mongo_client.close()
        logger.info(action="migrate", event="mongodb_disconnected")
 
    logger.info(
        action="migrate",
        event="migration_completed",
        total_docs=total,
        success_count=len(success_ids),
        error_count=len(failed_ids),
        failed_ids=failed_ids,
    )
 
 
if __name__ == "__main__":
    migrate()