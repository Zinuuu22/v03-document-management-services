#!/usr/bin/env python3
"""
Kafka Services Entry Point
"""

import os
import sys
import signal
import threading
import structlog

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

from logs.logger_conf import setup_logging
from services.kafka.common.client import KafkaClient
from services.kafka.common.consumer_registry import ConsumerRegistry

setup_logging()
logger = structlog.get_logger()


class KafkaServiceManager:

    def __init__(self, name, exclude_handlers=None):
        self._client = KafkaClient()
        self._registry = ConsumerRegistry()
        self._stop_event = threading.Event()
        self._exclude_handlers = exclude_handlers
        self._handlers_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "handlers", name
        )

    def start(self) -> None:
        logger.info("kafka_service_manager_initializing", action="start")

        self._registry.discover_handlers(self._handlers_dir, exclude_files=self._exclude_handlers)

        if not self._registry.get_all_topics():
            logger.error("no_handlers_found", action="start", **{"error.code": "SYS"})
            sys.exit(1)

        logger.info("registered_handlers", action="start", summary=self._registry.summary())

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._client.start_all_consumers(self._registry)
        logger.info("kafka_services_started", action="start")

        # Block main thread cho đến khi nhận stop signal
        self._stop_event.wait()

    def stop(self) -> None:
        logger.info("kafka_services_stopping", action="stop")
        self._client.stop_all_consumers()
        self._stop_event.set()  # Wake up main thread
        logger.info("kafka_services_stopped", action="stop")

    def _signal_handler(self, signum, frame) -> None:
        logger.info("received_shutdown_signal", action="_signal_handler", signal=signum)
        self.stop()