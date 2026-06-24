import json
import sys
import os
import re
import asyncio
import httpx
from typing import Dict, List, Set, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.common.mongo.client import get_mongo_client
from constants import LLMsConfigExtractRelationship
from core.common.llms import LLMs
from core.v03.relationship_extractor.utils import remove_reference, remove_article, remove_multi_underline, extract_doc_number

LLMs = LLMs(llms_config=LLMsConfigExtractRelationship)
MD_FILE_PATH = f"{PROJECT_ROOT}/core/v03/relationship_extractor/utils/prompts_relationship_document.md"

def load_prompt_by_title(title_pattern: str):
    with open(MD_FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = rf"({title_pattern}.*?)(?=\n# Prompt|\Z)"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(1).strip()
    return None

EXTRACT_RELATIONSHIP_REFERENTIAL_PROMPT = load_prompt_by_title(
    r"# Prompt 6: Trích xuất mối quan hệ dẫn chiếu, áp dụng"
)


# Các cụm tín hiệu của quan hệ dẫn chiếu / áp dụng. Đối ngẫu với module amend:
# chính những cụm này là TỪ KHÓA CẤM trong amend nhưng là TÍN HIỆU NHẬN DIỆN ở đây.
# Danh sách rộng -> nhiều false-positive ở bước candidate, chấp nhận được vì LLM
# (Prompt 6) lọc tiếp.
REFERENTIAL_SIGNAL_PHRASES = (
    "theo quy định tại",
    "thực hiện theo",
    "áp dụng theo",
    "theo quy định của",
    "được thực hiện theo",
    "quy định tại điều",
    "quy định tại khoản",
    "quy định tại nghị định",
    "quy định tại thông tư",
    "dẫn chiếu",
    "tuân theo",
    "phù hợp với quy định",
)


def __is_referential_candidate(article_title, article_content):
    """
    "Cổng" tiền lọc thô trước khi gọi LLM (giống vai trò candidate filter trong
    amend.py): trả True nếu tiêu đề HOẶC nội dung điều luật chứa ít nhất một cụm
    tín hiệu dẫn chiếu, VÀ tiêu đề không phải phụ lục. Quyết định cuối cùng do LLM.
    """
    title_lower = article_title.lower()
    content_lower = article_content.lower()

    if title_lower.find('phụ lục') != -1:
        return False

    for phrase in REFERENTIAL_SIGNAL_PHRASES:
        if title_lower.find(phrase) != -1 or content_lower.find(phrase) != -1:
            return True
    return False


# Bộ trích DETERMINISTIC bổ trợ cho LLM: bắt văn bản đứng ngay sau một CỤM TÍN HIỆU
# dẫn chiếu/áp dụng (xem __RESCUE_TRIGGER): động từ áp dụng "(được) điều chỉnh/tính/
# áp dụng/thực hiện ... theo", "theo quy định của/tại" (phổ biến nhất), "ban hành kèm
# theo" (biểu mẫu/phụ lục). Cần thiết vì các văn bản này thường nằm trong PHỤ LỤC/
# BIỂU MẪU (bị __clean_article_content cắt khỏi input của LLM) hoặc trong ô tính minh
# họa nơi LLM hay bỏ sót. Mọi kết quả vẫn đi qua bộ lọc filter_relationship_results
# (khử base, tự dẫn chiếu, chống hallucination...).
# Mẫu tên một văn bản CÓ số hiệu (kèm ngày/cơ quan nếu có), dùng lại cho cả cụm
# chính lẫn cụm nối "và ...".
__RESCUE_DOC_CODED = (
    r"(?:Nghị định|Thông tư liên tịch|Thông tư|Quyết định|Pháp lệnh|Nghị quyết|Bộ luật|Luật)"
    # Mã cơ quan phải bắt đầu bằng ÍT NHẤT 2 chữ in hoa (vd TT, NĐ, TTLT) -> tránh
    # bắt mã cụt như "71/2023/TT" (dừng giữa chừng do khoảng trắng/chữ thường).
    r"\s+số\s+\d+/\d{4}/[A-ZĐ]{2,}[A-ZĐ0-9\-]*"
    r"(?:\s+ngày\s+\d{1,2}(?:/\d{1,2}/\d{4}|\s+tháng\s+\d{1,2}\s+năm\s+\d{4}))?"
    # "của <cơ quan>": dừng trước ranh giới mệnh đề (và / hướng dẫn / quy định / dấu
    # câu) để KHÔNG nuốt sang văn bản kế tiếp trong cụm liệt kê.
    r"(?:\s+của\s+(?:(?!\s+(?:và|hướng dẫn|quy định|là)\b)[^):;.,\n])+)?"
)
# Mẫu văn bản KHÔNG có số hiệu: chỉ áp cho họ LUẬT (Luật/Bộ luật/Pháp lệnh/Hiến pháp)
# vì đây là loại thường được định danh bằng tên trần ("Luật Đầu tư", "Bộ luật Lao động").
# Nuốt từng từ cho tới RANH GIỚI: dấu câu (; . , xuống dòng) hoặc stop-word mệnh đề
# (và/thì/là/hoặc/để/do/nhằm/này/của). Tên lõi ngắn vẫn fuzzy-match đúng GT.
# KHÔNG mở cho Nghị định/Thông tư... (đã có nhánh CODED) -> hạn chế false-positive.
__RESCUE_DOC_NAMED = (
    r"(?:Bộ luật|Luật|Pháp lệnh|Hiến pháp)"
    r"(?:\s+"
    # Dừng tại stop-word mệnh đề (không thuộc tên văn bản). Lưu ý KHÔNG chặn theo
    # loại văn bản ("Luật"/...) vì tên có thể chứa lại loại đó (vd "Luật Luật sư").
    r"(?!(?:và|thì|là|hoặc|để|do|nhằm|này|của|theo|gồm|bao gồm|về|trong|trước|sau|"
    r"khi|tại|đối|với|kể|được|có|quy định|liên quan|mà|hay|nếu|cũng|vẫn|sẽ|đã|đang)\b)"
    # Mỗi từ: không chứa dấu câu / ngoặc / xuống dòng.
    r"[^\s;.,()\n]+"
    r"){1,10}"
)
# Bất kỳ văn bản nào: ưu tiên CODED (đặc hiệu hơn) rồi mới NAMED.
__RESCUE_DOC_ANY = r"(?:" + __RESCUE_DOC_CODED + r"|" + __RESCUE_DOC_NAMED + r")"

# "Điều/khoản/điểm N [của]" có thể xen giữa "theo"/"và" và tên văn bản.
__RESCUE_LOC = r"(?:(?:điểm\s+\w+\s+)?(?:khoản\s+[\d, ]+)?(?:điều\s+[\d, ]+)?(?:của\s+)?)?"

# Các cụm TÍN HIỆU đứng ngay trước văn bản dẫn chiếu/áp dụng:
#   - động từ áp dụng "(được) điều chỉnh/tính/áp dụng/thực hiện ... theo"
#   - "theo quy định của/tại"           (Pattern A - phổ biến nhất)
#   - "(ban hành) kèm theo"             (Pattern B - biểu mẫu/phụ lục)
__RESCUE_TRIGGER = (
    r"(?:"
    r"(?:được\s+)?(?:điều chỉnh|tính|áp dụng|thực hiện)\s+(?:mức[^.\n]{0,20}?)?theo"
    # "(theo|tuân thủ|tuân theo|đúng|phù hợp với) quy định (của|tại)" — Pattern A mở rộng:
    # ngoài "theo", các động từ áp dụng khác cũng dẫn tới văn bản được áp dụng.
    r"|(?:theo|tuân thủ|tuân theo|đúng|phù hợp với)\s+quy\s+định\s+(?:của|tại)"
    r"|ban hành\s+kèm\s+theo"
    r")"
)

# Cụm chính: "<tín hiệu> [Điều/khoản..] <văn bản>".
__REFERENTIAL_RESCUE_RE = re.compile(
    __RESCUE_TRIGGER + r"\s+" + __RESCUE_LOC + r"(" + __RESCUE_DOC_ANY + r")",
    re.IGNORECASE,
)
# Cụm nối: "... và/, [khoản.. Điều..] <văn bản>" -> đồng chủ thể với cụm chính,
# bắt các văn bản liệt kê tiếp (vd "thực hiện theo NQ A và khoản 4 Điều 1 NQ B").
__REFERENTIAL_RESCUE_CONT_RE = re.compile(
    r"\s*(?:và|,)\s+" + __RESCUE_LOC + r"(" + __RESCUE_DOC_ANY + r")",
    re.IGNORECASE,
)


# Ngữ cảnh SỬA ĐỔI/BÃI BỎ ngay trước tín hiệu: văn bản đứng sau KHÔNG phải dẫn chiếu
# áp dụng mà là ĐỐI TƯỢNG bị sửa đổi/thay thế (vd "Sửa đổi, bổ sung Mẫu X ban hành kèm
# theo Thông tư số ..." trong văn bản amend) -> để module amend/replace xử lý, bỏ ở đây.
__MODIFICATION_PRECONTEXT = (
    "sửa đổi", "bổ sung", "bãi bỏ", "thay thế", "hủy bỏ", "ngưng hiệu lực", "thay cho",
)


def __rescue_referential_by_signal(text: str) -> List[str]:
    """Trả về danh sách tên văn bản (đầy đủ như xuất hiện) đứng sau cụm tín hiệu
    dẫn chiếu/áp dụng, gồm cả các văn bản được liệt kê nối bằng "và/," ngay sau đó."""
    if not text:
        return []
    seen = []

    def _add(raw):
        name = re.sub(r"\s+", " ", raw).strip(" ,.;")
        if name and name not in seen:
            seen.append(name)

    for m in __REFERENTIAL_RESCUE_RE.finditer(text):
        # Bỏ qua nếu ngay trước tín hiệu là ngữ cảnh sửa đổi/bãi bỏ (văn bản là đối
        # tượng bị tác động, không phải được dẫn chiếu áp dụng).
        pre = text[max(0, m.start() - 50): m.start()].lower()
        if any(kw in pre for kw in __MODIFICATION_PRECONTEXT):
            continue
        _add(m.group(1))
        # Nuốt tiếp các cụm "và/,/; <văn bản>" liền kề (liệt kê cùng một tín hiệu).
        pos = m.end()
        while True:
            cont = __REFERENTIAL_RESCUE_CONT_RE.match(text, pos)
            if not cont:
                break
            _add(cont.group(1))
            pos = cont.end()
    return seen


def __clean_article_content(article_content: str) -> str:
    """
    Xóa toàn bộ nội dung kể từ từ 'PHỤ LỤC' trở đi.
    Nếu không tìm thấy 'PHỤ LỤC' thì giữ nguyên nội dung.
    """
    parts = article_content.split("PHỤ LỤC", 1)

    if len(parts) > 1:
        keep_len = len(parts[0])
        return article_content[:keep_len].rstrip()
    return article_content


def __normalize_name(name: str) -> str:
    """Chuẩn hóa tên văn bản để dedup khi không có số hiệu: lowercase + gộp khoảng trắng."""
    return re.sub(r"\s+", " ", name.strip().lower())


def __doc_identity_signature(name: str):
    """
    Chữ ký định danh cho văn bản KHÔNG có số hiệu (Luật/Bộ luật/Pháp lệnh... được
    định danh bằng tên + năm): trả về (tên_lõi_bỏ_ngày_tháng_năm, năm).

    Dùng để khử trùng referential với base khi hai bên ghi KHÁC cách cùng một văn bản,
    ví dụ "Bộ luật Tố tụng hình sự ngày 27 tháng 11 năm 2015" (ở base) và
    "Bộ luật Tố tụng hình sự năm 2015" (LLM nhặt vào referential).

    Trả None nếu không lấy được năm -> không đủ tin cậy để khử (tránh khử nhầm).
    """
    low = __normalize_name(name)
    year_match = re.search(r"năm\s+(\d{4})", low)
    if not year_match:
        return None
    year = year_match.group(1)
    # Bỏ phần "ngày .. tháng .. năm ...." hoặc "năm ...." về sau để lấy tên lõi.
    core = re.sub(r"ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}.*$", "", low)
    core = re.sub(r"năm\s+\d{4}.*$", "", core)
    core = core.strip(" ,.;")
    if not core:
        return None
    return (core, year)


def __name_core(name: str) -> str:
    """
    Tên LÕI của một văn bản, bỏ mọi thành phần định danh biến thiên (số hiệu, "số",
    ngày/tháng/năm, phần trong ngoặc). Dùng để khử trùng referential <-> base khi
    văn bản LUẬT được ghi KHÁC độ chi tiết, ví dụ:
      base       : "Bộ luật Lao động ngày 20 tháng 11 năm 2019"
      referential: "Bộ luật Lao động"            -> cùng lõi "bộ luật lao động"
      base       : "Bộ luật Tố tụng hình sự số 101/2015/QH13 ngày 27/11/2015"
      referential: "Bộ luật Tố tụng hình sự"      -> cùng lõi "bộ luật tố tụng hình sự"

    Khác __doc_identity_signature (đòi hỏi có năm) ở chỗ KHÔNG cần năm -> bắt được
    cả khi referential ghi tên trần không kèm năm/số hiệu.
    """
    low = __normalize_name(name)
    low = re.sub(r"\(.*?\)", " ", low)                       # bỏ "(sửa đổi, bổ sung ...)"
    # Bỏ số hiệu: bao gồm cả mã kết thúc bằng chữ-số như QH13, QH14 (\w bắt cả chữ số).
    low = re.sub(r"\d+/\d{4}/[\wđ&./\-]+", " ", low, flags=re.UNICODE)
    low = re.sub(r"\bsố\b", " ", low)
    low = re.sub(r"ngày\s+\d{1,2}.*$", " ", low)             # bỏ "ngày ..." về sau
    low = re.sub(r"năm\s+\d{4}.*$", " ", low)                 # bỏ "năm YYYY ..." về sau
    low = re.sub(r"\s+", " ", low).strip(" ,.;")
    return low


# Loại văn bản hợp lệ: tên phải bắt đầu bằng một trong các cụm này (nếu không có số hiệu)
# thì mới coi là một văn bản định danh được. Sắp dài trước để startswith chính xác.
DOCUMENT_TYPE_TOKENS = (
    "thông tư liên tịch", "bộ luật", "luật", "pháp lệnh", "nghị định", "nghị quyết",
    "thông tư", "quyết định", "chỉ thị", "hiến pháp", "sắc lệnh", "sắc luật",
    "công ước", "hiệp định", "điều ước", "văn bản hợp nhất",
)

# Cụm tự dẫn chiếu (chính văn bản đầu vào) -> loại.
SELF_REFERENCE_MARKERS = (
    "thông tư này", "nghị định này", "luật này", "bộ luật này", "pháp lệnh này",
    "nghị quyết này", "quyết định này", "chỉ thị này", "văn bản này",
    "thông tư liên tịch này",
)

# Cụm mơ hồ/gộp -> không phải một văn bản cụ thể -> loại.
VAGUE_MARKERS = (
    "các văn bản", "văn bản hướng dẫn", "văn bản khác", "văn bản có liên quan",
    "văn bản liên quan", "quy định khác", "quy định của pháp luật", "pháp luật có liên quan",
    "và các", "và của",
)

# Dấu hiệu HIỆN TRẠNG/LỊCH SỬ THỤ HƯỞNG: văn bản chỉ được nhắc để nói đối tượng
# đang/đã/được/thôi hưởng một chế độ THEO văn bản đó -> KHÔNG phải dẫn chiếu áp dụng.
__ENTITLEMENT_RE = re.compile(r"(?:đang|đã|được|thôi|tiếp tục|chưa được)\s+hưởng")


def __entitlement_needle(doc: str, doc_number: str) -> Optional[str]:
    """Chuỗi định danh ngắn để dò ngữ cảnh: ưu tiên số hiệu đầy đủ; nếu không có thì
    lấy mã dạng '613/QĐ-TTg'. Văn bản chỉ có TÊN (không mã) -> bỏ qua (tránh khớp rộng)."""
    if doc_number:
        return doc_number.lower()
    m = re.search(r"\d+/[A-ZĐ][\wđ\-]{1,}", doc)
    return m.group(0).lower() if m else None


def __in_entitlement_context(needle: str, joined_lower: str, window: int = 130) -> bool:
    """True nếu MỌI lần xuất hiện của `needle` đều nằm trong ngữ cảnh 'thụ hưởng'
    (có '(đang|đã|được|thôi...) hưởng' ngay trước đó trong ~window ký tự)."""
    if not needle or not joined_lower:
        return False
    idx = joined_lower.find(needle)
    if idx == -1:
        return False
    while idx != -1:
        if not __ENTITLEMENT_RE.search(joined_lower[max(0, idx - window): idx]):
            return False  # có ít nhất một lần KHÔNG phải ngữ cảnh thụ hưởng -> giữ
        idx = joined_lower.find(needle, idx + 1)
    return True


def __is_valid_document_name(name: str) -> bool:
    """
    Giữ lại chỉ khi `name` là MỘT văn bản định danh được:
    - Không phải tự dẫn chiếu ("Thông tư này"...).
    - Không phải cụm mơ hồ/gộp ("các văn bản hướng dẫn...", "... và của ...").
    - Có số hiệu, HOẶC bắt đầu bằng một loại văn bản hợp lệ (Luật, Nghị định, ...).
    Lọc các trường hợp như "Bộ Công an", "Chính phủ và của Bộ Công an",
    "Chính phủ về chế độ tiền lương ..." (chỉ là tên cơ quan / mảnh câu).
    """
    low = __normalize_name(name)
    if not low:
        return False
    if any(m in low for m in SELF_REFERENCE_MARKERS):
        return False
    if any(m in low for m in VAGUE_MARKERS):
        return False
    if extract_doc_number(name):
        return True
    return any(low.startswith(t) for t in DOCUMENT_TYPE_TOKENS)


def filter_relationship_results(
    relationships: Dict[str, List[str]],
    document_name: str,
    base_doc_numbers: Optional[Set[str]] = None,
    full_content_list: Optional[List[str]] = None,
    base_names: Optional[List[str]] = None,
    protected_numbers: Optional[Set[str]] = None,
) -> Dict[str, List[str]]:
    """
    - Loại bỏ chính văn bản đầu vào (self-reference)
    - Loại bỏ các văn bản trùng số hiệu (hoặc trùng tên chuẩn hóa nếu thiếu số hiệu)
    - Loại bỏ văn bản đã thuộc nhóm 'base' (chống nhân đôi với căn cứ):
      + theo số hiệu khi truyền base_doc_numbers (Phương án A);
      + theo CHỮ KÝ TÊN (tên lõi + năm) khi truyền base_names -- xử lý văn bản LUẬT
        không có số hiệu (vd "Bộ luật Tố tụng hình sự") mà base_doc_numbers bỏ sót.
    - Chống hallucination: tên văn bản phải thực sự xuất hiện trong nội dung nguồn
      (khi truyền full_content_list).
    """

    source_doc_number = extract_doc_number(document_name)
    base_doc_numbers = base_doc_numbers or set()
    protected_numbers = protected_numbers or set()

    # Nguồn dạng chữ thường (giữ khoảng trắng) -> dò ngữ cảnh 'thụ hưởng' theo cửa sổ.
    joined_content_lower = (
        " ".join(full_content_list).lower()
        if full_content_list is not None else None
    )

    # Chữ ký định danh của các văn bản căn cứ KHÔNG có số hiệu (Luật/Bộ luật/...),
    # để khử văn bản căn cứ bị LLM nhặt nhầm vào referential dù ghi khác cách.
    base_name_signatures = set()
    # Tên lõi của TẤT CẢ văn bản căn cứ (kể cả loại có số hiệu) -> khử văn bản LUẬT
    # không số hiệu bị LLM nhặt vào referential dù base ghi kèm số hiệu/ngày tháng.
    base_name_cores = set()
    for base_name in (base_names or []):
        core = __name_core(base_name)
        # Bỏ qua lõi rỗng hoặc chỉ là một LOẠI văn bản trần ("luật", "nghị định"...)
        # -> tránh khử nhầm mọi văn bản cùng loại (vd luật sửa đổi rút về "luật").
        if core and core not in DOCUMENT_TYPE_TOKENS:
            base_name_cores.add(core)
        if extract_doc_number(base_name):
            continue  # đã được phủ bởi base_doc_numbers
        sig = __doc_identity_signature(base_name)
        if sig:
            base_name_signatures.add(sig)

    # Nội dung nguồn nối lại (upper, bỏ khoảng trắng) để kiểm tra số hiệu có thật sự
    # xuất hiện hay không -> dùng cho guard chống hallucination theo NEO số hiệu.
    joined_content_nospace = (
        "".join(full_content_list).upper().replace(" ", "")
        if full_content_list is not None else None
    )

    unique_referential = {}
    for doc in relationships.get('referential', []):
        # Loại tự dẫn chiếu, cụm mơ hồ, và mảnh không phải tên văn bản định danh được.
        if not __is_valid_document_name(doc):
            logger.warning("remove_invalid_document_name", action="filter_relationship_results", doc=doc, doc_type="referential")
            continue

        doc_number = extract_doc_number(doc)
        # Văn bản không có số hiệu rõ -> dedup theo tên chuẩn hóa để không gộp nhầm
        # hai văn bản khác nhau cùng thiếu số hiệu.
        dedup_key = doc_number if doc_number else __normalize_name(doc)

        # Bỏ nếu là chính văn bản gốc
        if doc_number and doc_number == source_doc_number:
            logger.warning("remove_self_reference_invalid", action="filter_relationship_results", doc=doc, doc_type="referential")
            continue

        # Bỏ nếu đã thuộc nhóm base (ưu tiên giữ ở base)
        if doc_number and doc_number in base_doc_numbers:
            logger.warning("remove_base_duplicate_invalid", action="filter_relationship_results", doc=doc, doc_type="referential")
            continue

        # Văn bản LUẬT không số hiệu nhưng trùng định danh (tên lõi + năm) với một
        # văn bản căn cứ -> chính là căn cứ ghi khác cách -> loại khỏi referential.
        if not doc_number and base_name_signatures:
            sig = __doc_identity_signature(doc)
            if sig and sig in base_name_signatures:
                logger.warning("remove_base_duplicate_invalid", action="filter_relationship_results", doc=doc, doc_type="referential")
                continue

        # Văn bản không số hiệu trùng TÊN LÕI với một văn bản căn cứ (kể cả khi base
        # ghi kèm số hiệu/ngày tháng còn referential chỉ ghi tên trần) -> là căn cứ
        # ghi gọn lại -> loại. Chỉ áp cho item KHÔNG số hiệu để tránh khử nhầm.
        if not doc_number and base_name_cores:
            if __name_core(doc) in base_name_cores:
                logger.warning("remove_base_duplicate_invalid", action="filter_relationship_results", doc=doc, doc_type="referential")
                continue

        # Chống hallucination theo NEO:
        # - VB có số hiệu: chỉ cần SỐ HIỆU xuất hiện trong nguồn. LLM thường bổ sung
        #   trích yếu đầy đủ (đúng) nhưng không liền mạch trong văn bản -> KHÔNG so khớp
        #   cả chuỗi (sẽ giết nhầm). Hallucination thật (số hiệu bịa) vẫn bị loại vì
        #   số hiệu không có trong nguồn.
        # - VB không số hiệu: yêu cầu tên xuất hiện nguyên văn trong nguồn.
        if full_content_list is not None:
            if doc_number:
                if doc_number.replace(" ", "") not in joined_content_nospace:
                    logger.warning("remove_hallucinated_document_invalid", action="filter_relationship_results", doc=doc, doc_type="referential")
                    continue
            elif not any(doc in content for content in full_content_list):
                logger.warning("remove_hallucinated_document_invalid", action="filter_relationship_results", doc=doc, doc_type="referential")
                continue

        # Loại văn bản chỉ xuất hiện trong ngữ cảnh HIỆN TRẠNG/LỊCH SỬ THỤ HƯỞNG
        # ("đang/đã/được/thôi hưởng ... theo <văn bản>") -> không phải dẫn chiếu áp dụng.
        # KHÔNG áp dụng cho văn bản đã được bộ trích deterministic xác nhận (protected),
        # vì những văn bản đó đứng sau động từ áp dụng thật ("điều chỉnh theo"...).
        if (doc_number not in protected_numbers and joined_content_lower is not None):
            ent_needle = __entitlement_needle(doc, doc_number)
            if ent_needle and __in_entitlement_context(ent_needle, joined_content_lower):
                logger.warning("remove_entitlement_context_invalid", action="filter_relationship_results", doc=doc, doc_type="referential")
                continue

        # Chống trùng: nếu đã có khóa này, GIỮ LẠI tên ĐẦY ĐỦ hơn (dài hơn).
        # LLM có thể trả cùng một văn bản ở nhiều dạng (ngắn "Nghị định số 145/2020/NĐ-CP"
        # và đầy đủ "...ngày ... của Chính phủ quy định ...") -> phải giữ bản đầy đủ,
        # không để bản rút gọn gặp trước thắng.
        if dedup_key in unique_referential:
            if len(doc) > len(unique_referential[dedup_key]):
                logger.warning("remove_duplicate_document_invalid", action="filter_relationship_results", doc=unique_referential[dedup_key], doc_type="referential")
                unique_referential[dedup_key] = doc
            else:
                logger.warning("remove_duplicate_document_invalid", action="filter_relationship_results", doc=doc, doc_type="referential")
            continue

        unique_referential[dedup_key] = doc

    return {
        'referential': list(unique_referential.values())
    }


async def extract_relationship_referential(segments, document_name, client: httpx.AsyncClient, semaphore: asyncio.Semaphore, base_doc_numbers: Optional[Set[str]] = None, base_names: Optional[List[str]] = None, document_content: Optional[str] = None):
    '''
        Trích xuất mối quan hệ dẫn chiếu, áp dụng

        document_content: toàn văn văn bản (gồm cả PHỤ LỤC/BIỂU MẪU không nằm trong
        `segments`) -> dùng cho bộ trích deterministic bổ trợ và làm NEO chống
        hallucination, để bắt các văn bản dẫn chiếu chỉ xuất hiện ở phụ lục.
    '''
    relationships = {
        'referential': []
    }

    # Lưu lại nội dung điều khoản để guard chống hallucination ở bước hậu xử lý.
    full_content_list = []
    for segment in segments:
        article_title = segment['article_title']
        article_content = remove_reference(segment['article_content'])
        full_content_list.append(f"{article_title}\n{article_content}")
    # Toàn văn (kể cả phụ lục) cũng là nguồn hợp lệ cho guard chống hallucination.
    # Thêm cả bản RAW (chưa khử trích dẫn) để văn bản dẫn chiếu nằm trong khối trích
    # dẫn (mà remove_reference cắt) vẫn qua được neo chống hallucination.
    if document_content:
        full_content_list.append(remove_reference(document_content))
        full_content_list.append(document_content)

    async def process_seg(segment):
        article_title = segment['article_title']
        article_content = remove_reference(segment['article_content'])
        article_content = __clean_article_content(article_content)

        if not __is_referential_candidate(article_title, article_content):
            return None

        logger.debug("process_article_started", action="extract_relationship_referential", article_title=article_title, content_len=len(article_content))

        prompt = EXTRACT_RELATIONSHIP_REFERENTIAL_PROMPT.format(
            document_name=document_name,
            article_title=remove_article(article_title),
            article_content=remove_multi_underline(article_content)
        )
        try:
            async with semaphore:
                answer = await LLMs.llms_async(prompt, client=client)
            relationship_rs = LLMs.llms_post_process(answer)
            logger.info("extract_relationship_completed", action="extract_relationship_referential", relationship_rs=relationship_rs)
            return relationship_rs
        except Exception as e:
            logger.error("extract_relationship_failed", action="extract_relationship_referential", **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
            return None

    results = []
    batch_size = 20
    for i in range(0, len(segments), batch_size):
        chunk = segments[i : i + batch_size]
        logger.info("processing_batch",
                    start_index=i,
                    end_index=i + len(chunk),
                    total=len(segments))
        tasks = [process_seg(seg) for seg in chunk]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        results.extend(batch_results)

    for relationship_rs in results:
        if relationship_rs is not None and isinstance(relationship_rs, dict) and 'referential' in relationship_rs:
            relationships['referential'].extend(relationship_rs['referential'])

    # Bổ trợ deterministic: bắt văn bản dẫn chiếu theo cụm "áp dụng/điều chỉnh ...
    # theo <văn bản>" trên TOÀN VĂN (phụ lục/biểu mẫu mà LLM theo điều khoản bỏ sót).
    protected_numbers = set()
    if document_content:
        # Chạy rescue trên bản RAW (không khử trích dẫn): tín hiệu dẫn chiếu trong
        # phụ lục/biểu mẫu thường nằm trong khối trích dẫn bị remove_reference cắt.
        rescued = __rescue_referential_by_signal(document_content)
        if rescued:
            logger.info("referential_rescue_by_signal", action="extract_relationship_referential", count=len(rescued))
            relationships['referential'].extend(rescued)
            protected_numbers = {n for r in rescued if (n := extract_doc_number(r))}

    relationships = filter_relationship_results(
        relationships,
        document_name,
        base_doc_numbers=base_doc_numbers,
        full_content_list=full_content_list,
        base_names=base_names,
        protected_numbers=protected_numbers,
    )

    return relationships


async def main():
    import asyncio
    from pymongo import MongoClient
    from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig
    from core.v03.relationship_extractor.documents.base import extract_relationship_base

    client = get_mongo_client()

    db = client[MigrateConfig.MIGRATE_CORE_DB]

    documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]

    document_id = '426343'      # "5bd79bc7-0a02-42db-94e7-f17401142042"
    document = documents_collection.find_one({'doc_id': document_id})
    from core.v03.content_extractor import extract_components
    segments = extract_components(document['doc_content'])

    logger.info("process_document_started", action="__main__", doc_title=document['doc_title'], segment_count=len(segments))

    http_client = httpx.AsyncClient()
    semaphore = asyncio.Semaphore(10)

    # Chạy module base trước để lấy số hiệu văn bản căn cứ, truyền xuống referential
    # nhằm tái lập đúng điều kiện của extractor.py (loại văn bản đã thuộc nhóm base).
    base_relationships = await extract_relationship_base(
        content=document['doc_content'],
        document_name=document['doc_title'],
        client=http_client,
        semaphore=semaphore,
    ) or {}
    base_doc_numbers = {
        num for name in base_relationships.get('base', [])
        if (num := extract_doc_number(name))
    }
    logger.info("base_doc_numbers_computed", action="__main__", base_doc_numbers=list(base_doc_numbers))

    result = await extract_relationship_referential(
        segments=segments,
        document_name=document['doc_title'],
        client=http_client,
        semaphore=semaphore,
        base_doc_numbers=base_doc_numbers,
        base_names=base_relationships.get('base', []),
    )
    logger.info("extract_relationship_referential_successful", action="__main__", result=result)
    for idx, doc in enumerate(result.get('referential', []), 1):
        logger.info("show_referential_document_successful", action="__main__", index=idx, doc_name=doc)

    await http_client.aclose()

if __name__ == '__main__':
    asyncio.run(main())
