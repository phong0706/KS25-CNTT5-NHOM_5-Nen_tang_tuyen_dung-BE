"""Router Quản trị cấp cao: Công ty, Logo, CV ứng viên và Nhật ký thay đổi (/api/admin/...)."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from PIL import Image
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user, role_required
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.company_logo import CompanyLogo
from app.models.job import Job
from app.models.user import User
from app.services.company_logo_service import (
    approve_company_logo,
    clear_home_companies_cache,
    get_company_logo_state,
    get_logo_original_meta,
    upload_company_logo,
)
from app.services.company_verification_service import get_latest_verification, serialize_verification

router = APIRouter(prefix="/admin", tags=["Admin Companies & CVs Governance"])
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_LOGO_BYTES = 200 * 1024  # 200 KB
MAX_LOGO_DIM = 512  # 512 px


def _write_audit(
    db: Session, actor: User, target_type: str, target_id: int, action: str,
    old_val: str | None = None, new_val: str | None = None, target_label: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id, actor_name=actor.full_name or actor.email, actor_role=actor.role,
        target_type=target_type, target_id=target_id, target_label=target_label,
        action=action, old_value=old_val, new_value=new_val,
    )
    db.add(entry)
    return entry


def _full_logo_url(request: Request, rel_path: str | None) -> str | None:
    if not rel_path:
        return None
    if rel_path.startswith(("http://", "https://")):
        return rel_path
    base = str(request.base_url).rstrip("/")
    return f"{base}{rel_path if rel_path.startswith('/') else '/' + rel_path}"


def _serialize_company(db: Session, request: Request, comp: Company, open_jobs: int = 0) -> dict:
    u = db.get(User, comp.logo_uploaded_by) if comp.logo_uploaded_by else None
    uploader_name = (u.full_name if u else f"User #{comp.logo_uploaded_by}") if comp.logo_uploaded_by else None
    owner = db.get(User, comp.employer_id) if comp.employer_id else None
    logo_state = get_company_logo_state(db, comp, request)
    raw_logo_rel = comp.logo_url or comp.logo
    full_url = logo_state["logo_full_url"] or _full_logo_url(request, raw_logo_rel)
    logo_url = logo_state["logo_url"] or raw_logo_rel

    pending_logo = logo_state["pending_logo"]
    if not pending_logo and (comp.logo_status == "pending" or logo_state["status"] == "pending") and raw_logo_rel:
        meta = get_logo_original_meta(Path(raw_logo_rel).name) if raw_logo_rel else {"orig_width": 256, "orig_height": 256, "orig_ratio": 1.0}
        pending_logo = {
            "id": None, "version": comp.logo_version or 1,
            "file_key": Path(raw_logo_rel).name, "file_key_2x": Path(raw_logo_rel).name,
            "logo_url": raw_logo_rel, "logo_full_url": full_url,
            "logo_url_2x": None, "logo_full_url_2x": None, "original_url": full_url,
            "orig_width": meta["orig_width"], "orig_height": meta["orig_height"], "orig_ratio": meta["orig_ratio"],
            "uploader_name": uploader_name or (owner.full_name if owner else "Nhà tuyển dụng"),
            "created_at": comp.logo_uploaded_at.isoformat() if comp.logo_uploaded_at else "",
        }

    return {
        "id": comp.id, "name": comp.name, "slug": comp.slug,
        "employer_id": comp.employer_id,
        "employer_name": owner.full_name if owner else "Chưa gán",
        "employer_email": owner.email if owner else "",
        "tax_code": comp.tax_code, "size": comp.size or comp.company_size,
        "website": comp.website, "address": comp.address,
        "status": comp.status.value if hasattr(comp.status, "value") else str(comp.status),
        "open_jobs_count": int(open_jobs or 0),
        "logo": raw_logo_rel,
        "logo_url": logo_url,
        "logo_path": logo_state["logo_path"] or raw_logo_rel,
        "logo_full_url": full_url,
        "logo_url_2x": logo_state["logo_url_2x"],
        "logo_status": logo_state["status"],
        "logo_status_label": logo_state["label"],
        "logo_version": logo_state["logo_version"],
        "logo_uploaded_by": comp.logo_uploaded_by,
        "logo_uploaded_by_name": uploader_name,
        "logo_uploaded_at": comp.logo_uploaded_at.isoformat() if comp.logo_uploaded_at else None,
        "updated_at": comp.updated_at.isoformat() if comp.updated_at else None,
        "pending_logo": pending_logo,
    }


def _check_company_access(user: User, comp: Company):
    if user.role in ("admin", "operator") or (user.role in ("employer", "recruiter") and comp.employer_id == user.id):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền truy cập hoặc chỉnh sửa thông tin công ty của người khác.")


@router.get("/companies", summary="Danh sách công ty cho khu quản trị")
def list_admin_companies(
    request: Request, q: str = Query("", max_length=100), logo_status: str = Query("all"),
    current_user: User = Depends(role_required("admin", "operator")), db: Session = Depends(get_db),
):
    job_sub = select(Job.company_id, func.count(Job.id).label("cnt")).where(Job.status == "published").group_by(Job.company_id).subquery()
    stmt = select(Company, func.coalesce(job_sub.c.cnt, 0).label("open_jobs")).outerjoin(job_sub, Company.id == job_sub.c.company_id)
    kw = q.strip()
    if kw:
        stmt = stmt.where(or_(Company.name.ilike(f"%{kw}%"), Company.slug.ilike(f"%{kw}%")))
    if logo_status == "pending":
        logo_pending_sub = select(CompanyLogo.company_id).where(CompanyLogo.status == "cho_duyet").distinct()
        stmt = stmt.where(or_(Company.logo_status == "pending", Company.id.in_(logo_pending_sub)))
    elif logo_status in ("active", "approved"):
        stmt = stmt.where(Company.logo_status.in_(["active", "approved"]))
    elif logo_status in ("removed", "missing"):
        stmt = stmt.where(Company.logo_status == logo_status)
    rows = db.execute(stmt.order_by(Company.id.asc())).all()
    items = [_serialize_company(db, request, r[0], int(r[1] or 0)) for r in rows]
    return {"items": items, "total": len(items), "viewer_role": current_user.role}


@router.get("/companies/{company_id}", summary="Chi tiết công ty kèm thông tin logo và quyền sở hữu")
def get_admin_company_detail(
    company_id: int, request: Request, current_user: User = Depends(role_required("admin", "operator")), db: Session = Depends(get_db),
):
    comp = db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Không tìm thấy công ty.")
    open_jobs = db.scalar(select(func.count(Job.id)).where(and_(Job.company_id == company_id, Job.status == "published"))) or 0
    res = _serialize_company(db, request, comp, open_jobs)
    v_data = serialize_verification(db, comp, get_latest_verification(db, comp.id))
    res["verification_status"] = v_data["verification_status"]
    res["verification_label"] = v_data["status_label"]
    res["verification"] = v_data["request"]
    return res


@router.post("/companies/{company_id}/logo", summary="Upload/Thay logo công ty (PNG/JPEG/WebP, chuẩn hóa 256/512)")
def upload_company_logo_admin(
    company_id: int,
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(role_required("admin", "operator", "employer", "recruiter")),
    db: Session = Depends(get_db),
):
    comp = db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Không tìm thấy công ty.")
    _check_company_access(current_user, comp)

    raw_bytes = file.file.read()
    if not raw_bytes:
        raise HTTPException(status_code=422, detail="Tệp tải lên trống.")

    old_full = _full_logo_url(request, comp.logo_url or comp.logo)
    new_logo = upload_company_logo(db, comp.id, raw_bytes, current_user.id)
    approve_company_logo(db, new_logo.id, current_user.id, current_user.full_name or current_user.email, current_user.role)
    db.refresh(comp)

    open_jobs = db.scalar(select(func.count(Job.id)).where(and_(Job.company_id == comp.id, Job.status == "published"))) or 0
    res = _serialize_company(db, request, comp, open_jobs)
    res["old_logo_full_url"] = old_full
    return res
