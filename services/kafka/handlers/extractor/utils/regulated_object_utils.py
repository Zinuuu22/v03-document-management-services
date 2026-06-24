from typing import List, Dict
from datetime import datetime
from uuid import uuid4


def compose_formal_records(article_id: str, article_class: List[str], entities: List[Dict], created_by: str | None = None) -> List[Dict]:
    created_by_val = created_by if created_by else "system"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results: List[Dict] = []

    for e in entities:
        if not isinstance(e, dict):
            continue
        name = e.get("name") if isinstance(e.get("name"), str) else ""
        if not name:
            continue
        results.append({
            "article_id": article_id,
            "article_class": article_class,
            "regulated_entity_id": "RE-" + uuid4().hex,
            "regulated_entity_name": name,
            "regulated_entity_name_norm": name,
            "status": "Active",
            "created_date": now_str,
            "created_by": created_by_val,
            "last_modified": "",
            "last_modified_by": "",
        })
    return results


