from core.common.mongo.client import get_mongo_client
import os
import sys
import time
from typing import Tuple, List, Dict, Any
import structlog
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.cursor import Cursor
from concurrent.futures import ThreadPoolExecutor
import threading

# Set up project root and import paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.append(PROJECT_ROOT)

from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.common.embedding import EMBEDDING_MODELS
from core.common.qdrant import QdrantStorageManager
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

# Constants
MODEL = MigrateConfig.MIGRATE_EMBEDDING
VERSION = MigrateConfig.MIGRATE_EMBEDDING_VERSION
EMBEDDING_SIZE = MigrateConfig.MIGRATE_EMBEDDING_EMBEDDING_SIZE
KNOWLEDGE_NAME = f"NB_V03_Sentences_Level_{MODEL}_{VERSION}_Name".format(MODEL=MODEL, VERSION=VERSION)
STATUS_FIELD = f"is_in_NB_V03_Sentences_Level_{MODEL}_{VERSION}_Name".format(MODEL=MODEL, VERSION=VERSION)
MAX_WORKERS = int(MigrateConfig.MIGRATE_EMBEDDING_MAX_WORKERS)
BATCH_SIZE = 1000  # Process articles in batches to manage memory
logger.debug(action="main", event="max_workers_type", type=str(type(MAX_WORKERS)))


# Initialize embedding model and Qdrant
EMBEDDING_MODEL = EMBEDDING_MODELS[MODEL]
QDRANT = QdrantStorageManager()

client = get_mongo_client()
core_db = client[MigrateConfig.MIGRATE_CORE_DB]
document_collection = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]                
articles_collection = core_db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
articles_class_collection = core_db[MongoDBCollectionConfig.LAW_ARTICLE_CLASS_COLLECTION_NAME]

def setup_qdrant_collection() -> None:
    """Set up Qdrant collection if it does not exist.

    Raises:
        Exception: If checking or creating the collection fails.
    """
    try:
        if QDRANT.check_qdrant_collection_exists(collection_name=KNOWLEDGE_NAME):
            logger.info(action="setup_qdrant_collection", event="collection_exists", collection=KNOWLEDGE_NAME)
            return
        QDRANT.create_collection(collection_name=KNOWLEDGE_NAME, embedding_size=EMBEDDING_SIZE)
        logger.info(action="setup_qdrant_collection", event="collection_created", collection=KNOWLEDGE_NAME)
    except Exception as e:
        logger.error(action="setup_qdrant_collection", event="collection_setup_failed", **{"error.code": "DB", "error.message": str(e)}, collection=KNOWLEDGE_NAME, exc_info=True)
        raise

def add_vector_to_qdrant(
    payload: Dict[str, Any],
    knowledge_name: str,
    model_type: str,
    document_id: str
) -> None:
    """Add a vector to Qdrant.

    Args:
        payload: Payload containing segment data and vector.
        knowledge_name: Name of the Qdrant collection.
        model_type: Type of embedding model.
        document_id: ID of the document.

    Raises:
        Exception: If adding the vector fails.
    """
    try:
        segment_id = payload['segment_id']
        QDRANT.add_vector(
            collection_name=knowledge_name,
            document_id=document_id,
            segment_id=segment_id,
            segment_index=payload['segment_index'],
            chunk_id=payload['chunk_id'],
            chunk_index=payload['chunk_index'],
            text=payload['text'],
            vector=payload['vector'],
            hash_text=None,
            metadata=None,
            model_type=model_type
        )
        logger.debug(action="add_vector_to_qdrant", event="vector_added", segment_id=segment_id)
    except Exception as e:
        logger.error(action="add_vector_to_qdrant", event="add_vector_failed", **{"error.code": "DB", "error.message": str(e)}, segment_id=payload.get('segment_id', 'unknown'), exc_info=True)
        raise

def add_segment_to_vector_db(
    knowledge_name: str,
    document_id: str,
    segments_id: List[str],
    segments_index: List[int],
    segments_text: List[str]
) -> None:
    """Embed and add segments to Qdrant vector database sequentially.

    Args:
        knowledge_name: Name of the Qdrant collection.
        document_id: ID of the document.
        segments_id: List of segment IDs.
        segments_index: List of segment indices.
        segments_text: List of segment texts.

    Raises:
        Exception: If embedding or adding vectors fails.
    """
    try:
        payloads = EMBEDDING_MODEL.embed_segments_batch(segments_id, segments_index, segments_text)
        for payload in payloads:
            add_vector_to_qdrant(payload, knowledge_name, MODEL, document_id)
    except Exception as e:
        logger.error(action="add_segment_to_vector_db", event="add_segment_failed", **{"error.code": "EXT", "error.message": str(e)}, document_id=document_id, exc_info=True)
        raise

def process_article(
    article: Dict[str, Any],
    articles_collection: Any,
    processed_count_lock: threading.Lock,
    error_count_lock: threading.Lock
) -> None:
    """Process a single article and add its segments to Qdrant.

    Args:
        article: The article document to process.
        articles_collection: MongoDB collection for articles.
        processed_count_lock: Lock for thread-safe processed count updates.
        error_count_lock: Lock for thread-safe error count updates.
    """
    try:
        article_id = article['article_id']
        if 'embedding' in article and article['embedding'].get(STATUS_FIELD, False):
            logger.debug(action="process_article", event="article_already_embedded", article_id=article_id)
            return

        document_id = article['doc_id']
        article_title = article.get('article_title', '').strip()
        article_content = article.get('article_content', '').strip()

        content = f"{article_title}\n{article_content}".strip().replace('\n\n', '\n')
        sentences = content.split('\n')

        segments_id = []
        segments_index = []
        segments_text = []
        for idx, sentence in enumerate(sentences):
            segments_id.append(article_id)
            segments_index.append(idx)
            segments_text.append(sentence)

        add_segment_to_vector_db(
            knowledge_name=KNOWLEDGE_NAME,
            document_id=document_id,
            segments_id=segments_id,
            segments_index=segments_index,
            segments_text=segments_text
        )

        articles_collection.update_one(
            {'_id': article['_id']},
            {
                '$set': {f'embedding.{STATUS_FIELD}': "SUCCESS"},
                '$unset': {f'error_{KNOWLEDGE_NAME}': ""}
            }
        )

        with processed_count_lock:
            global processed_count
            processed_count += 1
        logger.info(action="process_article", event="article_embedded", article_id=article_id)

    except Exception as e:
        with error_count_lock:
            global error_count
            error_count += 1
        logger.error(action="process_article", event="article_embedding_failed", **{"error.code": "EXT", "error.message": str(e)}, article_id=article.get('article_id', 'unknown'), exc_info=True)
        articles_collection.update_one(
            {'_id': article['_id']},
            {'$set': {f'error_{KNOWLEDGE_NAME}': str(e)}}
        )

def process_article_batch(
    articles: List[Dict[str, Any]],
    articles_collection: Any,
    processed_count_lock: threading.Lock,
    error_count_lock: threading.Lock
) -> None:
    """Process a batch of articles concurrently using ThreadPoolExecutor.

    Args:
        articles: List of article documents to process.
        articles_collection: MongoDB collection for articles.
        processed_count_lock: Lock for thread-safe processed count updates.
        error_count_lock: Lock for thread-safe error count updates.
    """
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(
                process_article,
                article,
                articles_collection,
                processed_count_lock,
                error_count_lock
            )
            for article in articles
        ]
        for future in futures:
            future.result()  # Ensure exceptions are raised

def migrate_embedded_segments() -> None:
    """Migrate and embed segments from law_articles to Qdrant vector database."""
    setup_qdrant_collection()
    global processed_count, error_count
    processed_count = 0
    error_count = 0
    processed_count_lock = threading.Lock()
    error_count_lock = threading.Lock()

    try:
        cursor: Cursor = articles_collection.find({}, no_cursor_timeout=True).batch_size(BATCH_SIZE)
        articles_batch = []
        for article in cursor:
            articles_batch.append(article)
            if len(articles_batch) >= BATCH_SIZE:
                process_article_batch(articles_batch, articles_collection, processed_count_lock, error_count_lock)
                articles_batch = []

        # Process remaining articles
        if articles_batch:
            process_article_batch(articles_batch, articles_collection, processed_count_lock, error_count_lock)
        logger.info(action="migrate_embedded_segments", event="migration_completed", processed=processed_count, errors=error_count)
    except Exception as e:
        logger.error(action="migrate_embedded_segments", event="migration_failed", **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
        raise
    finally:
        cursor.close()
        client.close()

def main() -> None:
    """Run the article segment embedding migration process."""
    logger.info(action="main", event="sentence_embedding_migration_started")
    start_time = time.time()
    try:
        migrate_embedded_segments()
        logger.info(action="main", event="sentence_embedding_migration_completed", duration=time.time() - start_time)
    except Exception as e:
        logger.error(action="main", event="sentence_embedding_migration_failed", **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
        raise

if __name__ == "__main__":
    main()