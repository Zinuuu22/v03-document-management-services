from core.common.elastic.client import get_elastic_client
import json
from typing import Dict, Any, Generator, Optional, List
from datetime import datetime
import structlog
from elasticsearch import Elasticsearch
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import ElasticConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

es_client = get_elastic_client()

def parse_date(value: str) -> Optional[datetime]:
    """Parse string to datetime, expecting YYYY-MM-DD format.

    Args:
        value (str): Date string in YYYY-MM-DD format.

    Returns:
        Optional[datetime]: Parsed datetime or None if empty.

    Raises:
        ValueError: If date format is invalid.
    """
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Date must be in YYYY-MM-DD format (e.g., 2025-01-05)")

def build_query(args: Dict[str, Any]) -> Dict[str, Any]:
    """Build Elasticsearch query based on input filters for document_segment_data index.

    Args:
        args (Dict[str, Any]): Filter parameters (text, status, codes, dates, searchMethod, searchFields, etc.).

    Returns:
        Dict[str, Any]: Elasticsearch bool query.
    """
    query = {"bool": {"filter": []}}

    # Full-text search
    if args.get('text'):
        scope = args.get('searchFields', ['name', 'content'])
        if scope == ['name']:
            search_fields = ['doc_title']
        elif scope == ['content']:
            search_fields = ['doc_content']
        else:
            search_fields = ['doc_title', 'doc_content']
        
        search_method = args.get('searchMethod', 'normal')
        
        if search_method == 'exact':
            if len(search_fields) == 1:
                query['bool']['must'] = {
                    "match_phrase": {
                        search_fields[0]: args['text']
                    }
                }
            else:
                query['bool']['must'] = {
                    "multi_match": {
                        "query": args['text'],
                        "fields": search_fields,
                        "type": "phrase"
                    }
                }
        else:  # normal
            # Boost doc_title field for normal searches
            weighted_fields = [f"{field}^2" if field == 'doc_title' else field for field in search_fields]
            
            if args.get('filterType') == 'fuzzy':
                query['bool']['must'] = {
                    "multi_match": {
                        "query": args['text'],
                        "fields": weighted_fields,
                        "fuzziness": "AUTO"
                    }
                }
            else:
                query['bool']['must'] = {
                    "multi_match": {
                        "query": args['text'],
                        "fields": weighted_fields,
                        "type": "best_fields"
                    }
                }

    # Status filter
    if args.get('status'):
        query['bool']['filter'].append({"term": {"status_in_system": args['status']}})

    # Multi-value code filters s
    for field, values in [
        ("type_id.keyword", args.get('documentTypeCodes', [])),
        ("category_id.keyword", args.get('documentCategoryCodes', [])),        
        ("keyword_ids.keyword", args.get('keywordCodes', [])),
        ("industry_sector_ids.keyword", args.get('industrySectorCodes', [])),
        ("issuing_level_id.keyword", args.get('issuedLevelCodes', [])),
        ("agency_ids.keyword", args.get('agencyIssuedCodes', [])),
        ("effective_status_id.keyword", args.get('decreeStatusCodes', [])),
        ("doc_id.keyword", args.get('codes', [])),
        ("position_ids.keyword", args.get('positionCodes', [])),
        ("signer_ids.keyword", args.get('signerCodes', []))
    ]:
        if values:
            query['bool']['filter'].append({"terms": {field: values}})


    # Date range filters
    for field, start, end in [
        ("doc_issue_date.keyword", args.get('decreeIssuedFrom'), args.get('decreeIssuedTo')),
        ("doc_expiry_date.keyword", args.get('dateExpiredFrom'), args.get('dateExpiredTo')),
        ("doc_effective_date.keyword", args.get('decreeEffectFrom'), args.get('decreeEffectTo'))
    ]:
        if start or end:
            range_query = {}
            if start:
                range_query["gte"] = start.strftime('%Y-%m-%d')
            if end:
                range_query["lte"] = end.strftime('%Y-%m-%dz')
            query['bool']['filter'].append({"range": {field: range_query}})

    # If no must clause (no text search), add match_all
    if 'must' not in query['bool']:
        query['bool']['must'] = {"match_all": {}}

    logger.debug("build_query_success", action="build_query")
    return query


def build_query_semantic_search(args: Dict[str, Any]) -> Dict[str, Any]:
    """Build Elasticsearch query based on input filters for document_segment_data index.

    Args:
        args (Dict[str, Any]): Filter parameters (text, status, codes, dates, searchMethod, searchFields, etc.).

    Returns:
        Dict[str, Any]: Elasticsearch bool query.
    """
    query = {"bool": {"filter": []}}

    # Status filter
    if args.get('status'):
        query['bool']['filter'].append({"term": {"status_in_system": args['status']}})

    # Multi-value code filters (including documentCategoryCodes)
    for field, values in [
        ("type_id.keyword", args.get('documentTypeCodes', [])),
        ("category_id.keyword", args.get('documentCategoryCodes', [])),        
        ("keyword_ids.keyword", args.get('keywordCodes', [])),
        ("industry_sector_ids.keyword", args.get('industrySectorCodes', [])),
        ("issuing_level_id.keyword", args.get('issuedLevelCodes', [])),
        ("agency_ids.keyword", args.get('agencyIssuedCodes', [])),
        ("effective_status_id.keyword", args.get('decreeStatusCodes', [])),
        ("doc_id.keyword", args.get('codes', [])),
        ("position_ids.keyword", args.get('positionCodes', [])),
        ("signer_ids.keyword", args.get('signerCodes', []))
    ]:
        if values:
            query['bool']['filter'].append({"terms": {field: values}})

    # Date range filters
    for field, start, end in [
        ("doc_issue_date.keyword", args.get('decreeIssuedFrom'), args.get('decreeIssuedTo')),
        ("doc_expiry_date.keyword", args.get('dateExpiredFrom'), args.get('dateExpiredTo')),
        ("doc_effective_date.keyword", args.get('decreeEffectFrom'), args.get('decreeEffectTo'))
    ]:
        if start or end:
            range_query = {}
            if start:
                range_query["gte"] = start.strftime('%Y-%m-%d')
            if end:
                range_query["lte"] = end.strftime('%Y-%m-%dz')
            query['bool']['filter'].append({"range": {field: range_query}})

    # If no must clause (no text search), add match_all
    if 'must' not in query['bool']:
        query['bool']['must'] = {"match_all": {}}

    logger.debug("build_query_semantic_search_success", action="build_query_semantic_search")
    return query


def search(es_client: Elasticsearch, 
           index: str = ElasticConfig.ELASTIC_INDEX, 
           query: Dict[str, Any] = None, 
           batch_size: int = 1000,
           max_records: int = 1000,
           skip: int = 0) -> Generator[List[Dict], None, None]:
    """Thực hiện tìm kiếm trên Elasticsearch và trả về generator cho các lô kết quả.

    Args:
        es_client (Elasticsearch): Thể hiện của client Elasticsearch.
        index (str): Tên chỉ mục Elasticsearch.
        query (Dict[str, Any]): Truy vấn Elasticsearch.
        batch_size (int): Số lượng tài liệu trong mỗi lô.
        max_records (int): Số lượng tài liệu tối đa cần trả về.
        skip (int): Số lượng tài liệu cần bỏ qua (offset).

    Yields:
        List[Dict]: Danh sách các tài liệu trong mỗi lô.

    Raises:
        Exception: Nếu tìm kiếm hoặc scroll thất bại.
    """
    try:
        # Thực thi tìm kiếm với scroll
        search_params = {
            "index": index,
            "query": query,
            "size": batch_size,
            "scroll": "2m"
        }
        logger.debug("search_elasticsearch_started", action="search", skip=skip, max_records=max_records)
        
        total_skipped = 0
        total_yielded = 0
        response = es_client.search(**search_params)
        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']
        
        while hits:
            for hit in hits:
                if total_skipped < skip:
                    total_skipped += 1
                    continue
                if total_yielded >= max_records:
                    break
                yield [hit]
                total_yielded += 1
            
            if total_yielded >= max_records:
                break
                
            # Fetch next batch
            response = es_client.scroll(scroll_id=scroll_id, scroll="2m")
            hits = response['hits']['hits']

        # Xóa scroll
        es_client.clear_scroll(scroll_id=scroll_id)
    except Exception as e:
        logger.error("search_elasticsearch_failed", action="search", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)
        raise

def stream(search_generator: Generator[List[Dict], None, None], 
           total_count: int) -> Generator[bytes, None, None]:
    """Stream Elasticsearch results as JSON.

    Args:
        search_generator (Generator[List[Dict], None, None]): Generator yielding documents (already paginated).
        total_count (int): Total number of documents found.

    Yields:
        bytes: JSON chunks.
    """
    logger.debug("stream_elasticsearch_started", action="stream", total_count=total_count)

    # Start JSON response
    yield b'{"code": 0, "message": "Search completed successfully", "data": {"count": '
    yield str(total_count).encode('utf-8')
    yield b', "model": ['


    first = True
    for batch in search_generator:
        for hit in batch:
            if not first:
                yield b','
            first = False

            doc = hit['_source']
            result = {
                "code": doc.get("doc_id", ""),
                "name": doc.get("doc_title", ""),
                "documentCode": doc.get("doc_code", ""),
                "decreeEffect": doc.get("doc_effective_date", ""),
                "decreeIssued": doc.get("doc_issue_date", ""),
                "dateExpired": doc.get("doc_expiry_date", ""), 
                "agencyIssuedCodes": doc.get("agency_ids", ""),                
                "documentCategoryCode": doc.get("category_id", ""),
                "storageCode": doc.get("storage_id", ""),
                "agencySymbol": doc.get("agencySymbol", ""),
                "keywordCodes": doc.get("keyword_ids", ""),
                "industrySectorCodes": doc.get("industry_sector_ids", ""),
                "issuedLevelCode": doc.get("issuing_level_id", ""),
                "properties": doc.get("properties", ""),
                "documentTypeCode": doc.get("type_id", ""),
                "signerCodes": doc.get("signer_ids", ""),
                "decreeStatusCode": doc.get("effective_status_id", ""),
                "shortDescription": doc.get("doc_short_description", ""),
                "correctedDocuments": doc.get("correctedDocuments", ""),
                "correctDocuments": doc.get("correctDocuments", ""),
                "replacedDocuments": doc.get("replacedDocuments", ""),
                "replaceDocuments": doc.get("replaceDocuments", ""),
                "referentialDocuments": doc.get("referentialDocuments", ""),
                "basisDocuments": doc.get("basisDocuments", ""),
                "contentConnectionDocuments": doc.get("contentConnectionDocuments", ""),
                "amendDocuments": doc.get("amendDocuments", ""),
                "amendedDocuments": doc.get("amendedDocuments", ""),
                "languageConnectionDocuments": doc.get("languageConnectionDocuments", ""),
                "source": doc.get("source", ""),
                "dataSource": doc.get("data_source", ""),
                "embeddingStatus": doc.get("embeddingStatus", ""),
                "status": doc.get("status_in_system", ""),
                "referenceStorageCodes": doc.get("reference_storage_ids", "")
            }

            json_chunk = json.dumps(result, ensure_ascii=False).encode('utf-8')
            yield json_chunk

    logger.debug("stream_elasticsearch_completed", action="stream")
    yield b']}}'


if __name__ == "__main__":
    # Xây dựng truy vấn
    # query = build_query({'documentCategoryCodes': ['20250300001CAD']})
    # logger.info("main", msg="Generated query", query=query)

    # # Lấy tổng số bản ghi
    # count_result = es_client.count(index=ElasticConfig.ELASTIC_INDEX, body={"query": query})
    # total_count = count_result['count']
    # logger.debug("main", total_count=total_count)

    # # Tạo generator cho kết quả tìm kiếm
    # search_gen = search(es_client, query=query)

    output = parse_date('2022-09-19T00:00:00')
    logger.info("parse_date_success", action="main", output=str(output))