"""
Cleanup script: loại bỏ số thứ tự đầu dòng (1., 2., 3., ...) trong authority_content
Collection: law_authority | DB: v03_core_11032026

Chạy với --dry-run để xem trước, không ghi DB.
Chạy không có flag để thực sự update.

Usage:
    python scripts/cleanup_authority_content_numbering.py --dry-run
    python scripts/cleanup_authority_content_numbering.py
"""

import re
import sys
import os
import argparse
from datetime import datetime
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

load_dotenv()

from core.common.mongo.client import get_mongo_client
from constants import MigrateConfig, MongoDBCollectionConfig

NUMBER_PREFIX = re.compile(r"^\s*\d+(?:\.\d+)*\.\s+")


def strip_prefix(content: str) -> str:
    return NUMBER_PREFIX.sub("", content).strip()


def main(dry_run: bool):
    client = get_mongo_client()
    db = client[MigrateConfig.MIGRATE_CORE_DB]
    col = db[MongoDBCollectionConfig.LAW_AUTHORITY_COLLECTION_NAME]

    query = {"authority_content": {"$regex": r"^\s*\d+(?:\.\d+)*\.\s+"}}
    total = col.count_documents(query)
    print(f"Bản ghi cần xử lý: {total}")

    if total == 0:
        print("Không có gì để cleanup.")
        return

    mode = "[DRY RUN]" if dry_run else "[LIVE]"
    print(f"Mode: {mode}\n")

    updated = 0
    skipped = 0
    errors = 0

    for doc in col.find(query, {"_id": 1, "authority_id": 1, "authority_content": 1}):
        old_content = doc.get("authority_content", "")
        new_content = strip_prefix(old_content)

        if not new_content:
            print(f"  SKIP (empty after strip): {doc.get('authority_id')} | {old_content[:60]!r}")
            skipped += 1
            continue

        if old_content == new_content:
            skipped += 1
            continue

        if dry_run:
            print(f"  WOULD UPDATE {doc.get('authority_id')}")
            print(f"    before: {old_content[:100]!r}")
            print(f"    after : {new_content[:100]!r}")
        else:
            try:
                col.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "authority_content": new_content,
                        "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "last_modified_by": "admin",
                    }}
                )
            except Exception as e:
                print(f"  ERROR {doc.get('authority_id')}: {e}")
                errors += 1
                continue

        updated += 1

    print(f"\n{'─'*50}")
    print(f"Kết quả {mode}:")
    print(f"  Sẽ/Đã update : {updated}")
    print(f"  Bỏ qua       : {skipped}")
    print(f"  Lỗi          : {errors}")

    if not dry_run and updated > 0:
        remaining = col.count_documents(query)
        print(f"\nKiểm tra sau cleanup:")
        print(f"  Còn bản ghi có prefix số: {remaining}")
        if remaining == 0:
            print("  Sạch hoàn toàn.")
        else:
            print(f"  Vẫn còn {remaining} bản ghi — kiểm tra lại.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Xem trước thay đổi, không ghi DB")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
