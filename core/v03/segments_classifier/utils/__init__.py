from typing import Dict, Union

ClassifyResponse = {
        "Phạm Vi Điều Chỉnh": False,
        "Giải Thích Thuật Ngữ": False,
        "Hiệu Lực và Quy Định Chuyển Tiếp": False,
        "Ngoại Lệ/Miễn Trừ": False,
        "Chế Tài": False,
        "Nguyên Tắc Cơ Bản": False,
        "Quy Định Hành Vi": False,
        "Thẩm Quyền": False,
        "Quyền Lợi và Nghĩa Vụ": False,
        "Thủ Tục/Quy Trình": False,
        "Điều Kiện/Tiêu Chuẩn": False,
        "Chi Phí/Lệ Phí": False,
    }


def convert_string_to_bool(value: Union[str, bool]) -> bool:
    """Convert a string or boolean value to a boolean."""
    if isinstance(value, bool):
        return value
    try:
        return value.lower() != "false"
    except AttributeError:
        return True


def is_pham_vi_ap_dung(content: str) -> bool:
    """Check if the legal text relates to 'Phạm vi điều chỉnh' or similar terms."""
    keywords = ["Phạm vi điều chỉnh", "Phạm vi áp dụng", "Đối tượng áp dụng"]
    return any(keyword in content for keyword in keywords)