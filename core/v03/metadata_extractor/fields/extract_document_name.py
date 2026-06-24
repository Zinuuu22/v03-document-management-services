import re
import sys
import os
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.common.llms import LLMs
from core.v03.metadata_extractor.utils import get_brief_content
from constants import LLMsConfigExtractMetadata
#Call LLMs
LLMs = LLMs(llms_config=LLMsConfigExtractMetadata)

# Load the prompt from JSON file once at module level
JSON_FILE_PATH = f"{PROJECT_ROOT}/core/v03/metadata_extractor/utils/prompts.json"
try:
    with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
        prompt_data = json.load(f)
        EXTRACT_DOCUMENT_NAME_PROMPT = prompt_data["extract_document_name_prompt"]
except Exception as e:
    logger.error("load_prompt_failed", action="module", **{"error.code": "IO", "error.message": str(e)}, json_path=JSON_FILE_PATH, exc_info=True)

# When the regex heuristic produces a name longer than this many characters it has
# almost certainly overrun the title into the body (preamble / "Căn cứ" clauses),
# so we discard it and fall back to the LLM. Legit names in our corpus top out
# around ~250 chars; runaways balloon well past this.
MAX_REGEX_NAME_LEN = 300

# A heading line that merely restates the document's own number/date — e.g.
# "SỐ 61/2014/TT-BCA NGÀY 20-11-2014 [CỦA ...]" or a parenthesized
# "(Số 46/2014/QH13 ngày 13-06-2014)" — appears either just before or just after
# the real title depending on format. Drop it from the regex-walked title so it
# isn't duplicated against the "số {code}" prefix we prepend. Allows an optional
# leading "(" and no space after "SỐ" (OCR variant "SỐ339").
SO_NGAY_LINE = re.compile(r"^\s*\(?\s*SỐ\s*\S.*\bNGÀY\b", re.IGNORECASE)


def _compose_name(document_type, document_code, name):
    """Build the final name as '{type} số {code} {name}', dropping the 'số {code}'
    segment when the document has no code (e.g. old ordinances with no number),
    so it reads cleanly as '{type} {name}' instead of '{type} số  {name}'."""
    prefix = f"{document_type} số {document_code}" if document_code else f"{document_type}"
    return f"{prefix} {name}".strip()


def _lower_keep_codes(text: str) -> str:
    """Lowercase the title for consistent casing, but leave any code-like token —
    one containing '/' and an uppercase letter — untouched, so references to other
    documents (e.g. '17/2012/TT-BCA', '3218/QĐ-UBND') aren't mangled to lowercase."""
    def is_code(tok: str) -> bool:
        return "/" in tok and any(c.isupper() for c in tok)
    return " ".join(tok if is_code(tok) else tok.lower() for tok in text.split())



def extract_document_name(content: str, document_code: str, document_type: str) -> str:
    """
    Trích xuất tên văn bản từ nội dung, sử dụng document_type để hỗ trợ.
    """
    document_name = ""
    if document_type:
        pattern = r"\n(" + re.escape(document_type) + r")\s*\n+"
        matches = list(re.finditer(pattern, "\n" + content, re.IGNORECASE))
        if matches:
            first_match = min(matches, key=lambda m: m.start())
            remaining_text = content[first_match.end(1):]
            # Dấu hiệu kết thúc tên văn bản
            END_MARKERS = re.compile(
                r"^(căn\s+cứ|điều\s+\d|chương\s+[ivx\d]|phần\s+[ivx\d]"
                r"|[-_—=]{3,}"   
                r"|\d+\.\s)",   
                re.IGNORECASE
            )
            lines = []
            consecutive_blanks = 0
            for line in remaining_text.split("\n"):
                stripped = line.strip()
                if END_MARKERS.match(stripped):
                    break
                if not stripped:
                    # Ignore blank lines until the title has started; the gap
                    # between the type label and the title must not trip the break.
                    if lines:
                        consecutive_blanks += 1
                        if consecutive_blanks > 1:
                            break
                    continue
                consecutive_blanks = 0
                lines.append(stripped)
            # Drop any "SỐ <code> NGÀY <date>" heading line (before or after the
            # title) — it restates the document number and is not part of the title.
            lines = [ln for ln in lines if not SO_NGAY_LINE.match(ln)]
            name = _lower_keep_codes(" ".join(lines).strip())
            document_name = _compose_name(document_type, document_code, name)
            # Overrun guard: a too-long name means the heuristic swallowed the body.
            # Reset it so the LLM fallback below re-extracts a clean name.
            if len(document_name) > MAX_REGEX_NAME_LEN:
                logger.debug("document_name_too_long", action="extract_document_name", length=len(document_name), threshold=MAX_REGEX_NAME_LEN)
                document_name = ""
            else:
                logger.debug("extract_document_name", action="extract_document_name", source="after_document_type", document_name=document_name)
    # Nếu không tìm thấy doc_name hoặc không có document_type, sử dụng LLM
    if not document_name:
        try:
            first_part_content = get_brief_content(content, max_length=1000)
            # Use the pre-loaded prompt
            prompt = EXTRACT_DOCUMENT_NAME_PROMPT.format(first_part_content=first_part_content)
            response = LLMs.llms(prompt)
            dictionary = LLMs.llms_post_process(response)
            name = dictionary.get('document_name', 'Không xác định')
            # The LLM sometimes echoes the type and/or the code (as "số <code> ngày
            # <date>") at the start of the name; strip a single leading repeat of
            # each so the prepended "{type} số {code}" prefix isn't duplicated.
            if document_type:
                name = re.sub(r"^\s*" + re.escape(document_type) + r"\s+", "", name, flags=re.IGNORECASE)
            if document_code:
                name = re.sub(r"^\s*(số\s+)?" + re.escape(document_code) + r"(\s+ngày\s+[\d/.\-]+)?\s*", "", name, flags=re.IGNORECASE)
            document_name = _compose_name(document_type, document_code, name)
            logger.debug("extract_document_name_llm", action="extract_document_name", document_name=document_name)
        except Exception as e:
            logger.error("extract_llm_failed", action="extract_document_name", **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
            document_name = 'Không xác định'

    return document_name


async def extract_document_name_async(content: str, document_code: str, document_type: str, client, semaphore) -> str:
    """
    Trích xuất tên văn bản từ nội dung, sử dụng document_type để hỗ trợ.
    """
    document_name = ""
    if document_type:
        pattern = r"\n(" + re.escape(document_type) + r")\s*\n+"
        matches = list(re.finditer(pattern, "\n" + content, re.IGNORECASE))
        if matches:
            first_match = min(matches, key=lambda m: m.start())
            remaining_text = content[first_match.end(1):]
            # Dấu hiệu kết thúc tên văn bản
            END_MARKERS = re.compile(
                r"^(căn\s+cứ|điều\s+\d|chương\s+[ivx\d]|phần\s+[ivx\d]"
                r"|[-_—=]{3,}"   
                r"|\d+\.\s)",   
                re.IGNORECASE
            )
            lines = []
            consecutive_blanks = 0
            for line in remaining_text.split("\n"):
                stripped = line.strip()
                if END_MARKERS.match(stripped):
                    break
                if not stripped:
                    # Ignore blank lines until the title has started; the gap
                    # between the type label and the title must not trip the break.
                    if lines:
                        consecutive_blanks += 1
                        if consecutive_blanks > 1:
                            break
                    continue
                consecutive_blanks = 0
                lines.append(stripped)
            # Drop any "SỐ <code> NGÀY <date>" heading line (before or after the
            # title) — it restates the document number and is not part of the title.
            lines = [ln for ln in lines if not SO_NGAY_LINE.match(ln)]
            name = _lower_keep_codes(" ".join(lines).strip())
            document_name = _compose_name(document_type, document_code, name)
            # Overrun guard: a too-long name means the heuristic swallowed the body.
            # Reset it so the LLM fallback below re-extracts a clean name.
            if len(document_name) > MAX_REGEX_NAME_LEN:
                logger.debug("document_name_too_long", action="extract_document_name", length=len(document_name), threshold=MAX_REGEX_NAME_LEN)
                document_name = ""
            else:
                logger.debug("extract_document_name", action="extract_document_name", source="after_document_type", document_name=document_name)
    # Nếu không tìm thấy doc_name hoặc không có document_type, sử dụng LLM
    if not document_name:
        try:
            first_part_content = get_brief_content(content, max_length=1000)
            # Use the pre-loaded prompt
            prompt = EXTRACT_DOCUMENT_NAME_PROMPT.format(first_part_content=first_part_content)
            async with semaphore:
                response = await LLMs.llms_async(prompt, client)
            dictionary = LLMs.llms_post_process(response)
            name = dictionary.get('document_name', 'Không xác định')
            # The LLM sometimes echoes the type and/or the code (as "số <code> ngày
            # <date>") at the start of the name; strip a single leading repeat of
            # each so the prepended "{type} số {code}" prefix isn't duplicated.
            if document_type:
                name = re.sub(r"^\s*" + re.escape(document_type) + r"\s+", "", name, flags=re.IGNORECASE)
            if document_code:
                name = re.sub(r"^\s*(số\s+)?" + re.escape(document_code) + r"(\s+ngày\s+[\d/.\-]+)?\s*", "", name, flags=re.IGNORECASE)
            document_name = _compose_name(document_type, document_code, name)
            logger.debug("extract_document_name_llm", action="extract_document_name", document_name=document_name)
        except Exception as e:
            logger.error("extract_llm_failed", action="extract_document_name", **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
            document_name = 'Không xác định'

    return document_name

if __name__ == "__main__":
    txt = """
BỘ CÔNG THƯƠNG
_______
Số: 45/2025/TT-BCT

CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập – Tự do – Hạnh phúc
_______________________
Hà Nội, ngày 15 tháng 7 năm 2025





THÔNG TƯ

Sửa đổi, bổ sung một số điều của các Thông tư của Bộ trưởng
Bộ Công Thương trong lĩnh vực quản lý thị trường

_______



Căn cứ Pháp lệnh Quản lý thị trường ngày 08 tháng 3 năm 2016;

Căn cứ Nghị định số 33/2022/NĐ-CP ngày 27 tháng 5 năm 2022 của Chính phủ quy định chi tiết một số điều của Pháp lệnh Quản lý thị trường;

Căn cứ Nghị định số 40/2025/NĐ-CP ngày 26 tháng 02 năm 2025 của Chính phủ quy định chức năng, nhiệm vụ, quyền hạn và cơ cấu tổ chức của Bộ Công Thương;

Theo đề nghị của Cục trưởng Cục Quản lý và Phát triển thị trường trong nước;

Bộ trưởng Bộ Công Thương ban hành Thông tư sửa đổi, bổ sung một số điều của các Thông tư của Bộ trưởng Bộ Công Thương trong lĩnh vực quản lý thị trường.

    """
    logger.info("extract_result", action="main", result=extract_document_name(txt, '33/2018/TT-BCT', 'Thông tư'))
