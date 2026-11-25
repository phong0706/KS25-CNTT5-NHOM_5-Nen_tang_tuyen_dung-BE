"""Router Xác minh công ty phía Nhà tuyển dụng (/api/employer/...).
- Gửi yêu cầu (MST, ảnh/PDF giấy phép), xem trạng thái & lý do từ chối, gửi lại.
- Chặn xem yêu cầu của công ty khác (403).
Giới hạn: <= 200 dòng.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user, role_required
from app.db.session import get_db
from app.models.company import Company, CompanyStatus
from app.models.company_verification import CompanyVerification
from app.models.user import User
from app.services.company_verification_service import (
    LICENSE_PRIVATE_DIR,
    get_latest_verification,
    serialize_verification,
    submit_verification_request,
)
from app.services.employer_criteria_service import evaluate_employer_criteria

router = APIRouter(prefix="/employer", tags=["Employer Company Verification"])


def _require_employer_role(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("employer", "recruiter"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Chức năng này chỉ dành cho tài khoản nhà tuyển dụng."},
        )
    return user


def _get_or_create_my_company(db: Session, user: User) -> Company:
    comp = db.scalar(select(Company).where(Company.employer_id == user.id).order_by(Company.id.asc()))
    if comp:
        return comp
    comp = Company(
        employer_id=user.id,
        owner_id=user.id,
        name=f"Doanh nghiệp của {user.full_name or user.email.split('@')[0]}",
        status=CompanyStatus.PENDING,
        verification_status="chua_xac_minh",
        is_draft=True,
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp


@router.get("/company-verification", summary="Xem trạng thái xác minh công ty của nhà tuyển dụng hiện tại")
def get_my_company_verification(
    current_user: User = Depends(_require_employer_role),
    db: Session = Depends(get_db),
):
    comp = _get_or_create_my_company(db, current_user)
    verif = get_latest_verification(db, comp.id)
    return serialize_verification(db, comp, verif)


@router.get("/verification-criteria", summary="Xem danh sách tiêu chí xác thực của nhà tuyển dụng hiện tại")
def get_my_verification_criteria(
    current_user: User = Depends(_require_employer_role),
    db: Session = Depends(get_db),
):
    comp = _get_or_create_my_company(db, current_user)
    return evaluate_employer_criteria(db, comp)


@router.get("/companies/{company_id}/verification-criteria", summary="Xem tiêu chí xác thực theo company_id (chỉ chủ sở hữu hoặc admin)")
def get_company_verification_criteria(
    company_id: int,
    current_user: User = Depends(role_required("employer", "recruiter", "admin", "operator")),
    db: Session = Depends(get_db),
):
    if current_user.role not in ("employer", "recruiter", "admin", "operator"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "FORBIDDEN", "message": "Bạn không có quyền xem thông tin này."})
    comp = db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Không tìm thấy công ty."})
    if current_user.role in ("employer", "recruiter") and comp.employer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "FORBIDDEN", "message": "Bạn không có quyền xem tiêu chí xác thực của công ty khác."})
    return evaluate_employer_criteria(db, comp)


@router.get("/companies/{company_id}/verification", summary="Xem yêu cầu xác minh theo company_id (chỉ chủ sở hữu công ty)")
def get_company_verification_by_id(
    company_id: int,
    current_user: User = Depends(_require_employer_role),
    db: Session = Depends(get_db),
):
    comp = db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Không tìm thấy công ty."})
    if comp.employer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Bạn không có quyền xem hồ sơ xác minh của công ty khác."},
        )
    verif = get_latest_verification(db, comp.id)
    return serialize_verification(db, comp, verif)


@router.post(
    "/company-verification",
    status_code=status.HTTP_201_CREATED,
    summary="Gửi hoặc gửi lại yêu cầu xác minh công ty (MST + ảnh/PDF giấy phép)",
)
def post_my_company_verification(
    mst: str = Form(..., description="Mã số thuế 10 số hoặc 10 số kèm -XXX"),
    file: UploadFile = File(..., description="Ảnh JPG, PNG hoặc tài liệu PDF <= 5 MB"),
    current_user: User = Depends(_require_employer_role),
    db: Session = Depends(get_db),
):
    comp = _get_or_create_my_company(db, current_user)
    raw_bytes = file.file.read()
    return submit_verification_request(db, comp, current_user, mst, file.filename, raw_bytes)


@router.get("/company-verification/{verif_id}/license", summary="Nhà tuyển dụng xem lại tệp giấy phép đã gửi của chính công ty mình")
def get_my_verification_license(
    verif_id: int,
    current_user: User = Depends(_require_employer_role),
    db: Session = Depends(get_db),
):
    verif = db.get(CompanyVerification, verif_id)
    if not verif:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Không tìm thấy hồ sơ xác minh."})
    comp = db.get(Company, verif.company_id)
    if not comp or comp.employer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Bạn không có quyền truy cập giấy phép của công ty khác."},
        )
    path = LICENSE_PRIVATE_DIR / verif.license_storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "Không tìm thấy tệp giấy phép trên máy chủ."})
    return FileResponse(
        path=str(path),
        media_type=verif.license_mime_type,
        filename=verif.license_original_name or verif.license_storage_key,
        content_disposition_type="inline",
    )
