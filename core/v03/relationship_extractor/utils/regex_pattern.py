import re

# Regex pattern for extracting date in format "ngày X tháng Y năm Z"
DATE_PATTERN = re.compile(r"ngày (\d{1,2}) tháng (\d{1,2}) năm (\d{4})")

# Regex pattern for document number format 1, e.g., "01/2023/QĐ" or "01/QĐ-ABC"
DOCUMENT_NUMBER_PATTERN_1 = re.compile(r"\b\d{1,2}/\d{4}/[A-ZĐ0-9]+(?:-[A-ZĐ0-9]+)?\b|\b\d{1,2}/[A-ZĐ0-9]+-[A-ZĐ0-9]+\b")

# Regex pattern for document number format 2, e.g., "123/2023/QĐ"
DOCUMENT_NUMBER_PATTERN_2 = re.compile(r"\b\d{1,3}/\d{4}/[A-ZĐ0-9]+(?:-[A-ZĐ0-9]+)?\b")

# Regex pattern for removing article prefix, e.g., "Điều X."
ARTICLE_PATTERN = re.compile(r"^Điều\s+\d+\.?\s*")

# Regex pattern for extracting nested quotes content
QUOTES_PATTERN = r'[“](.*?)[”]'


DOCUMENT_TYPE = [
    'THÔNG TƯ LIÊN BỘ', 'THÔNG TƯ LIÊN NGÀNH', 'THÔNG TƯ LIÊN TỊCH', 'THÔNG TƯ LIÊN TỊCH',
    'NGHỊ ĐỊNH THƯ', 'NGHỊ QUYẾT', 'NGHỊ QUYẾT', 'QUYẾT ÐỊNH', 'QUYẾT ĐỊNH', 'QUYẾT ĐỊNH', 
    'HIẾN PHÁP', 'NGHỊ ĐỊNH', 'PHÁP LỆNH',    
    'SẮC LUẬT', 'SẮC LỆNH', 'THÔNG TƯ',  'LUẬT', 'LỆNH'
]

DOCUMENT_PART = ['Chương', 'Phần', 'Mục', 'Tiểu mục', 'Điều']