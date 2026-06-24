import os
import uuid
import time
import structlog
from functools import wraps
from structlog.contextvars import bind_contextvars, clear_contextvars

_LEVEL_MAP = {
    'debug': 10, 'info': 20, 'warning': 30, 'error': 40, 'critical': 50
}

def generate_trace_id():
    """Generates a standard UUID4 string for tracing."""
    return str(uuid.uuid4())

def generate_request_id():
    """Generates a standard UUID4 string for request correlation."""
    return str(uuid.uuid4())

def _normalize_duration(logger, method_name, event_dict):
    duration = None
    if "duration_ms" in event_dict:
        duration = event_dict.pop("duration_ms")
    elif "processing_time" in event_dict:
        duration = event_dict.pop("processing_time")
        
    if duration is not None:
        try:
            if isinstance(duration, str) and duration.endswith("s"):
                duration = float(duration[:-1]) * 1000.0
            else:
                duration = float(duration)
            event_dict["event.duration"] = duration
        except (ValueError, TypeError):
            event_dict["event.duration"] = duration
    return event_dict

def _normalize_status(logger, method_name, event_dict):
    if "status" in event_dict:
        status = event_dict.pop("status")
        if isinstance(status, str):
            status = status.lower()
            if status in ("ok", "success", "true"):
                status = "success"
            elif status in ("error", "fail", "failure", "false"):
                status = "failure"
            else:
                status = status
        event_dict["event.status"] = status
    return event_dict

def _ensure_lowercase_level(logger, method_name, event_dict):
    if "level" in event_dict and isinstance(event_dict["level"], str):
        event_dict["level"] = event_dict["level"].lower()
    return event_dict

# def _soft_schema_validation(logger, method_name, event_dict):
#     skip = event_dict.pop('_skip_schema_validation', False)
#     if skip:
#         return event_dict

#     warnings = []
#     if "trace.id" not in event_dict:
#         warnings.append("missing_trace_id")
#     if "service.name" not in event_dict:
#         warnings.append("missing_service_name")
        
#     if warnings:
#         event_dict["_schema.warning"] = warnings
#     return event_dict

logger = structlog.get_logger()

# --- PHẦN 1: CẤU HÌNH LOGGING CHUẨN ECS ---
def setup_logging():
    min_level_name = os.getenv('LOG_LEVEL', 'DEBUG').lower()
    min_level = _LEVEL_MAP.get(min_level_name, 0)

    def _filter_by_level(logger, method_name, event_dict):
        lvl = event_dict.get("level", method_name)
        if not isinstance(lvl, str):
            lvl = method_name
        current_level = _LEVEL_MAP.get(lvl.lower(), 0)
        if current_level < min_level:
            raise structlog.DropEvent
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _ensure_lowercase_level,
            _filter_by_level,
            _normalize_duration,
            _normalize_status,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="iso", key="@timestamp"),
            structlog.processors.JSONRenderer(
                ensure_ascii=False, # Để hiển thị tiếng Việt trực tiếp
                sort_keys=True      # Giúp log dễ đọc hơn khi debug
            )
        ],
        logger_factory=structlog.PrintLoggerFactory(), # In ra stdout
        cache_logger_on_first_use=True,
    )

# --- PHẦN 2: CẤU HÌNH LOGGING CHUẨN KÀFKA ---
class KafkaTraceTool:
    @staticmethod
    def get_headers():
        """Helper cho Producer: Lấy trace.id hiện tại để gửi đi."""
        ctx = structlog.contextvars.get_contextvars()
        trace_id = ctx.get("trace.id")
        if not trace_id:
            trace_id = generate_trace_id()
            logger.warning(
                "send_kafka_headers_trace_id_missing",
                action="get_headers",
                **{"trace.id": trace_id},
            )

        request_id = ctx.get("request.id")
        if not request_id:
            request_id = generate_request_id()
            logger.warning(
                "send_kafka_headers_request_id_missing",
                action="get_headers",
                **{"request.id": request_id},
            )

        # Trả về format chuẩn của kafka-python
        return [
            ('trace.id', trace_id.encode('utf-8')),
            ('request.id', request_id.encode('utf-8')),
            ('event.start_time', str(time.time()).encode('utf-8'))
        ]

    @staticmethod
    def trace_consumer(service_name):
        """Decorator cho Consumer: Tự động trích xuất trace.id từ message."""
        def decorator(func):
            @wraps(func)
            def wrapper(msg, *args, **kwargs):
                # 1. Dọn dẹp túi cũ
                clear_contextvars()
                
                # 2. Trích xuất Headers (Format của kafka-python là list of tuples)
                raw_headers = dict(msg.headers) if msg.headers else {}
                
                trace_id_bytes = raw_headers.get('trace.id')
                if trace_id_bytes:
                    trace_id = trace_id_bytes.decode('utf-8')
                else:
                    trace_id = generate_trace_id()
                    
                request_id_bytes = raw_headers.get('request.id')
                if request_id_bytes:
                    request_id = request_id_bytes.decode('utf-8')
                else:
                    request_id = generate_request_id()
                
                # 3. Dán nhãn xuyên suốt
                bind_contextvars(
                    **{
                        "trace.id": trace_id,
                        "request.id": request_id,
                        "service.name": service_name,
                        "messaging.kafka.topic": msg.topic,
                        "messaging.kafka.partition": msg.partition,
                        "messaging.kafka.offset": msg.offset
                    }
                )
                
                # 4. log "message received"
                logger.info("kafka_message_received", action=func.__name__)
                
                start_time = time.perf_counter()
                
                try:
                    # 5. process
                    result = func(msg, *args, **kwargs)
                    
                    # 6. log success
                    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    logger.info("kafka_message_processed", action=func.__name__, duration_ms=duration_ms, status="success")
                    return result
                except Exception as e:
                    # log failure
                    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    logger.error("kafka_message_failed", 
                                 action=func.__name__,
                                 **{"error.code": "KAF", "error.message": str(e)}, 
                                 duration_ms=duration_ms, 
                                 status="failure", 
                                 exc_info=True)
                    raise e
            return wrapper
        return decorator
