"""Router Giám sát ứng tuyển & Trao đổi Ứng viên - NTD cho Admin (/api/admin/applications).
Quy tắc: Quyền Admin (401/403/404), < 200 dòng.
"""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import role_required
from app.db.session import get_db
from app.models.application import Application, ApplicationStatusHistory, CV, MetaApplicationStatus
from app.models.company import Company
from app.models.job import Job
from app.models.user import User
from app.services.cv_service import get_cv_file_path
from app.schemas.application import AppTabOut, InterviewInfo, StatusHistoryItem
from app.schemas.employer_application import (
    AdminApplicationDetailOut,
    AdminAppEmployerOut,
    AdminApplicationItemOut,
    AdminApplicationListOut,
    ApplicantCandidateOut,
    ApplicantJobOut,
)

router = APIRouter(prefix="/admin/applications", tags=["Admin Applications Monitoring"])


def _smap(db: Session) -> dict[str, MetaApplicationStatus]:
    return {r.slug: r for r in db.scalars(select(MetaApplicationStatus)).all()}


@router.get("", response_model=AdminApplicationListOut, summary="Toàn bộ hồ sơ ứng tuyển toàn sàn")
def list_all_applications_admin(
    status_filter: str = Query("all", alias="status"),
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=50),
    current_user=Depends(role_required("admin")),
    db: Session = Depends(get_db),
):
    sm = _smap(db)

    # Đếm số lượng theo trạng thái
    raw_counts = dict(db.execute(select(Application.status, func.count(Application.id)).group_by(Application.status)).all())
    total_all = sum(raw_counts.values())

    tabs = [AppTabOut(key="all", label="Tất cả", count=total_all)]
    for meta in sorted(sm.values(), key=lambda m: m.sort_order):
        tabs.append(AppTabOut(key=meta.slug, label=meta.name, count=raw_counts.get(meta.slug, 0)))

    # Alias User cho NTD và Ứng viên
    cand_user = User
    base = (
        select(Application, Job.title.label("job_title"), cand_user, Job.employer_id, Company.name.label("company_name"))
        .join(Job, Application.job_id == Job.id)
        .join(cand_user, Application.candidate_id == cand_user.id)
        .outerjoin(Company, Job.company_id == Company.id)
    )

    if status_filter and status_filter != "all":
        base = base.where(Application.status == status_filter)

    keyword = q.strip()
    if keyword:
        base = base.where(
            cand_user.full_name.ilike(f"%{keyword}%")
            | cand_user.email.ilike(f"%{keyword}%")
            | Job.title.ilike(f"%{keyword}%")
            | Company.name.ilike(f"%{keyword}%")
        )

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(base.order_by(Application.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()

    # Thu thập employer users
    emp_ids = list({r[3] for r in rows if r[3]})
    emp_map = {}
    if emp_ids:
        emp_users = db.scalars(select(User).where(User.id.in_(emp_ids))).all()
        emp_map = {u.id: u for u in emp_users}

    items = []
    for app_row, j_title, cand, emp_id, comp_name in rows:
        meta = sm.get(app_row.status)
        emp = emp_map.get(emp_id)
        iv = None
        if app_row.interview_at:
            iv = InterviewInfo(
                interview_at=app_row.interview_at,
                interview_mode=app_row.interview_mode,
                interview_location=app_row.interview_location,
            )

        h_count = db.scalar(select(func.count(ApplicationStatusHistory.id)).where(ApplicationStatusHistory.application_id == app_row.id)) or 0

        items.append(AdminApplicationItemOut(
            id=app_row.id,
            job=ApplicantJobOut(id=app_row.job_id, title=j_title),
            candidate=ApplicantCandidateOut(id=cand.id, full_name=cand.full_name or "Ứng viên", email=cand.email, phone=cand.phone, avatar_url=cand.avatar_url),
            employer=AdminAppEmployerOut(id=emp_id or 0, full_name=emp.full_name if emp else "Nhà tuyển dụng", email=emp.email if emp else "", company_name=comp_name),
            cv_id=app_row.cv_id,
            cv_name=app_row.cv_name_snapshot or "",
            cover_letter=app_row.cover_letter,
            status=app_row.status,
            status_label=meta.name if meta else app_row.status,
            status_tone=meta.tone if meta else "neutral",
            created_at=app_row.created_at,
            interview=iv,
            history_count=h_count,
        ))

    return AdminApplicationListOut(items=items, tabs=tabs, total=total, page=page, page_size=page_size)


@router.get("/{app_id}", response_model=AdminApplicationDetailOut, summary="Chi tiết tương tác & lịch sử trao đổi")
def get_admin_application_detail(
    app_id: int,
    current_user=Depends(role_required("admin")),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(Application, Job.title.label("job_title"), User, Job.employer_id, Company.name.label("company_name"))
        .join(Job, Application.job_id == Job.id)
        .join(User, Application.candidate_id == User.id)
        .outerjoin(Company, Job.company_id == Company.id)
        .where(Application.id == app_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại.")

    app_row, j_title, cand, emp_id, comp_name = row
    emp = db.scalar(select(User).where(User.id == emp_id)) if emp_id else None
    sm = _smap(db)
    meta = sm.get(app_row.status)

    history_rows = db.scalars(
        select(ApplicationStatusHistory).where(ApplicationStatusHistory.application_id == app_id).order_by(ApplicationStatusHistory.changed_at.asc())
    ).all()
    history = [
        StatusHistoryItem(
            status=h.status, status_label=sm.get(h.status).name if sm.get(h.status) else h.status,
            status_tone=sm.get(h.status).tone if sm.get(h.status) else "neutral", note=h.note, changed_at=h.changed_at,
        ) for h in history_rows
    ]

    iv = None
    if app_row.interview_at:
        iv = InterviewInfo(
            interview_at=app_row.interview_at, interview_mode=app_row.interview_mode, interview_location=app_row.interview_location
        )

    return AdminApplicationDetailOut(
        id=app_row.id, job=ApplicantJobOut(id=app_row.job_id, title=j_title),
        candidate=ApplicantCandidateOut(id=cand.id, full_name=cand.full_name or "Ứng viên", email=cand.email, phone=cand.phone, avatar_url=cand.avatar_url),
        employer=AdminAppEmployerOut(id=emp_id or 0, full_name=emp.full_name if emp else "Nhà tuyển dụng", email=emp.email if emp else "", company_name=comp_name),
        cv_id=app_row.cv_id, cv_name=app_row.cv_name_snapshot, cover_letter=app_row.cover_letter,
        status=app_row.status, status_label=meta.name if meta else app_row.status, status_tone=meta.tone if meta else "neutral",
        created_at=app_row.created_at, updated_at=app_row.updated_at, interview=iv, history=history,
    )


@router.get("/{app_id}/cv", summary="Xem / Tải file CV của hồ sơ ứng tuyển dành cho Admin")
def get_admin_application_cv(
    app_id: int,
    current_user=Depends(role_required("admin")),
    db: Session = Depends(get_db),
):
    app_row = db.scalar(select(Application).where(Application.id == app_id))
    if not app_row or not app_row.cv_id:
        raise HTTPException(status_code=404, detail="Hồ sơ ứng tuyển không tồn tại hoặc không có CV.")
    cv = db.scalar(select(CV).where(CV.id == app_row.cv_id))
    if not cv:
        raise HTTPException(status_code=404, detail="Bản ghi CV không tồn tại.")
    fp = Path(get_cv_file_path(cv.stored_name))
    if not fp.is_file():
        raise HTTPException(status_code=404, detail="Tệp CV không tồn tại trên máy chủ.")
    ext = Path(cv.original_name or cv.stored_name).suffix.lower()
    mime = "application/pdf" if ext == ".pdf" else cv.mime_type or "application/octet-stream"
    return FileResponse(path=str(fp), media_type=mime, filename=cv.original_name, content_disposition_type="inline")

