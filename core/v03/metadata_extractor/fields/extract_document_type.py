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
from core.v03.metadata_extractor.utils.regex_pattern import REGEX_PATTERN_DOCUMENT_TYPE, DOCUMENT_CODE_TO_TYPE_MAPPING
from core.v03.metadata_extractor.utils import normalize_type


def extract_document_type(content: str, document_code: str) -> str:
    '''
        Trích xuất loại văn bản từ nội dung và mã văn bản.
    '''

    brief_content = get_brief_content(content)
    logger.debug("process_brief_content", action="extract_document_type", preview=brief_content[:100])

    # 1. Thử trích xuất document_type từ document_code
    document_type = ""
    document_code = document_code.lower().replace(" ", "")
    for pattern, info in DOCUMENT_CODE_TO_TYPE_MAPPING.items():
        if pattern in document_code:
            document_type = info["document_type"]
            logger.debug("document_type_from_code", action="extract_document_type", document_code=document_code, document_type=document_type)
            break

    # 2. Nếu không tìm thấy từ document_code, tìm trong nội dung
    if not document_type:
        # Kiểm tra kiểu dữ liệu của REGEX_PATTERN_DOCUMENT_TYPE
        if not isinstance(REGEX_PATTERN_DOCUMENT_TYPE, dict):
            logger.error("invalid_regex_pattern_type", action="extract_document_type", **{"error.code": "VAL", "error.message": "REGEX_PATTERN_DOCUMENT_TYPE is not a dict"}, pattern_type=str(type(REGEX_PATTERN_DOCUMENT_TYPE)))
            return document_type

        try:
            pattern = REGEX_PATTERN_DOCUMENT_TYPE["DOCUMENT_TYPE_REGEX"]["pattern"]
        except (KeyError, TypeError) as e:
            logger.error("regex_pattern_access_failed", action="extract_document_type", **{"error.code": "VAL", "error.message": str(e)}, exc_info=True)
            return document_type

        matches = list(re.finditer(pattern, "\n" + brief_content))
        if matches:
            first_match = min(matches, key=lambda m: m.start())
            document_type = first_match.group(1)
            logger.debug("document_type_from_content", action="extract_document_type", document_type=document_type)

    # Chuẩn hóa document_type
    document_type = normalize_type(document_type)
    return document_type


if __name__ == "__main__":
    txt = """
BỘ CÔNG THƯƠNG
-------
CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
---------------

Số: 2755/CĐ-BCT

Hà Nội, ngày 18 tháng 4 năm 2025

CÔNG ĐIỆN

VỀ VIỆC TĂNG CƯỜNG CÔNG TÁC GIÁM SÁT, KIỂM TRA, KIỂM SOÁT THỊ TRƯỜNG

BỘ TRƯỞNG BỘ CÔNG THƯƠNG,
PHÓ TRƯỞNG BAN CHỈ ĐẠO 389 QUỐC GIA điện:

- Ủy ban nhân dân các tỉnh, thành phố
- Cục Quản lý và Phát triển thị trường trong nước
- Sở Công Thương các tỉnh, thành phố

Trong thời gian qua, Chính phủ, các Bộ ngành đã ban hành nhiều văn bản chỉ đạo, đôn đốc về công tác phòng, chống, xử lý các hành vi sản xuất, buôn bán hàng giả, hàng cấm, hàng hóa không rõ nguồn gốc xuất xứ; hành vi xâm phạm quyền sở hữu trí tuệ; hành vi vi phạm pháp luật về chất lượng, đo lường, an toàn thực phẩm; hành vi vi phạm pháp luật về bảo vệ quyền lợi người tiêu dùng và các hành vi gian lận thương mại theo quy định pháp luật khác. Tuy nhiên, thời gian gần đây lực lượng chức năng liên tiếp kiểm tra, phát hiện một số doanh nghiệp, tổ chức, cá nhân sản xuất, quảng cáo, phân phối nhiều loại sữa giả; thuốc giả, thực phẩm bảo vệ sức khỏe giả tại một số địa phương. Đáng lưu ý là hoạt động sản xuất, buôn bán các loại hàng giả này đã kéo dài nhiều năm gây ảnh hưởng trực tiếp đến sức khỏe, tính mạng của người dân. Nhằm tăng cường trách nhiệm của các cơ quan liên quan trong việc quản lý, giám sát, kịp thời phát hiện, ngăn chặn và xử lý các hoạt động sản xuất, buôn bán hàng giả, đặc biệt là sản phẩm sữa, thuốc giả, thực phẩm bảo vệ sức khỏe giả, Bộ trưởng Bộ Công Thương, Phó trưởng Ban chỉ đạo 389 quốc gia yêu cầu:

1. Ủy ban nhân dân các tỉnh, thành phố

    """ 
    logger.info("extract_result", result=extract_document_type(txt, '2755/CĐ-BCT'))