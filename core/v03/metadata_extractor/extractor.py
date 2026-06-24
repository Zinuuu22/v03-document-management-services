import sys
import os
import asyncio
import httpx
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

sys.path.append(PROJECT_ROOT)

import structlog
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()
from core.v03.metadata_extractor.fields.extract_agency import extract_agency, extract_agency_async
from core.v03.metadata_extractor.fields.extract_document_category import extract_document_category
from core.v03.metadata_extractor.fields.extract_document_code import extract_document_code
from core.v03.metadata_extractor.fields.extract_document_level import extract_document_level
from core.v03.metadata_extractor.fields.extract_document_name import extract_document_name, extract_document_name_async
from core.v03.metadata_extractor.fields.extract_document_type import extract_document_type
from core.v03.metadata_extractor.fields.extract_issue_date import extract_issue_date
from core.v03.metadata_extractor.fields.extract_human_sign import extract_human_sign, extract_human_sign_async
from core.v03.metadata_extractor.fields.extract_effective_date import extract_effective_date, extract_effective_date_async
from core.v03.metadata_extractor.fields.extract_end_effective_date import extract_end_effective_date
from core.v03.metadata_extractor.fields.extract_effective_status import extract_effective_status


METADATA_NAMES = ['document_name', 
                'document_code', 
                'document_type', 
                'agency', 
                'human_sign', 
                'effective_date', 
                'issue_date', 
                'end_effective_date', 
                'effective_status', 
                'document_category', 
                'document_level']


def extract_metadata(content, metadata_names=METADATA_NAMES):
    
    metadata = {}
    for name in metadata_names:
        metadata[name] = None

    try:
        document_code = None
        document_code = extract_document_code(content)
        metadata['document_code'] = document_code
    except Exception as e:
        logger.error("extract_document_code_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

    try:
        document_type = None
        if 'document_type' in metadata_names and document_code is not None:
            document_type = extract_document_type(content=content, document_code=document_code)
            metadata['document_type'] = document_type
    except Exception as e:
        logger.error("extract_document_type_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

    try:
        if 'document_name' in metadata_names and metadata['document_type'] is not None:
            document_name = extract_document_name(content=content, document_code=document_code ,document_type=document_type)
            metadata['document_name'] = document_name
    except Exception as e:
        logger.error("extract_document_name_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

    try:
        if 'agency' in metadata_names and metadata['document_code'] is not None:
            agency = extract_agency(content=content, document_code=document_code)
            metadata['agency'] = agency
    except Exception as e:
        logger.error("extract_agency_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

    try:
        if 'human_sign' in metadata_names:
            human_signs = extract_human_sign(content=content)
            metadata['human_sign'] = human_signs
    except Exception as e:
        logger.error("extract_human_sign_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

    try:
        issue_date = None
        if 'issue_date' in metadata_names:
            issue_date = extract_issue_date(content=content)
            metadata['issue_date'] = issue_date['issue_date']
    except Exception as e:
        logger.error("extract_issue_date_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

    try:
        if 'effective_date' in metadata_names and metadata['issue_date'] is not None:
            effective_date = extract_effective_date(content=content, issue_date=metadata['issue_date'])
            metadata['effective_date'] = effective_date['effective_date']
    except Exception as e:
        logger.error("extract_effective_date_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

    try:
        if 'end_effective_date' in metadata_names and metadata['issue_date'] is not None:
            end_effective_date = extract_end_effective_date(content=content, issue_date=metadata['issue_date'])
            metadata['end_effective_date'] = end_effective_date['end_effective_date']
    except Exception as e:
        logger.error("extract_end_effective_date_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

    try:
        if 'effective_status' in metadata_names and metadata['issue_date'] is not None:
            effective_status = extract_effective_status(content=content, issue_date=metadata['issue_date'])
            metadata['effective_status'] = effective_status['effective_status']
    except Exception as e:
        logger.error("extract_effective_status_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

    try:
        if 'document_level' in metadata_names and metadata['document_code'] is not None:
            document_level = extract_document_level(document_code=document_code)
            metadata['document_level'] = document_level['document_level']
    except Exception as e:
        logger.error("extract_document_level_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

    try:
        if 'document_category' in metadata_names and metadata['document_code'] is not None and metadata['document_type'] is not None:
            document_category = extract_document_category(document_code=document_code, document_type=document_type)
            metadata['document_category'] = document_category['document_category']
    except Exception as e:
        logger.error("extract_document_category_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)  

    return metadata


async def extract_metadata_async(content, metadata_names=METADATA_NAMES, batch_size: int = 10):
    custom_timeout = httpx.Timeout(600.0, connect=10.0)
    semaphore = asyncio.Semaphore(batch_size)
    limits = httpx.Limits(max_keepalive_connections=batch_size, max_connections=batch_size * 2)
    async with httpx.AsyncClient(limits=limits, timeout=custom_timeout) as client:
        metadata = {}
        for name in metadata_names:
            metadata[name] = None

        try:
            document_code = None
            document_code = extract_document_code(content)
            metadata['document_code'] = document_code
        except Exception as e:
            logger.error("extract_document_code_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

        try:
            document_type = None
            if 'document_type' in metadata_names and document_code is not None:
                document_type = extract_document_type(content=content, document_code=document_code)
                metadata['document_type'] = document_type
        except Exception as e:
            logger.error("extract_document_type_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

        try:
            issue_date = None
            if 'issue_date' in metadata_names:
                issue_date = extract_issue_date(content=content)
                metadata['issue_date'] = issue_date['issue_date']
        except Exception as e:
            logger.error("extract_issue_date_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

        try:
            if 'end_effective_date' in metadata_names and metadata['issue_date'] is not None:
                end_effective_date = extract_end_effective_date(content=content, issue_date=metadata['issue_date'])
                metadata['end_effective_date'] = end_effective_date['end_effective_date']
        except Exception as e:
            logger.error("extract_end_effective_date_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

        try:
            if 'effective_status' in metadata_names and metadata['issue_date'] is not None:
                effective_status = extract_effective_status(content=content, issue_date=metadata['issue_date'])
                metadata['effective_status'] = effective_status['effective_status']
        except Exception as e:
            logger.error("extract_effective_status_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

        try:
            if 'document_level' in metadata_names and metadata['document_code'] is not None:
                document_level = extract_document_level(document_code=document_code)
                metadata['document_level'] = document_level['document_level']
        except Exception as e:
            logger.error("extract_document_level_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)

        try:
            if 'document_category' in metadata_names and metadata['document_code'] is not None and metadata['document_type'] is not None:
                document_category = extract_document_category(document_code=document_code, document_type=document_type)
                metadata['document_category'] = document_category['document_category']
        except Exception as e:
            logger.error("extract_document_category_failed", action="extract_metadata", **{"error.code": "EXT", "error.message": str(e)}, exc_info=True)  

        tasks = {}
        if 'document_name' in metadata_names and metadata['document_type'] is not None:
            tasks['document_name'] = asyncio.create_task(
                extract_document_name_async(content=content, document_code=document_code, document_type=document_type, client=client, semaphore=semaphore)
            )

        if 'agency' in metadata_names and metadata['document_code'] is not None:
            tasks['agency'] = asyncio.create_task(
                extract_agency_async(content=content, document_code=document_code, client=client, semaphore=semaphore)
            )

        if 'human_sign' in metadata_names:
            tasks['human_sign'] = asyncio.create_task(
                extract_human_sign_async(content=content, client=client, semaphore=semaphore)
            )

        if 'effective_date' in metadata_names and metadata['issue_date'] is not None:
            tasks['effective_date'] = asyncio.create_task(
                extract_effective_date_async(content=content, issue_date=metadata['issue_date'], client=client, semaphore=semaphore)
            )

        # --- Chạy song song, return_exceptions để không abort khi 1 task lỗi ---
        keys = list(tasks.keys())
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        # --- Xử lý kết quả ---
        for key, result in zip(keys, results):
            if isinstance(result, Exception):
                logger.error("extract_failed", action="extract_metadata",
                    **{"error.code": "EXT", "error.message": str(result), "field": key},
                    exc_info=result,
                )
            else:
                if key == 'effective_date':
                    metadata[key] = result['effective_date']
                else:
                    metadata[key] = result

    return metadata


if __name__ == '__main__':    
    content = """
    BỘ CÔNG THƯƠNG
-------
Số: 33/2018/TT-BCT | CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc 
---------------
Hà Nội, ngày 08 tháng 10 năm 2018

THÔNG TƯ

QUY ĐỊNH VỀ THẺ KIỂM TRA THỊ TRƯỜNG

Căn cứ Pháp lệnh Quản lý thị trường ngày 08 tháng 3 năm 2016;

Căn cứ Nghị định số 98/2017/NĐ-CP ngày 18 tháng 8 năm 2017 của Chính phủ về chức năng, nhiệm vụ, quyền hạn và cơ cấu tổ chức của Bộ Công Thương;

Căn cứ Quyết định số 34/2018/QĐ-TTg ngày 10 tháng 8 năm 2018 của Thủ tướng Chính phủ quy định chức năng, nhiệm vụ, quyền hạn và cơ cấu tổ chức của Tổng cục Quản lý thị trường trực thuộc Bộ Công Thương;

Theo đề nghị của Cục trưởng Cục Quản lý thị trường;

Bộ trưởng Bộ Công Thương ban hành Thông tư quy định về Thẻ kiểm tra thị trường.

Chương I
    """
    document_code = extract_document_code(content)
    document_type = extract_document_type(content=content, document_code=document_code)
    document_name = extract_document_name(content=content, document_type=document_type, document_code=document_code)
    logger.debug('document_name_extracted', action="main", document_name=document_name)