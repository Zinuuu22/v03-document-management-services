import os
import sys
import json
import httpx
from typing import List, Dict

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
loaded_any = False
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    loaded_any = True
if os.path.exists(ENV_PROD_PATH):
    load_dotenv(ENV_PROD_PATH)
    loaded_any = True
if not loaded_any:
    load_dotenv()

from core.common.llms import LLMs
from constants import LLMsConfigExtractRelationship
from .utils import read_prompt, normalize_name_no_diacritics, local_now_str


LLMs = LLMs(llms_config=LLMsConfigExtractRelationship)


def _normalize_relations_obj(obj) -> Dict[str, List[dict]]:
    if obj is None:
        return {"social_relations": []}
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            return {"social_relations": []}
    if isinstance(obj, list):
        return {"social_relations": obj}
    if isinstance(obj, dict):
        if "social_relations" in obj and isinstance(obj["social_relations"], list):
            return {"social_relations": obj["social_relations"]}
        for k in ("data", "result", "output", "response"):
            if k in obj:
                nested = obj[k]
                if isinstance(nested, dict) and "social_relations" in nested:
                    return {"social_relations": nested["social_relations"]}
                if isinstance(nested, list):
                    return {"social_relations": nested}
    return {"social_relations": []}




async def generate_social_relations_async(article_content: str, article_class: List[str], client: httpx.AsyncClient, semaphore) -> dict:
    """Return only the extracted relations list. Early dismiss if classes contain invalid labels (exact match)."""
    invalid_classes = ["Phạm vi điều chỉnh", "Hiệu Lực và Quy Định Chuyển Tiếp", "Giải Thích Thuật Ngữ"]
    if isinstance(article_class, list) and any(cls in invalid_classes for cls in article_class):
        return {"social_relations": []}

    prompt_template = read_prompt("social_extractor")
    prompt = f"{prompt_template}\n\n# Đầu vào\n\"\"\"\n{article_content}\n\"\"\"\n"

    async with semaphore:
        response = await LLMs.llms_async(prompt, client=client)
        if response and isinstance(response, str) and response.find("null") != -1:
            response = response.replace("null", "false")
        logger.debug("receive_llm_response", action="generate_social_relations", response_len=len(response) if response else 0)

        result = None
        try:
            result = LLMs.llms_post_process(response)
        except Exception as e:
            logger.error("LLMs.llms_post_process failed", action="generate_social_relations", 
                        **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
            result = None

    normalized = _normalize_relations_obj(result)

    cleaned: List[dict] = []
    for item in normalized.get("social_relations", []):
        if not isinstance(item, dict):
            continue
        rel_text = item.get("relation_text")
        rel_name = item.get("social_relation")
        cleaned.append({
            "relation_text": rel_text,
            "social_relation": rel_name,
        })
    return {"social_relations": cleaned}


def compose_debug_record(content: str, article_id: str, article_class: List[str], relations: dict) -> dict:
    rels = relations.get("social_relations", []) if isinstance(relations, dict) else []
    with_meta: List[dict] = []
    for r in rels:
        if isinstance(r, dict):
            obj = dict(r)
            obj["article_id"] = article_id
            obj["article_class"] = article_class
            with_meta.append(obj)
    return {
        "legal_segment": content,
        "social_relations_extracted": {"social_relations": with_meta},
    }


def compose_formal_records(article_id: str, article_class: List[str], relations: dict, created_by: str | None = None, doc_id: str | None = None) -> Dict[str, List[dict]]:
    """
    Compose formal records for the new data model with two collections:
    - law_social_relation: master list of social relations (one per unique relation)
    - law_social_relation_mapping: links (doc_id, article_id) to social_relation_id
    
    Returns:
        Dict with keys:
        - 'relations': List of records for law_social_relation collection
        - 'mappings': List of records for law_social_relation_mapping collection
    """
    rels = relations.get("social_relations", []) if isinstance(relations, dict) else []
    created_by_val = created_by if created_by else "system"
    now_str = local_now_str()
    relation_records: List[dict] = []
    mapping_records: List[dict] = []
    from uuid import uuid4

    for r in rels:
        if not isinstance(r, dict):
            continue
        name = r.get("relation_text") if isinstance(r.get("relation_text"), str) else ""
        legal_basis = r.get("social_relation") if isinstance(r.get("social_relation"), str) else ""
        
        if name != "":
            social_relation_id = str(uuid4())
            relation_records.append({
                "social_relation_id": social_relation_id,
                "social_relation_name": name,
                "social_relation_name_norm": normalize_name_no_diacritics(name) if isinstance(name, str) else name,
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
                "relation_type": "PRIMARY",
                "created_at": now_str,
                "created_by": created_by_val,
                "last_modified_at": now_str,
                "last_modified_by": created_by_val,
            })
    
    return {
        "relations": relation_records,
        "mappings": mapping_records,
    }

