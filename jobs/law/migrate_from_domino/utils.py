from core.common.mongo.client import get_mongo_client
import structlog
import sys
import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from pymongo import MongoClient
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(PROJECT_ROOT)
from constants import MongoDBConfig, MigrateConfig, MongoDBCollectionConfig
from core.common.elastic import ElasticIndexer
from core.common.minio import MinIOClient
from logs.logger_conf import setup_logging

setup_logging()
logger = structlog.get_logger()

USER_CREATED = "system"
CURRENT_TIME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
BASE_URL = "http://10.0.0.180"  
URL_COLLECTION = 'http://10.0.0.180/BCA/VBPQ_KT.nsf/api/data/collections'
URL_VIEW_ALL = 'http://10.0.0.180/BCA/VBPQ_KT.nsf/api/data/collections/unid/'
URL_DOCUMENT = 'http://10.0.0.180/BCA/VBPQ_KT.nsf/api/data/documents/unid/'
SAVE_FOLDER = os.path.join(PROJECT_ROOT, 'jobs/law/migrate_from_domino/Tai_lieu_VBPQ')


mongo_client = get_mongo_client()

db = mongo_client[MigrateConfig.MIGRATE_RAW_DB]
document_segment_colection = db[MongoDBCollectionConfig.RAW_DOCUMENTS_SEGMENTS_COLLECTION_NAME]
resources_col = db[MongoDBCollectionConfig.RAW_RESOURCE_COLLECTION_NAME]

minio_client = MinIOClient()
elastic_client = ElasticIndexer()


def format_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def get_view_all_unid() -> str | None:
    res = requests.get(URL_COLLECTION)
    if res.status_code != 200:
        return None

    for item in res.json():
        if item.get("@title", "").lower() == "văn bản all":
            return item.get("@unid")
    return None


def get_all_document_unids(view_unid: str, batch_size: int = 100) -> list[str]:
    start = 1
    results = []

    while True:
        res = requests.get(
            URL_VIEW_ALL + view_unid,
            params={"start": start, "count": batch_size}
        )
        if res.status_code != 200:
            break
        data = res.json()
        if not data:
            break
        results.extend(d["@unid"] for d in data if "@unid" in d)
        if len(data) < batch_size:
            break
        start += batch_size
    return results


def download_and_upload(url: str) -> str | None:
    os.makedirs(SAVE_FOLDER, exist_ok=True)
    filename = url.split("/")[-1]
    filepath = os.path.join(SAVE_FOLDER, filename)

    try:
        res = requests.get(url, stream=True, timeout=30)
        res.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in res.iter_content(8192):
                f.write(chunk)

        minio_client.upload_file(file=filepath)
        os.remove(filepath)
        return filename

    except Exception as e:
        logger.error(action="download_and_upload", event="download_upload_failed", **{"error.code": "EXT", "error.message": str(e)}, url=url, exc_info=True)
        return None


def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()


def normalize_date(text):
    if not text:
        return None
    text = text.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
        except:
            pass
    try:  
        return datetime.strptime(text, "%m/%d/%y").strftime("%d/%m/%Y")
    except:
        return None


def extract_domino_metadata(unid):
    DOC_URL = f"{BASE_URL}/bca/VBPQ_KT.nsf/0/{unid}?OpenDocument"    
    session = requests.Session()
    resp = session.get(DOC_URL, timeout=30)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    data = {
        "so_ky_hieu": None,
        "ten_van_ban": None,
        "hinh_thuc_van_ban": None,
        "co_quan_ban_hanh": None,
        "nguoi_ky": None,
        "ngay_ban_hanh": None,
        "ngay_cong_bo": None,
        "ngay_co_hieu_luc": None,
        "ngay_het_hieu_luc": None,
        "ly_do_het_hieu_luc": None,
        "chuyen_de": None,
        "tu_khoa": None,
        "file_dinh_kem": [],
        "tinh_trang_hieu_luc": None,        
        "van_ban_bi_thay_the_toan_phan": [],
        "van_ban_bi_thay_the_mot_phan": []
    }
    
    rows = soup.find_all("tr")
    for row in rows:
        tds = row.find_all("td")
        if len(tds) < 2:
            continue
        label = clean_text(tds[0].get_text())
        if "Số/Ký hiệu" in label:
            data["so_ky_hieu"] = clean_text(tds[-1].get_text()).split(" ")[0]
        elif "Tên văn bản" in label:
            data["ten_van_ban"] = clean_text(tds[-1].get_text())
        elif "Hình thức văn bản" in label:
            data["hinh_thuc_van_ban"] = clean_text(tds[-1].get_text())
        elif "Cơ quan ban hành" in label:
            data["co_quan_ban_hanh"] = clean_text(tds[-1].get_text())
        elif "Người ký" in label:
            data["nguoi_ky"] = clean_text(tds[-1].get_text())
        elif "Ngày ban hành" in label and len(tds) >= 4:
            data["ngay_ban_hanh"] = normalize_date(clean_text(tds[1].get_text()))
            data["ngay_cong_bo"] = normalize_date(clean_text(tds[3].get_text()))
        elif "Ngày có hiệu lực" in label:
            data["ngay_co_hieu_luc"] = normalize_date(clean_text(tds[1].get_text()))
        elif "Ngày hết hiệu lực" in label:
            data["ngay_het_hieu_luc"] = normalize_date(clean_text(tds[1].get_text()))
        elif "Lý do hết hiệu lực" in label:
            data["ly_do_het_hieu_luc"] = clean_text(tds[-1].get_text())
        elif "Chuyên đề" in label:
            data["chuyen_de"] = clean_text(tds[-1].get_text())
        elif "Từ khóa" in label:
            data["tu_khoa"] = clean_text(tds[-1].get_text())
        elif "Văn bản bị thay thế" in label:
            try:
                listvb = json.loads(tds[1].get_text())["listvb"]            
            except Exception as e:
                listvb = []
                logger.error(action="extract_domino_metadata", event="metadata_parsing_failed", **{"error.code": "PARSE", "error.message": str(e)}, exc_info=True)
            logger.info(action="extract_domino_metadata", event="list_vb_extracted", listvb=listvb)
            listvb_btt_all = []
            listvb_btt_part = []
            for vb in listvb:
                id = vb.get("id", "")
                kieu = vb.get("kieu", "")                
                if id == "":
                    continue
                if kieu == "ALL":
                    listvb_btt_all.append(id)
                else:
                    listvb_btt_part.append(id)
            data["van_ban_bi_thay_the_toan_phan"]= listvb_btt_all
            data["van_ban_bi_thay_the_mot_phan"]= listvb_btt_part

    for a in soup.select('a[href*="/$FILE/"]'):
        href = a.get("href")
        name = a.get_text(strip=True)
        if name.lower().endswith(".doc") or name.lower().endswith(".docx"):
            data['file_dinh_kem'].append({
                "filename": name,
                "download_url": urljoin(BASE_URL, href)
            })
    return data


def map_to_target_schema(data):
    # Lấy thời gian hiện tại cho các trường hệ thống
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Hàm hỗ trợ chuyển đổi định dạng ngày từ DD/MM/YYYY sang YYYY-MM-DD HH:MM:SS
    def format_date(date_str):
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d 00:00:00")
        except:
            return date_str

    # Trích xuất Ký hiệu văn bản (Ví dụ: từ 101/2025/TT-BCA lấy TT)    
    mapped_record = {
        "code": "", 
        "amend_documents": [],
        "amended_documents": data.get("van_ban_bi_thay_the_mot_phan", []),
        "basis_documents": [],
        "consolidated_documents": [],
        "consolidating_documents": [],
        "content_connection_documents": [],
        "correct_documents": [],
        "corrected_documents": [],
        "created_by": "",
        "created_date": now,
        "data_source": "V03",
        "date_expired": format_date(data.get("ngay_het_hieu_luc")),
        "decree_effect": format_date(data.get("ngay_co_hieu_luc")),
        "decree_issued": format_date(data.get("ngay_ban_hanh")),
        "decree_status": data.get("tinh_trang_hieu_luc") or "Còn hiệu lực",
        "document_code": data.get("so_ky_hieu"),
        "language_connection_documents": [],
        "name": data.get("ten_van_ban"),
        "properties": [
            {"key": "Số hiệu văn bản", "value": data.get("so_ky_hieu") or ""},
            {"key": "Loại văn bản", "value": data.get("hinh_thuc_van_ban") or ""},
            {"key": "Ký hiệu đơn vị", "value": ""},
            {"key": "Ký hiệu văn bản", "value": data.get("so_ky_hieu")},
            {"key": "Tên văn bản", "value": data.get("ten_van_ban") or ""},
            {"key": "Cấp ban hành", "value": ""}, 
            {"key": "Cơ quan ban hành", "value": data.get("co_quan_ban_hanh") or ""},
            {"key": "Người ký ban hành", "value": data.get("nguoi_ky") or ""},
            {"key": "Lĩnh vực/Ngành", "value": data.get("chuyen_de") or ""},
            {"key": "Tình trạng hiệu lực", "value": data.get("tinh_trang_hieu_luc") or "Còn hiệu lực"},
            {"key": "Ngày ban hành", "value": data.get("ngay_ban_hanh") or ""},
            {"key": "Số công báo", "value": ""},
            {"key": "Ngày hết hiệu lực", "value": data.get("ngay_het_hieu_luc") or ""},
            {"key": "Ngày có hiệu lực", "value": data.get("ngay_co_hieu_luc") or ""},
            {"key": "Địa danh ban hành", "value": ""},
            {"key": "Ngày công bố", "value": data.get("ngay_cong_bo") or ""},
            {"key": "Ngày thông qua", "value": ""},
            {"key": "Ngày đăng công báo", "value": ""},
            {"key": "Lý do hết hiệu lực", "value": data.get("ly_do_het_hieu_luc") or ""}
        ],
        "referential_documents": [],
        "replace_documents": [],
        "replaced_documents": data.get("van_ban_bi_thay_the_toan_phan", []),
        "status": "ACTIVE",
        "storage_code": ""
    }
    return mapped_record