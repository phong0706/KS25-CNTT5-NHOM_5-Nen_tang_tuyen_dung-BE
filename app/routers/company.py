"""API hồ sơ công ty (dành cho employer).

    GET  /api/company/me            Xem hồ sơ công ty của mình
    PUT  /api/company/me            Sửa thông tin hồ sơ công ty
    POST /api/company/me/logo       Upload logo (jpg/png, tối đa 2 MB)
    POST /api/company/me/cover      Upload ảnh bìa (jpg/png, tối đa 2 MB)
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.crud import company as company_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.company_schema import CompanyProfileUpdate, CompanyResponse

router = APIRouter(prefix="/company", tags=["Company"])

# ------------------------------------------------------------------
# Hằng số upload
# ------------------------------------------------------------------
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
_MAX_BYTES = settings.MAX_UPLOAD_BYTES  # mặc định 2 MB


# ------------------------------------------------------------------
# Dependency dùng chung
# ------------------------------------------------------------------

def _require_employer(current_user: User = Depends(get_current_user)) -> User:
    """Chỉ cho phép tài khoản có role='employer' truy cập."""
    if current_user.role != "employer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ nhà tuyển dụng (employer) mới được thực hiện thao tác này",
        )
    return current_user


def _get_my_company(
    current_user: User = Depends(_require_employer),
    db: Session = Depends(get_db),
):
    """Lấy công ty của employer đang đăng nhập, trả 404 nếu chưa có."""
    company = company_crud.get_company_by_employer(db, current_user.id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hồ sơ công ty cho tài khoản này",
        )
    return company


# ------------------------------------------------------------------
# Helper: lưu file upload
# ------------------------------------------------------------------

def _save_upload(file: UploadFile, subfolder: str) -> str:
    """Kiểm tra định dạng + dung lượng, lưu file, trả về URL tương đối."""
    # Kiểm tra định dạng
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS or file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Chỉ chấp nhận file ảnh JPG hoặc PNG",
        )

    # Đọc nội dung và kiểm tra dung lượng
    content = file.file.read()
    if len(content) > _MAX_BYTES:
        mb = _MAX_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File quá lớn. Giới hạn tối đa {mb} MB",
        )

    # Tạo tên file ngẫu nhiên để tránh ghi đè
    unique_name = f"{uuid.uuid4().hex}{suffix}"
    dest_dir = Path(settings.UPLOAD_DIR) / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / unique_name

    dest_path.write_bytes(content)

    # Trả về URL tương đối (FE ghép với BASE_URL)
    return f"/uploads/{subfolder}/{unique_name}"


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.get(
    "/me",
    response_model=CompanyResponse,
    summary="Xem hồ sơ công ty của tôi",
)
def get_my_company(company=Depends(_get_my_company)):
    """Trả về toàn bộ thông tin hồ sơ công ty của employer đang đăng nhập."""
    return company


@router.put(
    "/me",
    response_model=CompanyResponse,
    summary="Cập nhật hồ sơ công ty",
)
def update_my_company(
    data: CompanyProfileUpdate,
    company=Depends(_get_my_company),
    db: Session = Depends(get_db),
):
    """Sửa thông tin hồ sơ công ty.

    Chỉ gửi lên các trường muốn thay đổi; trường không gửi sẽ **giữ nguyên**.
    Employer **không thể** tự thay đổi `status` (chỉ admin mới được).
    """
    return company_crud.update_company(db, company, data)


@router.post(
    "/me/logo",
    response_model=CompanyResponse,
    summary="Upload logo công ty (jpg/png, tối đa 2 MB)",
)
def upload_logo(
    file: UploadFile = File(..., description="File ảnh logo (.jpg hoặc .png, tối đa 2 MB)"),
    company=Depends(_get_my_company),
    db: Session = Depends(get_db),
):
    """Upload logo công ty.

    - Chỉ chấp nhận **JPG / PNG**.
    - Dung lượng tối đa **2 MB**.
    - File cũ **không** tự động xóa (có thể dọn dẹp định kỳ nếu cần).
    """
    logo_url = _save_upload(file, "logos")
    return company_crud.update_company_logo(db, company, logo_url)


@router.post(
    "/me/cover",
    response_model=CompanyResponse,
    summary="Upload ảnh bìa công ty (jpg/png, tối đa 2 MB)",
)
def upload_cover(
    file: UploadFile = File(..., description="File ảnh bìa (.jpg hoặc .png, tối đa 2 MB)"),
    company=Depends(_get_my_company),
    db: Session = Depends(get_db),
):
    """Upload ảnh bìa công ty.

    - Chỉ chấp nhận **JPG / PNG**.
    - Dung lượng tối đa **2 MB**.
    """
    cover_url = _save_upload(file, "covers")
    return company_crud.update_company_cover(db, company, cover_url)
