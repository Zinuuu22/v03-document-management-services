from uuid import UUID
from decimal import Decimal
from datetime import datetime
try:
    from bson import ObjectId  # type: ignore
except Exception:
    ObjectId = None

def _serial_data(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if ObjectId is not None and isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _serial_data(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serial_data(v) for v in obj]
    return obj
    

def make_response(data=None, code=0, message="Success"):
    """
    Chuẩn hóa response API
    Args:
        data: Dữ liệu trả về (dict, list, ...)
        code: Mã code (0: thành công, khác 0: lỗi)
        message: Thông điệp mô tả
    Returns:
        dict: response chuẩn
    """
    return {
        "code": code,
        "message": message,
        "data": _serial_data(data)
    }
