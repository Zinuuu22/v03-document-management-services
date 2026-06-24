import os
import re
import unicodedata
from datetime import datetime
from typing import List


def _prompt_md_path(key: str) -> str:
    """Path to the Markdown prompt file for a given key."""
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "prompts",
        f"{key}.md",
    )


def read_prompt(key: str) -> str:
    """Load a prompt as raw UTF-8 Markdown from utils/prompts/{key}.md.

    The prompt body is returned verbatim — no Markdown parsing, no .format(), no
    mutation. Raises FileNotFoundError if the file does not exist.
    """
    path = _prompt_md_path(key)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt markdown file not found for key '{key}' at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def local_now_str() -> str:
    """Return server local time in 'YYYY-MM-DD HH:MM:SS' (repo-wide format)."""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def collapse_whitespace(text: str) -> str:
    """Collapse all runs of whitespace (incl. newlines) to a single space."""
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text).strip()


def normalize_name_no_diacritics(text: str) -> str:
    """Strip Vietnamese diacritics, collapse whitespace. Keeps original case.

    Note: 'đ'/'Đ' are LATIN letters with stroke (not combining marks), so NFD does
    not decompose them — handle them explicitly so they become 'd'/'D'.
    """
    if not isinstance(text, str):
        return ""
    try:
        text = text.replace("đ", "d").replace("Đ", "D")
        nfkd = unicodedata.normalize("NFD", text)
        no_diacritics = "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn")
        return " ".join(no_diacritics.split()).strip()
    except Exception:
        return ""


def normalize_agency_key(text: str) -> str:
    """Lowercased, diacritic-free, whitespace-collapsed key for agency matching."""
    return normalize_name_no_diacritics(text).lower().strip()


def normalize_for_match(text: str) -> str:
    """
    Aggressive normalization used for substring/near-substring tracing:
    lowercase, drop diacritics, replace any non-alphanumeric char with a space,
    then collapse whitespace. Makes matching robust to punctuation differences.
    """
    base = normalize_name_no_diacritics(text).lower()
    if not base:
        return ""
    base = re.sub(r"[^0-9a-z\s]", " ", base)
    return " ".join(base.split()).strip()


def is_near_substring(needle: str, haystack: str) -> bool:
    """
    True if `needle` appears (near-)verbatim inside `haystack`, tolerant of
    whitespace and punctuation differences. Used to verify that an LLM-returned
    authority_content can be traced back to the original article text.
    """
    n = normalize_for_match(needle)
    h = normalize_for_match(haystack)
    if not n or not h:
        return False
    return n in h


def contains_any(text: str, markers: List[str]) -> bool:
    """True if any marker (already diacritic-free, lowercase) appears in text."""
    norm = normalize_for_match(text)
    if not norm:
        return False
    return any(m in norm for m in markers)
