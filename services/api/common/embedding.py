import os
import sys
from typing import List, Dict, Any, Optional
from flask import jsonify
from flask_restful import Resource, reqparse
import structlog

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from constants import EmbeddingConfig
from core.common.embedding import EMBEDDING_MODELS
from core.common.textspliter import FixedRecursiveCharacterTextSplitter
from services.api.utils.response import make_response
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



class CreateChunksAPI(Resource):
    """API for splitting text into chunks."""

    def post(self) -> Dict[str, List[str]]:
        parser = reqparse.RequestParser()
        parser.add_argument("text", type=str, required=True, nullable=False, location="json")
        
        args = parser.parse_args()
        text = args["text"].replace("\n \n", "\n\n")
        
        try:
            chunks = TextSplitter.split_text(text)
            return make_response(data=chunks, code=0, message="Success"), 200
        except Exception as e:
            logger.error("create_chunks_failed", action="post", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return make_response(data=None, code=2000, message=str(e)), 500


class GetModelNameAPI(Resource):
    """API to retrieve names of supported embedding models."""

    def get(self) -> List[str]:
        try:
            return make_response(data=list(EMBEDDING_MODELS.keys()), code=0, message="Success"), 200
        except Exception as e:
            logger.error("get_model_names_failed", action="get", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return make_response(data=None, code=2000, message=str(e)), 500


class CreateEmbeddingsAPI(Resource):
    """API for creating embeddings from text chunks."""

    def post(self) -> tuple[Dict[str, Any], int]:
        parser = reqparse.RequestParser()
        parser.add_argument("chunks", type=list, required=True, nullable=False, location="json")
        parser.add_argument("model_type", type=str, required=False, default=EmbeddingConfig.DEFAULT_MODEL_EMBEDDING, location="json")
        
        args = parser.parse_args()
        chunks: List[str] = args["chunks"]
        model_type: str = args["model_type"]
        model = EMBEDDING_MODELS.get(model_type)

        if not model:
            return make_response(data=None, code=2001, message=f"Model '{model_type}' not found"), 400

        try:
            # Split chunks and track boundaries
            all_splitted_chunks = []
            start_idx = 0

            for chunk in chunks:
                split_chunks = TextSplitter.split_text(chunk)
                all_splitted_chunks.extend(split_chunks)
                start_idx += len(split_chunks)
            
            # Generate embeddings in batch
            all_embeddings = model.embed_chunks(all_splitted_chunks)
            logger.debug("create_embeddings_batch_success", action="post", count=len(all_embeddings))

            # Reorganize embeddings by original chunks
            embeddings = all_embeddings.tolist()

            return make_response(data=embeddings, code=0, message="Embeddings created successfully"), 200
        except Exception as e:
            logger.error("create_embeddings_failed", action="post", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
            return make_response(data=None, code=2002, message=str(e)), 500


# Register API resources
api.add_resource(CreateChunksAPI, "/embedding/create_chunks")
api.add_resource(GetModelNameAPI, "/embedding/get_models")
api.add_resource(CreateEmbeddingsAPI, "/embedding/create_embeddings")
