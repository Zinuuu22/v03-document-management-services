import re
from datetime import datetime, timedelta
import sys
import os
import json
import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.v03.metadata_extractor.utils.regex_pattern import REGEX_PATTERNS_EFFECTIVE_DATE
from core.common.llms import LLMs
from constants import LLMsConfigExtractMetadata

llms = LLMs(llms_config=LLMsConfigExtractMetadata)

# Khi không trích xuất được ngày hiệu lực, mặc định lấy ngày ban hành + 45 ngày.
DEFAULT_EFFECTIVE_OFFSET_DAYS = 45


def _default_effective_date(issue_date):
    """Ngày hiệu lực mặc định khi không xác định được: ngày ban hành + 45 ngày.
    Nhận issue_date dạng chuỗi 'dd/mm/yyyy'; trả về '' nếu trống/không hợp lệ."""
    if not issue_date:
        return ""
    try:
        base = datetime.strptime(issue_date, "%d/%m/%Y")
    except (ValueError, TypeError):
        return ""
    return (base + timedelta(days=DEFAULT_EFFECTIVE_OFFSET_DAYS)).strftime("%d/%m/%Y")


def extract_context(text, keyword="hiệu lực", window=500):
    if not isinstance(text, str):
        return ""
    match = re.search(keyword, text)
    if match:
        start = max(match.start() - window, 0)
        end = min(match.end() + window, len(text))
        return text[start:end]
    return ""


def extract_effective_date_llms(content):
    content = extract_context(content)
    
    PROMPT_LLMS = f"""
    /no_think
    ## Vai trò:
    Bạn là một chuyên gia ngôn ngữ pháp lý Việt Nam. Nhiệm vụ của bạn là **phân tích đoạn văn bản pháp luật** và **xác định chính xác ngày có hiệu lực** (ngày văn bản bắt đầu có hiệu lực thi hành).
    ## Điều cấm kị: Tuyệt đối không được dùng thông tin không có trong đoạn văn mà bạn được cung cấp
    ## Hướng dẫn:
    - Tìm trong đoạn văn các cụm như:
      - "Có hiệu lực từ ngày ... tháng ... năm ..."
      - "Bắt đầu có hiệu lực kể từ ngày ... tháng ... năm ..."
      - "Hiệu lực thi hành kể từ ngày ..."
      - Hoặc các cách diễn đạt tương tự.
    - Nếu tìm thấy, chỉ **trích xuất đúng phần ngày tháng năm**, chuẩn hóa về định dạng: `dd/mm/yyyy`
        - Nếu chỉ có tháng/năm → ghi `mm/yyyy`
        - Nếu chỉ có năm → ghi `yyyy`
    - Nếu **không có thông tin**, trả về đúng cụm từ: effective_date: Không có thông tin
    - Nếu **có thông tin**, trả về đúng định dạng: effective_date: dd/mm/yyyy

    ⚠️ Không giải thích thêm. Không thêm câu chữ, dấu ngoặc, hay ký tự thừa.
    ## Đoạn văn cần phân tích:
    {content}
    """    
    response = llms.llms(PROMPT_LLMS)    
    clean_result = response.split("/think")[-1].strip()
    return clean_result.strip().lower()

    
def extract_effective_date(content, issue_date):
    '''
        Hàm trích xuất ngày có hiệu lực
    '''
    result = {
        "effective_date": "",
        "method": ""
    }
    
    # TH1: Hiệu lực từ ngày...tháng...năm...
    EFFECTIVE_DATE_MATCH_1 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_1"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_1:
        day, month, year = map(int, EFFECTIVE_DATE_MATCH_1.groups())
        result["effective_date"] = f"{day:02d}/{month:02d}/{year}"
        result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_1"]["description"]
        return result
    
    # TH2: Hiệu lực từ dd/mm/yyyy
    EFFECTIVE_DATE_MATCH_2 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_2"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_2:
        day, month, year = map(int, EFFECTIVE_DATE_MATCH_2.groups())
        result["effective_date"] = f"{day:02d}/{month:02d}/{year}"
        result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_2"]["description"]
        return result

    # TH3: Hiệu lực từ ngày ký/ban hành
    EFFECTIVE_DATE_MATCH_3 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_3"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_3 and issue_date:
        result["effective_date"] = issue_date
        result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_3"]["description"]
        return result

    # TH4: Hiệu lực sau X ngày (có thể từ ngày đăng Công báo)
    EFFECTIVE_DATE_MATCH_4 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_4"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_4 and issue_date:
        days = int(EFFECTIVE_DATE_MATCH_4.group(1))
        issue_date = datetime.strptime(issue_date, "%d/%m/%Y")
        if "kể từ ngày đăng Công báo" in EFFECTIVE_DATE_MATCH_4.group(0):
            # Không có ngày đăng Công báo → dùng mặc định: ngày ban hành + 45 ngày.
            result["effective_date"] = (issue_date + timedelta(days=DEFAULT_EFFECTIVE_OFFSET_DAYS)).strftime("%d/%m/%Y")
            result["method"] = f"Mặc định: ngày ban hành + {DEFAULT_EFFECTIVE_OFFSET_DAYS} ngày (chưa có ngày đăng Công báo)"
            result["note"] = "Cần ngày đăng Công báo để tính chính xác; tạm dùng mặc định"
        else:
            effective_date = issue_date + timedelta(days=days)
            result["effective_date"] = effective_date.strftime("%d/%m/%Y")
            result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_4"]["description"]
        return result

    # TH5: Hiệu lực từ ngày thông qua
    EFFECTIVE_DATE_MATCH_5 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_5"]["pattern"], content)
    adoption_date_match = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_5_adoption_date"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_5 and adoption_date_match:
        # day, month, year = map(int, adoption_date_match.groups())
        # result["effective_date"] = f"{day:02d}/{month:02d}/{year}"
        # result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_5"]["description"]
        # return result
        try:
            groups = [int(g) for g in adoption_date_match.groups() if g]
            if len(groups) == 3:
                day, month, year = groups
                result["effective_date"] = f"{day:02d}/{month:02d}/{year}"
                result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_5"]["description"]
                return result
        except Exception as e:
            logger.error("parse_date_error", action="extract_effective_date", **{"error.code": "PARSE", "error.message": str(e)}, exc_info=True)
    
    # TH6: Hiệu lực sau X ngày kể từ ngày ký
    EFFECTIVE_DATE_MATCH_6 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_6"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_6 and issue_date:
        days = int(EFFECTIVE_DATE_MATCH_6.group(1))
        issue_date = datetime.strptime(issue_date, "%d/%m/%Y")
        effective_date = issue_date + timedelta(days=days)
        result["effective_date"] = effective_date.strftime("%d/%m/%Y")
        result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_6"]["description"]
        return result

    # TH7: Hiệu lực sau X (chữ) ngày kể từ ngày ký ban hành
    EFFECTIVE_DATE_MATCH_7 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_7"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_7 and issue_date:
        days = int(EFFECTIVE_DATE_MATCH_7.group(1))
        issue_date = datetime.strptime(issue_date, "%d/%m/%Y")
        effective_date = issue_date + timedelta(days=days)
        result["effective_date"] = effective_date.strftime("%d/%m/%Y")
        result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_7"]["description"]
        return result
    
    # TH8: Hiệu lực áp dụng từ ngày...tháng...năm...
    EFFECTIVE_DATE_MATCH_8 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_8"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_8:
        day, month, year = map(int, EFFECTIVE_DATE_MATCH_8.groups())
        result["effective_date"] = f"{day:02d}/{month:02d}/{year}"
        result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_8"]["description"]
        return result

    llm_result = extract_effective_date_llms(content)
    result["effective_date"] = llm_result.replace("effective_date:", "").strip()
    result["method"] = "LLM fallback"

    if "không có thông tin" in result["effective_date"].lower():
        result["effective_date"] = ""

    # Mặc định: nếu vẫn không xác định được ngày hiệu lực, lấy ngày ban hành + 45 ngày.
    if not result["effective_date"]:
        default_date = _default_effective_date(issue_date)
        if default_date:
            result["effective_date"] = default_date
            result["method"] = f"Mặc định: ngày ban hành + {DEFAULT_EFFECTIVE_OFFSET_DAYS} ngày"
        else:
            result["note"] = "Không thể xác định ngày có hiệu lực với thông tin hiện tại"

    return result


async def extract_effective_date_llms_async(content, client, semaphore):
    content = extract_context(content)
    
    PROMPT_LLMS = f"""
    /no_think
    ## Vai trò:
    Bạn là một chuyên gia ngôn ngữ pháp lý Việt Nam. Nhiệm vụ của bạn là **phân tích đoạn văn bản pháp luật** và **xác định chính xác ngày có hiệu lực** (ngày văn bản bắt đầu có hiệu lực thi hành).
    ## Điều cấm kị: Tuyệt đối không được dùng thông tin không có trong đoạn văn mà bạn được cung cấp
    ## Hướng dẫn:
    - Tìm trong đoạn văn các cụm như:
      - "Có hiệu lực từ ngày ... tháng ... năm ..."
      - "Bắt đầu có hiệu lực kể từ ngày ... tháng ... năm ..."
      - "Hiệu lực thi hành kể từ ngày ..."
      - Hoặc các cách diễn đạt tương tự.
    - Nếu tìm thấy, chỉ **trích xuất đúng phần ngày tháng năm**, chuẩn hóa về định dạng: `dd/mm/yyyy`
        - Nếu chỉ có tháng/năm → ghi `mm/yyyy`
        - Nếu chỉ có năm → ghi `yyyy`
    - Nếu **không có thông tin**, trả về đúng cụm từ: effective_date: Không có thông tin
    - Nếu **có thông tin**, trả về đúng định dạng: effective_date: dd/mm/yyyy

    ⚠️ Không giải thích thêm. Không thêm câu chữ, dấu ngoặc, hay ký tự thừa.
    ## Đoạn văn cần phân tích:
    {content}
    """    
    async with semaphore:
        response = await llms.llms_async(prompt=PROMPT_LLMS, client=client)    
    clean_result = response.split("/think")[-1].strip()
    return clean_result.strip().lower()

    
async def extract_effective_date_async(content, issue_date, client, semaphore):
    '''
        Hàm trích xuất ngày có hiệu lực
    '''
    result = {
        "effective_date": "",
        "method": ""
    }
    
    # TH1: Hiệu lực từ ngày...tháng...năm...
    EFFECTIVE_DATE_MATCH_1 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_1"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_1:
        day, month, year = map(int, EFFECTIVE_DATE_MATCH_1.groups())
        result["effective_date"] = f"{day:02d}/{month:02d}/{year}"
        result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_1"]["description"]
        return result
    
    # TH2: Hiệu lực từ dd/mm/yyyy
    EFFECTIVE_DATE_MATCH_2 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_2"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_2:
        day, month, year = map(int, EFFECTIVE_DATE_MATCH_2.groups())
        result["effective_date"] = f"{day:02d}/{month:02d}/{year}"
        result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_2"]["description"]
        return result

    # TH3: Hiệu lực từ ngày ký/ban hành
    EFFECTIVE_DATE_MATCH_3 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_3"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_3 and issue_date:
        result["effective_date"] = issue_date
        result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_3"]["description"]
        return result

    # TH4: Hiệu lực sau X ngày (có thể từ ngày đăng Công báo)
    EFFECTIVE_DATE_MATCH_4 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_4"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_4 and issue_date:
        days = int(EFFECTIVE_DATE_MATCH_4.group(1))
        issue_date = datetime.strptime(issue_date, "%d/%m/%Y")
        if "kể từ ngày đăng Công báo" in EFFECTIVE_DATE_MATCH_4.group(0):
            # Không có ngày đăng Công báo → dùng mặc định: ngày ban hành + 45 ngày.
            result["effective_date"] = (issue_date + timedelta(days=DEFAULT_EFFECTIVE_OFFSET_DAYS)).strftime("%d/%m/%Y")
            result["method"] = f"Mặc định: ngày ban hành + {DEFAULT_EFFECTIVE_OFFSET_DAYS} ngày (chưa có ngày đăng Công báo)"
            result["note"] = "Cần ngày đăng Công báo để tính chính xác; tạm dùng mặc định"
        else:
            effective_date = issue_date + timedelta(days=days)
            result["effective_date"] = effective_date.strftime("%d/%m/%Y")
            result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_4"]["description"]
        return result

    # TH5: Hiệu lực từ ngày thông qua
    EFFECTIVE_DATE_MATCH_5 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_5"]["pattern"], content)
    adoption_date_match = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_5_adoption_date"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_5 and adoption_date_match:
        # day, month, year = map(int, adoption_date_match.groups())
        # result["effective_date"] = f"{day:02d}/{month:02d}/{year}"
        # result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_5"]["description"]
        # return result
        try:
            groups = [int(g) for g in adoption_date_match.groups() if g]
            if len(groups) == 3:
                day, month, year = groups
                result["effective_date"] = f"{day:02d}/{month:02d}/{year}"
                result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_5"]["description"]
                return result
        except Exception as e:
            logger.error("parse_date_error", action="extract_effective_date", **{"error.code": "PARSE", "error.message": str(e)}, exc_info=True)
    
    # TH6: Hiệu lực sau X ngày kể từ ngày ký
    EFFECTIVE_DATE_MATCH_6 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_6"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_6 and issue_date:
        days = int(EFFECTIVE_DATE_MATCH_6.group(1))
        issue_date = datetime.strptime(issue_date, "%d/%m/%Y")
        effective_date = issue_date + timedelta(days=days)
        result["effective_date"] = effective_date.strftime("%d/%m/%Y")
        result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_6"]["description"]
        return result

    # TH7: Hiệu lực sau X (chữ) ngày kể từ ngày ký ban hành
    EFFECTIVE_DATE_MATCH_7 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_7"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_7 and issue_date:
        days = int(EFFECTIVE_DATE_MATCH_7.group(1))
        issue_date = datetime.strptime(issue_date, "%d/%m/%Y")
        effective_date = issue_date + timedelta(days=days)
        result["effective_date"] = effective_date.strftime("%d/%m/%Y")
        result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_7"]["description"]
        return result
    
    # TH8: Hiệu lực áp dụng từ ngày...tháng...năm...
    EFFECTIVE_DATE_MATCH_8 = re.search(REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_8"]["pattern"], content)
    if EFFECTIVE_DATE_MATCH_8:
        day, month, year = map(int, EFFECTIVE_DATE_MATCH_8.groups())
        result["effective_date"] = f"{day:02d}/{month:02d}/{year}"
        result["method"] = REGEX_PATTERNS_EFFECTIVE_DATE["EFFECTIVE_DATE_REGEX_8"]["description"]
        return result

    llm_result = await extract_effective_date_llms_async(content, client, semaphore)
    result["effective_date"] = llm_result.replace("effective_date:", "").strip()
    result["method"] = "LLM fallback"

    if "không có thông tin" in result["effective_date"].lower():
        result["effective_date"] = ""

    # Mặc định: nếu vẫn không xác định được ngày hiệu lực, lấy ngày ban hành + 45 ngày.
    if not result["effective_date"]:
        default_date = _default_effective_date(issue_date)
        if default_date:
            result["effective_date"] = default_date
            result["method"] = f"Mặc định: ngày ban hành + {DEFAULT_EFFECTIVE_OFFSET_DAYS} ngày"
        else:
            result["note"] = "Không thể xác định ngày có hiệu lực với thông tin hiện tại"

    return result

if __name__ == "__main__":
    txt = """
ỦY BAN THƯỜNG VỤ 
QUỐC HỘI
-------
CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc 
---------------
Nghị quyết số: 45/2024/UBTVQH15
Hà Nội, ngày 15 tháng 4 năm 2024
 
NGHỊ QUYẾT
ĐIỀU CHỈNH CHƯƠNG TRÌNH XÂY DỰNG LUẬT, PHÁP LỆNH NĂM 2024
ỦY BAN THƯỜNG VỤ QUỐC HỘI
Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;
Căn cứ Luật Tổ chức Quốc hội số 57/2014/QH13 đã được sửa đổi, bổ sung một số điều theo Luật số 65/2020/QH14;
Căn cứ Luật Ban hành văn bản quy phạm pháp luật số 80/2015/QH13 đã được sửa đổi, bổ sung một số điều theo Luật số 63/2020/QH14;
Trên cơ sở xem xét các Tờ trình số 82/TTr-CP ngày 05/3/2024, số 125/TTr-CP ngày 02/4/2024, số 128/TTr-CP ngày 04/4/2024 của Chính phủ và Báo cáo thẩm tra số 2734/BC-UBPL15 ngày 12/4/2024 của Ủy ban Pháp luật;
QUYẾT NGHỊ:
Điều 1. Điều chỉnh Chương trình xây dựng luật, pháp lệnh năm 2024
1. Bổ sung vào Chương trình xây dựng luật, pháp lệnh năm 2024, trình Quốc hội cho ý kiến và thông qua tại kỳ họp thứ 7 (tháng 5/2024) theo quy trình tại một kỳ họp và theo trình tự, thủ tục rút gọn các dự thảo:
a) Nghị quyết sửa đổi, bổ sung Nghị quyết số 119/2020/QH14 của Quốc hội về thí điểm tổ chức mô hình chính quyền đô thị và một số cơ chế, chính sách đặc thù phát triển thành phố Đà Nẵng (Quốc hội sẽ xem xét, quyết định tên gọi chính thức của dự thảo Nghị quyết);
b) Nghị quyết về thí điểm bổ sung một số cơ chế, chính sách đặc thù phát triển tỉnh Nghệ An.
2. Bổ sung vào Chương trình xây dựng luật, pháp lệnh năm 2024, trình Quốc hội cho ý kiến tại kỳ họp thứ 7 (tháng 5/2024) và thông qua tại kỳ họp thứ 8 (tháng 10/2024): dự án Luật Phòng cháy, chữa cháy và cứu nạn, cứu hộ.
3. Điều chỉnh từ Chương trình cho ý kiến tại kỳ họp thứ 7 (tháng 5/2024) và thông qua tại kỳ họp thứ 8 (tháng 10/2024) sang Chương trình cho ý kiến tại kỳ họp thứ 8 (tháng 10/2024) và thông qua tại kỳ họp thứ 9 (tháng 5/2025): dự án Luật sửa đổi, bổ sung một số điều của Luật Tiêu chuẩn và quy chuẩn kỹ thuật.
Điều 2. Tổ chức thực hiện
1. Phân công cơ quan trình, cơ quan chủ trì thẩm tra, tham gia thẩm tra các dự án, dự thảo được bổ sung vào Chương trình xây dựng luật, pháp lệnh năm 2024 như sau:
TT
Tên dự án
Cơ quan trình
Cơ quan chủ trì thẩm tra
Cơ quan tham gia thẩm tra
1.
Nghị quyết sửa đổi, bổ sung Nghị quyết số 119/2020/QH14 của Quốc hội về thí điểm tổ chức mô hình chính quyền đô thị và một số cơ chế, chính sách đặc thù phát triển thành phố Đà Nẵng
Chính phủ
Ủy ban Tài chính, Ngân sách
Hội đồng Dân tộc, các Ủy ban khác của Quốc hội
2.
Nghị quyết về thí điểm bổ sung một số cơ chế, chính sách đặc thù phát triển tỉnh Nghệ An
Chính phủ
Ủy ban Tài chính, Ngân sách
Hội đồng Dân tộc, các Ủy ban khác của Quốc hội
3.
Luật Phòng cháy, chữa cháy và cứu nạn, cứu hộ
Chính phủ
Ủy ban Quốc phòng và An ninh
Hội đồng Dân tộc, các Ủy ban khác của Quốc hội
2. Đối với các dự án, dự thảo được bổ sung vào Chương trình xây dựng luật, pháp lệnh năm 2024, đề nghị Chính phủ:
a) Chỉ đạo các Bộ, cơ quan được giao chủ trì soạn thảo nghiên cứu, tiếp thu ý kiến của Ủy ban Thường vụ Quốc hội, ý kiến thẩm tra của các cơ quan của Quốc hội để khẩn trương chuẩn bị hồ sơ các dự án, dự thảo bảo đảm chất lượng, tiến độ; trong quá trình soạn thảo, nếu điều chỉnh, bổ sung chính sách so với nội dung Chính phủ đã đề nghị thì phải đánh giá tác động đầy đủ theo quy định của Luật Ban hành văn bản quy phạm pháp luật;
b) Trình Ủy ban Thường vụ Quốc hội xem xét, cho ý kiến về các dự án, dự thảo tại phiên họp Ủy ban Thường vụ Quốc hội tháng 4/2024, chậm nhất là tại phiên họp tháng 5/2024.
Điều 3. Hiệu lực thi hành
Nghị quyết này có hiệu lực thi hành từ ngày thông qua./.
Nghị quyết này được Ủy ban Thường vụ Quốc hội nước Cộng hòa xã hội chủ nghĩa Việt Nam khóa XV, phiên họp thứ 32 thông qua ngày 15 tháng 4 năm 2024.
 
Epas: 31184.
TM. ỦY BAN THƯỜNG VỤ QUỐC HỘI
CHỦ TỊCH




Vương Đình Huệ
    """
    import asyncio
    import httpx
    async def main():
        async with httpx.AsyncClient() as client:
            semaphore = asyncio.Semaphore(10)
            result = await extract_effective_date(txt, '27/07/2017', client, semaphore)
            print("result:", result)
    
    asyncio.run(main())

