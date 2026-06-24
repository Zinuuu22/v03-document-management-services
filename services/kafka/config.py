"""
Global Kafka Configuration
Centralized configuration for all Kafka services
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class KafkaConfig:
    """Kafka connection configuration"""
    BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    API_VERSION: tuple = (0, 11, 5)
    MAX_PARTITION_FETCH_BYTES: int = 104857600  # 100MB
    AUTO_OFFSET_RESET: str = "latest"
    MAX_POLL_INTERVAL_MS: int = 9000000  # 2.5 hours
    ENABLE_AUTO_COMMIT: bool = False
    SESSION_TIMEOUT_MS: int = 30000
    HEARTBEAT_INTERVAL_MS: int = 3000
    MAX_POLL_RECORDS: int = 100


@dataclass
class ConsumerConfig:
    """Consumer-specific configuration"""
    GROUP_ID_SUFFIX: str = "_group"
    CONSUMER_TIMEOUT_MS: int = 1000
    FETCH_MIN_BYTES: int = 1
    FETCH_MAX_WAIT_MS: int = 500


@dataclass
class WorkerConfig:
    """Worker pool configuration"""
    MAX_WORKERS: int = int(os.getenv("KAFKA_MAX_WORKERS", "10"))
    THREAD_POOL_SIZE: int = int(os.getenv("KAFKA_THREAD_POOL_SIZE", "20"))
    GRACEFUL_SHUTDOWN_TIMEOUT: int = 30  # seconds


@dataclass
class TopicConfig:
    """Topic-specific configurations"""
    
    # Extraction topics
    EXTRACT_METADATA_TOPIC: str = "extract_metadata_query"
    EXTRACT_KEYWORDS_TOPIC: str = "extract_keywords_query"
    EXTRACT_LAW_AUTHORITY_TOPIC: str = "extract_law_authority_query"
    EXTRACT_REGULATED_ENTITIES_TOPIC: str = "extract_regulated_entities_query"
    EXTRACT_REGULATED_OBJECT_TOPIC: str = "extract_regulated_object_query"
    EXTRACT_RELATIONSHIP_TOPIC: str = "extract_relationship_query"
    EXTRACT_RELATIONSHIP_ARTICLE_TOPIC: str = "extract_relationship_article_query"
    EXTRACT_SOCIAL_RELATION_TOPIC: str = "extract_social_relation_query"
    
    # Tree topics
    IMPORT_TREE_TOPIC: str = "import_tree_query"
    TREE_CLASSIFIER_TOPIC: str = "tree_classifier_query"
    
    # Response topics
    EXTRACT_METADATA_RESPONSE_TOPIC: str = "extract_metadata_response"
    EXTRACT_KEYWORDS_RESPONSE_TOPIC: str = "extract_keywords_response"
    EXTRACT_LAW_AUTHORITY_RESPONSE_TOPIC: str = "extract_law_authority_response"
    EXTRACT_REGULATED_ENTITIES_RESPONSE_TOPIC: str = "extract_regulated_entities_response"
    EXTRACT_REGULATED_OBJECT_RESPONSE_TOPIC: str = "extract_regulated_object_response"
    EXTRACT_RELATIONSHIP_RESPONSE_TOPIC: str = "extract_relationship_response"
    EXTRACT_RELATIONSHIP_ARTICLE_RESPONSE_TOPIC: str = "extract_relationship_article_response"
    EXTRACT_SOCIAL_RELATION_RESPONSE_TOPIC: str = "extract_social_relation_response"
    IMPORT_TREE_RESPONSE_TOPIC: str = "import_tree_response"
    TREE_CLASSIFIER_RESPONSE_TOPIC: str = "tree_classifier_response"


@dataclass
class HandlerConfig:
    """Handler-specific configurations"""
    
    # Worker counts per handler
    EXTRACT_METADATA_WORKERS: int = int(os.getenv("EXTRACT_METADATA_WORKERS", "2"))
    EXTRACT_KEYWORDS_WORKERS: int = int(os.getenv("EXTRACT_KEYWORDS_WORKERS", "2"))
    EXTRACT_LAW_AUTHORITY_WORKERS: int = int(os.getenv("EXTRACT_LAW_AUTHORITY_WORKERS", "2"))
    EXTRACT_REGULATED_ENTITIES_WORKERS: int = int(os.getenv("EXTRACT_REGULATED_ENTITIES_WORKERS", "2"))
    EXTRACT_REGULATED_OBJECT_WORKERS: int = int(os.getenv("EXTRACT_REGULATED_OBJECT_WORKERS", "2"))
    EXTRACT_RELATIONSHIP_WORKERS: int = int(os.getenv("EXTRACT_RELATIONSHIP_WORKERS", "2"))
    EXTRACT_RELATIONSHIP_ARTICLE_WORKERS: int = int(os.getenv("EXTRACT_RELATIONSHIP_ARTICLE_WORKERS", "2"))
    EXTRACT_SOCIAL_RELATION_WORKERS: int = int(os.getenv("EXTRACT_SOCIAL_RELATION_WORKERS", "2"))
    IMPORT_TREE_WORKERS: int = int(os.getenv("IMPORT_TREE_WORKERS", "2"))
    TREE_CLASSIFIER_WORKERS: int = int(os.getenv("TREE_CLASSIFIER_WORKERS", "2"))
    
    # Retry configurations
    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_DELAY_SECONDS: int = 5
    
    # Timeout configurations
    HANDLER_TIMEOUT_SECONDS: int = 300  # 5 minutes
    LONG_RUNNING_HANDLER_TIMEOUT_SECONDS: int = 1800  # 30 minutes


@dataclass
class EnvironmentConfig:
    """Environment-specific configuration"""
    ENV: str = os.getenv("ENV", "development")


class ConfigManager:
    """Central configuration manager"""
    
    def __init__(self):
        self.kafka = KafkaConfig()
        self.consumer = ConsumerConfig()
        self.worker = WorkerConfig()
        self.topics = TopicConfig()
        self.handler = HandlerConfig()
        self.env = EnvironmentConfig()
    
    def get_topic_config(self, topic_name: str) -> Dict[str, Any]:
        """Get configuration for a specific topic"""
        topic_attr = topic_name.upper()
        if hasattr(self.topics, topic_attr):
            return {
                "topic": getattr(self.topics, topic_attr),
                "group_id": f"{getattr(self.topics, topic_attr)}{self.consumer.GROUP_ID_SUFFIX}",
                "bootstrap_servers": [self.kafka.BOOTSTRAP_SERVERS],
                "api_version": self.kafka.API_VERSION,
                "max_partition_fetch_bytes": self.kafka.MAX_PARTITION_FETCH_BYTES,
                "auto_offset_reset": self.kafka.AUTO_OFFSET_RESET,
                "max_poll_interval_ms": self.kafka.MAX_POLL_INTERVAL_MS,
                "enable_auto_commit": self.kafka.ENABLE_AUTO_COMMIT,
            }
        raise ValueError(f"Unknown topic: {topic_name}")
    
    def get_handler_worker_count(self, handler_name: str) -> int:
        """Get worker count for a specific handler"""
        worker_attr = f"{handler_name.upper()}_WORKERS"
        if hasattr(self.handler, worker_attr):
            return getattr(self.handler, worker_attr)
        return 2  # Default worker count
    
    def get_all_topics(self) -> Dict[str, str]:
        """Get all topic configurations"""
        return {
            name: getattr(self.topics, name) 
            for name in dir(self.topics) 
            if not name.startswith('_') and isinstance(getattr(self.topics, name), str)
        }


# Global configuration instance
config = ConfigManager()
