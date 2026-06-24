import re


LEGAL_DOCUMENT_TYPES = {'hiến pháp',
 'luật',
 'lệnh',
 'nghị quyết',
 'nghị quyết liên tịch',
 'nghị định',
 'pháp lệnh',
 'quyết định',
 'sắc luật',
 'sắc lệnh',
 'thông tư',
 'thông tư liên tịch',
 }

# LEGAL_DOCUMENT_PATTERN = r"^\d+/[12]\d{3}/[A-Z0-9]+$"
# LEGAL_DOCUMENT_PATTERN = r"^\d+/[12]\d{4}/[A-Z0-9\-]+$"
LEGAL_DOCUMENT_PATTERN = r"^\d+/\d{4}/.+$" 
    

# Regex patterns for effective date
REGEX_PATTERNS_EFFECTIVE_DATE = {
    "EFFECTIVE_DATE_REGEX_1": {
        "pattern": r"có hiệu lực(?: thi hành)? (?:kể )?từ ngày (\d{1,2}) tháng (\d{1,2}) năm (\d{4})",
        "description": "TH1: Hiệu lực từ ngày...tháng...năm..."
    },
    "EFFECTIVE_DATE_REGEX_2": {
        "pattern": r"có hiệu lực(?: thi hành)? (?:kể )?từ (?:ngày)? (\d{1,2})/(\d{1,2})/(\d{4})",
        "description": "TH2: Hiệu lực từ dd/mm/yyyy"
    },
    "EFFECTIVE_DATE_REGEX_3": {
        "pattern": r"có hiệu lực(?: thi hành)? (?:kể )?từ ngày (ký|ban hành)",
        "description": "TH3: Hiệu lực từ ngày ký/ban hành"
    },
    "EFFECTIVE_DATE_REGEX_4": {
        "pattern": r"hiệu lực thi hành sau (\d+) ngày(?:, kể từ ngày đăng Công báo)?",
        "description": "TH4: Hiệu lực sau X ngày (có thể từ ngày đăng Công báo)"
    },
    "EFFECTIVE_DATE_REGEX_5": {
        "pattern": r"có hiệu lực thi hành từ ngày thông qua",
        "description": "TH5: Hiệu lực từ ngày thông qua"
    },
    "EFFECTIVE_DATE_REGEX_5_adoption_date": {
        "pattern": r"thông qua ngày (?:(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})|(\d{1,2})/(\d{1,2})/(\d{4}))",
        "description": "TH5: Ngày thông qua"
    },
    "EFFECTIVE_DATE_REGEX_6": {
        "pattern": r"có hiệu lực(?: thi hành)? sau (\d+) ngày(?:, kể từ ngày ký)?",
        "description": "TH6: Hiệu lực sau X ngày kể từ ngày ký"
    },
    "EFFECTIVE_DATE_REGEX_7": {
        "pattern": r"có hiệu lực(?: thi hành)? sau (\d+)\s*(?:\((?:bảy|mười)\)\s*)?ngày(?:,)? kể từ ngày ký(?: ban hành)?",
        "description": "TH7: Hiệu lực sau X (chữ) ngày kể từ ngày ký ban hành"
    },
    "EFFECTIVE_DATE_REGEX_8": {
        "pattern": r"có hiệu lực(?: áp dụng)? (?:kể )?từ ngày (\d{1,2}) tháng (\d{1,2}) năm (\d{4})",
        "description": "TH8: Hiệu lực áp dụng từ ngày...tháng...năm..."
    }
}

# Regex patterns for issue date
REGEX_PATTERNS_ISSUE_DATE = {
    "ISSUE_DATE_REGEX": {
        "pattern": r",?\s*(?:ngày\s*)?(\d{1,2})\s*(?:tháng|[/-])\s*(\d{1,2})\s*(?:năm|[/-])\s*(\d{4})",
        "description": "Ngày ban hành: 'ngày...tháng...năm...' hoặc dạng số 'dd/mm/yyyy', 'dd-mm-yyyy'"
    }
}

# Regex patterns for document code
REGEX_PATTERN_DOCUMENT_CODE = {
    "DOCUMENT_CODE_REGEX": {
        "pattern": r"(?:Luật số|Pháp lệnh số|Nghị quyết số|Số)\s*(\d.*?)\n",
        "description": "Số hiệu văn bản"
    }
}

# Regex patterns for document type
REGEX_PATTERN_DOCUMENT_TYPE = {
    "DOCUMENT_TYPE_REGEX": {
        "pattern": r"\n(" + "|".join(map(re.escape, [
            'BỘ LUẬT', 'THÔNG TƯ LIÊN TỊCH', 'QUY NƯỚC VIỆT ĐỊNH', 'VĂN BẢN HỢP NHẤT', 'ĐIỀU ƯỚC QUỐC TẾ',
            'WTO_CAM KẾT VN', 'NGHỊ ĐỊNH THƯ', 'CHƯƠNG TRÌNH', 'VĂN BẢN KHÁC', 'BÁO CÁO THẨM TRA',
            'HƯỚNG DẪN TẠM THỜI', 'VĂN BẢN WTO', 'WTO_VĂN BẢN', 'NGHỊ QUYẾT', 'QUYẾT ĐỊNH', 'CÔNG ĐIỆN KHẨN',
            'THỎA THUẬN', 'CÔNG ĐIỆN', 'HIẾN PHÁP', 'HIỆP ĐỊNH', 'HƯỚNG DẪN', 'NGHỊ ĐỊNH', 'PHÁP LỆNH',
            'NGHỊ ĐỊNH LIÊN BỘ', 'QUY CHẾ PHỐI HỢP', 'PHƯƠNG ÁN', 'THÔNG BÁO', 'THÔNG TRI', 'ĐIỆN KHẨN',
            'CÔNG ƯỚC', 'KẾ HOẠCH', 'HƯỚNG DẪN LIÊN NGÀNH', 'KẾT LUẬN THANH TRA', 'KẾT LUẬN KIỂM TRA', 'KẾT LUẬN',
            'QUY ĐỊNH', 'SẮC LUẬT', 'SẮC LỆNH', 'THÔNG TƯ', 'TỜ TRÌNH', 'ĐIỀU ƯỚC', 'CHƯƠNG TRÌNH HÀNH ĐỘNG',
            'HIỆP ĐỊNH KHUNG', 'BÁO CÁO', 'CHỈ THỊ', 'CÔNG BỐ', 'QUY CHẾ', 'ĐIỀU LỆ', 'LUẬT', 'LỆNH',
            'QUYẾT ĐỊNH ĐÍNH CHÍNH', 'HƯỚNG DẪN BỔ SUNG'
        ])) + r")\b",
        "description": "Tìm loại văn bản trong nội dung (ví dụ: NGHỊ ĐỊNH, THÔNG TƯ, ...)"
    }
}

# Document code to type mapping
DOCUMENT_CODE_TO_TYPE_MAPPING = {
    "l-ctn": {
        "document_type": "Lệnh",
        "description": "Lệnh (ví dụ: l-ctn)"
    },
    "nqlt-": {
        "document_type": "NGHỊ QUYẾT LIÊN TỊCH",
        "description": "Nghị quyết liên tịch (ví dụ: nqlt-)"
    },
    "ttlb": {
        "document_type": "Thông tư liên tịch",
        "description": "Thông tư liên tịch (ví dụ: ttlb)"
    },
    "tt/lb": {
        "document_type": "Thông tư liên tịch",
        "description": "Thông tư liên tịch (ví dụ: tt/lb)"
    },
    "tt-lb": {
        "document_type": "Thông tư liên tịch",
        "description": "Thông tư liên tịch (ví dụ: tt-lb)"
    },
    "ttln": {
        "document_type": "Thông tư liên tịch",
        "description": "Thông tư liên ngành (ví dụ: ttln)"
    },
    "tt/ln": {
        "document_type": "Thông tư liên tịch",
        "description": "Thông tư liên ngành (ví dụ: tt/ln)"
    },
    "tt-ln": {
        "document_type": "Thông tư liên tịch",
        "description": "Thông tư liên ngành (ví dụ: tt-ln)"
    },
    "ttlt": {
        "document_type": "Thông tư liên tịch",
        "description": "Thông tư liên tịch (ví dụ: ttlt)"
    },
    "nđ-": {
        "document_type": "Nghị định",
        "description": "Nghị định (ví dụ: nđ-)"
    },
    "nđ/": {
        "document_type": "Nghị định",
        "description": "Nghị định (ví dụ: nđ/)"
    },
    "nq-": {
        "document_type": "Nghị quyết",
        "description": "Nghị quyết (ví dụ: nq-)"
    },
    "nq/": {
        "document_type": "Nghị quyết",
        "description": "Nghị quyết (ví dụ: nq/)"
    },
    "qđ-": {
        "document_type": "Quyết định",
        "description": "Quyết định (ví dụ: qđ-)"
    },
    "qđ/": {
        "document_type": "Quyết định",
        "description": "Quyết định (ví dụ: qđ/)"
    },
    "/bc": {
        "document_type": "Báo cáo",
        "description": "Báo cáo (ví dụ: /bc)"
    },
    "/ct": {
        "document_type": "Chỉ thị",
        "description": "Chỉ thị (ví dụ: /ct)"
    },
    "tt-": {
        "document_type": "Thông tư",
        "description": "Thông tư (ví dụ: tt-)"
    },
    "tt/": {
        "document_type": "Thông tư",
        "description": "Thông tư (ví dụ: tt/)"
    }
}

# Regex patterns for agency
REGEX_PATTERNS_AGENCY = {
    "AGENCY_REGEX_CTN": {
        "pattern": r"CTN",
        "agency": "Chủ tịch nước",
        "description": "Cơ quan ban hành: Chủ tịch nước"
    },
    "AGENCY_REGEX_HĐTP": {
        "pattern": r"HĐTP",
        "agency": "Hội đồng Thẩm phán Tòa án nhân dân tối cao",
        "description": "Cơ quan ban hành: Hội đồng Thẩm phán Tòa án nhân dân tối cao"
    },
    "AGENCY_REGEX_NQLT_UBTVQH_CP_ĐCTUBTWMTTQVN": {
        "pattern": r"NQLT-UBTVQH\d+-CP-ĐCTUBTWMTTQVN",
        "agency": "Ủy ban thường vụ Quốc hội - Chính Phủ - Đoàn Công tác Ủy ban trung ương mặt trận tổ quốc Việt Nam",
        "description": "Cơ quan ban hành: Ủy ban thường vụ Quốc hội - Chính Phủ - Đoàn Công tác Ủy ban trung ương mặt trận tổ quốc Việt Nam"
    },
    "AGENCY_REGEX_CP_UBTWMTTQVN": {
        "pattern": r"CP-UBTWMTTQVN",
        "agency": "Chính phủ - Ủy ban trung ương mặt trận tổ quốc Việt Nam",
        "description": "Cơ quan ban hành: Chính phủ - Ủy ban trung ương mặt trận tổ quốc Việt Nam"
    },
    "AGENCY_REGEX_CP_ĐCTUBTƯMTTQVN": {
        "pattern": r"CP-ĐCTUBTƯMTTQVN",
        "agency": "Chính phủ - Đoàn công tác Uỷ ban trung ương mặt trận tổ quốc Việt Nam",
        "description": "Cơ quan ban hành: Chính phủ - Đoàn công tác Uỷ ban trung ương mặt trận tổ quốc Việt Nam"
    },
    "AGENCY_REGEX_TANDTC": {
        "pattern": r"TANDTC",
        "agency": "Tòa án nhân dân tối cao",
        "description": "Cơ quan ban hành: Tòa án nhân dân tối cao"
    },
    "AGENCY_REGEX_VKSTC": {
        "pattern": r"VKSTC",
        "agency": "Viện kiểm sát nhân dân tối cao",
        "description": "Cơ quan ban hành: Viện kiểm sát nhân dân tối cao"
    },
    "AGENCY_REGEX_BQP": {
        "pattern": r"BQP",
        "agency": "Bộ Quốc phòng",
        "description": "Cơ quan ban hành: Bộ Quốc phòng"
    },
    "AGENCY_REGEX_BCA": {
        "pattern": r"BCA",
        "agency": "Bộ Công an",
        "description": "Cơ quan ban hành: Bộ Công an"
    },
    "AGENCY_REGEX_BNG": {
        "pattern": r"BNG",
        "agency": "Bộ Ngoại giao",
        "description": "Cơ quan ban hành: Bộ Ngoại giao"
    },
    "AGENCY_REGEX_BNV": {
        "pattern": r"BNV",
        "agency": "Bộ Nội vụ",
        "description": "Cơ quan ban hành: Bộ Nội vụ"
    },
    "AGENCY_REGEX_BTP": {
        "pattern": r"BTP",
        "agency": "Bộ Tư pháp",
        "description": "Cơ quan ban hành: Bộ Tư pháp"
    },
    "AGENCY_REGEX_BKHĐT": {
        "pattern": r"BKHĐT",
        "agency": "Bộ Kế hoạch và Đầu tư",
        "description": "Cơ quan ban hành: Bộ Kế hoạch và Đầu tư"
    },
    "AGENCY_REGEX_BTC": {
        "pattern": r"BTC",
        "agency": "Bộ Tài chính",
        "description": "Cơ quan ban hành: Bộ Tài chính"
    },
    "AGENCY_REGEX_BCT": {
        "pattern": r"BCT",
        "agency": "Bộ Công Thương",
        "description": "Cơ quan ban hành: Bộ Công Thương"
    },
    "AGENCY_REGEX_BNNPTNT": {
        "pattern": r"BNNPTNT",
        "agency": "Bộ Nông nghiệp và Phát triển nông thôn",
        "description": "Cơ quan ban hành: Bộ Nông nghiệp và Phát triển nông thôn"
    },
    "AGENCY_REGEX_BGTVT": {
        "pattern": r"BGTVT",
        "agency": "Bộ Giao thông vận tải",
        "description": "Cơ quan ban hành: Bộ Giao thông vận tải"
    },
    "AGENCY_REGEX_BXD": {
        "pattern": r"BXD",
        "agency": "Bộ Xây dựng",
        "description": "Cơ quan ban hành: Bộ Xây dựng"
    },
    "AGENCY_REGEX_BTNMT": {
        "pattern": r"BTNMT",
        "agency": "Bộ Tài nguyên và Môi trường",
        "description": "Cơ quan ban hành: Bộ Tài nguyên và Môi trường"
    },
    "AGENCY_REGEX_BTTTT": {
        "pattern": r"BTTTT",
        "agency": "Bộ Thông tin và Truyền thông",
        "description": "Cơ quan ban hành: Bộ Thông tin và Truyền thông"
    },
    "AGENCY_REGEX_BLĐTBXH": {
        "pattern": r"BLĐTBXH",
        "agency": "Bộ Lao động - Thương binh và Xã hội",
        "description": "Cơ quan ban hành: Bộ Lao động - Thương binh và Xã hội"
    },
    "AGENCY_REGEX_BVHTTDL": {
        "pattern": r"BVHTTDL",
        "agency": "Bộ Văn hóa, Thể thao và Du lịch",
        "description": "Cơ quan ban hành: Bộ Văn hóa, Thể thao và Du lịch"
    },
    "AGENCY_REGEX_BKHCN": {
        "pattern": r"BKHCN",
        "agency": "Bộ Khoa học và Công nghệ",
        "description": "Cơ quan ban hành: Bộ Khoa học và Công nghệ"
    },
    "AGENCY_REGEX_BGDĐT": {
        "pattern": r"BGDĐT",
        "agency": "Bộ Giáo dục và Đào tạo",
        "description": "Cơ quan ban hành: Bộ Giáo dục và Đào tạo"
    },
    "AGENCY_REGEX_BYT": {
        "pattern": r"BYT",
        "agency": "Bộ Y tế",
        "description": "Cơ quan ban hành: Bộ Y tế"
    },
    "AGENCY_REGEX_UBDT": {
        "pattern": r"UBDT",
        "agency": "Ủy ban Dân tộc",
        "description": "Cơ quan ban hành: Ủy ban Dân tộc"
    },
    "AGENCY_REGEX_NHNN": {
        "pattern": r"NHNN",
        "agency": "Ngân hàng Nhà nước Việt Nam",
        "description": "Cơ quan ban hành: Ngân hàng Nhà nước Việt Nam"
    },
    "AGENCY_REGEX_TTCP": {
        "pattern": r"TTCP",
        "agency": "Thanh tra Chính phủ",
        "description": "Cơ quan ban hành: Thanh tra Chính phủ"
    },
    "AGENCY_REGEX_VPCP": {
        "pattern": r"VPCP",
        "agency": "Văn phòng Chính phủ",
        "description": "Cơ quan ban hành: Văn phòng Chính phủ"
    },
    "AGENCY_REGEX_TTg": {
        "pattern": r"TTg",
        "agency": "Thủ tướng Chính phủ",
        "description": "Cơ quan ban hành: Thủ tướng Chính phủ"
    },
    "AGENCY_REGEX_KTNN": {
        "pattern": r"KTNN",
        "agency": "Kiểm toán nhà nước",
        "description": "Cơ quan ban hành: Kiểm toán nhà nước"
    },
    "AGENCY_REGEX_TCHQ": {
        "pattern": r"TCHQ",
        "agency": "Tổng cục Hải quan",
        "description": "Cơ quan ban hành: Tổng cục Hải quan"
    },
    "AGENCY_REGEX_VPQH": {
        "pattern": r"VPQH",
        "agency": "Văn phòng Quốc hội",
        "description": "Cơ quan ban hành: Văn phòng Quốc hội"
    },
    "AGENCY_REGEX_VPCTN": {
        "pattern": r"VPCTN",
        "agency": "Văn phòng Chủ tịch nước",
        "description": "Cơ quan ban hành: Văn phòng Chủ tịch nước"
    },
    "AGENCY_REGEX_HLHPNVN": {
        "pattern": r"HLHPNVN",
        "agency": "Hội Liên hiệp Phụ nữ Việt Nam",
        "description": "Cơ quan ban hành: Hội Liên hiệp Phụ nữ Việt Nam"
    },
    "AGENCY_REGEX_ĐTNCSHCM": {
        "pattern": r"ĐTNCSHCM",
        "agency": "Trung ương Đoàn Thanh niên Cộng sản Hồ Chí Minh",
        "description": "Cơ quan ban hành: Trung ương Đoàn Thanh niên Cộng sản Hồ Chí Minh"
    },
    "AGENCY_REGEX_MTTQ": {
        "pattern": r"MTTQ",
        "agency": "Ủy ban Trung ương Mặt trận Tổ quốc Việt Nam",
        "description": "Cơ quan ban hành: Ủy ban Trung ương Mặt trận Tổ quốc Việt Nam"
    },
    "AGENCY_REGEX_LMHTX": {
        "pattern": r"LMHTX",
        "agency": "Liên minh Hợp tác xã Việt Nam",
        "description": "Cơ quan ban hành: Liên minh Hợp tác xã Việt Nam"
    },
    "AGENCY_REGEX_HND": {
        "pattern": r"HND",
        "agency": "Hội Nông dân Việt Nam",
        "description": "Cơ quan ban hành: Hội Nông dân Việt Nam"
    },
    "AGENCY_REGEX_HCCB": {
        "pattern": r"HCCB",
        "agency": "Hội Cựu chiến binh Việt Nam",
        "description": "Cơ quan ban hành: Hội Cựu chiến binh Việt Nam"
    },
    "AGENCY_REGEX_QGHN": {
        "pattern": r"QGHN",
        "agency": "Đại học Quốc gia Hà Nội",
        "description": "Cơ quan ban hành: Đại học Quốc gia Hà Nội"
    },
    "AGENCY_REGEX_QGHCM": {
        "pattern": r"QGHCM",
        "agency": "Đại học Quốc gia TP. HCM",
        "description": "Cơ quan ban hành: Đại học Quốc gia TP. HCM"
    },
    "AGENCY_REGEX_TTXVN": {
        "pattern": r"TTXVN",
        "agency": "Thông tấn xã Việt Nam",
        "description": "Cơ quan ban hành: Thông tấn xã Việt Nam"
    },
    "AGENCY_REGEX_THVN": {
        "pattern": r"THVN",
        "agency": "Đài Truyền hình Việt Nam",
        "description": "Cơ quan ban hành: Đài Truyền hình Việt Nam"
    },
    "AGENCY_REGEX_TNVN": {
        "pattern": r"TNVN",
        "agency": "Đài Tiếng nói Việt Nam",
        "description": "Cơ quan ban hành: Đài Tiếng nói Việt Nam"
    },
    "AGENCY_REGEX_KHCNVN": {
        "pattern": r"KHCNVN",
        "agency": "Viện Khoa học và Công nghệ Việt Nam",
        "description": "Cơ quan ban hành: Viện Khoa học và Công nghệ Việt Nam"
    },
    "AGENCY_REGEX_KHXHVN": {
        "pattern": r"KHXHVN",
        "agency": "Viện Khoa học Xã hội Việt Nam",
        "description": "Cơ quan ban hành: Viện Khoa học Xã hội Việt Nam"
    },
    "AGENCY_REGEX_BQLHL": {
        "pattern": r"BQLHL",
        "agency": "Ban Quản lý Khu Công nghệ cao Hòa Lạc",
        "description": "Cơ quan ban hành: Ban Quản lý Khu Công nghệ cao Hòa Lạc"
    },
    "AGENCY_REGEX_BQLVHDL": {
        "pattern": r"BQLVHDL",
        "agency": "Ban Quản lý Làng Văn hóa - Du lịch",
        "description": "Cơ quan ban hành: Ban Quản lý Làng Văn hóa - Du lịch"
    },
    "AGENCY_REGEX_LĐLĐVN": {
        "pattern": r"LĐLĐVN",
        "agency": "Tổng Liên đoàn Lao động Việt Nam",
        "description": "Cơ quan ban hành: Tổng Liên đoàn Lao động Việt Nam"
    },
    "AGENCY_REGEX_BHXHVN": {
        "pattern": r"BHXHVN",
        "agency": "Bảo hiểm Xã hội Việt Nam",
        "description": "Cơ quan ban hành: Bảo hiểm Xã hội Việt Nam"
    },
    "AGENCY_REGEX_UBSMC": {
        "pattern": r"UBSMC",
        "agency": "Ủy ban Sông Mê Kông",
        "description": "Cơ quan ban hành: Ủy ban Sông Mê Kông"
    },
    "AGENCY_REGEX_BCĐCCHC": {
        "pattern": r"BCĐCCHC",
        "agency": "Ban Chỉ đạo Cải cách hành chính của Chính phủ",
        "description": "Cơ quan ban hành: Ban Chỉ đạo Cải cách hành chính của Chính phủ"
    },
    "AGENCY_REGEX_BC_BNN_VP": {
        "pattern": r"BC-BNN-VP",
        "agency": "Ban Chỉ đạo Cải cách hành chính của Chính phủ",
        "description": "Cơ quan ban hành: Ban Chỉ đạo Cải cách hành chính của Chính phủ"
    },
    "AGENCY_REGEX_CAAV": {
        "pattern": r"/CAAV",
        "agency": "Cục Hàng không Dân dụng Việt Nam",
        "description": "Cơ quan ban hành: Cục Hàng không Dân dụng Việt Nam"
    },
    "AGENCY_REGEX_BTGTW": {
        "pattern": r"BTGTW",
        "agency": "Ban Tuyên giáo Trung ương",
        "description": "Cơ quan ban hành: Ban Tuyên giáo Trung ương"
    },
    "AGENCY_REGEX_UBKTTW": {
        "pattern": r"UBKTTW",
        "agency": "Ủy ban Kiểm tra Trung ương",
        "description": "Cơ quan ban hành: Ủy ban Kiểm tra Trung ương"
    },
    "AGENCY_REGEX_WTO": {
        "pattern": r"WTO",
        "agency": "wto",
        "description": "Cơ quan ban hành: WTO"
    },
    "AGENCY_REGEX_VKSNDTC": {
        "pattern": r"VKSNDTC",
        "agency": "Viện Kiểm sát nhân dân tối cao",
        "description": "Cơ quan ban hành: Viện Kiểm sát nhân dân tối cao"
    }
}

# Regex patterns for position hierarchy
REGEX_PATTERNS_POSITION_HIERARCHY = {
    "POSITION_HIERARCHY_REGEX": {
        "pattern": r"\n[ \t]*(" + "|".join(map(re.escape, [
            'CHỦ TỊCH NƯỚC', 'THỦ TƯỚNG', 'PHÓ THỦ TƯỚNG', 'CHỦ TỊCH', 'PHÓ CHỦ TỊCH',
            'BỘ TRƯỞNG', 'THỨ TRƯỞNG', 'GIÁM ĐỐC', 'PHÓ GIÁM ĐỐC', 'TỔNG GIÁM ĐỐC',
            'PHÓ TỔNG GIÁM ĐỐC', 'CỤC TRƯỞNG', 'PHÓ CỤC TRƯỞNG', 'CHI CỤC TRƯỞNG',
            'PHÓ CHI CỤC TRƯỞNG', 'TRƯỞNG PHÒNG', 'PHÓ TRƯỞNG PHÒNG', 'TRƯỞNG BAN',
            'PHÓ TRƯỞNG BAN', 'THƯ KÝ', 'TRỢ LÝ', 'KIỂM SÁT VIÊN', 'THỐNG ĐỐC',
            'PHÓ THỐNG ĐỐC', 'TỔNG KIỂM TOÁN', 'PHÓ TỔNG KIỂM TOÁN', 'CHỦ NHIỆM',
            'PHÓ CHỦ NHIỆM', 'VIỆN TRƯỞNG', 'PHÓ VIỆN TRƯỞNG', 'CHÁNH ÁN', 'PHÓ CHÁNH ÁN',
            'TỔNG KIỂM TOÁN NHÀ NƯỚC', 'PHÓ TỔNG KIỂM TOÁN NHÀ NƯỚC', 'TỔNG THANH TRA',
            'PHÓ TỔNG THANH TRA', 'CHÁNH VĂN PHÒNG', 'CHỦ TỊCH', 'CHỦ TỊCH QUỐC HỘI', 'PHÓ CHỦ TỊCH QUỐC HỘI'
        ])) + r")\b",
        "description": "Tìm chức danh trong nội dung (ví dụ: CHỦ TỊCH NƯỚC, THỦ TƯỚNG, BỘ TRƯỞNG, ...)"
    }
}
