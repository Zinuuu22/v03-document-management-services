import re
import unicodedata
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.v03.content_extractor.utils.regex_pattern import EXTRACT_CONTENT_PATTERN
from core.common.elastic import ElasticSearcher

def normalize_content(text):
    '''
        Hàm chuẩn hóa nội dung và cắt ngắn
    '''
    text = unicodedata.normalize("NFC", text)
    #text = re.sub(r'ð', 'đ', text, flags=re.IGNORECASE)
    text = text.replace("\xa0", " ")
    text = text.replace("  ", " ")
    #text = text.replace(':', ' ')
    text = text.replace("\n \n \n", "\n")
    text = text.replace(' \n', '\n')
    text = text.replace('- ', '-')
    text = text.replace(' \r\n', '\n').strip()
    text = text.replace('\r\n', '\n').strip()
    text = text.replace('\r\n\t', '\n').strip()
    return text


def get_content_extract_v1(text: str) -> str:
    matches = re.findall(EXTRACT_CONTENT_PATTERN, text, re.DOTALL | re.IGNORECASE)
    logger.debug("found_content_blocks", action="get_content_extract_v1", method="v1", block_count=len(matches))
    return matches[0].strip() if matches else text.strip()


def get_content_extract_v2(text: str) -> str:
    split_keys = [
        '\nDANH MỤC MỘT SỐ BIỂU MẪU',
        '\nMỤC LỤC',
        '\nPHỤ LỤC',
        '\nDANH MỤC\n',
        '\nMẫu số',
        '\nTM.',
        '\nTM/',
        '\nKT.',
        '\n(Đã ký)',
        '\n./.',
        '\nNơi nhận'
    ]
    for key in split_keys:
        if key in text:
            logger.debug("found_content_cut_point", action="get_content_extract_v2", method="v2", cut_key=key.strip())
            return text.split(key)[0].strip()
    return text.strip()


def summarize_content(content: str) -> dict:
    content = normalize_content(content)

    appendix_keywords = [
        '\nPHỤ LỤC', '\nMỤC LỤC', '\nDANH MỤC MỘT SỐ BIỂU MẪU', '\nDANH MỤC BIỂU MẪU', '\nPHỤ LỤC 1'
        '\nBIỂU MẪU', '\nMẪU SỐ', '\nMẫu số'
    ]
    main_text_keywords = [
        '\nQUY ĐỊNH\n', '\nQUY ĐỊNH \n' '\nQUY CHẾ\n',
        '\nĐIỀU LỆ\n', '\nQCVN'
    ]

    has_appendix = any(k in content for k in appendix_keywords)
    has_main_text = any(k in content for k in main_text_keywords)

    if has_appendix and not has_main_text:
        doc_type = "TYPE_1"
        brief_content = get_content_extract_v2(content)

    elif not has_appendix and not has_main_text:
        doc_type = "TYPE_2"
        brief_content = get_content_extract_v2(content)

    elif has_main_text and not has_appendix:
        doc_type = "TYPE_3"
        brief_content = get_content_extract_v1(content)

    elif has_main_text and has_appendix:
        doc_type = "TYPE_4"
        cutoff_index = min(
            (content.find(k) for k in appendix_keywords if k in content),
            default=-1
        )
        main_part = content[:cutoff_index].strip() if cutoff_index != -1 else content
        brief_content = get_content_extract_v1(main_part)

    else:
        doc_type = "TYPE_5"
        brief_content = get_content_extract_v2(content)

    logger.debug("brief_content_classified", action="summarize_content", doc_type=doc_type)
    return {"type": doc_type, "brief_content": brief_content}


def encapsulate_quotes(text):
    """
        encapsulate quotes in text
    """
    quote_pattern = r'“[^”]*?”'
    quotes = re.findall(quote_pattern, text)
    quote_dict = {f"{{QUOTE_{i}}}" : quote for i, quote in enumerate(quotes)}
    
    for i, quote in enumerate(quotes):
        text = text.replace(quote, f"{{QUOTE_{i}}}")
    
    return text, quote_dict


def restore_segments(segment, quote_dict):
    """
        restore segments from quote_dict
    """
    restored_segment = segment
    for placeholder, quote in quote_dict.items():
        restored_segment = restored_segment.replace(placeholder, quote)
    
    return restored_segment.strip()


if __name__ == "__main__":
    id = '97287'
    elastic_searcher = ElasticSearcher()
    content = elastic_searcher.get_document_content(id)
    logger.info("retrieved_content", action="main", content_length=len(content))
    brief_content = summarize_content(content)
    logger.info("summarized_content", action="main", doc_type=brief_content.get("type"), brief_content_len=len(brief_content.get("brief_content", "")))