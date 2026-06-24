"""
Compose schema-stable formal records (groups / relations / mappings) from the
final social_relations list. Pure in-memory; never writes to any datastore.
"""

import os
import sys
from datetime import datetime
from typing import Dict, List
from uuid import uuid4

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from .utils import normalize_name_no_diacritics, local_now_str


def compose_formal_records(
    social_relations: List[dict],
    *,
    doc_id: str | None = None,
    article_id: str | None = None,
    article_class: List[str] | None = None,
    created_by: str = "social_extractor_v2",
    now: datetime | None = None,
) -> Dict[str, List[dict]]:
    
    rels = social_relations if isinstance(social_relations, list) else []
    created_by_val = created_by if created_by else "system"
    now_str = now.astimezone().strftime("%Y-%m-%d %H:%M:%S") if isinstance(now, datetime) else local_now_str()
    normalized_article_class = article_class if isinstance(article_class, list) else []

    group_records: List[dict] = []
    relation_records: List[dict] = []
    mapping_records: List[dict] = []

    group_id_by_norm: Dict[str, str] = {}
    seen_relations: set = set()

    for r in rels:
        if not isinstance(r, dict):
            continue
        name = r.get("relation_text") if isinstance(r.get("relation_text"), str) else ""
        core_relation = r.get("social_relation") if isinstance(r.get("social_relation"), str) else ""
        group_name = r.get("social_relation_group") if isinstance(r.get("social_relation_group"), str) else ""

        if not name or not core_relation or not group_name:
            continue

        group_norm = normalize_name_no_diacritics(group_name)
        relation_norm = normalize_name_no_diacritics(name)
        core_norm = normalize_name_no_diacritics(core_relation)

        dedupe_key = (relation_norm, core_norm, group_norm)
        if dedupe_key in seen_relations:
            continue
        seen_relations.add(dedupe_key)

        group_id = group_id_by_norm.get(group_norm)
        if group_id is None:
            group_id = str(uuid4())
            group_id_by_norm[group_norm] = group_id
            group_records.append({
                "social_relation_group_id": group_id,
                "social_relation_group_name": group_name,
                "social_relation_group_name_norm": group_norm,
                "status": "ACTIVE",
                "created_at": now_str,
                "created_by": created_by_val,
                "last_modified_at": now_str,
                "last_modified_by": created_by_val,
            })

        social_relation_id = str(uuid4())
        relation_records.append({
            "social_relation_id": social_relation_id,
            "social_relation_name": name,
            "social_relation_name_norm": relation_norm,
            "social_relation": core_relation,
            "social_relation_group_id": group_id,
            "social_relation_group_name": group_name,
            "status": "ACTIVE",
            "created_at": now_str,
            "created_by": created_by_val,
            "last_modified_at": now_str,
            "last_modified_by": created_by_val,
        })

        mapping_records.append({
            "doc_id": doc_id,
            "article_id": article_id,
            "social_relation_id": social_relation_id,
            "article_class": normalized_article_class,
            "created_at": now_str,
            "created_by": created_by_val,
            "last_modified_at": now_str,
            "last_modified_by": created_by_val,
        })

    return {
        "groups": group_records,
        "relations": relation_records,
        "mappings": mapping_records,
    }
