import uuid
import sys
import os
from qdrant_client import QdrantClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from qdrant_client.models import Distance, VectorParams, Filter, FieldCondition, PointStruct, MatchValue, FilterSelector, MatchAny
from core.common.external_logging import execute_external_with_logging

def classify_qdrant_error(e):
    e_str = str(e).lower()
    e_type = type(e).__name__.lower()
    if "timeout" in e_type or "timeout" in e_str:
        return "timeout"
    if "connection" in e_type or "connection error" in e_str:
        return "network"
    if "unavailable" in e_str or "503" in e_str or "502" in e_str:
        return "service_unavailable"
    return "unknown"


from constants import QdrantConfig

class QdrantStorageManager():
    def __init__(self,
                 host=QdrantConfig.HOST, 
                 port=QdrantConfig.PORT,
                 api_key=QdrantConfig.API_KEY):
        self.client = QdrantClient(host=host, port=port, api_key=api_key, https=False, timeout=10)        
        
    def get_type(self) -> str:
        return 'qdrant'
    
    def to_index_struct(self) -> dict:
        return {
            "type": self.get_type(),
            "vector_store": {"class_prefix": self._collection_name}
        }

    def create_collection(self, 
                          collection_name,
                          embedding_size=768):
        self.client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=embedding_size, 
                                        distance=Distance.COSINE)
        )

    def delete_collecion(self, 
                        collection_name):
        self.client.delete_collection(collection_name=collection_name)

    def get_collections(self):
        collections = self.client.get_collections().collections
        result = []
        for collection in collections:
            result.append(collection.__dict__)
        return result

    def get_infor(self,
                 collection_name):
        __info = {}
        info = vars(self.client.get_collection(collection_name=collection_name))
        logger.debug("collection_info_retrieved", action="get_infor", **info)
        if info:
            __info['vectors_count'] = info['vectors_count']
            __info['points_count'] = info['points_count']
            __info['indexed_vectors_count'] = info['indexed_vectors_count']
            __info['points_count'] = info['points_count']
            __info['segments_count'] = info['segments_count']

            vector_param = vars(vars(vars(info['config'])['params'])['vectors'])
            __info['vector_param'] = {
                'size' : vector_param['size'],
                'distance': vars(vector_param['distance'])['_value_']
            }
            return __info
        return {}
    
    def add_vector(self, 
                   collection_name,
                   document_id,
                   segment_id,
                   segment_index,
                   chunk_id,
                   chunk_index, 
                   text,
                   vector,
                   hash_text=None, 
                   metadata=None,
                   model_type=None):
        
        def do_upsert():
            return self.client.upsert(
                collection_name=collection_name,
                points=[PointStruct(
                            id=str(uuid.uuid4()),
                            payload={
                                "code": chunk_id,
                                "knowledge_id": collection_name, 
                                "document_id": document_id,
                                "segment_id": segment_id,
                                "segment_index": segment_index,
                                "chunk_index": chunk_index,
                                "hash": hash_text,
                                "text": text,
                                "metadata": metadata,
                                "model_type": model_type
                            },
                        vector=vector,
                    ),
                ],
            )
            
        stt = execute_external_with_logging(
            func=do_upsert,
            action="add_vector",
            service_name="qdrant",
            operation="upsert_vectors",
            error_classifier=classify_qdrant_error,
            meta={"collection_name": collection_name},
            error_code="DB"
        )
        return True
        
    def add_vectors_batch(self,
                      collection_name,
                      document_id,
                      segment_id,
                      vectors,
                      hash_text=None,
                      metadata=None,
                      model_type=None):

        def do_upsert():
            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    payload={
                        "code": v["chunk_id"],
                        "knowledge_id": collection_name,
                        "document_id": document_id,
                        "segment_id": segment_id,
                        "segment_index": v["segment_index"],
                        "chunk_index": v["chunk_index"],
                        "hash": hash_text,
                        "text": v["text"],
                        "metadata": metadata,
                        "model_type": model_type,
                    },
                    vector=v["vector"],
                )
                for v in vectors
            ]
            return self.client.upsert(
                collection_name=collection_name,
                points=points,
            )

        execute_external_with_logging(
            func=do_upsert,
            action="add_vectors_batch",
            service_name="qdrant",
            operation="upsert_vectors",
            error_classifier=classify_qdrant_error,
            meta={"collection_name": collection_name, "count": len(vectors)},
            error_code="DB",
        )
        return True
        
    def delete_vector(self, 
                      collection_name,
                      document_id=None,
                      segment_id=None,                   
                      chunk_id=None):        
        
        
        logger.debug("delete_vector_called", action="delete_vector", document_id=document_id)

        if document_id != None:
            self.client.delete(collection_name=collection_name, 
                               points_selector=FilterSelector(
                                   filter=Filter(
                                            must=[
                                                FieldCondition(
                                                    key="document_id",
                                                    match=MatchValue(value=document_id),
                                                ),
                                            ],
                                        )
                                    )
                                )
        elif segment_id != None:
            self.client.delete(collection_name=collection_name, 
                   points_selector=Filter(
                                        must=[  
                                            FieldCondition(
                                                key="segment_id", 
                                                match=MatchValue(value=segment_id)
                                            )
                                        ]
                                    )
                    )
        elif chunk_id != None:
            self.client.delete(collection_name=collection_name, 
                   points_selector=Filter(
                                        must=[  
                                            FieldCondition(
                                                key="chunk_id", 
                                                match=MatchValue(value=chunk_id)
                                            )
                                        ]
                                    )
                    )
            
        return True
    
        
    def search_vector(self, 
                      collection_name, 
                      query_vector,
                      score_threshold=0.1,
                      document_codes = None,
                      top_k=4,
                      metadata=None):
        
        query_filter = None
        
        if metadata is not None and document_codes is not None:
            logger.debug("search_case", action="search_vector", case=2)
            query_filter = Filter(
                must=[  
                    FieldCondition(key='document_id', match=MatchAny(any=document_codes)),
                    FieldCondition(key='metadata', match=MatchValue(value=metadata))
                ]
            )
        elif document_codes is not None:
            logger.debug("search_case", action="search_vector", case=3)
            query_filter = Filter(
                must=[  
                    FieldCondition(key='document_id', match=MatchAny(any=document_codes))
                ]
            )
        elif metadata is not None:
            logger.debug("search_case", action="search_vector", case=4)
            query_filter = Filter(
                must=[  
                    FieldCondition(key='metadata', match=MatchValue(value=metadata))
                ]
            )
        else:
            logger.debug("search_case", action="search_vector", case=1)

        def do_search():
            if query_filter:
                return self.client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=top_k,
                    with_payload=True,
                    with_vectors=True,
                    score_threshold=score_threshold,
                    query_filter=query_filter
                )
            else:
                return self.client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=top_k,
                    with_payload=True,
                    with_vectors=True,
                    score_threshold=score_threshold
                )

        score_point = execute_external_with_logging(
            func=do_search,
            action="search_vector",
            service_name="qdrant",
            operation="search_vectors",
            error_classifier=classify_qdrant_error,
            meta={"collection_name": collection_name},
            error_code="DB"
        )
                
        results = []
        for i in range(len(score_point)): 
            payload = score_point[i].payload            
            payload['score'] = score_point[i].score            
            results.append(payload)
        return results

    def check_qdrant_collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists in Qdrant."""
        try:
            self.client.get_collection(collection_name)
            logger.debug("collection_exists", action="check_qdrant_collection_exists", collection=collection_name)
            return True
        except Exception as e:
            logger.debug("collection_not_found", action="check_qdrant_collection_exists", collection=collection_name, )
            return False



if __name__ == "__main__":
    esm = QdrantStorageManager(host='127.0.0.1', port=6333)
    # esm.create_collection('test_collection')
    
    # import numpy as np
    # import uuid
    # vector =  np.random.rand(1, 768).tolist()[0]
    # esm.add_vector(collection_name='test_collection',
    #                 document_id=str(uuid.uuid4()),
    #                 segment_id=str(uuid.uuid4()),
    #                 segment_index=str(uuid.uuid4()),
    #                 chunk_id=str(uuid.uuid4()),
    #                 chunk_index=str(uuid.uuid4()), 
    #                 text='test_text',
    #                 vector=vector)
    
    
    esm.delete_vector('V03_Doc_Titles_vietnameseEmbedding_1_1', '1e50f341-08d9-4cc7-bf52-ef8363691ae2')
