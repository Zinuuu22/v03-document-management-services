"""
Law authority (nội dung giao quyền) extractor.

Round 1 introduces an LLM-based core (`llm_extractor`) whose `authority_content` is
always the verbatim delegation sentence. The legacy regex-only module (`extractor.py`)
is preserved untouched as a fallback and is still imported directly by existing callers.

Note: importing this package does NOT import the legacy `extractor` module, because the
latter opens a MongoDB connection at import time. Use `get_legacy_extractor()` to access
it lazily when a regex-only fallback is explicitly required.
"""

from core.v03.law_authority_extractor.llm_extractor import (
    AUTHORITY_CANDIDATE_PATTERNS,
    STRONG_CANDIDATE_PATTERNS,
    WEAK_CANDIDATE_PATTERNS,
    ACTION_MARKERS,
    REFERENCE_ONLY_PATTERNS,
    is_law_authority_candidate,
    find_law_authority_candidate_spans,
    generate_law_authorities_async,
    compose_formal_records,
    compose_debug_record,
)

__all__ = [
    "AUTHORITY_CANDIDATE_PATTERNS",
    "STRONG_CANDIDATE_PATTERNS",
    "WEAK_CANDIDATE_PATTERNS",
    "ACTION_MARKERS",
    "REFERENCE_ONLY_PATTERNS",
    "is_law_authority_candidate",
    "find_law_authority_candidate_spans",
    "generate_law_authorities_async",
    "compose_formal_records",
    "compose_debug_record",
    "get_legacy_extractor",
]


def get_legacy_extractor():
    from core.v03.law_authority_extractor import extractor as legacy
    return legacy
