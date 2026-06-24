import os
import sys
import fasttext
import time
import random

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.v03.tree_classifier.utils import (
    get_classes,
    load_data_summary,
    prepare_fasttext_datasets,
    train_fasttext_model,
)

CONFIG = {
    "lr": 0.1,
    "epoch": 10,
    "dim": 512,
    "wordngrams": 3
}


def prepare_data(tree_id, train_id, test_ratio=0.2):
    """Full pipeline: load -> split -> train -> evaluate"""
    logger.info("prepare_model_training_started", action="prepare_data", tree_id=tree_id)
    
    start_time = time.time()
    classes = get_classes(tree_id)    
    start_time = time.time()
    final_data = []
    for _class in classes:
        class_name = _class.get("class_name")
        doc_ids = _class.get("doc_ids")
        logger.debug("process_class_started", action="prepare_data", class_name=class_name, doc_count=len(doc_ids))
        try:
            data = load_data_summary(class_name, doc_ids)
            final_data.extend(data)
        except Exception as e:
            logger.error("load_data_failed", action="prepare_data", **{"error.code": "DB", "error.message": str(e)}, class_name=class_name, exc_info=True)
    logger.info("collect_data_samples_successful", action="prepare_data", total_samples=len(final_data))

    # Shuffle data
    random.shuffle(final_data)

    output_dir = os.path.join(PROJECT_ROOT, "core/v03/tree_classifier/datasets", train_id)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    train_path, test_path = prepare_fasttext_datasets(final_data, output_dir, test_ratio)
    end_time = time.time()
    total_time = end_time - start_time
    logger.info("prepare_dataset_completed", action="prepare_data", elapsed_seconds=round(total_time, 2))   
    logger.info("configure_dataset_paths_successful", action="prepare_data", train_path=train_path, test_path=test_path)
    return train_path, test_path, total_time, output_dir


def train(tree_id, train_id, train_path, test_path, output_dir, config=CONFIG):
    """Full pipeline: load -> split -> train -> evaluate"""
    logger.info("train_model_started", action="train", tree_id=tree_id)
    
    start_time = time.time()
    model_path, metrics = train_fasttext_model(
        train_file=train_path,
        test_file=test_path,
        output_dir=output_dir,
        lr=config.get("lr", 0.1),
        epoch=config.get("epoch", 1000),
        dim=config.get("dim", 512),
        wordNgrams=config.get("wordngrams", 3)
    )
    end_time = time.time()
    logger.info("train_model_completed", action="train", elapsed_seconds=round(end_time - start_time, 2))   
    logger.info("save_model_successful", action="train", model_path=model_path)
    return model_path, metrics


# =========================
# 6️⃣ INFERENCE
# =========================
def predict(model_path, input):
    model = fasttext.load_model(model_path)        
    input = input.strip().replace('\n', ' ').replace('\t', ' ')    
    label, prob = model.predict(input)
    return label[0].replace("__label__", ""), prob[0]


if __name__ == "__main__":
    tree_id = input("Nhập tree_id cần huấn luyện: ").strip()
    train_id = "version 1"
    train(tree_id, train_id)
