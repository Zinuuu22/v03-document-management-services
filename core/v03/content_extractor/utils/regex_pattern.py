# EXTRACT_SEGMENTS_PART_PATTERN = (
#     r"(?:(?<=\n)|^)"  
#     r"((Phần|PHẦN)\s[0-9IVXLCDM]+.*?)" 
#     r"(?=\n(Chương|CHƯƠNG|Mục|MỤC|TIỂU MỤC|Tiểu mục|Tiểu Mục|Điều|Ðiều))"  
# )

EXTRACT_SEGMENTS_PART_PATTERN = (
    r"(?:(?<=\n)|^)"
    r"((Phần|PHẦN)\s*(?:[0-9IVXLCDM]+|THỨ\s+[A-ZĐÂÊÔƯẠ-Ỵ]+).*?)"
    r"(?=\n(Chương|CHƯƠNG|Mục|MỤC|TIỂU MỤC|Tiểu mục|Tiểu Mục|Điều|Ðiều))"
)


EXTRACT_SEGMENTS_CHAPTER_PATTERN = (
    r"(?:(?<=\n)|^)"  
    r"((Chương|CHƯƠNG)\s[0-9IVXLCDM]+.*?)" 
    r"(?=\n((Chương|CHƯƠNG)\s[0-9IVXLCDM]+|Mục|MỤC|TIỂU MỤC|Tiểu mục|Tiểu Mục|Điều|Ðiều))"  
)

EXTRACT_SEGMENTS_SECTION_PATTERN = (
    r"(?:(?<=\n)|^)"  
    r"((Mục|MỤC)\s[0-9IVX]+.*?)" 
    r"(?=\n((Tiểu mục|Tiểu Mục|TIỂU MỤC|CHƯƠNG|Chương|Điều|Ðiều)\s[0-9IVX]+))"  
)

EXTRACT_SEGMENTS_SUB_SECTION_PATTERN = (
    r"(?:(?<=\n)|^)"  
    r"((Tiểu mục|TIỂU MỤC|Tiểu Mục)\s[0-9IVXLCDM]+.*?)" 
    r"(?=\n(Điều|Ðiều))"  
)

EXTRACT_SEGMENTS_SEGMENT_PATTERN_1 = (
    r"(\n\s*[ĐÐ]iều\s*\d+\s*\..*?|\n\s*[ĐÐ]iều\s*\d+\s*:.*?|\n\s*[ĐÐ]iều\s*\d+\s*-\s*.*?|\n\s*[ĐÐ]iều\s*\d+\s*:\s*.*?|(?:^|\n)([ĐÐ]iều\s*\d+\s*\n[\s\S]*?))"
    r"(?=(?:\n\s*[ĐÐ]iều\s*\d+\s*[\.\-:\n]|$|"
    r"./\n|\./\.|\n\s*PHỤ LỤC [IVX]+|\n\s*PHỤ LỤC \d+|\n\s*PHỤ LỤC|\n\s*Phụ lục [IVX]+|\n\s*Phụ lục \d+|\n\s*Phụ lục|"
    r"\nChương \d+|\nCHƯƠNG \d+|\nChương [IVX]+|\nCHƯƠNG [IVX]+|\nCHƯƠNG TRÌNH"
    r"\nQUI CHẾ|\nQUY ĐỊNH\n|\nQUY CHẾ\n|"
    r"\nCỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM\n|\n\(Đã ký\)|"
    r".\nMục \d+|.\nMỤC \d+|.\nTIỂU MỤC|.\nTiểu mục|.\nTiểu Mục|\nMục [IVX]+|\nMỤC [IVX]+"
    r"\nNơi nhận|\nKT\.|\nTM\.|\nTM/|\nT/M|\nMỤC LỤC|"
    r"\nCHỦ TỊCH NƯỚC|\nTHỦ TƯỚNG|\nPHÓ THỦ TƯỚNG|\nBỘ TRƯỞNG|\nTHỨ TRƯỞNG|\nCHỦ TỊCH|\nPHÓ CHỦ TỊCH|"
    r"\nTHỐNG ĐỐC|\nPHÓ THỐNG ĐỐC|\nTỔNG KIỂM TOÁN NHÀ NƯỚC|\nPHÓ TỔNG KIỂM TOÁN NHÀ NƯỚC|"
    r"\nTỔNG THANH TRA|\nPHÓ TỔNG THANH TRA|\nTỔNG KIỂM TOÁN|\nPHÓ TỔNG KIỂM TOÁN|"
    r"\nCHỦ NHIỆM|\nPHÓ CHỦ NHIỆM|\nCHÁNH ÁN))"
)

EXTRACT_SEGMENTS_SEGMENT_PATTERN_2 = (
    r"\n\s*((?:\d+(?!\.\d)|[IVX]+)\s*[\.\:\/-]\s*(?! \d+).*?)"  
    r"(?=\n\s*(?:\d+(?!\.\d)|[IVX]+)\s*[\.\:\/-]|\Z|"           
    r"\n\s*PHỤ LỤC(?: [IVX\d]+)?|"
    r"\n\s*Chương(?: [IVX\d]+)?|"
    r"\n\s*Mục(?: [IVX\d]+)?|"
    r"\n\s*Tiểu\s*mục|"
    r"\n\s*(QUY ĐỊNH|QUI CHẾ|MỤC LỤC|CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM)|"
    r"\n\s*(KT\.|TM\.|TM/|T/M)|"
    r"\n\s*(CHỦ TỊCH|PHÓ CHỦ TỊCH|THỦ TƯỚNG|PHÓ THỦ TƯỚNG|BỘ TRƯỞNG|THỨ TRƯỞNG|CHÁNH ÁN|TỔNG KIỂM TOÁN))"
)

EXTRACT_SEGMENTS_SEGMENT_PATTERN_ARABIC = (
    r"\n\s*(\d+(?!\.\d)\s*[\.\:\/\-]\s*(?! \d+).*?)"
    r"(?=\n\s*\d+(?!\.\d)\s*[\.\:\/\-]|\Z|"
    r"\n\s*PHỤ LỤC(?: [IVX\d]+)?|"
    r"\n\s*Chương(?: [IVX\d]+)?|"
    r"\n\s*Mục(?: [IVX\d]+)?|"
    r"\n\s*Tiểu\s*mục|"
    r"\n\s*(QUY ĐỊNH|QUI CHẾ|MỤC LỤC|CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM)|"
    r"\n\s*(KT\.|TM\.|TM/|T/M)|"
    r"\n\s*(CHỦ TỊCH|PHÓ CHỦ TỊCH|THỦ TƯỚNG|PHÓ THỦ TƯỚNG|BỘ TRƯỞNG|THỨ TRƯỞNG|CHÁNH ÁN|TỔNG KIỂM TOÁN))"
)

EXTRACT_SEGMENTS_SEGMENT_PATTERN_ROMAN = (
    r"\n\s*([IVX]+\s*[\.\:\/\-]\s*(?! \d+).*?)"
    r"(?=\n\s*[IVX]+\s*[\.\:\/\-]|\Z|"
    r"\n\s*PHỤ LỤC(?: [IVX\d]+)?|"
    r"\n\s*Chương(?: [IVX\d]+)?|"
    r"\n\s*Mục(?: [IVX\d]+)?|"
    r"\n\s*Tiểu\s*mục|"
    r"\n\s*(QUY ĐỊNH|QUI CHẾ|MỤC LỤC|CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM)|"
    r"\n\s*(KT\.|TM\.|TM/|T/M)|"
    r"\n\s*(CHỦ TỊCH|PHÓ CHỦ TỊCH|THỦ TƯỚNG|PHÓ THỦ TƯỚNG|BỘ TRƯỞNG|THỨ TRƯỞNG|CHÁNH ÁN|TỔNG KIỂM TOÁN))"
)





EXTRACT_SEGMENTS_TYPE_UNKNOWN = r"\n((?:NAY CÔNG BỐ|QUYẾT NGHỊ):?.*?)(?=\.\/\.|\nCHỦ TỊCH|\nQUYỀN CHỦ TỊCH|$)"

EXTRACT_SEGMENTS_TYPE_2_5 = r'(\n\s*(I{1,3}|IV|VI{0,3}|IX)\s*[-./]? .*?)(?=\n\s*(I{1,3}|IV|VI{0,3}|IX)\s*[-./]?|\./\.|\nNơi nhận:|KT\s*\.|TM\s*\.|\nCHỦ TỊCH|$)'


EXTRACT_CLAUDS_POINT_PATTERN =  r'(?:(?<=\n)|^)\s*[a-z]\) .*?(?=\n[a-z]\)|\Z)'
#EXTRACT_CLAUDS_CLAUD_PATTERN =  r'(?:(?<=\n)|^)\s*\d+\.\s*.*?(?=\n\d+\.\s*|$)'
EXTRACT_CLAUDS_CLAUD_PATTERN_1 = r'(?:(?<=\n)|^)\s*\d+\.(?!\d)\s*.*?(?=\n\d+\.(?!\d)\s*|$)'
EXTRACT_CLAUDS_CLAUD_PATTERN_2 = r'(?:(?<=\n)|^)\s*\d+\.\d+\s*.*?(?=\n\d+\.\d+\s*|$)'

EXTRACT_CLAUDS_REFERENCE_SAMPLE_PATTERN = r'\[REFERENCE_(\d+)\]'
EXTRACT_CLAUDS_REFERENCE_PATTERN = r'[“](.*?)[”]'

EXTRACT_CONTENT_PATTERN = r'^(.*?)(?=(?:(?:\r\n|\n\r|\n)\s*(?:PHỤ LỤC(?:\s+\d+|\s+[IVXLCDM]+)?|DANH MỤC MỘT SỐ BIỂU MẪU|QCVN|Mẫu số\s*\d+(?:\r\n|\n\r|\n)?))|$)'
