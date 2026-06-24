import os
import sys
from typing import List, Dict, Any, Optional
from flask_restful import Resource, reqparse
import structlog

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from constants import QdrantConfig, EmbeddingConfig, MigrateConfig
from core.common.embedding import EMBEDDING_MODELS
from core.common.qdrant import QdrantStorageManager
from core.common.textspliter import FixedRecursiveCharacterTextSplitter
from services.api import api
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

# Initialize global components
TextSplitter = FixedRecursiveCharacterTextSplitter(
    fixed_separator="\n" * 8,
    chunk_size=EmbeddingConfig.MAX_CHUNK_SIZE,
    separators=["\n\n", "\n", " ", ""]
)
QDRANT = QdrantStorageManager(host=QdrantConfig.HOST, port=QdrantConfig.PORT)


class AddSegmentsAPI(Resource):
    """API for adding document segments to vector storage."""

    def post(self) -> tuple[Dict[str, Any], int]:
        parser = reqparse.RequestParser()
        parser.add_argument("knowledge_name", type=str, required=True, location="json")
        parser.add_argument("document_id", type=str, required=True, location="json")
        parser.add_argument("segments_id", type=list, required=True, location="json")
        parser.add_argument("segments_index", type=list, required=True, location="json")
        parser.add_argument("segments_text", type=list, required=True, location="json")
        parser.add_argument("model_type", type=str, required=False, default=EmbeddingConfig.DEFAULT_MODEL_EMBEDDING, location="json")
        
        args = parser.parse_args()
        knowledge_name: str = args["knowledge_name"]
        document_id: str = args["document_id"]
        model_type: str = args["model_type"]
        model = EMBEDDING_MODELS.get(model_type)

        if not model:
            return {"status": False, "message": f"Model '{model_type}' not found"}, 400

        try:
            # Generate embeddings in batch
            payloads = model.embed_segments_batch(
                args["segments_id"],
                args["segments_index"],
                args["segments_text"]
            )

            # Add vectors to storage
            success_count = 0
            for payload in payloads:
                try:
                    QDRANT.add_vector(
                        collection_name=knowledge_name,
                        document_id=document_id,
                        segment_id=payload["segment_id"],
                        segment_index=payload["segment_index"],
                        chunk_id=payload["chunk_id"],
                        chunk_index=payload["chunk_index"],
                        text=payload["text"],
                        vector=payload["vector"],
                        model_type=model_type
                    )
                    success_count += 1
                except Exception as e:
                    logger.error("add_segment_vector_failed", action="post", **{"error.code": "EXT", "error.message": str(e)}, segment_id=payload["segment_id"], exc_info=True)

            return {
                "status": True,
                "success_count": success_count,
                "total_count": len(payloads),
                "message": f"Added {success_count}/{len(payloads)} segments successfully"
            }, 200
        except Exception as e:
            logger.error("add_segments_embed_failed", action="post", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return {"status": False, "message": f"Embedding generation failed: {str(e)}"}, 400


class SearchSegmentsAPI(Resource):
    """API for searching similar segments in vector storage."""

    def post(self) -> tuple[Dict[str, Any], int]:
        parser = reqparse.RequestParser()
        parser.add_argument("knowledge_name", type=str, required=True, default=EmbeddingConfig.DEFAULT_COLLECTION, location="json")
        parser.add_argument("segments_text", type=list, required=True, location="json")
        parser.add_argument("document_codes", type=list, required=False, default=None, location="json")
        parser.add_argument("model_type", type=str, required=False, default=EmbeddingConfig.DEFAULT_MODEL_EMBEDDING, location="json")
        parser.add_argument("top_k", type=int, required=False, default=EmbeddingConfig.TOP_K, location="json")
        parser.add_argument("score_threshold", type=float, required=False, default=EmbeddingConfig.THRESHOLD, location="json")
        
        args = parser.parse_args()
        knowledge_name: str = args["knowledge_name"]
        segments_text: List[str] = args["segments_text"]
        document_codes: Optional[List[str]] = args["document_codes"]
        model_type: str = args["model_type"]
        top_k: Optional[int] = args["top_k"]
        score_threshold: Optional[float] = args["score_threshold"]
        logger.debug("search_segments_params", action="post", model=model_type, top_k=top_k, score_threshold=score_threshold)

        model = EMBEDDING_MODELS.get(model_type)
        if not model:
            return {"status": False, "message": f"Model '{model_type}' not found"}, 400

        try:
            # Generate embeddings for segments
            payloads = model.embed_segments(segments_text)
            logger.debug("search_segments_embed_success", action="post", count=len(payloads))

            # Search for similar segments
            for payload in payloads:
                result = QDRANT.search_vector(
                    collection_name=knowledge_name,
                    query_vector=payload["vector"],
                    top_k=top_k,
                    document_codes=document_codes,
                    score_threshold=score_threshold
                )
                payload["vector"] = None  # Reduce payload size
                payload["search"] = result

            return {"status": True, "payloads": payloads, "message": "Search completed successfully"}, 200
        except Exception as e:
            logger.error("search_segments_failed", action="post", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return {"status": False, "message": f"Search failed: {str(e)}"}, 400


class DeleteDocumentAPI(Resource):
    """API for deleting document from vector storage."""

    def post(self) -> tuple[Dict[str, Any], int]:
        parser = reqparse.RequestParser()
        parser.add_argument("knowledge_name", type=str, required=False, default=EmbeddingConfig.DEFAULT_COLLECTION, location="json")
        parser.add_argument("document_id", type=str, required=True, location="json")
        args = parser.parse_args()

        knowledge_name: str = args["knowledge_name"]
        document_id: str = args["document_id"]

        try:
            QDRANT.delete_vector(collection_name=knowledge_name, document_id=document_id)
            return {"status": True, "message": f"Document '{document_id}' deleted successfully"}, 200
        except Exception as e:
            logger.error("delete_document_vector_failed", action="post", **{"error.code": "EXT", "error.message": str(e)}, document_id=document_id, exc_info=True)
            return {"status": False, "message": f"Document deletion failed: {str(e)}"}, 400


class DeleteSegmentAPI(Resource):
    """API for deleting segment from vector storage."""

    def post(self) -> tuple[Dict[str, Any], int]:
        parser = reqparse.RequestParser()
        parser.add_argument("knowledge_name", type=str, required=False, default=EmbeddingConfig.DEFAULT_COLLECTION, location="json")
        parser.add_argument("segment_id", type=str, required=True, location="json")
        args = parser.parse_args()

        knowledge_name: str = args["knowledge_name"]
        segment_id: str = args["segment_id"]

        try:
            QDRANT.delete_vector(collection_name=knowledge_name, segment_id=segment_id)
            return {"status": True, "message": f"Segment '{segment_id}' deleted successfully"}, 200
        except Exception as e:
            logger.error("delete_segment_vector_failed", action="post", **{"error.code": "EXT", "error.message": str(e)}, segment_id=segment_id, exc_info=True)
            return {"status": False, "message": f"Segment deletion failed: {str(e)}"}, 400
        

class CreateKnowledgeAPI(Resource):
    """API for create knowledge vector storage."""

    def post(self) -> tuple[Dict[str, Any], int]:
        parser = reqparse.RequestParser()
        parser.add_argument("knowledge_name", type=str, required=False, default=None, location="json")
        parser.add_argument("model_type", type=str, required=False, default=EmbeddingConfig.DEFAULT_MODEL_EMBEDDING, location="json")        
        args = parser.parse_args()

        knowledge_name: str = args["knowledge_name"]
        model_type: str = args["model_type"]
        
        try:
            embedding_size = EMBEDDING_MODELS[model_type].embedding_size
            QDRANT.create_collection(collection_name=knowledge_name, embedding_size=embedding_size)
            return {"status": True, "message": f"Knowledge '{knowledge_name}' Created successfully"}, 200
        except Exception as e:
            logger.error("create_knowledge_collection_failed", action="post", **{"error.code": "EXT", "error.message": str(e)}, knowledge_name=knowledge_name, exc_info=True)
            return {"status": False, "message": f"Knowledge creation failed: {str(e)}"}, 400


class DeleteKnowledgeAPI(Resource):
    """API for create knowledge vector storage."""

    def post(self) -> tuple[Dict[str, Any], int]:
        parser = reqparse.RequestParser()
        parser.add_argument("knowledge_name", type=str, required=False, default=None, location="json")
        args = parser.parse_args()

        knowledge_name: str = args["knowledge_name"]
        try:
            QDRANT.delete_collecion(collection_name=knowledge_name)
            return {"status": True, "message": f"Knowledge '{knowledge_name}' deleted successfully"}, 200
        except Exception as e:
            logger.error("delete_knowledge_collection_failed", action="post", **{"error.code": "EXT", "error.message": str(e)}, knowledge_name=knowledge_name, exc_info=True)
            return {"status": False, "message": f"Knowledge deletion failed: {str(e)}"}, 400


class SemanticSearchKnowledgeAPI(Resource):
    """API for semantic search knowledge."""
    def post(self) -> tuple[Dict[str, Any], int]:
        parser = reqparse.RequestParser()
        parser.add_argument("knowledge_name", type=str, required=False, default=MigrateConfig.MIGRATE_EMBEDDING_KNOWLEDGE_SENTENCE, location="json")
        parser.add_argument("query", type=str, required=True, location="json")
        parser.add_argument("model_type", type=str, required=False, default=MigrateConfig.MIGRATE_EMBEDDING_MODEL_SENTENCE, location="json")
        parser.add_argument("top_k", type=int, required=False, default=EmbeddingConfig.TOP_K, location="json")
        parser.add_argument("score_threshold", type=float, required=False, default=EmbeddingConfig.THRESHOLD, location="json")
        args = parser.parse_args()

        knowledge_name: str = args["knowledge_name"]
        query: str = args["query"]
        model_type: str = args["model_type"]
        top_k: Optional[int] = args["top_k"]
        score_threshold: Optional[float] = args["score_threshold"]
        logger.debug("semantic_search_params", action="post", model=model_type, top_k=top_k, score_threshold=score_threshold)

        model = EMBEDDING_MODELS.get(model_type)
        if not model:
            return {"status": False, "message": f"Model '{model_type}' not found"}, 400

        try:
            # Generate embeddings for query
            query_embedding = model.embed_segments([query])[0]["vector"]
            logger.debug("semantic_search_embed_success", action="post")

            # Search for similar segments
            result = QDRANT.search_vector(
                collection_name=knowledge_name,
                query_vector=query_embedding,
                top_k=top_k,
                score_threshold=score_threshold
            )            
            logger.debug("semantic_search_result", action="post", count=len(result))

            return {"status": True, "result": result, "message": "Search completed successfully"}, 200
        except Exception as e:
            logger.error("semantic_search_failed", action="post", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return {"status": False, "message": f"Search failed: {str(e)}"}, 400



# Register API resources
api.add_resource(CreateKnowledgeAPI, "/knowledge/create_knowledge")
api.add_resource(DeleteKnowledgeAPI, "/knowledge/delete_knowledge")
api.add_resource(AddSegmentsAPI, "/knowledge/add_segments")
api.add_resource(SearchSegmentsAPI, "/knowledge/search_segments")
api.add_resource(DeleteDocumentAPI, "/knowledge/delete_document")
api.add_resource(DeleteSegmentAPI, "/knowledge/delete_segment")
api.add_resource(SemanticSearchKnowledgeAPI, "/knowledge/semantic_search")
# api.add_resource(SemanticSearchKnowledgeWithRerankerAPI, "/knowledge/semantic_search_with_reranker")