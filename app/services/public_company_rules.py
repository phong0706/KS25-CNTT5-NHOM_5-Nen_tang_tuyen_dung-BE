"""Quy tắc chuẩn hóa tìm kiếm, kiểm tra URL hợp lệ và rate limit cho API Công ty công khai."""
from collections import defaultdict, deque
from datetime import datetime, timezone
import re
import time
import unicodedata
from urllib.parse import urlparse

VALID_SIZE_RANGES = ("1-50", "51-200", "201-500", "501-1000", "1000+")

# Rate limit nhẹ trong bộ nhớ cho endpoint tìm kiếm /api/companies?q=
_SEARCH_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_SEARCH_WINDOW_SEC = 60.0
_SEARCH_MAX_REQ = 60


def normalize_search_text(*parts: str | None) -> str:
    """Chuẩn hóa chuỗi tìm kiếm: chữ thường, bỏ dấu tiếng Việt, đ -> d, gộp khoảng trắng."""
    joined = " ".join(str(p) for p in parts if p)
    if not joined:
        return ""
    lowered = joined.replace("Đ", "d").replace("đ", "d").lower()
    nfd = unicodedata.normalize("NFD", lowered)
    no_marks = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", no_marks).strip()


def escape_like(raw_query: str) -> str:
    """Chuẩn hóa và escape ký tự đại diện LIKE (%, _, \\) chống wildcard injection."""
    norm = normalize_search_text(raw_query)
    if not norm:
        return ""
    return norm.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def slugify_skill(name: str) -> str:
    """Chuyển tên kỹ năng thành slug ASCII an toàn cho URL filter ?skills=."""
    norm = normalize_search_text(name)
    norm = norm.replace("#", "sharp").replace("++", "pp").replace(".", "")
    return re.sub(r"[^a-z0-9]+", "-", norm).strip("-") or "skill"


def validate_company_website(url: str | None) -> str | None:
    """Chỉ chấp nhận http:// hoặc https:// có hostname; từ chối javascript:, data:, file:."""
    if url is None or not str(url).strip():
        return None
    val = str(url).strip()
    if len(val) > 255 or any(ord(c) < 32 for c in val):
        raise ValueError("URL website không hợp lệ.")
    parsed = urlparse(val)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise ValueError("Website chỉ hỗ trợ giao thức http:// hoặc https://.")
    return val


def validate_company_media_url(url: str | None) -> str | None:
    """Chỉ chấp nhận ảnh từ https:// hoặc đường dẫn /uploads/... hợp lệ."""
    if url is None or not str(url).strip():
        return None
    val = str(url).strip()
    if len(val) > 500 or any(ord(c) < 32 for c in val):
        raise ValueError("Đường dẫn ảnh không hợp lệ.")
    if val.startswith("/uploads/") and ".." not in val:
        return val
    parsed = urlparse(val)
    if parsed.scheme.lower() == "https" and parsed.netloc:
        return val
    raise ValueError("Ảnh công ty chỉ chấp nhận URL https:// hoặc đường dẫn /uploads/.")


def validate_founded_year(year: int | None) -> int | None:
    """Kiểm tra năm thành lập nằm trong khoảng 1900..năm hiện tại."""
    if year is None:
        return None
    cur_year = datetime.now(timezone.utc).year
    if year < 1900 or year > cur_year:
        raise ValueError(f"Năm thành lập phải từ 1900 đến {cur_year}.")
    return year


def check_company_search_rate_limit(client_ip: str) -> bool:
    """Trả False nếu IP vượt quá 60 request tìm kiếm / phút (không làm hỏng health/pytest)."""
    key = client_ip or "unknown"
    now = time.monotonic()
    q = _SEARCH_RATE_BUCKETS[key]
    while q and now - q[0] > _SEARCH_WINDOW_SEC:
        q.popleft()
    if len(q) >= _SEARCH_MAX_REQ:
        return False
    q.append(now)
    return True
