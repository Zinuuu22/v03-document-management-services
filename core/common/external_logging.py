import time
import structlog

logger = structlog.get_logger()

def execute_external_with_logging(
    func, 
    action, 
    service_name, 
    operation, 
    error_classifier, 
    meta=None, 
    error_code="UNKNOWN", 
    slow_threshold_ms=1000
):
    """
    Generic wrapper for external dependency calls that enforces standard observability fields.
    
    Args:
        func: The external operation to execute.
        action: The logical action name (e.g. the calling function name).
        service_name: Name of the external service (e.g. 'elasticsearch', 'mongo', 'minio').
        operation: The specific external operation being performed (e.g. 'search_documents').
        error_classifier: Callable that takes an exception and returns a taxonomy string (e.g. 'network').
        meta: Optional dict with external operation metadata.
        error_code: The domain-specific error code to use on failure.
        slow_threshold_ms: Threshold in milliseconds before logging performance.slow_call=True.
    """
    start_time = time.perf_counter()
    if meta is None:
        meta = {}
        
    try:
        result = func()
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        kwargs = {
            "external.service.name": service_name,
            "external.operation": operation,
            "event.duration": duration_ms,
            "event.status": "success",
            "external.meta": meta
        }
        
        if duration_ms > slow_threshold_ms:
            kwargs["performance.slow_call"] = True
            
        logger.info(f"{operation}_{service_name}_success", action=action, **kwargs)
        return result
        
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        
        err_type = "unknown"
        if callable(error_classifier):
            try:
                err_type = error_classifier(e)
            except Exception:
                pass

        kwargs = {
            "external.service.name": service_name,
            "external.operation": operation,
            "event.duration": duration_ms,
            "event.status": "failure",
            "error.code": error_code,
            "error.message": str(e),
            "error.type": err_type,
            "external.meta": meta
        }
        logger.error(f"{operation}_{service_name}_failed", action=action, exc_info=True, **kwargs)
        raise e
