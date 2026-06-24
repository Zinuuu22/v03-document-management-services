from bdb import effective
import uuid
import os
import sys
import structlog
from pymongo import MongoClient
from pymongo import UpdateOne
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)
from core.v03.metadata_extractor.fields.extract_document_category import extract_document_category
from jobs.law.utils import connect_to_databases
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()


if __name__ == "__main__":
    _, core_db = connect_to_databases()
    
    documents = list(core_db.law_documents.find({'doc_category': 'Văn bản Pháp Luật'}))
    logger.info(action="main", event="documents_found", count=len(documents))
    
    count = 0
    effective_count = 0
    operations = []  # List to store bulk update operations

    for doc in documents:
        document_code = doc.get('doc_code', None)
        document_type = doc.get('doc_type', None)
        doc_effective_status = doc.get('doc_effective_status', None)

        response = extract_document_category(document_code, document_type)
        document_category = response.get('document_category', '')

        if document_category == 'Văn bản Pháp Luật':
            count += 1
            if doc_effective_status == 'Còn hiệu lực':
                effective_count += 1
        
        # Add update operation to the batch
        if document_category != doc['doc_category']:
            operations.append(
                UpdateOne(
                    {'doc_id': doc['doc_id']},
                    {'$set': {'doc_category': document_category}}
                )
            )

        # Process updates in batches of 1000 to balance memory and performance
        if len(operations) >= 500:
            core_db.law_documents.bulk_write(operations, ordered=False)
            operations = []  # Clear the list after writing

    # Write any remaining operations
    if operations:
        core_db.law_documents.bulk_write(operations, ordered=False)

    logger.info(action="main", event="documents_processed", count=count)
    logger.info(action="main", event="effective_documents_processed", count=effective_count)