"""admin_company_logos.py - Quản lý duyệt và từ chối logo công ty cho Admin (<= 150 dòng)."""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.company import Company
from app.models.company_logo import CompanyLogo
from app.models.user import User
from app.services.company_logo_service import clear_home_companies_cache
from app.services.notification import NotificationType, create_notification

router = APIRouter(prefix="/admin/company-logos", tags=["Admin Company Logos"])


class LogoItemOut(BaseModel):
    company_id: int
    company_name: str
    logo_url: str | None
    logo_status: str
    employer_id: int
    employer_name: str | None
    employer_email: str
    logo_uploaded_at: datetime | None


class LogoRejectIn(BaseModel):
    reason: str = Field(..., min_length=10, description="Lý do từ chối bắt buộc >= 10 ký tự")


class LogoListOut(BaseModel):
    items: list[LogoItemOut]
    total: int
    counts: dict[str, int]


@router.get("", response_model=LogoListOut)
def list_company_logos(
    status_filter: str = Query("pending", alias="status"),
    search: str = Query("", alias="q"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    query = (
        select(Company, User.email.label("emp_email"), User.full_name.label("emp_name"))
        .join(User, Company.employer_id == User.id)
        .where(Company.logo.is_not(None), Company.logo != "")
    )
    if status_filter and status_filter != "all":
        if status_filter == "pending":
            query = query.where(Company.logo_status.in_(["pending", "pending_review"]))
        elif status_filter == "approved":
            query = query.where(Company.logo_status.in_(["approved", "active"]))
        else:
            query = query.where(Company.logo_status == status_filter)

    if search.strip():
        term = f"%{search.strip()}%"
        query = query.where(Company.name.ilike(term) | User.email.ilike(term) | User.full_name.ilike(term))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    offset = (page - 1) * limit
    results = db.execute(query.order_by(Company.logo_uploaded_at.desc()).offset(offset).limit(limit)).all()

    counts = {
        "pending": db.scalar(select(func.count(Company.id)).where(Company.logo.is_not(None), Company.logo_status.in_(["pending", "pending_review"]))) or 0,
        "approved": db.scalar(select(func.count(Company.id)).where(Company.logo.is_not(None), Company.logo_status.in_(["approved", "active"]))) or 0,
        "rejected": db.scalar(select(func.count(Company.id)).where(Company.logo.is_not(None), Company.logo_status == "rejected")) or 0,
    }

    items = [
        LogoItemOut(
            company_id=comp.id,
            company_name=comp.name,
            logo_url=comp.logo_url or comp.logo,
            logo_status=comp.logo_status,
            employer_id=comp.employer_id,
            employer_name=emp_name,
            employer_email=emp_email,
            logo_uploaded_at=comp.logo_uploaded_at,
        )
        for comp, emp_email, emp_name in results
    ]
    return LogoListOut(items=items, total=total, counts=counts)


@router.post("/{company_id}/approve")
def approve_company_logo(
    company_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    comp = db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công ty.")
    old_status = comp.logo_status
    comp.logo_status = "approved"
    db.query(CompanyLogo).filter_by(company_id=comp.id, status="cho_duyet").update({"status": "dang_dung", "is_current": True})
    clear_home_companies_cache()

    # Gọi lại duyệt khi đã approved: không tạo thông báo mới
    if old_status not in ("approved", "active"):
        create_notification(
            db,
            user_id=comp.employer_id,
            actor_id=admin.id,
            type=NotificationType.LOGO_APPROVED,
            title="Logo công ty đã được duyệt",
            message=f"Logo của công ty {comp.name} đã được phê duyệt và hiển thị công khai.",
            link="/pages/employer/company-settings.html",
            ref_type="company_logo",
            ref_id=comp.id,
        )

    db.commit()
    return {"success": True, "message": f"Đã duyệt logo cho công ty {comp.name}.", "logo_status": "approved"}


@router.post("/{company_id}/reject")
def reject_company_logo(
    company_id: int,
    payload: LogoRejectIn,
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    comp = db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy công ty.")
    comp.logo_status = "rejected"
    db.query(CompanyLogo).filter_by(company_id=comp.id, status="cho_duyet").update({"status": "tu_choi"})
    clear_home_companies_cache()

    create_notification(
        db,
        user_id=comp.employer_id,
        actor_id=admin.id,
        type=NotificationType.LOGO_REJECTED,
        title="Logo công ty bị từ chối duyệt",
        message=f"Logo của công ty {comp.name} bị từ chối duyệt. Lý do: {payload.reason}",
        link="/pages/employer/company-settings.html",
        ref_type="company_logo",
        ref_id=comp.id,
    )

    db.commit()
    return {"success": True, "message": f"Đã từ chối logo cho công ty {comp.name}.", "logo_status": "rejected"}
