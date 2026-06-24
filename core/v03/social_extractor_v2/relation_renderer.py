"""
Stage 3 — relation rendering.

Production path calls an LLM using the `relation_renderer.md` prompt; if that
prompt is empty the path raises PromptNotConfiguredError (no silent template
fallback). A deterministic `render_relation_from_frame` helper exists for unit
tests / debug only and must be opted into explicitly.
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
from .schemas import CleanFrame, CandidateRelation, new_id


_LLMS = LLMs(llms_config=LLMsConfigExtractRelationship)

_RELATION_PREFIX = "Quan hệ giữa "
_RELATION_MID = "trong việc"


def _frames_payload(clean_frames: List[CleanFrame]) -> str:
    items = [
        {
            "frame_id": cf.frame_id,
            "frame_type": cf.frame_type,
            "actor_1": cf.actor_1,
            "actor_2": cf.actor_2,
            "action": cf.action,
            "domain": cf.domain,
            "object": cf.object,
        }
        for cf in clean_frames
    ]
    return json.dumps({"frames": items}, ensure_ascii=False, indent=2)


def _valid_relation_text(text: str) -> bool:
    return (
        isinstance(text, str)
        and text.startswith(_RELATION_PREFIX)
        and _RELATION_MID in text
    )


def _social_relation_suffix(relation_text: str) -> str:
    """The canonical social_relation is the substring after the last 'trong việc'."""
    idx = relation_text.rfind(_RELATION_MID)
    if idx == -1:
        return ""
    return relation_text[idx + len(_RELATION_MID):].strip()


def _frame_index(clean_frames: List[CleanFrame]) -> dict:
    return {cf.frame_id: cf for cf in clean_frames}


def _parse_relations(parsed: object, clean_frames: List[CleanFrame]) -> List[CandidateRelation]:
    if isinstance(parsed, dict):
        items = parsed.get("relations")
    elif isinstance(parsed, list):
        items = parsed
    else:
        items = None
    if not isinstance(items, list):
        return []

    by_id = _frame_index(clean_frames)
    out: List[CandidateRelation] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        relation_text = collapse_whitespace(item.get("relation_text") or "")
        if not _valid_relation_text(relation_text):
            logger.warning("social_extractor_v2_relation_rendering", action="social_extractor_v2_relation_rendering",
                           drop_reason="invalid_relation_text", relation_text=relation_text[:160])
            continue
        social_relation = _social_relation_suffix(relation_text)
        if not social_relation:
            continue

        source_ids = item.get("source_frame_ids")
        source_ids = [s for s in source_ids if isinstance(s, str)] if isinstance(source_ids, list) else []
        src_frames = [by_id[s] for s in source_ids if s in by_id]
        base = src_frames[0] if src_frames else None

        actor_1 = collapse_whitespace(item.get("actor_1") or "") or (base.actor_1 if base else "")
        actor_2 = collapse_whitespace(item.get("actor_2") or "") or (base.actor_2 if base else "")
        frame_type = collapse_whitespace(item.get("frame_type") or "") or (base.frame_type if base else "other")
        domain = collapse_whitespace(item.get("domain") or "") or (base.domain if base else None)
        evidence = []
        for f in src_frames:
            for ev in f.evidence:
                if ev and ev not in evidence:
                    evidence.append(ev)

        out.append(CandidateRelation(
            relation_id=str(item.get("relation_id") or "").strip() or new_id("r"),
            relation_text=relation_text,
            social_relation=social_relation,
            actor_1=actor_1,
            actor_2=actor_2,
            frame_type=frame_type,
            domain=domain,
            object=(base.object if base else None),
            source_frame_ids=source_ids,
            evidence=evidence,
        ))
    return out


async def render_relations_async(clean_frames: List[CleanFrame], *, client: httpx.AsyncClient, semaphore,
                                 article_title: str | None = None) -> List[CandidateRelation]:
    """
    Render candidate relations from renderable clean frames via the LLM.

    Raises PromptNotConfiguredError if `relation_renderer.md` is empty/missing.
    Never silently template-renders when the prompt is absent.
    """
    renderable = [cf for cf in clean_frames if isinstance(cf, CleanFrame) and cf.renderable]
    if not renderable:
        return []

    prompt_template = read_prompt("relation_renderer")  # raises if not configured
    title_block = f"# Tên điều\n{article_title}\n\n" if article_title else ""
    prompt = f"{prompt_template}\n\n{title_block}# Đầu vào\n{_frames_payload(renderable)}\n"

    max_attempts = 3
    parsed = None
    async with semaphore:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await _LLMS.llms_async(prompt, client=client)
                parsed = _LLMS.llms_post_process(response)
                break
            except Exception as e:
                logger.warning("social_extractor_v2_relation_rendering_attempt_failed",
                               action="social_extractor_v2_relation_rendering",
                               attempt=attempt, max_attempts=max_attempts,
                               **{"error.code": "LLM", "error.message": str(e)})
                parsed = None
                if attempt < max_attempts:
                    await asyncio.sleep(0.5 * attempt)

    relations = _parse_relations(parsed, renderable)
    logger.debug("social_extractor_v2_relation_rendering", action="social_extractor_v2_relation_rendering",
                 clean_frames_count=len(renderable), candidate_relations_count=len(relations))
    return relations


def render_relation_from_frame(frame: CleanFrame) -> CandidateRelation:
    """Deterministic relation render — unit-test/debug helper only.

    Not used on the production path: when the LLM prompt is absent the production
    path must raise, not fall back to this template.
    """
    social_relation = collapse_whitespace(frame.action)
    relation_text = f"{_RELATION_PREFIX}{frame.actor_1} và {frame.actor_2} {_RELATION_MID} {social_relation}".strip()
    return CandidateRelation(
        relation_id=new_id("r"),
        relation_text=relation_text,
        social_relation=social_relation,
        actor_1=frame.actor_1,
        actor_2=frame.actor_2,
        frame_type=frame.frame_type,
        domain=frame.domain,
        object=frame.object,
        source_frame_ids=list(frame.source_frame_ids),
        evidence=list(frame.evidence),
    )
