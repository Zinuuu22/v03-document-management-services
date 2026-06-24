"""
Internal data model for the v2 multi-stage QHXH pipeline.

Plain dataclasses (no new dependency) plus light enum normalization helpers.
These objects are intermediate/debug-only; the public `social_relations`
output stays compatible with v2 and never exposes frame/confidence fields.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


# --- Enum value sets -------------------------------------------------------
FRAME_TYPES = {
    "procedure_record",
    "licensing_certification",
    "reporting_information",
    "inspection_supervision",
    "sanction_enforcement",
    "support_incentive",
    "state_management_coordination",
    "state_management_responsibility",
    "technical_no_relation",
    "definition_no_relation",
    "other",
}

DETAIL_LEVELS = {
    "primary",
    "sub_relation",
    "detail",
    "technical",
    "unknown",
}

# frame_types that never produce a renderable relation.
NO_RELATION_FRAME_TYPES = {
    "technical_no_relation",
    "definition_no_relation",
}


def normalize_frame_type(value: Any) -> str:
    """Map an arbitrary value to an allowed frame_type, defaulting to 'other'."""
    if isinstance(value, str):
        v = value.strip().lower()
        if v in FRAME_TYPES:
            return v
    return "other"


def normalize_detail_level(value: Any) -> str:
    """Map an arbitrary value to an allowed detail_level, defaulting to 'unknown'."""
    if isinstance(value, str):
        v = value.strip().lower()
        if v in DETAIL_LEVELS:
            return v
    return "unknown"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


# --- Stage 1 output --------------------------------------------------------
@dataclass
class LegalFrame:
    frame_id: str
    frame_type: str
    primary_subject: str | None = None
    counterparty: str | None = None
    action: str | None = None
    domain: str | None = None
    object: str | None = None
    is_bilateral: bool = False
    is_primary: bool = False
    detail_level: str = "unknown"
    evidence: str | None = None
    confidence: float | None = None
    raw: dict = field(default_factory=dict)


# --- Stage 2 output --------------------------------------------------------
@dataclass
class CleanFrame:
    frame_id: str
    frame_type: str
    actor_1: str
    actor_2: str
    action: str
    domain: str | None = None
    object: str | None = None
    source_frame_ids: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    renderable: bool = True
    drop_reason: str | None = None


# --- Stage 3 output --------------------------------------------------------
@dataclass
class CandidateRelation:
    relation_id: str
    relation_text: str
    social_relation: str
    actor_1: str
    actor_2: str
    frame_type: str
    domain: str | None = None
    object: str | None = None
    source_frame_ids: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


# --- Stage 4 output --------------------------------------------------------
@dataclass
class GroupAssignment:
    group_id: str
    social_relation_group: str
    relation_ids: list[str] = field(default_factory=list)
    group_family: str | None = None


def to_dict(obj: Any) -> Any:
    """Recursively turn dataclasses into plain dicts for logging/debug output."""
    from dataclasses import asdict, is_dataclass

    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
