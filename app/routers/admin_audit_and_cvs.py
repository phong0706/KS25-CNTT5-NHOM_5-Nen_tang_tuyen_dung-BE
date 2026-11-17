"""Router Quản trị cấp cao: Gỡ logo, Xóa công ty, Danh sách/Xem CV ứng viên & Nhật ký thay đổi.
Giới hạn: < 200 dòng.
"""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user, role_required
from app.db.session import get_db
from app.models.application import Application, CV
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.job import Job
from app.models.user import User
from app.routers.admin_companies_cvs import (
    _check_company_access,
    _full_logo_url,
    _serialize_company,
    _write_audit,
)

router = APIRouter(prefix="/admin", tags=["Admin Audit & CV Governance"])


@router.post("/companies/{company_id}/logo/remove", summary="Gỡ logo công ty (chỉ đổi trạng thái, không xóa file vật lý)")
def remove_company_logo_admin(
    company_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comp = db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Không tìm thấy công ty.")
    _check_company_access(current_user, comp)

    old_status = comp.logo_status or "active"
    comp.logo_status = "removed"
    full_url = _full_logo_url(request, comp.logo_url or comp.logo)
    _write_audit(
        db,
        current_user,
        "company_logo",
        comp.id,
        "remove_logo",
        f"{old_status} ({full_url or 'N/A'})",
        f"removed ({full_url or 'N/A'})",
        comp.name,
    )
    db.commit()
    db.refresh(comp)
    open_jobs = db.scalar(select(func.count(Job.id)).where(and_(Job.company_id == comp.id, Job.status == "published"))) or 0
    return _serialize_company(db, request, comp, open_jobs)


@router.delete("/companies/{company_id}", summary="Xóa công ty (chỉ dành cho Admin cấp cao)")
def delete_company_admin(
    company_id: int,
    current_user: User = Depends(role_required("admin")),
    db: Session = Depends(get_db),
):
    comp = db.get(Company, company_id)
    if not comp:
        raise HTTPException(status_code=404, detail="Không tìm thấy công ty.")
    name_snap = comp.name
    _write_audit(db, current_user, "company", comp.id, "delete_company", name_snap, "deleted", name_snap)
    db.delete(comp)
    db.commit()
    return {"message": f"Đã xóa công ty '{name_snap}' thành công.", "deleted_id": company_id}


@router.get("/candidate-cvs", summary="Danh sách CV ứng viên đã nộp kèm tin tuyển dụng và ngày nộp")
def list_admin_candidate_cvs(
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(role_required("admin", "operator")),
    db: Session = Depends(get_db),
):
    stmt = (
        select(
            Application,
            User.full_name.label("candidate_name"),
            User.email.label("candidate_email"),
            Job.title.label("job_title"),
            Company.name.label("company_name"),
            CV.original_name.label("cv_original_name"),
            CV.stored_name.label("cv_stored_name"),
            CV.size_bytes.label("cv_size_bytes"),
        )
        .join(User, Application.candidate_id == User.id)
        .join(Job, Application.job_id == Job.id)
        .outerjoin(Company, Job.company_id == Company.id)
        .outerjoin(CV, Application.cv_id == CV.id)
        .where(Application.cv_id.is_not(None))
    )
    kw = q.strip()
    if kw:
        stmt = stmt.where(
            or_(
                User.full_name.ilike(f"%{kw}%"),
                User.email.ilike(f"%{kw}%"),
                Job.title.ilike(f"%{kw}%"),
                Company.name.ilike(f"%{kw}%"),
                Application.cv_name_snapshot.ilike(f"%{kw}%"),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(Application.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()

    items = []
    for app_row, c_name, c_email, j_title, comp_name, cv_orig, cv_stored, cv_size in rows:
        items.append({
            "application_id": app_row.id,
            "cv_id": app_row.cv_id,
            "candidate_id": app_row.candidate_id,
            "candidate_name": c_name or "Ứng viên",
            "candidate_email": c_email or "",
            "job_id": app_row.job_id,
            "job_title": j_title or "Tin tuyển dụng",
            "company_name": comp_name or "Doanh nghiệp",
            "cv_name": app_row.cv_name_snapshot or cv_orig or "CV.pdf",
            "size_bytes": cv_size or 0,
            "submitted_at": app_row.created_at.isoformat() if app_row.created_at else None,
            "status": app_row.status,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/candidate-cvs/{app_id}/file", summary="Mở file CV cho khu quản trị (kiểm tra quyền, ghi nhật ký mỗi lần mở)")
def open_admin_candidate_cv_file(
    app_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role not in ("admin", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập tệp CV trong khu vực quản trị.",
        )

    app_row = db.get(Application, app_id)
    if not app_row or not app_row.cv_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn ứng tuyển hoặc đơn không có CV.")

    cv = db.get(CV, app_row.cv_id)
    if not cv or not cv.stored_name:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bản ghi CV không tồn tại.")

    cand = db.get(User, app_row.candidate_id)
    job = db.get(Job, app_row.job_id)

    cv_dir = Path(__file__).resolve().parent.parent.parent / "uploads" / "cvs"
    file_path = cv_dir / cv.stored_name
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File CV không tồn tại trên hệ thống lưu trữ.")

    display_name = app_row.cv_name_snapshot or cv.original_name or cv.stored_name
    label = f"{cand.full_name if cand else 'Ứng viên'} - {job.title if job else 'Tin tuyển dụng'}"
    _write_audit(db, current_user, "candidate_cv", app_row.id, "view_cv", None, display_name, label)
    db.commit()

    ext = Path(display_name).suffix.lower()
    mime = "application/pdf" if ext == ".pdf" else (cv.mime_type or "application/octet-stream")
    return FileResponse(path=str(file_path), media_type=mime, filename=display_name, content_disposition_type="inline")


@router.get("/audit-logs", summary="Danh sách nhật ký thay đổi hệ thống")
def list_admin_audit_logs(
    target_type: str = Query("all"),
    q: str = Query("", max_length=100),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(role_required("admin", "operator")),
    db: Session = Depends(get_db),
):
    stmt = select(AuditLog)
    if target_type and target_type != "all":
        stmt = stmt.where(AuditLog.target_type == target_type)
    kw = q.strip()
    if kw:
        stmt = stmt.where(
            or_(
                AuditLog.actor_name.ilike(f"%{kw}%"),
                AuditLog.target_label.ilike(f"%{kw}%"),
                AuditLog.action.ilike(f"%{kw}%"),
                AuditLog.old_value.ilike(f"%{kw}%"),
                AuditLog.new_value.ilike(f"%{kw}%"),
            )
        )
    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).limit(limit)).all()
    items = [
        {
            "id": r.id,
            "actor_id": r.actor_id,
            "actor_name": r.actor_name,
            "actor_role": r.actor_role,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "target_label": r.target_label,
            "action": r.action,
            "old_value": r.old_value,
            "new_value": r.new_value,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}
