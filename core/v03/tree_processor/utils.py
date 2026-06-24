from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import sys
import os
import structlog

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname((os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)


from logs.logger_conf import setup_logging
from core.v03.relationship_extractor.utils import mapping_document

setup_logging()
logger = structlog.get_logger()



class DocumentMapper:
    """Utility class for document-related operations."""

    @staticmethod
    def is_valid_text(text: str) -> bool:
        """Check if the input text is non-empty and valid.

        Args:
            text: Input text to validate.

        Returns:
            True if text is non-empty and valid, False otherwise.
        """
        if text and isinstance(text, str):
            return True
        logger.error("process_text_invalid", action="is_valid_text", **{"error.code": "VAL", "error.message": "Invalid or empty text input"}, text_type=type(text).__name__)
        return False

    def map_document_name(self, doc_name: str) -> List[Dict]:
        """Map document name to its corresponding document ID.

        Args:
            doc_name: Name of the document.

        Returns:
            List of dictionaries containing document metadata, including '_id'.

        Note:
            This is a placeholder implementation. Replace with actual logic to map
            document name to a document ID in your system.
        """
        try:
            mapped_doc = mapping_document(doc_name)
            return mapped_doc            
        except Exception as e:
            logger.error("map_document_failed", action="map_document_name", **{"error.code": "DB", "error.message": str(e)}, doc_name=doc_name, exc_info=True)
            raise

    def map_document_names(self, doc_names: list) -> Dict:
        """Map document names to its corresponding documents ID.

        Args:
            doc_names: Name of the documents.

        Returns:
            Dictionary of document names and their corresponding document IDs.

        Note:
            This is a placeholder implementation. Replace with actual logic to map
            document name to a document ID in your system.
        """
        try:
            mapped_docs = {}
            for doc_name in doc_names:
                mapped_doc = mapping_document(doc_name)
                mapped_docs[doc_name] = mapped_doc[0]["_id"]
            return mapped_docs            
        except Exception as e:
            logger.error("map_documents_failed", action="map_document_names", **{"error.code": "DB", "error.message": str(e)}, doc_count=len(doc_names), exc_info=True)
            raise

    def map_document_names_multithread(self, doc_names: List[str], max_workers: int = 20) -> Dict[str, str]:
        """Map document names to their corresponding document IDs using multithreading.

        Args:
            doc_names: List of document names.
            max_workers: Maximum number of worker threads to use.

        Returns:
            Dictionary mapping document names to document codes.
        """
        mapped_docs = {}

        def process(doc_name):
            try:
                mapped = mapping_document(doc_name)
                return doc_name, mapped[0]["_id"] if mapped else None
            except Exception as e:
                logger.error("map_document_error", action="process", **{"error.code": "DB", "error.message": str(e)}, doc_name=doc_name, exc_info=True)
                return doc_name, None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process, name): name for name in doc_names}
            for future in as_completed(futures):
                doc_name, code = future.result()
                if code:
                    mapped_docs[doc_name] = code
        return mapped_docs

if __name__ == '__main__':
    doc_names = ["Luật 32/2004/QH11 An ninh Quốc gia"]
    mapper = DocumentMapper()
    # mapped_docs = mapper.map_document_names_multithread(doc_names)
    mapped_docs = mapper.map_document_names(doc_names)
    logger.info("show_mapped_docs_result", action="__main__", docs=mapped_docs)