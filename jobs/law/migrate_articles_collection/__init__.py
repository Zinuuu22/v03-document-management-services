from core.common.mongo.client import get_mongo_client
import os
import sys
import uuid
import structlog
from datetime import datetime
from pymongo import MongoClient
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()


def parse_datetime(date_str):
    """Chuyển đổi chuỗi ngày giờ sang định dạng datetime."""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return None


def parse_date(date_str):
    """Chuyển đổi chuỗi ngày sang định dạng datetime (chỉ ngày)."""
    try:
        return datetime.strptime(date_str, '%d/%m/%Y').date()
    except (ValueError, TypeError):
        return None


def connect_to_databases():
    """Kết nối tới raw_db và core_db."""
    try:
        client = get_mongo_client()
        raw_db = client[MigrateConfig.MIGRATE_RAW_DB]
        core_db = client[MigrateConfig.MIGRATE_CORE_DB]
        return raw_db, core_db
    except Exception as e:
        logger.error(action="connect_to_databases", event="connect_to_databases_failed", **{"error.code": "DB", "error.message": str(e)}, exc_info=True)
        raise


def get_last_modified_by(doc):
    val = doc.get('last_modified_by', None)
    if val is None or val == '':
        return datetime.now().strftime('%H:%M:%S %d/%m/%y')
    return val


def migrate_data():
    """Chuyển đổi dữ liệu từ document_segments sang law_documents, law_agencies, law_references, law_signers."""
    raw_db, core_db = connect_to_databases()
    
    documents = raw_db[MongoDBCollectionConfig.RAW_DOCUMENTS_SEGMENTS_COLLECTION_NAME].find()
    for doc in documents:
        try:
            # 1. Migrate sang law_documents
            law_doc = {
                'doc_id': str(doc['_id']),
                'doc_code': doc.get('document_code', ''),
                'doc_title': doc.get('name', ''),
                'doc_short_description': doc.get('short_description', ''),
                'doc_type': next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Loại văn bản'), ''),
                'doc_category': doc.get('document_category_code', ''),
                'doc_content': doc.get('description', None),
                'doc_issuing_level': next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Cấp ban hành'), ''),
                'doc_issuing_agency_code': doc.get('issued_level_code', ''),
                'doc_signer_code': doc.get('signer_codes', [None])[0] or '',
                'doc_issue_date': parse_date(next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Ngày ban hành'), None)),
                'doc_effective_date': parse_date(next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Ngày có hiệu lực'), None)),
                'doc_expiry_date': parse_date(next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Ngày hết hiệu lực'), None)),
                'doc_effective_status': doc.get('decree_status', ''),
                'data_source': doc.get('data_source', ''),
                'storage_code': doc.get('storage_code', ''),
                'created_date': parse_datetime(doc.get('created_date', None)),
                'created_by': doc.get('created_by', ''),
                'last_modified': parse_datetime(doc.get('last_modified', None)),
                'last_modified_by': get_last_modified_by(doc),
                'extract_article_state': None
            }

            if law_doc['doc_content'] is None:
                logger.warning(action="migrate_data", event="document_empty_content", document_code=doc.get('document_code', 'Unknown'))
                continue

            core_db.law_documents.insert_one(law_doc)
            logger.info(action="migrate_data", event="law_document_migrated", doc_code=law_doc['doc_code'])

            # 2. Migrate sang law_agencies
            agency_name = next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Cơ quan ban hành'), '')
            if agency_name:
                existing_agency = core_db.law_agencies.find_one({'agency_name': agency_name})
                if not existing_agency:
                    agency = {
                        'agency_id': str(uuid.uuid4()),
                        'agency_name': agency_name,
                        'created_date': parse_datetime(doc.get('created_date', None)),
                        'created_by': doc.get('created_by', ''),
                        'last_modified': parse_datetime(doc.get('last_modified', None)),
                        'last_modified_by': get_last_modified_by(doc)
                    }
                    core_db.law_agencies.insert_one(agency)
                    logger.info(action="migrate_data", event="law_agency_migrated", agency_name=agency_name)

            # 3. Migrate sang law_signers
            signer_name = next((prop['value'] for prop in doc.get('properties', []) if prop['key'] == 'Người ký ban hành'), '')
            if signer_name:
                existing_signer = core_db.law_signers.find_one({'signer_name': signer_name})
                if not existing_signer:
                    signer = {
                        'signer_id': doc.get('signer_codes', [None])[0] or str(uuid.uuid4()),
                        'signer_name': signer_name,
                        'signer_role': '',  # Không có trường tương ứng trong document_segments
                        'created_date': parse_datetime(doc.get('created_date', None)),
                        'created_by': doc.get('created_by', ''),
                        'last_modified': parse_datetime(doc.get('last_modified', None)),
                        'last_modified_by': get_last_modified_by(doc)
                    }
                    core_db.law_signers.insert_one(signer)
                    logger.info(action="migrate_data", event="law_signer_migrated", signer_name=signer_name)

            # 4. Migrate sang law_references
            reference_types = [
                ('AMEND', doc.get('amend_documents', [])),
                ('AMENDED', doc.get('amended_documents', [])),
                ('BASIS', doc.get('basis_documents', [])),
                ('CONSOLIDATED', doc.get('consolidated_documents', [])),
                ('CONTENT_CONNECTION', doc.get('content_connection_documents', [])),
                ('REPLACE', doc.get('replace_documents', [])),
                ('REPLACED', doc.get('replaced_documents', []))
            ]

            for ref_type, ref_docs in reference_types:
                for target_id in ref_docs:
                    reference = {
                        'reference_id': str(uuid.uuid4()),
                        'source_id': str(doc['_id']),
                        'source_type': 'DOCUMENT',
                        'target_id': target_id,
                        'target_type': 'DOCUMENT',
                        'reference_status': doc.get('decree_status', ''),
                        'reference_type': ref_type,
                        'created_date': parse_datetime(doc.get('created_date', None)),
                        'last_modified': parse_datetime(doc.get('last_modified', None)),
                        'last_modified_by': get_last_modified_by(doc)
                    }
                    core_db.law_references.insert_one(reference)
                    logger.info(action="migrate_data", event="law_reference_migrated", ref_type=ref_type, source=doc['document_code'], target=target_id)

        except Exception as e:
            logger.error(action="migrate_data", event="migrate_data_failed", **{"error.code": "DB", "error.message": str(e)}, doc_code=doc.get('document_code', 'Unknown'), exc_info=True)
            continue

def main():
    """Hàm chính để chạy migration."""
    try:
        logger.info(action="main", event="migration_process_started")
        migrate_data()
        logger.info(action="main", event="migration_process_completed")
    except Exception as e:
        logger.error(action="main", event="migration_process_failed", **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
        raise

if __name__ == "__main__":
    main()
