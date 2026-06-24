import json
import os
import sys
import asyncio
import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

from core.v03.segments_classifier.utils import is_pham_vi_ap_dung, convert_string_to_bool, ClassifyResponse
from core.common.llms import LLMs
from constants import LLMsConfigExtractClassification

LLMs = LLMs(llms_config=LLMsConfigExtractClassification)
PATH_PROMPT_JSON = os.path.join(PROJECT_ROOT, 'core/v03/segments_classifier/utils/prompts.json')
try:
    if os.path.exists(PATH_PROMPT_JSON):
        with open(PATH_PROMPT_JSON, "r", encoding="utf-8") as file:
            PROMPTS = json.load(file)
except Exception as e:
    logger.error("load_prompts_failed", action="__main__", **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)


# ------------------------------------------------------------------ #
# Sync (giữ nguyên để backward-compatible)                           #
# ------------------------------------------------------------------ #

def classify_segment(segment: str, version: str = 'version_1') -> dict:
    """Phiên bản đồng bộ — giữ nguyên để không breaking change."""
    try:
        classification = ClassifyResponse.copy()

        if not isinstance(segment, str) or not segment.strip():
            logger.error("process_segment_invalid", action="classify_segment",
                         **{"error.code": "VAL", "error.message": "Input must be a non-empty string"})
            raise ValueError("Input must be a non-empty string")

        status_phamvidieuchinh = is_pham_vi_ap_dung(segment)
        classification['Phạm Vi Điều Chỉnh'] = status_phamvidieuchinh

        prompt = PROMPTS[version]['prompt'].format(segment=segment)
        logger.debug("prepare_llm_prompt", action="classify_segment", prompt_length=len(prompt))

        response = LLMs.llms(prompt)
        logger.debug("receive_llm_response", action="classify_segment",
                     response_len=len(response) if response else 0)

        dictionary = LLMs.llms_post_process(response)
        logger.debug("parse_llm_response", action="classify_segment", result=dictionary)
        if dictionary is None:
            raise ValueError("Invalid LLM response format")

        return _build_result(status_phamvidieuchinh, dictionary)

    except ValueError as e:
        logger.error("classify_segment_failed", action="classify_segment",
                     **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
        return classification


# ------------------------------------------------------------------ #
# Async                                                               #
# ------------------------------------------------------------------ #

async def classify_segment_async(
    segment: str,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    version: str = 'version_1',
) -> dict:
    """
    Phiên bản bất đồng bộ của classify_segment.

    Args:
        segment:   Nội dung điều luật cần classify.
        client:    httpx.AsyncClient dùng chung (connection pooling).
        semaphore: asyncio.Semaphore kiểm soát số request đồng thời tới LLM.
        version:   Phiên bản prompt, mặc định 'version_1'.

    Returns:
        dict kết quả classification (cùng schema với classify_segment đồng bộ).
    """
    classification = ClassifyResponse.copy()

    if not isinstance(segment, str) or not segment.strip():
        logger.error("process_segment_invalid", action="classify_segment_async",
                     **{"error.code": "VAL", "error.message": "Input must be a non-empty string"})
        return classification

    try:
        # Bước 1: Rule-based check (không cần LLM, chạy ngay)
        status_phamvidieuchinh = is_pham_vi_ap_dung(segment)

        # Bước 2: Build prompt
        prompt = PROMPTS[version]['prompt'].format(segment=segment)
        logger.debug("prepare_llm_prompt", action="classify_segment_async", prompt_length=len(prompt))

        # Bước 3: Gọi LLM async (giới hạn đồng thời bằng semaphore)
        async with semaphore:
            response = await LLMs.llms_async(prompt, client=client)

        logger.debug("receive_llm_response", action="classify_segment_async",
                     response_len=len(response) if response else 0)

        # Bước 4: Post-process JSON từ LLM
        dictionary = LLMs.llms_post_process(response)
        logger.debug("parse_llm_response", action="classify_segment_async", result=dictionary)

        if dictionary is None:
            raise ValueError("Invalid LLM response format")

        return _build_result(status_phamvidieuchinh, dictionary)

    except ValueError as e:
        logger.error("classify_segment_async_failed", action="classify_segment_async",
                     **{"error.code": "LLM", "error.message": str(e)}, exc_info=True)
        return classification
    except Exception as e:
        logger.error("classify_segment_async_failed", action="classify_segment_async",
                     **{"error.code": "SYS", "error.message": str(e)}, exc_info=True)
        return classification


async def classify_segments_batch(
    segments: list[dict],
    max_concurrent: int = 5,
    version: str = 'version_1',
) -> list[dict]:
    """
    Classify nhiều segments song song.

    Args:
        segments:       List các dict có key 'article_id', 'segment' (text cần classify).
        max_concurrent: Số request LLM đồng thời tối đa.
        version:        Phiên bản prompt.

    Returns:
        List các dict {'article_id': ..., 'classification': ...}.

    Ví dụ đầu vào:
        [
            {'article_id': 'ART_001', 'segment': 'Điều 1. ...'},
            {'article_id': 'ART_002', 'segment': 'Điều 2. ...'},
        ]
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    timeout   = httpx.Timeout(120.0, connect=10.0)
    limits    = httpx.Limits(
        max_keepalive_connections=max_concurrent,
        max_connections=max_concurrent * 2,
    )

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:

        async def _process_one(item: dict) -> dict:
            article_id = item.get("article_id", "unknown")
            segment    = item.get("segment", "")
            result     = await classify_segment_async(
                segment=segment,
                client=client,
                semaphore=semaphore,
                version=version,
            )
            logger.info("classify_segment_batch_item_done",
                        action="classify_segments_batch", article_id=article_id)
            return {"article_id": article_id, "classification": result}

        tasks   = [_process_one(item) for item in segments]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            article_id = segments[i].get("article_id", "unknown")
            logger.error("classify_segment_batch_item_failed",
                         action="classify_segments_batch",
                         article_id=article_id,
                         **{"error.code": "SYS", "error.message": str(res)},
                         exc_info=res)
            output.append({"article_id": article_id, "classification": ClassifyResponse.copy()})
        else:
            output.append(res)

    return output


# ------------------------------------------------------------------ #
# Helper dùng chung                                                   #
# ------------------------------------------------------------------ #

def _build_result(status_phamvidieuchinh: bool, dictionary: dict) -> dict:
    """Map raw LLM dict → schema chuẩn."""
    return {
        'Phạm Vi Điều Chỉnh':             status_phamvidieuchinh,
        'Giải Thích Thuật Ngữ':           convert_string_to_bool(dictionary.get('giai_thich_thuat_ngu', False)),
        'Hiệu Lực và Quy Định Chuyển Tiếp': convert_string_to_bool(dictionary.get('hieu_luc_chuyen_tiep', False)),
        'Ngoại Lệ/Miễn Trừ':             convert_string_to_bool(dictionary.get('ngoai_le_mien_tru', False)),
        'Chế Tài':                        convert_string_to_bool(dictionary.get('che_tai', False)),
        'Nguyên Tắc Cơ Bản':             convert_string_to_bool(dictionary.get('nguyen_tac_co_ban', False)),
        'Quy Định Hành Vi':               convert_string_to_bool(dictionary.get('quy_dinh_hanh_vi', False)),
        'Thẩm Quyền':                     convert_string_to_bool(dictionary.get('tham_quyen', False)),
        'Quyền Lợi và Nghĩa Vụ':         convert_string_to_bool(dictionary.get('quyen_loi_nghia_vu', False)),
        'Thủ Tục/Quy Trình':             convert_string_to_bool(dictionary.get('thu_tuc_quy_trinh', False)),
        'Điều Kiện/Tiêu Chuẩn':         convert_string_to_bool(dictionary.get('dieu_kien_tieu_chuan', False)),
        'Chi Phí/Lệ Phí':               convert_string_to_bool(dictionary.get('chi_phi_le_phi', False)),
    }


# ------------------------------------------------------------------ #
# Smoke test                                                          #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import time

    segments = [
        {
            "article_id": "ART_001",
            "segment": "Điều 13. Vật liệu tháp giếng đứng\n1. Việc lựa chọn vật liệu cho kết cấu tháp giếng phải đáp ứng các yêu cầu sau đây..."
        },
        {
            "article_id": "ART_002",
            "segment": "Điều 8. Tài sản dùng để bảo đảm thực hiện nghĩa vụ\n1. Tài sản hiện có hoặc tài sản hình thành trong tương lai..."
        },
    ]

    start = time.time()
    results = asyncio.run(classify_segments_batch(segments, max_concurrent=3))
    elapsed = round(time.time() - start, 3)

    for r in results:
        logger.debug("show_classification_result", action="__main__",
                     article_id=r["article_id"], result=r["classification"])

    logger.info("batch_completed", action="__main__", total=len(results), elapsed_seconds=elapsed)