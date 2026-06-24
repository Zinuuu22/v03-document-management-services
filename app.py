import os
import time
import warnings
import uuid
import json
import threading
from flask import Flask, Response, request
from flask_cors import CORS
import structlog
import elasticapm
from elasticapm.contrib.flask import ElasticAPM
from structlog.contextvars import bind_contextvars, clear_contextvars

# Import các công cụ logging mới
from constants import AppConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

warnings.simplefilter("ignore", ResourceWarning)

apm = ElasticAPM()

# --- PHẦN 2: THIẾT LẬP TIMEZONE ---
if os.name == "nt":
    # Lưu ý: tzutil cần quyền Admin, trong docker/linux thường dùng TZ env
    pass 
else:
    os.environ['TZ'] = 'UTC'
    if hasattr(time, 'tzset'):
        time.tzset()

class App(Flask):
    pass

# ----------------------------
# Application Factory Function
# ----------------------------
def setup_request_hooks(app):
    # ĐĂNG KÝ MIDDLEWARE (LOGGING HOOKS) ---    
    def sanitize_body(body):
        """Lọc bỏ các trường nhạy cảm trước khi log."""
        if not isinstance(body, dict):
            return body
        
        # Danh sách các key nhạy cảm cần ẩn
        sensitive_keys = {'password', 'token', 'secret', 'authorization', 'access_token'}
        
        # Tạo bản sao để tránh làm hỏng dữ liệu gốc của request
        sanitized = body.copy()
        for key in sensitive_keys:
            if key in sanitized:
                sanitized[key] = "********"
        return sanitized

    @app.before_request
    def start_trace():
        clear_contextvars()
            
        # Ưu tiên lấy Trace ID từ APM để đồng bộ hóa (Log-to-Trace correlation)
        # Nếu APM chưa kịp khởi tạo, fallback về header hoặc uuid
        transaction_id = elasticapm.get_transaction_id()
        trace_id = elasticapm.get_trace_id() or request.headers.get('X-Trace-Id', str(uuid.uuid4()))
        
        start_time = time.perf_counter()
        
        # Thu thập Request Body
        request_body = None
        if request.is_json:
            # silent=True để tránh crash nếu JSON gửi lên bị lỗi format
            request_body = sanitize_body(request.get_json(silent=True))
        elif request.form:
            request_body = sanitize_body(request.form.to_dict())

        request_id = str(uuid.uuid4())

        bind_contextvars(
            **{
                "trace.id": trace_id,
                "request.id": request_id,
                "transaction.id": transaction_id, # Thêm cái này cho chuẩn ECS
                "service.name": AppConfig.APP_NAME,
                "event.start": start_time
            }
        )
        
        # Log Ingress kèm theo Body
        logger.info("api_request_received", **{"url.path": request.path, "http.request.method": request.method, "client.ip": request.remote_addr, "http.request.body": request_body})

    @app.after_request
    def end_trace(response):
        ctx = structlog.contextvars.get_contextvars()
        start_time = ctx.get("event.start")
        
        duration_ms = 0
        if start_time:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            
        # Log Egress (Chuẩn ECS)
        logger.info("api_request_completed", **{"http.response.status_code": response.status_code, "event.duration_ms": duration_ms})
        return response
    return app


def register_blueprints(app):
    # CHỈ IMPORT VÀ REGISTER, KHÔNG CẤU HÌNH CORS TẠI ĐÂY
    from services.api import bp as service_api_bp
    app.register_blueprint(service_api_bp)


def create_app(test_config=None) -> Flask:
    app = App(__name__)

    app.config['ELASTIC_APM'] = {
        # Lấy từ ENV "ELASTIC_APM_SERVICE_NAME", nếu không có thì lấy AppConfig.APP_NAME
        'SERVICE_NAME': os.getenv('ELASTIC_APM_SERVICE_NAME', AppConfig.APP_NAME),
        'SERVER_URL': os.getenv('ELASTIC_APM_SERVER_URL', 'http://192.168.1.200:8200'),
        'ENVIRONMENT': os.getenv('ELASTIC_APM_ENVIRONMENT', 'testing'),
        'SECRET_TOKEN': os.getenv('ELASTIC_APM_SECRET_TOKEN', 'AAEAAWVsYXN0aWMvZmxlZXQtc2VydmVyL3Rva2VuLTE3Njk1MDQ0MDA1NDQ6U2J3UUtYeTNUeGliRUxvazlMN3BZQQ'),
        'VERIFY_SERVER_CERT': os.getenv('ELASTIC_APM_VERIFY_SERVER_CERT', 'false').lower() == 'true',
        'ENABLED': False,  # ← thêm dòng này
    }        
    apm.init_app(app)

    # 1. Áp dụng CORS cho toàn bộ App thay vì Blueprint
    # Điều này giúp tránh lỗi "after_request" trên Blueprint
    CORS(app, 
         resources={r"/*": {"origins": "*"}}, # Bạn có thể thu hẹp origin sau
         allow_headers=['Content-Type', 'Authorization', 'X-App-Code', 'X-Trace-Id'],
         methods=['GET', 'PUT', 'POST', 'DELETE', 'OPTIONS', 'PATCH']
    )

    if test_config:
        app.config.from_object(test_config)
    
    # Đăng ký Blueprints (chỉ làm nhiệm vụ route)
    register_blueprints(app)
    
    # Đăng ký các Hook Logging (after_request, before_request) vào APP
    setup_request_hooks(app)
    return app

# Khởi tạo app
app = create_app()

# --- CÁC ROUTE HỆ THỐNG ---
@app.route('/health')
def health():
    logger.info("health_check_ping")
    return Response(json.dumps({
        'status': 'ok',
        'version': app.config.get('CURRENT_VERSION', '1.0.0')
    }), status=200, content_type="application/json")


@app.route('/threads')
def threads():
    num_threads = threading.active_count()
    # ... logic lấy thread list của bạn giữ nguyên ...
    logger.info("threads_diagnostic_called", thread_count=num_threads)
    return {"thread_num": num_threads}

@app.route('/debug-error')
def debug_error():
    1 / 0  # Gây lỗi ZeroDivisionError

if __name__ == '__main__':
    from constants import AppConfig
    app.run(host=AppConfig.API_SERVICE_HOST, 
            port=AppConfig.API_SERVICE_PORT, 
            debug=False)