"""Router quản trị doanh nghiệp nổi bật & audit log (/api/admin/home/featured-companies & /api/admin/home/audit).
Tuân thủ Bước 3 & techrecruit-rules: < 195 dòng.
"""
from datetime import datetime, date
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.company import Company
from app.models.job import Job
from app.models.home_config import HomeFeaturedCompany, HomeConfigAudit, HomeSalarySettings
from app.models.user import User
from app.services.home_config_service import invalidate_home_cache, record_audit

router = APIRouter(prefix="/admin/home", tags=["Admin Home Companies & Audit"])


class FeaturedCompanyIn(BaseModel):
    company_id: int
    position: Optional[int] = Field(None, ge=1, le=20)


class UpdateFeaturedCompaniesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    reason: str
    companies: List[FeaturedCompanyIn]

    @field_validator("reason")
    @classmethod
    def check_reason(cls, v: str) -> str:
        s = v.strip() if isinstance(v, str) else ""
        if len(s) < 10:
            raise ValueError("Lý do bắt buộc tối thiểu 10 ký tự.")
        return s


@router.get("/featured-companies")
def get_admin_featured_companies(db: Session = Depends(get_db), admin: User = Depends(role_required("admin"))):
    today = date.today()
    subq = (
        select(Job.company_id, func.count(Job.id).label("open_jobs"))
        .where(Job.status == "published", Job.deleted_at.is_(None), (Job.deadline.is_(None) | (Job.deadline >= today)))
        .group_by(Job.company_id)
        .subquery()
    )
    stmt = (
        select(Company.id, Company.name, Company.logo_url, Company.logo_status, subq.c.open_jobs, HomeFeaturedCompany.position)
        .join(subq, Company.id == subq.c.company_id)
        .outerjoin(HomeFeaturedCompany, Company.id == HomeFeaturedCompany.company_id)
        .where((Company.is_verified == True) | (Company.verification_status == "da_xac_minh"), Company.is_visible == True, Company.is_draft == False)
    )
    rows = db.execute(stmt).all()
    items = []
    for r in rows:
        cid, name, logo, l_status, open_j, pos = r
        items.append({
            "company_id": cid,
            "name": name,
            "logo_url": logo if (logo and l_status != "removed") else None,
            "open_jobs": int(open_j or 0),
            "is_pinned": pos is not None,
            "position": pos,
        })
    items.sort(key=lambda x: (x["position"] if x["position"] is not None else 999, -x["open_jobs"], x["name"]))
    return {"companies": items}


@router.put("/featured-companies")
def update_admin_featured_companies(payload: UpdateFeaturedCompaniesIn, db: Session = Depends(get_db), admin: User = Depends(role_required("admin"))):
    comp_ids = [c.company_id for c in payload.companies]
    valid_comps = set(db.execute(
        select(Company.id).where(
            Company.id.in_(comp_ids),
            (Company.is_verified == True) | (Company.verification_status == "da_xac_minh"),
            Company.is_visible == True,
        )
    ).scalars().all())
    for cid in comp_ids:
        if cid not in valid_comps:
            raise HTTPException(status_code=422, detail=f"Công ty id {cid} chưa được xác minh hoặc không tồn tại.")

    before_rows = db.execute(select(HomeFeaturedCompany)).scalars().all()
    before = [{"company_id": r.company_id, "position": r.position} for r in before_rows]

    for r in before_rows:
        if r.company_id not in comp_ids:
            db.delete(r)

    for c in payload.companies:
        existing = db.scalar(select(HomeFeaturedCompany).where(HomeFeaturedCompany.company_id == c.company_id))
        if existing:
            existing.position = c.position
            existing.updated_by = admin.id
        else:
            db.add(HomeFeaturedCompany(company_id=c.company_id, position=c.position, updated_by=admin.id))

    record_audit(db, "companies", "update_companies", admin.id, before, [c.model_dump() for c in payload.companies], payload.reason)
    db.commit()
    invalidate_home_cache()
    return {"message": "Cập nhật doanh nghiệp nổi bật thành công"}


@router.get("/audit")
def get_admin_home_audit(
    section: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    stmt = select(HomeConfigAudit, User.email.label("actor_email"), User.full_name.label("actor_name")).outerjoin(User, HomeConfigAudit.actor_id == User.id)
    if section and section != "all":
        stmt = stmt.where(HomeConfigAudit.section == section)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(HomeConfigAudit.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()

    items = []
    for audit_obj, a_email, a_name in rows:
        items.append({
            "id": audit_obj.id,
            "section": audit_obj.section,
            "action": audit_obj.action,
            "actor_id": audit_obj.actor_id,
            "actor_name": a_name or (a_email.split("@")[0] if a_email else "Admin"),
            "before": json.loads(audit_obj.before_json) if audit_obj.before_json else None,
            "after": json.loads(audit_obj.after_json) if audit_obj.after_json else None,
            "reason": audit_obj.reason,
            "created_at": audit_obj.created_at.isoformat(),
        })
    return {"total": total or 0, "page": page, "page_size": page_size, "items": items}
