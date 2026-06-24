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


def extract_end_effective_date(content, issue_date):
    '''
        Hàm trích xuất ngày end hiệu lực
    '''
    result = {
        "end_effective_date": "",
        "method": ""
    }    
    return result


if __name__ == "__main__":
    txt = """
ỦY BAN NHÂN DÂN TỈNH NAM ĐỊNH -------
CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập - Tự do - Hạnh phúc  ---------------
Số: 1680/QĐ-UBND
Nam Định, ngày 27 tháng 07 năm 2017
QUYẾT ĐỊNH
V/V CÔNG BỐ DANH MỤC “VĂN BẢN QUY PHẠM PHÁP LUẬT DO UBND TỈNH BAN HÀNH” HẾT HIỆU LỰC TOÀN BỘ
ỦY BAN NHÂN DÂN TỈNH NAM ĐỊNH
Căn cứ Luật Tổ chức chính quyền địa phương ngày 19/6/2015;
Căn cứ Luật Ban hành văn bản quy phạm pháp luật ngày 22/6/2015;
Căn cứ Nghị định số 34/2016/NĐ-CP ngày 14/5/2016 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Ban hành văn bản quy phạm pháp luật;
Xét đề nghị của Sở Tư pháp tại Tờ trình số 34/TTr-STP ngày 26/7/2017 về việc công bố Danh mục “Văn bản quy phạm pháp luật do UBND tỉnh ban hành” hết hiệu lực toàn bộ,
QUYẾT ĐỊNH:
Điều 1. Công bố Danh mục “Văn bản quy phạm pháp luật do UBND tỉnh ban hành” hết hiệu lực toàn bộ (có Danh mục kèm theo).
Điều 2. Quyết định có hiệu lực thi hành kể từ ngày ký.
Điều 3. Chánh Văn phòng UBND tỉnh, Giám đốc Sở Tư pháp, Giám đốc, Thủ trưởng các sở, ban, ngành trong tỉnh; Chủ tịch UBND các huyện và thành phố Nam Định; các tổ chức và cá nhân có liên quan chịu trách nhiệm thi hành Quyết định này./.
Nơi nhận: - Bộ Tư pháp (Cục Kiểm tra VBQPPL); - Như Điều 3; - Website của tỉnh và VPUBND tỉnh; - Công báo tỉnh; - Lưu VP1, VP6, VP8.
TM. ỦY BAN NHÂN DÂN CHỦ TỊCH     Phạm Đình Nghị
DANH MỤC
“VĂN BẢN QUY PHẠM PHÁP LUẬT DO UBND TỈNH BAN HÀNH” HẾT HIỆU LỰC TOÀN BỘ  (Ban hành kèm theo Quyết định số 1680/QĐ-UBND ngày 27/07/2017 của UBND tỉnh Nam Định)
STT
Số, ký hiệu văn bản
Ngày, tháng, năm ban hành
Tên gọi của văn bản
Lý do hết hiệu lực
Ngày hết hiệu lực
1
3443/2004/QĐ-UBND
25/12/2004
Ban hành quy định chế độ t
    """
    
    logger.info("extract_result", result=extract_end_effective_date(txt, '27/07/2017'))