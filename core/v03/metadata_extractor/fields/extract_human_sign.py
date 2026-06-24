import re
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.v03.metadata_extractor.utils.regex_pattern import REGEX_PATTERNS_POSITION_HIERARCHY
from core.common.llms import LLMs
import json
from constants import LLMsConfigExtractMetadata

#Call LLMs
LLMs = LLMs(llms_config=LLMsConfigExtractMetadata)

# Load the prompt from JSON file once at module level
JSON_FILE_PATH = f"{PROJECT_ROOT}/core/v03/metadata_extractor/utils/prompts.json"
try:
    with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
        prompt_data = json.load(f)
        EXTRACT_HUMAN_SIGN_PROMPT = prompt_data["extract_human_sign_prompt"]
except Exception as e:
    logger.error("load_prompt_failed", **{"error.code": "IO", "error.message": str(e)}, json_path=JSON_FILE_PATH, exc_info=True)


# Các loại dấu ngoặc kép/đơn (thẳng và cong) thường bao quanh trích dẫn
QUOTE_CHARS = "\"'“”‘’"

# Kích thước cửa sổ của chiến lược 1 (pre_chars + post_chars). Fallback cuối
# (__get_area_signature_3) lấy đúng từng ấy ký tự ở cuối văn bản.
SIGNATURE_PRE_CHARS = 200
SIGNATURE_POST_CHARS = 1300
SIGNATURE_WINDOW_SIZE = SIGNATURE_PRE_CHARS + SIGNATURE_POST_CHARS

# Tiền tố quyền hạn ký: Ký thay, Thay mặt, Thừa lệnh, Thừa ủy quyền.
SIGN_AUTHORITY_PREFIXES = r"(?:KT|TM|TL|TUQ)\.?"

# Regex xóa chức danh, dùng để kiểm tra một dòng có CHỈ gồm chức danh hay không.
# Tái sử dụng đúng danh sách chức danh trong POSITION_HIERARCHY_REGEX bằng cách
# lấy phần alternation giữa nhóm '(' ... ')' (không phụ thuộc tiền tố/hậu tố của
# pattern), nhưng sắp xếp chức danh DÀI trước để 'CHỦ TỊCH QUỐC HỘI' không bị cắt
# cụt thành 'CHỦ TỊCH'.
_POSITION_HIERARCHY_PATTERN = REGEX_PATTERNS_POSITION_HIERARCHY["POSITION_HIERARCHY_REGEX"]["pattern"]
_POSITION_TITLE_ALTERNATION = _POSITION_HIERARCHY_PATTERN[_POSITION_HIERARCHY_PATTERN.index("(") + 1:_POSITION_HIERARCHY_PATTERN.rindex(")")]
_TITLE_CLEAN_REGEX = re.compile("|".join(sorted(_POSITION_TITLE_ALTERNATION.split("|"), key=len, reverse=True)))


def __extract_window(content, start_idx, pre_chars=200, post_chars=1300):
    '''
        Cắt một cửa sổ văn bản quanh vị trí start_idx.
    '''
    extract_start = max(0, start_idx - pre_chars)
    extract_end = min(len(content), start_idx + post_chars)
    return content[extract_start:extract_end]


def __is_standalone_title_line(content, pos):
    '''
        Kiểm tra dòng chứa vị trí pos có phải DÒNG CHỮ KÝ độc lập hay không:
        chỉ gồm (các) chức danh, có thể kèm tiền tố KT./TM./TL./TUQ. và dấu phân
        cách. Nếu sau khi bỏ hết những thứ đó vẫn còn chữ thì đây là TIÊU ĐỀ mục
        dài (vd 'VIỆN TRƯỞNG, PHÓ VIỆN TRƯỞNG VIỆN KIỂM SÁT NHÂN DÂN CÁC CẤP'),
        không phải chữ ký -> loại bỏ.
    '''
    line_start = content.rfind("\n", 0, pos) + 1
    line_end = content.find("\n", pos)
    if line_end == -1:
        line_end = len(content)
    line = content[line_start:line_end]

    leftover = re.sub(SIGN_AUTHORITY_PREFIXES, "", line)
    leftover = _TITLE_CLEAN_REGEX.sub("", leftover)
    leftover = re.sub(r"[\s,./;:]", "", leftover)
    return leftover == ""


def __is_quoted_mark(content, start, end):
    '''
        Kiểm tra dấu './.' có bị ngoặc kép/đơn bao quanh hay không.
        Dấu kết thúc thật luôn là 'chữ ./. xuống dòng' nên không kề ngoặc;
        nếu một trong hai phía là ngoặc thì đây là trích dẫn văn bản khác.
    '''
    i = start - 1
    while i >= 0 and content[i].isspace():
        i -= 1
    before = content[i] if i >= 0 else ""

    j = end
    while j < len(content) and content[j].isspace():
        j += 1
    after = content[j] if j < len(content) else ""

    return before in QUOTE_CHARS or after in QUOTE_CHARS


def __get_area_signature_1(content, additional_chars=1300):
    """
        Trích xuất vùng chữ ký dựa trên marker ĐẦU TIÊN hợp lệ.
        Khối chữ ký của văn bản chính nằm ngay sau dấu kết thúc './.' đầu tiên
        và 'Nơi nhận:' đầu tiên; các Phụ lục, biểu mẫu phía sau cũng chứa
        'Nơi nhận:' và './.' nhưng chỉ là mẫu trống nên phải bỏ qua.
        Vì vậy lấy marker xuất hiện SỚM NHẤT, đồng thời:
          - 'Nơi nhận:' phải ở đầu dòng (tránh khớp giữa câu).
          - './.' phải KHÔNG bị ngoặc kép/đơn bao quanh (tránh trích dẫn).
    """
    candidates = []

    # 1) 'Nơi nhận:' đầu dòng — vị trí đầu tiên
    noi_nhan = re.search(r"(?m)^[ \t]*Nơi nhận:", content)
    if noi_nhan:
        candidates.append(noi_nhan.start())

    # 2) './.' đầu tiên không bị ngoặc kép/đơn bao quanh
    for m in re.finditer(r"\./\.", content):
        if not __is_quoted_mark(content, m.start(), m.end()):
            candidates.append(m.end())  # ngay sau dấu, giữ ngữ nghĩa lookbehind cũ
            break

    if candidates:
        return __extract_window(content, min(candidates), SIGNATURE_PRE_CHARS, additional_chars)
    return None


def __get_area_signature_2(content, additional_chars=1300):
    """
        Fallback theo chức danh khi không có 'Nơi nhận:' / './.'.
        Khối chữ ký nằm cuối văn bản nên lấy chức danh ĐỨNG ĐỘC LẬP CUỐI CÙNG;
        bỏ qua các tiêu đề mục viết hoa ở giữa văn bản (vd 'VIỆN TRƯỞNG, PHÓ VIỆN
        TRƯỞNG ...') vốn cũng khớp pattern nhưng không phải dòng chữ ký.
    """
    # Pattern từ CHUC_DANH_HIERARCHY
    pattern = REGEX_PATTERNS_POSITION_HIERARCHY["POSITION_HIERARCHY_REGEX"]["pattern"]
    anchor = None
    for m in re.finditer(pattern, content):
        # m.start() ở ký tự '\n'; chức danh bắt đầu ở m.start(1)
        if __is_standalone_title_line(content, m.start(1)):
            anchor = m.start(1)
    if anchor is not None:
        return __extract_window(content, anchor, 300, additional_chars)
    return None


def __get_area_signature_3(content):
    """
        Fallback cuối cùng: không tìm thấy 'Nơi nhận:', './.' hay chức danh nào.
        Khối chữ ký gần như luôn nằm ở cuối văn bản, nên lấy phần đuôi có độ dài
        bằng cửa sổ của chiến lược 1 (SIGNATURE_WINDOW_SIZE ký tự).
    """
    if not content:
        return None
    return content[-SIGNATURE_WINDOW_SIZE:]


def __get_area(content):
    """
        Xác định format của văn bản và trích xuất phần liên quan.
    """
    area = __get_area_signature_1(content)
    if area is not None:
        logger.debug("found_signature_pattern", action="__get_area", pattern="Nơi nhận: or ./.")
        return area
    area = __get_area_signature_2(content)
    if area is not None:
        logger.debug("try_hierarchy_regex", action="__get_area")
        return area
    logger.debug("fallback_tail", action="__get_area", tail_chars=SIGNATURE_WINDOW_SIZE)
    return __get_area_signature_3(content)


def __llms_extract_human_sign(content):  
    '''
        Extract human sign by llms
    '''  
    dictionary = {}    
    logger.debug("extract_human_sign", action="__llms_extract_human_sign", content_len=len(content) if content else 0)
    
    if content is not None:    
        prompt = EXTRACT_HUMAN_SIGN_PROMPT.format(content=content)
        try:
            response = LLMs.llms(prompt)
            logger.debug("receive_llm_response", action="__llms_extract_human_sign", response_len=len(response) if response else 0)
            dictionary = LLMs.llms_post_process(response)
        except Exception as e:
            logger.error("extract_llm_failed", action="__llms_extract_human_sign", **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
            dictionary = {}
    return dictionary


def extract_human_sign(content):
    """
        Xử lý toàn bộ văn bản theo các bước: xác định format, trích xuất dữ liệu, bóc chức danh.
    """
    extracted_content = __get_area(content)        
    logger.debug("extract_content", action="extract_human_sign", content_len=len(extracted_content) if extracted_content else 0)
    
    outputs = []
    if extracted_content:
        dictionary = __llms_extract_human_sign(extracted_content)        
        logger.debug("dictionary_type", action="extract_human_sign", dict_type=str(type(dictionary)))
        if dictionary.get('output') is not None:            
            outputs = dictionary['output']
            outputs = clean_human_sign_ranks(outputs) ## clean cấp bậc của người ký
    return outputs

def clean_human_sign_ranks(human_sign_list):
    """
    Loại bỏ cấp bậc / học vị / danh hiệu khỏi human_name trong danh sách human_sign.
    Ví dụ: 'Đại tướng Nguyễn Tân Cương' -> 'Nguyễn Tân Cương'
    """
    # Danh sách các tiền tố thường gặp (có thể mở rộng thêm)
    rank_prefixes = [
        r"Đại\s*tướng", r"Thượng\s*tướng", r"Trung\s*tướng", r"Thiếu\s*tướng",
        r"Đại\s*tá", r"Thượng\s*tá", r"Trung\s*tá", r"Thiếu\s*tá",
        r"Trung\s*úy", r"Thiếu\s*úy", r"Đại\s*úy", r"Thượng\s*úy",
        r"Giáo\s*sư", r"Phó\s*Giáo\s*sư", r"Tiến\s*sĩ", r"Thạc\s*sĩ", r"Cử\s*nhân",
        r"Kỹ\s*sư", r"Bác\s*sĩ", r"PGS\.?(\s*TS\.?)?", r"TS\.?", r"CN",
        r"Đ/c", r"Đồng\s*chí", r"Ông", r"Bà", r"Anh", r"Chị"
    ]

    # Tạo regex tổng hợp, không phân biệt hoa thường
    pattern = re.compile(r"^(?:" + "|".join(rank_prefixes) + r")\s+", re.IGNORECASE)

    cleaned_list = []
    for person in human_sign_list:
        name = person.get("human_name", "").strip()
        # Lặp đến khi không còn tiền tố
        while True:
            new_name = re.sub(pattern, "", name)
            if new_name == name:
                break
            name = new_name.strip()
        # Chuẩn hóa lại khoảng trắng
        person["human_name"] = re.sub(r"\s+", " ", name)
        cleaned_list.append(person)

    return cleaned_list


async def __llms_extract_human_sign_async(content, client, semaphore):  
    '''
        Extract human sign by llms
    '''  
    dictionary = {}    
    logger.debug("extract_human_sign", action="__llms_extract_human_sign", content_len=len(content) if content else 0)
    
    if content is not None:    
        prompt = EXTRACT_HUMAN_SIGN_PROMPT.format(content=content)
        try:
            async with semaphore:
                response = await LLMs.llms_async(prompt, client=client)
            logger.debug("receive_llm_response", action="__llms_extract_human_sign", response_len=len(response) if response else 0)
            dictionary = LLMs.llms_post_process(response)
        except Exception as e:
            logger.error("extract_llm_failed", action="__llms_extract_human_sign", **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
            dictionary = {}
    return dictionary


async def extract_human_sign_async(content, client, semaphore):
    """
        Xử lý toàn bộ văn bản theo các bước: xác định format, trích xuất dữ liệu, bóc chức danh.
    """
    extracted_content = __get_area(content)        
    logger.debug("extract_content", action="extract_human_sign", content_len=len(extracted_content) if extracted_content else 0)
    
    outputs = []
    if extracted_content:
        dictionary = await __llms_extract_human_sign_async(extracted_content, client, semaphore)        
        logger.debug("dictionary_type", action="extract_human_sign", dict_type=str(type(dictionary)))
        if dictionary.get('output') is not None:            
            outputs = dictionary['output']
            outputs = clean_human_sign_ranks(outputs) ## clean cấp bậc của người ký
    return outputs


if __name__ == "__main__":
    txt = """
Điều 84. Tổ chức thực hiện

1. Ủy ban Dân tộc

Ủy ban Dân tộc chủ trì, phối hợp với các Bộ, ngành liên quan, UBND cấp tỉnh tổ chức triển khai thực hiện các nội dung quy định tại Thông tư này.

2. Các Bộ, ngành liên quan

Căn cứ nhiệm vụ được Thủ tướng Chính phủ phân công, phối hợp với Ủy ban Dân tộc tổ chức thực hiện các nội dung quy định tại Thông tư này.

3. UBND cấp tỉnh

a) Theo chức năng, nhiệm vụ, thẩm quyền được giao chỉ đạo, hướng dẫn và tổ chức thực hiện các nội dung quy định tại Thông tư này đảm bảo phù hợp, và tuân thủ quy định của pháp luật; chịu trách nhiệm trực tiếp, toàn diện về tiến độ, chất lượng, hiệu quả thực hiện các Dự án, Tiểu dự án, Nội dung thành phần thuộc Chương trình.

b) Thực hiện chế độ báo cáo theo các quy định hiện hành.

Điều 85. Điều khoản thi hành

1. Thông tư này có hiệu lực thi hành kể từ ngày 15 tháng 8 năm 2022.

2. Trường hợp các văn bản trích dẫn tại Thông tư này được sửa đổi, bổ sung hoặc thay thế bằng văn bản khác thì áp dụng quy định tại văn bản sửa đổi, bổ sung hoặc thay thế.

3. Trong quá trình tổ chức thực hiện, nếu có vướng mắc, đề nghị phản ánh về Ủy ban Dân tộc để nghiên cứu, sửa đổi, bổ sung cho phù hợp./.



Nơi nhận:
- Ban Bí thư TW Đảng;
- Thủ tướng, các Phó Thủ tướng Chính phủ;
- Văn phòng Tổng Bí thư;
- Văn phòng Trung ương và các Ban của Đảng;
- Văn phòng Chủ tịch nước;
- Văn phòng Quốc hội;
- Văn phòng Chính phủ;
- Hội đồng Dân tộc của Quốc hội;
- Các Bộ, cơ quan ngang Bộ, cơ quan thuộc CP;
- Tòa án Nhân dân tối cao;
- Viện Kiểm sát Nhân dân Tối cao;
- Kiểm toán Nhà nước;
- Ủy ban Giám sát Tài chính Quốc gia;
- Văn phòng Ban chỉ đạo TW phòng chống tham nhũng;
- Ủy ban TW Mặt trận Tổ quốc Việt Nam;
- Cơ quan TW của các Đoàn thể;
- Ngân hàng Chính sách xã hội;
- Cục Kiểm tra VBQPPL (Bộ Tư pháp);
- HĐND, UBND các tỉnh, thành phố trực thuộc TW
thực hiện Chương trình;
- Ban Dân tộc, Sở Kế hoạch và Đầu tư, Sở Tài chính
các tỉnh, TP trực thuộc TW thực hiện Chương trình;
- Ủy ban Dân tộc: Bộ trưởng, Chủ nhiệm; các Thứ trưởng, Phó Chủ nhiệm; các vụ, đơn vị trực thuộc;
- Công báo và Cổng thông tin điện tử Chính phủ;
- Cổng TTĐT của Ủy ban Dân tộc;
- Lưu: VT, CSDT (10b).

BỘ TRƯỞNG, CHỦ NHIỆM




Hầu A Lềnh
    """
    import asyncio
    import httpx
    async def main():
        async with httpx.AsyncClient() as client:
            semaphore = asyncio.Semaphore(10)
            result = await extract_human_sign(txt, client, semaphore)
            print("result:", result)
    
    asyncio.run(main())

