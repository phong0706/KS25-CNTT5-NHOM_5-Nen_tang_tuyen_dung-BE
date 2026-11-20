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
from app.models.company import CompanyStatus
from app.models.company_logo import CompanyLogo
from app.models.user import User
from app.schemas.company_schema import (
    CompanyProfileUpdate,
    CompanyResponse,
    CompanyVerificationDecision,
    CompanyVerificationSubmit,
)
from app.services.company_logo_service import remove_company_logo, upload_company_logo
from app.services.company_verification_actions import handle_employer_mst_update_if_changed

router = APIRouter(prefix="/company", tags=["Company"])
admin_router = APIRouter(prefix="/admin/companies", tags=["Company verification - Admin"])

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


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ Admin mới được thực hiện thao tác này")
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
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File ảnh không được để trống",
        )
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
def get_my_company(
    company=Depends(_get_my_company),
    db: Session = Depends(get_db),
):
    """Trả về toàn bộ thông tin hồ sơ công ty của employer đang đăng nhập kèm trạng thái logo."""
    pending = db.query(CompanyLogo).filter_by(company_id=company.id, status="cho_duyet").order_by(CompanyLogo.id.desc()).first()
    if pending:
        company.logo_status = "pending"
        company.pending_logo = {
            "id": pending.id,
            "version": pending.version,
            "logo_url": f"/uploads/logos/{pending.file_key}?v={pending.version}",
            "logo_url_2x": f"/uploads/logos/{pending.file_key_2x}?v={pending.version}" if pending.file_key_2x else None,
            "created_at": pending.created_at.isoformat() if pending.created_at else None,
        }
    return company


@router.put(
    "/me",
    response_model=CompanyResponse,
    summary="Cập nhật hồ sơ công ty",
)
def update_my_company(
    data: CompanyProfileUpdate,
    company=Depends(_get_my_company),
    current_user: User = Depends(_require_employer),
    db: Session = Depends(get_db),
):
    """Sửa thông tin hồ sơ công ty.

    Nếu sửa MST của công ty đang da_xac_minh -> chuẩn hóa MST, chuyển về cho_duyet & đưa tin mở sang chờ xác minh lại.
    """
    if data.tax_code is not None:
        data.tax_code = handle_employer_mst_update_if_changed(db, company, current_user, data.tax_code)
    return company_crud.update_company(db, company, data)


@router.post(
    "/me/logo",
    summary="Upload logo công ty (PNG/JPEG/WebP, tối đa 2 MB, chờ duyệt)",
)
async def upload_logo(
    file: UploadFile = File(..., description="File ảnh logo (.png, .jpg, .webp, tối đa 2 MB)"),
    company=Depends(_get_my_company),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload logo công ty qua module chuẩn hóa và đưa vào hàng đợi duyệt."""
    content = await file.read()
    logo_entry = upload_company_logo(db, company.id, content, current_user.id)
    return {
        "status": "pending",
        "message": "Logo đã được tải lên thành công và đang chờ admin duyệt.",
        "logo_id": logo_entry.id,
        "company_id": company.id,
        "version": logo_entry.version,
    }


@router.delete(
    "/me/logo",
    summary="Xóa logo công ty của tôi",
)
def remove_my_logo(
    company=Depends(_get_my_company),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comp = remove_company_logo(
        db, company.id, current_user.id, current_user.full_name or current_user.email, current_user.role
    )
    return {
        "status": "success",
        "message": f"Đã gỡ logo của công ty {comp.name}.",
        "company_id": comp.id,
        "logo_version": comp.logo_version,
    }


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


@router.post(
    "/me/verification-document",
    response_model=CompanyResponse,
    summary="Tải ảnh giấy phép kinh doanh",
)
def upload_verification_document(
    file: UploadFile = File(..., description="Ảnh giấy phép kinh doanh (.jpg hoặc .png)"),
    company=Depends(_get_my_company),
    db: Session = Depends(get_db),
):
    company.verification_document = _save_upload(file, "verification")
    db.commit()
    db.refresh(company)
    return company


@router.post(
    "/me/verification",
    response_model=CompanyResponse,
    summary="Gửi hồ sơ xác minh công ty",
)
def submit_verification(
    data: CompanyVerificationSubmit,
    company=Depends(_get_my_company),
    db: Session = Depends(get_db),
):
    if company.status == CompanyStatus.VERIFIED:
        raise HTTPException(status_code=409, detail="Công ty đã được xác minh")
    if not company.verification_document:
        raise HTTPException(
            status_code=422,
            detail="Vui lòng tải ảnh giấy phép kinh doanh trước khi gửi xác minh",
        )
    if not data.tax_code.strip():
        raise HTTPException(status_code=422, detail="Mã số thuế không được để trống")
    return company_crud.submit_company_verification(db, company, data.tax_code)


@admin_router.get(
    "/verifications",
    response_model=list[CompanyResponse],
    summary="Danh sách hồ sơ công ty chờ xác minh",
)
def list_company_verifications(
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    return company_crud.get_pending_verifications(db)


@admin_router.post(
    "/{company_id}/verification",
    response_model=CompanyResponse,
    summary="Duyệt hoặc từ chối hồ sơ xác minh",
)
def review_company_verification(
    company_id: int,
    data: CompanyVerificationDecision,
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    company = company_crud.get_company_for_review(db, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy công ty")
    if company.status != CompanyStatus.PENDING:
        raise HTTPException(status_code=409, detail="Hồ sơ công ty không còn ở trạng thái chờ duyệt")
    if company.verification_submitted_at is None:
        raise HTTPException(status_code=409, detail="Công ty chưa gửi hồ sơ xác minh")
    if data.status == "REJECTED" and not (data.reason and data.reason.strip()):
        raise HTTPException(status_code=422, detail="Vui lòng nhập lý do từ chối")

    return company_crud.decide_company_verification(
        db,
        company,
        status=CompanyStatus(data.status),
        reason=data.reason.strip() if data.reason else None,
    )
