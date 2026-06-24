"""
Batch test: select top-N law_article candidates likely to contain delegation clauses
(nội dung giao quyền), run the core law_authority extractor on each, and export
results to CSV for manual review.

Does NOT write to the database in any way.
Agencies are NOT passed to the LLM — only used in Python post-processing.

Usage:
    python tests/test_core/test_law_authority_to_csv.py
    python tests/test_core/test_law_authority_to_csv.py --limit 50
    python tests/test_core/test_law_authority_to_csv.py --limit 200 --concurrency 5
    python tests/test_core/test_law_authority_to_csv.py --output /tmp/my_review.csv

Output: tests/test_core/law_authority_100_cases.csv  (utf-8-sig, Excel-safe)
"""

import os
import sys
import csv
import json
import argparse
import asyncio
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, ".env.prod"))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from core.v03.law_authority_extractor import (
    is_law_authority_candidate,
    find_law_authority_candidate_spans,
    generate_law_authorities_async,
    compose_formal_records,
)
from constants import (
    MongoDBConfig, MongoDBCollectionConfig, MigrateConfig,
    LLMsConfigExtractRelationship,
)

# ---------------------------------------------------------------------------
# Scoring patterns
# ---------------------------------------------------------------------------

# Weight +2: strong delegation signals
_STRONG = re.compile(
    r"giao\s+Ch[íi]nh\s+ph[ủu]"
    r"|giao\s+Th[ủu]\s+t[ưu][ớo]ng\s+Ch[íi]nh\s+ph[ủu]"
    r"|giao\s+B[ộo]\s+tr[ưu][ởo]ng"
    r"|ch[ịi]u\s+tr[áa]ch\s+nhi[eệ]m\s+h[ưu][ớo]ng\s+d[aẫ]n"
    r"|do\s+B[ộo]\s+tr[ưu][ởo]ng.{0,60}quy\s*[dđ][ịi]nh"
    r"|B[ộo]\s+tr[ưu][ởo]ng.{0,60}quy\s*[dđ][ịi]nh"
    r"|Ch[íi]nh\s+ph[ủu]\s+quy\s*[dđ][ịi]nh"
    r"|Th[ủu]\s+t[ưu][ớo]ng\s+Ch[íi]nh\s+ph[ủu]\s+quy\s*[dđ][ịi]nh"
    r"|ch[ủu]\s+tr[ìi],?\s*ph[ốo]i\s+h[ợo]p",
    re.IGNORECASE | re.UNICODE,
)

# Weight +1: medium signals
_MEDIUM = re.compile(
    r"quy\s*[dđ][ịi]nh\s+chi\s+ti[eế]t"
    r"|h[ưu][ớo]ng\s+d[aẫ]n\s+thi\s+h[àa]nh"
    r"|h[ưu][ớo]ng\s+d[aẫ]n\s+th[uự]c\s+hi[eệ]n",
    re.IGNORECASE | re.UNICODE,
)

# Penalty -1: reference-only phrases (per unique match in text)
_REF_ONLY = re.compile(
    r"theo\s+quy\s*[dđ][ịi]nh\s+c[ủu]a"
    r"|th[uự]c\s+hi[eệ]n\s+theo\s+quy\s*[dđ][ịi]nh"
    r"|ph[ùu]\s+h[ợo]p\s+v[ớo]i\s+quy\s*[dđ][ịi]nh"
    r"|c[aă]n\s+c[ứu]\s+quy\s*[dđ][ịi]nh"
    r"|Lu[aậ]t\s+n[aà]y\s+quy\s*[dđ][ịi]nh\s+v[eề]"
    r"|[DĐ]i[eề]u\s+n[aà]y\s+quy\s*[dđ][ịi]nh\s+v[eề]",
    re.IGNORECASE | re.UNICODE,
)


def _score_article(text: str) -> int:
    strong_hits  = len(_STRONG.findall(text))
    medium_hits  = len(_MEDIUM.findall(text))
    ref_hits     = len(_REF_ONLY.findall(text))
    return strong_hits * 2 + medium_hits * 1 - ref_hits * 1


# ---------------------------------------------------------------------------
# DB helpers (read-only)
# ---------------------------------------------------------------------------

def _get_db():
    from urllib.parse import quote_plus
    from pymongo import MongoClient
    host     = MongoDBConfig.HOST
    port     = MongoDBConfig.PORT
    username = quote_plus(MongoDBConfig.USERNAME)
    password = quote_plus(MongoDBConfig.PASSWORD)
    auth_src = MongoDBConfig.AUTH_SOURCE
    uri = f"mongodb://{username}:{password}@{host}:{port}/?authSource={auth_src}"
    client = MongoClient(uri)
    return client[MigrateConfig.MIGRATE_CORE_DB]


def _fetch_agencies(db) -> List[dict]:
    try:
        cursor = db[MongoDBCollectionConfig.LAW_AGENCIES_COLLECTION_NAME].find(
            {"status": {"$in": ["ACTIVE", "Active", "active", None]}},
            {"_id": 0, "agency_id": 1, "agency_name": 1},
        )
        return [d for d in cursor if d.get("agency_id") and d.get("agency_name")]
    except Exception as e:
        print(f"[WARN] Could not fetch agencies: {e}", file=sys.stderr)
        return []


def _fetch_doc_metas(db, doc_ids: List) -> Dict[str, dict]:
    try:
        cursor = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME].find(
            {"doc_id": {"$in": list(doc_ids)}},
            {"_id": 0, "doc_id": 1, "doc_code": 1, "doc_title": 1,
             "doc_effective_date": 1, "doc_expiry_date": 1, "effective_status_id": 1},
        )
        return {str(d["doc_id"]): d for d in cursor if d.get("doc_id")}
    except Exception as e:
        print(f"[WARN] Could not fetch doc metas: {e}", file=sys.stderr)
        return {}


def _select_top_candidates(db, limit: int) -> List[dict]:
    """
    Scan law_articles, score each, return top `limit` by score (score > 0 only).
    Fetches up to 300k articles to ensure enough candidates even in a large corpus.
    """
    print(f"[INFO] Scanning law_articles for candidates (limit={limit}) …", file=sys.stderr)
    scored: List[Tuple[int, dict]] = []

    cursor = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME].find(
        {},
        {
            "_id": 0,
            "article_id": 1,
            "doc_id": 1,
            "article_title": 1,
            "article_content": 1,
            "article_index": 1,
        },
    ).limit(300_000)

    scan_count = 0
    for art in cursor:
        scan_count += 1
        title   = (art.get("article_title") or "").strip()
        content = (art.get("article_content") or "").strip()
        text    = f"{title}\n{content}".strip()
        if not text:
            continue
        score = _score_article(text)
        if score > 0:
            scored.append((score, art))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [art for _, art in scored[:limit]]

    print(
        f"[INFO] Scanned {scan_count} articles → {len(scored)} scored>0 → "
        f"selected top {len(selected)}",
        file=sys.stderr,
    )
    return selected


# ---------------------------------------------------------------------------
# LLM reachability check
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

async def _process_one_article(
    art: dict,
    agencies: List[dict],
    doc_meta: dict,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    shared_seen_keys: set,
    shared_agency_cache: dict,
) -> dict:
    """
    Returns a dict with fields needed to write CSV rows.
    On LLM error: returns a diagnostic row with error info.
    """
    article_id    = str(art.get("article_id", ""))
    article_title = (art.get("article_title") or "").strip()
    article_index = art.get("article_index", "")
    content       = (art.get("article_content") or "").strip()
    seg_text      = f"{article_title}\n{content}".strip()

    doc_id    = str(art.get("doc_id", ""))
    doc_code  = doc_meta.get("doc_code", "")
    doc_title = doc_meta.get("doc_title", "")

    spans   = find_law_authority_candidate_spans(seg_text)
    is_cand = is_law_authority_candidate(seg_text, agencies=agencies)

    if not is_cand:
        # Scored positive by Python patterns but rejected by core prefilter —
        # return empty diagnostic so we can track false positives at the scoring layer.
        return {
            "doc_id": doc_id, "doc_code": doc_code, "doc_title": doc_title,
            "article_id": article_id, "article_index": article_index,
            "article_title": article_title,
            "is_candidate": False,
            "authorities": [],
            "mappings_by_auth_id": {},
            "error": None,
        }

    # --- LLM call (agencies NOT passed to LLM) ---
    try:
        llm_output = await generate_law_authorities_async(
            seg_text, None, None, client, sem,
            article_title=article_title,
            doc_title=doc_title,
            doc_code=doc_code,
            candidate_spans=spans,
        )
    except Exception as exc:
        return {
            "doc_id": doc_id, "doc_code": doc_code, "doc_title": doc_title,
            "article_id": article_id, "article_index": article_index,
            "article_title": article_title,
            "is_candidate": True,
            "authorities": [],
            "mappings_by_auth_id": {},
            "error": str(exc),
        }

    # --- Python post-processing (agencies used here, not in LLM) ---
    formal = compose_formal_records(
        article_id=article_id,
        authorities=llm_output,
        doc_id=doc_id,
        doc_meta=doc_meta,
        agency_lookup=agencies,
        seen_keys=shared_seen_keys,
        new_agency_cache=shared_agency_cache,
    )

    # Index mappings by authority_id for easy lookup per row.
    mappings_by_auth_id: Dict[str, List[dict]] = {}
    for m in formal.get("mappings", []):
        aid = m.get("authority_id", "")
        mappings_by_auth_id.setdefault(aid, []).append(m)

    return {
        "doc_id": doc_id, "doc_code": doc_code, "doc_title": doc_title,
        "article_id": article_id, "article_index": article_index,
        "article_title": article_title,
        "is_candidate": True,
        "authorities": formal.get("authorities", []),
        "mappings_by_auth_id": mappings_by_auth_id,
        "error": None,
    }


async def _run_pipeline(
    articles: List[dict],
    agencies: List[dict],
    doc_meta_index: Dict[str, dict],
    concurrency: int,
) -> List[dict]:
    sem     = asyncio.Semaphore(concurrency)
    timeout = httpx.Timeout(600.0, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        shared_seen_keys: set = set()
        shared_agency_cache: dict = {}

        tasks = []
        for art in articles:
            doc_id   = str(art.get("doc_id", ""))
            doc_meta = doc_meta_index.get(doc_id, {})
            tasks.append(_process_one_article(
                art, agencies, doc_meta, client, sem,
                shared_seen_keys, shared_agency_cache,
            ))

        total    = len(tasks)
        done_n   = 0
        results  = []
        llm_calls = 0
        auth_rows = 0

        for coro in asyncio.as_completed(tasks):
            res = await coro
            done_n += 1
            results.append(res)
            if res["is_candidate"]:
                llm_calls += 1
            auth_rows += max(len(res["authorities"]), 1 if res["is_candidate"] else 0)
            print(
                f"\r[INFO] {done_n}/{total} processed | "
                f"LLM calls: {llm_calls} | authority rows: {auth_rows}",
                end="",
                file=sys.stderr,
            )

    print("", file=sys.stderr)
    return results


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "doc_id",
    "article_id",
    "doc_code",
    "tên điều",
    "authority_content",    # LLM summary (formal authority_content); verbatim fallback if summary absent
    "authority_quotation",  # verbatim delegation sentence (formal authority_quotation)
    "formal_record_authority",
    "formal_record_mapping",
]


def _write_csv(results: List[dict], output_path: str) -> int:
    rows_written = 0
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for res in results:
            doc_id        = res["doc_id"]
            article_id    = res["article_id"]
            doc_code      = res["doc_code"]
            article_title = res["article_title"]
            error         = res.get("error")
            authorities   = res.get("authorities", [])
            mappings_idx  = res.get("mappings_by_auth_id", {})

            if error:
                # LLM error diagnostic row
                writer.writerow({
                    "doc_id":                  doc_id,
                    "article_id":              article_id,
                    "doc_code":                doc_code,
                    "tên điều":                article_title,
                    "authority_content":       "",
                    "authority_quotation":     "",
                    "formal_record_authority": json.dumps({"error": error}, ensure_ascii=False, indent=2),
                    "formal_record_mapping":   json.dumps([], ensure_ascii=False, indent=2),
                })
                rows_written += 1
                continue

            if not res["is_candidate"]:
                # Passed scoring but rejected by core prefilter — skip silently
                # (these are not false positives the reviewer needs to see)
                continue

            if not authorities:
                # Candidate article: LLM returned no authorities → false positive diagnostic
                writer.writerow({
                    "doc_id":                  doc_id,
                    "article_id":              article_id,
                    "doc_code":                doc_code,
                    "tên điều":                article_title,
                    "authority_content":       "",
                    "authority_quotation":     "",
                    "formal_record_authority": json.dumps({}, ensure_ascii=False, indent=2),
                    "formal_record_mapping":   json.dumps([], ensure_ascii=False, indent=2),
                })
                rows_written += 1
                continue

            # One row per extracted authority.
            # authority_content = formal record authority_content (LLM summary or verbatim fallback).
            # authority_quotation = formal record authority_quotation (verbatim extraction evidence).
            for auth in authorities:
                auth_id   = auth.get("authority_id", "")
                mappings  = mappings_idx.get(auth_id, [])
                writer.writerow({
                    "doc_id":                  doc_id,
                    "article_id":              article_id,
                    "doc_code":                doc_code,
                    "tên điều":                article_title,
                    "authority_content":       auth.get("authority_content", ""),
                    "authority_quotation":     auth.get("authority_quotation", ""),
                    "formal_record_authority": json.dumps(auth, ensure_ascii=False, indent=2),
                    "formal_record_mapping":   json.dumps(mappings, ensure_ascii=False, indent=2),
                })
                rows_written += 1

    return rows_written


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_output = os.path.join(script_dir, "law_authority_100_cases.csv")

    parser = argparse.ArgumentParser(
        description=(
            "Select top-N law_article candidates for delegation content "
            "(nội dung giao quyền), run core extractor, export to CSV. "
            "NO DB writes. Agencies NOT passed to LLM."
        )
    )
    parser.add_argument("--limit",       type=int, default=100,          help="Number of top candidates to process (default: 100)")
    parser.add_argument("--concurrency", type=int, default=3,            help="Async LLM concurrency (default: 3)")
    parser.add_argument("--output",      type=str, default=default_output, help=f"CSV output path (default: {default_output})")
    args = parser.parse_args()

    # --- LLM reachability check (fail fast before any DB work) ---
    print("[INFO] Checking LLM endpoint …", file=sys.stderr)
    if not _check_llm_reachable():
        endpoint = getattr(LLMsConfigExtractRelationship, "LLMS_BASE_URL", "(not set)")
        print(
            f"[ERROR] LLM endpoint not reachable: {endpoint}\n"
            "Aborting — no point fetching data if LLM is down.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("[INFO] LLM endpoint OK.", file=sys.stderr)

    # --- DB: select candidates ---
    db = _get_db()

    articles = _select_top_candidates(db, limit=args.limit)
    if not articles:
        print("[ERROR] No candidate articles found. Aborting.", file=sys.stderr)
        sys.exit(1)

    # --- DB: batch fetch doc metas ---
    unique_doc_ids = list({str(a.get("doc_id")) for a in articles if a.get("doc_id")})
    doc_meta_index = _fetch_doc_metas(db, unique_doc_ids)
    print(
        f"[INFO] {len(articles)} candidate articles | {len(doc_meta_index)} unique docs",
        file=sys.stderr,
    )

    # --- DB: fetch agencies (for Python post-processing only) ---
    agencies = _fetch_agencies(db)
    print(f"[INFO] {len(agencies)} agencies loaded (Python post-processing only).", file=sys.stderr)

    # --- Run async pipeline ---
    print(
        f"[INFO] Running extractor | concurrency={args.concurrency} | "
        f"LLM: {getattr(LLMsConfigExtractRelationship, 'LLMS_BASE_URL', '?')}",
        file=sys.stderr,
    )
    started_at = datetime.now()
    results = asyncio.run(_run_pipeline(articles, agencies, doc_meta_index, args.concurrency))
    elapsed = (datetime.now() - started_at).total_seconds()

    # --- Write CSV ---
    rows_written = _write_csv(results, args.output)

    # --- Summary ---
    llm_count  = sum(1 for r in results if r["is_candidate"] and not r.get("error"))
    err_count  = sum(1 for r in results if r.get("error"))
    auth_count = sum(len(r.get("authorities", [])) for r in results)
    fp_count   = sum(
        1 for r in results
        if r["is_candidate"] and not r.get("error") and not r.get("authorities")
    )

    print(
        f"\n[DONE] {len(results)} articles processed in {elapsed:.1f}s\n"
        f"  LLM calls:           {llm_count}\n"
        f"  Errors:              {err_count}\n"
        f"  Authorities found:   {auth_count}\n"
        f"  False positives:     {fp_count} (candidate but 0 authorities)\n"
        f"  CSV rows written:    {rows_written}\n"
        f"  Output:              {args.output}\n"
        f"\n  Guarantees:\n"
        f"    - No DB writes\n"
        f"    - Agencies NOT passed to LLM\n"
        f"    - Concurrency: {args.concurrency}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
