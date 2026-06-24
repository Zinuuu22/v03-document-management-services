"""
SignalR Client Utility
Handles communication with SignalR for real-time updates
"""

import json
import requests
from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger()


class SignalRClient:
    """Client for sending messages to SignalR endpoints"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or self._get_signalr_url()
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })

    def _get_signalr_url(self) -> str:
        """Get SignalR URL from environment or use default"""
        import os
        return os.getenv(
            "SIGNALR_BASE_URL",
            "http://localhost:5000/signalr"
        )

    def send_message(self, message: Dict[str, Any], topic: str) -> bool:
        """Send message to SignalR topic"""
        try:
            url = f"{self.base_url}/send"
            payload = {
                "topic": topic,
                "message": message
            }

            response = self.session.post(
                url,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                logger.debug(
                    "send_signalr_message_success",
                    action="send_message",
                    topic=topic,
                    message_id=message.get("request_id", "unknown")
                )
                return True
            else:
                logger.error(
                    "send_signalr_message_failed",
                    action="send_message",
                    topic=topic,
                    **{"error.code": "EXT", "error.message": f"HTTP {response.status_code}: {response.text}"}
                )
                return False

        except requests.exceptions.RequestException as e:
            logger.error(
                "send_signalr_request_failed",
                action="send_message",
                topic=topic,
                **{"error.code": "NET", "error.message": str(e)},
                exc_info=True
            )
            return False
        except Exception as e:
            logger.error(
                "send_signalr_message_failed",
                action="send_message",
                topic=topic,
                **{"error.code": "SYS", "error.message": str(e)},
                exc_info=True
            )
            return False

    def send_status_update(self, status: str, request_id: str, additional_data: Dict[str, Any] = None) -> bool:
        """Send status update for a request"""
        message = {
            "status": status,
            "request_id": request_id,
            "timestamp": self._get_timestamp(),
            **(additional_data or {})
        }

        # Determine topic based on status type
        topic = self._get_topic_from_status(status)

        return self.send_message(message, topic)

    def send_error_notification(self, error: str, request_id: str, context: Dict[str, Any] = None) -> bool:
        """Send error notification"""
        message = {
            "status": "error",
            "error": error,
            "request_id": request_id,
            "timestamp": self._get_timestamp(),
            **(context or {})
        }

        return self.send_message(message, "error_notifications")

    def send_completion_notification(self, request_id: str, result: Dict[str, Any], topic: str) -> bool:
        """Send completion notification"""
        message = {
            "status": "completed",
            "request_id": request_id,
            "result": result,
            "timestamp": self._get_timestamp()
        }

        return self.send_message(message, topic)

    def _get_topic_from_status(self, status: str) -> str:
        """Determine topic based on status"""
        topic_mapping = {
            "CREATE_DATA": "tree_classifier",
            "TRAINING": "tree_classifier",
            "COMPLETED": "tree_classifier",
            "PROCESSING": "extract_metadata",
            "EXTRACTING": "extract_keywords",
            "ANALYZING": "extract_law_authority",
            "IDENTIFYING": "extract_regulated_entities",
            "CLASSIFYING": "extract_regulated_object",
            "MAPPING": "extract_relationship",
            "LINKING": "extract_relationship_article",
            "ANALYZING_SOCIAL": "extract_social_relation",
            "IMPORTING": "import_tree"
        }

        return topic_mapping.get(status, "general_updates")

    def _get_timestamp(self) -> float:
        """Get current timestamp"""
        import time
        return time.time()

    def health_check(self) -> bool:
        """Check if SignalR service is healthy"""
        try:
            url = f"{self.base_url}/health"
            response = self.session.get(url, timeout=5)

            if response.status_code == 200:
                logger.debug("signalr_health_check_success", action="health_check")
                return True
            else:
                logger.warning(
                    "signalr_health_check_failed",
                    action="health_check",
                    **{"error.code": "EXT", "error.message": f"HTTP {response.status_code}"}
                )
                return False

        except Exception as e:
            logger.error(
                "signalr_health_check_failed",
                action="health_check",
                **{"error.code": "NET", "error.message": str(e)},
                exc_info=True
            )
            return False

    def close(self):
        """Close the session"""
        if hasattr(self, 'session'):
            self.session.close()
            logger.debug("signalr_client_session_closed", action="close")
