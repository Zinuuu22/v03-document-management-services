"""
Stage 5 — final validation.

Turns clean CandidateRelations + GroupAssignments into the final, schema-stable
`social_relations` list. Conservative by default: it removes exact duplicates
and structurally invalid items, but only logs (does not delete) likely
detail/near-duplicate variants unless they are clearly identical.
"""

import os
import sys
from typing import List, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from .utils import normalize_name_no_diacritics, normalize_for_label_match
from .schemas import CandidateRelation, GroupAssignment
from .relation_renderer import _valid_relation_text, _social_relation_suffix
from .group_assigner import _GROUP_PREFIX
from .frame_cleaner import _is_denied_actor


def is_group_too_similar_to_relation(group: str, relation: str) -> bool:
    """True only when the group name is the relation with just the group prefix added.

    Conservative: returns True for a clear identity (group == prefix + relation,
    after normalization), not for mere overlap.
    """
    g = normalize_for_label_match(group)
    r = normalize_for_label_match(relation)
    prefix = normalize_for_label_match(_GROUP_PREFIX)
    if g.startswith(prefix):
        g = g[len(prefix):].strip()
    return bool(g) and g == r


def _group_name_by_relation_id(groups: List[GroupAssignment]) -> dict:
    mapping: dict = {}
    for g in groups if isinstance(groups, list) else []:
        if not isinstance(g, GroupAssignment):
            continue
        for rid in g.relation_ids:
            mapping[rid] = g.social_relation_group
    return mapping


def validate_final_relations(relations: List[CandidateRelation],
                             groups: List[GroupAssignment]) -> Tuple[List[dict], List[dict]]:
    """
    Produce the final social_relations list plus a validation audit.

    Each final item has exactly relation_text / social_relation /
    social_relation_group. Returns (final_social_relations, audit).
    """
    group_by_rel = _group_name_by_relation_id(groups)
    final: List[dict] = []
    audit: List[dict] = []
    seen: set = set()

    for r in relations if isinstance(relations, list) else []:
        if not isinstance(r, CandidateRelation):
            continue

        if not _valid_relation_text(r.relation_text):
            audit.append({"stage": "final_validation", "relation_id": r.relation_id,
                          "decision": "dropped", "drop_reason": "invalid_relation_text"})
            continue

        if _is_denied_actor(r.actor_1) or _is_denied_actor(r.actor_2):
            audit.append({"stage": "final_validation", "relation_id": r.relation_id,
                          "decision": "dropped", "drop_reason": "denylist_actor"})
            continue

        group_name = group_by_rel.get(r.relation_id)
        if not group_name:
            audit.append({"stage": "final_validation", "relation_id": r.relation_id,
                          "decision": "dropped", "drop_reason": "no_group_assignment"})
            continue
        if not group_name.startswith(_GROUP_PREFIX):
            audit.append({"stage": "final_validation", "relation_id": r.relation_id,
                          "decision": "dropped", "drop_reason": "invalid_group_prefix"})
            continue

        # social_relation must equal the suffix after the last 'trong việc'.
        suffix = _social_relation_suffix(r.relation_text)
        social_relation = r.social_relation.strip()
        if suffix and social_relation != suffix:
            audit.append({"stage": "final_validation", "relation_id": r.relation_id,
                          "decision": "normalized", "field": "social_relation"})
            social_relation = suffix

        if is_group_too_similar_to_relation(group_name, social_relation):
            audit.append({"stage": "final_validation", "relation_id": r.relation_id,
                          "decision": "dropped", "drop_reason": "group_equals_relation"})
            continue

        key = (
            normalize_name_no_diacritics(r.relation_text),
            normalize_name_no_diacritics(social_relation),
            normalize_name_no_diacritics(group_name),
        )
        if key in seen:
            audit.append({"stage": "final_validation", "relation_id": r.relation_id,
                          "decision": "dropped", "drop_reason": "exact_duplicate"})
            continue
        seen.add(key)

        final.append({
            "relation_text": r.relation_text,
            "social_relation": social_relation,
            "social_relation_group": group_name,
        })

    logger.debug("social_extractor_v2_final_validation", action="social_extractor_v2_final_validation",
                 candidate_relations_count=len(relations) if isinstance(relations, list) else 0,
                 final_relations_count=len(final),
                 audit_warnings_count=len(audit))
    return final, audit
