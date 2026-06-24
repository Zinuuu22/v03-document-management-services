from bdb import effective
import uuid
import os
import sys
import structlog
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from jobs.law.utils import connect_to_databases, parse_datetime, get_last_modified_by
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

if __name__ == "__main__":
    raw_db, core_db = connect_to_databases()
    
    documents = list(raw_db.document_segment.find({}))
    logger.info(action="main", event="documents_found", count=len(documents))
    
    operations = []  # List to store bulk update operations
    for doc in documents:
        doc_id = doc.get('code', None)
        guided_documents = doc.get('guided_documents', None)
        if doc_id is None or guided_documents is None:
            continue
        
        for target_id in guided_documents:
            reference = {
                'reference_id': str(uuid.uuid4()),
                'source_id': str(doc_id),
                'source_type': 'DOCUMENT',
                'target_id': str(target_id),
                'target_type': 'DOCUMENT',
                'reference_status': doc.get('decree_status', ''),
                'reference_type': 'DETAIL',
                'created_date': parse_datetime(doc.get('created_date', None)),
                'last_modified': get_last_modified_by(doc),
                'last_modified_by': doc.get('last_modified_by', '')
            }
            core_db.law_references.insert_one(reference)
            core_db.law_references.insert_one(reference)
            logger.info(action="main", event="law_reference_migrated", source=doc['document_code'], target=target_id)
