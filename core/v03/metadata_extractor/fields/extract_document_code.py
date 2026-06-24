import re
import unicodedata
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.v03.metadata_extractor.utils import get_brief_content
from core.v03.metadata_extractor.utils.regex_pattern import REGEX_PATTERN_DOCUMENT_CODE


def __clean_document_code(raw_code: str) -> str:
    """Xử lý hậu kỳ mã văn bản để loại bỏ các phần không cần thiết."""
    # Cắt bỏ phần ngày/hồi/trích yếu phía sau mã. Dùng regex không phân biệt hoa
    # thường để chịu được lỗi OCR như 'NGàY' (vốn không khớp 'Ngày'/'NGÀY').
    raw_code = re.split(r"\bNgày\b|\bHồi\b|\bCủa\b|V/v", raw_code, maxsplit=1, flags=re.IGNORECASE)[0]
    for sep in [',', '   ', '|']:
        if sep in raw_code:
            raw_code = raw_code.split(sep)[0]
    # Bỏ khoảng trắng quanh '/', '-', '(', ')' (lỗi OCR như '1999/ TTLT' hay
    # 'BNV (C17)'). Giữ nguyên ngoặc vì đôi khi là một phần của mã (vd '(C17)').
    raw_code = re.sub(r"\s*([/()-])\s*", r"\1", raw_code)
    # Mã văn bản không chứa khoảng trắng: lấy token đầu để cắt bỏ phần mô tả phía
    # sau (vd 'thông qua', tên cơ quan...) mà các bộ tách phía trên bỏ sót.
    tokens = raw_code.split()
    code = tokens[0] if tokens else ""
    # Bỏ ')' thừa ở cuối khi mã không có '(' (vd mã nằm trong '(số ...)'),
    # nhưng giữ ngoặc cân bằng là một phần của mã (vd '08/TT-BNV(C17)').
    if "(" not in code:
        code = code.rstrip(")")
    return code


def extract_document_code(description: str) -> str:
    """
        Trích xuất mã văn bản từ mô tả.
    """
    if not isinstance(description, str) or not description.strip():
        return ""

    # Lấy nội dung rút gọn và chuẩn hóa
    normalized_content = get_brief_content(description, max_length=300)

    # Nối lại mã bị xuống dòng giữa chừng: dòng kết thúc bằng '-' hoặc '/' là
    # phần mã còn tiếp ở dòng sau (vd 'TTLT-BTP-BCA-BQP-\nBTC-VKSNDTC-TANDTC').
    # Nuốt luôn phần thụt đầu dòng kế tiếp để không sót khoảng trắng giữa mã.
    normalized_content = re.sub(r"([/-])\n[ \t]*", r"\1", normalized_content)

    # Tìm kiếm theo regex
    pattern = REGEX_PATTERN_DOCUMENT_CODE["DOCUMENT_CODE_REGEX"]["pattern"]
    match = re.search(pattern, normalized_content, re.IGNORECASE)

    if not match:
        return ""

    raw_code = match.group(1).strip()
    return __clean_document_code(raw_code)


if __name__ == "__main__":
    txt = """
BỘ CÔNG AN - VIỆN KIỂM SÁT NHÂN DÂN TỐI CAO - TÒA ÁN NHÂN DÂN TỐI CAO
-------

CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
---------------

Số: 03/2025/TTLT-BCA-VKSNDTC-TANDTC

Hà Nội, ngày 01 tháng 3 năm 2025


THÔNG TƯ LIÊN TỊCH

QUY ĐỊNH VỀ XỬ LÝ MỘT SỐ VẤN ĐỀ LIÊN QUAN ĐẾN ÁP DỤNG CÁC BIỆN PHÁP XỬ LÝ HÀNH CHÍNH ĐƯA VÀO TRƯỜNG GIÁO DƯỠNG, CƠ SỞ GIÁO DỤC BẮT BUỘC, CƠ SỞ CAI NGHIỆN BẮT BUỘC VÀ BIỆN PHÁP ĐƯA VÀO CƠ SỞ CAI NGHIỆN BẮT BUỘC ĐỐI VỚI NGƯỜI NGHIỆN MA TÚY TỪ ĐỦ 12 TUỔI ĐẾN DƯỚI 18 TUỔI KHI SẮP XẾP TỔ CHỨC BỘ MÁY NHÀ NƯỚC

Căn cứ Nghị quyết số 190/2025/QH15 ngày 19 tháng 02 năm 2025 của Quốc hội quy định về xử lý một số vấn đề liên quan đến sắp xếp tổ chức bộ máy nhà nước;

Bộ trưởng Bộ Công an, Viện trưởng Viện kiểm sát nhân dân tối cao, Chánh án Tòa án nhân dân tối cao ban hành Thông tư liên tịch quy định về xử lý một số vấn đề liên quan đến áp dụng các biện pháp xử lý hành chính đưa vào trường giáo dưỡng, cơ sở giáo dục bắt buộc, cơ sở cai nghiện bắt buộc và biện pháp đưa vào cơ sở cai nghiện bắt buộc đối với người nghiện ma túy từ đủ 12 tuổi đến dưới 18 tuổi khi sắp xếp tổ chức bộ máy nhà nước.

Điều 1. Phạm vi điều chỉnh, đối tượng áp dụng

1. Phạm vi điều chỉnh

Thông tư liên tịch này quy định về xử lý một số vấn đề liên quan đến áp dụng các biện pháp xử lý hành chính đưa vào trường giáo dưỡng, cơ sở giáo dục bắt buộc, cơ sở cai nghiện bắt buộc và biện pháp đưa vào cơ sở cai nghiện bắt buộc đối với người nghiện ma túy từ đủ 12 tuổi đến dưới 18 tuổi khi không tổ chức Công an cấp huyện và tiếp nhận nhiệm vụ quản lý nhà nước về cai nghiện ma túy, quản lý sau cai nghiện ma túy về Bộ Công an.
    """
    logger.info("extract_result", result=extract_document_code(txt))
