import re
import unicodedata

def get_brief_content(text, max_length=500):
    '''
        Hàm chuẩn hóa nội dung và cắt ngắn
    '''
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r'ð', 'đ', text, flags=re.IGNORECASE)
    text = text.replace("\xa0", " ")
    text = text.replace("  ", " ")
    text = text.replace(':', ' ')
    text = text.replace('- ', '-')
    text = text.replace('\r\n', '\n').strip()
    return text[:max_length]


def normalize_type(document_type: str) -> str:
    if document_type in ('ĐIỆN',):
        document_type = 'CÔNG ĐIỆN'
    elif document_type in ('THÔNG TƯ LIÊN BỘ', 'THÔNG TƯ LIÊN NGÀNH'):
        document_type = 'THÔNG TƯ LIÊN TỊCH'
    elif document_type in ('NGHỊ QUYẾT LIÊN BỘ', 'NGHỊ QUYẾT LIÊN NGÀNH'):
        document_type = 'NGHỊ QUYẾT LIÊN TỊCH'
    # Canonical casing for every path (Step 1 mapping outliers, Step 2 regex
    # captures, and the uppercase remaps above): first letter upper, rest lower.
    # Applied last so the uppercase alias checks above still match their inputs.
    if document_type:
        document_type = document_type[0].upper() + document_type[1:].lower()
    return document_type
