"""
test_steps.py — Chay va kiem tra tung buoc migration Domino -> MongoDB.

Cach dung:
    python test_steps.py --step 1   # kiem tra ket noi
    python test_steps.py --step 2   # lay danh sach View
    python test_steps.py --step 3   # phan trang lay UNID
    python test_steps.py --step 4 --unid <UNID>   # scrape metadata
    python test_steps.py --step 5 --unid <UNID>   # upsert MongoDB
    python test_steps.py            # chay tat ca
"""
import argparse
import sys
import json
import os
import re
from pprint import pprint
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin


# ══════════════════════════════════════════════════════════════════════════════
# Load .env
# ══════════════════════════════════════════════════════════════════════════════

def _load_env() -> None:
    for parent in [Path.cwd(), *Path.cwd().parents]:
        env_file = parent / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())
            print(f"  .   Doc config tu: {env_file}")
            return
    print("  !   Khong tim thay .env")

_load_env()


# ══════════════════════════════════════════════════════════════════════════════
# Config — chi doc Domino URL va MongoDB, khong can auth
# ══════════════════════════════════════════════════════════════════════════════

DOMINO_BASE_URL   = os.getenv("DOMINO_BASE_URL",    "http://10.0.0.5")
NSF_PATH          = os.getenv("DOMINO_NSF_PATH",    "BCA/VBPQ_KT.nsf")
TARGET_VIEW_TITLE = os.getenv("DOMINO_TARGET_VIEW", "van ban all")
BATCH_SIZE        = int(os.getenv("DOMINO_BATCH_SIZE", "5"))

MONGO_HOST       = os.getenv("MONGO_HOST",       "localhost")
MONGO_PORT       = int(os.getenv("MONGO_PORT",   "27017"))
MONGO_USERNAME   = os.getenv("MONGO_USERNAME",   "")
MONGO_PASSWORD   = os.getenv("MONGO_PASSWORD",   "")
MONGO_DB         = os.getenv("MONGO_DB",         "law_db")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "documents")

SAMPLE_UNID   = ""
DOWNLOAD_DIR  = os.getenv("DOWNLOAD_DIR", "downloads")


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")

def _ok(msg: str)   -> None: print(f"  [OK]  {msg}")
def _warn(msg: str) -> None: print(f"  [!!]  {msg}")
def _err(msg: str)  -> None: print(f"  [XX]  {msg}")
def _info(msg: str) -> None: print(f"  [ ]   {msg}")

def _abort(msg: str) -> None:
    _err(msg)
    sys.exit(1)

def _get(url: str, **kwargs):
    """Anonymous GET — khong can auth."""
    import requests
    kwargs.setdefault("timeout", 30)
    return requests.get(url, **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# Buoc 1 — Kiem tra thu vien & ket noi
# ══════════════════════════════════════════════════════════════════════════════

def step1_check() -> None:
    _header("Buoc 1 — Kiem tra thu vien & ket noi")

    # Thu vien
    for pkg in ["requests", "bs4", "pymongo"]:
        try:
            __import__(pkg)
            _ok(f"import {pkg}")
        except ImportError:
            _abort(f"Thieu '{pkg}'. Chay: pip install {pkg}")

    # Ping Domino
    url = f"{DOMINO_BASE_URL}/{NSF_PATH}/api/data/collections"
    _info(f"Ping: {url}")
    try:
        resp = _get(url)
        if resp.status_code == 200:
            _ok(f"Ket noi Domino OK — HTTP 200")
        elif resp.status_code == 403:
            _warn("HTTP 403 — Server yeu cau xac thuc hoac chua bat Domino Data Service")
            _info("Hoi admin bat: Server Document -> Internet Protocols -> Domino Access Services -> Data")
        elif resp.status_code == 404:
            _warn(f"HTTP 404 — Sai NSF path: {NSF_PATH}")
            _info("Kiem tra lai DOMINO_NSF_PATH trong .env")
        else:
            _warn(f"HTTP {resp.status_code} — {resp.text[:100]}")
        resp.raise_for_status()
    except Exception as e:
        _abort(f"Loi ket noi Domino: {e}")

    # Ping MongoDB
    try:
        from pymongo import MongoClient
        c = MongoClient(
            host=MONGO_HOST, port=MONGO_PORT,
            username=MONGO_USERNAME or None,
            password=MONGO_PASSWORD or None,
            serverSelectionTimeoutMS=3000,
        )
        c.server_info()
        _ok(f"Ket noi MongoDB OK — {MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}")
        c.close()
    except Exception as e:
        _warn(f"Khong ket noi duoc MongoDB: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Buoc 2 — Lay danh sach Collections
# ══════════════════════════════════════════════════════════════════════════════

def step2_get_collections() -> str:
    _header("Buoc 2 — Lay danh sach Collections")

    url  = f"{DOMINO_BASE_URL}/{NSF_PATH}/api/data/collections"
    resp = _get(url)
    resp.raise_for_status()
    cols = resp.json()

    _ok(f"Tong collections: {len(cols)}")
    print()
    print(f"  {'TITLE':40s}  {'UNID':14s}  DOCS")
    print(f"  {'-'*40}  {'-'*14}  ----")

    view_unid = None
    for c in cols:
        title  = c.get("@title", "")
        unid   = c.get("@unid",  "")
        count  = c.get("@count",  0)
        is_hit = title.strip().lower() == TARGET_VIEW_TITLE.strip().lower()
        marker = "  <-- TARGET" if is_hit else ""
        print(f"  {title:40s}  {unid[:14]}  {count:>6}{marker}")
        if is_hit:
            view_unid = unid

    print()
    if view_unid:
        _ok(f"Tim thay View: '{TARGET_VIEW_TITLE}'")
        _info(f"View UNID = {view_unid}")
    else:
        _abort(f"Khong tim thay View '{TARGET_VIEW_TITLE}'. Kiem tra DOMINO_TARGET_VIEW trong .env")

    return view_unid


# ══════════════════════════════════════════════════════════════════════════════
# Buoc 3 — Phan trang lay UNID
# ══════════════════════════════════════════════════════════════════════════════

def step3_get_unids(view_unid: str) -> list[str]:
    _header("Buoc 3 — Phan trang lay UNID")

    url     = f"{DOMINO_BASE_URL}/{NSF_PATH}/api/data/collections/unid/{view_unid}"
    results = []
    start   = 1
    page    = 0

    while True:
        page += 1
        resp  = _get(url, params={"start": start, "count": BATCH_SIZE})
        resp.raise_for_status()
        batch = resp.json()

        if not batch:
            break

        new = [d["@unid"] for d in batch if "@unid" in d]
        results.extend(new)
        _info(f"Trang {page:3d}: +{len(new):3d} UNIDs  (tong: {len(results)})")

        if len(batch) < BATCH_SIZE:
            break
        start += BATCH_SIZE

    print()
    if results:
        _ok(f"Tong UNID: {len(results)}")
        _info("3 UNID dau (copy de dung --unid):")
        for u in results[:3]:
            print(f"        {u}")
    else:
        _warn("Khong co UNID nao trong View nay")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# Buoc 4 — Scrape HTML & extract metadata
# ══════════════════════════════════════════════════════════════════════════════

def step4_extract(unid: str) -> dict:
    _header(f"Buoc 4 — Extract metadata  [{unid}]")

    from bs4 import BeautifulSoup

    def clean(text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        # Bo so thu tu / ky tu thua cuoi chuoi (VD: "Luat5", "Quoc hoi19")
        text = re.sub(r"\d+$", "", text).strip()
        return text

    def norm_date(text) -> str | None:
        if not text:
            return None
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%m/%d/%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
        return None

    url  = f"{DOMINO_BASE_URL}/bca/VBPQ_KT.nsf/0/{unid}?OpenDocument"
    _info(f"URL: {url}")
    resp = _get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    raw: dict = {
        "so_ky_hieu": None, "ten_van_ban": None, "hinh_thuc_van_ban": None,
        "co_quan_ban_hanh": None, "nguoi_ky": None, "cap_ban_hanh": None,
        "ngay_ban_hanh": None, "ngay_cong_bo": None,
        "ngay_co_hieu_luc": None, "ngay_het_hieu_luc": None,
        "ly_do_het_hieu_luc": None, "chuyen_de": None, "tu_khoa": None,
        "tinh_trang_hieu_luc": None,
        "file_dinh_kem": [],
        "van_ban_bi_thay_the_toan_phan": [],
        "van_ban_bi_thay_the_mot_phan" : [],
    }

    for row in soup.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) < 2:
            continue
        label = clean(tds[0].get_text())
        if   "Số/Ký hiệu"           in label: raw["so_ky_hieu"]           = clean(tds[-1].get_text()).split()[0]
        elif "Tên văn bản"           in label: raw["ten_van_ban"]          = clean(tds[-1].get_text())
        elif "Hình thức văn bản"     in label: raw["hinh_thuc_van_ban"]    = clean(tds[-1].get_text())
        elif "Cơ quan ban hành"      in label: raw["co_quan_ban_hanh"]     = clean(tds[-1].get_text())
        elif "Người ký"              in label: raw["nguoi_ky"]             = clean(tds[-1].get_text())
        elif "Cấp ban hành"          in label: raw["cap_ban_hanh"]         = clean(tds[-1].get_text())
        elif "Tình trạng hiệu lực"   in label: raw["tinh_trang_hieu_luc"] = clean(tds[-1].get_text())
        elif "Lý do hết hiệu lực"    in label: raw["ly_do_het_hieu_luc"]  = clean(tds[-1].get_text())
        elif "Chuyên đề"             in label: raw["chuyen_de"]            = clean(tds[-1].get_text())
        elif "Từ khóa"               in label: raw["tu_khoa"]              = clean(tds[-1].get_text())
        elif "Ngày ban hành" in label and len(tds) >= 4:
            raw["ngay_ban_hanh"] = norm_date(clean(tds[1].get_text()))
            raw["ngay_cong_bo"]  = norm_date(clean(tds[3].get_text()))
        elif "Ngày có hiệu lực"      in label: raw["ngay_co_hieu_luc"]    = norm_date(clean(tds[1].get_text()))
        elif "Ngày hết hiệu lực"     in label: raw["ngay_het_hieu_luc"]   = norm_date(clean(tds[1].get_text()))
        elif "Văn bản bị thay thế"   in label:
            try:
                listvb = json.loads(tds[1].get_text()).get("listvb", [])
            except Exception:
                listvb = []
            for vb in listvb:
                vid = vb.get("id", "").strip()
                if not vid:
                    continue
                key = "van_ban_bi_thay_the_toan_phan" if vb.get("kieu") == "ALL" \
                      else "van_ban_bi_thay_the_mot_phan"
                raw[key].append(vid)

    for a in soup.select('a[href*="/$FILE/"]'):
        name = a.get_text(strip=True)
        if name.lower().endswith((".doc", ".docx", ".pdf")):
            raw["file_dinh_kem"].append({
                "filename"    : name,
                "download_url": urljoin(DOMINO_BASE_URL, a.get("href", "")),
            })

    REQUIRED = {"so_ky_hieu", "ten_van_ban", "ngay_ban_hanh", "hinh_thuc_van_ban"}
    print()
    print(f"  {'TRUONG':32s}  GIA TRI")
    print(f"  {'-'*32}  {'-'*42}")
    for k, v in raw.items():
        if isinstance(v, list):
            display = f"[{len(v)} items] " + str(v)[:35] if v else "[]"
        else:
            display = str(v)[:55] if v else "(trong)"
        flag = "  * required" if (k in REQUIRED and not v) else ""
        print(f"  {k:32s}  {display}{flag}")

    print()
    missing = [k for k in REQUIRED if not raw.get(k)]
    if missing:
        _warn(f"Thieu truong bat buoc: {missing}")
    else:
        _ok("Du truong bat buoc")
    _ok(f"File dinh kem : {len(raw['file_dinh_kem'])}")
    _ok(f"REPLACE docs  : {len(raw['van_ban_bi_thay_the_toan_phan'])}")
    _ok(f"AMEND docs    : {len(raw['van_ban_bi_thay_the_mot_phan'])}")

    return raw


# ══════════════════════════════════════════════════════════════════════════════
# Buoc 5 — Map schema & upsert MongoDB
# ══════════════════════════════════════════════════════════════════════════════

def step5_upsert(raw: dict, unid: str) -> None:
    _header("Buoc 5 — Map schema & Upsert MongoDB")

    from pymongo import MongoClient

    def split_names(text):
        if not text: return []
        return [{"name": p.strip(), "id": ""} for p in re.split(r"[;,]", text) if p.strip()]

    def split_list(text):
        if not text: return []
        return [p.strip() for p in re.split(r"[;,]", text) if p.strip()]

    def resolve_status(r):
        s = (r.get("tinh_trang_hieu_luc") or "").lower()
        if "còn hiệu lực" in s: return "Con hieu luc"
        if "hết hiệu lực" in s: return "Het hieu luc"
        if r.get("ngay_het_hieu_luc"):
            try:
                if datetime.strptime(r["ngay_het_hieu_luc"], "%Y-%m-%d") < datetime.now():
                    return "Het hieu luc"
            except ValueError:
                pass
        return "Khong xac dinh"

    now  = datetime.now().strftime("%Y-%m-%d")
    rels = []
    for did in raw.get("van_ban_bi_thay_the_toan_phan", []):
        rels.append({"relationship_type": "REPLACE", "target_doc_id": did, "target_doc_title": ""})
    for did in raw.get("van_ban_bi_thay_the_mot_phan", []):
        rels.append({"relationship_type": "AMEND",   "target_doc_id": did, "target_doc_title": ""})

    doc = {
        "doc_id"          : f"doc_{unid[:8]}",
        "doc_code"        : raw.get("so_ky_hieu")       or "",
        "doc_title"       : raw.get("ten_van_ban")       or "",
        "doc_type"        : raw.get("hinh_thuc_van_ban") or "",
        "issue_agencies"  : split_names(raw.get("co_quan_ban_hanh")),
        "signers"         : split_names(raw.get("nguoi_ky")),
        "issued_level"    : {"name": raw.get("cap_ban_hanh") or "", "id": ""},
        "issued_date"     : raw.get("ngay_ban_hanh"),
        "effective_date"  : raw.get("ngay_co_hieu_luc"),
        "effective_status": resolve_status(raw),
        "industry_sectors": split_list(raw.get("chuyen_de")),
        "keywords"        : split_list(raw.get("tu_khoa")),
        "content": {
            "doc_file_path": raw["file_dinh_kem"][0]["filename"] if raw.get("file_dinh_kem") else "",
            "raw_text": None, "html": None,
        },
        "source"       : {"name": "crawler", "id": unid},
        "relationships": rels,
        "created_at"   : now,
        "updated_at"   : now,
    }

    _info("Document sau khi map:")
    pprint({k: v for k, v in doc.items() if k != "relationships"}, indent=4)
    if rels:
        _info(f"relationships: {rels}")

    try:
        client = MongoClient(
            host=MONGO_HOST, port=MONGO_PORT,
            username=MONGO_USERNAME or None,
            password=MONGO_PASSWORD or None,
            serverSelectionTimeoutMS=3000,
        )
        client.server_info()
        col = client[MONGO_DB][MONGO_COLLECTION]
        _ok(f"Ket noi MongoDB: {MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}")
    except Exception as e:
        _abort(f"Khong ket noi duoc MongoDB: {e}")

    existing = col.find_one({"doc_id": doc["doc_id"]}, {"created_at": 1})
    if existing:
        doc["created_at"] = existing.get("created_at", now)
        doc["updated_at"] = now
        col.update_one({"doc_id": doc["doc_id"]}, {"$set": doc})
        action = "UPDATED"
    else:
        col.insert_one(doc)
        action = "INSERTED"

    print()
    _ok(f"Ket qua: {action}  —  doc_id = {doc['doc_id']}")
    _ok(f"Collection '{MONGO_COLLECTION}' hien co: {col.count_documents({})} docs")




# ══════════════════════════════════════════════════════════════════════════════
# Buoc 4.5 — Download file dinh kem ve local
# ══════════════════════════════════════════════════════════════════════════════

def step45_download(raw: dict) -> dict:
    """
    Download tung file dinh kem trong raw["file_dinh_kem"] ve DOWNLOAD_DIR.
    Cap nhat raw["file_dinh_kem"] voi "local_path" sau khi download thanh cong.
    Tra ve raw da cap nhat.
    """
    _header("Buoc 4.5 — Download file dinh kem")

    files = raw.get("file_dinh_kem", [])
    if not files:
        _warn("Khong co file dinh kem nao de download")
        return raw

    import requests
    save_dir = Path(DOWNLOAD_DIR)
    save_dir.mkdir(parents=True, exist_ok=True)
    _info(f"Thu muc luu: {save_dir.resolve()}")
    _info(f"So file can download: {len(files)}")
    print()

    for i, f in enumerate(files, 1):
        filename    = f.get("filename", "")
        download_url= f.get("download_url", "")

        if not download_url:
            _warn(f"  [{i}] {filename} — khong co URL, bo qua")
            continue

        save_path = save_dir / filename
        _info(f"  [{i}] {filename}")
        _info(f"       URL: {download_url}")

        # Bo qua neu da ton tai
        if save_path.exists():
            _ok(f"       Da ton tai: {save_path}")
            f["local_path"] = str(save_path)
            continue

        try:
            resp = requests.get(download_url, timeout=60, stream=True)
            resp.raise_for_status()

            size = 0
            with open(save_path, "wb") as fp:
                for chunk in resp.iter_content(chunk_size=8192):
                    fp.write(chunk)
                    size += len(chunk)

            f["local_path"] = str(save_path)
            _ok(f"       Luu thanh cong — {size/1024:.1f} KB -> {save_path}")

        except Exception as e:
            _err(f"       Loi download: {e}")
            f["local_path"] = None

    print()
    ok_count   = sum(1 for f in files if f.get("local_path"))
    fail_count = len(files) - ok_count
    _ok(f"Thanh cong: {ok_count}/{len(files)} file")
    if fail_count:
        _warn(f"That bai   : {fail_count}/{len(files)} file")

    return raw

# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Test tung buoc migration Domino -> MongoDB")
    parser.add_argument("--step", type=str, choices=["1","2","3","4","45","5"],
                        help="Chi chay buoc cu the (1/2/3/4/45/5). Mac dinh: chay tat ca.")
    parser.add_argument("--unid", type=str, default=SAMPLE_UNID,
                        help="UNID de test Buoc 4 & 5")
    args = parser.parse_args()

    raw_step  = args.step
    only      = int(raw_step) if raw_step and raw_step != "45" else (45 if raw_step == "45" else None)
    unid      = args.unid
    view_unid = None
    raw       = None

    try:
        if only in (None, 1): step1_check()
        if only in (None, 2): view_unid = step2_get_collections()

        if only in (None, 3):
            if not view_unid:
                view_unid = step2_get_collections()
            unids = step3_get_unids(view_unid)
            if unids and not unid:
                unid = unids[0]
                _info(f"Tu dong chon UNID dau tien: {unid}")

        if only in (None, 4):
            if not unid:
                _abort("Can UNID. Chay buoc 3 truoc hoac truyen --unid <UNID>")
            raw = step4_extract(unid)

        if only in (None, "45", 45):
            if not raw:
                if not unid:
                    _abort("Can UNID. Chay buoc 4 truoc hoac truyen --unid <UNID>")
                raw = step4_extract(unid)
            raw = step45_download(raw)

        if only in (None, 5):
            if not raw:
                if not unid:
                    _abort("Can UNID. Truyen --unid <UNID>")
                raw = step4_extract(unid)
            step5_upsert(raw, unid)

        print(f"\n{'='*60}")
        print(f"  [OK]  Hoan thanh!")
        print(f"{'='*60}\n")

    except SystemExit:
        raise
    except Exception as e:
        print()
        _err(f"Loi khong mong doi: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()