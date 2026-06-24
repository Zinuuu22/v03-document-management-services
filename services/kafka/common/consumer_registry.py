"""
Consumer Registry
Auto-discovers and manages all consumer handlers
"""

import os
import importlib
import inspect
from typing import Dict, List, Type, Optional
from .base_consumer import BaseConsumer
import structlog

logger = structlog.get_logger()


class ConsumerRegistry:
    """
    Registry for managing all consumer handlers.

    Mapping: topic (str) -> consumer_class (Type[BaseConsumer])
    Mỗi handler tự khai báo topic của nó qua class attribute TOPIC.

    Caller tự truyền vào đúng handlers_dir cần scan, ví dụ:
        registry.discover_handlers(".../handlers/extractor")
        registry.discover_handlers(".../handlers/tree_processor")
    """

    def __init__(self):
        # key: topic string, value: consumer class
        self._topic_map: Dict[str, Type[BaseConsumer]] = {}
        # key: dotted module path, value: module object (để reload)
        self._modules: Dict[str, any] = {}

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_handlers(self, handlers_dir: str, exclude_files: Optional[List[str]] = None) -> None:
        """
        Scan tất cả .py files trong handlers_dir và đăng ký consumer classes.

        handlers_dir phải là đường dẫn tuyệt đối đến thư mục chứa handler files,
        ví dụ: .../handlers/extractor  hoặc  .../handlers/tree_processor
        """
        logger.debug("discover_handlers_started", action="discover_handlers", path=handlers_dir,
                    exists=os.path.exists(handlers_dir))

        if not os.path.exists(handlers_dir):
            logger.error("discover_handlers_directory_not_found", action="discover_handlers",
                         **{"error.code": "CFG", "error.message": f"Handlers directory not found: {handlers_dir}"},
                         path=handlers_dir)
            return

        excluded = set(exclude_files or [])

        handler_files = [
            f[:-3]
            for f in os.listdir(handlers_dir)
            if f.endswith(".py") and f != "__init__.py" and f not in excluded
        ]

        if excluded:
            logger.info("discover_handlers_files_excluded", action="discover_handlers",
                        excluded=sorted(excluded))

        logger.debug("discover_handlers_files_found", action="discover_handlers", files=handler_files)

        package_prefix = self._resolve_package_prefix(handlers_dir)

        for name in handler_files:
            module_path = f"{package_prefix}.{name}"
            try:
                self._load_module(module_path)
            except Exception as e:
                logger.error("load_handler_failed", action="discover_handlers",
                             **{"error.code": "LOAD", "error.message": str(e)},
                             module=module_path, exc_info=True)

    @staticmethod
    def _resolve_package_prefix(handlers_dir: str) -> str:
        """
        Chuyển đường dẫn tuyệt đối thành dotted package path tương đối với sys.path.

        Ví dụ:
            /project/services/kafka/handlers/extractor
            → "handlers.extractor"   (nếu /project/services/kafka có trong sys.path)
        """
        import sys

        handlers_dir = os.path.normpath(handlers_dir)

        for base in sorted(sys.path, key=len, reverse=True):
            base = os.path.normpath(base)
            if handlers_dir.startswith(base + os.sep):
                relative = handlers_dir[len(base) + 1:]
                return relative.replace(os.sep, ".")

        # Fallback: dùng 2 phần cuối của path
        parts = handlers_dir.replace("\\", "/").rstrip("/").split("/")
        return ".".join(parts[-2:])

    def _load_module(self, module_path: str) -> None:
        """Import module theo dotted path và đăng ký consumer class tìm được."""
        module = importlib.import_module(module_path)

        for _, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, BaseConsumer)
                and cls is not BaseConsumer
                and cls.__module__ == module_path
            ):
                self._register_class(cls, module_path, module)
                break  # one consumer per module

    def _register_class(self, cls: Type[BaseConsumer], module_path: str, module) -> None:
        """Đăng ký class vào topic_map, validate TOPIC trước."""
        topic: str = getattr(cls, "TOPIC", None)

        if not topic:
            raise ValueError(
                f"Handler '{cls.__name__}' in module '{module_path}' "
                f"phải định nghĩa class attribute TOPIC."
            )

        if topic in self._topic_map:
            existing = self._topic_map[topic].__name__
            raise ValueError(
                f"Topic '{topic}' đã được đăng ký bởi '{existing}'. "
                f"Không thể đăng ký thêm '{cls.__name__}'."
            )

        self._topic_map[topic] = cls
        self._modules[module_path] = module

        logger.info("register_handler_success", action="_register_class", topic=topic,
                    class_name=cls.__name__, module=module_path)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_handler_class(self, topic: str) -> Type[BaseConsumer]:
        if topic not in self._topic_map:
            raise KeyError(f"No handler registered for topic: '{topic}'")
        return self._topic_map[topic]

    def get_all_topics(self) -> List[str]:
        """Trả về danh sách tất cả topics đã đăng ký — dùng để subscribe."""
        return list(self._topic_map.keys())

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reload_handler(self, module_path: str) -> None:
        """
        Hot-reload một handler module.
        module_path là dotted path, ví dụ: "handlers.extractor.extract_metadata"
        """
        if module_path not in self._modules:
            logger.warning("reload_handler_not_found", action="reload_handler",
                           **{"error.code": "CFG", "error.message": "Module not registered, cannot reload"},
                           module=module_path)
            return

        # Xoá topic cũ thuộc module này
        stale_topics = [
            topic
            for topic, cls in self._topic_map.items()
            if cls.__module__ == module_path
        ]
        for topic in stale_topics:
            del self._topic_map[topic]

        try:
            importlib.reload(self._modules[module_path])
            self._load_module(module_path)
            logger.info("reload_handler_success", action="reload_handler", module=module_path)
        except Exception as e:
            logger.error("reload_handler_failed", action="reload_handler",
                         **{"error.code": "LOAD", "error.message": str(e)},
                         module=module_path, exc_info=True)

    # ------------------------------------------------------------------
    # Introspection (không tạo instance)
    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, str]:
        """Trả về {topic: class_name} — dùng để log/debug, không tạo instance."""
        return {
            topic: cls.__name__
            for topic, cls in self._topic_map.items()
        }

    def validate(self) -> Dict[str, bool]:
        """Kiểm tra các handler có implement đủ required methods không."""
        required = {"process_message", "get_handler_name"}
        results = {}

        for topic, cls in self._topic_map.items():
            missing = [m for m in required if not callable(getattr(cls, m, None))]
            results[topic] = not missing

            if missing:
                logger.warning("validate_handler_methods_missing", action="validate",
                               topic=topic, missing=missing)

        return results