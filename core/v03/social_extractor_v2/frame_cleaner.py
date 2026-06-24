"""
Stage 2 — deterministic frame cleaner / merger (no LLM).

Takes raw LegalFrame objects from Stage 1 and applies conservative,
generic (non case-specific) rules to drop, mark-not-renderable, canonicalize
and merge them into CleanFrame objects. Anything uncertain is kept and logged,
never aggressively dropped.
"""

import os
import sys
import re
from typing import List, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from .utils import collapse_whitespace, normalize_for_label_match
from .schemas import LegalFrame, CleanFrame, NO_RELATION_FRAME_TYPES


# Actors that are objects/documents/budget/data/assets, not legal subjects.
_ACTOR_DENYLIST = {
    "ngan sach tinh",
    "ngan sach nha nuoc",
    "du an dau tu",
    "ho so",
    "van ban",
    "thiet bi",
    "he thong",
    "bieu mau",
    "khoan ho tro",
    "thue thu nhap doanh nghiep",
    "kinh phi",
    "giay phep",
    "giay chung nhan",
    "quyet dinh",
    "du lieu",
    "thong tin",
    "tai san",
    "cong trinh",
}

# Markers that signal an actor is a state/management/competent agency.
_AGENCY_MARKERS = (
    "co quan",
    "uy ban nhan dan",
    "ubnd",
    "chu tich",
    "thanh tra",
    "tong cuc",
    "cuc ",
    "chi cuc",
    "so ",
    "bo ",
    "ban quan ly",
    "chinh phu",
    "nha nuoc",
    "tham quyen",
)

# Generic detail markers (deadlines, quantities, references, fine print).
_DETAIL_PATTERNS = [
    re.compile(r"\b\d+\s*(ngày|ngay|tháng|thang|năm|nam|giờ|gio|tuần|tuan)\b", re.IGNORECASE),
    re.compile(r"\d+\s*%"),
    re.compile(r"\b\d+\s*(bộ|bo|bản|ban|bộ hồ sơ)\b", re.IGNORECASE),
    re.compile(r"mẫu\s*số", re.IGNORECASE),
    re.compile(r"phụ\s*lục", re.IGNORECASE),
    re.compile(r"\bkhoản\b", re.IGNORECASE),
    re.compile(r"\bđiểm\b", re.IGNORECASE),
    re.compile(r"\bĐiều\s*\d", re.IGNORECASE),
    re.compile(r"chậm\s*nhất", re.IGNORECASE),
    re.compile(r"trong\s*thời\s*hạn", re.IGNORECASE),
    re.compile(r"kèm\s*theo\s*bản\s*sao", re.IGNORECASE),
    re.compile(r"có\s*chứng\s*thực", re.IGNORECASE),
    re.compile(r"đóng\s*dấu\s*giáp\s*lai", re.IGNORECASE),
]


def _is_denied_actor(actor: str) -> bool:
    norm = normalize_for_label_match(actor)
    if not norm:
        return False
    for deny in _ACTOR_DENYLIST:
        if norm == deny:
            return True
        # dominant-substring: deny phrase makes up most of the actor string.
        if deny in norm and len(deny) >= 0.7 * len(norm):
            return True
    return False


def _is_agency(actor: str) -> bool:
    norm = " " + normalize_for_label_match(actor) + " "
    return any(m.strip() and (" " + m.strip()) in norm for m in _AGENCY_MARKERS)


def has_detail_marker(text: str) -> bool:
    if not isinstance(text, str) or not text:
        return False
    return any(p.search(text) for p in _DETAIL_PATTERNS)


def _canonicalize_actors(actor_1: str, actor_2: str) -> Tuple[str, str, bool]:
    """Put a competent/state agency as actor_1 when the pairing is agency↔subject.

    Returns (actor_1, actor_2, swapped).
    """
    a1_agency = _is_agency(actor_1)
    a2_agency = _is_agency(actor_2)
    # Only reorder for a clear agency↔non-agency pair; leave agency↔agency and
    # subject↔subject in their original text order.
    if a2_agency and not a1_agency:
        return actor_2, actor_1, True
    return actor_1, actor_2, False


def _drop_event(frame: LegalFrame, reason: str, **extra) -> dict:
    return {
        "stage": "frame_cleaning",
        "frame_id": frame.frame_id,
        "frame_type": frame.frame_type,
        "decision": "dropped",
        "drop_reason": reason,
        **extra,
    }


def _evaluate_frame(frame: LegalFrame) -> Tuple[CleanFrame | None, dict]:
    """Apply per-frame drop / not-renderable rules. Returns (clean_frame|None, audit)."""
    primary = collapse_whitespace(frame.primary_subject or "")
    counter = collapse_whitespace(frame.counterparty or "")
    action = collapse_whitespace(frame.action or "")
    domain = collapse_whitespace(frame.domain or "") or None
    obj = collapse_whitespace(frame.object or "") or None
    evidence = [collapse_whitespace(frame.evidence)] if frame.evidence else []

    # No-relation frame types and technical detail level: not renderable.
    if frame.frame_type in NO_RELATION_FRAME_TYPES:
        return None, _drop_event(frame, "no_relation_frame_type")
    if frame.detail_level == "technical":
        return None, _drop_event(frame, "technical_detail_level")

    # Structural minimums.
    if not primary:
        return None, _drop_event(frame, "missing_primary_subject")
    if not action:
        return None, _drop_event(frame, "missing_action")

    # Denylist: a primary that is really an object/document/budget is unusable.
    if _is_denied_actor(primary):
        return None, _drop_event(frame, "denylist_actor", actor=primary, actor_role="primary_subject")
    # A denied counterparty is treated as no counterparty (do not invent one).
    if counter and _is_denied_actor(counter):
        counter = ""

    # Bilateral requirement: never invent a vague counterparty for a unilateral
    # responsibility frame.
    if not counter:
        return None, _drop_event(frame, "unilateral_no_counterparty", actor=primary)

    actor_1, actor_2, swapped = _canonicalize_actors(primary, counter)
    audit = {
        "stage": "frame_cleaning",
        "frame_id": frame.frame_id,
        "frame_type": frame.frame_type,
        "decision": "accepted",
    }
    if swapped:
        audit["canonicalized"] = True
        audit["actor_order"] = "agency_first"

    clean = CleanFrame(
        frame_id=frame.frame_id,
        frame_type=frame.frame_type,
        actor_1=actor_1,
        actor_2=actor_2,
        action=action,
        domain=domain,
        object=obj,
        source_frame_ids=[frame.frame_id],
        evidence=evidence,
        renderable=True,
        drop_reason=None,
    )
    return clean, audit


def _merge_key(cf: CleanFrame) -> tuple:
    return (
        cf.frame_type,
        normalize_for_label_match(cf.actor_1),
        normalize_for_label_match(cf.actor_2),
        normalize_for_label_match(cf.domain or ""),
    )


def _pick_representative(group: List[CleanFrame]) -> CleanFrame:
    """Prefer a frame whose action carries no detail marker, then the shortest."""
    no_marker = [cf for cf in group if not has_detail_marker(cf.action)]
    pool = no_marker if no_marker else group
    return min(pool, key=lambda cf: len(cf.action))


def _merge_clean_frames(frames: List[CleanFrame]) -> Tuple[List[CleanFrame], List[dict]]:
    audit: List[dict] = []
    groups: dict = {}
    order: List[tuple] = []
    for cf in frames:
        key = _merge_key(cf)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(cf)

    merged: List[CleanFrame] = []
    for key in order:
        group = groups[key]
        if len(group) == 1:
            merged.append(group[0])
            continue
        rep = _pick_representative(group)
        for cf in group:
            if cf is rep:
                continue
            for fid in cf.source_frame_ids:
                if fid not in rep.source_frame_ids:
                    rep.source_frame_ids.append(fid)
            for ev in cf.evidence:
                if ev and ev not in rep.evidence:
                    rep.evidence.append(ev)
            audit.append({
                "stage": "frame_cleaning",
                "frame_id": cf.frame_id,
                "decision": "merged",
                "drop_reason": "merged_detail_variant",
                "merged_into": rep.frame_id,
            })
        merged.append(rep)
    return merged, audit


def clean_and_merge_frames(frames: List[LegalFrame]) -> Tuple[List[CleanFrame], List[dict]]:
    """
    Validate, canonicalize and merge raw frames into renderable CleanFrames.

    Returns (clean_frames, audit). Only frames with renderable=True proceed to
    relation rendering; everything dropped is explained in the audit list.
    """
    audit: List[dict] = []
    accepted: List[CleanFrame] = []
    for frame in frames if isinstance(frames, list) else []:
        if not isinstance(frame, LegalFrame):
            continue
        clean, event = _evaluate_frame(frame)
        audit.append(event)
        if clean is not None:
            accepted.append(clean)

    merged, merge_audit = _merge_clean_frames(accepted)
    audit.extend(merge_audit)

    logger.debug("social_extractor_v2_frame_cleaning", action="social_extractor_v2_frame_cleaning",
                 raw_frames_count=len(frames) if isinstance(frames, list) else 0,
                 clean_frames_count=len(merged),
                 dropped_frames_count=sum(1 for e in audit if e.get("decision") in ("dropped", "merged")))
    return merged, audit
