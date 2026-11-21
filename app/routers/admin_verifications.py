"""Router Quản trị Xác minh công ty (/api/admin/...):
- Danh sách theo trạng thái kèm số đếm, xem chi tiết & mở giấy phép (ghi audit_logs mỗi lần mở).
- Duyệt, từ chối (lý do >= 10 ký tự), thu hồi (lý do >= 10 ký tự), idempotent + chống ghi đè đồng thời (409).
Giới hạn: <= 200 dòng.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.company import Company
from app.models.company_logo import CompanyLogo
from app.models.company_verification import CompanyVerification
from app.models.job import Job
from app.models.user import User
from app.routers.admin_companies_cvs import _serialize_company
from app.services.company_verification_actions import reject_verification_request, revoke_company_verification
from app.services.company_verification_rules import VERIF_STATUS_LABELS
from app.services.company_verification_service import (
    LICENSE_PRIVATE_DIR, approve_verification_request, get_latest_verification, serialize_verification, write_verif_audit,
)
from app.services.employer_criteria_service import evaluate_employer_criteria, manual_approve_criterion

router = APIRouter(prefix="/admin", tags=["Admin Company Verifications"])


class ApproveBodyIn(BaseModel):
    version: Optional[int] = None
    checked_criteria: Optional[list[str]] = None


class ReasonActionBodyIn(BaseModel):
    reason: Optional[str] = None
    version: Optional[int] = None


def _require_admin_or_operator(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("admin", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Bạn không có quyền truy cập chức năng xét duyệt doanh nghiệp."},
        )
    return user


@router.get("/company-verifications", summary="Danh sách công ty & hồ sơ xác minh kèm bộ đếm theo trạng thái")
def list_admin_company_verifications(
    request: Request,
    verif_status: str = Query("all"),
    logo_status: str = Query("all"),
    has_unchecked: bool = Query(False),
    has_open_reports: bool = Query(False),
    q: str = Query("", max_length=120),
    current_user: User = Depends(_require_admin_or_operator),
    db: Session = Depends(get_db),
):
    count_rows = db.execute(
        select(Company.verification_status, func.count(Company.id)).group_by(Company.verification_status)
    ).all()
    counts = {"all": 0, "chua_xac_minh": 0, "cho_duyet": 0, "da_xac_minh": 0, "tu_choi": 0, "thu_hoi": 0, "logo_pending": 0}
    for st_key, cnt in count_rows:
        k = st_key or "chua_xac_minh"
        counts[k] = counts.get(k, 0) + int(cnt)
        counts["all"] += int(cnt)

    logo_pending_sub = select(CompanyLogo.company_id).where(CompanyLogo.status == "cho_duyet").distinct()
    logo_pending_cnt = db.scalar(select(func.count(Company.id)).where(or_(Company.logo_status == "pending", Company.id.in_(logo_pending_sub)))) or 0
    counts["logo_pending"] = int(logo_pending_cnt)
    all_pending_cnt = db.scalar(select(func.count(Company.id)).where(or_(Company.verification_status == "cho_duyet", Company.logo_status == "pending", Company.id.in_(logo_pending_sub)))) or 0
    counts["cho_duyet"] = int(all_pending_cnt)

    job_sub = (
        select(Job.company_id, func.count(Job.id).label("cnt"))
        .where(Job.status == "published")
        .group_by(Job.company_id)
        .subquery()
    )
    stmt = select(Company, func.coalesce(job_sub.c.cnt, 0).label("open_jobs")).outerjoin(
        job_sub, Company.id == job_sub.c.company_id
    )
    if verif_status == "cho_duyet":
        stmt = stmt.where(or_(Company.verification_status == "cho_duyet", Company.logo_status == "pending", Company.id.in_(logo_pending_sub)))
    elif verif_status in ("chua_xac_minh", "da_xac_minh", "tu_choi", "thu_hoi"):
        stmt = stmt.where(Company.verification_status == verif_status)

    if logo_status == "pending":
        stmt = stmt.where(or_(Company.logo_status == "pending", Company.id.in_(logo_pending_sub)))
    elif logo_status in ("active", "approved"):
        stmt = stmt.where(Company.logo_status.in_(["active", "approved"]))
    elif logo_status in ("removed", "missing"):
        stmt = stmt.where(Company.logo_status == logo_status)
    kw = q.strip()
    if kw:
        stmt = stmt.where(
            or_(Company.name.ilike(f"%{kw}%"), Company.tax_code.ilike(f"%{kw}%"), Company.slug.ilike(f"%{kw}%"))
        )

    rows = db.execute(stmt.order_by(Company.id.asc())).all()
    items = []
    for comp, open_jobs in rows:
        base_info = _serialize_company(db, request, comp, int(open_jobs or 0))
        latest = get_latest_verification(db, comp.id)
        verif_data = serialize_verification(db, comp, latest)
        base_info["verification_status"] = verif_data["verification_status"]
        base_info["verification_label"] = verif_data["status_label"]
        base_info["verification"] = verif_data["request"]
        criteria_data = evaluate_employer_criteria(db, comp)
        base_info["criteria_summary"] = criteria_data
        if has_unchecked and criteria_data["unchecked_count"] <= 0:
            continue
        if has_open_reports and criteria_data["open_reports_count"] <= 0:
            continue
        items.append(base_info)

    return {
        "items": items,
        "total": len(items),
        "counts": counts,
        "status_labels": VERIF_STATUS_LABELS,
        "viewer_role": current_user.role,
    }


@router.get("/company-verifications/{verif_id}", summary="Chi tiết một yêu cầu xác minh")
def get_admin_verification_detail(
    verif_id: int,
    current_user: User = Depends(_require_admin_or_operator),
    db: Session = Depends(get_db),
):
    verif = db.get(CompanyVerification, verif_id)
    if not verif:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Không tìm thấy yêu cầu xác minh."})
    comp = db.get(Company, verif.company_id)
    if not comp:
        raise HTTPException(status_code=404, detail={"code": "COMPANY_NOT_FOUND", "message": "Không tìm thấy công ty."})
    return serialize_verification(db, comp, verif)


@router.get("/company-verifications/{verif_id}/license", summary="Admin mở xem ảnh/PDF giấy phép (ghi audit_logs mỗi lần mở)")
def open_admin_verification_license(
    verif_id: int,
    current_user: User = Depends(_require_admin_or_operator),
    db: Session = Depends(get_db),
):
    verif = db.get(CompanyVerification, verif_id)
    if not verif:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Không tìm thấy yêu cầu xác minh."})
    comp = db.get(Company, verif.company_id)
    path = LICENSE_PRIVATE_DIR / verif.license_storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "Tệp giấy phép không tồn tại trên hệ thống lưu trữ."})

    display_name = verif.license_original_name or verif.license_storage_key
    write_verif_audit(
        db, current_user, "company_license", verif.id, "view_license",
        None, display_name, comp.name if comp else f"Company #{verif.company_id}",
    )
    db.commit()
    return FileResponse(path=str(path), media_type=verif.license_mime_type, filename=display_name, content_disposition_type="inline")


@router.post("/company-verifications/{verif_id}/approve", summary="Admin duyệt yêu cầu xác minh công ty")
def post_admin_approve_verification(
    verif_id: int,
    body: ApproveBodyIn = ApproveBodyIn(),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(_require_admin_or_operator),
    db: Session = Depends(get_db),
):
    return approve_verification_request(db, verif_id, current_user, body.version, idempotency_key, body.checked_criteria)


@router.post("/company-verifications/{verif_id}/reject", summary="Admin từ chối yêu cầu xác minh (lý do bắt buộc >= 10 ký tự)")
def post_admin_reject_verification(
    verif_id: int,
    body: ReasonActionBodyIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(_require_admin_or_operator),
    db: Session = Depends(get_db),
):
    return reject_verification_request(db, verif_id, current_user, body.reason, body.version, idempotency_key)


@router.post("/companies/{company_id}/revoke-verification", summary="Admin thu hồi xác minh công ty (lý do bắt buộc >= 10 ký tự)")
def post_admin_revoke_verification(
    company_id: int,
    body: ReasonActionBodyIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(_require_admin_or_operator),
    db: Session = Depends(get_db),
):
    return revoke_company_verification(db, company_id, current_user, body.reason, body.version, idempotency_key)


@router.post("/companies/{company_id}/criteria/{criterion_code}/approve", summary="Admin duyệt thủ công một tiêu chí xác thực (bắt buộc lý do)")
def post_admin_manual_approve_criterion(
    company_id: int,
    criterion_code: str,
    body: ReasonActionBodyIn,
    current_user: User = Depends(_require_admin_or_operator),
    db: Session = Depends(get_db),
):
    return manual_approve_criterion(db, company_id, criterion_code, body.reason, current_user)
