import uuid
import os
import sys
import asyncio
import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname((os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.common.mongo.client import get_mongo_client
from core.v03.relationship_extractor.documents.amend import extract_relationship_amend
from core.v03.relationship_extractor.documents.replace import extract_relationship_replace
from core.v03.relationship_extractor.documents.repeal import extract_relationship_repeal
from core.v03.relationship_extractor.documents.detail import extract_relationship_detail
from core.v03.relationship_extractor.documents.referential import extract_relationship_referential
from core.v03.relationship_extractor.documents.base import extract_relationship_base
from core.v03.relationship_extractor.utils import mapping_document, extract_document_info, arbitrate_relationships, extract_doc_number



MAP_TYPE_AND_REASON = {
    'base': 'Được văn bản đầu vào sử dụng làm căn cứ',
    'amend': 'Bị sửa đổi bởi văn bản đầu vào',
    'add': 'Bị bổ sung bởi văn bản đầu vào',
    'replace': 'Bị thay thế bởi văn bản đầu vào',
    'repeal_apart': 'Bị bãi bỏ một phần bởi văn bản đầu vào',
    'repeal_full': 'Bị bãi bỏ toàn bộ bởi văn bản đầu vào',
    'detail': 'Được quy định chi tiết bởi văn bản đầu vào',
    'referential': 'Văn bản được văn bản đầu vào dẫn chiếu, áp dụng',
}


async def extract_relationship_from_segments_level_documment(segments, document_name, document_code=None, client=None, semaphore=None, base_doc_numbers=None, base_names=None, document_content=None):
    '''
        extract relationship documment include amend, replace, detail, repeal and referential
    '''
    relationships = {}

    tasks = [
        extract_relationship_amend(segments, document_name, client, semaphore),
        extract_relationship_replace(segments, document_name, client, semaphore),
        extract_relationship_detail(segments, document_name, client, semaphore),
        extract_relationship_repeal(segments, document_name, client, semaphore),
        extract_relationship_referential(segments, document_name, client, semaphore, base_doc_numbers, base_names, document_content)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    relationships_amend = results[0]
    relationships_replace = results[1]
    relationships_detail = results[2]
    relationships_repeal = results[3]
    relationships_referential = results[4]
    if 'amend' in relationships_amend: relationships['amend'] = relationships_amend['amend'] + relationships_replace['replace_apart']
    if 'add' in relationships_amend: relationships['add'] = relationships_amend['add']
    if 'replace_full' in relationships_replace: relationships['replace'] = relationships_replace['replace_full']
    if 'repeal_full' in relationships_repeal: relationships['repeal_full'] = relationships_repeal['repeal_full']
    if 'repeal_apart' in relationships_repeal: relationships['repeal_apart'] = relationships_repeal['repeal_apart']
    if 'detail' in relationships_detail: relationships['detail'] = relationships_detail['detail']
    if isinstance(relationships_referential, dict) and 'referential' in relationships_referential: relationships['referential'] = relationships_referential['referential']


    # Khử trùng chéo: mỗi văn bản (theo số hiệu) chỉ giữ ở loại quan hệ ưu tiên cao nhất.
    relationships = arbitrate_relationships(relationships)

    mapping_relationships = []
    for key, names in relationships.items():
        if len(names) != 0:
            for name in names:
                mapping_relationships.append({
                    'name': name,
                    'rel_type': key,
                    'type': MAP_TYPE_AND_REASON[key],
                    'document_code': '',
                    'agency': '',
                    'code': ''
                    
                })
                                
    final_mapping_relationships = []
    __set_codes = set()
    for __relationship in mapping_relationships:
        __relationship['code'] = ""
        __relationship['document_code'] = ""
        __relationship['agency'] = ""        
        
        name = __relationship['name']
        documents = mapping_document(name)
        if len(documents) == 0:
            # Không map được sang văn bản trong DB -> giữ lại dạng unmapped,
            # trích document_code từ tên để lưu vào draft ở bước sau.
            __relationship['name'] = name
            __relationship['code'] = ''
            __relationship['document_code'] = (extract_document_info(name).get('document_codes') or '')
            __relationship['agency'] = ''
            final_mapping_relationships.append(__relationship)  # Thêm trực tiếp
        else:
            document = documents[0]
            __relationship['name'] = name
            __relationship['code'] = document['_source']['doc_id']
            __relationship['document_code'] = document['_source']['doc_code']
            __relationship['agency'] = document['_source']['agency_ids']
            if document_code is not None and document['_source']['doc_id'] == document_code:
                continue
            if __relationship['code'] not in __set_codes:                
                __set_codes.add(__relationship['code'])
                final_mapping_relationships.append(__relationship)
    
    return relationships, final_mapping_relationships


async def extract_relationship_from_brief_level_documment(document_content, document_name, document_code=None, client=None, semaphore=None):
    '''
        extract base relationship from brief of document 
    '''
    relationships = await extract_relationship_base(content=document_content, document_name=document_name, client=client, semaphore=semaphore)

    if relationships is None:
        relationships = {}

    mapping_relationships = []
    for key, names in relationships.items():
        if key !=  'base':
            continue
        if len(names) != 0:
            for name in names:
                mapping_relationships.append({
                    'name': name,
                    'rel_type': key,
                    'type': MAP_TYPE_AND_REASON[key],
                    'document_code': '',
                    'agency': '',
                    'code': ''
                    
                })
                
                                
    final_mapping_relationships = []
    __set_codes = set()
    for __relationship in mapping_relationships:
        __relationship['code'] = ""
        __relationship['document_code'] = ""
        __relationship['agency'] = ""        
        
        name = __relationship['name']
        logger.info("get_document_name_info", action="extract_relationship_from_brief_level_documment", name=name)
        documents = mapping_document(name)
        if not documents or not any(documents):
            # Không map được sang văn bản trong DB (vd: sai tên so với doc_code) ->
            # giữ lại quan hệ ở dạng unmapped (name + document_code) thay vì bỏ mất.
            __relationship['name'] = name
            __relationship['code'] = ''
            __relationship['document_code'] = (extract_document_info(name).get('document_codes') or '')
            __relationship['agency'] = ''
            final_mapping_relationships.append(__relationship)
            continue
        document = documents[0]
        
        __relationship['name'] = name
        __relationship['code'] = document['_source']['doc_id']
        __relationship['document_code'] = document['_source']['doc_code']
        __relationship['agency'] = document['_source']['agency_ids']
        
        if document_code is not None and document['_source']['doc_id'] == document_code:
            continue
                        
        if document['_source']['doc_id'] not in __set_codes:                
            __set_codes.add(document['_source']['doc_id'])
            final_mapping_relationships.append(__relationship)
     
    return relationships, final_mapping_relationships

    
async def extract_relationship_level_document(document_content, document_name, segments, document_code=None, batch_size: int = 10):
    custom_timeout = httpx.Timeout(600.0, connect=10.0)
    semaphore = asyncio.Semaphore(batch_size)
    limits = httpx.Limits(max_keepalive_connections=batch_size, max_connections=batch_size * 2)
    async with httpx.AsyncClient(limits=limits, timeout=custom_timeout) as client:
        # Chạy module base (brief) trước để lấy danh sách số hiệu văn bản căn cứ,
        # truyền xuống module referential nhằm chống nhân đôi: một văn bản vừa là
        # căn cứ vừa bị dẫn chiếu trong thân -> ưu tiên giữ ở base, loại khỏi referential.
        base_relationships, base_final_mapping_relationships = await extract_relationship_from_brief_level_documment(
            document_content, document_name, document_code, client, semaphore
        )
        base_doc_numbers = {
            num for name in base_relationships.get('base', [])
            if (num := extract_doc_number(name))
        }
        # Tên đầy đủ của các văn bản căn cứ -> khử văn bản LUẬT không số hiệu
        # (vd "Bộ luật Tố tụng hình sự") bị nhặt nhầm vào referential.
        base_names = base_relationships.get('base', [])

        other_relationships, other_final_mapping_relationships = await extract_relationship_from_segments_level_documment(
            segments, document_name, document_code, client, semaphore, base_doc_numbers, base_names, document_content
        )

        relationships = base_relationships | other_relationships
        final_mapping_relationships = base_final_mapping_relationships + other_final_mapping_relationships
        return relationships, final_mapping_relationships


if __name__ == "__main__":
    from core.common.elastic import ElasticSearcher
    from pymongo import MongoClient
    from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig

    client = get_mongo_client()

    db = client[MigrateConfig.MIGRATE_CORE_DB]
    law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
    law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]

    doc_id = '5bd79bc7-0a02-42db-94e7-f17401142042'
    elastic_searcher = ElasticSearcher()
    doc_content = elastic_searcher.get_document_content(doc_id)
    doc_code = law_documents_collection.find_one({'doc_id': doc_id})['doc_code']
    doc_title = law_documents_collection.find_one({'doc_id': doc_id})['doc_title']
    effective_status_id = law_documents_collection.find_one({'doc_id': doc_id})['effective_status_id']
    segments = list(law_articles_collection.find({'doc_id': doc_id}))

    async def main():
        if doc_content and doc_title and segments and doc_code:
            relationships, final_mapping_relationships = await extract_relationship_level_document(doc_content, doc_title, segments, doc_code, batch_size=5)
            logger.info("extract_relationship_level_document_successful", action="__main__", relationships=relationships, final_mapping_relationships=final_mapping_relationships)
    asyncio.run(main())


    
