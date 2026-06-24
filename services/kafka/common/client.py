"""
Single Kafka Client
Quản lý toàn bộ consumers, dispatch message đến đúng handler.
"""

import threading
import inspect
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Type

from kafka import KafkaConsumer
from constants import KafkaConfig
from services.kafka.common.consumer_registry import ConsumerRegistry
from services.kafka.common.base_consumer import BaseConsumer
import structlog

logger = structlog.get_logger()


class KafkaClient:

    def __init__(self):
        self._executors: Dict[str, ThreadPoolExecutor] = {}
        self._consumer_threads: list[threading.Thread] = []
        self._running = False

    def start_all_consumers(self, registry: ConsumerRegistry) -> None:
        topics = registry.get_all_topics()

        if not topics:
            logger.warning("start_all_consumers_no_handlers", action="start_all_consumers")
            return

        self._running = True
        logger.info("start_all_consumers_started", action="start_all_consumers", topics=topics)

        for topic in topics:
            handler_class = registry.get_handler_class(topic)
            self._start_consumer_thread(topic, handler_class)

    def _start_consumer_thread(
        self, topic: str, handler_class: Type[BaseConsumer]
    ) -> None:
        """Mỗi topic chạy trên một thread riêng với worker pool riêng."""

        handler = handler_class()
        num_workers = getattr(handler_class, "NUM_WORKERS", 1)
        group_id = getattr(handler_class, "GROUP_ID", f"{topic}_group")

        executor = ThreadPoolExecutor(
            max_workers=num_workers,
            thread_name_prefix=f"worker-{handler.get_handler_name()}",
        )
        self._executors[topic] = executor

        def _consume():
            consumer = KafkaConsumer(
                topic,
                group_id=group_id,
                bootstrap_servers=[KafkaConfig.BOOTSTRAP_SERVERS],
                api_version=(0, 11, 5),
                max_partition_fetch_bytes=104857600,
                auto_offset_reset="latest",
                max_poll_interval_ms=9000000,
                enable_auto_commit=False,
            )
            logger.info("consume_worker_started", action="_start_consumer_thread",
                        topic=topic, group_id=group_id, workers=num_workers)

            def _run_handler(handler_obj, raw_msg):
                result = handler_obj.process_message(raw_msg)
                if inspect.iscoroutine(result):
                    asyncio.run(result)

            for raw_message in consumer:
                consumer.commit()
                if not self._running:
                    break
                executor.submit(_run_handler, handler, raw_message)

            consumer.close()
            logger.info("consume_worker_stopped", action="_start_consumer_thread", topic=topic)

        t = threading.Thread(
            target=_consume,
            name=f"consumer-{handler.get_handler_name()}",
            daemon=True,
        )
        self._consumer_threads.append(t)
        t.start()

    def stop_all_consumers(self) -> None:
        self._running = False
        for topic, executor in self._executors.items():
            executor.shutdown(wait=True)
            logger.debug("stop_consumer_executor_shutdown", action="stop_all_consumers", topic=topic)
        logger.info("stop_all_consumers_success", action="stop_all_consumers")