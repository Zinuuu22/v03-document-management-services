import os
import sys
import json
import unicodedata
from statistics import median
from typing import Tuple

import pandas as pd
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()


def _prompts_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts.json")


def read_prompt(key: str) -> str:
    path = _prompts_path()
    if not os.path.exists(path):
        raise FileNotFoundError(f"prompts.json not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if key not in data:
        raise KeyError(f"Prompt key '{key}' not found in prompts.json")
    prompt_obj = data[key]
    if isinstance(prompt_obj, dict) and "prompt" in prompt_obj:
        return prompt_obj["prompt"]
    if isinstance(prompt_obj, str):
        return prompt_obj
    raise ValueError(f"Invalid prompt structure for key '{key}'")


def normalize_name_no_diacritics(text: str) -> str:
    if not isinstance(text, str):
        return ""
    try:
        nfkd = unicodedata.normalize("NFD", text)
        no_diacritics = "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn")
        collapsed = " ".join(no_diacritics.split())
        return collapsed.strip()
    except Exception:
        return ""


def local_now_str() -> str:
    """Return server local time in 'YYYY-MM-DD HH:MM:SS'."""
    from datetime import datetime

    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def append_jsonl_line(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _safe_actor_pair(actors) -> Tuple[str, str]:
    a1 = ""
    a2 = ""
    if isinstance(actors, list):
        if len(actors) >= 1 and isinstance(actors[0], str):
            a1 = actors[0]
        if len(actors) >= 2 and isinstance(actors[1], str):
            a2 = actors[1]
    return a1, a2


def _extract_from_relation_text(text: str) -> Tuple[str, str, str]:
    if not isinstance(text, str):
        return "", "", ""
    t = text.strip().strip('"')
    patterns = [
        r"(?i)\bquan\s*hệ\s*giữa\s+(.*?)\s+(?:và|and)\s+(.*?)\s+(?:trong\s+việc|về|trong)\s+(.*)",
        r"(?i)\bquan\s*hệ\s*giữa\s+(.*?)\s+(?:và|and)\s+(.*)"
    ]
    for pat in patterns:
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m:
            g1 = m.group(1).strip().rstrip(',.;') if m.lastindex and m.lastindex >= 1 else ""
            g2 = m.group(2).strip().rstrip(',.;') if m.lastindex and m.lastindex >= 2 else ""
            g3 = m.group(3).strip().rstrip(',.;') if m.lastindex and m.lastindex >= 3 else ""
            return g1, g2, g3
    return "", "", ""


def debug_jsonl_to_csv(jsonl_path: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)

    rows = []
    record_counts = []
    num_records = 0

    if not os.path.isfile(jsonl_path):
        df = pd.DataFrame(columns=[
            "doc_id",
            "article_id",
            "relation_text",
            "actor_1",
            "actor_2",
            "social_relation",
            "legal_segment",
        ])
        out_csv = os.path.join(out_dir, "relations.csv")
        df.to_csv(out_csv, index=False, encoding="utf-8")
        cleaned_csv = os.path.join(out_dir, "relations_cleaned.csv")
        df.to_csv(cleaned_csv, index=False, encoding="utf-8")
        logger.info("show_debug_stats", action="debug_jsonl_to_csv", records=0, relations=0, mean=0.0, median=0.0)
        return

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                rec = json.loads(s)
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue

            num_records += 1

            legal_segment = rec.get("legal_segment", "")
            sre = rec.get("social_relations_extracted", {})
            if isinstance(sre, str):
                try:
                    sre = json.loads(sre)
                except Exception:
                    sre = {}
            if not isinstance(sre, dict):
                sre = {}
            rel_list = sre.get("social_relations", [])
            if not isinstance(rel_list, list):
                rel_list = []

            record_counts.append(len(rel_list))

            for item in rel_list:
                if not isinstance(item, dict):
                    continue
                doc_id = item.get("doc_id", "")
                article_id = item.get("article_id", "")
                relation_text = item.get("relation_text", "")
                rel_name = item.get("social_relation", "")
                a1, a2, rel_from_text = _extract_from_relation_text(relation_text)
                rel = rel_name.strip() if isinstance(rel_name, str) and rel_name.strip() != "" else rel_from_text

                rows.append({
                    "doc_id": doc_id,
                    "article_id": article_id,
                    "relation_text": relation_text,
                    "actor_1": a1,
                    "actor_2": a2,
                    "social_relation": rel,
                    "legal_segment": legal_segment,
                })

    num_relations = len(rows)
    if num_records > 0:
        mean_per_record = (sum(record_counts) / float(num_records)) if num_records else 0.0
        median_per_record = median(record_counts) if record_counts else 0.0
    else:
        mean_per_record = 0.0
        median_per_record = 0.0

    logger.info("show_debug_stats", action="debug_jsonl_to_csv", records=num_records, relations=num_relations, mean=round(mean_per_record, 2), median=round(median_per_record, 2))

    df = pd.DataFrame(rows, columns=[
        "doc_id",
        "article_id",
        "relation_text",
        "actor_1",
        "actor_2",
        "social_relation",
        "legal_segment",
    ])
    out_csv = os.path.join(out_dir, "relations.csv")
    df.to_csv(out_csv, index=False, encoding="utf-8")

    required_cols = ["relation_text", "actor_1", "actor_2", "social_relation"]
    if not df.empty:
        mask = df[required_cols].applymap(lambda x: isinstance(x, str) and x.strip() != "").all(axis=1)
        df_cleaned = df.loc[mask]
    else:
        df_cleaned = df
    cleaned_csv = os.path.join(out_dir, "relations_cleaned.csv")
    df_cleaned.to_csv(cleaned_csv, index=False, encoding="utf-8")