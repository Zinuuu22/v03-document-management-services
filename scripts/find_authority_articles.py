from pymongo import MongoClient
from urllib.parse import quote_plus
import re
import json

_PATTERNS = [
    r"quy\s*định\s+chi\s+tiết",
    r"hướng\s+dẫn\s+thi\s+hành",
    r"giao\s+Chính\s+phủ",
    r"giao\s+Thủ\s+tướng\s+Chính\s+phủ",
    r"giao\s+Bộ\s+trưởng",
    r"chủ\s+trì\s*,?\s*phối\s+hợp",
    r"chịu\s+trách\s+nhiệm\s+hướng\s+dẫn",
    r"do\s+Bộ\s+trưởng.*?quy\s*định",
]
_RX = re.compile("|".join(_PATTERNS), re.IGNORECASE | re.UNICODE)


def find_authority_articles(db, limit=500):
    """Scan law_articles and return up to `limit` authority candidate articles.

    Returns list of dicts: doc_id, doc_code, doc_title, article_id,
    article_index, article_title, snippet.
    Algorithm and patterns are unchanged from the original standalone script.
    """
    rows = []
    for a in db.law_articles.find({}, {
        "_id": 0,
        "doc_id": 1,
        "article_id": 1,
        "article_title": 1,
        "article_content": 1,
        "index": 1,
    }).limit(200000):
        text = f"{a.get('article_title', '')}\n{a.get('article_content', '')}"
        if _RX.search(text):
            doc = db.law_documents.find_one(
                {"doc_id": a.get("doc_id")},
                {"_id": 0, "doc_id": 1, "doc_code": 1, "doc_title": 1}
            ) or {}
            rows.append({
                "doc_id": a.get("doc_id"),
                "doc_code": doc.get("doc_code"),
                "doc_title": doc.get("doc_title"),
                "article_id": a.get("article_id"),
                "article_index": a.get("index"),
                "article_title": a.get("article_title"),
                "snippet": text[:800],
            })
            if limit and len(rows) >= limit:
                break
    return rows


if __name__ == "__main__":
    USER = quote_plus("admin")
    PASSWORD = quote_plus("Ab@123456")
    HOST = "10.0.0.13"
    PORT = "27017"
    DB_NAME = "v03_core_11032026"
    uri = f"mongodb://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB_NAME}?authSource=admin"
    client = MongoClient(uri)
    db = client[DB_NAME]
    rows = find_authority_articles(db, limit=500)
    print("candidates:", len(rows))
    print(json.dumps(rows[:15], ensure_ascii=False, indent=2))
