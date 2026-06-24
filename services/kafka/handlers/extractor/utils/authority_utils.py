from typing import List, Dict
from datetime import datetime
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import core.v03.law_authority_extractor.extractor as lae


def set_agency_list(agencies: List[str]):
    lae.AGENCY_LIST = agencies or []


def extract_segment_assignments(seg_content: str) -> Dict:
    try:
        check = lae.detect_detail_regulation(seg_content)
    except Exception:
        check = {"has_pattern": False}

    if not isinstance(check, dict) or not check.get("has_pattern"):
        return {"has_pattern": False, "agency": None, "items": []}

    items: List[Dict] = []
    clause_content = check.get("clause_content")
    if isinstance(clause_content, str) and clause_content.strip():
        try:
            parts = lae.split_clause_content(clause_content)
            for p in parts or []:
                if not isinstance(p, dict):
                    continue
                title = p.get("clause_content_title")
                detail = p.get("clause_content_detail")
                if isinstance(title, str) and title.strip():
                    clean_title = re.sub(r"^\s*\d+(?:\.\d+)*\.\s*", "", title).strip()
                    if clean_title:
                        items.append({
                            "authority_content": clean_title,
                            "authority_content_detail": detail if isinstance(detail, list) else None
                        })
        except Exception:
            pass

    return {
        "has_pattern": True,
        "agency": check.get("agency"),
        "items": items,
    }


def compose_formal_records(article_id: str, article_class: List[str], agency_name: str, agency_id: str | None, items: List[Dict], created_by: str | None = None) -> List[Dict]:
    """
    Convert segmented items into formal draft records.
    """
    created_by_val = created_by if created_by else "system"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    results: List[Dict] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        content = it.get("authority_content")
        if not isinstance(content, str) or not content.strip():
            continue
        results.append({
            "article_id": article_id,
            "article_class": article_class,
            "agency_id": agency_id,
            "agency_name": agency_name,
            "authority_content": content.strip(),
            "authority_content_detail": it.get("authority_content_detail") if isinstance(it.get("authority_content_detail"), list) else None,
            "status": "Active",
            "created_date": now_str,
            "created_by": created_by_val,
            "last_modified": "",
            "last_modified_by": "",
        })
    return results
