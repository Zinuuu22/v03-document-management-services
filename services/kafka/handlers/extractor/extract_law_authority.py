"""
Extract Law Authority Handler — uses core LLM extractor (v03).

Replaces the legacy regex-based handler. Core module processes per article;
full document text is never sent to the LLM.
"""

import asyncio
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

import httpx
import structlog
from structlog.contextvars import bind_contextvars

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from services.kafka.common.base_consumer import BaseConsumer
from constants import (
    AppConfig,
    MongoDBCollectionConfig,
    PreprocessTopics,
    SignalRConfig,
)
from core.v03.law_authority_extractor import (
    compose_formal_records,
    find_law_authority_candidate_spans,
    generate_law_authorities_async,
    is_law_authority_candidate,
)

logger = structlog.get_logger()


class ExtractLawAuthorityHandler(BaseConsumer):

    TOPIC       = PreprocessTopics.EXTRACT_LAW_AUTHORITY_QUERY_TOPIC
    GROUP_ID    = PreprocessTopics.EXTRACT_LAW_AUTHORITY_GROUP
    NUM_WORKERS = AppConfig.EXTRACT_NORM_LAW_AUTHORITY_NUMBER_WORKER

    _LLM_CONCURRENCY = 3

    def __init__(self):
        super().__init__()
        self._db = self._init_db(extra_collections={
            "articles":        MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME,
            "law_documents":   MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME,
            "law_agencies":    MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME,
            "law_authority":   MongoDBCollectionConfig.LAW_AUTHORITY_COLLECTION_NAME,
            "law_authority_mapping": MongoDBCollectionConfig.LAW_AUTHORITY_MAPPING_COLLECTION_NAME,
            "pipeline":        MongoDBCollectionConfig.PIPELINE_DOCUMENT_STATE_COLLECTION_NAME,
        })

    # ------------------------------------------------------------------
    # BaseConsumer interface
    # ------------------------------------------------------------------

    def get_handler_name(self) -> str:
        return "extract_law_authority"

    def _get_response_topic(self) -> str:
        return PreprocessTopics.EXTRACT_LAW_AUTHORITY_RESPONSE_TOPIC

    @staticmethod
    def _make_response(request_id: str) -> Dict[str, Any]:
        return {
            "request_id": request_id,
            "status":     True,
            "doc_id":     None,
            "segments":   [],
            "records":    [],
            "summary":    {"assignments_count": 0, "segments_processed": 0},
        }

    # ------------------------------------------------------------------
    # Main message processor
    # ------------------------------------------------------------------

    async def process_message(self, raw_message) -> None:
        self._init_trace_context(raw_message)
        bind_contextvars(task="KafkaExtractLawAuthority")

        data       = self._parse_message(raw_message)
        request_id = self._bind_request_context(data)
        doc_id     = data.get("doc_id")

        start_at = self._now()
        start    = time.time()
        response = self._make_response(request_id)
        response["doc_id"] = str(doc_id) if doc_id is not None else None

        try:
            bind_contextvars(step="step_1_fetch_data")
            articles = self._fetch_segments(doc_id)
            if not articles:
                response["status"] = False
                logger.error(
                    "extract_law_authority_failed",
                    action="process_message",
                    **{"event.status": "failed", "error.code": "NOSEG",
                       "error.message": "No segments found for doc_id"},
                    doc_id=doc_id,
                )
                self._update_pipeline_state(doc_id, "FAILED", start_at)
                self._send_response(response)
                self._notify_signalr(request_id, False)
                return

            doc_meta = self._fetch_doc_meta(doc_id)
            agencies = self._fetch_agencies()

            logger.info(
                "extract_law_authority_data_ready",
                action="process_message",
                doc_id=doc_id,
                articles_fetched=len(articles),
                agencies_loaded=len(agencies),
            )
            response["summary"]["articles_fetched"] = len(articles)

            bind_contextvars(step="step_2_extract")
            ext_start = time.time()
            authority_records, mapping_records, new_agencies, segments, extract_summary = await (
                self._extract_all_async(articles, doc_id, doc_meta, agencies)
            )
            ext_elapsed = round(time.time() - ext_start, 3)

            total_assignments = sum(len(s.get("assignments", [])) for s in segments)
            logger.info(
                "extract_law_authority_extraction_done",
                action="process_message",
                doc_id=doc_id,
                **{"event.duration": ext_elapsed},
                segments_processed=len(segments),
                assignments_count=total_assignments,
                candidate_articles=extract_summary["candidate_articles"],
                llm_calls=extract_summary["llm_calls"],
                article_errors=extract_summary["article_errors"],
            )

            bind_contextvars(step="step_3_insert")
            self._insert_records(authority_records, mapping_records, new_agencies)

            response["segments"] = segments
            response["records"]  = authority_records
            response["summary"]  = {
                "assignments_count":  total_assignments,
                "segments_processed": len(segments),
            }
            self._update_pipeline_state(doc_id, "PROCESSED", start_at)
            response["status"] = True

        except Exception as e:
            response["status"] = False
            self._update_pipeline_state(doc_id, "FAILED", start_at)
            logger.error(
                "extract_law_authority_failed",
                action="process_message",
                **{"event.status": "failed",
                   "event.duration": round(time.time() - start, 3),
                   "error.code": "SYS", "error.message": str(e)},
                doc_id=doc_id,
                exc_info=True,
            )

        total_elapsed = round(time.time() - start, 3)
        logger.info(
            "process_law_authority_message_done",
            action="process_message",
            **{"event.duration": total_elapsed, "event.status": "success" if response["status"] else "failed"},
            doc_id=doc_id,
        )

        bind_contextvars(step="step_4_send_response")
        self._send_response(response)
        self._notify_signalr(request_id, response["status"])

    # ------------------------------------------------------------------
    # Async extraction
    # ------------------------------------------------------------------

    async def _extract_all_async(
        self,
        articles: List[dict],
        doc_id: str,
        doc_meta: dict,
        agencies: List[dict],
    ):
        sem     = asyncio.Semaphore(self._LLM_CONCURRENCY)
        timeout = httpx.Timeout(600.0, connect=10.0)

        shared_seen_keys:    set  = set()
        shared_agency_cache: dict = {}

        summary = {
            "candidate_articles": 0,
            "llm_calls":          0,
            "article_errors":     0,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            tasks = [
                self._process_one_article(
                    art, doc_id, doc_meta, agencies, client, sem,
                    shared_seen_keys, shared_agency_cache, summary,
                )
                for art in articles
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_authority_records: List[dict] = []
        all_mapping_records:   List[dict] = []
        all_new_agencies:      List[dict] = []
        all_segments:          List[dict] = []

        for r in results:
            if isinstance(r, Exception):
                logger.error(
                    "article_task_exception",
                    action="_extract_all_async",
                    **{"error.code": "EXT", "error.message": str(r)},
                )
                summary["article_errors"] += 1
                continue
            all_authority_records.extend(r.get("authorities", []))
            all_mapping_records.extend(r.get("mappings", []))
            all_new_agencies.extend(r.get("agencies_to_create", []))
            if r.get("segment"):
                all_segments.append(r["segment"])

        return all_authority_records, all_mapping_records, all_new_agencies, all_segments, summary

    async def _process_one_article(
        self,
        art: dict,
        doc_id: str,
        doc_meta: dict,
        agencies: List[dict],
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        shared_seen_keys: set,
        shared_agency_cache: dict,
        summary: dict,
    ) -> dict:
        empty = {"authorities": [], "mappings": [], "agencies_to_create": [], "segment": None}

        try:
            article_id    = str(art.get("article_id", ""))
            article_title = (art.get("article_title") or "").strip()
            article_text  = f"{article_title}\n{(art.get('article_content') or '').strip()}".strip()

            if not is_law_authority_candidate(article_text):
                return empty

            summary["candidate_articles"] += 1
            candidate_spans = find_law_authority_candidate_spans(article_text)

            summary["llm_calls"] += 1
            llm_output = await generate_law_authorities_async(
                article_text,
                None,
                None,
                client,
                sem,
                article_title=article_title,
                doc_title=doc_meta.get("doc_title", ""),
                doc_code=doc_meta.get("doc_code", ""),
                candidate_spans=candidate_spans,
            )

            formal = compose_formal_records(
                article_id=article_id,
                authorities=llm_output,
                doc_id=doc_id,
                doc_meta=doc_meta,
                agency_lookup=agencies,
                seen_keys=shared_seen_keys,
                new_agency_cache=shared_agency_cache,
            )
            if llm_output:
                formal["segment"] = {
                    "article_id":  article_id,
                    "assignments": llm_output,
                }
            return formal

        except Exception as e:
            logger.error(
                "process_article_failed",
                action="_process_one_article",
                article_id=art.get("article_id"),
                **{"error.code": "EXT", "error.message": str(e)},
                exc_info=True,
            )
            summary["article_errors"] += 1
            return empty

    # ------------------------------------------------------------------
    # DB insert
    # ------------------------------------------------------------------

    @staticmethod
    def _collapse_ws(text: str) -> str:
        """Collapse runs of whitespace to a single space and strip. For dedup comparison only."""
        return re.sub(r'\s+', ' ', text).strip()

    def _insert_records(
        self,
        authority_records: List[dict],
        mapping_records:   List[dict],
        new_agencies:      List[dict],
    ):
        inserted_authorities = 0
        inserted_mappings    = 0
        inserted_agencies    = 0

        for ag in new_agencies:
            try:
                if not self._db["law_agencies"].find_one({"agency_id": ag["agency_id"]}):
                    self._db["law_agencies"].insert_one(dict(ag))
                    inserted_agencies += 1
            except Exception as e:
                logger.error(
                    "insert_agency_failed",
                    agency_id=ag.get("agency_id"),
                    **{"error.code": "DB", "error.message": str(e)},
                    exc_info=True,
                )

        # compose_formal_records generates a fresh uuid4() authority_id each call,
        # so dedup cannot rely on authority_id matching.
        # Dedup is scoped to (article_id, normalized authority_quotation):
        #   - scoping prevents boilerplate clauses shared across articles from collapsing into one record
        #   - normalization collapses whitespace/newline differences only (no diacritics, no lowercase)
        auth_to_article: dict = {}
        for m in mapping_records:
            aid = m.get("authority_id")
            if aid and aid not in auth_to_article:
                auth_to_article[aid] = m.get("article_id")

        auth_id_remap: dict = {}
        for rec in authority_records:
            try:
                raw_quotation = (rec.get("authority_quotation") or "").strip()
                norm_quotation = self._collapse_ws(raw_quotation)
                article_id = auth_to_article.get(rec["authority_id"])

                existing = None
                if norm_quotation and article_id:
                    existing_auth_ids = [
                        m["authority_id"]
                        for m in self._db["law_authority_mapping"].find(
                            {"article_id": article_id},
                            {"authority_id": 1, "_id": 0},
                        )
                    ]
                    if existing_auth_ids:
                        for a in self._db["law_authority"].find(
                            {"authority_id": {"$in": existing_auth_ids}},
                            {"authority_id": 1, "authority_quotation": 1, "_id": 0},
                        ):
                            if self._collapse_ws(a.get("authority_quotation") or "") == norm_quotation:
                                existing = a
                                break

                if existing:
                    auth_id_remap[rec["authority_id"]] = existing["authority_id"]
                else:
                    self._db["law_authority"].insert_one(dict(rec))
                    auth_id_remap[rec["authority_id"]] = rec["authority_id"]
                    inserted_authorities += 1
            except Exception as e:
                logger.error(
                    "insert_authority_failed",
                    authority_id=rec.get("authority_id"),
                    **{"error.code": "DB", "error.message": str(e)},
                    exc_info=True,
                )
                auth_id_remap[rec["authority_id"]] = rec["authority_id"]

        for m in mapping_records:
            try:
                resolved_auth_id = auth_id_remap.get(m["authority_id"], m["authority_id"])
                existing = self._db["law_authority_mapping"].find_one({
                    "authority_id": resolved_auth_id,
                    "doc_id":       m.get("doc_id"),
                    "article_id":   m.get("article_id"),
                    "agency_id":    m.get("agency_id"),
                })
                if not existing:
                    m_insert = dict(m)
                    m_insert["authority_id"] = resolved_auth_id
                    self._db["law_authority_mapping"].insert_one(m_insert)
                    inserted_mappings += 1
            except Exception as e:
                logger.error(
                    "insert_mapping_failed",
                    authority_id=m.get("authority_id"),
                    **{"error.code": "DB", "error.message": str(e)},
                    exc_info=True,
                )

        logger.info(
            "insert_records_summary",
            action="_insert_records",
            inserted_authorities=inserted_authorities,
            inserted_mappings=inserted_mappings,
            inserted_agencies=inserted_agencies,
        )
        return inserted_authorities, inserted_mappings, inserted_agencies

    # ------------------------------------------------------------------
    # Fetch helpers
    # ------------------------------------------------------------------

    def _fetch_segments(self, doc_id) -> List[dict]:
        candidates = [doc_id]
        try:
            s = str(doc_id)
            if s not in candidates:
                candidates.append(s)
            if s.isdigit():
                iv = int(s)
                if iv not in candidates:
                    candidates.append(iv)
        except Exception:
            pass

        try:
            cursor = self._db["articles"].find(
                {"doc_id": {"$in": candidates}},
                {"_id": 0, "doc_id": 1, "article_id": 1, "article_title": 1,
                 "article_content": 1, "article_index": 1},
            ).sort("article_index", 1)
            segments = list(cursor)
            logger.debug("segments_fetched", count=len(segments), doc_id=doc_id)
            return segments
        except Exception as e:
            logger.error(
                "fetch_segments_failed",
                doc_id=doc_id,
                **{"error.code": "DB", "error.message": str(e)},
                exc_info=True,
            )
            return []

    def _fetch_doc_meta(self, doc_id) -> dict:
        try:
            doc = self._db["law_documents"].find_one(
                {"doc_id": doc_id},
                {"_id": 0, "doc_id": 1, "doc_code": 1, "doc_title": 1,
                 "doc_effective_date": 1, "doc_expiry_date": 1, "effective_status_id": 1},
            )
            if doc:
                return doc
        except Exception as e:
            logger.error(
                "fetch_doc_meta_failed",
                doc_id=doc_id,
                **{"error.code": "DB", "error.message": str(e)},
                exc_info=True,
            )
        return {"doc_id": doc_id}

    def _fetch_agencies(self) -> List[dict]:
        try:
            cursor = self._db["law_agencies"].find(
                {"status": {"$in": ["ACTIVE", "Active", "active", None]}},
                {"_id": 0, "agency_id": 1, "agency_name": 1},
            )
            return [d for d in cursor if d.get("agency_id") and d.get("agency_name")]
        except Exception as e:
            logger.error(
                "fetch_agencies_failed",
                **{"error.code": "DB", "error.message": str(e)},
                exc_info=True,
            )
            return []

    # ------------------------------------------------------------------
    # Pipeline state
    # ------------------------------------------------------------------

    def _update_pipeline_state(self, doc_id: str, status: str, start_at: str) -> None:
        if not doc_id:
            return

        finish_at = self._now()
        step_info = {
            "status":        status,
            "start_at":      start_at,
            "finish_at":     finish_at,
            "duration_time": self._duration(start_at, finish_at),
        }

        extraction_fields = [
            "metadata_extraction",
            "keyword_extraction",
            "relationship_extraction",
            "article_relationship_extraction",
            "regulated_entity_extraction",
            "social_relation_extraction",
            "authority_extraction",
        ]

        try:
            self._db["pipeline"].update_one(
                {"doc_id": doc_id},
                {
                    "$set": {
                        "authority_extraction": step_info,
                        "last_modified_at":     finish_at,
                        "last_modified_by":     "admin",
                    },
                    "$setOnInsert": {
                        "doc_id":     doc_id,
                        "created_at": finish_at,
                        "created_by": "admin",
                    },
                },
                upsert=True,
            )

            record = self._db["pipeline"].find_one({"doc_id": doc_id})
            if record:
                all_processed = all(
                    (record.get(f) or {}).get("status") == "PROCESSED"
                    for f in extraction_fields
                )
                if all_processed:
                    self._db["pipeline"].update_one(
                        {"doc_id": doc_id},
                        {"$set": {
                            "status":           "DONE",
                            "last_modified_at": self._now(),
                            "last_modified_by": "admin",
                        }},
                    )
                    logger.debug(
                        "pipeline_all_steps_completed",
                        action="_update_pipeline_state",
                        doc_id=doc_id,
                    )

            logger.info(
                "update_pipeline_state_success",
                action="_update_pipeline_state",
                doc_id=doc_id,
                status=status,
            )
        except Exception as e:
            logger.error(
                "pipeline_state_update_failed",
                action="_update_pipeline_state",
                doc_id=doc_id,
                **{"error.code": "MONGO", "error.message": str(e)},
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # SignalR
    # ------------------------------------------------------------------

    def _notify_signalr(self, request_id: str, success: bool) -> None:
        self.push_to_signalr_api(
            api_url=SignalRConfig.API_URL,
            topic=SignalRConfig.UPLOAD_TOPIC,
            message={"request_id": request_id, "status": success},
        )
