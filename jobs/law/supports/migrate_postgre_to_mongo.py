from core.common.mongo.client import get_mongo_client
import pandas as pd
from pymongo import MongoClient
from datetime import datetime
import structlog
import sys
sys.path.append("/home/ubuntu/projects/AI/git/users/haivt/law-document-sync-core-service/law-document-sync-core-service/")
from jobs.law.supports.ultils import list_objects, convert_ngay_hieu_luc, get_or_create_signer_code, format_date, get_storage_code, connect_postgres, get_decree_status, get_doc_content
from core.common.elastic import ElasticIndexer
from constants import MongoDBConfig, MigrateConfig
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()


client = get_mongo_client()

db_raw = client[MigrateConfig.MIGRATE_RAW_DB]
document_segment_collection = db_raw['document_segment']

USER_CREATED = "SYSTEM" 

migrate_document = ElasticIndexer()

def transfer_to_mongodb(df):
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df['ngay_ban_hanh'] = pd.to_datetime(df['ngay_ban_hanh'], errors='coerce')
        minio_documents = list_objects()

        for _, row in df.iterrows():
            if document_segment_collection.find_one({"document_code": row['so_hieu']}):
                logger.info(action="transfer_to_mongodb", event="document_already_exists")
                continue
            signer_codes = get_or_create_signer_code(row['nguoi_ky'], current_time)
            ngay_hieu_luc = convert_ngay_hieu_luc(row['ngay_hieu_luc'], row['ngay_ban_hanh'])
            decree_status, date_expired = get_decree_status(row['tinh_trang'])


            doc = {
                "code": str(row['doc_id']),
                "agency_issued_codes": [], 
                "created_by": USER_CREATED,
                "created_date": current_time,
                "data_source": "SYSTEM",
                "date_expired": format_date(date_expired) if date_expired != "" else "", 
                "decree_effect": format_date(ngay_hieu_luc),
                "decree_issued": format_date(row['ngay_ban_hanh']),
                "decree_status": decree_status,
                "decree_status_code": "", 
                "document_category_code": "", 
                "document_code": row['so_hieu'] if pd.notna(row['so_hieu']) else "",
                "embedding_status": "PENDING",
                "industry_sector_codes": [], 
                "issued_level_code": "", 
                "last_modified": current_time,
                "last_modified_by": "",
                "name": row['tieu_de'] if pd.notna(row['tieu_de']) else "",
                "properties": [
                    {"key": "Số hiệu văn bản", "value": row['so_hieu'] if pd.notna(row['so_hieu']) else ""},
                    {"key": "Loại văn bản", "value": row['loai_van_ban'] if pd.notna(row['loai_van_ban']) else ""},
                    {"key": "Ký hiệu đơn vị", "value": ""},
                    {"key": "Ký hiệu văn bản", "value": row['so_hieu'].split('/')[-1].split('-')[0] if pd.notna(row['so_hieu']) and '/' in row['so_hieu'] else ""},
                    {"key": "Tên văn bản", "value": row['tieu_de'] if pd.notna(row['tieu_de']) else ""},
                    {"key": "Cấp ban hành", "value": "Địa phương" if pd.notna(row['so_hieu']) and ( "ubnd" in row['so_hieu'].lower() or "hdnd" in row['so_hieu'].lower() or "hđnd" in row['so_hieu'].lower() ) else "Trung ương"},
                    {"key": "Cơ quan ban hành", "value": row['noi_ban_hanh'] if pd.notna(row['noi_ban_hanh']) else ""},
                    {"key": "Người ký ban hành", "value": row['nguoi_ky'] if pd.notna(row['nguoi_ky']) else ""},
                    {"key": "Lĩnh vực/Ngành", "value": row['linh_vuc_nganh'] if pd.notna(row['linh_vuc_nganh']) else ""},
                    {"key": "Tình trạng hiệu lực", "value": row['tinh_trang'] if pd.notna(row['tinh_trang']) else "Còn hiệu lực"},
                    {"key": "Ngày ban hành", "value": format_date(row['ngay_ban_hanh'])},
                    {"key": "Số công báo", "value": ""},
                    {"key": "Ngày hết hiệu lực", "value": format_date(date_expired) if date_expired != "" else ""},
                    {"key": "Ngày có hiệu lực", "value": format_date(ngay_hieu_luc)},
                    {"key": "Địa danh ban hành", "value": ""},
                    {"key": "Ngày công bố", "value": ""},
                    {"key": "Ngày thông qua", "value": ""},
                    {"key": "Ngày đăng công báo", "value": ""},
                    {"key": "Lý do hết hiệu lực", "value": ""}
                ],
                "signer_codes": signer_codes,
                "amend_documents": row['vb_sdbs'] if row['vb_sdbs'] is not None and len(row['vb_sdbs']) > 0 else [],
                "amended_documents": row['vb_bi_sdbs'] if row['vb_bi_sdbs'] is not None and len(row['vb_bi_sdbs']) > 0 else [],
                "basis_documents": row['vb_duoc_can_cu'] if row['vb_duoc_can_cu'] is not None and len(row['vb_duoc_can_cu']) > 0 else [],
                "consolidated_documents": row['vb_duoc_hop_nhat'] if row['vb_duoc_hop_nhat'] is not None and len(row['vb_duoc_hop_nhat']) > 0 else [],
                "consolidating_documents": row['vd_hop_nhat'] if row['vd_hop_nhat'] is not None and len(row['vd_hop_nhat']) > 0 else [],
                "content_connection_documents": row['vb_lien_quan_cung_noi_dung'] if row['vb_lien_quan_cung_noi_dung'] is not None and len(row['vb_lien_quan_cung_noi_dung']) > 0 else [],
                "correct_documents": row['vb_dinh_chinh_boi'] if row['vb_dinh_chinh_boi'] is not None and len(row['vb_dinh_chinh_boi']) > 0 else [],
                "corrected_documents": row['vb_bi_dinh_chinh'] if row['vb_bi_dinh_chinh'] is not None and len(row['vb_bi_dinh_chinh']) > 0 else [],
                "referential_documents": row['vb_duoc_dan_chieu'] if row['vb_duoc_dan_chieu'] is not None and len(row['vb_duoc_dan_chieu']) > 0 else [],
                "replace_documents": row['vb_thay_the_boi'] if row['vb_thay_the_boi'] is not None and len(row['vb_thay_the_boi']) > 0 else [],
                "replaced_documents": row['vb_bi_thay_the'] if row['vb_bi_thay_the'] is not None and len(row['vb_bi_thay_the']) > 0 else [],
                "guided_documents": row['vb_duoc_huong_dan'] if row['vb_duoc_huong_dan'] is not None and len(row['vb_duoc_huong_dan']) > 0 else [],
                "guide_documents": row['vb_huong_dan'] if row['vb_huong_dan'] is not None and len(row['vb_huong_dan']) > 0 else [],
                "storage_code": get_storage_code(str(row['doc_id']), minio_documents)
            }

            document_segment_collection.insert_one(doc)
            logger.info(action="transfer_to_mongodb", event="document_transferred", doc_id=row['doc_id'])
            
            doc_content = get_doc_content(doc['storage_code'])
            doc['description'] = doc_content
            migrate_document.insert_document_to_eslastic(doc)



    except Exception as error:
        logger.error(action="transfer_to_mongodb", event="transfer_to_mongodb_failed", **{"error.code": "DB", "error.message": str(error)}, exc_info=True)

if __name__ == "__main__":
    df = connect_postgres()
    
    if df is not None:
        transfer_to_mongodb(df)