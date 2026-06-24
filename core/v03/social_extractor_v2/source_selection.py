"""
Stage 0 — lightweight source selection for v2.

No target gating: every article that is not an explicit hard-skip defaults to
extract. Only HARD_SKIP_LABELS blocks extraction.
"""

import os
import sys
import re
from typing import Dict, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from .utils import normalize_for_label_match


# Hard-skip labels: the only thing that blocks extraction in v2.
HARD_SKIP_LABELS: Dict[str, str] = {
    "giai thich tu ngu": "Giải thích từ ngữ",
    "pham vi dieu chinh": "Phạm vi điều chỉnh",
    "hieu luc thi hanh": "Hiệu lực thi hành",
    "dieu khoan chuyen tiep": "Điều khoản chuyển tiếp",
    "dieu khoan thi hanh": "Điều khoản thi hành",
}


def _match_labels(title: str, article_class: List[str], labels: Dict[str, str]) -> List[str]:
    matched: List[str] = []
    norm_title = normalize_for_label_match(title)
    norm_classes = [
        normalize_for_label_match(c)
        for c in (article_class if isinstance(article_class, list) else [])
        if isinstance(c, str)
    ]
    for norm_label, original in labels.items():
        hit = False
        if norm_label and norm_title and norm_label in norm_title:
            hit = True
        elif any(norm_label and nc and norm_label in nc for nc in norm_classes):
            hit = True
        if hit:
            matched.append(original)
    return matched


def _title_from_content(article_content: str) -> str:
    """Return the 'Điều <số>. <tên điều>' header line if present, else ''."""
    if not isinstance(article_content, str):
        return ""
    for raw_line in article_content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^Điều\s+\d+", line, flags=re.IGNORECASE):
            return line
        break
    return ""


def select_social_relation_source(article_title: str | None, article_class: List[str] | None) -> dict:
    """
    Decide whether an article is an extraction source in v2.

    Hard-skip labels block extraction; everything else defaults to extract.
    `article_title` may be a bare title or a full article body — a leading
    'Điều N.' header is recovered from the body when present.

    Returns:
        {"should_extract": bool, "reason": str, "matched_signals": [str, ...]}
        reason ∈ {"hard_skip_source", "default_extract_source"}
    """
    title = article_title if isinstance(article_title, str) else ""
    if "\n" in title:
        title = _title_from_content(title) or title
    article_class = article_class if isinstance(article_class, list) else []

    skip_hits = _match_labels(title, article_class, HARD_SKIP_LABELS)
    if skip_hits:
        return {
            "should_extract": False,
            "reason": "hard_skip_source",
            "matched_signals": skip_hits,
        }
    return {
        "should_extract": True,
        "reason": "default_extract_source",
        "matched_signals": [],
    }


def select_social_relation_sources(segments: List[dict], classes_map: dict) -> dict:
    """
    Run source selection across a list of segments.

    Returns:
        {
            "segments": [{"article_id", "article_class", "source_selection"}, ...],
            "summary": {"total_segments", "selected_segments", "skipped_segments"},
        }
    """
    classes_map = classes_map if isinstance(classes_map, dict) else {}
    out_segments: List[dict] = []
    selected = 0
    for seg in segments if isinstance(segments, list) else []:
        if not isinstance(seg, dict):
            continue
        article_id = seg.get("article_id")
        title = seg.get("title") if isinstance(seg.get("title"), str) else ""
        content = seg.get("content") if isinstance(seg.get("content"), str) else ""
        article_class = classes_map.get(article_id, [])
        if not isinstance(article_class, list):
            article_class = []
        probe = title if title else content
        selection = select_social_relation_source(probe, article_class)
        if selection["should_extract"]:
            selected += 1
        out_segments.append({
            "article_id": article_id,
            "article_class": article_class,
            "source_selection": selection,
        })
    total = len(out_segments)
    logger.debug("social_extractor_v2_source_selection", action="social_extractor_v2_source_selection",
                 total_segments=total, selected_segments=selected, skipped_segments=total - selected)
    return {
        "segments": out_segments,
        "summary": {
            "total_segments": total,
            "selected_segments": selected,
            "skipped_segments": total - selected,
        },
    }
