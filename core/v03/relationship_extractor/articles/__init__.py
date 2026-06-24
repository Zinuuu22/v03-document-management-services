from core.common.mongo.client import get_mongo_client
import json
import sys
import uuid
import re
import os
import unicodedata
from datetime import datetime
import time
import pandas as pd
import asyncio
import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from constants import LLMsConfigExtractRelationshipArticle
from core.common.llms import LLMs
from core.v03.relationship_extractor.utils import convert_relationships_to_records
from core.v03.relationship_extractor.utils.regex_pattern import DOCUMENT_TYPE as _DOC_TYPE_WORDS

# Call LLMs
LLMs = LLMs(llms_config=LLMsConfigExtractRelationshipArticle)

# Load prompts from Markdown file and map them to relationship types
MD_FILE_PATH = f"{PROJECT_ROOT}/core/v03/relationship_extractor/utils/prompts_relationship_extractor_article.md"

def load_prompts_from_md(file_path):
    prompts = {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        prompt_sections = re.split(r'\n# Prompt \d+: ', content)[1:]  
        for section in prompt_sections:
            match = re.search(r'Trích xuất mối quan hệ ([^\n]+) từ điều luật', section)
            if match:
                rel_type = match.group(1).strip()
                prompts[rel_type] = f"# Prompt: {section.strip()}"
        return prompts
    except Exception as e:
        logger.error("load_prompts_failed", action="load_prompts_from_md", **{"error.code": "IO", "error.message": str(e)}, file_path=file_path, exc_info=True)
        return {}

# Load prompts once at module level
EXTRACT_RELATIONSHIP_PROMPTS = load_prompts_from_md(MD_FILE_PATH)

# Define updated relationship patterns with keywords included in evidence
RELATIONSHIP_PATTERNS = {
    "Dẫn chiếu": [
        r"(quy định tại Điều|quy định tại khoản|quy định tại điểm|được sửa đổi, bổ sung theo|theo các tiêu chí tại Điều|theo các tiêu chí tại khoản|theo các tiêu chí tại điểm|quy định tại các Điều|quy định tại các khoản|quy định tại các điểm|quy định tại một trong các điểm|nêu tại)(.*?)(?=\n|$)"
    ],

    "Sửa đổi, bổ sung": [
        r"(\.\sSửa đổi khoản|Sửa đổi điểm|Sửa đổi Điều|thay thế khoản|Thay thế khoản|thay thế điểm|Thay thế điểm|thay thế cụm từ|thay thế từ|Bổ sung cụm từ|Bổ sung Điều|Bổ sung điểm|Bổ sung khoản)(.*?)(?=$)"
    ],

    "Bãi bỏ": [
        r"(\.\sBãi bỏ Điều|Bãi bỏ khoản|Bãi bỏ điểm|Bãi bỏ|hết hiệu lực|Bỏ cụm từ)(.*?)(?=$)",
        r"((Các\s+)?Điều[s]?\s+[\d,\s và]+.*?hết hiệu lực(?: thi hành)?)"
    ],

    "Thay thế": [
        r"(Thay thế Điều|Thay thế một số Điều)(.*?)(?=\n|$)"
    ],

    "Hướng dẫn chi tiết": [
        r"(quy định chi tiết tại Điều|quy định chi tiết tại khoản|quy định chi tiết tại điểm|quy định chi tiết các Điều|quy định chi tiết các khoản|quy định chi tiết các điểm)(.*?)(?=$)"
    ]
}


def extract_number_of_article(text: str) -> str:
    match = re.search(r"Điều\s*\d+", text)
    return match.group(0) if match else ''


# ---------------------------------------------------------------------------
# Quote handling, context building, and cross-document filtering.
# Ported from the test_article_rel harness (validated against real documents):
#  - long quoted “…” bodies (newly inserted article text) are stripped before
#    detection so references inside them are ignored; short inline quotes stay;
#  - the LLM is fed the article TITLE + matched paragraph(s) as context, so an
#    amendment whose target document is named only in the article title resolves;
#  - only cross-document references to a real, DIFFERENT document at a concrete
#    Điều survive (self/internal refs and non-document labels are dropped).
# ---------------------------------------------------------------------------

_MAX_INLINE_QUOTE = 80  # “…” bodies up to this length are kept (e.g. cụm-từ replacements)


def _strip_long_quotes(text: str) -> str:
    """Remove only LONG quoted “…” bodies (new article text we don't extract from),
    keeping short inline quotes like 'thay thế cụm từ "X" bằng cụm từ "Y"'."""
    def repl(m):
        return m.group(0) if len(m.group(1)) <= _MAX_INLINE_QUOTE else " "
    return re.sub(r"“([^”]*)”", repl, text, flags=re.DOTALL)


def _normalize(text: str) -> str:
    """NFC, collapse whitespace, lowercase — for name/marker comparisons."""
    text = unicodedata.normalize("NFC", text or "")
    return re.sub(r"\s+", " ", text).strip().lower()


# "…này" self-markers: a reference to the current article/document, not another one.
_SELF_MARKER_RE = re.compile(
    r"\b(điều|khoản|điểm|mục|chương|phần|tiểu\s*mục)\s+này\b"
    r"|\b(thông\s*tư|nghị\s*định|nghị\s*quyết|pháp\s*lệnh|quyết\s*định|bộ\s*luật|"
    r"luật|hiến\s*pháp|văn\s*bản|lệnh|chỉ\s*thị|sắc\s*lệnh|sắc\s*luật)\s+này\b"
)


def is_same_document_ref(detail: dict, doc_title: str) -> bool:
    """A detail is a same-document (self/internal) reference — to be dropped — if it
    names no other document, names the current document, or its evidence uses a
    '…này' self-marker. Only references to a DIFFERENT named document survive."""
    name = _normalize(detail.get("detail_name", ""))
    if not name:                              # no external document named
        return True
    if name == _normalize(doc_title):         # names the current document
        return True
    evidence = _normalize(detail.get("detail_evidence", ""))
    return bool(_SELF_MARKER_RE.search(evidence))


# A valid detail_name must look like a legal DOCUMENT, not an appendix/section
# label (Phụ lục, Phần, Chương, Mục, Danh mục, Biểu mẫu, …): it must contain a
# document-type word or a document code/number pattern.
_DOC_NAME_TYPES = sorted(
    {t.lower() for t in _DOC_TYPE_WORDS}
    | {"bộ luật", "chỉ thị", "quy chế", "quy định", "điều lệ", "hiệp định",
       "công ước", "điều ước", "văn bản hợp nhất"},
    key=len, reverse=True,
)
_DOC_CODE_RE = re.compile(r"\d+\s*/\s*\d{2,4}|/\s*(tt|nđ|nd|qđ|qd|nq|pl|ct|sl|l)\b")


def is_valid_document_name(name: str) -> bool:
    """True if `name` looks like a real legal document (has a document-type word
    or a document code), False for appendix/section labels like 'Phụ lục 3'."""
    n = _normalize(name)
    if not n:
        return False
    if any(t in n for t in _DOC_NAME_TYPES):
        return True
    return bool(_DOC_CODE_RE.search(n))


def is_keepable_detail(detail: dict, doc_title: str) -> bool:
    """A detail survives only if it targets a real, DIFFERENT document at a concrete
    Điều: requires a non-empty detail_article and a resolvable, cross-document
    detail_name."""
    if not (detail.get("detail_article") or "").strip():
        return False
    if not is_valid_document_name(detail.get("detail_name", "")):
        return False
    return not is_same_document_ref(detail, doc_title)


def _context_for(text: str, title: str, start: int, end: int) -> str:
    """Context fed to the LLM for a match: the article title + the blank-line
    paragraph(s) the match span [start, end) overlaps. The title is always
    included because the amended/target document is frequently named only in the
    article title, not in the individual clause that the regex matched."""
    blocks = [
        (m.start(1), m.end(1), m.group(1).strip())
        for m in re.finditer(r"(.+?)(?:\n\s*\n|\Z)", text, re.DOTALL)
    ]
    selected = [b for s, e, b in blocks if s < end and e > start and b]
    body = "\n\n".join(selected) if selected else text[start:end].strip()
    title = (title or "").strip()
    if title and title not in body:
        return f"{title}\n\n{body}"
    return body



async def extract_relationship_article_async(content: str, doc_title: str, number_of_article: str, type_rel: str, client: httpx.AsyncClient, semaphore: asyncio.Semaphore):
    content = content.strip()
    doc_title = doc_title.strip()
    number_of_article = number_of_article.strip()
    type_rel = type_rel.strip()
    
    try:
        prompt = EXTRACT_RELATIONSHIP_PROMPTS[type_rel].format(
            content=content,
            doc_title=doc_title,
            number_of_article=number_of_article,
            type_rel=type_rel
        )
        logger.debug("prepare_llm_prompt", action="extract_relationship_article_async", prompt_len=len(prompt))
    except KeyError as e:
        logger.error("format_prompt_failed", action="extract_relationship_article_async", **{"error.code": "VAL", "error.message": str(e)}, type_rel=type_rel, exc_info=True)
        return [{"type": "Không có mối quan hệ", "article": "", "clause": "", "point": "", "name": "", "evidence": ""}]
    async with semaphore:
        response = await LLMs.llms_async(prompt, client=client)
    dictionary = LLMs.llms_post_process(response)
    return dictionary


def extract_relationship_article(content: str, doc_title: str, number_of_article: str, type_rel: str):
    content = content.strip()
    doc_title = doc_title.strip()
    number_of_article = number_of_article.strip()
    type_rel = type_rel.strip()
    
    try:
        prompt = EXTRACT_RELATIONSHIP_PROMPTS[type_rel].format(
            content=content,
            doc_title=doc_title,
            number_of_article=number_of_article,
            type_rel = type_rel
        )
        logger.debug("prepare_llm_prompt", action="extract_relationship_article", prompt_len=len(prompt))
    except KeyError as e:
        logger.error("format_prompt_failed", action="extract_relationship_article", **{"error.code": "VAL", "error.message": str(e)}, type_rel=type_rel, exc_info=True)
        return [{"type": "Không có mối quan hệ", "article": "", "clause": "", "point": "", "name": "", "evidence": ""}]
    
    response = LLMs.llms(prompt)
    dictionary = LLMs.llms_post_process(response)
    return dictionary

async def process_article_async(article: dict, doc_title: str, client: httpx.AsyncClient, semaphore: asyncio.Semaphore):
    results = []

    article_title = article['article_title']
    article_content = article['article_content']
    article_id = article['article_id']
    doc_id = article['doc_id']
    content_article = article_title + '\n' + article_content
    number_of_article = extract_number_of_article(article_title)

    results.append({
        "article_id": article_id,
        "doc_id": doc_id,
        "content": content_article,
        "relationships": []
    })

    # Remove only LONG quoted “…” bodies (newly inserted article text we don't
    # extract references from); keep short inline quotes (e.g. cụm-từ replacements).
    # Pre-filters and candidate detection run on this stripped text.
    work = _strip_long_quotes(content_article)
    logger.debug("prepare_article_content", action="process_article_async", article_id=article_id, content_len=len(work))

    legal_keywords = [
        'theo quy định tại', 'quy định tại', 'được sửa đổi, bổ sung theo',
        'bãi bỏ', 'chấm dứt hiệu lực', 'thay thế', 'sửa đổi', 'bổ sung', 'quy định chi tiết'
    ]
    has_legal_reference = any(keyword in work.lower() for keyword in legal_keywords) and (
        work.count('Điều') >= 1 or
        any(x in work for x in [
            'Hiến pháp', 'Bộ luật', 'Luật', 'Pháp lệnh', 'Lệnh', 'Nghị quyết', 'Nghị định', 'Thông tư'
        ])
    )

    if not has_legal_reference:
        logger.debug("article_skipped_no_legal_keywords", action="process_article_async", article_id=article_id)
        return results

    if re.search(r'\.{4,}', work):
        logger.debug("article_skipped_consecutive_dots", action="process_article_async", article_id=article_id)
        return results

    # Regex stage: locate candidates and build each one's CONTEXT (article title +
    # the paragraph(s) the match spans), so the LLM can attribute a relationship to
    # a document named only in the article title. De-dup by (type_rel, context) so
    # the same paragraph+type isn't sent to the LLM twice.
    title = article_title.strip()
    candidates = []
    seen = set()
    for type_rel, patterns in RELATIONSHIP_PATTERNS.items():
        for pattern in patterns:
            for m in re.finditer(pattern, work.lower(), re.DOTALL | re.IGNORECASE):
                evidence = "".join(g or "" for g in m.groups()[:2]).strip()
                if not evidence:
                    continue
                context = _context_for(work, title, m.start(), m.end())
                key = (type_rel, context)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append({"excerpt": evidence, "type_rel": type_rel, "context": context})

    if not candidates:
        return results

    logger.info("detect_relationships", action="process_article_async", count=len(candidates))

    async def _fetch_rel(cand):
        # `context` (title + paragraph) is sent to the LLM but NOT emitted in the
        # final relationship object — only excerpt/type_rel/details are kept.
        rel = {"excerpt": cand['excerpt'], "type_rel": cand['type_rel'], "details": []}
        try:
            llm_result = await extract_relationship_article_async(
                content=cand['context'],
                doc_title=doc_title,
                number_of_article=number_of_article,
                type_rel=cand['type_rel'],
                client=client,
                semaphore=semaphore
            )
            if isinstance(llm_result, dict):
                details = [llm_result]
            elif isinstance(llm_result, list):
                details = [d for d in llm_result if isinstance(d, dict)]
            else:
                details = []
            # Keep only cross-document refs to a real, different document at a Điều.
            rel['details'] = [d for d in details if is_keepable_detail(d, doc_title)]
        except Exception as e:
            logger.error("process_llm_failed", action="process_article_async", **{"error.code": "LLM", "error.message": str(e)}, article_id=article_id, type_rel=cand['type_rel'], exc_info=True)
            rel['error'] = f"LLM error: {str(e)}"
        return rel

    processed_details = []
    batch_size = 20
    for i in range(0, len(candidates), batch_size):
        chunk = candidates[i : i + batch_size]
        logger.info("processing_batch",
                    start_index=i,
                    end_index=i + len(chunk),
                    total=len(candidates))
        tasks = [_fetch_rel(cand) for cand in chunk]
        chunk_result = await asyncio.gather(*tasks)
        processed_details.extend(chunk_result)

    # Drop relationship entries left with no cross-document details (regex fired but
    # nothing survived) so the output isn't cluttered with empty candidates.
    results[0]['relationships'] = [r for r in processed_details if r.get("details")]

    return results

def filter_information(relationships: list):
    final_relationships = []
    relationship_raw = relationships[0].get('relationships', []) 
    for rel in relationship_raw:
        filtered_relationships = []
        for d in rel.get("details", []):
            if d.get("detail_evidence") == "" or d.get("detail_name") == "":
                continue

            if d.get('detail_part') == '' and d.get('detail_chapter') == '' and d.get('detail_section') == '' and d.get('detail_subsection') == '' and d.get('detail_article') == '' and d.get('detail_clause') == '' and d.get('detail_point') == '':
                continue

            logger.debug("filter_detail", action="filter_information", detail=d)
            type_llm = d.get("type_llm")
            evidence = (d.get("detail_evidence") or "").lower()

            if type_llm == "Sửa đổi, bổ sung":
                if 'sửa đổi' in evidence:
                    filtered_relationships.append(d)

            elif type_llm == "Thay thế":
                if 'thay thế' in evidence:
                    filtered_relationships.append(d)

            elif type_llm == "Bãi bỏ":
                if 'bãi bỏ' in evidence or 'thay thế' in evidence or 'hết hiệu lực' in evidence:
                    filtered_relationships.append(d)

            elif type_llm == "Bãi bỏ một phần":
                if 'bãi bỏ' in evidence:
                    filtered_relationships.append(d)

            elif type_llm == "Sửa đổi":
                if 'sửa đổi' in evidence or 'thay thế' in evidence or 'nội dung tương ứng tại':
                    filtered_relationships.append(d)

            elif type_llm == "Bổ sung":
                if 'bổ sung' in evidence:
                    filtered_relationships.append(d)

            elif type_llm == "Hướng dẫn chi tiết":
                if 'quy định chi tiết' in evidence:
                    filtered_relationships.append(d)
            elif type_llm == "Dẫn chiếu":
                if 'quy định tại' in evidence or 'nêu tại' in evidence:
                    filtered_relationships.append(d)
        final_relationships.append(filtered_relationships)
    return final_relationships
    

if __name__ == '__main__':
    from pymongo import MongoClient
    from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig

    # Connect to MongoDB
    client = get_mongo_client()
    db = client[MigrateConfig.MIGRATE_CORE_DB]
    law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
    law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
    law_relationship_article_collection = db[MongoDBCollectionConfig.LAW_REFERENCE_ARTICLE_COLLECTION_NAME]

    article_id = "374406f9-f807-4be9-a8e1-b28711109e0c"
    article = law_articles_collection.find_one({'article_id': article_id})
    if not article:
        article = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME].find_one({'article_id': article_id})
        if not article:
            logger.warning("article_not_found", action="__main__", article_id=article_id)
            exit()
    doc_title = law_documents_collection.find_one({'doc_id': article['doc_id']})['doc_title']

    relationships = process_article(article, doc_title)
    logger.info("process_relationships_successful", action="__main__", relationships=relationships)

    # convert_data = convert_relationships_to_records(relationships)
    # logger.info("data_converted", convert_data=convert_data)
