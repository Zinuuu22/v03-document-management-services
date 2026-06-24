"""
Stage 4 — group assignment.

Group assignment runs after relations are clean and must not alter
relation_text / social_relation / actors. It only returns group names plus the
relation_ids that belong to each group. Production path uses the
`group_assigner.md` LLM prompt; an empty prompt raises PromptNotConfiguredError.
"""

import os
import sys
import json
import asyncio
import httpx
from typing import List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.common.llms import LLMs
from constants import LLMsConfigExtractRelationship
from .utils import read_prompt, collapse_whitespace
from .schemas import CandidateRelation, GroupAssignment, new_id


_LLMS = LLMs(llms_config=LLMsConfigExtractRelationship)

_GROUP_PREFIX = "Các QHXH về "

# Helper-only family templates (NOT a closed taxonomy for final output).
_GROUP_FAMILY_TEMPLATES = {
    "procedure_record": "Các QHXH về tiếp nhận, đăng ký, quản lý, xử lý hồ sơ, văn bản",
    "licensing_certification": "Các QHXH về cấp phép, chứng nhận, phê duyệt, công nhận điều kiện hoạt động",
    "reporting_information": "Các QHXH về báo cáo, cung cấp, trao đổi thông tin, dữ liệu",
    "inspection_supervision": "Các QHXH về thanh tra, kiểm tra, giám sát việc tuân thủ pháp luật",
    "sanction_enforcement": "Các QHXH về xử lý vi phạm",
    "support_incentive": "Các QHXH về hỗ trợ, ưu đãi, khuyến khích đầu tư và phát triển sản xuất",
    "state_management_coordination": "Các QHXH về phân công, phối hợp quản lý nhà nước và tổ chức thực hiện chính sách",
}


def suggest_group_family(frame_type: str) -> str:
    """Deterministic family-template suggestion (helper only, not a default fallback)."""
    return _GROUP_FAMILY_TEMPLATES.get(frame_type, "Các QHXH về tổ chức thực hiện và quản lý nhà nước")


def _relations_payload(relations: List[CandidateRelation]) -> str:
    items = [
        {
            "relation_id": r.relation_id,
            "relation_text": r.relation_text,
            "social_relation": r.social_relation,
            "frame_type": r.frame_type,
            "domain": r.domain,
        }
        for r in relations
    ]
    return json.dumps({"relations": items}, ensure_ascii=False, indent=2)


def _parse_groups(parsed: object, relations: List[CandidateRelation]) -> List[GroupAssignment]:
    if isinstance(parsed, dict):
        items = parsed.get("groups")
    elif isinstance(parsed, list):
        items = parsed
    else:
        items = None
    if not isinstance(items, list):
        return []

    valid_ids = {r.relation_id for r in relations}
    seen_relation_ids: set = set()
    out: List[GroupAssignment] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        group_name = collapse_whitespace(item.get("social_relation_group") or "")
        if not group_name.startswith(_GROUP_PREFIX):
            logger.warning("social_extractor_v2_group_assignment", action="social_extractor_v2_group_assignment",
                           drop_reason="invalid_group_prefix", social_relation_group=group_name[:160])
            continue
        rel_ids_raw = item.get("relation_ids")
        rel_ids: List[str] = []
        for rid in rel_ids_raw if isinstance(rel_ids_raw, list) else []:
            if not isinstance(rid, str) or rid not in valid_ids:
                continue
            if rid in seen_relation_ids:
                logger.warning("social_extractor_v2_group_assignment", action="social_extractor_v2_group_assignment",
                               drop_reason="relation_in_multiple_groups", relation_id=rid)
                continue
            seen_relation_ids.add(rid)
            rel_ids.append(rid)
        if not rel_ids:
            continue
        family = item.get("group_family")
        out.append(GroupAssignment(
            group_id=str(item.get("group_id") or "").strip() or new_id("g"),
            social_relation_group=group_name,
            relation_ids=rel_ids,
            group_family=family if isinstance(family, str) and family else None,
        ))
    return out


async def assign_groups_async(relations: List[CandidateRelation], *, client: httpx.AsyncClient, semaphore,
                              article_title: str | None = None,
                              allow_fallback_group: bool = False) -> List[GroupAssignment]:
    """
    Assign groups to candidate relations via the LLM.

    Raises PromptNotConfiguredError if `group_assigner.md` is empty/missing.
    Unassigned relations are reported as a clear error and left unassigned by
    default; pass allow_fallback_group=True (debug/test only) to build a
    deterministic family-template group for the remainder.
    """
    relations = [r for r in relations if isinstance(r, CandidateRelation)]
    if not relations:
        return []

    prompt_template = read_prompt("group_assigner")  # raises if not configured
    title_block = f"# Tên điều\n{article_title}\n\n" if article_title else ""
    prompt = f"{prompt_template}\n\n{title_block}# Đầu vào\n{_relations_payload(relations)}\n"

    max_attempts = 3
    parsed = None
    async with semaphore:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await _LLMS.llms_async(prompt, client=client)
                parsed = _LLMS.llms_post_process(response)
                break
            except Exception as e:
                logger.warning("social_extractor_v2_group_assignment_attempt_failed",
                               action="social_extractor_v2_group_assignment",
                               attempt=attempt, max_attempts=max_attempts,
                               **{"error.code": "LLM", "error.message": str(e)})
                parsed = None
                if attempt < max_attempts:
                    await asyncio.sleep(0.5 * attempt)

    groups = _parse_groups(parsed, relations)

    assigned = {rid for g in groups for rid in g.relation_ids}
    unassigned = [r for r in relations if r.relation_id not in assigned]
    if unassigned:
        if allow_fallback_group:
            groups.extend(_fallback_groups(unassigned))
        else:
            logger.error("social_extractor_v2_group_assignment", action="social_extractor_v2_group_assignment",
                         **{"error.code": "GROUP", "error.message": "relations left without a group assignment"},
                         unassigned_relation_ids=[r.relation_id for r in unassigned])

    logger.debug("social_extractor_v2_group_assignment", action="social_extractor_v2_group_assignment",
                 relations_count=len(relations), groups_count=len(groups),
                 unassigned_count=len(unassigned))
    return groups


def _fallback_groups(relations: List[CandidateRelation]) -> List[GroupAssignment]:
    """Deterministic family-template grouping — debug/test fallback only."""
    by_family: dict = {}
    order: List[str] = []
    for r in relations:
        name = suggest_group_family(r.frame_type)
        if name not in by_family:
            by_family[name] = []
            order.append(name)
        by_family[name].append(r.relation_id)
    return [
        GroupAssignment(group_id=new_id("g"), social_relation_group=name, relation_ids=by_family[name])
        for name in order
    ]
