from core.common.mongo.client import get_mongo_client
import os
import sys
import time
from typing import List, Dict, Any
import structlog
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor
import threading
import uuid
import nltk
from nltk.tokenize import sent_tokenize

for pkg in ["punkt", "punkt_tab"]:
    try:
        nltk.data.find(f"tokenizers/{pkg}")
    except LookupError:
        nltk.download(pkg)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.common.embedding import EMBEDDING_MODELS
from core.common.qdrant import QdrantStorageManager
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

MODEL = MigrateConfig.MIGRATE_EMBEDDING
VERSION = MigrateConfig.MIGRATE_EMBEDDING_VERSION
EMBEDDING_SIZE = MigrateConfig.MIGRATE_EMBEDDING_EMBEDDING_SIZE
KNOWLEDGE_NAME = f"NB_V03_Doc_Content_Sentence_Level_{MODEL}_{VERSION}".format(MODEL=MODEL, VERSION=VERSION)
STATUS_FIELD = f"is_in_NB_V03_Doc_Content_Sentence_Level_{MODEL}_{VERSION}".format(MODEL=MODEL, VERSION=VERSION)

MAX_WORKERS = int(MigrateConfig.MIGRATE_EMBEDDING_MAX_WORKERS)
BATCH_SIZE = 1000

EMBEDDING_MODEL = EMBEDDING_MODELS[MODEL]
QDRANT = QdrantStorageManager()
client = get_mongo_client()
core_db = client[MigrateConfig.MIGRATE_CORE_DB]
law_documents_collection = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]


def setup_qdrant_collection() -> None:
    """Set up Qdrant collection if it does not exist."""
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
    document_id: str,
    segment_id: str=None,
    segment_index: int=None,
    chunk_id: str=None,
    chunk_index: int=None    
) -> None:
    """Add a vector to Qdrant."""
    try:
        QDRANT.add_vector(
            collection_name=knowledge_name,
            document_id=document_id,
            segment_id=segment_id,
            segment_index=segment_index,
            chunk_id=segment_id,
            chunk_index=chunk_index,
            text=payload['text'],
            vector=payload['vector'],
            hash_text=None,
            metadata=None,
            model_type=model_type
        )
        logger.debug(action="add_vector_to_qdrant", event="vector_added", document_id=document_id)
    except Exception as e:
        logger.error(action="add_vector_to_qdrant", event="add_vector_failed", **{"error.code": "DB", "error.message": str(e)}, document_id=document_id, exc_info=True)
        raise

def embed_doc_content_sentences(
    knowledge_name: str,
    document_id: str,
    doc_content: str
) -> None:
    """Embed and add sentences from doc_content to Qdrant vector database."""
    try:
        if not doc_content.strip():
            logger.debug(action="embed_doc_content_sentences", event="empty_content", document_id=document_id)
            return
        
        sentences = sent_tokenize(doc_content.strip())
        if not sentences:
            logger.debug(action="embed_doc_content_sentences", event="no_sentences_found", document_id=document_id)
            return
        
        segments_id = []
        segments_index = []
        segments_text = []
        for idx, sentence in enumerate(sentences):
            if sentence.strip() and len(sentence.strip()) > 6:
                segments_id.append(str(uuid.uuid4()))
                segments_index.append(idx)
                segments_text.append(sentence)
        if not segments_text:
            logger.debug(action="embed_doc_content_sentences", event="no_valid_sentences", document_id=document_id)
            return
        
        for idx in range(len(segments_text)):
            payloads = EMBEDDING_MODEL.embed_segments_batch(
                segments_id=[segments_id[idx]],
                segments_index=[segments_index[idx]],
                segments_text=[segments_text[idx]]
            )

            for payload in payloads:
                add_vector_to_qdrant(
                    payload=payload,
                    knowledge_name=knowledge_name,
                    model_type=MODEL,
                    document_id=document_id,
                    segment_id=payload['segment_id'],
                    segment_index=payload['segment_index'],
                    chunk_id=payload['segment_id'],
                    chunk_index=payload['segment_index']
                )
    except Exception as e:
        logger.error(action="embed_doc_content_sentences", event="sentence_embedding_failed", **{"error.code": "EXT", "error.message": str(e)}, document_id=document_id, exc_info=True)
        raise


def process_document(
    document: Dict[str, Any],
    processed_count_lock: threading.Lock,
    error_count_lock: threading.Lock
) -> None:
    """Process a single document and add its sentences to Qdrant."""
    try:
        document_id = document['doc_id']
        if 'embedding' in document and document['embedding'].get(STATUS_FIELD, False):
            logger.debug(action="process_document", event="document_already_embedded", document_id=document_id)
            return

        doc_content = document.get('doc_content', '').strip()
        if not doc_content:
            logger.debug(action="process_document", event="no_content_found", document_id=document_id)
            return
        embed_doc_content_sentences(
            knowledge_name=KNOWLEDGE_NAME,
            document_id=document_id,
            doc_content=doc_content
        )
        law_documents_collection.update_one(
            {'_id': document['_id']},
            {'$set': {f'embedding.{STATUS_FIELD}': "SUCCESS"}}
        )

        with processed_count_lock:
            global processed_count
            processed_count += 1
        logger.info(action="process_document", event="document_embedded", document_id=document_id)
    except Exception as e:
        with error_count_lock:
            global error_count
            error_count += 1
        logger.error(action="process_document", event="document_processing_failed", **{"error.code": "EXT", "error.message": str(e)}, document_id=document.get('doc_id', 'unknown'), exc_info=True)
        law_documents_collection.update_one(
            {'_id': document['_id']},
            {'$set': {f'error_{KNOWLEDGE_NAME}': str(e)}}
        )


def process_document_batch(
    documents: List[Dict[str, Any]],
    processed_count_lock: threading.Lock,
    error_count_lock: threading.Lock
) -> None:
    """Process a batch of documents concurrently using ThreadPoolExecutor."""
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(
                process_document,
                document,
                processed_count_lock,
                error_count_lock
            )
            for document in documents
        ]
        for future in futures:
            future.result()


def migrate_embedded_sentences() -> None:
    """Migrate and embed sentences from law_documents to Qdrant vector database."""        
    setup_qdrant_collection()
    
    global processed_count, error_count
    processed_count = 0
    error_count = 0
    processed_count_lock = threading.Lock()
    error_count_lock = threading.Lock()

    try:
        # Only fetch doc_id, doc_content, migrate, and _id fields
        cursor: Cursor = law_documents_collection.find(
            {'embedding.'+STATUS_FIELD: {'$eq': None}},
            {'doc_id': 1, 'doc_content': 1, 'embedding': 1, '_id': 1},
            no_cursor_timeout=True
        ).batch_size(BATCH_SIZE)
        documents_batch = []
        for document in cursor:
            documents_batch.append(document)
            if len(documents_batch) >= BATCH_SIZE:
                process_document_batch(documents_batch, processed_count_lock, error_count_lock)
                documents_batch = []

        if documents_batch:
            process_document_batch(documents_batch, processed_count_lock, error_count_lock)
        logger.info(action="migrate_embedded_sentences", event="migration_completed", processed=processed_count, errors=error_count)
    except Exception as e:
        logger.error(action="migrate_embedded_sentences", event="migration_failed", **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
        raise
    finally:
        cursor.close()
        client.close()


def main() -> None:
    """Run the document content sentences embedding migration process."""
    logger.info(action="main", event="content_sentence_embedding_migration_started")
    start_time = time.time()
    try:
        migrate_embedded_sentences()
        logger.info(action="main", event="content_sentence_embedding_migration_completed", duration=time.time() - start_time)
    except Exception as e:
        logger.error(action="main", event="content_sentence_embedding_migration_failed", **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
        raise


if __name__ == "__main__":
    main()