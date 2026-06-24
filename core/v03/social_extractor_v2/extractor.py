"""
v2 orchestrator + Stage 1 (LLM legal-frame extraction).

Pipeline: source selection → frame extraction (LLM) → deterministic frame
clean/merge → relation rendering (LLM) → group assignment (LLM) → final
validation. Public output stays in the {"social_relations": [...]} shape.
No DB/Kafka integration here.
"""

import os
import sys
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

from dotenv import load_dotenv
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
ENV_PROD_PATH = os.path.join(PROJECT_ROOT, ".env.prod")
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
if os.path.exists(ENV_PROD_PATH):
    load_dotenv(ENV_PROD_PATH)

from core.common.llms import LLMs
from constants import LLMsConfigExtractRelationship
from .utils import read_prompt, collapse_whitespace
from .schemas import (
    LegalFrame,
    new_id,
    normalize_frame_type,
    normalize_detail_level,
    to_dict,
)
from .source_selection import (
    select_social_relation_source,
    select_social_relation_sources,
)
from .frame_cleaner import clean_and_merge_frames
from .relation_renderer import render_relations_async
from .group_assigner import assign_groups_async
from .validator import validate_final_relations
from .compose import compose_formal_records


_LLMS = LLMs(llms_config=LLMsConfigExtractRelationship)


# --- Stage 1 parsing -------------------------------------------------------
def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "có", "co")
    return bool(value)


def _coerce_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_opt(value) -> str | None:
    text = collapse_whitespace(value) if isinstance(value, str) else ""
    return text or None


def _parse_frames(parsed: object) -> List[LegalFrame]:
    if isinstance(parsed, dict):
        items = parsed.get("frames")
        if not isinstance(items, list):
            items = parsed.get("data") if isinstance(parsed.get("data"), list) else None
    elif isinstance(parsed, list):
        items = parsed
    else:
        items = None
    if not isinstance(items, list):
        return []

    frames: List[LegalFrame] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        primary = _clean_opt(item.get("primary_subject"))
        action = _clean_opt(item.get("action"))
        frame_type = normalize_frame_type(item.get("frame_type"))
        # Completely unusable: no subject, no action, no informative type.
        if not primary and not action and frame_type == "other":
            continue
        frames.append(LegalFrame(
            frame_id=str(item.get("frame_id") or "").strip() or new_id("f"),
            frame_type=frame_type,
            primary_subject=primary,
            counterparty=_clean_opt(item.get("counterparty")),
            action=action,
            domain=_clean_opt(item.get("domain")),
            object=_clean_opt(item.get("object")),
            is_bilateral=_coerce_bool(item.get("is_bilateral")),
            is_primary=_coerce_bool(item.get("is_primary")),
            detail_level=normalize_detail_level(item.get("detail_level")),
            evidence=_clean_opt(item.get("evidence")),
            confidence=_coerce_float(item.get("confidence")),
            raw=item,
        ))
    return frames


async def extract_legal_frames_async(article_content: str, *, article_title: str | None = None,
                                     article_class: List[str] | None = None,
                                     client: httpx.AsyncClient | None = None, semaphore=None) -> List[LegalFrame]:
    """
    Stage 1 — extract legal frames from one article via the LLM.

    Reads the `frame_extractor.md` prompt; raises PromptNotConfiguredError if it
    is empty/missing (no hardcoded fallback). Creates its own client/semaphore when not
    supplied so the stage is independently callable.
    """
    prompt_template = read_prompt("frame_extractor")  # raises if not configured
    title_block = f"# Tên điều\n{article_title}\n\n" if article_title else ""
    prompt = f"{prompt_template}\n\n{title_block}# Đầu vào\n\"\"\"\n{article_content}\n\"\"\"\n"

    if client is None:
        timeout = httpx.Timeout(600.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as own_client:
            return await _extract_frames_with_client(prompt, article_content, own_client, semaphore or asyncio.Semaphore(1))
    return await _extract_frames_with_client(prompt, article_content, client, semaphore or asyncio.Semaphore(1))


async def _extract_frames_with_client(prompt: str, article_content: str, client: httpx.AsyncClient, semaphore) -> List[LegalFrame]:
    max_attempts = 3
    parsed = None
    async with semaphore:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await _LLMS.llms_async(prompt, client=client)
                parsed = _LLMS.llms_post_process(response)
                break
            except Exception as e:
                logger.warning("social_extractor_v2_frame_extraction_attempt_failed",
                               action="social_extractor_v2_frame_extraction",
                               attempt=attempt, max_attempts=max_attempts,
                               content_len=len(article_content) if article_content else 0,
                               **{"error.code": "LLM", "error.message": str(e)})
                parsed = None
                if attempt < max_attempts:
                    await asyncio.sleep(0.5 * attempt)

    frames = _parse_frames(parsed)
    logger.debug("social_extractor_v2_frame_extraction", action="social_extractor_v2_frame_extraction",
                 raw_frames_count=len(frames))
    return frames


# --- Orchestration ---------------------------------------------------------
def _empty_pipeline(source_selection: dict) -> dict:
    return {
        "source_selection": source_selection,
        "raw_frames": [],
        "clean_frames": [],
        "candidate_relations": [],
        "group_assignments": [],
        "final_social_relations": [],
        "audit": [],
    }


async def _run_pipeline_async(article_content: str, article_title: str | None, article_class: List[str] | None,
                              client: httpx.AsyncClient, semaphore) -> dict:
    probe = article_title if article_title else article_content
    source_selection = select_social_relation_source(probe, article_class)
    result = _empty_pipeline(source_selection)

    if not source_selection["should_extract"]:
        logger.info("social_extractor_v2_done", action="social_extractor_v2_done",
                    reason=source_selection["reason"], final_relations_count=0)
        return result

    raw_frames = await extract_legal_frames_async(
        article_content, article_title=article_title, article_class=article_class,
        client=client, semaphore=semaphore,
    )
    clean_frames, clean_audit = clean_and_merge_frames(raw_frames)
    result["raw_frames"] = to_dict(raw_frames)
    result["clean_frames"] = to_dict(clean_frames)
    result["audit"].extend(clean_audit)

    renderable = [cf for cf in clean_frames if cf.renderable]
    if not renderable:
        logger.info("social_extractor_v2_done", action="social_extractor_v2_done",
                    raw_frames_count=len(raw_frames), clean_frames_count=0, final_relations_count=0)
        return result

    relations = await render_relations_async(renderable, client=client, semaphore=semaphore, article_title=article_title)
    result["candidate_relations"] = to_dict(relations)
    if not relations:
        logger.info("social_extractor_v2_done", action="social_extractor_v2_done",
                    raw_frames_count=len(raw_frames), clean_frames_count=len(renderable),
                    candidate_relations_count=0, final_relations_count=0)
        return result

    groups = await assign_groups_async(relations, client=client, semaphore=semaphore, article_title=article_title)
    result["group_assignments"] = to_dict(groups)

    final, val_audit = validate_final_relations(relations, groups)
    result["final_social_relations"] = final
    result["audit"].extend(val_audit)

    logger.info("social_extractor_v2_done", action="social_extractor_v2_done",
                raw_frames_count=len(raw_frames), clean_frames_count=len(renderable),
                candidate_relations_count=len(relations), groups_count=len(groups),
                final_relations_count=len(final))
    return result


async def generate_social_relations_async(article_content: str, *, article_title: str | None = None,
                                          article_class: List[str] | None = None, debug: bool = False,
                                          client: httpx.AsyncClient | None = None, semaphore=None) -> dict:
    """
    Full pipeline for one article. Returns {"social_relations": [...]}.

    If debug=True, returns the full intermediate pipeline object instead.
    Raises PromptNotConfiguredError if an LLM stage's prompt is not configured.
    """
    if client is None:
        timeout = httpx.Timeout(600.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as own_client:
            result = await _run_pipeline_async(article_content, article_title, article_class, own_client, semaphore or asyncio.Semaphore(1))
    else:
        result = await _run_pipeline_async(article_content, article_title, article_class, client, semaphore or asyncio.Semaphore(1))

    if debug:
        return result
    return {"social_relations": result["final_social_relations"]}


async def generate_debug_pipeline_async(article_content: str, *, article_title: str | None = None,
                                        article_class: List[str] | None = None,
                                        client: httpx.AsyncClient | None = None, semaphore=None) -> dict:
    """Run the full pipeline and return every intermediate stage for audit/test."""
    return await generate_social_relations_async(
        article_content, article_title=article_title, article_class=article_class,
        debug=True, client=client, semaphore=semaphore,
    )


async def generate_social_relations_for_segments_async(segments: List[dict], classes_map: dict, *,
                                                       concurrency: int = 3, debug: bool = False) -> dict:
    """
    Document/segment-level batch extraction. Does NOT write to the DB.

    Returns {"segments": [...], "source_selection_summary": {...}}. Each segment
    entry carries source_selection + extraction (and full debug stages if debug).
    """
    selection = select_social_relation_sources(segments, classes_map)
    seg_by_id = {seg.get("article_id"): seg for seg in segments if isinstance(seg, dict)}

    timeout = httpx.Timeout(600.0, connect=10.0)
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async with httpx.AsyncClient(timeout=timeout) as client:

        async def _run_one(entry: dict) -> dict:
            article_id = entry["article_id"]
            article_class = entry["article_class"]
            src_sel = entry["source_selection"]
            base = {
                "article_id": article_id,
                "article_class": article_class,
                "source_selection": src_sel,
                "extraction": {"social_relations": []},
            }
            if not src_sel["should_extract"]:
                return base
            seg = seg_by_id.get(article_id, {})
            title = seg.get("title") if isinstance(seg.get("title"), str) else ""
            content = seg.get("content") if isinstance(seg.get("content"), str) else ""
            article_content = f"{title}\n{content}".strip() if title else content
            pipeline = await _run_pipeline_async(article_content, title or None, article_class, client, semaphore)
            base["extraction"] = {"social_relations": pipeline["final_social_relations"]}
            if debug:
                base["debug"] = pipeline
            return base

        results = await asyncio.gather(*[_run_one(e) for e in selection["segments"]], return_exceptions=True)

    out_segments: List[dict] = []
    for entry, res in zip(selection["segments"], results):
        if isinstance(res, Exception):
            logger.error("social_extractor_v2_segment_failed", action="social_extractor_v2_done",
                         article_id=entry.get("article_id"),
                         **{"error.code": "EXTRACT", "error.message": str(res)})
            out_segments.append({
                "article_id": entry.get("article_id"),
                "article_class": entry.get("article_class"),
                "source_selection": entry.get("source_selection"),
                "extraction": {"social_relations": []},
                "error": str(res),
            })
        else:
            out_segments.append(res)

    return {
        "segments": out_segments,
        "source_selection_summary": selection["summary"],
    }
