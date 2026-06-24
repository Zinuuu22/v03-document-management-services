from core.common.mongo.client import get_mongo_client
import os
import json
import random
import sys
import uuid
from collections import defaultdict
from datetime import datetime
from pymongo import MongoClient
import fasttext
from bson import ObjectId

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from constants import MongoDBConfig, MongoDBCollectionConfig, MigrateConfig

# =========================
# KẾT NỐI MONGODB
# =========================
client = get_mongo_client()
db = client[MigrateConfig.MIGRATE_CORE_DB]

law_documents_collection = db[MongoDBCollectionConfig.LAW_DOCUMENT_COLLECTION_NAME]
law_articles_collection = db[MongoDBCollectionConfig.LAW_ARTICLE_COLLECTION_NAME]
law_summaries_collection = db[MongoDBCollectionConfig.BIZ_SUMMARY_COLLECTION_NAME]
law_tree_components = db[MongoDBCollectionConfig.LAW_TREE_COMPONENT_COLLECTION_NAME]

biz_upload_documents_collection = db[MongoDBCollectionConfig.BIZ_UPLOAD_DOCUMENTS_COLLECTION_NAME]
biz_upload_articles_collection = db[MongoDBCollectionConfig.BIZ_UPLOAD_ARTICLES_COLLECTION_NAME]

# =========================
# 1️⃣ SUMMARY
# =========================
def get_summary_upload_document(doc_id, version="v1.0", summary_type="structured"):
    """
    Tóm tắt văn bản pháp luật dựa trên tiêu đề, phần, chương, mục, tiểu mục và tiêu đề các điều.
    """
    if not doc_id:
        return "Không tìm thấy văn bản"

    is_new = True
    
    # Step 1: Tìm kiếm trong cơ sở dữ liệu
    summary = law_summaries_collection.find_one({"doc_id": doc_id, "version": version})
    if summary:
        summary_content = summary.get("summary_content", "Không tìm thấy tóm tắt")
        is_new = False
        return is_new, summary_content
    
    
    # Step 2: Lấy thông tin văn bản gốc
    doc = biz_upload_documents_collection.find_one({"doc_id": doc_id})
    if not doc:
        return is_new, f"Không tìm thấy văn bản với doc_id = {doc_id}"        
    doc_title = doc.get("doc_title", "Không có tiêu đề").strip()

    # Step 3: Lấy toàn bộ các điều trong văn bản
    articles = list(biz_upload_articles_collection.find({"doc_id": doc_id}).sort("article_index", 1))
    if not articles:
        return is_new, f"Văn bản '{doc_title}' chưa có điều nào."

    # Step 4: Nhóm điều theo cấu trúc phân cấp
    summary_structure = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    for a in articles:
        part = a.get("part", "").strip() or "Không phân phần"
        chapter = a.get("chapter", "").strip() or "Không phân chương"
        section = a.get("section", "").strip() or "Không phân mục"
        sub_section = a.get("sub_section", "").strip() or "Không phân tiểu mục"
        title = a.get("article_title", "").strip()

        summary_structure[part][chapter][section][sub_section].append(title)

    # Step 5: Tạo bản tóm tắt có định dạng rõ ràng
    summary_lines = [f"{doc_title}\n"]
    for part, chapters in summary_structure.items():
        if part != "Không phân phần":
            summary_lines.append(f"== {part} ==")
        for chapter, sections in chapters.items():
            if chapter != "Không phân chương":
                summary_lines.append(f"{chapter}")
            for section, sub_sections in sections.items():
                if section != "Không phân mục":
                    summary_lines.append(f"{section}")
                for sub_section, articles_list in sub_sections.items():                    
                    if sub_section != "Không phân tiểu mục":
                        summary_lines.append(f"{sub_section}")
                    for article_title in articles_list:
                        summary_lines.append(f"{article_title}")
    summary = " ".join(summary_lines)
    
    # Step 6: Lưu tóm tắt vào cơ sở dữ liệu
    law_summaries_collection.insert_one({
        "doc_id": doc_id,
        "version": version,
        "summary_type": summary_type,
        "summary_content": summary,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    return is_new, summary


def get_summary(doc_id, version="v1.0", summary_type="structured"):
    """
    Tóm tắt văn bản pháp luật dựa trên tiêu đề, phần, chương, mục, tiểu mục và tiêu đề các điều.
    """
    if not doc_id:
        return "Không tìm thấy văn bản"

    is_new = True
    
    # Step 1: Tìm kiếm trong cơ sở dữ liệu
    summary = law_summaries_collection.find_one({"doc_id": doc_id, "version": version})
    if summary:
        summary_content = summary.get("summary_content", "Không tìm thấy tóm tắt")
        is_new = False
        return is_new, summary_content
    
    
    # Step 2: Lấy thông tin văn bản gốc
    doc = law_documents_collection.find_one({"doc_id": doc_id})
    if not doc:
        return is_new, f"Không tìm thấy văn bản với doc_id = {doc_id}"        
    doc_title = doc.get("doc_title", "Không có tiêu đề").strip()

    # Step 3: Lấy toàn bộ các điều trong văn bản
    articles = list(law_articles_collection.find({"doc_id": doc_id}).sort("article_index", 1))
    if not articles:
        return is_new, f"Văn bản '{doc_title}' chưa có điều nào."

    # Step 4: Nhóm điều theo cấu trúc phân cấp
    summary_structure = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    for a in articles:
        part = a.get("part", "").strip() or "Không phân phần"
        chapter = a.get("chapter", "").strip() or "Không phân chương"
        section = a.get("section", "").strip() or "Không phân mục"
        sub_section = a.get("sub_section", "").strip() or "Không phân tiểu mục"
        title = a.get("article_title", "").strip()

        summary_structure[part][chapter][section][sub_section].append(title)

    # Step 5: Tạo bản tóm tắt có định dạng rõ ràng
    summary_lines = [f"{doc_title}\n"]
    for part, chapters in summary_structure.items():
        if part != "Không phân phần":
            summary_lines.append(f"== {part} ==")
        for chapter, sections in chapters.items():
            if chapter != "Không phân chương":
                summary_lines.append(f"{chapter}")
            for section, sub_sections in sections.items():
                if section != "Không phân mục":
                    summary_lines.append(f"{section}")
                for sub_section, articles_list in sub_sections.items():                    
                    if sub_section != "Không phân tiểu mục":
                        summary_lines.append(f"{sub_section}")
                    for article_title in articles_list:
                        summary_lines.append(f"{article_title}")
    summary = " ".join(summary_lines)
    
    # Step 6: Lưu tóm tắt vào cơ sở dữ liệu
    law_summaries_collection.insert_one({
        "doc_id": doc_id,
        "version": version,
        "summary_type": summary_type,
        "summary_content": summary,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    return is_new, summary


def get_summaries_bulk(doc_ids, version="v1.0", summary_type="structured"):
    """
    Tạo hoặc lấy tóm tắt cho nhiều văn bản cùng lúc.
    Tối ưu hóa hiệu suất bằng cách batch query và batch insert.
    """
    if not doc_ids:
        return {}

    # Bước 1: Lấy tất cả summary hiện có
    existing_summaries = {
        s["doc_id"]: s["summary_content"]
        for s in law_summaries_collection.find(
            {"doc_id": {"$in": doc_ids}, "version": version},
            {"doc_id": 1, "summary_content": 1}
        )
    }

    # Bước 2: Lấy toàn bộ doc cần xử lý (những doc chưa có summary)
    missing_doc_ids = [d for d in doc_ids if d not in existing_summaries]
    summaries_to_insert = []
    new_summaries = {}

    if missing_doc_ids:
        docs = {
            d["doc_id"]: d
            for d in law_documents_collection.find({"doc_id": {"$in": missing_doc_ids}})
        }

        # Lấy toàn bộ articles liên quan (một lần)
        articles_cursor = law_articles_collection.find(
            {"doc_id": {"$in": missing_doc_ids}},
            {"doc_id": 1, "part": 1, "chapter": 1, "section": 1, "sub_section": 1, "article_title": 1, "article_index": 1}
        ).sort("article_index", 1)

        # Gom articles theo doc_id
        articles_by_doc = defaultdict(list)
        for art in articles_cursor:
            articles_by_doc[art["doc_id"]].append(art)

        # Sinh summary cho từng doc
        for doc_id in missing_doc_ids:
            doc = docs.get(doc_id)
            if not doc:
                new_summaries[doc_id] = f"Không tìm thấy văn bản với doc_id = {doc_id}"
                continue

            doc_title = doc.get("doc_title", "Không có tiêu đề")
            articles = articles_by_doc.get(doc_id, [])
            if not articles:
                new_summaries[doc_id] = f"Văn bản '{doc_title}' chưa có điều nào."
                continue

            # Gom nhóm cấu trúc
            summary_structure = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
            for a in articles:
                part = a.get("part", "").strip() or "Không phân phần"
                chapter = a.get("chapter", "").strip() or "Không phân chương"
                section = a.get("section", "").strip() or "Không phân mục"
                sub_section = a.get("sub_section", "").strip() or "Không phân tiểu mục"
                title = a.get("article_title", "").strip()
                summary_structure[part][chapter][section][sub_section].append(title)

            summary_lines = [f"{doc_title}\n"]
            for part, chapters in summary_structure.items():
                if part != "Không phân phần":
                    summary_lines.append(f"== {part} ==")
                for chapter, sections in chapters.items():
                    if chapter != "Không phân chương":
                        summary_lines.append(f"{chapter}")
                    for section, sub_sections in sections.items():
                        if section != "Không phân mục":
                            summary_lines.append(f"{section}")
                        for sub_section, articles_list in sub_sections.items():
                            if sub_section != "Không phân tiểu mục":
                                summary_lines.append(f"{sub_section}")
                            for article_title in articles_list:
                                summary_lines.append(f"{article_title}")

            summary_text = "\n".join(summary_lines)
            new_summaries[doc_id] = summary_text

            summaries_to_insert.append({
                "doc_id": doc_id,
                "version": version,
                "summary_type": summary_type,
                "summary_content": summary_text,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        # Bước 3: Insert batch summaries (nếu có)
        if summaries_to_insert:
            law_summaries_collection.insert_many(summaries_to_insert)

    # Bước 4: Hợp nhất kết quả cũ và mới
    return {**existing_summaries, **new_summaries}


# =========================
# 2️⃣ LOAD TREE CLASSES
# =========================
def get_classes(tree_id: str):
    """Lấy danh sách chủ đề con trong cây chuyên đề."""
    children = law_tree_components.find({
        "tree_id": tree_id,
        "subject_level": "CHILD"
    })
    return [
        {
            "class_name": child.get("subject_id", "").strip(),
            "doc_ids": child.get("doc_id_includes", [])
        }
        for child in children
    ]


# =========================
# 3️⃣ LOAD DATA
# =========================
def load_data_summary(class_name: str, doc_ids: list):
    """Tải nhanh dữ liệu tóm tắt của các văn bản theo class (batch)."""
    summaries = get_summaries_bulk(doc_ids)
    return [(content, class_name) for content in summaries.values() if content]



# =========================
# 4️⃣ FASTTEXT DATASET
# =========================
def prepare_fasttext_datasets(data, output_dir="datasets", test_ratio=0.2):
    os.makedirs(output_dir, exist_ok=True)
    random.shuffle(data)
    split_idx = int(len(data) * (1 - test_ratio))
    train_data, test_data = data[:split_idx], data[split_idx:]

    train_path = os.path.join(output_dir, "train.txt")
    test_path = os.path.join(output_dir, "test.txt")

    def write_file(path, dataset):
        with open(path, "w", encoding="utf-8") as f:
            for text, label in dataset:
                f.write(f"__label__{label.replace(' ', '__')} {text.replace(chr(10), ' ')}\n")

    write_file(train_path, train_data)
    write_file(test_path, test_data)
    return train_path, test_path


# =========================
# 5️⃣ TRAINING
# =========================
def train_fasttext_model(train_file, test_file, output_dir="models",
                         model_name="model", lr=0.1, epoch=30, dim=128, wordNgrams=2):
    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, f"{model_name}.bin")
    
    # Tính số lượng mẫu huấn luyện
    with open(train_file, "r", encoding="utf-8") as f:
        n_samples_train = len(f.readlines())
    
    # Tính số lượng mẫu test
    with open(test_file, "r", encoding="utf-8") as f:
        n_samples_test = len(f.readlines())
    
    # Huấn luyện mô hình
    model = fasttext.train_supervised(
        input=train_file,
        lr=lr,
        epoch=epoch,
        dim=dim,
        wordNgrams=wordNgrams,
        loss="softmax"
    )
    model.save_model(model_path)
    
    # Đánh giá mô hình
    _, precision, recall = model.test(test_file)
    f1 = 2 * precision * recall / (precision + recall + 1e-9)

    metrics = {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "n_samples_test": n_samples_test,
        "n_samples_train": n_samples_train,
        "trained_at": datetime.now()
    }
    
    logger.info("save_model_successful", action="train_fasttext_model", model_path=model_path, metrics = metrics)
    return model_path, metrics


if __name__ == '__main__':
    doc_id = "0d1de0ad-ce02-4daf-9ee6-f281a62f8b64"    
    logger.info("test_document_started", action="__main__", doc_id=doc_id)
    summary = get_summary_upload_document(doc_id)
    logger.info("show_summary_result", action="__main__", summary_len=len(summary) if summary else 0)