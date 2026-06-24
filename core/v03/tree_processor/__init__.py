from typing import List, Dict
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

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

    def map_document_content(self, doc_content: str) -> List[Dict]:
        """Map document content to its corresponding document ID.

        Args:
            doc_content: Content or name of the document.

        Returns:
            List of dictionaries containing document metadata, including '_id'.

        Note:
            This is a placeholder implementation. Replace with actual logic to map
            document content to a document ID in your system.
        """
        try:
            # Example return format: [{"_id": "351416", "content": doc_content}]
            return [{"_id": str(hash(doc_content))[:6], "content": doc_content}]
        except Exception as e:
            logger.error("map_document_content_failed", action="map_document_content", **{"error.code": "PARSE", "error.message": str(e)}, content_len=len(doc_content) if doc_content else 0, exc_info=True)
            raise