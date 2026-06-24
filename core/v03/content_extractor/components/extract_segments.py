from email import message
import uuid
import re
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.v03.content_extractor.utils import encapsulate_quotes, restore_segments, summarize_content
from core.common.elastic import ElasticSearcher
from core.v03.content_extractor.utils.regex_pattern import EXTRACT_SEGMENTS_PART_PATTERN, \
                                                        EXTRACT_SEGMENTS_CHAPTER_PATTERN, \
                                                        EXTRACT_SEGMENTS_SECTION_PATTERN, \
                                                        EXTRACT_SEGMENTS_SUB_SECTION_PATTERN, \
                                                        EXTRACT_SEGMENTS_SEGMENT_PATTERN_1, \
                                                        EXTRACT_SEGMENTS_SEGMENT_PATTERN_ARABIC, \
                                                        EXTRACT_SEGMENTS_SEGMENT_PATTERN_ROMAN, \
                                                        EXTRACT_SEGMENTS_TYPE_UNKNOWN, \
                                                        EXTRACT_SEGMENTS_SEGMENT_PATTERN_2


total_needs_check = 0
check_list = []

def __extract_main_components(content):
    parts = []
    matches = re.finditer(EXTRACT_SEGMENTS_PART_PATTERN, content, flags=re.S)
    for match in matches:
        parts.append({'text': match.group(1).strip(),
                        'index': match.start(1)})

    chapters = []
    matches = re.finditer(EXTRACT_SEGMENTS_CHAPTER_PATTERN, content, flags=re.S)
    for match in matches:
        chapters.append({'text': match.group(1).strip(),
                        'index': match.start(1)})

    sections = []
    matches = re.finditer(EXTRACT_SEGMENTS_SECTION_PATTERN, content, flags=re.S)
    for match in matches:
        sections.append({'text': match.group(1).strip(),
                        'index': match.start(1)})

    sub_sections = []
    matches = re.finditer(EXTRACT_SEGMENTS_SUB_SECTION_PATTERN, content, flags=re.S)
    for match in matches:
        sub_sections.append({'text': match.group(1).strip(),
                        'index': match.start(1)})

    return {
        'parts': parts,
        'chapters': chapters,
        'sections': sections,
        'sub_sections': sub_sections        
    }

    
def __get_component_info(segment_index, 
                    components):
    part, chapter, section, sub_section = '', '', '', '' 
    part_index = chapter_index = section_index = -1

    for _part in components['parts']:
        _part_index = _part['index']
        _part_text = _part['text']
        logger.debug("compare_part", action="__get_component_info", part_index=_part_index, segment_index=segment_index)
        if int(segment_index) > int(_part_index):
            part = _part_text
            part_index = _part_index

    for _chapter in components['chapters']:
        _chapter_index = _chapter['index']
        _chapter_text = _chapter['text']
        logger.debug("compare_subsection", action="__get_component_info", chapter_index=_chapter_index, segment_index=segment_index, part_index=part_index)
        if int(segment_index) > int(_chapter_index) and int(_chapter_index) > int(part_index):
            chapter = _chapter_text
            chapter_index = _chapter_index

    for _section in components['sections']:
        _section_index = _section['index']
        _section_text = _section['text']
        logger.debug("compare_subsection", action="__get_component_info", section_index=_section_index, segment_index=segment_index, chapter_index=chapter_index)
        if int(segment_index) > int(_section_index) and int(_section_index) > int(chapter_index):
            section = _section_text
            section_index = _section_index
    
    for _sub_section in components['sub_sections']:
        _sub_section_index = _sub_section['index']
        _sub_section_text = _sub_section['text']
        logger.debug("compare_subsection", action="__get_component_info", subsection_index=_sub_section_index, segment_index=segment_index, section_index=section_index)
        if int(segment_index) > int(_sub_section_index) and int(_sub_section_index) > int(section_index):
            sub_section = _sub_section_text
    
    return {
        'part': part,
        'chapter': chapter,
        'section': section,
        'sub_section': sub_section        
    }


def get_index_article(text):
    pattern = r"[ĐÐ]iều\s*(\d+)"
    matches = re.findall(pattern, text)
    if matches:
        return int(matches[0])
    return 0

def get_article_start_index(content, article_text):
    index = content.find(article_text)
    logger.debug("search_article_index", action="get_article_start_index", article_text_length=len(article_text), found_index=index)
    return index if index != -1 else None


    
def extract_segments(content, document_code=None):    

    brief_content = summarize_content(content)['brief_content']
    quote_dict = {}
    if "“" in brief_content and "”" in brief_content:
        brief_content, quote_dict = encapsulate_quotes(brief_content)
    main_components = __extract_main_components(content=brief_content)

    norm_segments = []        
    try:
        segments = []
        pattern_1_found = re.search(r"\n\s*[ĐÐ]iều\s*\d+\s*[\.\-:\n]", brief_content)
        pattern_2_found = re.search(r"\n\s*(\d+)\s*[\.\-:/]", brief_content)
        pattern_chapter_found = re.search(r"\n(Chương|CHƯƠNG)\s+([IVXLC]+|\d+)", brief_content)
        pattern_3_found = "LỆNH" in brief_content and "NAY CÔNG BỐ" in brief_content
        pattern_roman_found = re.search(r"\n[IVX]+\b", brief_content)

        if pattern_1_found:
            regex_to_use = EXTRACT_SEGMENTS_SEGMENT_PATTERN_1
            logger.debug("sellect_parttern", action="extract_segments", pattern="PATTERN_1", document_code=document_code)
        elif pattern_roman_found:
            if pattern_chapter_found:
                regex_to_use = EXTRACT_SEGMENTS_SEGMENT_PATTERN_ARABIC
                logger.debug("sellect_parttern", action="extract_segments", pattern="PATTERN_ARABIC_CHAPTER", document_code=document_code)
            else:
                regex_to_use = EXTRACT_SEGMENTS_SEGMENT_PATTERN_ROMAN
                logger.debug("sellect_parttern", action="extract_segments", pattern="PATTERN_ROMAN", document_code=document_code)
        elif pattern_2_found:
            regex_to_use = EXTRACT_SEGMENTS_SEGMENT_PATTERN_2
            logger.debug("sellect_parttern", action="extract_segments", pattern="PATTERN_2", document_code=document_code)
        elif pattern_3_found:
            regex_to_use = EXTRACT_SEGMENTS_TYPE_UNKNOWN
            logger.debug("sellect_parttern",  action="extract_segments" , pattern="PATTERN_3", document_code=document_code)
        else:
            global total_needs_check, check_list
            total_needs_check += 1
            if document_code:
                check_list.append(document_code)
            logger.warning("found_no_pattern", action="extract_segments", document_code=document_code, total_needs_check=total_needs_check)
            return norm_segments

        matches = re.finditer(regex_to_use, brief_content, flags=re.S)
        for match in matches:
            if quote_dict:
                text = restore_segments(match.group(1).strip(), quote_dict)
            else:
                text = match.group(1).strip()
            segments.append({'text': text,
                            'index': match.start(1)})

        brief_content = restore_segments(brief_content, quote_dict)
        
        for idx, segment in enumerate(segments):
            segment_text = segment['text']
            segment_title_index = segment_text.split("\n")[0]
            segment_index = get_article_start_index(content=brief_content, article_text=segment_title_index)


            # Extract title and content
            segment_text = segment_text.split('./.')[0]
            _components = segment_text.split('\n')
            article_title = _components[0]
            article_content = '\n'.join(_component for _component in _components[1:])

            # Find part, chapter, section and sub_section depend on
            info = __get_component_info(segment_index=segment_index, 
                                    components=main_components)

            norm_segments.append({
                "code": str(uuid.uuid4()),
                "document_code": document_code,
                "article_title": article_title,
                "article_content": article_content,
                "index": idx,
                "segment_index": segment_index,
                "created_at": None,
                "last_modified_at": None,
                'part': info['part'],
                'chapter': info['chapter'],
                'section': info['section'],
                'sub_section': info['sub_section'],
                "status": "ACTIVE"
            })
    except Exception as e:
        logger.error("extract_segments_failed", action="extract_segments", **{"error.code": "PARSE", "error.message": str(e)}, exc_info=True)
        
    return norm_segments


if __name__ == '__main__':
    doc_id = '10265'    
    elastic_searcher = ElasticSearcher()
    document_content = elastic_searcher.get_document_content(doc_id)  
    segments = extract_segments(document_content)
    logger.debug("extract_segments_output", action="extract_segments", segment_count=len(segments))