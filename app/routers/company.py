"""API hồ sơ công ty và xác minh pháp nhân."""
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import get_current_user
from app.crud import company as company_crud
from app.db.session import get_db
from app.models.company import Company, CompanyStatus
from app.models.user import User
from app.schemas.company_schema import (
    CompanyProfileUpdate,
    CompanyResponse,
    CompanyVerificationDecision,
    CompanyVerificationSubmit,
)
from app.services.company_logo_service import validate_and_save_company_logo
from app.services.company_verification_actions import handle_employer_mst_update_if_changed

router = APIRouter(prefix="/company", tags=["Company"])
admin_router = APIRouter(prefix="/admin/companies", tags=["Company verification - Admin"])

_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}


def _require_employer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "employer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Chỉ nhà tuyển dụng mới được thực hiện thao tác này")
    return current_user


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Chỉ Admin mới được thực hiện thao tác này")
    return current_user


def _get_my_company(current_user: User = Depends(_require_employer), db: Session = Depends(get_db)):
    company = company_crud.get_company_by_employer(db, current_user.id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy hồ sơ công ty cho tài khoản này")
    return company


def _save_upload(file: UploadFile, subfolder: str) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS or file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Chỉ chấp nhận file ảnh JPG hoặc PNG")
    content = file.file.read()
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "File ảnh không được để trống")
    if len(content) > settings.MAX_UPLOAD_BYTES:
        mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File quá lớn. Giới hạn tối đa {mb} MB")

    unique_name = f"{uuid.uuid4().hex}{suffix}"
    dest_dir = Path(settings.UPLOAD_DIR) / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / unique_name).write_bytes(content)
    return f"/uploads/{subfolder}/{unique_name}"


@router.get("/me", response_model=CompanyResponse, summary="Xem hồ sơ công ty của tôi")
def get_my_company(company=Depends(_get_my_company)):
    return company


@router.put("/me", response_model=CompanyResponse, summary="Cập nhật hồ sơ công ty")
def update_my_company(
    data: CompanyProfileUpdate,
    company=Depends(_get_my_company),
    current_user: User = Depends(_require_employer),
    db: Session = Depends(get_db),
):
    if data.tax_code is not None:
        data.tax_code = handle_employer_mst_update_if_changed(db, company, current_user, data.tax_code)
    return company_crud.update_company(db, company, data)


@router.post("/me/logo", response_model=CompanyResponse, summary="Upload logo công ty (PNG/WebP, <= 200 KB)")
def upload_my_company_logo(
    file: UploadFile = File(..., description="File ảnh PNG hoặc WebP"),
    company=Depends(_get_my_company),
    current_user: User = Depends(_require_employer),
    db: Session = Depends(get_db),
):
    logo_url = validate_and_save_company_logo(file, company.id)
    return company_crud.update_company_logo(db, company, logo_url, current_user.id)


@router.post("/me/logo/remove", response_model=CompanyResponse, summary="Gỡ logo công ty")
def remove_my_company_logo(company=Depends(_get_my_company), db: Session = Depends(get_db)):
    return company_crud.remove_company_logo(db, company)


@router.post("/{company_id}/logo", response_model=CompanyResponse, summary="Upload logo công ty theo ID")
def upload_company_logo_by_id(
    company_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comp = db.get(Company, company_id)
    if comp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy công ty")
    if current_user.role != "admin" and comp.employer_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bạn không có quyền sửa logo của công ty này")
    logo_url = validate_and_save_company_logo(file, comp.id)
    return company_crud.update_company_logo(db, comp, logo_url, current_user.id)


@router.post("/me/cover", response_model=CompanyResponse, summary="Upload ảnh bìa công ty")
def upload_cover(file: UploadFile = File(...), company=Depends(_get_my_company), db: Session = Depends(get_db)):
    cover_url = _save_upload(file, "covers")
    return company_crud.update_company_cover(db, company, cover_url)


@router.post("/me/verification-document", response_model=CompanyResponse, summary="Tải ảnh giấy phép kinh doanh")
def upload_verification_document(
    file: UploadFile = File(...),
    company=Depends(_get_my_company),
    db: Session = Depends(get_db),
):
    company.verification_document = _save_upload(file, "verification")
    db.commit()
    db.refresh(company)
    return company


@router.post("/me/verification", response_model=CompanyResponse, summary="Gửi hồ sơ xác minh công ty")
def submit_verification(
    data: CompanyVerificationSubmit,
    company=Depends(_get_my_company),
    db: Session = Depends(get_db),
):
    if company.status == CompanyStatus.VERIFIED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Công ty đã được xác minh")
    if not company.verification_document:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Vui lòng tải ảnh giấy phép kinh doanh trước khi gửi")
    if not data.tax_code.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Mã số thuế không được để trống")
    return company_crud.submit_company_verification(db, company, data.tax_code)


@admin_router.get("/verifications", response_model=list[CompanyResponse], summary="Danh sách hồ sơ chờ xác minh")
def list_company_verifications(_admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    return company_crud.get_pending_verifications(db)


@admin_router.post("/{company_id}/verification", response_model=CompanyResponse, summary="Duyệt / từ chối xác minh")
def review_company_verification(
    company_id: int,
    data: CompanyVerificationDecision,
    _admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    company = company_crud.get_company_for_review(db, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy công ty")
    if company.status != CompanyStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Hồ sơ công ty không còn ở trạng thái chờ duyệt")
    if company.verification_submitted_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Công ty chưa gửi hồ sơ xác minh")
    if data.status == "REJECTED" and not (data.reason and data.reason.strip()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Vui lòng nhập lý do từ chối")
    return company_crud.decide_company_verification(
        db, company, status=CompanyStatus(data.status), reason=data.reason.strip() if data.reason else None
    )
