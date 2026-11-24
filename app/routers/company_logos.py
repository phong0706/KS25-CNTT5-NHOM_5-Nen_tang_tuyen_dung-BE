"""Router cho quản lý logo công ty & danh sách công ty trang chủ (/api/home/companies, /api/companies/{id}/logos...).
Tuân thủ techrecruit-rules: <= 200 dòng, phân quyền chặt chẽ.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user, role_required
from app.db.session import get_db
from app.models.company import Company
from app.models.company_logo import CompanyLogo
from app.models.user import User
from app.services.company_logo_service import (
    approve_company_logo,
    get_home_companies,
    get_logo_original_path,
    handle_logo_error,
    reject_company_logo,
    remove_company_logo,
    upload_company_logo,
)
from app.services.logo_processing import LogoError, process_logo

router = APIRouter(tags=["Company Logos & Home Companies"])


class HomeCompanyOut(BaseModel):
    id: int
    name: str
    slug: Optional[str] = None
    logo_url: Optional[str] = None
    logo_url_2x: Optional[str] = None
    logo_version: int = 1
    open_jobs: int = 0


class LogoRejectPayload(BaseModel):
    reason: str = Field(..., min_length=10, description="Lý do từ chối tối thiểu 10 ký tự")


class CompanyLogoOut(BaseModel):
    id: int
    company_id: int
    file_key: str
    file_key_2x: Optional[str] = None
    version: int
    status: str
    is_current: bool
    uploaded_by: Optional[int] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[str] = None
    reject_reason: Optional[str] = None
    created_at: str
    logo_url: str
    logo_url_2x: Optional[str] = None


def _serialize_logo(logo: CompanyLogo) -> dict:
    return {
        "id": logo.id,
        "company_id": logo.company_id,
        "file_key": logo.file_key,
        "file_key_2x": logo.file_key_2x,
        "version": logo.version,
        "status": logo.status,
        "is_current": logo.is_current,
        "uploaded_by": logo.uploaded_by,
        "reviewed_by": logo.reviewed_by,
        "reviewed_at": logo.reviewed_at.isoformat() if logo.reviewed_at else None,
        "reject_reason": logo.reject_reason,
        "created_at": logo.created_at.isoformat() if logo.created_at else "",
        "logo_url": f"/uploads/logos/{logo.file_key}?v={logo.version}",
        "logo_url_2x": f"/uploads/logos/{logo.file_key_2x}?v={logo.version}" if logo.file_key_2x else None,
    }


@router.get("/uploads/logos/{filename}", summary="Phục vụ file ảnh logo với bảo vệ nosniff")
def serve_logo_file(filename: str):
    clean_name = os.path.basename(filename)
    file_path = Path(settings.UPLOAD_DIR) / "logos" / clean_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "Không tìm thấy tệp ảnh logo.")
    media_type = "image/webp" if clean_name.endswith(".webp") else "image/png"
    return FileResponse(
        str(file_path),
        media_type=media_type,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=86400"},
    )


@router.get("/api/company-logos/{logo_id}/original", summary="Phục vụ ảnh gốc của logo cho quản trị viên")
def serve_original_logo(
    logo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin", "operator")),
):
    logo = db.query(CompanyLogo).filter_by(id=logo_id).first()
    if not logo:
        raise HTTPException(404, "Không tìm thấy logo.")
    orig_path = get_logo_original_path(logo.file_key)
    if not orig_path or not orig_path.exists():
        raise HTTPException(404, "Không tìm thấy tệp ảnh gốc.")
    return FileResponse(
        str(orig_path),
        media_type="image/png",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-cache"},
    )


@router.post("/api/employer/company/logo/preview", summary="Xem trước logo chuẩn hóa mà không lưu")
@router.post("/api/company/me/logo/preview", summary="Xem trước logo chuẩn hóa mà không lưu")
async def preview_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(role_required("employer", "recruiter", "admin", "operator")),
):
    content = await file.read()
    if not content:
        raise HTTPException(422, "Tệp ảnh rỗng hoặc không có dữ liệu.")
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Dung lượng ảnh vượt quá giới hạn 2MB. Vui lòng chọn tệp nhỏ hơn.")
    try:
        processed = process_logo(content)
    except LogoError as e:
        handle_logo_error(e)

    import base64, io
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(content))
        orig_w, orig_h = im.size
    except Exception:
        orig_w, orig_h = 256, 256

    b64_256 = base64.b64encode(processed[256]).decode("utf-8")
    b64_512 = base64.b64encode(processed[512]).decode("utf-8")
    return {
        "preview_url_256": f"data:image/webp;base64,{b64_256}",
        "preview_url_512": f"data:image/webp;base64,{b64_512}",
        "orig_width": orig_w,
        "orig_height": orig_h,
        "orig_ratio": round(orig_w / orig_h, 2) if orig_h else 1.0,
    }


@router.get("/api/home/companies", response_model=List[HomeCompanyOut], summary="Danh sách công ty đủ điều kiện cho trang chủ")
def list_home_companies(db: Session = Depends(get_db)):
    return get_home_companies(db)


@router.get("/api/companies/{company_id}/logos", response_model=List[CompanyLogoOut], summary="Lịch sử các phiên bản logo của công ty")
def list_company_logos(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer", "recruiter", "admin", "operator")),
):
    comp = db.query(Company).filter_by(id=company_id).first()
    if not comp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy công ty.")
    if current_user.role in ("employer", "recruiter") and comp.owner_id != current_user.id and comp.employer_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy công ty.")
    logos = db.query(CompanyLogo).filter_by(company_id=company_id).order_by(CompanyLogo.version.desc(), CompanyLogo.id.desc()).all()
    return [_serialize_logo(l) for l in logos]


@router.post("/api/companies/{company_id}/logos", response_model=CompanyLogoOut, summary="Tải lên logo công ty mới (chờ duyệt)")
async def upload_logo(
    company_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer", "recruiter", "admin", "operator")),
):
    comp = db.query(Company).filter_by(id=company_id).first()
    if not comp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy công ty.")
    if current_user.role in ("employer", "recruiter"):
        if comp.owner_id != current_user.id and comp.employer_id != current_user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy công ty.")

    content = await file.read()
    new_logo = upload_company_logo(db, company_id, content, current_user.id)
    return _serialize_logo(new_logo)


@router.post("/api/company-logos/{logo_id}/approve", response_model=CompanyLogoOut, summary="Duyệt logo công ty")
def approve_logo(
    logo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin", "operator")),
):
    logo = approve_company_logo(
        db, logo_id, current_user.id, current_user.full_name or current_user.email, current_user.role
    )
    return _serialize_logo(logo)


@router.post("/api/company-logos/{logo_id}/reject", response_model=CompanyLogoOut, summary="Từ chối logo công ty")
def reject_logo(
    logo_id: int,
    payload: LogoRejectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("admin", "operator")),
):
    logo = reject_company_logo(
        db, logo_id, payload.reason, current_user.id, current_user.full_name or current_user.email, current_user.role
    )
    return _serialize_logo(logo)


@router.delete("/api/companies/{company_id}/logo", summary="Gỡ logo đang dùng của công ty")
def remove_logo(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("employer", "recruiter", "admin", "operator")),
):
    comp = db.query(Company).filter_by(id=company_id).first()
    if not comp:
        raise HTTPException(404, "Không tìm thấy công ty.")
    if current_user.role not in ("admin", "operator"):
        if comp.owner_id != current_user.id and comp.employer_id != current_user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy công ty.")
    comp = remove_company_logo(
        db, company_id, current_user.id, current_user.full_name or current_user.email, current_user.role
    )
    return {
        "status": "success",
        "message": f"Đã gỡ logo của công ty {comp.name}.",
        "company_id": comp.id,
        "logo_version": comp.logo_version,
    }
