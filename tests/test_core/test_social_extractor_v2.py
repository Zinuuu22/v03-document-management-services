"""
Read-only CLI test for core/v03/social_extractor_v2. No DB writes.
Lifecycle/status logs go through structlog as usual (compact JSON, repo standard).
Only the actual pipeline RESULT payloads are logged via `result_logger`, which
uses an indented JSONRenderer so they're readable in a terminal.

The LLM stages need their prompt Markdown files to be populated. While the
prompts are empty this harness fails gracefully with a clear `prompt_not_configured`
log instead of a stacktrace.

Usage:
    python tests/test_core/test_social_extractor_v2.py --article-id <id>
    python tests/test_core/test_social_extractor_v2.py --doc-id <id> --concurrency 5
    python tests/test_core/test_social_extractor_v2.py --doc-id <id> --skip-llm-check
    python tests/test_core/test_social_extractor_v2.py --article-id <id> --debug
    python tests/test_core/test_social_extractor_v2.py --article-id <id> --stage frames
    python tests/test_core/test_social_extractor_v2.py --doc-id <id> --stage frames
    python tests/test_core/test_social_extractor_v2.py --article-id <id> --stage relations
    python tests/test_core/test_social_extractor_v2.py --doc-id <id> --stage relations
    python tests/test_core/test_social_extractor_v2.py --article-id <id> --stage groups
    python tests/test_core/test_social_extractor_v2.py --doc-id <id> --stage groups

`--stage frames` stops the pipeline after Stage 2 (source selection → Stage 1
frame extraction → Stage 2 deterministic clean/merge). It never calls
relation_renderer / group_assigner / validator / compose, so its
relation_renderer.md / group_assigner.md prompts being empty is irrelevant —
only an empty frame_extractor.md prompt can fail this mode.

`--stage relations` goes one step further: source selection → Stage 1 →
Stage 2 → Stage 3 relation rendering. It never calls group_assigner /
validator / compose, so an empty group_assigner.md is irrelevant in this
mode; an empty relation_renderer.md still fails with prompt_not_configured
(same as the full pipeline) whenever there is at least one renderable clean
frame to render.

`--stage groups` goes one step further still: source selection → Stage 1 →
Stage 2 → Stage 3 → Stage 4 group assignment. It never calls validate_final_relations
/ compose_formal_records, so neither runs and nothing is written to the DB.
An empty group_assigner.md still fails with prompt_not_configured (same as
the full pipeline) whenever there is at least one candidate relation to
assign a group to.
"""

import os
import sys
import time
import argparse
import asyncio
import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env.prod"))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

import structlog
from logs.logger_conf import setup_logging
setup_logging()
logger = structlog.get_logger()

# Independent logger, just for result payloads — does not touch the global
# structlog config, so normal log lines elsewhere stay exactly as before.
result_logger = structlog.wrap_logger(
    structlog.PrintLogger(),
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", key="@timestamp"),
        structlog.processors.JSONRenderer(ensure_ascii=False, sort_keys=True, indent=2),
    ],
)

from constants import MigrateConfig, MongoDBCollectionConfig, LLMsConfigExtractRelationship
from core.common.mongo.client import get_mongo_client
from core.v03.social_extractor_v2 import (
    generate_social_relations_async,
    generate_debug_pipeline_async,
    generate_social_relations_for_segments_async,
    compose_formal_records,
    select_social_relation_source,
    select_social_relation_sources,
    PromptNotConfiguredError,
)
from core.v03.social_extractor_v2.schemas import LegalFrame, CleanFrame, CandidateRelation, GroupAssignment, to_dict
from core.v03.social_extractor_v2.frame_cleaner import clean_and_merge_frames
from core.v03.social_extractor_v2.relation_renderer import render_relation_from_frame, render_relations_async
from core.v03.social_extractor_v2.group_assigner import suggest_group_family, _fallback_groups, assign_groups_async
from core.v03.social_extractor_v2.validator import validate_final_relations
from core.v03.social_extractor_v2.extractor import extract_legal_frames_async
from core.v03.social_extractor_v2.utils import read_prompt


# --- Offline smoke tests (pytest-collectible, no DB/LLM calls) -------------

def test_prompt_loader_detects_empty_prompt():
    for name in ("frame_extractor", "relation_renderer", "group_assigner"):
        try:
            read_prompt(name)
            assert False, f"expected PromptNotConfiguredError for {name}"
        except PromptNotConfiguredError:
            pass


def test_source_selection_default_extract_for_ordinary_article():
    sel = select_social_relation_source("Điều 5. Hồ sơ đề nghị cấp phép", [])
    assert sel["should_extract"] is True
    assert sel["reason"] == "default_extract_source"


def test_source_selection_hard_skip_by_title():
    sel = select_social_relation_source("Điều 1. Phạm vi điều chỉnh", [])
    assert sel["should_extract"] is False
    assert sel["reason"] == "hard_skip_source"


def test_source_selection_hard_skip_by_class():
    sel = select_social_relation_source("Điều 9. Bất kỳ", ["Giải thích từ ngữ"])
    assert sel["should_extract"] is False
    assert sel["reason"] == "hard_skip_source"


def test_frame_cleaner_drops_denylist_actor():
    frames = [LegalFrame(frame_id="f1", frame_type="procedure_record",
                         primary_subject="hồ sơ", counterparty="Doanh nghiệp",
                         action="nộp", is_bilateral=True)]
    clean, audit = clean_and_merge_frames(frames)
    assert clean == []
    assert any(e.get("drop_reason") == "denylist_actor" for e in audit)


def test_frame_cleaner_drops_unilateral_without_counterparty():
    frames = [LegalFrame(frame_id="f1", frame_type="state_management_responsibility",
                         primary_subject="Ủy ban nhân dân tỉnh", counterparty="",
                         action="chịu trách nhiệm quản lý", is_bilateral=False)]
    clean, audit = clean_and_merge_frames(frames)
    assert clean == []
    assert any(e.get("drop_reason") == "unilateral_no_counterparty" for e in audit)


def test_frame_cleaner_merges_detail_variants():
    frames = [
        LegalFrame(frame_id="f1", frame_type="reporting_information", primary_subject="Doanh nghiệp",
                   counterparty="Cơ quan quản lý", action="báo cáo tình hình hoạt động",
                   domain="đầu tư", is_bilateral=True, detail_level="primary"),
        LegalFrame(frame_id="f2", frame_type="reporting_information", primary_subject="Doanh nghiệp",
                   counterparty="Cơ quan quản lý", action="báo cáo chậm nhất 60 ngày trước khi ngừng hoạt động",
                   domain="đầu tư", is_bilateral=True, detail_level="detail"),
    ]
    clean, audit = clean_and_merge_frames(frames)
    assert len(clean) == 1
    assert set(clean[0].source_frame_ids) == {"f1", "f2"}
    assert any(e.get("drop_reason") == "merged_detail_variant" for e in audit)


def test_frame_cleaner_canonicalizes_agency_first():
    frames = [LegalFrame(frame_id="f1", frame_type="reporting_information", primary_subject="Doanh nghiệp",
                         counterparty="Cơ quan quản lý nhà nước", action="báo cáo", is_bilateral=True)]
    clean, _ = clean_and_merge_frames(frames)
    assert len(clean) == 1
    assert clean[0].actor_1 == "Cơ quan quản lý nhà nước"


def test_validator_rejects_invalid_relation_text():
    rel = CandidateRelation(relation_id="r1", relation_text="Báo cáo gì đó", social_relation="x",
                            actor_1="A", actor_2="B", frame_type="other")
    grp = GroupAssignment(group_id="g1", social_relation_group="Các QHXH về x", relation_ids=["r1"])
    final, audit = validate_final_relations([rel], [grp])
    assert final == []
    assert any(e.get("drop_reason") == "invalid_relation_text" for e in audit)


def test_validator_accepts_well_formed_relation():
    cf = CleanFrame(frame_id="f1", frame_type="reporting_information", actor_1="Cơ quan quản lý",
                    actor_2="Doanh nghiệp", action="báo cáo tình hình hoạt động", source_frame_ids=["f1"])
    rel = render_relation_from_frame(cf)
    groups = _fallback_groups([rel])
    final, _ = validate_final_relations([rel], groups)
    assert len(final) == 1
    assert set(final[0].keys()) == {"relation_text", "social_relation", "social_relation_group"}
    assert final[0]["social_relation_group"].startswith("Các QHXH về ")


def test_compose_formal_records_shape():
    social_relations = [{
        "relation_text": "Quan hệ giữa Cơ quan quản lý và Doanh nghiệp trong việc báo cáo",
        "social_relation": "báo cáo",
        "social_relation_group": "Các QHXH về báo cáo, cung cấp, trao đổi thông tin, dữ liệu",
    }]
    formal = compose_formal_records(social_relations, doc_id="d1", article_id="a1", article_class=["X"])
    assert len(formal["groups"]) == 1
    assert len(formal["relations"]) == 1
    assert len(formal["mappings"]) == 1
    assert formal["relations"][0]["status"] == "ACTIVE"
    assert formal["mappings"][0]["article_id"] == "a1"


# --- Read-only DB / LLM helpers --------------------------------------------

def _get_db():
    return get_mongo_client()[MigrateConfig.MIGRATE_CORE_DB]


def _check_llm_reachable() -> bool:
    url = getattr(LLMsConfigExtractRelationship, "LLMS_BASE_URL", None)
    if not url:
        return False
    try:
        with httpx.Client(timeout=8) as c:
            r = c.post(
                url,
                json={
                    "model": LLMsConfigExtractRelationship.LLMS_MODEL_NAME,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                    "stream": False,
                },
                headers={"Content-Type": "application/json", "Authorization": "Bearer abc-123"},
            )
            return r.status_code == 200
    except Exception:
        return False


def _fetch_article(db, article_id: str) -> dict:
    return db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME].find_one(
        {"article_id": article_id},
        {"_id": 0, "article_id": 1, "doc_id": 1, "article_title": 1, "article_content": 1, "article_index": 1},
    )


def _fetch_articles_by_doc(db, doc_id: str) -> list:
    cursor = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME].find(
        {"doc_id": doc_id},
        {"_id": 0, "article_id": 1, "doc_id": 1, "article_title": 1, "article_content": 1, "article_index": 1},
    ).sort("article_index", 1)
    return list(cursor)


def _fetch_classes_map(db, article_ids: list) -> dict:
    classes_map = {}
    if not article_ids:
        return classes_map
    cursor = db[MongoDBCollectionConfig.LAW_ARTICLE_CLASS_COLLECTION_NAME].find(
        {"article_id": {"$in": article_ids}},
        {"_id": 0, "article_id": 1, "class": 1},
    )
    for doc in cursor:
        cls = doc.get("class", [])
        classes_map[doc.get("article_id")] = cls if isinstance(cls, list) else []
    return classes_map


async def _run_single_article(article_content: str, article_title: str, article_class: list, debug: bool) -> dict:
    if debug:
        return await generate_debug_pipeline_async(article_content, article_title=article_title, article_class=article_class)
    return await generate_social_relations_async(article_content, article_title=article_title, article_class=article_class)


# --- --stage frames: source selection -> Stage 1 -> Stage 2 only -----------
# Never calls relation_renderer / group_assigner / validator / compose, and
# never touches any DB. Only frame_extractor.md needs to be configured.

async def _run_frames_stage_single(article_content: str, article_title: str | None, article_class: list) -> dict:
    probe = article_title if article_title else article_content
    source_selection = select_social_relation_source(probe, article_class)
    if not source_selection["should_extract"]:
        return {"source_selection": source_selection, "raw_frames": [], "clean_frames": [], "audit": []}

    raw_frames = await extract_legal_frames_async(
        article_content, article_title=article_title, article_class=article_class,
    )
    clean_frames, audit = clean_and_merge_frames(raw_frames)
    return {
        "source_selection": source_selection,
        "raw_frames": to_dict(raw_frames),
        "clean_frames": to_dict(clean_frames),
        "audit": audit,
    }


async def _run_frames_stage_for_segments(segments: list, classes_map: dict, concurrency: int) -> dict:
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
                "raw_frames": [],
                "clean_frames": [],
                "audit": [],
            }
            if not src_sel["should_extract"]:
                return base
            seg = seg_by_id.get(article_id, {})
            title = seg.get("title") if isinstance(seg.get("title"), str) else ""
            content = seg.get("content") if isinstance(seg.get("content"), str) else ""
            article_content = f"{title}\n{content}".strip() if title else content
            raw_frames = await extract_legal_frames_async(
                article_content, article_title=title or None, article_class=article_class,
                client=client, semaphore=semaphore,
            )
            clean_frames, audit = clean_and_merge_frames(raw_frames)
            base["raw_frames"] = to_dict(raw_frames)
            base["clean_frames"] = to_dict(clean_frames)
            base["audit"] = audit
            return base

        results = await asyncio.gather(*[_run_one(e) for e in selection["segments"]], return_exceptions=True)

    out_segments: list = []
    for entry, res in zip(selection["segments"], results):
        if isinstance(res, Exception):
            logger.error("frames_stage_segment_failed", action="main",
                         article_id=entry.get("article_id"),
                         **{"error.code": "EXTRACT", "error.message": str(res)})
            out_segments.append({
                "article_id": entry.get("article_id"),
                "article_class": entry.get("article_class"),
                "source_selection": entry.get("source_selection"),
                "raw_frames": [],
                "clean_frames": [],
                "audit": [],
                "error": str(res),
            })
        else:
            out_segments.append(res)

    return {"segments": out_segments, "source_selection_summary": selection["summary"]}


# --- --stage relations: source selection -> Stage 1 -> Stage 2 -> Stage 3 --
# Never calls group_assigner / validator / compose, and never touches any DB.
# An empty group_assigner.md is irrelevant here; an empty relation_renderer.md
# still fails with prompt_not_configured whenever there is something to render.

async def _run_relations_stage_single(article_content: str, article_title: str | None, article_class: list) -> dict:
    probe = article_title if article_title else article_content
    source_selection = select_social_relation_source(probe, article_class)
    if not source_selection["should_extract"]:
        return {
            "source_selection": source_selection,
            "raw_frames": [], "clean_frames": [], "candidate_relations": [], "audit": [],
        }

    timeout = httpx.Timeout(600.0, connect=10.0)
    semaphore = asyncio.Semaphore(1)
    async with httpx.AsyncClient(timeout=timeout) as client:
        raw_frames = await extract_legal_frames_async(
            article_content, article_title=article_title, article_class=article_class,
            client=client, semaphore=semaphore,
        )
        clean_frames, audit = clean_and_merge_frames(raw_frames)
        renderable = [cf for cf in clean_frames if cf.renderable]
        relations = []
        if renderable:
            relations = await render_relations_async(
                renderable, client=client, semaphore=semaphore, article_title=article_title,
            )

    return {
        "source_selection": source_selection,
        "raw_frames": to_dict(raw_frames),
        "clean_frames": to_dict(clean_frames),
        "candidate_relations": to_dict(relations),
        "audit": audit,
    }


async def _run_relations_stage_for_segments(segments: list, classes_map: dict, concurrency: int) -> dict:
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
                "raw_frames": [], "clean_frames": [], "candidate_relations": [], "audit": [],
            }
            if not src_sel["should_extract"]:
                return base
            seg = seg_by_id.get(article_id, {})
            title = seg.get("title") if isinstance(seg.get("title"), str) else ""
            content = seg.get("content") if isinstance(seg.get("content"), str) else ""
            article_content = f"{title}\n{content}".strip() if title else content
            raw_frames = await extract_legal_frames_async(
                article_content, article_title=title or None, article_class=article_class,
                client=client, semaphore=semaphore,
            )
            clean_frames, audit = clean_and_merge_frames(raw_frames)
            renderable = [cf for cf in clean_frames if cf.renderable]
            relations = []
            if renderable:
                relations = await render_relations_async(
                    renderable, client=client, semaphore=semaphore, article_title=title or None,
                )
            base["raw_frames"] = to_dict(raw_frames)
            base["clean_frames"] = to_dict(clean_frames)
            base["candidate_relations"] = to_dict(relations)
            base["audit"] = audit
            return base

        results = await asyncio.gather(*[_run_one(e) for e in selection["segments"]], return_exceptions=True)

    out_segments: list = []
    for entry, res in zip(selection["segments"], results):
        if isinstance(res, Exception):
            logger.error("relations_stage_segment_failed", action="main",
                         article_id=entry.get("article_id"),
                         **{"error.code": "EXTRACT", "error.message": str(res)})
            out_segments.append({
                "article_id": entry.get("article_id"),
                "article_class": entry.get("article_class"),
                "source_selection": entry.get("source_selection"),
                "raw_frames": [], "clean_frames": [], "candidate_relations": [], "audit": [],
                "error": str(res),
            })
        else:
            out_segments.append(res)

    return {"segments": out_segments, "source_selection_summary": selection["summary"]}


# --- --stage groups: source selection -> Stage 1 -> Stage 2 -> Stage 3 ->
# Stage 4 group assignment. Never calls validate_final_relations or
# compose_formal_records, and never touches any DB. An empty group_assigner.md
# still fails with prompt_not_configured whenever there is something to assign.

async def _run_groups_stage_single(article_content: str, article_title: str | None, article_class: list) -> dict:
    probe = article_title if article_title else article_content
    source_selection = select_social_relation_source(probe, article_class)
    if not source_selection["should_extract"]:
        return {
            "source_selection": source_selection,
            "raw_frames": [], "clean_frames": [], "candidate_relations": [], "group_assignments": [], "audit": [],
        }

    timeout = httpx.Timeout(600.0, connect=10.0)
    semaphore = asyncio.Semaphore(1)
    async with httpx.AsyncClient(timeout=timeout) as client:
        raw_frames = await extract_legal_frames_async(
            article_content, article_title=article_title, article_class=article_class,
            client=client, semaphore=semaphore,
        )
        clean_frames, audit = clean_and_merge_frames(raw_frames)
        renderable = [cf for cf in clean_frames if cf.renderable]
        relations = []
        if renderable:
            relations = await render_relations_async(
                renderable, client=client, semaphore=semaphore, article_title=article_title,
            )
        groups = []
        if relations:
            groups = await assign_groups_async(
                relations, client=client, semaphore=semaphore, article_title=article_title,
            )

    return {
        "source_selection": source_selection,
        "raw_frames": to_dict(raw_frames),
        "clean_frames": to_dict(clean_frames),
        "candidate_relations": to_dict(relations),
        "group_assignments": to_dict(groups),
        "audit": audit,
    }


async def _run_groups_stage_for_segments(segments: list, classes_map: dict, concurrency: int) -> dict:
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
                "raw_frames": [], "clean_frames": [], "candidate_relations": [], "group_assignments": [], "audit": [],
            }
            if not src_sel["should_extract"]:
                return base
            seg = seg_by_id.get(article_id, {})
            title = seg.get("title") if isinstance(seg.get("title"), str) else ""
            content = seg.get("content") if isinstance(seg.get("content"), str) else ""
            article_content = f"{title}\n{content}".strip() if title else content
            raw_frames = await extract_legal_frames_async(
                article_content, article_title=title or None, article_class=article_class,
                client=client, semaphore=semaphore,
            )
            clean_frames, audit = clean_and_merge_frames(raw_frames)
            renderable = [cf for cf in clean_frames if cf.renderable]
            relations = []
            if renderable:
                relations = await render_relations_async(
                    renderable, client=client, semaphore=semaphore, article_title=title or None,
                )
            groups = []
            if relations:
                groups = await assign_groups_async(
                    relations, client=client, semaphore=semaphore, article_title=title or None,
                )
            base["raw_frames"] = to_dict(raw_frames)
            base["clean_frames"] = to_dict(clean_frames)
            base["candidate_relations"] = to_dict(relations)
            base["group_assignments"] = to_dict(groups)
            base["audit"] = audit
            return base

        results = await asyncio.gather(*[_run_one(e) for e in selection["segments"]], return_exceptions=True)

    out_segments: list = []
    for entry, res in zip(selection["segments"], results):
        if isinstance(res, Exception):
            logger.error("groups_stage_segment_failed", action="main",
                         article_id=entry.get("article_id"),
                         **{"error.code": "EXTRACT", "error.message": str(res)})
            out_segments.append({
                "article_id": entry.get("article_id"),
                "article_class": entry.get("article_class"),
                "source_selection": entry.get("source_selection"),
                "raw_frames": [], "clean_frames": [], "candidate_relations": [], "group_assignments": [], "audit": [],
                "error": str(res),
            })
        else:
            out_segments.append(res)

    return {"segments": out_segments, "source_selection_summary": selection["summary"]}


# --- CLI run modes ---------------------------------------------------------

def _run_article_mode(db, article_id: str, created_by: str, debug: bool, stage: str) -> None:
    article = _fetch_article(db, article_id)
    if not article:
        logger.error("article_not_found", action="main", article_id=article_id)
        sys.exit(1)

    doc_id = str(article.get("doc_id", ""))
    article_class = _fetch_classes_map(db, [article_id]).get(article_id, [])
    title = (article.get("article_title") or "").strip()
    content = (article.get("article_content") or "").strip()
    article_content = f"{title}\n{content}".strip()

    logger.info("article_loaded", action="main", article_id=article_id, doc_id=doc_id,
                article_title=title, article_class=article_class, content_len=len(content))

    if stage == "frames":
        try:
            result = asyncio.run(_run_frames_stage_single(article_content, title or None, article_class))
        except PromptNotConfiguredError as e:
            logger.error("prompt_not_configured", action="main", article_id=article_id,
                         **{"error.code": "PROMPT", "error.message": str(e)})
            sys.exit(2)
        result_logger.info("frames_stage_result", action="main", article_id=article_id,
                           source_selection=result["source_selection"],
                           raw_frames=result["raw_frames"], clean_frames=result["clean_frames"],
                           audit=result["audit"],
                           raw_frames_count=len(result["raw_frames"]),
                           clean_frames_count=len(result["clean_frames"]),
                           guarantee_no_db_writes=True)
        return

    if stage == "relations":
        try:
            result = asyncio.run(_run_relations_stage_single(article_content, title or None, article_class))
        except PromptNotConfiguredError as e:
            logger.error("prompt_not_configured", action="main", article_id=article_id,
                         **{"error.code": "PROMPT", "error.message": str(e)})
            sys.exit(2)
        result_logger.info("relations_stage_result", action="main", article_id=article_id,
                           source_selection=result["source_selection"],
                           raw_frames=result["raw_frames"], clean_frames=result["clean_frames"],
                           candidate_relations=result["candidate_relations"], audit=result["audit"],
                           raw_frames_count=len(result["raw_frames"]),
                           clean_frames_count=len(result["clean_frames"]),
                           candidate_relations_count=len(result["candidate_relations"]),
                           guarantee_no_db_writes=True)
        return

    if stage == "groups":
        try:
            result = asyncio.run(_run_groups_stage_single(article_content, title or None, article_class))
        except PromptNotConfiguredError as e:
            logger.error("prompt_not_configured", action="main", article_id=article_id,
                         **{"error.code": "PROMPT", "error.message": str(e)})
            sys.exit(2)
        result_logger.info("groups_stage_result", action="main", article_id=article_id,
                           source_selection=result["source_selection"],
                           raw_frames=result["raw_frames"], clean_frames=result["clean_frames"],
                           candidate_relations=result["candidate_relations"],
                           group_assignments=result["group_assignments"], audit=result["audit"],
                           raw_frames_count=len(result["raw_frames"]),
                           clean_frames_count=len(result["clean_frames"]),
                           candidate_relations_count=len(result["candidate_relations"]),
                           group_assignments_count=len(result["group_assignments"]),
                           guarantee_no_db_writes=True)
        return

    try:
        result = asyncio.run(_run_single_article(article_content, title or None, article_class, debug))
    except PromptNotConfiguredError as e:
        logger.error("prompt_not_configured", action="main", article_id=article_id,
                     **{"error.code": "PROMPT", "error.message": str(e)})
        sys.exit(2)

    if debug:
        result_logger.info("debug_pipeline_result", action="main", article_id=article_id, **result)
        social_relations = result.get("final_social_relations", [])
    else:
        social_relations = result.get("social_relations", [])
        result_logger.info("extraction_result", action="main", article_id=article_id,
                           social_relations=social_relations, social_relations_count=len(social_relations))

    formal = compose_formal_records(
        social_relations, doc_id=doc_id, article_id=article_id,
        article_class=article_class, created_by=created_by,
    )
    result_logger.info("formal_records_result", action="main", article_id=article_id,
                       groups=formal["groups"], relations=formal["relations"], mappings=formal["mappings"],
                       groups_count=len(formal["groups"]), relations_count=len(formal["relations"]),
                       mappings_count=len(formal["mappings"]))


def _run_doc_mode(db, doc_id: str, concurrency: int, created_by: str, debug: bool, stage: str) -> None:
    articles = _fetch_articles_by_doc(db, doc_id)
    if not articles:
        logger.error("doc_articles_not_found", action="main", doc_id=doc_id)
        sys.exit(1)

    article_ids = [a["article_id"] for a in articles if a.get("article_id")]
    classes_map = _fetch_classes_map(db, article_ids)
    segments = [
        {
            "article_id": a["article_id"],
            "title": (a.get("article_title") or "").strip(),
            "content": (a.get("article_content") or "").strip(),
            "index": a.get("article_index"),
        }
        for a in articles
    ]

    logger.info("doc_segments_loaded", action="main", doc_id=doc_id,
                total_segments=len(segments), concurrency=concurrency)

    if stage == "frames":
        try:
            result = asyncio.run(_run_frames_stage_for_segments(segments, classes_map, concurrency))
        except PromptNotConfiguredError as e:
            logger.error("prompt_not_configured", action="main", doc_id=doc_id,
                         **{"error.code": "PROMPT", "error.message": str(e)})
            sys.exit(2)

        logger.info("doc_source_selection_summary", action="main", doc_id=doc_id,
                    **result["source_selection_summary"])

        total_raw = sum(len(seg["raw_frames"]) for seg in result["segments"])
        total_clean = sum(len(seg["clean_frames"]) for seg in result["segments"])
        result_logger.info("doc_frames_stage_result", action="main", doc_id=doc_id,
                           segments=result["segments"],
                           total_raw_frames=total_raw, total_clean_frames=total_clean,
                           guarantee_no_db_writes=True)
        return

    if stage == "relations":
        try:
            result = asyncio.run(_run_relations_stage_for_segments(segments, classes_map, concurrency))
        except PromptNotConfiguredError as e:
            logger.error("prompt_not_configured", action="main", doc_id=doc_id,
                         **{"error.code": "PROMPT", "error.message": str(e)})
            sys.exit(2)

        logger.info("doc_source_selection_summary", action="main", doc_id=doc_id,
                    **result["source_selection_summary"])

        total_raw = sum(len(seg["raw_frames"]) for seg in result["segments"])
        total_clean = sum(len(seg["clean_frames"]) for seg in result["segments"])
        total_relations = sum(len(seg["candidate_relations"]) for seg in result["segments"])
        result_logger.info("doc_relations_stage_result", action="main", doc_id=doc_id,
                           segments=result["segments"],
                           total_raw_frames=total_raw, total_clean_frames=total_clean,
                           total_candidate_relations=total_relations,
                           guarantee_no_db_writes=True)
        return

    if stage == "groups":
        try:
            result = asyncio.run(_run_groups_stage_for_segments(segments, classes_map, concurrency))
        except PromptNotConfiguredError as e:
            logger.error("prompt_not_configured", action="main", doc_id=doc_id,
                         **{"error.code": "PROMPT", "error.message": str(e)})
            sys.exit(2)

        logger.info("doc_source_selection_summary", action="main", doc_id=doc_id,
                    **result["source_selection_summary"])

        total_raw = sum(len(seg["raw_frames"]) for seg in result["segments"])
        total_clean = sum(len(seg["clean_frames"]) for seg in result["segments"])
        total_relations = sum(len(seg["candidate_relations"]) for seg in result["segments"])
        total_groups = sum(len(seg["group_assignments"]) for seg in result["segments"])
        result_logger.info("doc_groups_stage_result", action="main", doc_id=doc_id,
                           segments=result["segments"],
                           total_raw_frames=total_raw, total_clean_frames=total_clean,
                           total_candidate_relations=total_relations, total_group_assignments=total_groups,
                           guarantee_no_db_writes=True)
        return

    try:
        result = asyncio.run(generate_social_relations_for_segments_async(
            segments, classes_map, concurrency=concurrency, debug=debug))
    except PromptNotConfiguredError as e:
        logger.error("prompt_not_configured", action="main", doc_id=doc_id,
                     **{"error.code": "PROMPT", "error.message": str(e)})
        sys.exit(2)

    logger.info("doc_source_selection_summary", action="main", doc_id=doc_id,
                **result["source_selection_summary"])

    all_groups, all_relations, all_mappings = [], [], []
    total_relations = 0
    prompt_errors = 0
    for seg in result["segments"]:
        article_id = seg["article_id"]
        if "prompt_not_configured" in str(seg.get("error", "")) or "not configured" in str(seg.get("error", "")):
            prompt_errors += 1
        social_relations = seg["extraction"].get("social_relations", [])
        total_relations += len(social_relations)

        result_logger.info("segment_extraction_result", action="main", doc_id=doc_id, article_id=article_id,
                           article_class=seg["article_class"], **seg["source_selection"],
                           social_relations=social_relations, social_relations_count=len(social_relations))

        if not social_relations:
            continue
        formal = compose_formal_records(
            social_relations, doc_id=doc_id, article_id=article_id,
            article_class=seg["article_class"], created_by=created_by,
        )
        all_groups.extend(formal["groups"])
        all_relations.extend(formal["relations"])
        all_mappings.extend(formal["mappings"])

    if prompt_errors:
        logger.error("prompt_not_configured", action="main", doc_id=doc_id,
                     **{"error.code": "PROMPT", "error.message": "one or more segments hit an unconfigured prompt"},
                     segments_with_prompt_error=prompt_errors)

    result_logger.info("doc_formal_records_result", action="main", doc_id=doc_id,
                       groups=all_groups, relations=all_relations, mappings=all_mappings,
                       groups_count=len(all_groups), relations_count=len(all_relations),
                       mappings_count=len(all_mappings), total_relations_extracted=total_relations)


def main():
    parser = argparse.ArgumentParser(description="Read-only CLI test for social_extractor_v2 (no DB writes).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--article-id", type=str, help="Run the pipeline for a single article_id.")
    group.add_argument("--doc-id", type=str, help="Run the pipeline for every article of a doc_id.")
    parser.add_argument("--concurrency", type=int, default=3, help="Async LLM concurrency, --doc-id only (default: 3).")
    parser.add_argument("--created-by", type=str, default="test_social_extractor_v2",
                        help="created_by tag on in-memory formal records (not persisted).")
    parser.add_argument("--skip-llm-check", action="store_true", help="Skip the LLM reachability pre-check.")
    parser.add_argument("--debug", action="store_true", help="Emit the full intermediate pipeline (all stages).")
    parser.add_argument("--stage", choices=["full", "frames", "relations", "groups"], default="full",
                        help="'full' runs the entire pipeline (default). 'frames' stops after Stage 2 "
                             "(source selection -> Stage 1 extract_legal_frames_async -> Stage 2 "
                             "clean_and_merge_frames); it never calls relation_renderer/group_assigner/"
                             "validator/compose and ignores --debug. 'relations' goes one step further, "
                             "stopping after Stage 3 relation_rendering; it never calls group_assigner/"
                             "validator/compose and ignores --debug. 'groups' goes one step further still, "
                             "stopping after Stage 4 group assignment; it never calls validate_final_relations/"
                             "compose_formal_records and ignores --debug.")
    args = parser.parse_args()

    if args.article_id and args.concurrency != 3:
        logger.warning("concurrency_ignored_for_article_mode", action="main", concurrency=args.concurrency)

    if args.stage in ("frames", "relations", "groups") and args.debug:
        logger.warning("debug_ignored_for_stage", action="main", stage=args.stage)

    if not args.skip_llm_check:
        logger.info("llm_reachability_check_started", action="main")
        if not _check_llm_reachable():
            logger.error("llm_reachability_check_failed", action="main",
                         **{"error.code": "LLM", "error.message": "endpoint not reachable"},
                         endpoint=getattr(LLMsConfigExtractRelationship, "LLMS_BASE_URL", "(not set)"))
            sys.exit(1)
        logger.info("llm_reachability_check_success", action="main")

    db = _get_db()
    started_at = time.time()

    if args.article_id:
        _run_article_mode(db, args.article_id, args.created_by, args.debug, args.stage)
    else:
        _run_doc_mode(db, args.doc_id, args.concurrency, args.created_by, args.debug, args.stage)

    logger.info("test_social_extractor_v2_done", action="main",
                elapsed_seconds=round(time.time() - started_at, 3), guarantee_no_db_writes=True)


if __name__ == "__main__":
    main()
