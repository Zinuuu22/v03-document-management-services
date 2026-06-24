import re
from datetime import datetime, timedelta
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.v03.metadata_extractor.utils.regex_pattern import REGEX_PATTERNS_EFFECTIVE_DATE
from core.v03.metadata_extractor.fields.extract_effective_date import extract_effective_date


def extract_effective_status(content, issue_date):
    result = {
        "effective_status": "Còn hiệu lực",
        "method": ""
    }

    try:
        if isinstance(issue_date, dict):
            issue_date = issue_date.get("issue_date") or ""

        date_result = extract_effective_date(content, issue_date)

        effective_date_val = date_result.get("effective_date", "") if isinstance(date_result, dict) else ""

        if not isinstance(effective_date_val, str):
            effective_date_val = ""

        if not effective_date_val.strip():
            result["effective_status"] = "Không xác định"
            result["method"] = "Không xác định được ngày có hiệu lực"
        else:
            eff_date = datetime.strptime(effective_date_val, "%d/%m/%Y")
            if eff_date > datetime.now():
                result["effective_status"] = "Không xác định"
                result["method"] = "Ngày có hiệu lực sau ngày hiện tại"

    except Exception as e:
        logger.error("parse_effective_date_error", action="extract_effective_status", error=str(e))
        result["effective_status"] = "Không xác định"
        result["method"] = f"exception: {e}"

    return result


if __name__ == "__main__":
    from core.common.elastic import ElasticSearcher

    # elastic_searcher = ElasticSearcher()
    doc_id = "e749cbd4-aa4a-4a6a-899b-2cd050788c22"
    doc_content = """
    ỦY BAN NHÂN DÂN
TỈNH QUẢNG BÌNH
------- | CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc 
---------------

Số: 3218/QĐ-UBND | Quảng Bình, ngày 18 tháng 11 năm 2024

QUYẾT ĐỊNH

VỀ VIỆC CÔNG BỐ DANH MỤC THỦ TỤC HÀNH CHÍNH BAN HÀNH MỚI TRONG LĨNH VỰC CHĂN NUÔI THUỘC THẨM QUYỀN GIẢI QUYẾT CỦA UBND CẤP HUYỆN

CHỦ TỊCH ỦY BAN NHÂN DÂN TỈNH QUẢNG BÌNH

Căn cứ Luật Tổ chức chính quyền địa phương ngày 19/6/2015; Luật sửa đổi một số điều của Luật Tổ chức Chính phủ và Luật Tổ chức chính quyền địa phương ngày 22/11/2019;

Căn cứ Nghị định số 63/2010/NĐ-CP ngày 08/6/2010 của Chính phủ về kiểm soát thủ tục hành chính; Nghị định số 92/2017/NĐ-CP ngày 07/8/2017 của Chính phủ sửa đổi, bổ sung một số điều của các Nghị định liên quan đến kiểm soát thủ tục hành chính;

Căn cứ Thông tư số 02/2017/TT-VPCP ngày 31/10/2017 của Văn phòng Chính phủ hướng dẫn nghiệp vụ về kiểm soát thủ tục hành chính;

Căn cứ Quyết định số 2972/QĐ-BNN-CN ngày 29/8/2024 của Bộ Nông nghiệp và Phát triển nông thôn về việc công bố thủ tục hành chính mới ban hành lĩnh vực chăn nuôi thuộc phạm vi chức năng quản lý của Bộ Nông nghiệp và Phát triển nông thôn;

Theo đề nghị của Giám đốc Sở Nông nghiệp và Phát triển nông thôn tại Tờ trình số 3236/TTr -SNN ngày 12/11/2024 và Chánh Văn phòng UBND tỉnh.

QUYẾT ĐỊNH:

Điều 1. Công bố kèm theo Quyết định này Danh mục thủ tục hành chính ban hành mới trong lĩnh vực Chăn nuôi thuộc thẩm quyền giải quyết của UBND cấp huyện trên địa bàn tỉnh Quảng Bình.

Điều 2. Sở Nông nghiệp và Phát triển nông thôn có trách nhiệm phối hợp với UBND các huyện, thị xã, thành phố tổ chức xây dựng và trình UBND tỉnh phê duyệt các quy trình giải quyết thủ tục hành chính/ cung cấp dịch vụ công trực tuyến được công bố tại Quyết định này để thiết lập quy trình điện tử lên Hệ thống thông tin giải quyết thủ tục hành chính của tỉnh.

Điều 3. Quyết định này có hiệu lực thi hành kể từ ngày ký.

Điều 4. Chánh Văn phòng UBND tỉnh, Giám đốc Sở Nông nghiệp và Phát triển nông thôn, Giám đốc Sở Thông tin và Truyền thông, Chủ tịch UBND các huyện, thị xã, thành phố và các tổ chức, cá nhân có liên quan chịu trách nhiệm thi hành Quyết định này./.

Nơi nhận:
- Như Điều 4;
- Bộ NN&PTNT;
- Cục KS TTHC - VPCP;
- CT, các PCT UBND tỉnh;
- Cổng TTĐT QB;
- Lưu: VT, KSTTHC. | KT. CHỦ TỊCH
PHÓ CHỦ TỊCH




Đoàn Ngọc Lâm

PHỤ LỤC

DANH MỤC THỦ TỤC HÀNH CHÍNH MỚI BAN HÀNH TRONG LĨNH VỰC CHĂN NUÔI
(Kèm theo Quyết định số 3218/QĐ-UBND ngày 18/11/2024 của Chủ tịch UBND tỉnh Quảng Bình)

Số TT | Tên TTHC | Thời hạn giải quyết | Địa điểm thực hiện | Phí, lệ phí | Căn cứ pháp lý | Cơ quan thực hiện

1 | Hỗ trợ chi phí nâng cao hiệu quả chăn nuôi cho đơn vị đã cung cấp vật tư phối giống, công phối giống nhân tạo gia súc (trâu, bò); chi phí liều tinh để thực hiện phối giống cho lợn nái đối với các chính sách sử dụng vốn sự nghiệp nguồn ngân sách nhà nước | 90 ngày, kể từ ngày nhận được hồ sơ hợp lệ | Nộp hồ sơ và nhận kết quả giải quyết tại Bộ phận một cửa của UBND cấp huyện thông qua các cách thức sau:
- Trực tiếp.
- Qua dịch vụ bưu chính.
- Trực tuyến tại địa chỉ: https://dichvucong.quangbinh.gov.vn | Không | Điều 8, Điều 14, Nghị định số 106/2024/NĐ-CP ngày 01 tháng 8 năm 2024 của Chính phủ quy định chính sách hỗ trợ nâng cao hiệu quả chăn nuôi. | UBND cấp huyện

2 | Quyết định phê duyệt kinh phí hỗ trợ đào tạo, tập huấn để chuyển đổi từ chăn nuôi sang các nghề khác; chi phí cho cá nhân được đào tạo về kỹ thuật phối giống nhân tạo gia súc (trâu, bò); chi phí mua bình chứa Nitơ lỏng bảo quản tinh cho người làm dịch vụ phối giống nhân tạo gia súc (trâu, bò) đối với các chính sách sử dụng vốn sự nghiệp nguồn ngân sách nhà nước | 40 ngày, kể từ ngày nhận được hồ sơ. | Nộp hồ sơ và nhận kết quả giải quyết tại Bộ phận một cửa của UBND cấp huyện thông qua các cách thức sau:
- Trực tiếp.
- Qua dịch vụ bưu chính.
- Trực tuyến tại địa chỉ: https://dichvucong.quangbinh.gov.vn | Không | Điều 7, Điều 8, Điều 14, Nghị định số 106/2024/NĐ-CP ngày 01 tháng 8 năm 2024 của Chính phủ quy định chính sách hỗ trợ nâng cao hiệu quả chăn nuôi. | UBND cấp huyện
    """
   
    
    issue_date = ""  # Có thể thay đổi nếu cần thiết
    result = extract_effective_status(doc_content, issue_date)
    
    logger.info("extract_result", result=result)
