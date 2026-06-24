from core.common.mongo.client import get_mongo_client
import uuid
import os
import sys
import structlog
from pymongo import MongoClient
from datetime import datetime
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from jobs.law.utils import check_document_category, get_last_modified_by,\
                             parse_datetime, parse_date, check_document_level
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

client = get_mongo_client()
raw_db = client[MigrateConfig.MIGRATE_RAW_DB]
core_db = client[MigrateConfig.MIGRATE_CORE_DB]


def migrate_data():
    """Chuyển đổi dữ liệu từ document_segments sang law_documents, law_agencies, law_references, law_signers."""
    documents = list(raw_db[MongoDBCollectionConfig.RAW_DOCUMENTS_SEGMENTS_COLLECTION_NAME].find({}))    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    failed_codes = []
    
    for doc in documents:
        try:
            # 1. Migrate sang law_agencies
            doc_agency_name = next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Cơ quan ban hành'), '')
            if isinstance(doc_agency_name, list):
                agency_names = doc_agency_name
            elif isinstance(doc_agency_name, str):
                agency_names = doc_agency_name.split(',')
            else:
                agency_names = []
            agency_ids = []
            for agency_name in agency_names:
                agency_name = agency_name.strip()
                if not agency_name:
                    continue
                existing_agency = core_db[MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME].find_one({'agency_name': agency_name})
                if not existing_agency:
                    agency_id = str(uuid.uuid4())
                    agency = {
                            'agency_id': agency_id,
                            'agency_name': agency_name,
                            'created_date': parse_datetime(doc.get('created_date', None)),
                            'created_by': doc.get('created_by', ''),
                            'last_modified': get_last_modified_by(doc),
                            'last_modified_by': doc.get('last_modified_by', '')
                        }
                    core_db[MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME].insert_one(agency)
                    logger.info(action="migrate_data", event="law_agency_migrated", agency_name=agency_name)
                else:
                    agency_id = existing_agency['agency_id']
                agency_ids.append(agency_id)
                
            # 2. Migrate sang law_signers
            doc_signer_name = next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Người ký ban hành'), '')
            if isinstance(doc_signer_name, list):
                signer_names = doc_signer_name
            elif isinstance(doc_signer_name, str):
                signer_names = doc_signer_name.split(',')
            else:
                signer_names = []
            signer_ids = []
            for signer_name in signer_names:
                signer_name = signer_name.strip()
                if not signer_name:
                    continue
                existing_signer = core_db[MongoDBCollectionConfig.LAW_SIGNERS_COLLECTION_NAME].find_one({'signer_name': signer_name})
                if not existing_signer:
                    signer_id = str(uuid.uuid4())
                    signer = {
                        'signer_id': signer_id,
                        'signer_name': signer_name,
                        'signer_role': '',
                        'created_date': parse_datetime(doc.get('created_date', None)),
                        'created_by': doc.get('created_by', ''),
                        'last_modified': get_last_modified_by(doc),
                        'last_modified_by': doc.get('last_modified_by', '')
                    }
                    core_db[MongoDBCollectionConfig.LAW_SIGNERS_COLLECTION_NAME].insert_one(signer)
                    logger.info(action="migrate_data", event="law_signer_migrated", signer_name=signer_name)
                else:
                    signer_id = existing_signer['signer_id']
                signer_ids.append(signer_id)
    
            # 3. Migrate sang law_doc_types
            logger.info(action="migrate_data", event="law_doc_types_migration_started", document_code=doc.get('document_code', 'Unknown'))
            doc_type_name = next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Loại văn bản'), '')
            if doc_type_name:
                existing_doc_type = core_db[MongoDBCollectionConfig.LAW_DOCUMENT_TYPE_COLLECTION_NAME].find_one({'doc_type_name': doc_type_name})
                if not existing_doc_type:
                    type_id = str(uuid.uuid4())
                    doc_type_new = {
                        'type_id': type_id,
                        'doc_type_name': doc_type_name,
                        'created_date': parse_datetime(doc.get('created_date', None)),
                        'created_by': doc.get('created_by', ''),
                        'last_modified': get_last_modified_by(doc),
                        'last_modified_by': doc.get('last_modified_by', ''),
                        'status': 'ACTIVE'
                    }
                    core_db[MongoDBCollectionConfig.LAW_DOCUMENT_TYPE_COLLECTION_NAME].insert_one(doc_type_new)
                    logger.info(action="migrate_data", event="law_doc_type_migrated", doc_type_new=doc_type_new)
                else:
                    type_id = existing_doc_type['type_id']
    
            # 4. Migrate sang law_documents
            doc_category = check_document_category(doc)
            expiry_date_str = parse_date(next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Ngày hết hiệu lực'), None))
            doc_status = doc.get('decree_status', '')        
            if expiry_date_str:
                expiry_date = parse_date(expiry_date_str.strip())
                status = "Hết hiệu lực" if expiry_date and expiry_date < now else "Còn hiệu lực"
            else:
                expiry_date_str = ''
                if doc_status:
                    status = doc_status
                else:
                    status = "Không xác định"
    
            # 5. Get decree_status_id from law_decree_status
            decree_status_id = None
            if status:
                existing_decree_status = core_db[MongoDBCollectionConfig.LAW_DECREE_STATUS_COLLECTION_NAME].find_one({'decree_status_name': status})
                if not existing_decree_status:
                    decree_status_id = str(uuid.uuid4())
                    decree_status = {
                        'decree_status_id': decree_status_id,
                        'decree_status_name': status,
                        'created_date': parse_datetime(doc.get('created_date', None)),
                        'created_by': doc.get('created_by', ''),
                        'last_modified': get_last_modified_by(doc),
                        'last_modified_by': doc.get('last_modified_by', ''),
                        'status': 'ACTIVE'
                    }
                    core_db[MongoDBCollectionConfig.LAW_DECREE_STATUS_COLLECTION_NAME].insert_one(decree_status)
                    logger.info(action="migrate_data", event="decree_status_migrated", decree_status=decree_status)
                else:
                    decree_status_id = existing_decree_status['decree_status_id']
    
            # 6. Migrate sang law_industry_sectors
            doc_industry_sector_name = next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Lĩnh vực/Ngành'), '')
            if isinstance(doc_industry_sector_name, list):
                industry_sector_names = doc_industry_sector_name
            elif isinstance(doc_industry_sector_name, str):
                industry_sector_names = doc_industry_sector_name.split(',')
            else:
                industry_sector_names = []
            industry_sector_ids = []
            for industry_sector_name in industry_sector_names:
                existing_industry_sector = core_db[MongoDBCollectionConfig.LAW_INDUSTRY_SECTORS_COLLECTION_NAME].find_one({'industry_sector_name': industry_sector_name})
                if not existing_industry_sector:
                    industry_sector_id = str(uuid.uuid4())
                    industry_sector = {
                        'industry_sector_id': industry_sector_id,
                        'industry_sector_name': industry_sector_name,
                        'created_date': parse_datetime(doc.get('created_date', None)),
                        'created_by': doc.get('created_by', ''),
                        'last_modified': get_last_modified_by(doc),
                        'last_modified_by': doc.get('last_modified_by', ''),
                        'status': 'ACTIVE'
                    }
                    core_db[MongoDBCollectionConfig.LAW_INDUSTRY_SECTORS_COLLECTION_NAME].insert_one(industry_sector)
                    logger.info(action="migrate_data", event="law_industry_sector_migrated", industry_sector_name=industry_sector_name)
                else:
                    industry_sector_id = existing_industry_sector['industry_sector_id']
                industry_sector_ids.append(industry_sector_id)
            logger.info(action="migrate_data", event="law_industry_sectors_migration_completed", document_code=doc.get('document_code', 'Unknown'))
    
            # 7. Migrate sang law_keywords
            logger.info(action="migrate_data", event="law_keywords_migration_started", document_code=doc.get('document_code', 'Unknown'))
            keyword_codes = doc.get('keyword_codes', [])        
            keyword_ids = []
            for keyword_code in keyword_codes:
                existing_keyword = core_db[MongoDBCollectionConfig.LAW_KEYWORD_COLLECTION_NAME].find_one({'keyword_name': keyword_name})
                if not existing_keyword:
                    keyword_id = str(uuid.uuid4())
                    keyword = {
                        'keyword_id': keyword_id,
                        'keyword_name': keyword_name,
                        'created_date': parse_datetime(doc.get('created_date', None)),
                        'created_by': doc.get('created_by', ''),
                        'last_modified': get_last_modified_by(doc),
                        'last_modified_by': doc.get('last_modified_by', ''),
                        'status': "ACTIVE"
                    }
                    core_db[MongoDBCollectionConfig.LAW_KEYWORD_COLLECTION_NAME].insert_one(keyword)
                else:
                    keyword_id = existing_keyword['keyword_id']
                keyword_ids.append(keyword_id)
            logger.info(action="migrate_data", event="law_keywords_migration_completed", document_code=doc.get('document_code', 'Unknown'))
    
            # 8. Migrate sang doc_issuing_level
            doc_code = doc.get("document_code", "")
            doc_issuing_level_name = check_document_level(doc_code)
            existing_doc_issuing_level = core_db[MongoDBCollectionConfig.LAW_ISSUING_LEVEL_COLLECTION_NAME].find_one({'doc_issuing_level_name': doc_issuing_level_name})
            if not existing_doc_issuing_level:
                doc_issuing_level_id = str(uuid.uuid4())
                doc_issuing_level = {
                    'doc_issuing_level_id': doc_issuing_level_id,
                    'doc_issuing_level_name': doc_issuing_level_name,
                    'created_date': parse_datetime(doc.get('created_date', None)),
                    'created_by': doc.get('created_by', ''),
                    'last_modified': get_last_modified_by(doc),
                    'last_modified_by': doc.get('last_modified_by', ''),
                    'status': 'ACTIVE'
                }
                core_db[MongoDBCollectionConfig.LAW_ISSUING_LEVEL_COLLECTION_NAME].insert_one(doc_issuing_level)
                logger.info(action="migrate_data", event="law_issued_level_migrated", doc_issuing_level_name=doc_issuing_level_name)
            else:
                doc_issuing_level_id = existing_doc_issuing_level['doc_issuing_level_id']
            logger.info(action="migrate_data", event="doc_issuing_level_details", document_code=doc.get('document_code', 'Unknown'), doc_issuing_level_name=doc_issuing_level_name)
    
            # 9. Migrate sang law_documents
            doc_category = doc_type_name
            law_doc = {
                'doc_id': str(doc['code']),
                'doc_code': doc.get('document_code', ''),
                'doc_title': doc.get('name', ''),
                'doc_short_description': doc.get('short_description', ''),
                'type_id': type_id,
                'doc_category': doc_category,
                'doc_content': doc.get('description', None),
                'issuing_level_id': doc_issuing_level_id,
                'agency_ids': agency_ids,
                'doc_issue_date': parse_date(next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Ngày ban hành'), None)),
                'doc_effective_date': parse_date(next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Ngày có hiệu lực'), None)),
                'doc_expiry_date': parse_date(expiry_date_str.strip()),
                'doc_effective_status': status,
                'data_source': doc.get('data_source', ''),
                'storage_id': doc.get('storage_code', ''),
                'created_date': parse_date(doc.get('created_date', None)),
                'created_by': doc.get('created_by', ''),
                'last_modified': get_last_modified_by(doc),
                'last_modified_by': doc.get('last_modified_by', ''),
                'decree_status_id': decree_status_id,
                'industry_sector_ids': industry_sector_ids,
                'keyword_ids': keyword_ids,
                'signer_ids': signer_ids
            }
            core_db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME].update_one(
                                        {"doc_id": law_doc["doc_id"]},
                                        {"$set": law_doc},
                                        upsert=True
                                        )
            logger.info(action="migrate_data", event="law_document_migrated", doc_code=law_doc['doc_code'])            
    
            # 9. Migrate sang law_references
            reference_types = [
                ('AMEND', doc.get('amend_documents', [])),
                ('AMENDED', doc.get('amended_documents', [])),
                ('BASIS', doc.get('basis_documents', [])),
                ('CONSOLIDATED', doc.get('consolidated_documents', [])),
                ('CONTENT_CONNECTION', doc.get('content_connection_documents', [])),
                ('REPLACE', doc.get('replace_documents', [])),
                ('REPLACED', doc.get('replaced_documents', [])),
                ('DETAIL', doc.get('guided_documents', [])),
                ('CORRECT', doc.get('correct_documents', [])),
                ('CORRECTED', doc.get('corrected_documents', [])),
                ('REFERENTIAL', doc.get('referential_documents', []))
            ]
            for ref_type, ref_docs in reference_types:
                for target_id in ref_docs:
                    reference = {
                        'reference_id': str(uuid.uuid4()),
                        'source_id': str(doc['code']),
                        'source_type': 'DOCUMENT',
                        'target_id': str(target_id),
                        'target_type': 'DOCUMENT',
                        'created_by': doc.get('created_by', ''),
                        'reference_status': doc.get('decree_status', ''),
                        'reference_type': ref_type,
                        'created_date': parse_date(doc.get('created_date', None)),
                        'last_modified': get_last_modified_by(doc),
                        'last_modified_by': doc.get('last_modified_by', '')
                    }
                    core_db[MongoDBCollectionConfig.LAW_REFERENCE_COLLECTION_NAME].update_one({'source_id': str(doc['code']), 'target_id': str(target_id)}, 
                                                    {'$set': reference}, 
                                                    upsert=True)
                    logger.info(action="migrate_data", event="law_reference_migrated", ref_type=ref_type, document_code=doc['document_code'], target_id=target_id)
        except Exception as e:
            logger.error(action="migrate_data", event="migrate_data_failed", **{"error.code": "DB", "error.message": str(e)}, document_code=doc.get('document_code', 'Unknown'), exc_info=True)
            failed_codes.append(doc.get('code'))
            continue
    if failed_codes:
        logger.info(action="migrate_data", event="failed_documents_summary", failed_codes=failed_codes)


def main():
    try:
        logger.info(action="main", event="migration_started")
        import time
        start_time = time.time()
        migrate_data()
        logger.info(action="main", event="migration_completed", duration=time.time() - start_time)
    except Exception as e:
        logger.error(action="main", event="migration_failed", **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
        raise

if __name__ == "__main__":
    main()
