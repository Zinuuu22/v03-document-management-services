# ========================== #
# 1️⃣ Pattern cho split_clause_content
# ========================== #
SPLIT_CLAUSE_PATTERN = (
    r"(?=(?:^|\n)\s*\d+(?:\.\d+)*\.\s)"
)

CLAUSE_HEADER_BODY_PATTERN = (
    r"^\s*(\d+(?:\.\d+)*\.)\s*(.*?)(?:[:\n]|$)\s*(.*)$"
)

CLAUSE_SIMPLE_PATTERN = (
    r"^\s*(\d+(?:\.\d+)*\.\s*.*)$"
)

SUBITEM_SPLIT_PATTERN = (
    r"(?<=\n)(?=[a-zàáâãèéêìíòóôõùúăđĩũơư"
    r"ạảấầẩẫậắằẳẵặẹẻẽềểễệỉịọỏốồổỗộớờởỡợ"
    r"ụủứừửữựỳỵỷỹ]\))"
)

# ========================== #
# 2️⃣ Pattern cho detect_detail_regulation
# ========================== #
DETAIL_REGULATION_PATTERN = (
    r"(?<!\d)([2-9]|\d{2,})\. "
    r"(?P<agency>{agency_list}) quy định chi tiết "
    r"(?P<clause>.+?)(?P<article>Điều [\w\d]+|Điều này)"
)

DETAIL_REGULATION_SHORT_PATTERN = (
    r"(?<!\d)([2-9]|\d{2,})\. "
    r"(?P<agency>{agency_list}) quy định chi tiết "
    r"(?P<article>Điều [\w\d]+|Điều này)"
)


DETAIL_REGULATION_HEADER_PATTERN = (
    r"(?<!\d)([2-9]|\d{2,})\. "
)

CLAUSE_CAPTURE_PATTERN = (
    r"((\d+\..+?)(?=(\n\d+\.|\Z)))"
)

RELATIONSHIP_PATTERNS = {
    "Bãi bỏ": [
        r"(Bãi bỏ Điều|Bãi bỏ khoản|Bãi bỏ điểm|Bãi bỏ Thông tư|Bãi bỏ Nghị quyết|Bãi bỏ Nghị định|Bãi bỏ Luật|Bãi bỏ Pháp lệnh|Bãi bỏ Lệnh|Bãi bỏ Quyết định)(.*?)(?=\n|$)",
        r"(Bãi bỏ một số văn bản|Bãi bỏ các văn bản|Bãi bỏ toàn bộ|thay thế)(.*?)(?=\n|$)",
        r"(hết hiệu lực)(.*?)(?=\nĐiều\s*\d+|$)"
    ],
    "Sửa đổi, bổ sung": [
        r"(sửa đổi Điều|sửa đổi khoản|sửa đổi điểm|bổ sung Điều|bổ sung khoản|bổ sung điểm|sửa đổi, bổ sung Điều|sửa đổi, bổ sung khoản|sửa đổi, bổ sung điểm)(.*?)(?=\n)",
        r"(bãi bỏ khoản|bãi bỏ điểm|thay thế điểm|thay thế khoản|bổ sung vào Điều|bổ sung vào khoản|bổ sung vào điểm)(.*?)(?=\n|$)",
        r"(sửa đổi, bổ sung một số điều|sửa đổi, bổ sung một số khoản|sửa đổi, bổ sung một số điểm)(.*?)(?=$)",
        r"(bỏ cụm từ|thay thế từ|thay thế cụm từ)(.*?)(?=\n)"
    ],
    "Thay thế": [
        r"(Thay thế Điều|Thay thế|thay thế)(.*?)(?=\n|$)",
        r"(hết hiệu lực kể từ ngày)(.*?)(?=\n|$)"
    ]
}
