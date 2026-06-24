#!/usr/bin/env python3
"""
Kafka Services Entry Point
"""
import structlog
import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

from services.kafka.manager import KafkaServiceManager

logger = structlog.get_logger()

def main():
    manager = KafkaServiceManager(
        name="extractor",
        exclude_handlers=[
            "extract_social_relation.py",
            "extract_law_authority_legacy.py",
        ],
    )
    try:
        manager.start()
    except Exception as e:
        logger.error("start_kafka_services_failed", action="main",
                     **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()