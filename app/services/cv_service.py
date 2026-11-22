"""cv_service.py - Nghiệp vụ kiểm tra magic bytes, bảo mật lưu trữ và xử lý file CV.

Tuân thủ techrecruit-rules: <= 180 dòng, thuần chuẩn thư viện chuẩn Python (không thêm dependency).
"""
import hashlib
import io
import logging
import os
from pathlib import Path
import re
import uuid
import zipfile
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.application import CV, Application
from app.schemas.application import CVOut

logger = logging.getLogger("techrecruit.cv")

MAX_CV_SIZE = 5 * 1024 * 1024  # 5MB
MAX_UNCOMPRESSED_ZIP_SIZE = 30 * 1024 * 1024  # 30MB
MAX_ZIP_ENTRIES = 500
MAX_CVS_PER_USER = 5

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CV_STORAGE_DIR = os.path.join(BASE_DIR, getattr(settings, "CV_UPLOAD_DIR", "storage/cvs"))
LEGACY_UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "cvs")


def should_delete_physical_file(used_in_apps_count: int, other_cv_references_count: int = 0) -> bool:
    """Quyết định có xóa file vật lý trên đĩa không (chỉ xóa khi 0 đơn và 0 CV khác trỏ tới)."""
    return used_in_apps_count == 0 and other_cv_references_count == 0


def pick_new_default_cv(remaining_active_cvs: list):
    """Chọn CV mặc định mới từ danh sách còn lại (chưa xóa mềm), ưu tiên bản ghi mới nhất."""
    if not remaining_active_cvs:
        return None
    from datetime import datetime, timezone
    min_date = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(remaining_active_cvs, key=lambda c: getattr(c, "created_at", None) or min_date, reverse=True)[0]


def ensure_storage_dirs() -> None:
    os.makedirs(CV_STORAGE_DIR, exist_ok=True)


def get_cv_file_path(stored_name: str) -> str:
    """Trả về đường dẫn tuyệt đối của file CV. Ưu tiên storage/cvs, fallback uploads/cvs."""
    clean = os.path.basename(stored_name or "")
    p = os.path.join(CV_STORAGE_DIR, clean)
    if os.path.isfile(p):
        return p
    legacy_p = os.path.join(LEGACY_UPLOAD_DIR, clean)
    if os.path.isfile(legacy_p):
        return legacy_p
    return p


def sanitize_cv_name(name: str, max_length: int = 120) -> str:
    """Làm sạch tên hiển thị của file CV (chặn traversal, bỏ ký tự điều khiển, giữ dấu tiếng Việt)."""
    clean = os.path.basename(name.replace("\\", "/"))
    clean = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]', "", clean).strip()
    if not clean:
        clean = "CV_Tai_Len.pdf"
    if len(clean) > max_length:
        base, ext = os.path.splitext(clean)
        clean = base[: max_length - len(ext)] + ext
    return clean


def validate_cv_content(content: bytes) -> tuple[str, str]:
    """Kiểm tra magic bytes thật của file (PDF, DOC, DOCX) và chống zip bomb."""
    if not content or len(content) == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="File rỗng (0 byte).")
    if len(content) < 1024:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dung lượng file quá nhỏ (tối thiểu 1 KB).")
    if len(content) > MAX_CV_SIZE:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dung lượng file vượt quá 5 MB.")

    # 1. PDF: %PDF-
    if content.startswith(b"%PDF-"):
        return "application/pdf", ".pdf"

    # 2. DOC (OLE2 compound binary): \xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1
    if content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/msword", ".doc"

    # 3. DOCX: ZIP archive chứa [Content_Types].xml và thư mục word/
    if content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                namelist = zf.namelist()
                if len(namelist) > MAX_ZIP_ENTRIES:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="DOCX chứa quá nhiều tệp con bất thường.")
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > MAX_UNCOMPRESSED_ZIP_SIZE:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="DOCX vượt quá giới hạn giải nén (chống zip bomb).")
                has_content_types = "[Content_Types].xml" in namelist
                has_word_dir = any(n.startswith("word/") for n in namelist)
                if not (has_content_types and has_word_dir):
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cấu trúc DOCX không hợp lệ.")
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"
        except zipfile.BadZipFile:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tệp ZIP bị hỏng hoặc không phải DOCX hợp lệ.")

    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nội dung file không hợp lệ. Chỉ chấp nhận PDF, DOC hoặc DOCX.")


def check_duplicate_content(db: Session, candidate_id: int, content: bytes) -> None:
    """Kiểm tra trùng hash SHA-256 nội dung trong cùng người dùng."""
    in_hash = hashlib.sha256(content).hexdigest()
    user_cvs = db.scalars(select(CV).where(CV.candidate_id == candidate_id)).all()
    for cv in user_cvs:
        p = get_cv_file_path(cv.stored_name)
        if os.path.isfile(p):
            try:
                with open(p, "rb") as f:
                    if hashlib.sha256(f.read()).hexdigest() == in_hash:
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CV này đã được tải lên trước đó.")
            except HTTPException:
                raise
            except Exception:
                pass


def build_cv_response(cv: CV, used_count: int, active_count: int) -> CVOut:
    """Tạo schema CVOut đầy đủ thông tin bổ sung và allowed_actions."""
    actions = ["view", "download", "rename"]
    if not cv.is_default:
        actions.append("set_default")
    if active_count == 0:
        actions.append("delete")

    return CVOut(
        id=cv.id,
        original_name=cv.original_name,
        mime_type=cv.mime_type,
        size_bytes=cv.size_bytes,
        is_default=cv.is_default,
        created_at=cv.created_at,
        mime=cv.mime_type,
        size=cv.size_bytes,
        uploaded_at=cv.created_at,
        used_count=used_count,
        allowed_actions=actions,
    )
