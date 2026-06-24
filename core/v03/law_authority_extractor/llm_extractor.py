"""
LLM-based law authority (nội dung giao quyền) extractor — round 1.5.

Pipeline (unchanged from round 1, hardened in 1.5):
- Regex pre-filter (`is_law_authority_candidate`) — now two-tier (strong/weak) — selects
  suspicious articles. The LLM is only invoked for candidates.
- LLM extracts delegation clauses (`generate_law_authorities_async`).
- Python hard-gates validate each item (`_validate_authority_item`): trace-back to article,
  action marker, agency present + traceable, reference-only rejection, optional semantic
  verifier flag.
- `compose_formal_records` builds records for the law_authority / law_authority_mapping schema.

LLM output schema (new):
  authority_content   — business summary (what article X delegates to whom to do what)
  authority_quotation — verbatim delegation clause from the article (the evidence)
  delegated_agencies  — agencies named in authority_quotation
  is_valid_authority  — boolean filter from LLM

Formal record schema (post-compose):
  law_authority:
    authority_content   — business summary (from LLM authority_content)
    authority_quotation — verbatim delegation clause (from LLM authority_quotation)

  law_authority_mapping:
    agency_id           — scalar string (one mapping record per authority–agency pair)

The legacy regex-only module (`extractor.py`) is left untouched as a fallback.
"""

import os
import sys
import json
from uuid import uuid4
from typing import List, Dict, Optional

import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import re
import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from dotenv import load_dotenv

ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
ENV_PROD_PATH = os.path.join(PROJECT_ROOT, ".env.prod")
_loaded_any = False
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    _loaded_any = True
if os.path.exists(ENV_PROD_PATH):
    load_dotenv(ENV_PROD_PATH)
    _loaded_any = True
if not _loaded_any:
    load_dotenv()

from core.common.llms import LLMs
from constants import LLMsConfigExtractRelationship
from core.v03.law_authority_extractor.utils import (
    read_prompt,
    local_now_str,
    collapse_whitespace,
    normalize_for_match,
    normalize_agency_key,
    is_near_substring,
    contains_any,
)


# Reuse the relationship-extraction LLM config (same endpoint social_extractor uses),
# so the module does not introduce new env vars / config classes.
LLMs = LLMs(llms_config=LLMsConfigExtractRelationship)

PROMPT_KEY = "law_authority_extractor"


# ---------------------------------------------------------------------------
# Regex pre-filter (two-tier)
# ---------------------------------------------------------------------------
# STRONG signals: specific enough to flag a candidate on their own.
STRONG_CANDIDATE_PATTERNS: List[str] = [
    r"quy\s*định\s+chi\s+tiết",
    r"hướng\s+dẫn\s+thi\s+hành",
    r"hướng\s+dẫn\s+thực\s+hiện",
    r"quy\s*định\s+cụ\s+thể",
    r"quy\s*định\s+trình\s+tự\s*,?\s*thủ\s+tục",
    r"quy\s*định\s+điều\s+kiện",
    r"quy\s*định\s+tiêu\s+chuẩn",
    r"ban\s+hành\s+quy\s+chế",
    r"ban\s+hành\s+quy\s+trình",
    r"ban\s+hành\s+biểu\s+mẫu",
    r"giao\s+Chính\s+phủ",
    r"giao\s+Thủ\s+tướng\s+Chính\s+phủ",
    r"giao\s+Bộ\s+trưởng",
    r"giao\s+Bộ\b",
    r"giao\s+Ủy\s+ban\s+nhân\s+dân",
    r"chủ\s+trì\s*,?\s*phối\s+hợp",
]

# WEAK signals: broad; only promote to candidate when an agency marker is nearby.
WEAK_CANDIDATE_PATTERNS: List[str] = [
    r"quy\s*định\s+về",
    r"phối\s+hợp\s+với",
    r"chịu\s+trách\s+nhiệm\s+thi\s+hành",
    r"chịu\s+trách\s+nhiệm\s+hướng\s+dẫn",
]

# Backward-compatible union (round 1 name kept for callers / debug).
AUTHORITY_CANDIDATE_PATTERNS: List[str] = STRONG_CANDIDATE_PATTERNS + WEAK_CANDIDATE_PATTERNS

_STRONG_REGEXES = [re.compile(p, flags=re.IGNORECASE | re.UNICODE) for p in STRONG_CANDIDATE_PATTERNS]
_WEAK_REGEXES = [re.compile(p, flags=re.IGNORECASE | re.UNICODE) for p in WEAK_CANDIDATE_PATTERNS]
_ALL_CANDIDATE_REGEXES = _STRONG_REGEXES + _WEAK_REGEXES

# Built-in agency markers (used to promote weak signals when caller passes no agency list).
AGENCY_MARKER_PATTERNS: List[str] = [
    r"Chính\s+phủ",
    r"Thủ\s+tướng\s+Chính\s+phủ",
    r"Bộ\s+trưởng",
    r"Bộ\s+[A-ZÀ-Ỹ]",          # "Bộ Y tế", "Bộ Tư pháp", ...
    r"Ủy\s+ban\s+nhân\s+dân",
    r"Hội\s+đồng\s+nhân\s+dân",
    r"Tòa\s+án\s+nhân\s+dân\s+tối\s+cao",
    r"Viện\s+kiểm\s+sát\s+nhân\s+dân\s+tối\s+cao",
]
_AGENCY_MARKER_REGEXES = [re.compile(p, flags=re.UNICODE) for p in AGENCY_MARKER_PATTERNS]

# Action markers (diacritic-free, lowercase) a real delegation sentence must contain.
ACTION_MARKERS: List[str] = [
    "quy dinh",
    "huong dan",
    "giao",
    "ban hanh",
    "chu tri",
    "phoi hop",
    "chiu trach nhiem",
]

# Active-delegation verbs (diacritic-free) — agency must be paired with one of these.
_ACTIVE_VERBS: List[str] = ["quy dinh", "huong dan", "ban hanh", "chu tri", "chiu trach nhiem"]

# Secondary safety net: normalized prefixes that are clearly normative/enumeration content.
NORMATIVE_PREFIX_BLOCKLIST: List[str] = [
    "dang tat bao gom",
    "nguoi khuyet tat duoc chia",
    "den ngay",
]

# Reference-only (viện dẫn) patterns (diacritic-free) — these are NOT delegation by themselves.
REFERENCE_ONLY_PATTERNS: List[str] = [
    "theo quy dinh cua",
    "theo quy dinh tai",
    "theo quy dinh phap luat",
    "theo quy dinh cua phap luat",
    "thuc hien theo quy dinh",
    "duoc thuc hien theo quy dinh",
    "phu hop voi quy dinh",
    "can cu quy dinh",
]

# Generic agency terms (normalized) that must never drive a fuzzy match or auto-create.
GENERIC_AGENCY_TERMS = {
    "bo",
    "bo truong",
    "uy ban nhan dan",
    "hoi dong nhan dan",
    "co quan",
    "co quan nha nuoc",
    "co quan co tham quyen",
    "chinh quyen dia phuong",
    "to chuc",
    "ca nhan",
}

# ---------------------------------------------------------------------------
# Shared normalization for agency blocking
# ---------------------------------------------------------------------------
# LLM sometimes returns agency names with leading coordination conjunctions:
#   "và các Bộ, cơ quan ngang Bộ có liên quan"
#   "phối hợp với các cơ quan liên quan"
# Strip these before checking denylist/patterns so the core phrase is matched.
_CONJUNCTION_PREFIX_RE = re.compile(
    r"^(?:phoi hop voi |chu tri phoi hop voi |va |voi |cung )"
)


def _normalize_for_block(name: str) -> str:
    """normalize_for_match then strip leading conjunction/coordination prefixes."""
    norm = normalize_for_match(name)
    return _CONJUNCTION_PREFIX_RE.sub("", norm).strip()


# ---------------------------------------------------------------------------
# Generic related-party phrases  ("…liên quan")
# ---------------------------------------------------------------------------
_GENERIC_RELATED_PHRASES: frozenset = frozenset({
    "cac bo co quan ngang bo co lien quan",
    "cac bo co quan ngang bo lien quan",
    "cac bo nganh lien quan",
    "bo nganh lien quan",
    "cac bo nganh dia phuong lien quan",
    "cac co quan lien quan",
    "cac co quan co lien quan",
    "co quan lien quan",
    "co quan co lien quan",
    "cac co quan to chuc co lien quan",
    "co quan to chuc co lien quan",
    "cac to chuc co lien quan",
    "to chuc co lien quan",
    "to chuc ca nhan co lien quan",
    "cac to chuc ca nhan co lien quan",
    "cac ben lien quan",
    "ben lien quan",
    "cac don vi lien quan",
    "don vi lien quan",
    "cac dia phuong lien quan",
    "dia phuong lien quan",
})

_GENERIC_RELATED_PATTERNS: List[re.Pattern] = [
    re.compile(p) for p in [
        r"^cac bo.*co quan ngang bo.*lien quan$",
        r"^cac bo.*nganh.*lien quan$",
        r"^bo.*nganh.*lien quan$",
        r"^cac co quan.*lien quan$",
        r"^co quan.*lien quan$",
        r"^cac co quan.*to chuc.*lien quan$",
        r"^co quan.*to chuc.*lien quan$",
        r"^cac to chuc.*lien quan$",
        r"^to chuc.*lien quan$",
        r"^to chuc.*ca nhan.*lien quan$",
        r"^cac ben.*lien quan$",
        r"^ben.*lien quan$",
        r"^cac don vi.*lien quan$",
        r"^don vi.*lien quan$",
        r"^cac dia phuong.*lien quan$",
        r"^dia phuong.*lien quan$",
    ]
]


def is_generic_related_agency(name: str) -> bool:
    """True if `name` is a generic related-party phrase ending with "liên quan".

    Returns True:  "các Bộ, cơ quan ngang Bộ có liên quan"
                   "và các cơ quan có liên quan"   ← conjunction prefix stripped
    Returns False: "Bộ Công Thương", "Ủy ban nhân dân cấp tỉnh"
    """
    norm = _normalize_for_block(name)
    if not norm:
        return False
    if norm in _GENERIC_RELATED_PHRASES:
        return True
    return any(p.match(norm) for p in _GENERIC_RELATED_PATTERNS)

_GENERIC_NON_AGENCY_PHRASES: frozenset = frozenset({
    "dia phuong",
    "cac dia phuong",
    "tinh",
    "cac tinh",
    "tinh thanh pho",
    "cac tinh thanh pho",
    "thanh pho",
    "nganh",
    "cac nganh",
    "ban",
    "cac ban",
    "co quan co tham quyen",
    "cac co quan co tham quyen",
    "co quan nha nuoc co tham quyen",
    "cac co quan nha nuoc co tham quyen",
    "to chuc ca nhan",
    "cac to chuc ca nhan",
    "don vi",
    "cac don vi",
})


def is_generic_non_agency(name: str) -> bool:
    """True if `name` is a standalone generic placeholder (not a real agency).

    Returns True:  "địa phương", "các địa phương"
                   "cơ quan có thẩm quyền", "đơn vị"
    Returns False: "Ủy ban nhân dân cấp tỉnh", "Bộ Công Thương"
    """
    norm = _normalize_for_block(name)
    if not norm:
        return False
    return norm in _GENERIC_NON_AGENCY_PHRASES


def is_invalid_agency_candidate(name: str) -> bool:
    """True if `name` must never produce an agency record or a mapping entry.

    Combines both filter families:
      - generic related-party phrases ("…liên quan")
      - generic standalone non-agency placeholders ("địa phương", "đơn vị", …)
    """
    return is_generic_related_agency(name) or is_generic_non_agency(name)

_AGENCY_ROLE_PREFIXES: List[str] = [
    "bo truong ",   # Bộ trưởng Bộ X → Bộ X; Bộ trưởng X → X
    "thu truong ",  # Thủ trưởng Bộ X → Bộ X
    "giam doc ",    # Giám đốc Sở X → Sở X
    "truong ban ",  # Trưởng ban X → ban X
]


def _strip_agency_role_prefix(key: str) -> Optional[str]:
    """Strip a known role prefix from a normalized agency key and return the remainder.

    E.g.: "bo truong bo y te" → "bo y te" (then re-try exact match in the agency index).
    Returns None if no prefix matches or the remainder would be empty.
    """
    for prefix in _AGENCY_ROLE_PREFIXES:
        if key.startswith(prefix):
            stripped = key[len(prefix):].strip()
            if stripped:
                return stripped
    return None


def _split_sentences(text: str) -> List[str]:
    """Split into rough sentences/lines for span extraction and weak-signal locality."""
    if not isinstance(text, str) or not text.strip():
        return []
    parts = re.split(r"[\n\r]+|(?<=[.;:])\s+", text)
    return [p.strip() for p in parts if p and p.strip()]


def _has_agency_marker(flat_sentence: str, agencies: Optional[List[dict]] = None) -> bool:
    """True if a built-in agency marker (or a caller-supplied agency name) appears."""
    if any(rx.search(flat_sentence) for rx in _AGENCY_MARKER_REGEXES):
        return True
    if agencies:
        norm = normalize_for_match(flat_sentence)
        for a in agencies:
            name = a.get("agency_name") if isinstance(a, dict) else None
            if name and normalize_agency_key(name) and normalize_agency_key(name) in norm:
                return True
    return False


def is_law_authority_candidate(
    text: str,
    article_class: Optional[List[str]] = None,
    agencies: Optional[List[dict]] = None,
) -> bool:
    """
    Two-tier regex pre-filter. Returns True if the text plausibly carries a delegation
    clause. The LLM is only invoked for candidates.

    - A STRONG signal anywhere => candidate.
    - A WEAK signal only promotes to candidate when an agency marker appears in the same
      sentence (reduces false positives from broad phrases like "quy định về").

    `article_class` is accepted for API symmetry; round 1.5 does not dismiss by class
    (terminal delegation clauses frequently live in "Hiệu lực thi hành" articles).
    `agencies` (optional) lets caller-supplied names count as agency markers.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    sentences = _split_sentences(text)
    # whole-text flat for strong scan (handles signals split oddly across lines)
    flat_all = collapse_whitespace(text)
    if any(rx.search(flat_all) for rx in _STRONG_REGEXES):
        return True
    for sent in sentences:
        flat = collapse_whitespace(sent)
        if any(rx.search(flat) for rx in _WEAK_REGEXES) and _has_agency_marker(flat, agencies):
            return True
    return False


def find_law_authority_candidate_spans(text: str) -> List[str]:
    """
    Return short sentences/spans that carry a delegation signal. Debug/prompt-context aid
    ONLY — never used to build records (full article remains the LLM context).
    """
    spans: List[str] = []
    seen = set()
    for sent in _split_sentences(text):
        flat = collapse_whitespace(sent)
        if any(rx.search(flat) for rx in _ALL_CANDIDATE_REGEXES):
            key = normalize_for_match(sent)
            if key and key not in seen:
                seen.add(key)
                spans.append(sent.strip())
    return spans


# ---------------------------------------------------------------------------
# LLM output normalization & validation
# ---------------------------------------------------------------------------
def _normalize_authorities_obj(obj) -> Dict[str, List[dict]]:
    """Defensive parser: coerce arbitrary LLM JSON shapes into {'law_authorities': [...]}.

    Items are returned as-is (dict passthrough) so optional fields like
    `authority_summary` / `is_valid_authority` survive to validation.
    """
    if obj is None:
        return {"law_authorities": []}
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            return {"law_authorities": []}
    if isinstance(obj, list):
        return {"law_authorities": obj}
    if isinstance(obj, dict):
        if "law_authorities" in obj and isinstance(obj["law_authorities"], list):
            return {"law_authorities": obj["law_authorities"]}
        for k in ("data", "result", "output", "response", "authorities"):
            if k in obj:
                nested = obj[k]
                if isinstance(nested, dict) and isinstance(nested.get("law_authorities"), list):
                    return {"law_authorities": nested["law_authorities"]}
                if isinstance(nested, list):
                    return {"law_authorities": nested}
    return {"law_authorities": []}


def _coerce_agencies(value) -> List[str]:
    """Coerce delegated_agencies into a clean list of non-empty strings."""
    out: List[str] = []
    if isinstance(value, str):
        value = [value]
    if isinstance(value, list):
        for v in value:
            if isinstance(v, str):
                v2 = v.strip().strip('"').strip()
                if v2:
                    out.append(v2)
    return out


def _is_reference_only_sentence(content: str) -> bool:
    """True if the sentence is a pure citation/reference (not an active delegation)."""
    norm = normalize_for_match(content)
    if not norm:
        return False
    return any(p in norm for p in REFERENCE_ONLY_PATTERNS)


def _has_active_delegation_structure(content: str, agencies: List[str]) -> bool:
    """
    True if the sentence has an explicit active delegation structure:
      - "<agency> ... <quy định|hướng dẫn|ban hành|chủ trì|chịu trách nhiệm> ..."
      - "Giao <agency> ..."
    """
    norm = normalize_for_match(content)
    if not norm:
        return False
    for ag in agencies:
        key = normalize_agency_key(ag)
        if not key or key not in norm:
            continue
        idx = norm.find(key)
        before = norm[:idx].rstrip()
        after = norm[idx + len(key):]
        if any(v in after for v in _ACTIVE_VERBS):
            return True
        if before.endswith("giao"):
            return True
    return False


def _agencies_traceable(content: str, agencies: List[str]) -> bool:
    """True only if EVERY raw delegated agency is a (near-)substring of authority_content."""
    for ag in agencies:
        if not is_near_substring(ag, content):
            return False
    return True


def _clean_optional_str(value) -> Optional[str]:
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    return None


# Sentinel used to distinguish "field absent" from "field present but None".
_SENTINEL_MISSING = object()


def _coerce_is_valid_authority(raw) -> bool:
    """Coerce the `is_valid_authority` field from arbitrary LLM output to Python bool.

    Rules:
        - Field absent (raw is _SENTINEL_MISSING) → True  (backward-compat: old prompts don't
          emit this field; treat absence as "LLM did not reject it").
        - bool True/False → as-is.
        - str "true"/"yes"/"1" (case-insensitive) → True.
        - str "false"/"no"/"0" (case-insensitive) → False.
        - Field present but null, or any other ambiguous value → False (conservative safe default:
          if the LLM put something unexpected here, reject rather than accept).
    """
    if raw is _SENTINEL_MISSING:
        return True
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("true", "yes", "1"):
            return True
        if s in ("false", "no", "0"):
            return False
    # present but null or ambiguous → safe conservative reject
    return False


def _validate_authority_item(item: dict, article_text: str) -> Optional[dict]:
    """
    Hard-gate a single LLM item. Returns a cleaned internal item, or None if rejected.

    LLM schema (new):
        authority_content   — business summary (UI-facing; not required to be verbatim)
        authority_quotation — verbatim delegation clause from the article (the evidence)
        delegated_agencies  — agencies named in authority_quotation
        is_valid_authority  — boolean filter

    Gates (in order):
      0. is_valid_authority coercion: if LLM marked the item invalid → reject.
      1. authority_content (summary) non-empty.
      2. authority_quotation (verbatim) non-empty.
      3. at least one delegated agency.
      4. authority_quotation contains an action marker.
      5. authority_quotation not a known normative/enumeration prefix.
      6. authority_quotation not a reference-only sentence (unless has active delegation structure).
      7. every delegated agency is traceable inside authority_quotation.
      8. authority_quotation is a (near-)substring of the article text.

    Returned cleaned item: authority_content, authority_quotation, delegated_agencies,
    is_valid_authority (True). Optional: validation_reason, validation_confidence.
    """
    if not isinstance(item, dict):
        return None

    # Gate 0: coerce is_valid_authority and reject if LLM flagged as invalid.
    raw_valid = item.get("is_valid_authority", _SENTINEL_MISSING)
    if not _coerce_is_valid_authority(raw_valid):
        logger.debug(
            "authority_rejected_verifier",
            action="_validate_authority_item",
            raw_is_valid=str(raw_valid)[:40],
        )
        return None

    content = item.get("authority_content")
    if not isinstance(content, str):
        return None
    content = content.strip()
    if not content:
        return None

    quotation = item.get("authority_quotation")
    if not isinstance(quotation, str):
        logger.debug("authority_rejected_no_quotation", action="_validate_authority_item", content=content[:120])
        return None
    quotation = quotation.strip()
    if not quotation:
        logger.debug("authority_rejected_no_quotation", action="_validate_authority_item", content=content[:120])
        return None

    agencies = _coerce_agencies(item.get("delegated_agencies"))
    if not agencies:
        logger.debug("authority_rejected_no_agency", action="_validate_authority_item", quotation=quotation[:120])
        return None

    if not contains_any(quotation, ACTION_MARKERS):
        logger.debug("authority_rejected_no_action_marker", action="_validate_authority_item", quotation=quotation[:120])
        return None

    norm_quotation = normalize_for_match(quotation)
    if any(norm_quotation.startswith(bad) for bad in NORMATIVE_PREFIX_BLOCKLIST):
        logger.debug("authority_rejected_normative_prefix", action="_validate_authority_item", quotation=quotation[:120])
        return None

    if _is_reference_only_sentence(quotation) and not _has_active_delegation_structure(quotation, agencies):
        logger.debug("authority_rejected_reference_only", action="_validate_authority_item", quotation=quotation[:120])
        return None

    if not _agencies_traceable(quotation, agencies):
        logger.debug("authority_rejected_agency_not_traceable", action="_validate_authority_item",
                     quotation=quotation[:120], agencies=agencies)
        return None

    if not is_near_substring(quotation, article_text):
        logger.debug("authority_rejected_not_in_article", action="_validate_authority_item", quotation=quotation[:120])
        return None

    cleaned: Dict[str, object] = {
        "authority_content":   content,
        "authority_quotation": quotation,
        "delegated_agencies":  agencies,
        "is_valid_authority":  True,
    }
    reason = _clean_optional_str(item.get("validation_reason"))
    if reason:
        cleaned["validation_reason"] = reason
    conf = item.get("validation_confidence")
    if isinstance(conf, (int, float)) and not isinstance(conf, bool):
        cleaned["validation_confidence"] = conf
    return cleaned


async def generate_law_authorities_async(
    article_content: str,
    article_class: Optional[List[str]],
    agencies: Optional[List[dict]],
    client: httpx.AsyncClient,
    semaphore,
    *,
    article_title: Optional[str] = None,
    doc_title: Optional[str] = None,
    doc_code: Optional[str] = None,
    candidate_spans: Optional[List[str]] = None,
) -> dict:
    """
    Extract verbatim delegation clauses for one article via LLM.

    Positional args are unchanged from round 1 (backward-compatible). The keyword-only
    args (article_title/doc_title/doc_code/candidate_spans) only add reference context to
    the prompt; the main business prompt is not rewritten. If omitted, behavior is identical.

    `agencies` is intentionally NOT appended to the prompt. The LLM extracts agency names
    verbatim from authority_content; mapping those names to agency_id records is done in
    Python post-processing inside compose_formal_records(). Passing the full DB agency list
    to the LLM would inflate the prompt by ~20k+ tokens without improving extraction quality.

    Returns:
        {"law_authorities": [{"authority_content", "delegated_agencies", <optional ...>}]}
    """
    if not is_law_authority_candidate(article_content, article_class, agencies):
        return {"law_authorities": []}

    prompt_template = read_prompt(PROMPT_KEY)

    class_hint = ""
    if article_class:
        labels = [c for c in article_class if isinstance(c, str) and c.strip()]
        if labels:
            class_hint = f"\n\n# Phân loại điều (tham khảo): {', '.join(labels)}"

    context_lines = []
    if doc_title:
        context_lines.append(f"Văn bản: {doc_title}")
    if doc_code:
        context_lines.append(f"Số hiệu: {doc_code}")
    if article_title:
        context_lines.append(f"Tên điều: {article_title}")
    context_hint = ""
    if context_lines:
        context_hint = "\n\n# Bối cảnh (tham khảo)\n- " + "\n- ".join(context_lines)

    span_hint = ""
    if candidate_spans:
        span_hint = (
            "\n\n# Câu khả nghi chứa tín hiệu giao quyền (tham khảo, vẫn đọc toàn bộ điều luật)\n- "
            + "\n- ".join(candidate_spans)
        )

    prompt = (
        f"{prompt_template}{class_hint}{context_hint}{span_hint}"
        f"\n\n# Đầu vào\n\"\"\"\n{article_content}\n\"\"\"\n"
    )

    logger.debug(
        "llm_prompt_stats",
        action="generate_law_authorities",
        prompt_chars=len(prompt),
        article_chars=len(article_content),
        agencies_received=len(agencies) if agencies else 0,
        agencies_in_prompt=0,
    )

    async with semaphore:
        response = await LLMs.llms_async(prompt, client=client)
        logger.debug(
            "receive_llm_response",
            action="generate_law_authorities",
            response_len=len(response) if response else 0,
        )
        result = None
        try:
            result = LLMs.llms_post_process(response)
        except Exception as e:
            logger.error(
                "llms_post_process_failed",
                action="generate_law_authorities",
                **{"error.code": "LLM", "error.message": str(e)},
                exc_info=True,
            )
            result = None

    normalized = _normalize_authorities_obj(result)

    cleaned: List[dict] = []
    seen_local: set = set()
    raw_count = 0
    invalid_count = 0  # items LLM marked as is_valid_authority=false

    for item in normalized.get("law_authorities", []):
        raw_count += 1
        # Count LLM-level invalids separately (for observability); gate 0 inside validate
        # will also reject these, but we capture the count here for debug stats.
        raw_valid = item.get("is_valid_authority", _SENTINEL_MISSING)
        if not _coerce_is_valid_authority(raw_valid):
            invalid_count += 1
        valid = _validate_authority_item(item, article_content)
        if not valid:
            continue
        key = (
            normalize_for_match(valid["authority_quotation"]),
            tuple(sorted(normalize_agency_key(a) for a in valid["delegated_agencies"])),
        )
        if key in seen_local:
            continue
        seen_local.add(key)
        cleaned.append(valid)

    return {
        "law_authorities": cleaned,
        "debug": {
            "raw_count": raw_count,
            "invalid_rejected": invalid_count,
        },
    }


# ---------------------------------------------------------------------------
# Agency mapping
# ---------------------------------------------------------------------------
def _build_agency_index(agency_lookup: Optional[List[dict]]) -> Dict[str, dict]:
    """normalized agency name -> {'agency_id', 'agency_name'}."""
    index: Dict[str, dict] = {}
    if not agency_lookup:
        return index
    for a in agency_lookup:
        if not isinstance(a, dict):
            continue
        name = a.get("agency_name")
        aid = a.get("agency_id")
        if not name or not aid:
            continue
        index[normalize_agency_key(name)] = {"agency_id": aid, "agency_name": name}
    return index


def _match_agencies(
    agency_names: List[str],
    agency_index: Dict[str, dict],
    new_agency_cache: Dict[str, dict],
) -> tuple:
    """
    Resolve LLM agency names to {agency_id, agency_name}.

    Returns:
        (resolved: List[dict], unmapped: List[str])
        `resolved`  — matched/created agency dicts, deduped by agency_id.
        `unmapped`  — raw names that could not be mapped and were NOT created (generic terms).

    Matching strategy:
      1. Exact normalized match against agency_index.
      2. Alias stripping: strip known role prefixes ("Bộ trưởng Bộ X" → "Bộ X") then retry
         exact match — handles common LLM verbatim patterns without fuzzy risk.
      3. Jaccard fuzzy (conservative): token-set subset + Jaccard >= 0.5 + smaller set >= 2
         tokens. Generic terms are excluded from fuzzy candidates.
      4. No match:
         - Generic term (GENERIC_AGENCY_TERMS) → add to `unmapped`, do NOT create a new record.
         - Non-generic → create a new record (via new_agency_cache for cross-article dedup).

    Resolved agencies are de-duplicated by agency_id.
    """
    resolved: List[dict] = []
    unmapped: List[str] = []
    seen_ids: set = set()

    for name in agency_names:
        key = normalize_agency_key(name)
        if not key:
            continue

        # 0. Block generic placeholders — must never create agency or mapping.
        if is_invalid_agency_candidate(name):
            logger.debug(
                "agency_rejected_generic_related_phrase",
                action="_match_agencies",
                name=name,
            )
            unmapped.append(name)
            continue

        match = None

        # 1. Exact normalized match
        if key in agency_index:
            match = agency_index[key]

        # 2. Alias stripping → exact match
        if match is None:
            stripped = _strip_agency_role_prefix(key)
            if stripped and stripped in agency_index:
                match = agency_index[stripped]

        # 3. Jaccard fuzzy (non-generic only)
        if match is None and key not in GENERIC_AGENCY_TERMS:
            ltok = set(key.split())
            best = None
            best_score = 0.0
            for idx_key, idx_val in agency_index.items():
                if idx_key in GENERIC_AGENCY_TERMS:
                    continue
                itok = set(idx_key.split())
                if not itok:
                    continue
                if ltok <= itok or itok <= ltok:
                    smaller = ltok if len(ltok) <= len(itok) else itok
                    if len(smaller) < 2:
                        continue
                    jacc = len(ltok & itok) / len(ltok | itok)
                    if jacc > best_score:
                        best_score = jacc
                        best = idx_val
            if best is not None and best_score >= 0.5:
                match = best

        # 4. No match: generic → unmapped; non-generic → create new
        if match is None:
            if key in GENERIC_AGENCY_TERMS:
                logger.debug(
                    "agency_skipped_generic",
                    action="_match_agencies",
                    name=name,
                )
                unmapped.append(name)
                continue
            if key in new_agency_cache:
                match = new_agency_cache[key]
            else:
                match = {"agency_id": str(uuid4()), "agency_name": name}
                new_agency_cache[key] = match
                logger.debug(
                    "agency_created_new",
                    action="_match_agencies",
                    name=name,
                    agency_id=match["agency_id"],
                )

        if match["agency_id"] not in seen_ids:
            seen_ids.add(match["agency_id"])
            resolved.append(match)

    return resolved, unmapped


# ---------------------------------------------------------------------------
# Record composition
# ---------------------------------------------------------------------------
def compose_formal_records(
    article_id: str,
    authorities: dict,
    created_by: Optional[str] = None,
    doc_id: Optional[str] = None,
    doc_meta: Optional[dict] = None,
    agency_lookup: Optional[List[dict]] = None,
    seen_keys: Optional[set] = None,
    new_agency_cache: Optional[dict] = None,
) -> Dict[str, List[dict]]:
    """
    Compose records for the law_authority / law_authority_mapping schema.

    Formal record shapes produced:

    law_authority (one per delegation clause):
        authority_content   — business summary from LLM authority_content.
        authority_quotation — verbatim delegation clause from LLM authority_quotation.

    law_authority_mapping (one per authority–agency pair):
        agency_id           — scalar string agency_id (one record per agency per authority).

    Args:
        article_id:        article the authorities were extracted from.
        authorities:       {"law_authorities": [<cleaned items>]}.
        created_by:        audit user (default "admin").
        doc_id:            owning document id.
        doc_meta:          optional {doc_effective_date, doc_expiry_date, effective_status_id}.
        agency_lookup:     optional list of {agency_id, agency_name} from law_agencies.
        seen_keys:         optional shared set for batch-level dedup across many articles.
        new_agency_cache:  optional shared dict (normalized name -> {agency_id, agency_name})
                           so the same unknown agency reuses one generated id across articles.

    Returns:
        {
          "authorities":        [law_authority records],
          "mappings":           [law_authority_mapping records],
          "agencies_to_create": [law_agencies records for agencies NEWLY created in THIS call],
          "unmapped_agencies":  [raw agency names that were generic/unresolvable — NOT created],
        }
    """
    rels = authorities.get("law_authorities", []) if isinstance(authorities, dict) else []
    created_by_val = created_by or "admin"
    now_str = local_now_str()
    doc_meta = doc_meta or {}
    eff_date = doc_meta.get("doc_effective_date", "") or ""
    exp_date = doc_meta.get("doc_expiry_date", "") or ""
    eff_status = doc_meta.get("effective_status_id", "") or ""

    agency_index = _build_agency_index(agency_lookup)
    if new_agency_cache is None:
        new_agency_cache = {}
    pre_existing_keys = set(new_agency_cache.keys())
    if seen_keys is None:
        seen_keys = set()

    authority_records: List[dict] = []
    mapping_records: List[dict] = []
    all_unmapped: List[str] = []

    for r in rels:
        if not isinstance(r, dict):
            continue
        content = r.get("authority_content")
        if not isinstance(content, str) or not content.strip():
            continue
        content = content.strip()
        quotation = (r.get("authority_quotation") or "").strip()
        if not quotation:
            continue
        agency_names = _coerce_agencies(r.get("delegated_agencies"))
        if not agency_names:
            continue

        resolved_agencies, unmapped = _match_agencies(agency_names, agency_index, new_agency_cache)
        all_unmapped.extend(unmapped)
        if not resolved_agencies:
            # All agencies were generic/invalid — drop the whole authority record.
            logger.debug(
                "authority_dropped_no_valid_agency",
                action="compose_formal_records",
                article_id=article_id,
                rejected_agencies=agency_names,
            )
            continue

        dedup_key = (
            doc_id,
            article_id,
            normalize_for_match(quotation),
            tuple(sorted(normalize_agency_key(a["agency_name"]) for a in resolved_agencies)),
        )
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        authority_id = str(uuid4())
        record = {
            "authority_id":        authority_id,
            "authority_content":   content,
            "authority_quotation": quotation,
            "doc_effective_date":  eff_date,
            "doc_expiry_date":     exp_date,
            "effective_status_id": eff_status,
            "status":              "ACTIVE",
            "created_at":          now_str,
            "created_by":          created_by_val,
            "last_modified_at":    now_str,
            "last_modified_by":    created_by_val,
        }
        # Optional verifier metadata from round-1.5 schema (written only if present).
        if isinstance(r.get("validation_reason"), str) and r["validation_reason"].strip():
            record["authority_validation_reason"] = r["validation_reason"].strip()
        if isinstance(r.get("validation_confidence"), (int, float)) and not isinstance(r.get("validation_confidence"), bool):
            record["authority_validation_confidence"] = r["validation_confidence"]
        authority_records.append(record)

        # One mapping record per (authority, agency); agency_id is a scalar string.
        for agency in resolved_agencies:
            mapping_records.append({
                "authority_id":     authority_id,
                "doc_id":           doc_id,
                "article_id":       article_id,
                "agency_id":        agency["agency_id"],
                "created_at":       now_str,
                "created_by":       created_by_val,
                "last_modified_at": now_str,
                "last_modified_by": created_by_val,
            })

    agencies_to_create: List[dict] = []
    for key, entry in new_agency_cache.items():
        if key in pre_existing_keys:
            continue
        agencies_to_create.append({
            "agency_id": entry["agency_id"],
            "agency_name": entry["agency_name"],
            "status": "ACTIVE",
            "created_at": now_str,
            "created_by": created_by_val,
            "last_modified_at": now_str,
            "last_modified_by": created_by_val,
        })

    return {
        "authorities": authority_records,
        "mappings": mapping_records,
        "agencies_to_create": agencies_to_create,
        "unmapped_agencies": list(dict.fromkeys(all_unmapped)),  # deduped, order-preserved
    }


def compose_debug_record(
    article_content: str,
    article_id: str,
    article_class: Optional[List[str]],
    authorities: dict,
) -> dict:
    """Lightweight debug record. Preserves all item fields (incl. authority_summary)."""
    rels = authorities.get("law_authorities", []) if isinstance(authorities, dict) else []
    with_meta: List[dict] = []
    for r in rels:
        if isinstance(r, dict):
            obj = dict(r)  # preserves authority_summary / validation_* if present
            obj["article_id"] = article_id
            obj["article_class"] = article_class
            with_meta.append(obj)
    return {
        "legal_segment": article_content,
        "law_authorities_extracted": {"law_authorities": with_meta},
    }
