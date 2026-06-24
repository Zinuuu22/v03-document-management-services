import unicodedata


def collapse_whitespace(text: str) -> str:
    """Collapse runs of whitespace into single spaces and strip the ends."""
    if not isinstance(text, str):
        return ""
    return " ".join(text.split()).strip()


def normalize_name_no_diacritics(text: str) -> str:
    """Strip Vietnamese diacritics and collapse whitespace (keeps casing)."""
    if not isinstance(text, str):
        return ""
    try:
        nfkd = unicodedata.normalize("NFD", text)
        no_diacritics = "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn")
        return collapse_whitespace(no_diacritics)
    except Exception:
        return ""


def normalize_for_label_match(text: str) -> str:
    """
    Lowercase + strip Vietnamese diacritics + collapse whitespace.
    Used to match source labels (article title / article_class) tolerant of
    diacritics and casing. NFD does not decompose đ/Đ, so fold them explicitly.
    """
    base = normalize_name_no_diacritics(text)
    base = base.replace("đ", "d").replace("Đ", "D")
    return base.lower().strip()


def normalize_name_fold_d(text: str) -> str:
    """
    Strip Vietnamese diacritics + fold đ/Đ -> d/D, but KEEP original casing.
    Used for the `*_norm` fields stored in the Mongo write schema (e.g.
    "dien luc", not "đien luc" / "DIEN LUC"). NFD does not decompose đ/Đ, so
    fold them explicitly, same as normalize_for_label_match but without the
    lowercasing that label matching needs and storage norms must not have.
    """
    base = normalize_name_no_diacritics(text)
    return base.replace("đ", "d").replace("Đ", "D")


def local_now_str() -> str:
    """Return server local time in 'YYYY-MM-DD HH:MM:SS'."""
    from datetime import datetime

    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
